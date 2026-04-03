import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION ---
# 1. These are the years we are MISSING (Everything except 2016-2023)
SEASONS_TO_SCRAPE = list(range(1997, 2016)) + [2024, 2025]

# 2. This is your source file (The 8 years you already have)
EXISTING_CSV = 'api_master_goals_8years.csv'

# 3. This is the NEW file name for the full history
OUTPUT_CSV = 'api_master_goals_ALL.csv'

MAX_WORKERS = 12 

def get_stealth_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'application/json'
    })
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[403, 429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
    session.mount('https://', adapter)
    return session

session = get_stealth_session()

def scrape_game_pbp(game_id):
    url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
    try:
        time.sleep(random.uniform(0.01, 0.05))
        resp = session.get(url, timeout=7)
        if resp.status_code == 404 or resp.status_code != 200:
            return None
            
        data = resp.json()
        season_year = int(str(game_id)[:4])
        game_goals = []
        local_names = {}
        
        for spot in data.get('rosterSpots', []):
            pid = spot.get('playerId')
            fn = spot.get('firstName', {}).get('default', '') if isinstance(spot.get('firstName'), dict) else spot.get('firstName', '')
            ln = spot.get('lastName', {}).get('default', '') if isinstance(spot.get('lastName'), dict) else spot.get('lastName', '')
            local_names[pid] = f"{fn} {ln}".strip()

        for play in data.get('plays', []):
            if str(play.get('typeDescKey', '')).lower() == 'goal':
                details = play.get('details', {})
                sid = details.get('scoringPlayerId')
                # Aggressive goalie detection for older API formats
                gid = details.get('goalieInNetId') or details.get('goalieId')
                
                if sid and gid:
                    game_goals.append({
                        'Shooter': local_names.get(sid, f"Unknown ({sid})"),
                        'Goalie': local_names.get(gid, f"Unknown ({gid})"),
                        'Year': season_year
                    })
        return game_goals
    except:
        return None

def run_full_history_scrape():
    start_time = time.time()
    
    # 1. LOAD EXISTING DATA
    print(f"--- 1. LOADING {EXISTING_CSV} ---")
    try:
        df_existing = pd.read_csv(EXISTING_CSV)
        # Ensure we use standard columns
        if 'Year' not in df_existing.columns:
            df_existing['Year'] = df_existing['Shooter_Year']
    except FileNotFoundError:
        print(f"ERROR: {EXISTING_CSV} not found.")
        return

    # 2. SCRAPE MISSING YEARS
    new_goals = []
    print(f"\n--- 2. SCRAPING {len(SEASONS_TO_SCRAPE)} MISSING SEASONS ---")
    
    for season in SEASONS_TO_SCRAPE:
        game_ids = [int(f"{season}02{g_num:04d}") for g_num in range(1, 1350)]
        season_total = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(scrape_game_pbp, gid) for gid in game_ids]
            for future in as_completed(futures):
                res = future.result()
                if res:
                    new_goals.extend(res)
                    season_total += len(res)
        
        print(f"[{season}] Finished. Found {season_total} goals.")

    # 3. MERGE AND CLEANUP
    print("\n--- 3. MERGING INTO NEW FILE AND CALCULATING ERAS ---")
    df_new = pd.DataFrame(new_goals)
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    
    # Calculate absolute debut year for every name across the entire history
    debuts = df_combined.groupby('Shooter')['Year'].min().to_dict()
    # Check goalies too (in case a goalie never scored a goal)
    goalie_debuts = df_combined.groupby('Goalie')['Year'].min().to_dict()
    
    # Merge the dictionaries
    for name, year in goalie_debuts.items():
        if name not in debuts or year < debuts[name]:
            debuts[name] = year

    # Apply the True Debut year to every row
    df_combined['Shooter_Year'] = df_combined['Shooter'].map(debuts)
    df_combined['Goalie_Year'] = df_combined['Goalie'].map(debuts)

    # Save to the brand new filename
    df_combined[['Shooter', 'Goalie', 'Shooter_Year', 'Goalie_Year']].to_csv(OUTPUT_CSV, index=False)
    
    print(f"\nSUCCESS! New file created: {OUTPUT_CSV}")
    print(f"Total Combined Goals: {len(df_combined)}")
    print(f"Total Scraping Time: {round((time.time() - start_time)/60, 2)} minutes.")

if __name__ == "__main__":
    run_full_history_scrape()
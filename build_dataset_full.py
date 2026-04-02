import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION ---
# We split the scraping into the years BEFORE your current dataset, and AFTER your current dataset.
SEASONS_TO_SCRAPE = [1997]
EXISTING_CSV = 'api_master_goals_8years.csv'
OUTPUT_CSV = 'api_master_goals_ALL.csv'

MAX_WORKERS = 12 # Fast but safe

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
        # Micro-delay: enough to bypass bot-detection, but extremely fast.
        time.sleep(random.uniform(0.01, 0.05))
        
        resp = session.get(url, timeout=7)
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            return None
            
        data = resp.json()
        season_year = int(str(game_id)[:4])
        game_goals =[]
        local_names = {}
        
        for spot in data.get('rosterSpots',[]):
            pid = spot.get('playerId')
            fname = spot.get('firstName', {}).get('default', '') if isinstance(spot.get('firstName'), dict) else spot.get('firstName', '')
            lname = spot.get('lastName', {}).get('default', '') if isinstance(spot.get('lastName'), dict) else spot.get('lastName', '')
            local_names[pid] = f"{fname} {lname}".strip()

        for play in data.get('plays',[]):
            if str(play.get('typeDescKey', '')).lower() == 'goal':
                details = play.get('details', {})
                shooter_id = details.get('scoringPlayerId')
                goalie_id = details.get('goalieInNetId')
                
                if shooter_id and goalie_id:
                    game_goals.append({
                        'Shooter_ID': shooter_id,
                        'Goalie_ID': goalie_id,
                        'Shooter': local_names.get(shooter_id, f"Unknown ({shooter_id})"),
                        'Goalie': local_names.get(goalie_id, f"Unknown ({goalie_id})"),
                        'Year': season_year
                    })
        return game_goals
    except Exception as e:
        return None

def run_resume_scrape():
    start_time = time.time()
    
    # 1. LOAD YOUR EXISTING 8-YEAR DATA
    print(f"--- 1. LOADING EXISTING DATA ---")
    try:
        df_existing = pd.read_csv(EXISTING_CSV)
        print(f"Loaded {len(df_existing)} goals from {EXISTING_CSV}.")
    except FileNotFoundError:
        print(f"ERROR: Could not find {EXISTING_CSV}. Make sure it is in the same folder.")
        return

    # 2. SCRAPE THE MISSING YEARS
    new_goals =[]
    print(f"\n--- 2. SCRAPING MISSING SEASONS ---")
    
    for season in SEASONS_TO_SCRAPE:
        # Older seasons had fewer games, but 1350 is a safe ceiling to catch everything.
        game_ids =[int(f"{season}02{g_num:04d}") for g_num in range(1, 1350)]
        season_total = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_game = {executor.submit(scrape_game_pbp, gid): gid for gid in game_ids}
            count = 0
            for future in as_completed(future_to_game):
                count += 1
                res = future.result()
                if res:
                    new_goals.extend(res)
                    season_total += len(res)
                
                if count % 100 == 0:
                    print(f"[{season}] Checked {count}/{len(game_ids)} games... (Found {season_total} goals)", end='\r')
        
        print(f"\n[{season}] Finished. Found {season_total} total goals.")

    # 3. MERGE AND CLEANUP
    print("\n--- 3. MERGING AND CALCULATING TRUE ERAS ---")
    df_new = pd.DataFrame(new_goals)
    
    # Ensure Column consistency
    required_cols = ['Shooter', 'Goalie', 'Shooter_Year', 'Goalie_Year']
    
    # --- IF THE NEW DATA IS MISSING YEAR COLUMNS, ADD THEM ---
    # We assign them the 'Year' value from the scrape for now
    if 'Shooter_Year' not in df_new.columns:
        df_new['Shooter_Year'] = df_new['Year']
        df_new['Goalie_Year'] = df_new['Year']
        
    # Combine old data with new data
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    
    # --- FIX: ROBUST DEBUT YEAR CALCULATION ---
    # Create a mapping of Name -> Year
    # We look at every row where this player is a Shooter OR a Goalie
    shooter_years = df_combined[['Shooter', 'Shooter_Year']].rename(columns={'Shooter': 'Name', 'Shooter_Year': 'Year'})
    goalie_years = df_combined[['Goalie', 'Goalie_Year']].rename(columns={'Goalie': 'Name', 'Goalie_Year': 'Year'})
    
    # Concat and find the minimum year for every player name
    debuts = pd.concat([shooter_years, goalie_years]).groupby('Name')['Year'].min().to_dict()

    # Re-apply these debut years to every single row in the master file
    df_combined['Shooter_Year'] = df_combined['Shooter'].map(debuts)
    df_combined['Goalie_Year'] = df_combined['Goalie'].map(debuts)

    # Final sort and save
    df_combined = df_combined[required_cols]
    df_combined.to_csv(OUTPUT_CSV, index=False)
    
    print(f"\nSUCCESS! Ultimate Dataset Created: {OUTPUT_CSV}")
    print(f"Total Combined Goals: {len(df_combined)}")
    print(f"Time taken to scrape missing years: {round((time.time() - start_time)/60, 2)} minutes.")

if __name__ == "__main__":
    run_resume_scrape()
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION ---
START_SEASON = 2016
END_SEASON = 2023
MAX_WORKERS = 5      # Lowered to 5. It's slower, but flies under the radar.
OUTPUT_CSV = 'api_master_goals_8years.csv'

def get_stealth_session():
    """ Creates a web session that looks like a real browser and auto-retries """
    session = requests.Session()
    
    # 1. Pretend to be a real human using Google Chrome
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'application/json'
    })
    
    # 2. Auto-Retry: If the server says "Too Many Requests" (429) or blocks us (403), wait and try again
    retry = Retry(
        total=5, 
        backoff_factor=1, # Waits 1s, then 2s, then 4s...
        status_forcelist=[403, 429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
    session.mount('https://', adapter)
    return session

# Create our global session
session = get_stealth_session()

def scrape_game_pbp(game_id):
    url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
    try:
        # Add a random micro-delay to simulate human clicking and prevent firewall triggers
        time.sleep(random.uniform(0.1, 0.4))
        
        resp = session.get(url, timeout=10)
        
        # If a game doesn't exist (like a cancelled game), it usually returns 404
        if resp.status_code == 404:
            return None
            
        # If we hit this, the firewall caught us even with the retries
        if resp.status_code != 200:
            print(f"\n[WARNING] Game {game_id} blocked. Status: {resp.status_code}")
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

def run_stealth_scrape():
    all_goals =[]
    start_time = time.time()

    print(f"--- STARTING STEALTH PBP SCRAPE ({START_SEASON}-{END_SEASON}) ---")
    print("This will take a bit longer to respect server limits. Please wait...\n")

    for season in range(START_SEASON, END_SEASON + 1):
        game_ids =[int(f"{season}02{g_num:04d}") for g_num in range(1, 1350)]
        season_total = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_game = {executor.submit(scrape_game_pbp, gid): gid for gid in game_ids}
            
            count = 0
            for future in as_completed(future_to_game):
                count += 1
                res = future.result()
                
                if res:
                    all_goals.extend(res)
                    season_total += len(res)
                
                # Print exactly what the script is seeing so you aren't left guessing
                if count % 50 == 0:
                    print(f"[{season}] Checked {count}/{len(game_ids)} games... (Found {season_total} goals so far)", end='\r')
        
        print(f"\n[{season}] Finished. Found {season_total} total goals.")

    print(f"\n--- ALL SEASONS SCRAPED ---")
    
    if not all_goals:
        print("Error: No data found. The firewall might be temporarily blocking you.")
        return

    df = pd.DataFrame(all_goals)

    print("Standardizing Player Eras...")
    player_first_years = df.groupby('Shooter_ID')['Year'].min().to_dict()
    goalie_first_years = df.groupby('Goalie_ID')['Year'].min().to_dict()
    
    master_year_map = player_first_years.copy()
    for pid, year in goalie_first_years.items():
        if pid not in master_year_map or year < master_year_map[pid]:
            master_year_map[pid] = year

    df['Shooter_Year'] = df['Shooter_ID'].map(master_year_map)
    df['Goalie_Year'] = df['Goalie_ID'].map(master_year_map)

    df[['Shooter', 'Goalie', 'Shooter_Year', 'Goalie_Year']].to_csv(OUTPUT_CSV, index=False)
    
    print(f"\nSUCCESS! Total Goals Saved: {len(df)}")
    print(f"Total time: {round((time.time() - start_time)/60, 2)} minutes.")

if __name__ == "__main__":
    run_stealth_scrape()
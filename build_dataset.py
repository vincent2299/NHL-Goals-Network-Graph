import requests
import pandas as pd
import time

def build_master_dataset(start_year, end_year):
    print(f"--- STARTING NHL API SCRAPE ({start_year} to {end_year}) ---")
    
    all_goals =[]
    player_names = {}
    player_years = {}

    # Loop through the seasons
    for season in range(start_year, end_year + 1):
        print(f"\nScraping {season}-{season+1} Season...")
        
        # There are roughly 1,312 games in a modern NHL season. 
        # We will loop through game IDs: [Year] + [02 for Regular Season] +[Game Number 0001 to 1350]
        # Example: 2023020001
        
        consecutive_errors = 0
        for game_num in range(1, 1350):
            game_id = int(f"{season}02{game_num:04d}")
            url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
            
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code != 200:
                    consecutive_errors += 1
                    if consecutive_errors > 20:
                        # If we hit 20 missing games in a row, the season is probably over.
                        break
                    continue
                
                # Reset error counter if we hit a valid game
                consecutive_errors = 0
                data = resp.json()
                
                # 1. Update Player Dictionary
                for spot in data.get('rosterSpots',[]):
                    pid = spot.get('playerId')
                    fname = spot.get('firstName', {}).get('default', '') if isinstance(spot.get('firstName'), dict) else spot.get('firstName', '')
                    lname = spot.get('lastName', {}).get('default', '') if isinstance(spot.get('lastName'), dict) else spot.get('lastName', '')
                    player_names[pid] = f"{fname} {lname}".strip()
                    
                    if pid not in player_years or season < player_years[pid]:
                        player_years[pid] = season

                # 2. Extract Goals
                for play in data.get('plays',[]):
                    if play.get('typeDescKey') == 'goal':
                        details = play.get('details', {})
                        shooter_id = details.get('scoringPlayerId')
                        goalie_id = details.get('goalieInNetId')
                        
                        if shooter_id and goalie_id:
                            all_goals.append({
                                'Shooter': player_names.get(shooter_id, f"Unknown ({shooter_id})"),
                                'Goalie': player_names.get(goalie_id, f"Unknown ({goalie_id})"),
                                'Shooter_Year': player_years.get(shooter_id, season),
                                'Goalie_Year': player_years.get(goalie_id, season)
                            })
                            
            except Exception as e:
                print(f"Error on game {game_id}: {e}")
                continue
                
            # Sleep for a tiny fraction of a second so we don't accidentally DDOS the NHL API
            time.sleep(0.05)
            
            if game_num % 100 == 0:
                print(f"   ...scraped {game_num} games...")

    print("\n--- SCRAPE COMPLETE ---")
    df = pd.DataFrame(all_goals)
    
    # Save it to a CSV so your Flask app can load it instantly!
    df.to_csv('api_master_goals.csv', index=False)
    print(f"Saved {len(df)} total goals to 'api_master_goals.csv'!")

if __name__ == "__main__":
    # CHANGE THIS TO 1997 IF YOU WANT ALL OF MODERN NHL HISTORY
    # (Warning: 1997 to 2023 will take hours to run!)
    build_master_dataset(start_year=2021, end_year=2023)
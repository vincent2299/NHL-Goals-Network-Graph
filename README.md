# 🏒 NHL Goal Network Universe (1997–Present)


<div align="center">
  <video src="https://github.com/user-attachments/assets/897b59a3-8f0a-4da1-bf04-05f8357b30c8" width="100%" controls autoplay loop muted>
  </video>
</div>

An interactive, high-performance network visualization mapping modern NHL history. Inspired by the viral MLB Home Run Network video, this project maps the relationship between **Shooters** and **Goalies** from the dawn of the NHL's digital Play-by-Play era (1997) to today. 

Players are rendered in a chronological "Horseshoe" layout, where the veterans of the late 90s (Red) bleed seamlessly into the modern superstars of today (Blue).

## ✨ Features

* **Chronological Horseshoe Layout:** Python mathematically positions players in a semi-circle based on their NHL debut year.
* **High-Performance GPU Rendering:** Uses **Sigma.js** and **Graphology** to tap directly into WebGL, smoothly displaying tens of thousands of nodes and curved edges at 60 FPS without browser lag.
* **Connection Pathfinder:** Calculates the shortest "Six Degrees of Kevin Bacon" path between any two players in modern NHL history.
* **Isolate & Inspect:** Search for or click any player to instantly dim the universe and illuminate all the goalies they've scored on (or shooters that scored on them).
* **Longest Chain Algorithm:** Uses a custom Bidirectional Breadth-First Search (BFS) to find the longest contiguous chain of goals in the dataset.

## 🛠️ The Tech Stack

* **Backend:** Python, Flask
* **Data Processing:** Pandas, NetworkX (for graph physics, layouts, and initial path calculations)
* **Frontend:** HTML/CSS, Vanilla JavaScript, Sigma.js, Graphology
* **Web Scraping:** `requests`, `concurrent.futures` (Multithreading)

## 📊 The Data Pipeline (The RTSS Era)

The NHL officially launched its digital Real-Time Scoring System (RTSS) in the 1997-1998 season. To capture this massive dataset without triggering API rate limits, this project uses a custom, multi-threaded Python scraper.

The scraper targets the NHL's live `/play-by-play` endpoint, utilizing a persistent `requests.Session()` with an Exponential Backoff Retry Strategy. This allows it to safely and politely download the play-by-play data for roughly ~35,000 games, accurately mapping the Shooter ID to the Goalie in net for over a quarter-century of hockey.

---

## 🚀 Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/NHL-Goal-Network.git
cd NHL-Goal-Network2. Install Dependencies
```
### 2. Install Dependencies
Ensure you have Python 3 installed, then run:

```bash
pip install flask pandas networkx requests
```

### 3. Build the Dataset

Note: Because the full dataset contains over 150,000+ goals, you must build the CSV locally (or download the one that is commited on the REPO).

Run the scraper to pull the data from the NHL API. (You can configure the START_SEASON and END_SEASON inside the file).
```bash
python build_dataset_safe.py
```
### 4. Run the Web App

Once your master CSV file is generated, start the Flask server:
```bash
python app.py
```
Open your web browser and go to http://127.0.0.1:5000 to explore the hockey goal tree!

## 📂 Project Structure
```Text

NHL-Goal-Network/
│
├── app.py                         # Main Flask API & NetworkX logic
|
├── build_dataset.py         # Initial single-threaded scraper (not recommended)
├── build_dataset_safe.py    # Multi-threaded (recommended for testing)
├── build_dataset_full.py    # Multi-threaded + full timeline (longer runtime)
|
├── build_dataset_safe.py          # Multi-threaded NHL API scraper
├── api_master_goals_ALL.csv       # (Generated) Master dataset
├── api_master_goals_8years.csv    # Sample dataset for quick testing
├── api_master_goals.csv           # Sample dataset for quick testing
|
│
└── templates/               
    └── index.html                 # Frontend UI, Sigma.js & Graphology Logic
```

## 🧠 Technical Highlights

- Smart Edge Filtering: To prevent the graph from becoming an illegible hairball, the Python backend aggregates the data and only draws visual edges between players who have a 2+ goal history against each other. (1-goal interactions are still mathematically counted in the player's total node size!).

- Algorithmic Layouts: Standard physics engines (like Force-Atlas) clump nodes together into a "snowball." This project calculates Polar coordinates (Angle/Radius) in Python to force the nodes into a distinct chronological arch before sending them to the Javascript renderer.

- Single-Page Application (SPA) Mechanics: Once the initial data payload is loaded, the UI relies heavily on Sigma.js Reducers to handle state changes (highlighting, dimming) instantly via the GPU without requiring page reloads or further API calls.

## 🙏 Acknowledgements

- Inspired by the viral MLB Home Run Graph video by adumb: https://youtu.be/LtJxJqAqt0Q?si=2Z1c9bC32VrlPT5W

- Data provided by the NHL API: https://github.com/Zmalski/NHL-API-Reference

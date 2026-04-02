from flask import Flask, render_template, request, jsonify
import pandas as pd
import networkx as nx
import math
import random

app = Flask(__name__)

# Global variables for instant access
G = nx.Graph()
GRAPH_JSON = {}
longest_path_global =[]

def interpolate_color(year_norm):
    """ Converts a 0.0 to 1.0 value into a Red -> Blue hex color """
    # Red: (231, 76, 60), Blue: (52, 152, 219)
    r = int(231 + (52 - 231) * year_norm)
    g = int(76 + (152 - 76) * year_norm)
    b = int(60 + (219 - 60) * year_norm)
    return f"#{r:02x}{g:02x}{b:02x}"

def calculate_horseshoe_layout(G, min_year, max_year):
    """ Maps players to a horseshoe shape based on their debut year """
    layout = {}
    for node, data in G.nodes(data=True):
        year = data.get('start_year', min_year)
        
        # 1. Normalize the year to a 0.0 -> 1.0 scale
        year_range = max_year - min_year
        if year_range == 0: year_range = 1
        year_norm = (year - min_year) / year_range
        
        # 2. Convert to an angle (Pi to 0 creates a left-to-right arch)
        # We add a tiny bit of random jitter so players from the same year don't form a perfect straight line
        jitter = random.uniform(-0.15, 0.15)
        angle = math.pi * (1.0 - year_norm) + jitter
        
        # 3. Random radius to create the "thickness" of the horseshoe band
        radius = random.uniform(100, 450)
        
        # 4. Convert Polar (Angle/Radius) to Cartesian (X/Y)
        # Note: We make Y negative so it arches upwards
        x = radius * math.cos(angle)
        y = -radius * math.sin(angle)
        
        # 5. Get color gradient
        color = interpolate_color(year_norm)
        
        layout[node] = {'x': x, 'y': y, 'color': color}
    return layout

def find_approximate_longest_path(graph):
    """ Super fast algorithm to find the longest chain in the network """
    try:
        largest_cc = max(nx.connected_components(graph), key=len)
        subgraph = graph.subgraph(largest_cc)
        start_node = random.choice(list(largest_cc))
        furthest_from_start = max(nx.single_source_shortest_path_length(subgraph, start_node).items(), key=lambda x: x[1])[0]
        longest_path_dict = nx.single_source_shortest_path(subgraph, furthest_from_start)
        furthest_node = max(longest_path_dict.keys(), key=lambda k: len(longest_path_dict[k]))
        return longest_path_dict[furthest_node]
    except:
        return[]

def initialize_data():
    global G, GRAPH_JSON, longest_path_global
    print("1. Loading CSV data...")
    try:
        df_raw = pd.read_csv('api_master_goals_ALL.csv')
    except FileNotFoundError:
        print("ERROR: CSV not found!")
        return

    df = df_raw.groupby(['Shooter', 'Goalie', 'Shooter_Year', 'Goalie_Year']).size().reset_index(name='Goals')
    
    
    # df = df[df['Goals'] >= 2]
    
    # THE FIX: Take the top 150 matchups from EVERY era equally!
    # df = df.sort_values(by='Goals', ascending=False).groupby('Shooter_Year').head(150)

    print("2. Building Graph...")
    for _, row in df.iterrows():
        shooter = row['Shooter']
        goalie = row['Goalie']
        goals = row['Goals']
        
        if not G.has_node(shooter): G.add_node(shooter, role='Shooter', total_goals=0, start_year=row['Shooter_Year'])
        if not G.has_node(goalie): G.add_node(goalie, role='Goalie', total_goals=0, start_year=row['Goalie_Year'])
            
        G.nodes[shooter]['total_goals'] += goals
        G.nodes[goalie]['total_goals'] += goals
        G.add_edge(shooter, goalie, weight=goals)

    print("3. Calculating Horseshoe Layout...")
    min_year = df['Shooter_Year'].min()
    max_year = df['Shooter_Year'].max()
    layout = calculate_horseshoe_layout(G, min_year, max_year)
    max_goals = max([G.nodes[n]['total_goals'] for n in G.nodes()]) if G.nodes() else 1

    # Format data for ECharts JS
    echarts_nodes =[]
    for node, data in G.nodes(data=True):
        pos_data = layout[node]
        # Size: minimum 2, maximum 15
        size = 2 + (data['total_goals'] / max_goals) * 13
        
        echarts_nodes.append({
            "id": node,
            "name": node,
            "x": pos_data['x'],
            "y": pos_data['y'],
            "symbolSize": size,
            "itemStyle": {"color": pos_data['color']},
            "attributes": {
                "role": data['role'],
                "era": data['start_year'],
                "goals": data['total_goals']
            }
        })

    # --- OPTIMIZATION: THE EDGE FILTER ---
    echarts_edges =[]
    for u, v, data in G.edges(data=True):
        # We ONLY draw the line if there are 2 or more goals.
        # This removes ~70% of the visual clutter/lag, but the total goals 
        # for the players (calculated above) remains 100% accurate!
        if data['weight'] >= 2:  
            echarts_edges.append({
                "source": u,
                "target": v,
                "value": data['weight']
            })

    GRAPH_JSON = {"nodes": echarts_nodes, "edges": echarts_edges}
    
    print("4. Calculating Longest Path...")
    longest_path_global = find_approximate_longest_path(G)
    print("--- SERVER READY! ---")


# --- FLASK ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/graph_data')
def get_graph_data():
    """ Sends the pre-calculated graph directly to JavaScript """
    return jsonify(GRAPH_JSON)

@app.route('/api/search')
def search_path():
    """ Instantly finds the path between two players via AJAX """
    p1 = request.args.get('p1')
    p2 = request.args.get('p2')
    
    if not p1 or not p2:
        return jsonify({"error": "Missing player names."})
        
    try:
        path = nx.shortest_path(G, source=p1, target=p2)
        return jsonify({"path": path})
    except nx.NetworkXNoPath:
        return jsonify({"error": f"No connection found between {p1} and {p2}."})
    except nx.NodeNotFound:
        return jsonify({"error": "One of those players is not in this dataset. Check spelling!"})

@app.route('/api/longest')
def get_longest():
    """ Returns the pre-calculated longest path """
    return jsonify({"path": longest_path_global})

if __name__ == '__main__':
    initialize_data()
    app.run(debug=False)
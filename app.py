from flask import Flask, render_template, request, jsonify
import pandas as pd
import networkx as nx
import math
import random
import os # Make sure os is imported

app = Flask(__name__)

# Global variables that will hold our data
G = nx.Graph()
pos = None
longest_path_global = []

# --- THIS IS THE MISSING FUNCTION! ---
def initialize_data():
    global G, pos, longest_path_global
    print("1. Loading Master API Dataset...")
    try:
        df_raw = pd.read_csv('api_master_goals_8years.csv')
    except FileNotFoundError:
        print("ERROR: 'api_master_goals_8years.csv' not found. Make sure it's in the same folder.")
        return

    df = df_raw.groupby(['Shooter', 'Goalie', 'Shooter_Year', 'Goalie_Year']).size().reset_index(name='Goals')
    
    print("2. Building Graph...")
    for _, row in df.iterrows():
        shooter, goalie, goals = row['Shooter'], row['Goalie'], row['Goals']
        if not G.has_node(shooter): G.add_node(shooter, role='Shooter', total_goals=0, start_year=row['Shooter_Year'])
        if not G.has_node(goalie): G.add_node(goalie, role='Goalie', total_goals=0, start_year=row['Goalie_Year'])
        G.nodes[shooter]['total_goals'] += goals
        G.nodes[goalie]['total_goals'] += goals
        G.add_edge(shooter, goalie, weight=goals)

    print("3. Calculating Horseshoe Layout...")
    min_year = min(df['Shooter_Year'].min(), df['Goalie_Year'].min())
    max_year = max(df['Shooter_Year'].max(), df['Goalie_Year'].max())
    pos = calculate_horseshoe_layout(G, min_year, max_year)
    
    print("4. Calculating Longest Path...")
    longest_path_global = find_approximate_longest_path(G)
    print("--- SERVER READY! ---")


def interpolate_color(year_norm):
    if year_norm < 0.5:
        t = year_norm * 2
        r, g, b = int(231 + (189 - 231) * t), int(76 + (195 - 76) * t), int(60 + (199 - 60) * t)
    else:
        t = (year_norm - 0.5) * 2
        r, g, b = int(189 + (52 - 189) * t), int(195 + (152 - 195) * t), int(199 + (219 - 199) * t)
    return f"#{r:02x}{g:02x}{b:02x}"

def calculate_horseshoe_layout(G, min_year, max_year):
    layout = {}
    for node, data in G.nodes(data=True):
        year = data.get('start_year', min_year)
        year_range = max_year - min_year
        if year_range == 0: year_range = 1
        year_norm = (year - min_year) / year_range
        jitter = random.uniform(-0.15, 0.15)
        angle = math.pi * (1.0 - year_norm) + jitter
        radius = random.uniform(80, 450)
        x, y = radius * math.cos(angle), -radius * math.sin(angle)
        color = interpolate_color(year_norm)
        layout[node] = {'x': x, 'y': y, 'color': color}
    return layout

def find_approximate_longest_path(graph):
    try:
        largest_cc = max(nx.connected_components(graph), key=len)
        subgraph = graph.subgraph(largest_cc)
        start_node = random.choice(list(largest_cc))
        furthest_from_start = max(nx.single_source_shortest_path_length(subgraph, start_node).items(), key=lambda x: x[1])[0]
        longest_path_dict = nx.single_source_shortest_path(subgraph, furthest_from_start)
        furthest_node = max(longest_path_dict.keys(), key=lambda k: len(longest_path_dict[k]))
        return longest_path_dict[furthest_node]
    except:
        return []

def create_graph_data(search_path=None, clicked_node=None):
    nodes_data, edges_data = [], []
    max_goals = max([G.nodes[n]['total_goals'] for n in G.nodes()]) if G.nodes() else 1
    
    clicked_neighbors = list(G.neighbors(clicked_node)) if clicked_node and G.has_node(clicked_node) else []
    path_edges_set = set()
    if search_path:
        for i in range(len(search_path) - 1):
            path_edges_set.add(frozenset([search_path[i], search_path[i+1]]))

    for node, data in G.nodes(data=True):
        layout_info = pos[node]
        size = 3 + (data['total_goals'] / max_goals) * 15
        color = layout_info['color']
        
        if search_path:
            color = '#f1c40f' if node in search_path else '#222'
            size += 6 if node in search_path else 0
        elif clicked_node:
            if node == clicked_node: color, size = '#f1c40f', size + 8
            elif node in clicked_neighbors: color, size = '#ffffff', size + 4
            else: color = '#222'

        nodes_data.append({
            "id": node, "name": node, "x": layout_info['x'], "y": layout_info['y'],
            "symbolSize": size, "itemStyle": {"color": color},
            "attributes": {"role": data['role'], "era": data['start_year'], "goals": data['total_goals']}
        })

    for u, v, data in G.edges(data=True):
        is_path_edge = search_path and frozenset([u, v]) in path_edges_set
        is_click_edge = clicked_node and (u == clicked_node or v == clicked_node)
        line_style = {
            "color": '#f1c40f' if is_path_edge or is_click_edge else 'rgba(255, 255, 255, 0.1)',
            "width": 2 if is_path_edge or is_click_edge else 0.1,
            "opacity": 1 if is_path_edge or is_click_edge else 0.1,
            "curveness": 0.1
        }
        edges_data.append({"source": u, "target": v, "lineStyle": line_style})

    return {"nodes": nodes_data, "edges": edges_data}

@app.route('/')
def home():
    p1, p2 = request.args.get('p1'), request.args.get('p2')
    get_longest = request.args.get('longest')
    clicked_node = request.args.get('clicked')
    
    path, error_msg = None, None

    if get_longest == 'true':
        path = longest_path_global
    elif p1 and p2:
        try:
            path = nx.shortest_path(G, source=p1, target=p2)
        except nx.NetworkXNoPath:
            error_msg = f"No connection found between {p1} and {p2}."
        except nx.NodeNotFound:
            error_msg = "One of those players not found. Check spelling!"

    graph_data_dict = create_graph_data(search_path=path, clicked_node=clicked_node)
    
    return render_template('index.html', graph_data=graph_data_dict, error=error_msg, path=path, clicked=clicked_node)

if __name__ == '__main__':
    initialize_data()
    app.run(debug=False)
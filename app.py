from flask import Flask, render_template, jsonify
import pandas as pd
import networkx as nx
import math
import random
import sys

app = Flask(__name__)

def get_color(year, min_y, max_y):
    try:
        norm = (year - min_y) / (max_y - min_y) if max_y != min_y else 0.5
        if norm < 0.5:
            t = norm * 2
            r, g, b = int(231 + (255-231)*t), int(76 + (255-76)*t), int(60 + (255-60)*t)
        else:
            t = (norm - 0.5) * 2
            r, g, b = int(255 + (52-255)*t), int(255 + (152-255)*t), int(255 + (219-255)*t)
        return f"#{r:02x}{g:02x}{b:02x}"
    except:
        return "#ffffff"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    try:
        # --- 1. LOAD DATA ---
        # Change this filename if you are using 'api_master_goals_8years.csv'
        filename = 'api_master_goals_ALL.csv'
        print(f"Loading {filename}...")
        df = pd.read_csv(filename)

        # --- 2. CLEAN DATA (Crucial Fix) ---
        # Remove any rows with missing names or years that break JSON
        df = df.dropna(subset=['Shooter', 'Goalie', 'Shooter_Year', 'Goalie_Year'])
        
        # Aggregate goals
        matchups = df.groupby(['Shooter', 'Goalie', 'Shooter_Year', 'Goalie_Year']).size().reset_index(name='count')
        
        if matchups.empty:
            return jsonify({"error": "No data found after cleaning"}), 400

        min_y = matchups['Shooter_Year'].min()
        max_y = matchups['Shooter_Year'].max()
        
        G = nx.Graph()
        
        # --- 3. BUILD GRAPH ---
        for _, row in matchups.iterrows():
            s, g = row['Shooter'], row['Goalie']
            if not G.has_node(s): 
                G.add_node(s, year=int(row['Shooter_Year']), goals=0, role='Shooter')
            if not G.has_node(g): 
                G.add_node(g, year=int(row['Goalie_Year']), goals=0, role='Goalie')
            
            G.nodes[s]['goals'] += row['count']
            G.nodes[g]['goals'] += row['count']
            
            if G.has_edge(s, g):
                G[s][g]['weight'] += row['count']
            else:
                G.add_edge(s, g, weight=row['count'])

        # --- 4. FORMAT FOR SIGMA ---
        max_g = max([d['goals'] for n, d in G.nodes(data=True)]) if G.nodes() else 1
        
        nodes_list = []
        for node, data in G.nodes(data=True):
            year_norm = (data['year'] - min_y) / (max_y - min_y) if max_y != min_y else 0.5
            angle = math.pi * (1.0 - year_norm) + random.uniform(-0.1, 0.1)
            radius = random.uniform(250, 600)
            
            nodes_list.append({
                "key": node,
                "label": node,
                "x": radius * math.cos(angle),
                "y": -radius * math.sin(angle),
                "size": 2 + (data['goals'] / max_g) * 15,
                "color": get_color(data['year'], min_y, max_y),
                "year": data['year'],
                "goals": data['goals'],
                "role": data['role']
            })

        edges_list = []
        for u, v, data in G.edges(data=True):
            if data['weight'] >= 1: # Keep performance high
                edges_list.append({"source": u, "target": v})

        print(f"Success! Sent {len(nodes_list)} nodes and {len(edges_list)} edges.")
        return jsonify({"nodes": nodes_list, "edges": edges_list})

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        # This sends the actual error back to the browser console for debugging
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
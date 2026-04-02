from flask import Flask, render_template, request
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import math

app = Flask(__name__)

G = nx.Graph()
pos = None

def initialize_data():
    global G, pos
    print("1. Loading Master API Dataset...")
    
    try:
        df_raw = pd.read_csv('api_master_goals.csv')
    except FileNotFoundError:
        print("ERROR: You need to run 'python build_dataset.py' first!")
        return

    print("2. Grouping matchups...")
    # Group by Shooter/Goalie to get total goals
    df = df_raw.groupby(['Shooter', 'Goalie', 'Shooter_Year', 'Goalie_Year']).size().reset_index(name='Goals')
    
    # Grab top 2000 matchups so the browser remains smooth
    df = df.sort_values(by='Goals', ascending=False).head(2000) 

    print("3. Building NetworkX graph...")
    for _, row in df.iterrows():
        shooter = row['Shooter']
        goalie = row['Goalie']
        goals = row['Goals']
        
        if not G.has_node(shooter):
            G.add_node(shooter, role='Shooter', total_goals=0, start_year=row['Shooter_Year'])
        if not G.has_node(goalie):
            G.add_node(goalie, role='Goalie', total_goals=0, start_year=row['Goalie_Year'])
            
        G.nodes[shooter]['total_goals'] += goals
        G.nodes[goalie]['total_goals'] += goals
        G.add_edge(shooter, goalie, weight=goals)

    print("4. Calculating Physics (Spreading out nodes)...")
    # k=1.5 forces them far apart
    pos = nx.spring_layout(G, k=1.5, iterations=150, seed=42)
    print("--- READY! ---")

def create_plotly_html(search_path=None):
    edge_x, edge_y = [], []
    path_edge_x, path_edge_y = [],[]
    
    path_edges =[]
    if search_path:
        for i in range(len(search_path)-1):
            path_edges.append((search_path[i], search_path[i+1]))
            path_edges.append((search_path[i+1], search_path[i]))

    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        if search_path and ((edge[0], edge[1]) in path_edges or (edge[1], edge[0]) in path_edges):
            path_edge_x.extend([x0, x1, None])
            path_edge_y.extend([y0, y1, None])
        else:
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

    traces =[go.Scatter(x=edge_x, y=edge_y, line=dict(width=0.3, color='rgba(255, 255, 255, 0.15)'), hoverinfo='none', mode='lines')]
    if search_path:
        traces.append(go.Scatter(x=path_edge_x, y=path_edge_y, line=dict(width=4, color='#f1c40f'), hoverinfo='none', mode='lines'))

    node_x, node_y, node_text, node_sizes, node_colors = [],[], [], [], []
    max_goals = max([G.nodes[n]['total_goals'] for n in G.nodes()]) if G.nodes() else 1

    for node in G.nodes():
        node_x.append(pos[node][0])
        node_y.append(pos[node][1])
        
        role = G.nodes[node]['role']
        goals = G.nodes[node]['total_goals']
        start_year = G.nodes[node]['start_year']
        
        node_text.append(
            f"<b style='font-size:16px;'>{node}</b><br>"
            f"<span style='color:#aaaaaa;'>Role:</span> {role}<br>"
            f"<span style='color:#aaaaaa;'>Debut Year:</span> {start_year}<br>"
            f"<span style='color:#aaaaaa;'>Goals Involved:</span> {goals}"
        )
        
        base_size = 8 + (goals / max_goals) * 30

        if search_path and node in search_path:
            node_colors.append('#f1c40f')  
            node_sizes.append(base_size + 15) 
        elif search_path:
            node_colors.append('#333333')  
            node_sizes.append(base_size)
        else:
            node_colors.append(start_year) 
            node_sizes.append(base_size)

    # Gradient: Red (Early) to Blue (Recent)
    red_to_blue_scale = [[0.0, '#e74c3c'],  # Red
        [0.5, '#bdc3c7'],  # Greyish-white
        [1.0, '#3498db']   # Blue
    ]

    if search_path:
        marker_config = dict(color=node_colors, size=node_sizes, line=dict(width=1, color='black'))
    else:
        marker_config = dict(
            showscale=True, colorscale=red_to_blue_scale, color=node_colors, size=node_sizes, 
            line=dict(width=1, color='rgba(255,255,255,0.4)'),
            colorbar=dict(title=dict(text="Start Year", font=dict(color="white")), tickfont=dict(color="white"))
        )

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode='markers', hoverinfo='text', text=node_text, marker=marker_config,
        hoverlabel=dict(bgcolor="rgba(20,20,20,0.9)", font_size=14, bordercolor="rgba(255,255,255,0.5)")
    )
    traces.append(node_trace)

    # Cleaned up the Modebar UI
    plotly_config = {
        'displayModeBar': True,
        'displaylogo': False,
        'scrollZoom': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'autoScale2d'] 
    }

    fig = go.Figure(data=traces, layout=go.Layout(
        showlegend=False, hovermode='closest', plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'),
        margin=dict(b=0, l=0, r=0, t=0), xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    ))

    return fig.to_html(full_html=False, include_plotlyjs='cdn', default_width='100%', default_height='100%', config=plotly_config)

@app.route('/')
def home():
    p1 = request.args.get('p1')
    p2 = request.args.get('p2')
    path, error_msg = None, None

    if p1 and p2:
        try:
            path = nx.shortest_path(G, source=p1, target=p2)
        except nx.NetworkXNoPath:
            error_msg = f"No connection found between {p1} and {p2}."
        except nx.NodeNotFound:
            error_msg = "One of those players is not in this dataset. Check spelling!"

    return render_template('index.html', graph_html=create_plotly_html(search_path=path), error=error_msg, path=path)

if __name__ == '__main__':
    initialize_data() 
    app.run(debug=False)
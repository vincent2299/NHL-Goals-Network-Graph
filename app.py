from flask import Flask, render_template, request
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
import math
import random

app = Flask(__name__)

G = nx.Graph()
pos = None
longest_path_global =[]

def find_approximate_longest_path(graph):
    """ Super fast algorithm to find the longest chain in the network """
    try:
        largest_cc = max(nx.connected_components(graph), key=len)
        subgraph = graph.subgraph(largest_cc)
        
        # 2-BFS Approximation: Pick a random node, find the furthest node from it.
        # Then find the furthest node from THAT node.
        start_node = random.choice(list(largest_cc))
        furthest_from_start = max(nx.single_source_shortest_path_length(subgraph, start_node).items(), key=lambda x: x[1])[0]
        
        longest_path_dict = nx.single_source_shortest_path(subgraph, furthest_from_start)
        furthest_node = max(longest_path_dict.keys(), key=lambda k: len(longest_path_dict[k]))
        return longest_path_dict[furthest_node]
    except:
        return[]

def initialize_data():
    global G, pos, longest_path_global
    print("1. Loading Master API Dataset...")
    
    try:
        df_raw = pd.read_csv('api_master_goals_8years.csv')
    except FileNotFoundError:
        print("ERROR: 'api_master_goals.csv' not found. Run the scraper first!")
        return

    print("2. Grouping matchups...")
    df = df_raw.groupby(['Shooter', 'Goalie', 'Shooter_Year', 'Goalie_Year']).size().reset_index(name='Goals')
    df = df.sort_values(by='Goals', ascending=False).head(2500) 

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
    # Increased k to 2.0 to force nodes further apart
    pos = nx.spring_layout(G, k=2.5, iterations=100)
    
    print("5. Calculating Longest Connection...")
    longest_path_global = find_approximate_longest_path(G)
    
    print("--- READY! ---")

def create_plotly_html(search_path=None, clicked_node=None):
    edge_x, edge_y = [],[]
    highlight_edge_x, highlight_edge_y = [],[]
    
    # Determine edges to highlight
    path_edges =[]
    if search_path:
        for i in range(len(search_path)-1):
            path_edges.append((search_path[i], search_path[i+1]))
            path_edges.append((search_path[i+1], search_path[i]))
            
    clicked_neighbors =[]
    if clicked_node and G.has_node(clicked_node):
        clicked_neighbors = list(G.neighbors(clicked_node))

    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        
        is_search_edge = search_path and ((edge[0], edge[1]) in path_edges or (edge[1], edge[0]) in path_edges)
        is_clicked_edge = clicked_node and (edge[0] == clicked_node or edge[1] == clicked_node)
        
        if is_search_edge or is_clicked_edge:
            highlight_edge_x.extend([x0, x1, None])
            highlight_edge_y.extend([y0, y1, None])
        else:
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

    # Background edges (Ultra thin and faint to prevent clumping)
    traces =[go.Scatter(x=edge_x, y=edge_y, line=dict(width=0.15, color='rgba(255, 255, 255, 0.1)'), hoverinfo='none', mode='lines')]
    
    # Highlighted edges
    if search_path or clicked_node:
        traces.append(go.Scatter(x=highlight_edge_x, y=highlight_edge_y, line=dict(width=2, color='#f1c40f'), hoverinfo='none', mode='lines'))

    node_x, node_y, node_text, node_sizes, node_colors, custom_data = [], [], [], [], [], []
    max_goals = max([G.nodes[n]['total_goals'] for n in G.nodes()]) if G.nodes() else 1

    for node in G.nodes():
        node_x.append(pos[node][0])
        node_y.append(pos[node][1])
        custom_data.append(node) # Used for JS Click Events
        
        role = G.nodes[node]['role']
        goals = G.nodes[node]['total_goals']
        start_year = G.nodes[node]['start_year']
        
        node_text.append(
            f"<b style='font-size:16px;'>{node}</b><br>"
            f"<span style='color:#aaaaaa;'>Role:</span> {role}<br>"
            f"<span style='color:#aaaaaa;'>Debut Year:</span> {start_year}<br>"
            f"<span style='color:#aaaaaa;'>Goals Involved:</span> {goals}"
        )
        
        # DRASTICALLY REDUCED SIZING: Min 3px, Max 15px
        base_size = 2 + (goals / max_goals) * 8

        # State 1: Search Path Active
        if search_path:
            if node in search_path:
                node_colors.append('#f1c40f')  # Gold
                node_sizes.append(base_size + 8)
            else:
                node_colors.append('#222222')  # Super Dim
                node_sizes.append(base_size)
                
        # State 2: Clicked Node Active
        elif clicked_node:
            if node == clicked_node:
                node_colors.append('#f1c40f')  # Gold
                node_sizes.append(base_size + 10)
            elif node in clicked_neighbors:
                node_colors.append('#ffffff')  # White for neighbors
                node_sizes.append(base_size + 4)
            else:
                node_colors.append('#222222')  # Super Dim
                node_sizes.append(base_size)
                
        # State 3: Default View
        else:
            node_colors.append(start_year) 
            node_sizes.append(base_size)

    # Red (Early) to Blue (Recent) Gradient
    red_to_blue_scale = [
        [0.0, '#e74c3c'],  # Red[0.5, '#bdc3c7'],  # Greyish
        [1.0, '#3498db']   # Blue
    ]

    if search_path or clicked_node:
        marker_config = dict(color=node_colors, size=node_sizes, line=dict(width=0.5, color='black'))
    else:
        marker_config = dict(
            showscale=True, colorscale=red_to_blue_scale, color=node_colors, size=node_sizes, 
            line=dict(width=0.5, color='rgba(0,0,0,0.8)'),
            colorbar=dict(title=dict(text="Debut Year", font=dict(color="white")), tickfont=dict(color="white"))
        )

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode='markers', hoverinfo='text', text=node_text, marker=marker_config,
        customdata=custom_data, # Hidden data used by JS to know who was clicked
        hoverlabel=dict(bgcolor="rgba(20,20,20,0.9)", font_size=14, bordercolor="rgba(255,255,255,0.5)")
    )
    traces.append(node_trace)

    # Clean Modebar
    plotly_config = {
        'displayModeBar': True,
        'displaylogo': False,
        'scrollZoom': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'autoScale2d'] 
    }

    # Added top margin (t=40) so the Modebar doesn't overlap the plot area
    fig = go.Figure(data=traces, layout=go.Layout(
        showlegend=False, hovermode='closest', plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'),
        margin=dict(b=0, l=0, r=0, t=40), xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    ))

    return fig.to_html(full_html=False, include_plotlyjs='cdn', default_width='100%', default_height='100%', config=plotly_config)

@app.route('/')
def home():
    p1 = request.args.get('p1')
    p2 = request.args.get('p2')
    get_longest = request.args.get('longest')
    clicked_node = request.args.get('clicked')
    
    path = None
    error_msg = None

    if get_longest == 'true':
        path = longest_path_global
    elif p1 and p2:
        try:
            path = nx.shortest_path(G, source=p1, target=p2)
        except nx.NetworkXNoPath:
            error_msg = f"No connection found between {p1} and {p2}."
        except nx.NodeNotFound:
            error_msg = "One of those players is not in this dataset. Check spelling!"

    graph_html_snippet = create_plotly_html(search_path=path, clicked_node=clicked_node)
    return render_template('index.html', graph_html=graph_html_snippet, error=error_msg, path=path, clicked=clicked_node)

if __name__ == '__main__':
    initialize_data() 
    app.run(debug=False)
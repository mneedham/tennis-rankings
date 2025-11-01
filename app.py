import streamlit as st
import chdb
import pandas as pd
import re
from typing import Dict, List, Optional, Tuple

# Page configuration
st.set_page_config(
    page_title="Tennis Player Development Comparison",
    page_icon="🎾",
    layout="wide"
)

# Title and description
st.title("🎾 Tennis Player Development Comparison")
st.markdown(
    "Comparing WTA rankings at similar ages across five young players "
    "(lower ranking number = better performance)"
)

# Function to get all available players
@st.cache_data
def get_all_players():
    query = """
    SELECT DISTINCT json.player.fullName::String AS player_name
    FROM file('data/rankings.json.gz', JSONAsObject)
    WHERE json.player.fullName IS NOT NULL
    ORDER BY player_name::String
    """
    result = chdb.query(query, 'DataFrame')
    return result['player_name'].tolist()

# Function to generate dynamic query based on selected players
def generate_query(selected_players, min_age=0, max_age=50):
    if not selected_players:
        return None
    
    # Generate column selections
    column_selections = []
    where_conditions = []
    having_conditions = []
    
    for player in selected_players:
        # Create a safe column name
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', player.lower())
        
        # Add column selection
        column_selections.append(
            f"minIfOrNull(ranking::UInt16, player_name LIKE '%{player}%') AS {safe_name}_ranking"
        )
        
        # Add WHERE condition
        where_conditions.append(f"(json.player.fullName LIKE '%{player}%')")
        
        # Add to HAVING condition
        having_conditions.append(f"{safe_name}_ranking")
    
    columns_str = ',\n    '.join(column_selections)
    where_str = ' OR '.join(where_conditions)
    having_str = ', '.join(having_conditions)
    
    query = f"""
    SELECT
        age_years,
        age_months,
        concat(toString(age_years), 'y', if(age_months = 0, '', concat(' ', toString(age_months), 'm'))) AS age,
        {columns_str}
    FROM (
        SELECT
            json.player.fullName AS player_name,
            json.points AS points,
            json.ranking AS ranking,
            age('year', toDate(json.player.dateOfBirth), toDate(splitByChar('_', json._file)[1])) AS age_years,
            age('month', toDate(json.player.dateOfBirth), toDate(splitByChar('_', json._file)[1])) % 12 AS age_months
        FROM file('data/rankings.json.gz', JSONAsObject)
        WHERE {where_str}
    )
    GROUP BY age_years, age_months
    HAVING isNotNull(arrayFirstOrNull(x -> isNotNull(x), [{having_str}]))
        AND age_years >= {min_age}
        AND (age_years < {max_age} OR (age_years = {max_age} AND age_months = 0))
    ORDER BY age_years::UInt16 ASC, age_months::UInt16 ASC
    """
    
    return query

def create_ranking_table(rankings_data: Dict[str, Dict[str, int]], sorted_ages: List[str]) -> None:
    """Display rankings in a table with players as rows and ages as columns.
    
    Args:
        rankings_data: Dictionary mapping player names to their age-based rankings
        sorted_ages: List of age strings in the correct order
    """
    if not rankings_data or not sorted_ages:
        st.warning("No ranking data available.")
        return
    
    # Create table data
    table_data = []
    
    # Header row
    header = ["Player"] + sorted_ages
    table_data.append(header)
    
    # Data rows
    for player, rankings in rankings_data.items():
        row = [player]
        for age in sorted_ages:
            rank = rankings.get(age, '')
            row.append(rank if rank != '' else '-')
        table_data.append(row)
    
    # Display the table with custom styling
    st.markdown("""
        <style>
            .ranking-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 14px;
                margin: 20px 0;
            }
            .ranking-table th, .ranking-table td {
                padding: 10px 8px;
                text-align: center;
                border: 1px solid #ddd;
                min-width: 60px;
            }
            .ranking-table th {
                background-color: #2c3e50;
                color: white;
                font-weight: bold;
                position: sticky;
                top: 0;
                z-index: 10;
            }
            .ranking-table th:first-child {
                text-align: left;
                min-width: 150px;
                background-color: #34495e;
            }
            .ranking-table td:first-child {
                text-align: left;
                font-weight: bold;
                background-color: #ecf0f1;
                color: #000;
                position: sticky;
                left: 0;
                z-index: 5;
            }
            .ranking-table tbody tr:hover {
                background-color: #e3f2fd;
            }
            .ranking-table tbody tr:hover td {
                color: #000;
            }
            .ranking-table tbody tr:hover td:first-child {
                background-color: #bbdefb;
            }
            .best-rank {
                background-color: #27ae60 !important;
                color: white;
                font-weight: bold;
            }
            .ranking-table-container {
                overflow-x: auto;
                max-width: 100%;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Find best ranks for each age
    best_ranks = {}
    for age in sorted_ages:
        ranks = []
        for player, rankings in rankings_data.items():
            if age in rankings and rankings[age] is not None:
                ranks.append(rankings[age])
        best_ranks[age] = min(ranks) if ranks else None
    
    # Create HTML table with best ranks highlighted
    html = ['<div class="ranking-table-container">']
    html.append('<table class="ranking-table">')
    
    # Header
    html.append('<thead><tr>')
    for col_name in header:
        html.append(f'<th>{col_name}</th>')
    html.append('</tr></thead><tbody>')
    
    # Rows
    for row_idx, row in enumerate(table_data[1:], 1):  # Skip header row
        html.append('<tr>')
        for col_idx, cell in enumerate(row):
            if col_idx == 0:  # Player name column
                html.append(f'<td>{cell}</td>')
            else:
                age = header[col_idx]
                player = row[0]
                rank = rankings_data[player].get(age)
                if rank is not None:
                    cell_class = 'class="best-rank"' if rank == best_ranks.get(age) else ''
                    html.append(f'<td {cell_class}>{int(rank)}</td>')
                else:
                    html.append('<td>-</td>')
        html.append('</tr>')
    
    html.append('</tbody></table>')
    html.append('</div>')
    
    # Display the table
    st.markdown(''.join(html), unsafe_allow_html=True)
    
    # Add a legend
    st.markdown("""
        <div style="margin-top: 10px; font-size: 12px; color: #666;">
            <span style="background-color: #27ae60; color: white; padding: 2px 8px; border-radius: 3px; margin-right: 10px;">Green</span>
            = Best ranking for that age
        </div>
    """, unsafe_allow_html=True)

# Sidebar for player selection
st.sidebar.header("Player Selection")

# Get all players
all_players = get_all_players()

# Default players
default_players = [
    'Hannah Klugman',
    'Mika Stojsavljevic',
    'Mingge Xu',
]

# Filter default players to only include those that exist
default_players = [p for p in default_players if p in all_players]

# Multi-select for players
selected_players = st.sidebar.multiselect(
    "Select players to compare:",
    options=all_players,
    default=default_players,
    help="Select multiple players to compare their rankings at similar ages"
)

# Age filters
st.sidebar.markdown("---")
st.sidebar.markdown("**Age Filters**")

col1, col2 = st.sidebar.columns(2)
with col1:
    min_age = st.number_input("Min Age (years)", min_value=14, max_value=45, value=14, step=1)
with col2:
    max_age = st.number_input("Max Age (years)", min_value=14, max_value=45, value=45, step=1)


# Main content
if not selected_players:
    st.info("👈 Please select at least one player from the sidebar to begin comparison.")
else:
    st.subheader(f"Comparing {len(selected_players)} players")
    
    # Generate and execute query
    with st.spinner("Loading data..."):
        query = generate_query(selected_players, min_age, max_age)
        
        if query:
            try:
                # Execute query
                result_df = chdb.query(query, 'DataFrame')
                
                if not result_df.empty:
                    try:
                        # Restructure data for the new table format
                        rankings_data = {}
                        age_map = {}  # Map formatted age string to (years, months) for sorting
                        
                        # Initialize player entries
                        for player in selected_players:
                            safe_name = re.sub(r'[^a-zA-Z0-9]', '_', player.lower())
                            rankings_data[player] = {}
                        
                        # First pass: collect all unique age strings and their (years, months)
                        for idx, row in result_df.iterrows():
                            try:
                                age_years = int(row.get('age_years', 0))
                                age_months = int(row.get('age_months', 0))
                                age_str = row.get('age', '')
                                
                                if age_str and pd.notna(age_str):
                                    age_map[age_str] = (age_years, age_months)
                                    
                            except Exception as e:
                                st.warning(f"Error processing age in row {idx}: {str(e)}")
                        
                        # Sort ages based on years and months
                        sorted_ages = sorted(age_map.keys(), 
                                          key=lambda x: (age_map[x][0], age_map[x][1]))
                        
                        # Second pass: fill in the rankings
                        for idx, row in result_df.iterrows():
                            try:
                                age_str = str(row.get('age', '')).strip()
                                if not age_str or age_str.lower() == 'nan':
                                    continue
                                    
                                for player in selected_players:
                                    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', player.lower())
                                    rank_col = f'{safe_name}_ranking'
                                    
                                    if rank_col in row and pd.notna(row[rank_col]):
                                        try:
                                            rank = int(float(row[rank_col]))
                                            rankings_data[player][age_str] = rank
                                        except (ValueError, TypeError):
                                            continue
                            except Exception as e:
                                st.warning(f"Error processing row {idx}: {str(e)}")
                                continue
                        
                        # Display the table with the sorted ages
                        create_ranking_table(rankings_data, sorted_ages)
                        
                    except Exception as e:
                        st.error(f"Error in data processing: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
                    
                else:
                    st.warning("No data found for the selected players.")
                    
            except Exception as e:
                st.error(f"Error executing query: {str(e)}")
                with st.expander("View Query"):
                    st.code(query, language="sql")
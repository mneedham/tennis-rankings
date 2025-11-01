import streamlit as st
import chdb
import pandas as pd
import re

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
    FROM file('wta_rankings/*.jsonl', JSONAsObject)
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
            age('year', toDate(json.player.dateOfBirth), toDate(splitByChar('_', _file)[1])) AS age_years,
            age('month', toDate(json.player.dateOfBirth), toDate(splitByChar('_', _file)[1])) % 12 AS age_months
        FROM file('wta_rankings/*.jsonl', JSONAsObject)
        WHERE {where_str}
    )
    GROUP BY age_years, age_months
    HAVING isNotNull(arrayFirstOrNull(x -> isNotNull(x), [{having_str}]))
        AND age_years >= {min_age}
        AND (age_years < {max_age} OR (age_years = {max_age} AND age_months = 0))
    ORDER BY age_years::UInt16 ASC, age_months::UInt16 ASC
    """
    
    return query

# Function to style the dataframe
def style_dataframe(df, selected_players):
    if df.empty:
        return df
    
    # Get ranking columns (exclude age columns)
    ranking_cols = [col for col in df.columns if col not in ['age']]
    
    def highlight_best(row):
        styles = [''] * len(row)
        
        # Get values for ranking columns only
        ranking_values = []
        ranking_indices = []
        
        for i, col in enumerate(df.columns):
            if col != 'age':
                val = row[col]
                if pd.notna(val):
                    ranking_values.append(val)
                    ranking_indices.append(i)
        
        if ranking_values:
            min_val = min(ranking_values)
            # Highlight cells with the best (minimum) ranking in green
            for i in ranking_indices:
                val = row[df.columns[i]]
                if pd.notna(val) and val == min_val:
                    styles[i] = 'background-color: #4CAF50; color: white; font-weight: bold'
        
        return styles
    
    # Apply styling
    styled_df = df.style.apply(highlight_best, axis=1)
    
    # Format all columns as integers (no decimal places)
    format_dict = {col: '{:.0f}' for col in ranking_cols}
    styled_df = styled_df.format(format_dict, na_rep='')
    
    return styled_df

# Sidebar for player selection
st.sidebar.header("Player Selection")

# Get all players
all_players = get_all_players()

# Default players
default_players = [
    'Hannah Klugman',
    'Mika Stojsavljevic',
    'Mingge Xu',
    'Mirra Andreeva',
    'Iva Jovic'
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
                    # Rename columns for display
                    display_df = result_df.copy()
                    
                    # Create a mapping for column names (just player names, no "Age" label)
                    col_mapping = {}
                    for player in selected_players:
                        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', player.lower())
                        col_mapping[f'{safe_name}_ranking'] = player
                    
                    # Select and rename columns for display
                    display_cols = ['age'] + [col for col in display_df.columns if col.endswith('_ranking')]
                    display_df = display_df[display_cols]
                    display_df = display_df.rename(columns=col_mapping)
                    
                    # Convert ranking columns to integers
                    for player in selected_players:
                        if player in display_df.columns:
                            display_df[player] = display_df[player].astype('Int64')
                    
                    # Remove completely empty rows (where all player columns are null)
                    player_cols = [col for col in display_df.columns if col != 'age']
                    display_df = display_df[display_df[player_cols].notna().any(axis=1)]
                    
                    # Style and display the dataframe
                    styled_df = style_dataframe(display_df, selected_players)
                    
                    st.dataframe(
                        styled_df,
                        use_container_width=True,
                        hide_index=True
                    )
                                      
                        
                else:
                    st.warning("No data found for the selected players.")
                    
            except Exception as e:
                st.error(f"Error executing query: {str(e)}")
                with st.expander("View Query"):
                    st.code(query, language="sql")
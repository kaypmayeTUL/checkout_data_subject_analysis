"""
Library Word Cloud Generator - Multi-Collection Version (Fixed)
Upload your library CSV file (Physical, Digital, or COUNTER) and instantly generate word clouds!
"""

import streamlit as st
import pandas as pd
import numpy as np
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import plotly.express as px
from collections import Counter
import re
from io import BytesIO
import base64

# Page configuration
st.set_page_config(
    page_title="Library Word Cloud Generator",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better appearance
st.markdown("""
    <style>
    .uploadbox {
        border: 2px dashed #0066CC;
        border-radius: 10px;
        padding: 30px;
        text-align: center;
        background-color: #f0f8ff;
    }
    .main > div {
        padding-top: 2rem;
    }
    .stButton>button {
        background-color: #0066CC;
        color: white;
        font-weight: bold;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        border: none;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #0052A3;
    }
    div[data-testid="metric-container"] {
        background-color: #F0F8FF;
        border: 1px solid #B0C4DE;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .success-message {
        padding: 1rem;
        border-radius: 5px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

# LC Classification descriptions (simplified)
LC_CLASSIFICATIONS = {
    'A': 'General Works', 'B': 'Philosophy, Psychology, Religion',
    'C': 'Auxiliary Sciences of History', 'D': 'World History',
    'E': 'US History', 'F': 'History of the Americas',
    'G': 'Geography, Anthropology', 'H': 'Social Sciences',
    'J': 'Political Science', 'K': 'Law', 'L': 'Education',
    'M': 'Music', 'N': 'Fine Arts', 'P': 'Language and Literature',
    'Q': 'Science', 'R': 'Medicine', 'S': 'Agriculture',
    'T': 'Technology', 'U': 'Military Science', 'V': 'Naval Science',
    'Z': 'Bibliography, Library Science'
}

def clean_subject_term(term):
    """Clean and standardize subject terms"""
    if pd.isna(term) or term == '':
        return None
    
    term = str(term).strip()
    term = term.rstrip('.;')
    # Remove date ranges in parentheses
    term = re.sub(r'\s*\([0-9\-]+\)', '', term)
    # Standardize separators
    term = term.replace('--', ' - ')
    
    return term if term else None

def process_subjects(subjects_str, weight):
    """Process subject string into weighted dictionary"""
    if pd.isna(subjects_str) or subjects_str == '':
        return {}
    
    # Handle multiple subjects separated by semicolons
    subjects = str(subjects_str).split(';')
    weighted_subjects = {}
    
    for subject in subjects:
        cleaned = clean_subject_term(subject)
        if cleaned:
            weighted_subjects[cleaned] = weighted_subjects.get(cleaned, 0) + weight
    
    return weighted_subjects

# Main app
def main():
    
    # Header
    st.title("📚 Library Collection Use/Subject Analyzer")
    st.markdown("### Select your data type and upload your CSV to analyze subject trends weighted by usage.")
    
    # Data Type Selection (First step in sidebar)
    with st.sidebar:
        st.header("⚙️ Data Source")
        data_type = st.radio(
            "Select Data Collection Type:",
            ['Physical Collections', 'Digital Collections (Tulane Digital Library)', 'COUNTER Reports (e-resources)'],
            index=1,  # Default to Digital Collections
            help="This determines the required columns and usage metric."
        )
        st.markdown("---")

    # Column definitions based on data type
    if data_type == 'Physical Collections':
        WEIGHT_COL_ALIASES = ['Loans', 'Loans (Total)', 'Loans (In House + Not In House)', 'Checkouts', 'Circulation']
        METRIC_TITLE = "Total Checkouts"
        METRIC_UNIT = "Checkouts"
        FILTER_COLS = {
            'Location': ['Location Name', 'Location'],
            'LC Classification': ['LC Classification Code', 'LC Classification', 'LC Class']
        }
    elif data_type == 'Digital Collections (Tulane Digital Library)':
        WEIGHT_COL_ALIASES = ['Digital File Downloads', 'Digital File Views', 'Downloads', 'Views']
        METRIC_TITLE = "Total Usage (Views + Downloads)"
        METRIC_UNIT = "Views + Downloads"
        FILTER_COLS = {
            'File Name': ['File Name', 'Name of file', 'Resource Name'],
            'Collection Name': ['Collection Name', 'Collection', 'Digital Collection']
        }
    else: # COUNTER Reports (e-resources)
        WEIGHT_COL_ALIASES = ['Total_Item_Requests', 'Unique_Item_Requests', 'Total_Requests', 'Searches_Platform']
        METRIC_TITLE = "Total Usage (COUNTER)"
        METRIC_UNIT = "Requests"
        FILTER_COLS = {
            'Title': ['Title'],
            'Platform': ['Platform'],
            'Publisher': ['Publisher']
        }

    # Upload section
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown(f"""
        <div class="uploadbox">
            <h2>📂 Upload {data_type} CSV</h2>
            <p>Drag and drop or click to browse</p>
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "Choose your CSV file",
            type=['csv'],
            help=f"Upload the {data_type.lower()} data CSV file",
            label_visibility="collapsed"
        )
    
    if uploaded_file is not None:
        st.success(f"✅ File '{uploaded_file.name}' uploaded successfully!")
        
        # Load data with proper encoding handling
        try:
            # Try UTF-8 with BOM first
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
        except:
            try:
                # Reset file pointer
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='latin-1')
            except Exception as e:
                st.error(f"Error reading file: {e}")
                return
        
        # Clean column names (remove any extra spaces or special characters)
        df.columns = df.columns.str.strip()
        
        # Debug: Show actual columns found
        with st.expander("🔍 Debug: Column Information", expanded=False):
            st.write("**Columns found in your file:**")
            st.write(list(df.columns))
            st.write(f"\n**Number of rows:** {len(df)}")
            
        # --- Column Validation and Weighting ---
        if 'Subjects' not in df.columns:
            st.error("❌ CSV must contain a 'Subjects' column.")
            st.info(f"Required column: **Subjects**. Found columns: {', '.join(df.columns)}")
            return

        # Initialize weight calculation
        weight_col = None
        df['Weight'] = 1  # Default weight
        
        # Special handling for Digital Collections
        if data_type == 'Digital Collections (Tulane Digital Library)':
            # Look for Downloads and Views columns
            downloads_col = None
            views_col = None
            
            for col in df.columns:
                if 'Download' in col:
                    downloads_col = col
                if 'View' in col and 'Last' not in col:  # Exclude "File Last View Date"
                    views_col = col
            
            # Calculate combined weight
            if downloads_col or views_col:
                st.info(f"Found columns - Downloads: {downloads_col}, Views: {views_col}")
                
                if downloads_col:
                    df['Downloads_clean'] = pd.to_numeric(df[downloads_col], errors='coerce').fillna(0)
                else:
                    df['Downloads_clean'] = 0
                    
                if views_col:
                    df['Views_clean'] = pd.to_numeric(df[views_col], errors='coerce').fillna(0)
                else:
                    df['Views_clean'] = 0
                
                df['Weight'] = df['Downloads_clean'] + df['Views_clean']
                
                # Update metric labels
                if downloads_col and views_col:
                    METRIC_TITLE = f"Total Usage (Views + Downloads)"
                    METRIC_UNIT = "Views + Downloads"
                elif downloads_col:
                    METRIC_TITLE = f"Total Downloads"
                    METRIC_UNIT = "Downloads"
                elif views_col:
                    METRIC_TITLE = f"Total Views"
                    METRIC_UNIT = "Views"
            else:
                st.warning("No usage columns found. Treating all items as having 1 unit of usage.")
                df['Weight'] = 1
                METRIC_TITLE = "Total Records"
                METRIC_UNIT = "Records"
                
        else:
            # Standard weight column detection for Physical and COUNTER
            for alias in WEIGHT_COL_ALIASES:
                matching_cols = [col for col in df.columns if alias in col or col == alias]
                if matching_cols:
                    weight_col = matching_cols[0]
                    df['Weight'] = pd.to_numeric(df[weight_col], errors='coerce').fillna(0)
                    METRIC_TITLE = f"Total {weight_col}"
                    METRIC_UNIT = weight_col
                    break
            
            if not weight_col:
                st.warning(f"No standard usage column found for {data_type}. Treating all items as having 1 unit of usage.")
                df['Weight'] = 1
                METRIC_TITLE = "Total Records"
                METRIC_UNIT = "Records"

        # Map filter keys to actual column names with better matching
        actual_filter_cols = {}
        for key, aliases in FILTER_COLS.items():
            for alias in aliases:
                # Check for exact match first, then partial match
                if alias in df.columns:
                    actual_filter_cols[key] = alias
                    break
                # Check for partial match (case-insensitive)
                matching_cols = [col for col in df.columns if alias.lower() in col.lower()]
                if matching_cols:
                    actual_filter_cols[key] = matching_cols[0]
                    break
        
        # Debug: Show filter mapping
        with st.expander("🔍 Debug: Filter Mapping", expanded=False):
            st.write("**Filter columns mapped:**")
            for key, col in actual_filter_cols.items():
                st.write(f"- {key}: {col}")
            if not actual_filter_cols:
                st.warning("No filter columns could be mapped!")
                
        # Display data overview
        st.markdown("---")
        st.subheader("📊 Data Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", f"{len(df):,}")
        with col2:
            # Sum the Weight column for total usage
            total_weight = df['Weight'].sum()
            st.metric(METRIC_TITLE, f"{total_weight:,.0f}")
        
        # Display available filter metrics
        filter_keys_available = list(actual_filter_cols.keys())
        
        with col3:
            if len(filter_keys_available) >= 1:
                key = filter_keys_available[0]
                col_name = actual_filter_cols[key]
                unique_count = df[col_name].nunique()
                st.metric(f"Unique {key}s", f"{unique_count:,}")
            else:
                st.metric("Filter 1", "N/A")
                
        with col4:
            if len(filter_keys_available) >= 2:
                key = filter_keys_available[1]
                col_name = actual_filter_cols[key]
                unique_count = df[col_name].nunique()
                st.metric(f"Unique {key}s", f"{unique_count:,}")
            else:
                st.metric("Filter 2", "N/A")

        # Settings in sidebar
        with st.sidebar:
            st.subheader("📊 Filter Data")
            
            filter_selections = {}
            
            if filter_keys_available:
                for key in filter_keys_available:
                    filter_col_name = actual_filter_cols[key]
                    
                    # Get unique values, handling NaN
                    unique_values = df[filter_col_name].dropna().unique()
                    options = sorted(unique_values.astype(str))
                    
                    # Create multiselect with all selected by default
                    selected_items = st.multiselect(
                        f"Filter by {key}",
                        options=options,
                        default=options,  # All selected by default
                        key=f"filter_{key}",
                        help=f"Select specific {key.lower()}s to include"
                    )
                    
                    filter_selections[filter_col_name] = selected_items
                    
                st.markdown("---")
            else:
                st.info("No filter columns available. Processing entire dataset.")
            
            # Word cloud settings
            st.subheader("🎨 Visualization Settings")
            max_words = st.slider("Maximum words", 20, 200, 100, 10)
            min_word_length = st.slider("Minimum word length", 1, 10, 3)
            color_scheme = st.selectbox(
                "Color scheme",
                ["viridis", "plasma", "inferno", "magma", "cividis", "twilight", "rainbow"]
            )
            
            # Display options
            st.markdown("---")
            st.subheader("📊 Display Options")
            show_table = st.checkbox("Show frequency table", value=True)
            show_bar = st.checkbox("Show bar chart", value=True)
            top_n = st.slider("Top N terms for bar chart", 10, 50, 20)
        
        # Generate button
        if st.button("🎨 Generate Word Cloud", type="primary", use_container_width=True):
            
            # Apply filters
            filtered_df = df.copy()
            filter_summary_parts = []
            
            for col_name, selected_values in filter_selections.items():
                if selected_values and len(selected_values) < df[col_name].dropna().nunique():
                    # Apply filter (convert column to string for comparison)
                    filtered_df = filtered_df[filtered_df[col_name].astype(str).isin(selected_values)]
                    
                    # Create summary for title
                    key = next((k for k, v in actual_filter_cols.items() if v == col_name), col_name)
                    if len(selected_values) <= 2:
                        filter_summary_parts.append(f"{key}: {', '.join(selected_values[:2])}")
                    else:
                        filter_summary_parts.append(f"{key}: {len(selected_values)} selected")
            
            # Create title suffix
            if filter_summary_parts:
                title_suffix = f"{data_type} - Filtered ({' | '.join(filter_summary_parts)})"
            else:
                title_suffix = f"{data_type} - Entire Collection"
            
            # Check if any data remains
            if filtered_df.empty:
                st.warning("No data found for the selected filters. Please adjust your selection.")
                return
            
            st.info(f"Processing {len(filtered_df)} records after filtering...")
            
            # Process subjects
            with st.spinner('Processing subjects...'):
                all_subjects = Counter()
                for _, row in filtered_df.iterrows():
                    if pd.notna(row['Subjects']) and row['Subjects']:
                        subjects_weighted = process_subjects(row['Subjects'], row['Weight'])
                        all_subjects.update(subjects_weighted)
            
            if not all_subjects:
                st.warning("No subject data found for this selection.")
                return
            
            # Generate word cloud
            st.markdown("---")
            st.subheader(f"☁️ Word Cloud - {title_suffix}")
            
            # Filter by minimum word length
            filtered_subjects = {term: count for term, count in all_subjects.items() 
                               if term and len(term) >= min_word_length}
            
            if not filtered_subjects:
                st.warning("No terms found after applying minimum word length filter.")
                return
            
            wordcloud = WordCloud(
                width=1200, 
                height=600, 
                background_color='white', 
                colormap=color_scheme,
                max_words=max_words, 
                relative_scaling=0.5, 
                min_font_size=10, 
                prefer_horizontal=0.7
            ).generate_from_frequencies(filtered_subjects)
            
            # Plot word cloud
            fig, ax = plt.subplots(figsize=(15, 8))
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis('off')
            ax.set_title(f'Subject Terms - {title_suffix}\n(Weighted by {METRIC_UNIT})', 
                        fontsize=16, fontweight='bold', pad=20)
            st.pyplot(fig)
            
            # Download button for word cloud
            img_buffer = BytesIO()
            fig.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight', facecolor='white')
            img_buffer.seek(0)
            
            safe_title = re.sub(r'[^\w\-_\. ]', '', title_suffix).replace(' ', '_')
            
            st.download_button(
                label="📥 Download Word Cloud (PNG)",
                data=img_buffer,
                file_name=f"wordcloud_{safe_title}.png",
                mime="image/png"
            )
            
            # Bar chart
            if show_bar:
                st.markdown("---")
                st.subheader(f"📊 Top {top_n} Subject Terms")
                
                top_terms = all_subjects.most_common(top_n)
                df_chart = pd.DataFrame(top_terms, columns=['Term', 'Count'])
                
                fig = px.bar(
                    df_chart, 
                    x='Count', 
                    y='Term', 
                    orientation='h',
                    color='Count',
                    color_continuous_scale=color_scheme,
                    title=f'Top {top_n} Subject Terms - {title_suffix}',
                    labels={'Count': f'Weighted Count ({METRIC_UNIT})', 'Term': 'Subject Term'}
                )
                
                fig.update_layout(
                    yaxis={'categoryorder': 'total ascending'},
                    height=max(400, top_n * 25),
                    showlegend=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Frequency table
            if show_table:
                st.markdown("---")
                st.subheader("📋 Complete Frequency Table")
                
                freq_df = pd.DataFrame(all_subjects.items(), columns=['Subject Term', 'Weighted Count'])
                freq_df = freq_df.sort_values('Weighted Count', ascending=False)
                freq_df['Rank'] = range(1, len(freq_df) + 1)
                freq_df = freq_df[['Rank', 'Subject Term', 'Weighted Count']]
                
                # Add search box
                search = st.text_input("🔍 Search terms:", "", key='search_table')
                if search:
                    freq_df = freq_df[freq_df['Subject Term'].str.contains(search, case=False, na=False)]
                
                # Display
                st.dataframe(
                    freq_df,
                    use_container_width=True,
                    height=400,
                    hide_index=True
                )
                
                # Download CSV
                csv = freq_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Frequency Table (CSV)",
                    data=csv,
                    file_name=f"frequencies_{safe_title}.csv",
                    mime="text/csv"
                )
                
                # Summary stats
                st.info(f"""
                **Summary Statistics:**
                - Total unique terms: {len(freq_df):,}
                - Total weighted occurrences: {freq_df['Weighted Count'].sum():,.0f}
                - Most common term: "{freq_df.iloc[0]['Subject Term'] if not freq_df.empty else 'N/A'}"
                - Average occurrences per term: {freq_df['Weighted Count'].mean():.1f if not freq_df.empty else 0}
                """)
    
    else:
        # Show instructions when no file uploaded
        st.markdown("---")
        
        with st.expander("📖 How to use this tool", expanded=True):
            st.markdown(f"""
            ### Step 1: Select Data Type
            Use the sidebar to choose your collection type:
            - **Physical Collections**: Traditional library materials
            - **Digital Collections**: Tulane Digital Library items  
            - **COUNTER Reports**: Electronic resources usage
            
            ### Step 2: Prepare Your CSV
            
            #### Required Column (All Types):
            - **Subjects**: Subject terms separated by semicolons (;)
            
            #### Expected Columns by Type:
            
            **Digital Collections (Tulane Digital Library):**
            - `Collection Name` - Name of digital collection
            - `File Name` - Name of the digital file
            - `Digital File Views` - Number of views
            - `Digital File Downloads` - Number of downloads
            
            **Physical Collections:**
            - `Location Name` - Physical location
            - `LC Classification Code` - Library classification
            - `Loans` or similar - Checkout count
            
            ### Step 3: Upload and Generate
            1. Upload your CSV file
            2. Use filters to focus on specific collections or files
            3. Adjust visualization settings
            4. Click "Generate Word Cloud"
            """)
        
        with st.expander("🔧 Troubleshooting"):
            st.markdown("""
            **Filters not showing?**
            - Check that your column names match expected names
            - Look at the Debug information after upload
            - Ensure no extra spaces in column headers
            
            **No data after filtering?**
            - Try selecting fewer filters
            - Check for empty values in filter columns
            - Use the debug expander to see column mapping
            
            **Word cloud is empty?**
            - Verify the Subjects column has data
            - Check that subjects are semicolon-separated
            - Ensure weight columns have numeric values
            """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #666;'>
            <p>Library Word Cloud Generator v4.2 | Built with Streamlit, Claude AI, and Gemini AI</p>
            <p>For support, contact Kay P Maye at kmaye@tulane.edu </p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

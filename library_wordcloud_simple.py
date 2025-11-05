"""
Library Word Cloud Generator - Multi-Collection Version
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
    
    # COUNTER reports often use a single subject per resource, but this handles multiple
    subjects = subjects_str.split(';')
    weighted_subjects = {}
    
    for subject in subjects:
        cleaned = clean_subject_term(subject)
        if cleaned:
            weighted_subjects[cleaned] = weighted_subjects.get(cleaned, 0) + weight
    
    return weighted_subjects

# Main app
def main():
    
    # Header
    st.title("📚 Library Collection Subject Analyzer")
    st.markdown("### Upload your usage data (Physical, Digital, or COUNTER) to analyze subject trends.")
    
    # Data Type Selection (First step in sidebar)
    with st.sidebar:
        st.header("⚙️ Data Source")
        data_type = st.radio(
            "Select Data Collection Type:",
            ['Physical Collections', 'Digital Collections (Local)', 'COUNTER Reports (e-resources)'],
            index=0,
            help="This determines the required columns and usage metric."
        )
        st.markdown("---")

    # Column definitions based on data type
    if data_type == 'Physical Collections':
        WEIGHT_COL_ALIASES = ['Loans', 'Checkouts', 'Circulation']
        METRIC_TITLE = "Total Checkouts"
        METRIC_UNIT = "Checkouts"
        FILTER_COLS = {
            'Location': 'Location Name',
            'LC Classification': 'LC Classification Code'
        }
    elif data_type == 'Digital Collections (Local)':
        WEIGHT_COL_ALIASES = ['Downloads', 'Views']
        METRIC_TITLE = "Total Usage (D/V)"
        METRIC_UNIT = "Views + Downloads"
        FILTER_COLS = {
            'Resource Name': 'Name of file',
            'Collection Name': 'Collection Name'
        }
    else: # COUNTER Reports (e-resources)
        WEIGHT_COL_ALIASES = ['Total_Item_Requests', 'Unique_Item_Requests', 'Total_Requests', 'Searches_Platform']
        METRIC_TITLE = "Total Usage (COUNTER)"
        METRIC_UNIT = "Requests"
        FILTER_COLS = {
            'Title': 'Title',
            'Platform': 'Platform',
            'Publisher': 'Publisher'
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
        
        # Load data
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
        except:
            try:
                df = pd.read_csv(uploaded_file, encoding='latin-1')
            except Exception as e:
                st.error(f"Error reading file: {e}")
                return
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # --- Column Validation and Weighting ---
        if 'Subjects' not in df.columns:
            st.error("❌ CSV must contain a 'Subjects' column.")
            st.info(f"Required column: **Subjects**.")
            return

        weight_col = None
        # Try to find a specific weight column based on alias list
        current_aliases = WEIGHT_COL_ALIASES
        for alias in current_aliases:
            if alias in df.columns:
                weight_col = alias
                break
        
        # Scenario 1: Digital Collections (Local) - Needs combined D/V logic if no single weight col found
        if data_type == 'Digital Collections (Local)' and not weight_col:
            has_downloads = 'Downloads' in df.columns
            has_views = 'Views' in df.columns
            
            if has_downloads or has_views:
                if has_downloads: df['Downloads'] = pd.to_numeric(df['Downloads'], errors='coerce').fillna(0)
                if has_views: df['Views'] = pd.to_numeric(df['Views'], errors='coerce').fillna(0)
                
                weight_val = (df['Downloads'] if has_downloads else 0) + (df['Views'] if has_views else 0)
                df['Weight'] = weight_val
                
                final_metric = ("Downloads" if has_downloads else "") + (" + " if has_downloads and has_views else "") + ("Views" if has_views else "")
                METRIC_TITLE = f"Total Usage ({final_metric})"
                METRIC_UNIT = final_metric
            else:
                weight_col = None # Ensure it falls to default if neither D nor V found

        # Scenario 2: Standard/COUNTER/Fallback (If a column was found or falls to default)
        if weight_col:
            df[weight_col] = pd.to_numeric(df[weight_col], errors='coerce').fillna(0)
            df['Weight'] = df[weight_col]
            final_metric = weight_col
            METRIC_TITLE = f"Total Usage ({final_metric})"
            METRIC_UNIT = final_metric
        elif 'Weight' not in df.columns: # Default to 1 if no specific weight column or D/V calculation succeeded
            st.warning(f"No standard usage column found for {data_type}. Treating all items as having 1 unit of usage.")
            df['Weight'] = 1
            final_metric = "Records"
            METRIC_TITLE = "Total Usage (Records)"
            METRIC_UNIT = "Records"

        # Ensure numeric conversion for the final metric calculation
        df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce').fillna(0)

        # Display data overview
        st.markdown("---")
        st.subheader("📊 Data Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", f"{len(df):,}")
        with col2:
            st.metric(METRIC_TITLE, f"{df['Weight'].sum():,}")
        
        # Dynamically display the first two available filter metrics
        filter_keys_available = [key for key, col in FILTER_COLS.items() if col in df.columns]

        with col3:
            if len(filter_keys_available) >= 1:
                key = filter_keys_available[0]
                st.metric(f"Unique {key}s", df[FILTER_COLS[key]].nunique())
            else:
                st.metric("Filter 1", "N/A")

        with col4:
            if len(filter_keys_available) >= 2:
                key = filter_keys_available[1]
                st.metric(f"Unique {key}s", df[FILTER_COLS[key]].nunique())
            else:
                st.metric("Filter 2", "N/A")

        # --- Settings in sidebar ---
        with st.sidebar:
            st.subheader("Filter & Visualize")
            
            analysis_options = ["Overall Collection"]
            
            # Add available filters based on data type and column presence
            available_filters = {}
            for key, col in FILTER_COLS.items():
                if col in df.columns:
                    analysis_options.append(f"By {key}")
                    available_filters[key] = col
            
            analysis_type = st.selectbox(
                "Analysis Type",
                analysis_options,
                help="Choose how to filter your data"
            )
            
            selected_items = None
            filter_col_name = None
            
            if analysis_type != "Overall Collection":
                filter_key = analysis_type.replace("By ", "")
                filter_col_name = available_filters.get(filter_key)
                
                if filter_col_name:
                    options = sorted(df[filter_col_name].dropna().unique())
                    selected_items = st.multiselect(
                        f"Select {filter_key}(s)",
                        options,
                        default=options
                    )
                else:
                    st.warning(f"Filter column for {filter_key} not found.")

            st.markdown("---")
            
            # Word cloud settings
            st.subheader("Word Cloud Settings")
            max_words = st.slider("Maximum words", 20, 200, 100, 10)
            min_word_length = st.slider("Minimum word length", 1, 10, 3)
            color_scheme = st.selectbox(
                "Color scheme",
                ["viridis", "plasma", "inferno", "magma", "cividis", "twilight", "rainbow"]
            )
            
            # Display options
            st.markdown("---")
            st.subheader("Display Options")
            show_table = st.checkbox("Show frequency table", value=True)
            show_bar = st.checkbox("Show bar chart", value=True)
            top_n = st.slider("Top N terms for bar chart", 10, 50, 20)
        
        # Generate button
        if st.button("🎨 Generate Word Cloud", type="primary", use_container_width=True):
            
            # --- Filtering Logic ---
            filtered_df = df
            title_suffix = f"{data_type} - Entire Collection"
            
            if analysis_type != "Overall Collection" and selected_items and filter_col_name:
                # Use isin() to filter for multiple selections
                filtered_df = df[df[filter_col_name].isin(selected_items)]
                
                # Create a concise title suffix
                display_list = selected_items[:2]
                filter_key = analysis_type.replace("By ", "")
                title_suffix = f"{data_type} - {filter_key}: {', '.join(display_list)}{'...' if len(selected_items) > 2 else ''} ({len(selected_items)} selected)"
            
            # Check if any data remains after filtering
            if filtered_df.empty:
                st.warning(f"No data found for the selected filter(s). Please adjust your selection.")
                return

            # Process subjects
            with st.spinner('Processing subjects...'):
                all_subjects = Counter()
                for _, row in filtered_df.iterrows():
                    if pd.notna(row['Subjects']):
                        # Use the calculated 'Weight' column
                        subjects_weighted = process_subjects(row['Subjects'], row['Weight'])
                        all_subjects.update(subjects_weighted)
            
            if not all_subjects:
                st.warning("No subject data found for this selection.")
                return
            
            # Generate word cloud
            st.markdown("---")
            st.subheader(f"☁️ Word Cloud - {title_suffix}")
            
            wordcloud = WordCloud(
                width=1200, height=600, background_color='white', colormap=color_scheme,
                max_words=max_words, relative_scaling=0.5, min_font_size=10, prefer_horizontal=0.7
            ).generate_from_frequencies(dict(all_subjects))
            
            # Plotting the word cloud
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
            
            st.download_button(
                label="📥 Download Word Cloud (PNG)",
                data=img_buffer,
                file_name=f"wordcloud_{title_suffix.replace(' ', '_').replace('/', '_')}.png",
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
                
                # Create dataframe
                freq_df = pd.DataFrame(all_subjects.items(), columns=['Subject Term', 'Weighted Count'])
                freq_df = freq_df.sort_values('Weighted Count', ascending=False)
                freq_df['Rank'] = range(1, len(freq_df) + 1)
                freq_df = freq_df[['Rank', 'Subject Term', 'Weighted Count']]
                
                # Add search box
                search = st.text_input("🔍 Search terms:", "", key='search_table')
                if search:
                    freq_df = freq_df[freq_df['Subject Term'].str.contains(search, case=False, na=False)]
                
                # Display with pagination
                st.dataframe(
                    freq_df,
                    use_container_width=True,
                    height=400,
                    hide_index=True
                )
                
                # Download button for CSV
                csv = freq_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Frequency Table (CSV)",
                    data=csv,
                    file_name=f"frequencies_{title_suffix.replace(' ', '_').replace('/', '_')}.csv",
                    mime="text/csv"
                )
                
                # Summary stats
                st.info(f"""
                **Summary Statistics:**
                - Total unique terms: {len(freq_df):,}
                - Total weighted occurrences: {freq_df['Weighted Count'].sum():,}
                - Most common term: "{freq_df.iloc[0]['Subject Term']}" ({freq_df.iloc[0]['Weighted Count']:,} occurrences)
                - Average occurrences per term: {freq_df['Weighted Count'].mean():.1f}
                """)
    
    else:
        # Define the requirements content for download
        requirements_content = """
streamlit
pandas
numpy
wordcloud
matplotlib
plotly
"""
        
        # Show setup instructions when no file is uploaded
        st.markdown("---")
        
        with st.expander("⚠️ **Setup and Dependencies**", expanded=True):
            st.markdown("""
            ### 1. Resolve Module Errors (Like 'wordcloud' not found)
            If you encounter a `ModuleNotFoundError`, you need to **install the necessary Python libraries**.
            
            **Run this command in your terminal/command prompt:**
            ```bash
            pip install streamlit pandas numpy wordcloud matplotlib plotly
            ```
            
            **For Streamlit Cloud deployment**, use the `requirements.txt` file below to list dependencies.
            """)
            
            # Download button for requirements.txt
            st.download_button(
                label="📥 Download requirements.txt",
                data=requirements_content,
                file_name="requirements.txt",
                mime="text/plain"
            )
            
        with st.expander("📖 How to use this tool", expanded=True):
            st.markdown(f"""
            ### Step 1: Select Data Type and Prepare CSV
            Use the sidebar to choose **Physical**, **Digital (Local)**, or **COUNTER Reports**.
            
            #### Required Columns
            - **All Types:** `Subjects` (terms separated by semicolons)
            - **Physical:** A column for **Loans** or **Checkouts** (for weighting)
            - **Digital (Local):** Columns for **Downloads** or **Views** (for weighting)
            - **COUNTER:** A column like **Total_Item_Requests** or **Unique_Item_Requests**
            
            #### Optional Columns (for filtering)
            - **Physical:** `Location Name` and `LC Classification Code`
            - **Digital (Local):** `Name of file` and `Collection Name`
            - **COUNTER:** `Title`, **Platform**, and **Publisher**
            
            ### Step 2: Upload your file
            - Click the upload area above or drag and drop your CSV file.
            
            ### Step 3: Configure settings
            - Choose analysis type (Overall or filtered by an available category)
            - **Note:** All filtering options now support selecting **multiple** items.
            
            ### Step 4: Generate visualizations
            - Click the "Generate Word Cloud" button to see the results.
            """)
        
        with st.expander("📊 Sample Data Structure"):
            st.markdown("#### Physical Collections Sample")
            sample_physical = pd.DataFrame({
                'Title': ['Book 1', 'Book 2', 'Book 3'],
                'Location Name': ['Main Library', 'Branch A', 'Main Library'],
                'LC Classification Code': ['PQ', 'F', 'HT'],
                'Subjects': [
                    'Poetry; Fiction; Latin American literature',
                    'History; Mexico - Antiquities; Indigenous peoples',
                    'Social sciences; Communities; Urban studies'
                ],
                'Loans (Total)': [3, 2, 5]
            })
            st.dataframe(sample_physical, use_container_width=True)

            st.markdown("#### Digital Collections (Local) Sample")
            sample_digital = pd.DataFrame({
                'Title': ['Report A', 'Image B', 'Video C'],
                'Name of file': ['Annual Report 2024', 'Historical Photo Set', 'Oral History Interview'],
                'Collection Name': ['Institutional Repository', 'Digital Archives', 'Institutional Repository'], 
                'URL': ['http://...', 'http://...', 'http://...'],
                'Subjects': [
                    'Finance; Economics; Corporate culture',
                    'Local history; Architecture; 1950s',
                    'Oral history; Interviews; Civil rights'
                ],
                'Downloads': [120, 50, 0],
                'Views': [500, 200, 800]
            })
            st.dataframe(sample_digital, use_container_width=True)

            st.markdown("#### COUNTER Reports (e-resources) Sample")
            sample_counter = pd.DataFrame({
                'Title': ['Journal X', 'Ebook Y', 'Database Z'],
                'Platform': ['Wiley', 'EBSCO', 'ProQuest'],
                'Publisher': ['Wiley Inc.', 'EBSCO Publishing', 'ProQuest LLC'],
                'Subjects': [
                    'Science; Chemistry; Research methods',
                    'Sociology; Anthropology; Global studies',
                    'Computer science; Data mining'
                ],
                'Total_Item_Requests': [1500, 800, 12000],
                'Unique_Item_Requests': [500, 200, 5000]
            })
            st.dataframe(sample_counter, use_container_width=True)
            
            # Download sample buttons
            col_p, col_d, col_c = st.columns(3)
            with col_p:
                csv_p = sample_physical.to_csv(index=False)
                st.download_button(
                    label="📥 Physical Sample CSV",
                    data=csv_p,
                    file_name="sample_physical_data.csv",
                    mime="text/csv"
                )
            with col_d:
                csv_d = sample_digital.to_csv(index=False)
                st.download_button(
                    label="📥 Digital Local Sample CSV",
                    data=csv_d,
                    file_name="sample_digital_data.csv",
                    mime="text/csv"
                )
            with col_c:
                csv_c = sample_counter.to_csv(index=False)
                st.download_button(
                    label="📥 COUNTER Sample CSV",
                    data=csv_c,
                    file_name="sample_counter_data.csv",
                    mime="text/csv"
                )
        
        with st.expander("❓ Frequently Asked Questions"):
            st.markdown("""
            **Q: How is the weighting calculated?**
            A: It uses the most relevant usage column found: Loans (Physical), Downloads/Views (Digital Local), or Total/Unique Requests (COUNTER). If no usage column is found, it defaults to counting the number of records.
            
            **Q: Can I analyze data from different types together?**
            A: You must upload one file type at a time. The reports can then be compared manually.
            """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #666;'>
            <p>Library Word Cloud Generator v4.0 | Built with Streamlit</p>
            <p>For support, contact your library data team</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

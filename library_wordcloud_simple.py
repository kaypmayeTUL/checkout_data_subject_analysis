"""
Library Word Cloud Generator - Simple Upload Version
Upload your library CSV file and instantly generate word clouds!
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
    'A': 'General Works',
    'B': 'Philosophy, Psychology, Religion',
    'C': 'Auxiliary Sciences of History',
    'D': 'World History',
    'E': 'US History',
    'F': 'History of the Americas',
    'G': 'Geography, Anthropology',
    'H': 'Social Sciences',
    'J': 'Political Science',
    'K': 'Law',
    'L': 'Education',
    'M': 'Music',
    'N': 'Fine Arts',
    'P': 'Language and Literature',
    'Q': 'Science',
    'R': 'Medicine',
    'S': 'Agriculture',
    'T': 'Technology',
    'U': 'Military Science',
    'V': 'Naval Science',
    'Z': 'Bibliography, Library Science'
}

def get_lc_description(code):
    """Get description for LC classification code"""
    if not code or pd.isna(code):
        return "Unknown"
    code = str(code).strip().upper()
    if code and code[0] in LC_CLASSIFICATIONS:
        return LC_CLASSIFICATIONS[code[0]]
    return f"LC Class {code}"

def clean_subject_term(term):
    """Clean and standardize subject terms"""
    if pd.isna(term) or term == '':
        return None
    
    term = term.strip()
    term = term.rstrip('.;')
    # Remove date ranges in parentheses
    term = re.sub(r'\s*\([0-9\-]+\)', '', term)
    # Standardize separators
    term = term.replace('--', ' - ')
    
    return term if term else None

def process_subjects(subjects_str, loans):
    """Process subject string into weighted dictionary"""
    if pd.isna(subjects_str) or subjects_str == '':
        return {}
    
    subjects = subjects_str.split(';')
    weighted_subjects = {}
    
    for subject in subjects:
        cleaned = clean_subject_term(subject)
        if cleaned:
            weighted_subjects[cleaned] = weighted_subjects.get(cleaned, 0) + loans
    
    return weighted_subjects

def generate_wordcloud(word_freq, min_word_length=3, max_words=100, colormap='viridis'):
    """Generate word cloud from frequency dictionary"""
    if not word_freq:
        return None
    
    # Filter short words
    filtered_freq = {word: freq for word, freq in word_freq.items() 
                     if len(word) >= min_word_length}
    
    if not filtered_freq:
        return None
    
    wordcloud = WordCloud(
        width=1200,
        height=600,
        background_color='white',
        colormap=colormap,
        max_words=max_words,
        relative_scaling=0.5,
        min_font_size=10,
        prefer_horizontal=0.7
    ).generate_from_frequencies(filtered_freq)
    
    return wordcloud

def create_download_link(df, filename="data.csv"):
    """Create a download link for dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV File</a>'
    return href

# Main app
def main():
    # Header with instructions
    st.title("📚 Library Word Cloud Generator")
    st.markdown("### Upload your library CSV file to create instant word clouds!")
    
    # Create columns for layout
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="uploadbox">
            <h2>📂 Upload Your Library Data</h2>
            <p>Drag and drop or click to browse</p>
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "Choose your CSV file",
            type=['csv'],
            help="Upload the library circulation data CSV file",
            label_visibility="collapsed"
        )
    
    if uploaded_file is not None:
        # Success message
        st.success(f"✅ File '{uploaded_file.name}' uploaded successfully!")
        
        # Load and process data
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
        
        # Check for required columns
        required_cols = ['Subjects']
        has_location = 'Location Name' in df.columns
        has_lc = 'LC Classification Code' in df.columns
        
        if 'Subjects' not in df.columns:
            st.error("❌ CSV must contain a 'Subjects' column")
            st.info("Required columns: Subjects, Location Name (optional), LC Classification Code (optional)")
            return
        
        # Find and process loan column
        loan_col = None
        for col in df.columns:
            if 'Loan' in col and 'Year' not in col:
                loan_col = col
                break
        
        if loan_col:
            df['Loans'] = pd.to_numeric(df[loan_col], errors='coerce').fillna(1)
        else:
            df['Loans'] = 1
            st.warning("No loan column found. Treating all items as having 1 checkout.")
        
        # Display data overview
        st.markdown("---")
        st.subheader("📊 Data Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", f"{len(df):,}")
        with col2:
            st.metric("Total Checkouts", f"{df['Loans'].sum():,}")
        with col3:
            if has_location:
                st.metric("Locations", df['Location Name'].nunique())
            else:
                st.metric("Locations", "N/A")
        with col4:
            if has_lc:
                st.metric("LC Classes", df['LC Classification Code'].nunique())
            else:
                st.metric("LC Classes", "N/A")
        
        # Settings in sidebar
        with st.sidebar:
            st.header("⚙️ Settings")
            
            # Analysis type based on available columns
            analysis_options = ["Overall Collection"]
            if has_location:
                analysis_options.append("By Location")
            if has_lc:
                analysis_options.append("By LC Classification")
            
            analysis_type = st.selectbox(
                "Analysis Type",
                analysis_options,
                help="Choose how to analyze your data"
            )
            
            # Specific selector based on analysis type
            selected_item = None
            if analysis_type == "By Location" and has_location:
                locations = sorted(df['Location Name'].dropna().unique())
                selected_item = st.selectbox(
                    "Select Location",
                    locations,
                    format_func=lambda x: f"{x} ({len(df[df['Location Name']==x])} items)"
                )
            elif analysis_type == "By LC Classification" and has_lc:
                lc_codes = sorted(df['LC Classification Code'].dropna().unique())
                selected_item = st.selectbox(
                    "Select LC Class",
                    lc_codes,
                    format_func=lambda x: f"{x} - {get_lc_description(x)}"
                )
            
            st.markdown("---")
            
            # Word cloud settings
            st.subheader("Word Cloud Settings")
            
            max_words = st.slider(
                "Maximum words",
                min_value=20,
                max_value=200,
                value=100,
                step=10,
                help="Number of words to show in the cloud"
            )
            
            min_word_length = st.slider(
                "Minimum word length",
                min_value=1,
                max_value=10,
                value=3,
                help="Filter out short words"
            )
            
            color_scheme = st.selectbox(
                "Color scheme",
                ["viridis", "plasma", "inferno", "magma", "cividis", "twilight", "rainbow"],
                help="Choose the color palette"
            )
            
            # Display options
            st.markdown("---")
            st.subheader("Display Options")
            show_table = st.checkbox("Show frequency table", value=True)
            show_bar = st.checkbox("Show bar chart", value=True)
            top_n = st.slider("Top N terms for bar chart", 10, 50, 20)
        
        # Generate button
        if st.button("🎨 Generate Word Cloud", type="primary", use_container_width=True):
            
            # Filter data based on selection
            if analysis_type == "Overall Collection":
                filtered_df = df
                title_suffix = "Entire Collection"
            elif analysis_type == "By Location":
                filtered_df = df[df['Location Name'] == selected_item]
                title_suffix = selected_item
            elif analysis_type == "By LC Classification":
                filtered_df = df[df['LC Classification Code'] == selected_item]
                title_suffix = f"{selected_item} - {get_lc_description(selected_item)}"
            else:
                filtered_df = df
                title_suffix = "All Data"
            
            # Process subjects
            with st.spinner('Processing subjects...'):
                all_subjects = Counter()
                for _, row in filtered_df.iterrows():
                    if pd.notna(row['Subjects']):
                        subjects_weighted = process_subjects(row['Subjects'], row['Loans'])
                        all_subjects.update(subjects_weighted)
            
            if not all_subjects:
                st.warning("No subject data found for this selection.")
                return
            
            # Generate word cloud
            st.markdown("---")
            st.subheader(f"☁️ Word Cloud - {title_suffix}")
            
            wordcloud = generate_wordcloud(
                dict(all_subjects),
                min_word_length,
                max_words,
                color_scheme
            )
            
            if wordcloud:
                fig, ax = plt.subplots(figsize=(15, 8))
                ax.imshow(wordcloud, interpolation='bilinear')
                ax.axis('off')
                ax.set_title(f'Subject Terms - {title_suffix}\n(Weighted by Checkouts)', 
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
                    labels={'Count': 'Weighted Count', 'Term': 'Subject Term'}
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
                search = st.text_input("🔍 Search terms:", "")
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
        # Show instructions when no file is uploaded
        st.markdown("---")
        
        with st.expander("📖 How to use this tool", expanded=True):
            st.markdown("""
            ### Step 1: Prepare your CSV file
            Your CSV file should contain at minimum:
            - **Subjects** column (required): Subject terms separated by semicolons
            - **Location Name** column (optional): Physical location of items
            - **LC Classification Code** column (optional): Library classification codes
            - **Loans** or similar column (optional): Number of checkouts
            
            ### Step 2: Upload your file
            - Click the upload area above or drag and drop your CSV file
            - The tool will automatically detect the columns
            
            ### Step 3: Configure settings
            - Choose analysis type (Overall, By Location, or By LC Classification)
            - Adjust word cloud settings in the sidebar
            - Select display options
            
            ### Step 4: Generate visualizations
            - Click the "Generate Word Cloud" button
            - View and download your word cloud
            - Explore the frequency data
            
            ### Step 5: Export results
            - Download the word cloud as PNG
            - Export frequency data as CSV
            - Use for reports, presentations, or further analysis
            """)
        
        with st.expander("📊 Sample data format"):
            sample_data = pd.DataFrame({
                'Title': ['Book 1', 'Book 2', 'Book 3'],
                'Location Name': ['Main Library', 'Branch A', 'Main Library'],
                'LC Classification Code': ['PQ', 'F', 'HT'],
                'Subjects': [
                    'Poetry; Fiction; Latin American literature',
                    'History; Mexico - Antiquities; Indigenous peoples',
                    'Social sciences; Communities; Urban studies'
                ],
                'Loans (In House + Not In House)': [3, 2, 5],
                'Loan Year': [2024, 2024, 2023]
            })
            st.dataframe(sample_data, use_container_width=True)
            
            # Download sample
            csv = sample_data.to_csv(index=False)
            st.download_button(
                label="📥 Download Sample CSV",
                data=csv,
                file_name="sample_library_data.csv",
                mime="text/csv"
            )
        
        with st.expander("❓ Frequently Asked Questions"):
            st.markdown("""
            **Q: What file format is required?**
            A: CSV (Comma-Separated Values) format. You can export this from Excel, Google Sheets, or your library system.
            
            **Q: How are the word sizes determined?**
            A: Word size is based on the frequency of subject terms, weighted by the number of checkouts.
            
            **Q: Can I use this with any library system?**
            A: Yes! As long as you can export your data to CSV format with a Subjects column.
            
            **Q: Is my data secure?**
            A: Your data is processed entirely in your browser (or on your server if self-hosted). Nothing is saved permanently.
            
            **Q: How many records can it handle?**
            A: The tool can handle thousands of records. For very large datasets (>50,000 records), processing may take longer.
            
            **Q: Can I customize the colors?**
            A: Yes! Use the sidebar to select from various color schemes.
            
            **Q: What if my subjects aren't separated by semicolons?**
            A: Currently, the tool expects semicolons. You can pre-process your data in Excel to replace other separators with semicolons.
            """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #666;'>
            <p>Library Word Cloud Generator v1.0 | Built with Streamlit</p>
            <p>For support, contact your library data team</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
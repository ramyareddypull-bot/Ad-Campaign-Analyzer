"""Ad Campaign Performance Analyzer — run with uv run streamlit run app.py."""
from hashlib import sha256
import streamlit as st
from analytics import load_data, DEFAULT_CSV
from views import render_sidebar, render_tab_overview, render_tab_platform, render_tab_campaign, render_tab_trends

st.set_page_config(page_title='Ad Campaign Performance Analyzer', page_icon='📊', layout='wide')
st.markdown('''<style>
.block-container {max-width:1500px;padding-top:2.3rem}
h1 {letter-spacing:-.035em}
[data-testid="stMetricValue"] {font-size:1.85rem}
[data-testid="stMetricLabel"] {font-size:.85rem}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:12px}
.stTabs [data-baseweb="tab"] {font-weight:600}
</style>''',unsafe_allow_html=True)
st.title('Ad Campaign Performance Analyzer')
st.caption('See where your budget goes, which channels deliver, and how campaign performance changes over time.')
with st.sidebar:
    st.header('Campaign workspace')
    uploaded=st.file_uploader('Upload campaign CSV',type=['csv'],help='Expected filename: social_media_advertising_sample.csv. Any CSV filename is accepted.')
    if DEFAULT_CSV.exists():
        st.download_button('Download sample CSV',DEFAULT_CSV.read_bytes(),'social_media_advertising_sample.csv','text/csv',width='stretch')
source=uploaded.getvalue() if uploaded is not None else None
# Session-only memoization avoids sharing private uploads between sessions.
fingerprint=sha256(source if source is not None else DEFAULT_CSV.read_bytes() if DEFAULT_CSV.exists() else b'missing').hexdigest()
if st.session_state.get('loaded_fingerprint')!=fingerprint:
    st.session_state['clean_data'],st.session_state['load_report']=load_data(source)
    st.session_state['loaded_fingerprint']=fingerprint
frame,report=st.session_state['clean_data'],st.session_state['load_report']
if uploaded is None:
    st.info('Demo mode · Showing bundled synthetic campaign data. Upload your CSV to analyze your own campaigns.')
else:
    st.caption(f'Data source: {uploaded.name}')
if report.get('error'):
    st.error(report['error'])
if report.get('dropped_rows') or report.get('incomplete_rows') or report.get('missing_columns'):
    with st.expander('Data quality notes',expanded=True):
        st.write(f"{report.get('dropped_rows',0):,} invalid records excluded. {report.get('incomplete_rows',0):,} retained records have missing measurements.")
        if report.get('missing_columns'):
            st.warning('Missing columns: '+', '.join(report['missing_columns']))
        st.caption('Unparseable dates, missing core measurements, negative activity/spend, invalid conversion rates and impossible click counts are excluded. Missing ROI stays unavailable; missing categories become Unknown. ROI averages skip missing values.')
if report.get('duplicate_rows'):
    st.warning(f"{report['duplicate_rows']:,} potentially duplicate records retained. Confirm these are intended observations.")
if frame.empty:
    tabs=st.tabs(['Overview','Platform Performance','Campaign Deep-Dive','Trends Over Time'])
    for tab in tabs:
        with tab:
            st.info('No usable campaign data. Upload a CSV with valid dates and measurements to begin.')
else:
    filtered,bounds=render_sidebar(frame,fingerprint)
    st.caption(f'{len(filtered):,} of {len(frame):,} records · {filtered.Campaign_ID.nunique():,} campaign IDs · {bounds[0]:%b %d, %Y} – {bounds[1]:%b %d, %Y}')
    tabs=st.tabs(['Overview','Platform Performance','Campaign Deep-Dive','Trends Over Time'])
    for tab,renderer in zip(tabs,[render_tab_overview,render_tab_platform,render_tab_campaign,render_tab_trends]):
        with tab:
            if filtered.empty:
                st.info('No data for selected filters. Try broadening the date range or resetting filters.')
            elif renderer in (render_tab_overview,render_tab_trends):
                renderer(filtered,bounds)
            else:
                renderer(filtered)
st.divider()
st.caption('Measurement notes: Acquisition_Cost is treated as spend. Conversions are rounded estimates from clicks × conversion rate. Avg ROI is the dataset’s average ROI, not revenue-based ROAS. All currency is displayed in USD.')

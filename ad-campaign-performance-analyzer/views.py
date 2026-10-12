"""Streamlit presentation built on the shared analytics functions."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from analytics import compute_metrics, platform_metrics, aggregate_time, filter_data

COLORS = {'Facebook':'#4263EB','Instagram':'#D9488B','Pinterest':'#E85959','Twitter':'#159DAD'}


def formatted(value, kind='number'):
    if value is None or pd.isna(value):
        return 'N/A'
    if kind == 'currency':
        return f'${value:,.2f}'
    if kind == 'percent':
        return f'{value:,.2f}%'
    if kind == 'roi':
        return f'{value:,.2f}'
    return f'{value:,.0f}'


def reset_filters(frame):
    st.session_state['date_range'] = (frame.Date.min().date(), frame.Date.max().date())
    for key, col in [('channels','Channel_Used'), ('goals','Campaign_Goal'), ('segments','Customer_Segment')]:
        st.session_state[key] = sorted(frame[col].unique())
    st.session_state['campaign_search'] = ''


def render_sidebar(frame, fingerprint):
    if st.session_state.get('data_fingerprint') != fingerprint:
        reset_filters(frame)
        st.session_state['data_fingerprint'] = fingerprint
    with st.sidebar:
        st.subheader('Refine your view')
        st.button('Reset Filters', on_click=reset_filters, args=(frame,), width='stretch')
        bounds = st.date_input('Date range', min_value=frame.Date.min().date(), max_value=frame.Date.max().date(), key='date_range')
        channels = st.multiselect('Platform', sorted(frame.Channel_Used.unique()), key='channels')
        goals = st.multiselect('Campaign goal', sorted(frame.Campaign_Goal.unique()), key='goals')
        segments = st.multiselect('Customer segment', sorted(frame.Customer_Segment.unique()), key='segments')
        st.caption('Filters apply to all four tabs. Clear a selection to show no matching campaigns.')
    if len(bounds) != 2:
        st.info('Select an end date to complete your date range.')
        return frame.iloc[0:0], (frame.Date.min().date(), frame.Date.max().date())
    return filter_data(frame, *bounds, channels, goals, segments), bounds


def polish(fig, height=360):
    fig.update_layout(height=height, margin=dict(l=12,r=12,t=35,b=12),
                      legend=dict(orientation='h', y=1.12, x=0),
                      font=dict(family='Arial, sans-serif'), hovermode='x unified')
    return fig


def render_tab_overview(frame, bounds):
    metrics = compute_metrics(frame)
    specs = [('Total Spend','Spend','currency','Sum of Acquisition_Cost, treated as spend.'),
             ('Total Conversions','Conversions','number','Estimated for each record as rounded Clicks × Conversion_Rate.'),
             ('Avg CTR','CTR','percent','Weighted CTR = total clicks / total impressions × 100; not a mean of row percentages.'),
             ('Avg CPC','CPC','currency','Total spend / total clicks.'),
             ('Avg ROI','Avg ROI','roi','Simple average of the supplied ROI column. Not calculated ROAS; source units are unspecified.')]
    for column, (label,key,kind,help_text) in zip(st.columns(5), specs):
        with column.container(border=True):
            st.metric(label, formatted(metrics[key],kind), help=help_text)
    st.subheader('Spend & conversion momentum')
    data, cadence = aggregate_time(frame, *bounds)
    chart = make_subplots(specs=[[{'secondary_y':True}]])
    chart.add_trace(go.Scatter(x=data.Date,y=data.Spend,name='Spend',mode='lines+markers',line=dict(color='#4263EB',width=3),hovertemplate='$%{y:,.2f}'),secondary_y=False)
    chart.add_trace(go.Scatter(x=data.Date,y=data.Conversions,name='Estimated conversions',mode='lines+markers',line=dict(color='#159DAD',width=3)),secondary_y=True)
    chart.update_yaxes(title_text='Spend ($)',tickprefix='$',secondary_y=False)
    chart.update_yaxes(title_text='Estimated conversions',secondary_y=True)
    set_date_range(chart,bounds)
    st.plotly_chart(polish(chart,400),width='stretch')
    st.caption(f'{cadence} aggregation · Each series has its own labeled axis. Conversions are estimates, not reported attribution counts.')


def render_tab_platform(frame):
    st.subheader('Compare your channels')
    st.caption('Separate scales keep spend, conversion counts and ROI comparable within each metric.')
    data = platform_metrics(frame)
    for column, metric, title in zip(st.columns(3), ['Spend','Conversions','Avg ROI'], ['Spend ($)','Estimated conversions','Avg ROI']):
        with column:
            st.markdown(f'**{title}**')
            chart = px.bar(data,x='Platform',y=metric,color='Platform',color_discrete_map=COLORS)
            chart.update_layout(showlegend=False)
            if metric == 'Spend':
                chart.update_yaxes(tickprefix='$')
            st.plotly_chart(polish(chart,320),width='stretch')
    st.subheader('Platform scorecard')
    st.dataframe(data, hide_index=True, width='stretch', column_config=metric_columns())


def metric_columns():
    return {**{key:st.column_config.NumberColumn(key,format='dollar') for key in ('Spend','CPC','CPA')},
            **{key:st.column_config.NumberColumn(key,format='localized',step=1) for key in ('Clicks','Impressions','Conversions')},
            'CTR':st.column_config.NumberColumn('CTR',format='%.2f%%'),
            'Conversion Rate':st.column_config.NumberColumn('Avg Conversion Rate',format='%.2f%%'),
            'Avg ROI':st.column_config.NumberColumn('Avg ROI',format='%.2f'),
            'ROI':st.column_config.NumberColumn('ROI',format='%.2f')}


def render_tab_campaign(frame):
    st.subheader('Campaign detail')
    search = st.text_input('Search campaigns', placeholder='Campaign ID, company, platform or goal…', key='campaign_search')
    table = frame[['Campaign_ID','Company','Channel_Used','Campaign_Goal','Spend','Clicks','Impressions','Conversions','CTR','ROI']]
    if search.strip():
        mask = table[['Campaign_ID','Company','Channel_Used','Campaign_Goal']].apply(lambda col: col.str.contains(search.strip(),case=False,regex=False)).any(axis=1)
        table = table.loc[mask]
    st.caption(f'{len(table):,} campaign records · Click a column header to sort. Search filters this table only; the funnel uses all sidebar-filtered records.')
    if table.empty:
        st.info('No campaigns match your search.')
    else:
        st.dataframe(table,hide_index=True,width='stretch',column_config=metric_columns())
    st.subheader('From reach to conversion')
    # Use the same complete rows for every stage to avoid inconsistent populations.
    complete = frame.dropna(subset=['Impressions','Clicks','Conversions'])
    if complete.empty:
        st.info('No complete impression, click and conversion records for the funnel.')
        return
    metrics = compute_metrics(complete)
    funnel = go.Figure(go.Funnel(y=['Impressions','Clicks','Estimated conversions'],
                                 x=[metrics['Impressions'],metrics['Clicks'],metrics['Conversions']],
                                 textinfo='value+percent initial',marker=dict(color=['#4263EB','#728CF1','#159DAD'])))
    st.plotly_chart(polish(funnel,340),width='stretch')
    if len(complete) != len(frame):
        st.caption(f'Funnel uses {len(complete):,} complete records; incomplete measurement rows are excluded from all stages.')


def set_date_range(chart,bounds):
    start,end = map(pd.Timestamp,bounds)
    if start == end:
        start -= pd.Timedelta(hours=12); end += pd.Timedelta(hours=12)
    chart.update_xaxes(range=[start,end],title_text='Date')


def render_tab_trends(frame,bounds):
    st.subheader('Track what matters')
    metric = st.selectbox('Metric',['Spend','Clicks','Conversions','ROI'],format_func=lambda name:'Avg ROI' if name=='ROI' else name)
    data,cadence = aggregate_time(frame,*bounds)
    chart = px.line(data,x='Date',y=metric,markers=True,color_discrete_sequence=['#4263EB'],
                     labels={metric:'Avg ROI' if metric=='ROI' else metric})
    if metric=='Spend':
        chart.update_yaxes(tickprefix='$')
    set_date_range(chart,bounds)
    st.plotly_chart(polish(chart,420),width='stretch')
    st.caption(f'{cadence} aggregation · ROI is averaged; spend, clicks and estimated conversions are summed. Missing observations are not filled with invented activity.')

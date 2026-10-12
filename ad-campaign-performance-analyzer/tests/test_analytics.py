from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest
from analytics import clean_data, load_data, compute_metrics, filter_data, platform_metrics, aggregate_time


def example():
    return pd.DataFrame({'Campaign_ID':['A','B'],'Acquisition_Cost':['$1,000.00','$500.00'],
        'Duration':['15 Days','7 Days'],'Date':['2026-05-01','2026-05-02'],
        'Clicks':[100,50],'Impressions':[1000,4000],'Conversion_Rate':[.15,.1],'ROI':[2,4],
        'Channel_Used':['Facebook','Instagram'],'Campaign_Goal':['Sales','Sales'],'Customer_Segment':['New','Old']})


def test_cleaning_and_exact_metrics():
    df,report=clean_data(example())
    assert df.Spend.tolist()==[1000,500]
    assert df.Duration_Days.tolist()==[15,7]
    assert df.Conversions.tolist()==[15,5]
    assert df.Conversion_Rate.tolist()==[.15,.1]
    metrics=compute_metrics(df)
    assert metrics=={'Spend':1500,'Conversions':20,'Clicks':150,'Impressions':5000,'CTR':3,'CPC':10,'CPA':75,'Conversion Rate':12.5,'Avg ROI':3}


def test_bad_rows_and_missing_values():
    raw=example()
    raw.loc[0,'Date']='not a date'
    raw.loc[1,'Duration']='bad'
    df,report=clean_data(raw)
    assert len(df)==1 and report['dropped_rows']==1
    assert pd.isna(df.Duration_Days.iloc[0])
    raw=example()
    raw.loc[0,'Conversion_Rate']=2
    raw.loc[1,'Clicks']=-1
    assert clean_data(raw)[0].empty


def test_no_zero_division():
    raw=example()
    raw[['Clicks','Impressions']]=0
    df,_=clean_data(raw)
    m=compute_metrics(df)
    assert m['CTR'] is None and m['CPC'] is None and m['CPA'] is None
    assert m['Conversions']==0


def test_filter_and_platform_reconciliation():
    df,_=load_data()
    start,end=df.Date.min(),df.Date.max()
    filtered=filter_data(df,start,end,['Facebook'],list(df.Campaign_Goal.unique()),list(df.Customer_Segment.unique()))
    assert set(filtered.Channel_Used)=={'Facebook'}
    platforms=platform_metrics(df)
    assert platforms.Spend.sum()==pytest.approx(compute_metrics(df)['Spend'])
    assert platforms.Conversions.sum()==compute_metrics(df)['Conversions']
    assert filter_data(df,start,end,[],[],[]).empty
    trend,cadence=aggregate_time(df,start,end)
    assert cadence=='Weekly'
    assert trend.Spend.sum()==pytest.approx(df.Spend.sum())
    assert trend.Date.min()>=start and trend.Date.max()<=end


def test_roi_is_mean_and_daily_aggregation():
    df,_=clean_data(example())
    trend,cadence=aggregate_time(df,'2026-05-01','2026-05-02')
    assert cadence=='Daily'
    assert trend.ROI.tolist()==[2,4]

@pytest.mark.parametrize('content',[b'',b'\xff',b'a,b\n1,2,3,4\n2,3',b'just_a_header'])
def test_unusable_csv_does_not_raise(content):
    df,report=load_data(content)
    assert df.empty or report

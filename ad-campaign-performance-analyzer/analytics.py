"""CSV cleaning and shared, filter-aware marketing calculations."""
from io import BytesIO
from pathlib import Path
import numpy as np
import pandas as pd

COLUMNS = ['Campaign_ID', 'Target_Audience', 'Campaign_Goal', 'Duration', 'Channel_Used',
           'Conversion_Rate', 'Acquisition_Cost', 'ROI', 'Location', 'Language', 'Clicks',
           'Impressions', 'Engagement_Score', 'Customer_Segment', 'Date', 'Company']
NUMERIC = ['Conversion_Rate', 'ROI', 'Clicks', 'Impressions', 'Engagement_Score']
CATEGORIES = ['Campaign_ID', 'Target_Audience', 'Campaign_Goal', 'Channel_Used',
              'Location', 'Language', 'Customer_Segment', 'Company']
DEFAULT_CSV = Path(__file__).with_name('social_media_advertising_sample.csv')


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Drop unusable dates and invalid measurement rows; retain unknown categories.

    Missing essential activity/spend measurements invalidate a row. Optional ROI
    and engagement values remain null; means skip missing inputs.
    Duplicate campaigns are retained because multiple observations may be valid.
    """
    frame = raw.copy()
    frame.columns = frame.columns.str.strip()
    missing = [col for col in COLUMNS if col not in frame.columns]
    report = {'input_rows': len(frame), 'dropped_rows': 0, 'missing_columns': missing,
              'incomplete_rows': 0, 'duplicate_rows': 0}
    for col in missing:
        frame[col] = pd.NA
    if frame.columns.duplicated().any():
        report['error'] = 'Duplicate column names found. Use unique CSV headers.'
        return pd.DataFrame(columns=COLUMNS + ['Spend', 'Duration_Days', 'Conversions', 'CTR']), report
    frame = frame.replace(r'^\s*$', pd.NA, regex=True)
    for col in CATEGORIES:
        frame[col] = frame[col].astype('string').str.strip().fillna('Unknown')
    frame['Date'] = pd.to_datetime(frame['Date'], errors='coerce', format='mixed', utc=True).dt.tz_convert(None).dt.normalize()
    frame['Spend'] = pd.to_numeric(frame.Acquisition_Cost.astype('string').str.replace(r'[$,\s]', '', regex=True), errors='coerce').astype(float)
    duration = pd.to_numeric(frame.Duration.astype('string').str.extract(r'^\s*(\d+)(?:\.0+)?\s*(?:Days?)?\s*$', flags=2, expand=False), errors='coerce')
    frame['Duration_Days'] = duration.where(duration.between(1, 100000)).astype('Int64')
    for col in NUMERIC:
        frame[col] = pd.to_numeric(frame[col].astype('string').str.replace(',', '', regex=False), errors='coerce').astype(float)
    frame.replace([np.inf, -np.inf], np.nan, inplace=True)
    # Ratios outside [0,1], negative activity/spend, fractional counts and impossible
    # click counts invalidate the row. A negative ROI is valid and is retained.
    invalid = frame.Date.isna() | (frame.Spend < 0)
    invalid |= frame[['Spend', 'Clicks', 'Impressions', 'Conversion_Rate']].isna().any(axis=1)
    invalid |= frame.Conversion_Rate.notna() & ~frame.Conversion_Rate.between(0, 1)
    for col in ('Clicks', 'Impressions'):
        invalid |= (frame[col] < 0) | (frame[col].notna() & (frame[col] % 1 != 0))
    invalid |= frame.Clicks.notna() & frame.Impressions.notna() & (frame.Clicks > frame.Impressions)
    report['dropped_rows'] = int(invalid.sum())
    frame = frame.loc[~invalid].copy()
    # Conventional half-up rounding of nonnegative estimated conversion counts.
    frame['Conversions'] = np.floor(frame.Clicks * frame.Conversion_Rate + .5)
    frame['CTR'] = (frame.Clicks / frame.Impressions.where(frame.Impressions > 0)) * 100
    report['incomplete_rows'] = int(frame[['Spend', 'Clicks', 'Impressions', 'Conversion_Rate', 'ROI']].isna().any(axis=1).sum())
    report['duplicate_rows'] = int(frame.duplicated(COLUMNS, keep=False).sum())
    return frame.sort_values('Date', kind='stable').reset_index(drop=True), report


def load_data(source: bytes | Path | None = None) -> tuple[pd.DataFrame, dict]:
    """Read a UTF-8 CSV safely, returning a report instead of leaking parse errors."""
    try:
        if isinstance(source, bytes) and len(source) > 20_000_000:
            raise ValueError('The upload exceeds 20 MB.')
        data = pd.read_csv(BytesIO(source) if isinstance(source, bytes) else source or DEFAULT_CSV,
                           encoding='utf-8-sig', dtype='string')
        return clean_data(data)
    except (ValueError, OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return pd.DataFrame(), {'error': 'Could not read this CSV. Check UTF-8 encoding, unique headers, consistent columns and the 20 MB size limit.'}


def _sum(series: pd.Series):
    value = series.sum(min_count=1)
    return None if pd.isna(value) else float(value)


def _mean(series: pd.Series):
    value = series.mean()
    return None if pd.isna(value) else float(value)


def _ratio(frame, numerator, denominator, scale=1):
    pairs = frame[[numerator, denominator]].dropna()
    num, den = _sum(pairs[numerator]), _sum(pairs[denominator])
    return num / den * scale if num is not None and den is not None and den > 0 else None


def compute_metrics(frame: pd.DataFrame) -> dict:
    """Aggregate counts and spend; calculate weighted CTR and simple mean ROI/CR."""
    return {'Spend': _sum(frame.Spend), 'Conversions': _sum(frame.Conversions),
            'Clicks': _sum(frame.Clicks), 'Impressions': _sum(frame.Impressions),
            'CTR': _ratio(frame, 'Clicks', 'Impressions', 100),
            'CPC': _ratio(frame, 'Spend', 'Clicks'), 'CPA': _ratio(frame, 'Spend', 'Conversions'),
            'Conversion Rate': None if (rate := _mean(frame.Conversion_Rate)) is None else rate * 100,
            'Avg ROI': _mean(frame.ROI)}


def filter_data(frame, start, end, channels, goals, segments):
    mask = (frame.Date >= pd.Timestamp(start)) & (frame.Date <= pd.Timestamp(end))
    for col, choices in [('Channel_Used', channels), ('Campaign_Goal', goals), ('Customer_Segment', segments)]:
        mask &= frame[col].isin(choices)
    return frame.loc[mask].copy()


def platform_metrics(frame):
    return pd.DataFrame([{'Platform': name, **compute_metrics(group)}
                         for name, group in frame.groupby('Channel_Used', sort=True)])


def aggregate_time(frame, start, end):
    """Sum activity and average ROI daily, or weekly for selected ranges over 90 days.

    Missing dates stay missing rather than implying zero activity. Weekly buckets
    start on the first selected day so x-coordinates stay within the date filter.
    """
    weekly = (pd.Timestamp(end) - pd.Timestamp(start)).days > 90
    data = frame.copy()
    data['Period'] = pd.Timestamp(start) + pd.to_timedelta(((data.Date - pd.Timestamp(start)).dt.days // 7) * 7, unit='D') if weekly else data.Date
    records = []
    for period, group in data.groupby('Period', sort=True):
        records.append({'Date': period, 'Spend': _sum(group.Spend), 'Clicks': _sum(group.Clicks),
                        'Conversions': _sum(group.Conversions), 'ROI': _mean(group.ROI)})
    return pd.DataFrame(records, columns=['Date','Spend','Clicks','Conversions','ROI']), 'Weekly' if weekly else 'Daily'

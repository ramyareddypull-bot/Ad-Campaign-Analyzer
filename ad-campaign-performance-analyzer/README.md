# Ad Campaign Performance Analyzer

A local Streamlit marketing dashboard with CSV upload, global date/platform/goal/segment filters, and four interactive tabs: Overview, Platform Performance, Campaign Deep-Dive, and Trends Over Time.

## Run

Python 3.12 and uv are required. From this project directory:

```sh
uv sync --locked
uv run streamlit run app.py --server.port 8502
```

Open http://localhost:8502. The separate port lets this app run alongside the stock dashboard. No API key or external service is needed. Files are processed in memory for the session.

## Data

`social_media_advertising_sample.csv` is included in the project root and loads automatically. It contains **240 synthetic demo records**, not real advertising results, covering four platforms between April and September 2026. Upload any CSV filename to replace it. Clear the uploader to return to the demo. `generate_sample.py` reproducibly regenerates this data.

Expected columns:

```text
Campaign_ID, Target_Audience, Campaign_Goal, Duration, Channel_Used,
Conversion_Rate, Acquisition_Cost, ROI, Location, Language, Clicks,
Impressions, Engagement_Score, Customer_Segment, Date, Company
```

Cleaning runs before filtering or charting:

- Strip dollar signs/commas from Acquisition_Cost into numeric Spend.
- Parse Duration such as `15 Days` into nullable integer Duration_Days.
- Parse Date, normalize to daily UTC calendar dates, and discard unusable dates.
- Keep Conversion_Rate as a decimal; derive Conversions as Clicks × Conversion_Rate, rounded half-up per record.
- Exclude rows with missing core measurements (Spend, Clicks, Impressions, Conversion_Rate), invalid conversion rates, negative activity/spend, noninteger counts or clicks exceeding impressions.
- Missing categorical values become Unknown. Missing ROI and engagement scores remain unavailable; averages skip missing ROI. Negative ROI is retained.
- Missing columns, excluded rows, incomplete measurements and potential duplicates are reported. Duplicate records are retained, since repeated campaign observations may be intentional.
- Empty, malformed, non-UTF-8 and oversized uploads produce friendly messages. Maximum upload size: 20 MB.

The dashboard uses the source's row granularity: repeated Campaign_ID values are separate records rather than silently merged or deduplicated. All currency is displayed as USD. Acquisition_Cost is treated as Spend as requested; verify this interpretation for your actual export.

## Metrics

Reusable functions in `analytics.py` calculate:

| Metric | Formula |
| --- | --- |
| Total Spend | Sum of Spend |
| Total Conversions | Sum of per-record estimated conversions |
| CTR | Total Clicks / Total Impressions × 100 |
| CPC | Total Spend / Total Clicks |
| Average Conversion Rate | Mean of Conversion_Rate × 100 |
| CPA | Total Spend / Total Conversions |
| Avg ROI | Simple average of the provided ROI column |

Zero denominators display N/A. Overview's **Avg CTR** is weighted by impressions and **Avg CPC** is calculated from aggregate spend/clicks, not averages of row ratios. ROI source units are unspecified, so Avg ROI is shown as a numeric value rather than falsely labeling it as a percent or revenue-based ROAS.

All tabs use one globally filtered dataframe. The platform scorecard includes every metric above. The campaign table supports native header sorting and explicit text search; table search affects that table only, while the funnel uses the complete global filter selection. The conversion funnel uses estimated counts.

Time charts aggregate daily for ranges of 90 days or less, weekly for longer ranges. Weekly buckets start at the selected range's beginning. Spend, clicks and conversions are summed; ROI is averaged. Unobserved dates are not invented as zero-activity periods. Charts respect the selected date range; one-day ranges have a half-day visual margin. Overview uses two clearly labeled axes because spend and counts have different units.

Reset Filters restores all sidebar selections and clears campaign search. Loading another CSV resets filters to its available dates/categories. Empty filter selections show a friendly message in each tab.

## Structure and verification

- `app.py`: application setup, upload, session memoization and four-tab orchestration.
- `analytics.py`: CSV parsing, cleaning, filtering, metrics and time/platform aggregation.
- `views.py`: sidebar, charts, table and tab rendering functions.
- `social_media_advertising_sample.csv`: bundled demo dataset.
- `tests/`: exact metric calculations, data cleaning, zero denominators, filtered totals, malformed uploads and Streamlit interaction checks.

```sh
uv run pytest -q
```

Streamlit AppTest verifies tab rendering, platform filtering, search, metric selection, empty results, reset and invalid upload states. No authentication is provided; run locally rather than exposing private campaign data on a public server.

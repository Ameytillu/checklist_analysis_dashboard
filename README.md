# Hotel Revenue Management Daily Checklist & Analytics Dashboard

Streamlit application for CSV-only hotel revenue checklist entry, day-over-day comparison, and 14-day trend analytics.

## Features

- Daily Revenue Checklist page with manual entry for hotel metrics, previous-night performance, Lighthouse demand, OTA pricing, comp set rates, 14-day forecast, and hourly pickup.
- Automatic comp set average, rate gap, rank, highest competitor rate, and lowest competitor rate.
- Automatic hourly pickup calculations and pickup chart.
- CSV export named `revenue_checklist_YYYY-MM-DD.csv`.
- Compare Two Days page for performance, OTA, comp set, forecast, and executive summary comparisons.
- 14-Day Revenue Dashboard page for trends, market position analytics, forecast performance, alerts, and combined CSV download.
- No SQL database, cloud database, or permanent app storage.

## Setup

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## CSV Workflow

1. Open `Daily Revenue Checklist`.
2. Enter the daily checklist.
3. Click `Export Today's Checklist`.
4. Store the CSV wherever you manage files, such as local folders, Google Drive, or a company drive.
5. Upload exported CSVs into `Compare Two Days` or `14-Day Revenue Dashboard`.

## Project Structure

```text
hotel_revenue_dashboard/
├── app.py
├── pages/
│   ├── 1_Daily_Revenue_Checklist.py
│   ├── 2_Compare_Two_Days.py
│   ├── 3_14_Day_Revenue_Dashboard.py
├── utils/
│   ├── calculations.py
│   ├── charts.py
│   ├── validation.py
│   ├── insights.py
├── sample_data/
│   ├── sample_revenue_checklist.csv
├── requirements.txt
├── README.md
```

## Sample Data

Use `sample_data/sample_revenue_checklist.csv` to test uploads. For trend testing, export several daily CSVs from the checklist page or duplicate the sample and adjust the `date` values.


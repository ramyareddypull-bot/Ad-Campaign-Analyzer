"""Rebuild the explicitly synthetic demo CSV deterministically (standard library only)."""
import csv
from datetime import date, timedelta
from pathlib import Path
import random


def main():
    rng = random.Random(72)
    rows = []
    channels = ['Facebook','Instagram','Pinterest','Twitter']
    for i in range(240):
        channel = channels[i % 4]
        impressions = rng.randint(12000,95000)
        clicks = round(impressions * rng.uniform(.012,.065))
        rows.append(dict(Campaign_ID=f'AD-{1001+i}',Target_Audience=rng.choice(['18–24','25–34','35–44','45–54']),
            Campaign_Goal=rng.choice(['Brand Awareness','Lead Generation','Product Launch','Sales']),
            Duration=f'{rng.choice([7,14,15,21,30])} Days',Channel_Used=channel,
            Conversion_Rate=round(rng.uniform(.025,.18) * (1.1 if channel=='Instagram' else 1),4),
            Acquisition_Cost=f'${rng.uniform(350,4200):,.2f}',ROI=round(rng.uniform(.5,6.5),2),
            Location=rng.choice(['New York','Austin','Chicago','Seattle','Los Angeles']),Language='English',
            Clicks=clicks,Impressions=impressions,Engagement_Score=round(rng.uniform(3,9.8),1),
            Customer_Segment=rng.choice(['New Customers','Returning Customers','High-Value Customers']),
            Date=str(date(2026,4,1)+timedelta(days=i*183//240)),
            Company=rng.choice(['Northstar Goods','Bloom Studio','Summit Outdoor','Orbit Software','Juniper Home'])))
    with Path(__file__).with_name('social_media_advertising_sample.csv').open('w',newline='') as output:
        writer=csv.DictWriter(output,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

if __name__=='__main__':
    main()

import csv
import random
from datetime import datetime, timedelta

meters = ['MTR-001', 'MTR-002', 'MTR-003', 'MTR-004', 'MTR-005']
tariffs = ['Standard', 'Time-of-Use', 'Peak/Off-Peak']

def generate_utility_data(filename, rows=60):
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['MeterID', 'PeriodStart', 'PeriodEnd', 'Consumption_kWh', 'Peak_kWh', 'OffPeak_kWh', 'Cost_USD', 'Tariff'])
        for _ in range(rows):
            start = datetime.now() - timedelta(days=random.randint(0, 365))
            end = start + timedelta(days=30)
            total_kwh = round(random.uniform(1000, 50000), 2)
            peak_kwh = round(total_kwh * random.uniform(0.3, 0.6), 2)
            offpeak_kwh = round(total_kwh - peak_kwh, 2)
            cost = round(total_kwh * random.uniform(0.08, 0.18), 2)
            writer.writerow([
                random.choice(meters),
                start.strftime('%Y-%m-%d'),
                end.strftime('%Y-%m-%d'),
                total_kwh,
                peak_kwh,
                offpeak_kwh,
                cost,
                random.choice(tariffs),
            ])
    print(f"Generated {filename} with {rows} rows")

generate_utility_data('../data/utility_bills.csv', rows=60)

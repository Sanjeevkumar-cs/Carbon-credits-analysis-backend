import csv
import random
from datetime import datetime, timedelta

plants = ['1000', '1010', '2000', '2020', '3030']
materials = ['DIESEL-001', 'PETROL-002', 'NATGAS-003', 'HEATING-OIL-004', 'LPG-005']
units = ['L', 'KG', 'M3', 'ST', 'T']

def generate_messy_sap_export(filename, rows=50):
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow(['SEGMENT', 'DATUM', 'MATERIALNR', 'MENGE', 'EINHEIT', 'WERK'])
        for _ in range(rows):
            random_days = random.randint(0, 365)
            raw_date = datetime.now() - timedelta(days=random_days)
            formatted_date = raw_date.strftime('%d.%m.%Y')
            writer.writerow([
                'E2EDP01',
                formatted_date,
                random.choice(materials),
                round(random.uniform(50.0, 8000.0), 2),
                random.choice(units),
                random.choice(plants)
            ])
    print(f"Generated {filename} with {rows} rows")

generate_messy_sap_export('../data/sap_procurement_export.csv', rows=75)

import csv
import random
from datetime import datetime, timedelta

employees = ['Alice M.', 'Bob K.', 'Carol S.', 'Dave L.', 'Eve R.']
flight_routes = [
    ('JFK', 'LHR', 5550), ('SFO', 'NRT', 8700), ('LHR', 'CDG', 350),
    ('FRA', 'JFK', 6200), ('DXB', 'LHR', 5500), ('SYD', 'LAX', 12100),
    ('AMS', 'BER', 580), ('HKG', 'SIN', 2600), ('ORD', 'DFW', 1300),
    ('IST', 'FRA', 1800),
]
hotel_cities = ['Berlin', 'London', 'New York', 'Tokyo', 'Paris', 'Dubai', 'Singapore']
car_types = ['CAR', 'TAXI', 'TRAIN', 'BUS']

def generate_travel_data(filename, rows=80):
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Employee', 'Type', 'Date', 'Origin', 'Destination', 'Distance', 'Unit', 'Cost', 'Purpose'])
        for _ in range(rows):
            travel_type = random.choices(
                ['FLIGHT', 'HOTEL', 'GROUND'],
                weights=[0.4, 0.3, 0.3]
            )[0]
            raw_date = datetime.now() - timedelta(days=random.randint(0, 365))
            employee = random.choice(employees)

            if travel_type == 'FLIGHT':
                route = random.choice(flight_routes)
                distance = route[2] + random.randint(-200, 200)
                origin, dest = route[0], route[1]
                cost = round(distance * random.uniform(0.05, 0.20), 2)
                unit = 'KM'
                purpose = random.choice(['Client meeting', 'Conference', 'Internal training', 'Audit'])
                writer.writerow([employee, travel_type, raw_date.strftime('%Y-%m-%d'), origin, dest, distance, unit, cost, purpose])
            elif travel_type == 'HOTEL':
                city = random.choice(hotel_cities)
                cost = round(random.uniform(150, 800), 2)
                nights = random.randint(1, 7)
                purpose = random.choice(['Business trip', 'Conference', 'Training'])
                writer.writerow([employee, travel_type, raw_date.strftime('%Y-%m-%d'), city, city, nights, 'NIGHTS', cost, purpose])
            else:
                mode = random.choice(car_types)
                origin = f'City{random.randint(1, 20)}'
                dest = f'City{random.randint(21, 40)}'
                if random.random() < 0.2:
                    distance = ''
                    unit = 'KM'
                else:
                    distance = random.randint(5, 500)
                    unit = 'KM' if random.random() > 0.3 else 'MI'
                cost = round(random.uniform(10, 200), 2)
                purpose = random.choice(['Local meeting', 'Site visit', 'Airport transfer', 'Client lunch'])
                writer.writerow([employee, f'{mode}', raw_date.strftime('%Y-%m-%d'), origin, dest, distance, unit, cost, purpose])
    print(f"Generated {filename} with {rows} rows")

generate_travel_data('../data/corporate_travel.csv', rows=80)

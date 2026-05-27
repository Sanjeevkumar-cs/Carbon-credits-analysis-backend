import csv
import json
import io
import re
from datetime import datetime
from django.utils import timezone
from .models import EmissionRecord, DataUploadJob, Facility, UnitConversion, AuditLog


UNIT_NORMALIZATION = {
    'L': 1.0, 'LITRE': 1.0, 'LITERS': 1.0, 'LTR': 1.0,
    'KG': 1.0, 'KILOGRAM': 1.0, 'KILOGRAMS': 1.0,
    'M3': 1.0, 'CUBIC_METER': 1.0, 'CBM': 1.0,
    'KWH': 1.0, 'KILOWATTHOUR': 1.0,
    'MWH': 1000.0, 'MEGAWATTHOUR': 1.0,
    'GJ': 277.778, 'GIGAJOULE': 277.778,
    'ST': None, 'PIECES': None, 'PC': None,
    'KM': 1.0, 'KILOMETER': 1.0, 'KILOMETERS': 1.0, 'KILOMETRES': 1.0,
    'MI': 1.60934, 'MILE': 1.60934, 'MILES': 1.60934,
    'GAL': 3.78541, 'GALLON': 3.78541, 'GALLONS': 3.78541,
    'T': 1000.0, 'TONNE': 1000.0, 'TONNES': 1000.0, 'METRIC_TON': 1000.0,
    'LB': 0.453592, 'POUND': 0.453592, 'POUNDS': 0.453592,
}

EMISSION_FACTORS = {
    'DIESEL': 2.68,
    'DIESEL-001': 2.68,
    'PETROL': 2.31,
    'PETROL-002': 2.31,
    'NATGAS': 2.02,
    'NATGAS-003': 2.02,
    'ELECTRICITY': 0.233,
    'FLIGHT_SHORT': 0.255,
    'FLIGHT_MEDIUM': 0.195,
    'FLIGHT_LONG': 0.150,
    'HOTEL': 31.0,
    'GROUND_CAR': 0.171,
    'GROUND_TAXI': 0.204,
    'GROUND_BUS': 0.103,
    'GROUND_TRAIN': 0.041,
}


def normalize_unit(value, unit, target_unit='KG'):
    unit_upper = unit.upper().strip() if unit else ''
    target_upper = target_unit.upper().strip()

    if unit_upper == target_upper:
        return value

    factor = UNIT_NORMALIZATION.get(unit_upper)
    if factor is None:
        return None

    target_factor = UNIT_NORMALIZATION.get(target_upper, 1.0)
    return value * factor / target_factor


def parse_european_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y']:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(date_str).date()
    except (ValueError, TypeError):
        return None


def process_sap_csv(file_content, upload_job, user):
    tenant = upload_job.tenant
    reader = csv.DictReader(io.StringIO(file_content), delimiter=';')
    success = 0
    failed = 0
    records = []

    for row in reader:
        try:
            raw_payload = dict(row)
            raw_date = row.get('DATUM', '')
            date_val = parse_european_date(raw_date)

            raw_value = float(row.get('MENGE', 0)) if row.get('MENGE') else None
            raw_unit = row.get('EINHEIT', '').strip()
            plant_code = row.get('WERK', '').strip()
            material = row.get('MATERIALNR', '').strip()

            description = f"SAP Procurement: {material}"
            scope = 'SCOPE1'

            if raw_unit in ('L', 'LITRE', 'LITERS', 'GAL', 'GALLON'):
                normalized_qty = normalize_unit(raw_value, raw_unit, 'L')
                norm_unit = 'L'
            elif raw_unit in ('KG', 'T', 'TONNE', 'LB'):
                normalized_qty = normalize_unit(raw_value, raw_unit, 'KG')
                norm_unit = 'KG'
            elif raw_unit in ('M3', 'CBM'):
                normalized_qty = raw_value
                norm_unit = 'M3'
            elif raw_unit in ('ST', 'PC', 'PIECES'):
                normalized_qty = None
                norm_unit = raw_unit
            else:
                normalized_qty = raw_value
                norm_unit = raw_unit

            facility = Facility.objects.filter(tenant=tenant, sap_plant_code=plant_code).first()
            if not facility and plant_code:
                facility = Facility.objects.create(
                    tenant=tenant,
                    sap_plant_code=plant_code,
                    name=f'Plant {plant_code}',
                )

            co2_kg = None
            if normalized_qty and norm_unit == 'L':
                co2_kg = normalized_qty * EMISSION_FACTORS.get(material, EMISSION_FACTORS.get('DIESEL', 2.68))
            elif normalized_qty and norm_unit == 'KG':
                co2_kg = normalized_qty * EMISSION_FACTORS.get(material, EMISSION_FACTORS.get('DIESEL', 2.68))

            status = 'PENDING'
            if raw_unit in ('ST', 'PC', 'PIECES'):
                status = 'FLAGGED'
            if normalized_qty and normalized_qty > 10000:
                status = 'FLAGGED'

            record = EmissionRecord(
                tenant=tenant,
                upload_job=upload_job,
                facility=facility,
                scope=scope,
                category='FUEL',
                source_type='SAP',
                raw_payload=raw_payload,
                activity_date=date_val,
                description=description,
                original_value=raw_value,
                original_unit=raw_unit,
                normalized_value=normalized_qty,
                normalized_unit=norm_unit,
                normalized_co2_kg=co2_kg,
                status=status,
            )
            record.save()
            AuditLog.objects.create(
                tenant=tenant,
                emission_record=record,
                user=user,
                action='CREATED',
                new_value=f"Imported from SAP: {material}, {raw_value} {raw_unit}",
            )
            success += 1
            records.append(record)
        except Exception as e:
            failed += 1

    upload_job.status = 'COMPLETED' if failed == 0 else 'PARTIAL'
    upload_job.total_rows = success + failed
    upload_job.success_rows = success
    upload_job.failed_rows = failed
    upload_job.processed_at = timezone.now()
    upload_job.save()

    return {'success': success, 'failed': failed, 'records': records}


def process_utility_csv(file_content, upload_job, user):
    tenant = upload_job.tenant
    content_text = file_content

    if ',' in file_content[:100]:
        reader = csv.DictReader(io.StringIO(content_text))
        delimiter = ','
    else:
        reader = csv.DictReader(io.StringIO(content_text), delimiter=';')
        delimiter = ';'

    success = 0
    failed = 0
    records = []

    for row in reader:
        try:
            raw_payload = dict(row)
            headers = list(row.keys())
            date_key = next((k for k in headers if 'date' in k.lower() or 'datum' in k.lower() or 'period' in k.lower()), None)
            usage_key = next((k for k in headers if 'usage' in k.lower() or 'consumption' in k.lower() or 'kwh' in k.lower() or 'menge' in k.lower()), None)
            unit_key = next((k for k in headers if 'unit' in k.lower() or 'einheit' in k.lower()), None)
            cost_key = next((k for k in headers if 'cost' in k.lower() or 'amount' in k.lower() or 'betrag' in k.lower()), None)
            meter_key = next((k for k in headers if 'meter' in k.lower() or 'account' in k.lower() or 'customer' in k.lower()), None)

            if not usage_key:
                usage_key = headers[1] if len(headers) > 1 else None

            raw_date = row.get(date_key) if date_key else ''
            date_val = parse_european_date(raw_date)

            raw_value_str = row.get(usage_key, '0').replace(',', '.').replace('"', '').replace(' ', '') if usage_key else '0'
            raw_value = float(raw_value_str) if raw_value_str else 0
            raw_unit = row.get(unit_key, 'KWH').strip().upper() if unit_key else 'KWH'

            if raw_unit in ('MWH', 'MW·H'):
                normalized_qty = raw_value * 1000
                norm_unit = 'KWH'
            else:
                normalized_qty = raw_value
                norm_unit = 'KWH'

            account = row.get(meter_key, '') if meter_key else ''

            facility = Facility.objects.filter(
                tenant=tenant,
                utility_account_number=account
            ).first()

            co2_kg = normalized_qty * EMISSION_FACTORS.get('ELECTRICITY', 0.233)
            status = 'PENDING'

            if normalized_qty > 1000000:
                status = 'FLAGGED'

            record = EmissionRecord(
                tenant=tenant,
                upload_job=upload_job,
                facility=facility,
                scope='SCOPE2',
                category='ELECTRICITY',
                source_type='UTILITY',
                raw_payload=raw_payload,
                activity_date=date_val,
                description=f'Utility bill - {account or "Unknown"}: {raw_value} {raw_unit}',
                original_value=raw_value,
                original_unit=raw_unit,
                normalized_value=normalized_qty,
                normalized_unit=norm_unit,
                normalized_co2_kg=co2_kg,
                status=status,
            )
            record.save()
            AuditLog.objects.create(
                tenant=tenant,
                emission_record=record,
                user=user,
                action='CREATED',
                new_value=f"Imported Utility: {raw_value} {raw_unit}",
            )
            success += 1
            records.append(record)
        except Exception as e:
            failed += 1

    upload_job.status = 'COMPLETED' if failed == 0 else 'PARTIAL'
    upload_job.total_rows = success + failed
    upload_job.success_rows = success
    upload_job.failed_rows = failed
    upload_job.processed_at = timezone.now()
    upload_job.save()

    return {'success': success, 'failed': failed, 'records': records}


def process_travel_csv(file_content, upload_job, user):
    tenant = upload_job.tenant
    reader = csv.DictReader(io.StringIO(file_content))
    success = 0
    failed = 0
    records = []

    for row in reader:
        try:
            raw_payload = dict(row)
            headers = list(row.keys())

            type_key = next((k for k in headers if 'type' in k.lower() or 'category' in k.lower() or 'segment' in k.lower()), None)
            date_key = next((k for k in headers if 'date' in k.lower() or 'datum' in k.lower() or 'travel' in k.lower()), None)
            dist_key = next((k for k in headers if 'distance' in k.lower() or 'km' in k.lower() or 'miles' in k.lower()), None)
            cost_key = next((k for k in headers if 'cost' in k.lower() or 'amount' in k.lower() or 'betrag' in k.lower()), None)
            origin_key = next((k for k in headers if 'origin' in k.lower() or 'from' in k.lower() or 'von' in k.lower()), None)
            dest_key = next((k for k in headers if 'dest' in k.lower() or 'to' in k.lower() or 'nach' in k.lower()), None)
            desc_key = next((k for k in headers if 'desc' in k.lower() or 'employee' in k.lower() or 'name' in k.lower() or 'purpose' in k.lower()), None)

            travel_type = row.get(type_key, 'FLIGHT').strip().upper() if type_key else 'FLIGHT'
            raw_date = row.get(date_key, '') if date_key else ''
            date_val = parse_european_date(raw_date)

            distance_raw = row.get(dist_key, '') if dist_key else ''
            if distance_raw and distance_raw.strip():
                distance = float(distance_raw.replace(',', '.'))
            else:
                distance = None

            unit = row.get('unit', 'KM').strip() if 'unit' in headers else 'KM'
            origin = row.get(origin_key, '') if origin_key else ''
            dest = row.get(dest_key, '') if dest_key else ''
            desc = row.get(desc_key, '') if desc_key else ''
            cost_raw = row.get(cost_key, '0') if cost_key else '0'
            cost = float(cost_raw.replace(',', '.').replace('$', '').replace('€', '').replace('£', '')) if cost_raw else 0

            if 'FLIGHT' in travel_type:
                category = 'FLIGHT'
                scope = 'SCOPE3'
                if distance:
                    if distance < 800:
                        co2_factor = EMISSION_FACTORS.get('FLIGHT_SHORT', 0.255)
                    elif distance < 2500:
                        co2_factor = EMISSION_FACTORS.get('FLIGHT_MEDIUM', 0.195)
                    else:
                        co2_factor = EMISSION_FACTORS.get('FLIGHT_LONG', 0.150)
                else:
                    co2_factor = EMISSION_FACTORS.get('FLIGHT_MEDIUM', 0.195)
            elif 'HOTEL' in travel_type:
                category = 'HOTEL'
                scope = 'SCOPE3'
                co2_factor = EMISSION_FACTORS.get('HOTEL', 31.0)
                distance = cost
            else:
                category = 'GROUND'
                scope = 'SCOPE3'
                if 'TRAIN' in travel_type:
                    co2_factor = EMISSION_FACTORS.get('GROUND_TRAIN', 0.041)
                elif 'BUS' in travel_type:
                    co2_factor = EMISSION_FACTORS.get('GROUND_BUS', 0.103)
                elif 'TAXI' in travel_type:
                    co2_factor = EMISSION_FACTORS.get('GROUND_TAXI', 0.204)
                else:
                    co2_factor = EMISSION_FACTORS.get('GROUND_CAR', 0.171)

            if distance and unit.upper() in ('MI', 'MILES'):
                distance = distance * 1.60934

            normalized_qty = distance if distance else cost
            norm_unit = 'KM' if distance else 'USD'
            co2_kg = normalized_qty * co2_factor if normalized_qty else None

            status = 'FLAGGED' if distance is None else 'PENDING'

            if distance and distance > 10000:
                status = 'FLAGGED'

            record = EmissionRecord(
                tenant=tenant,
                upload_job=upload_job,
                facility=None,
                scope=scope,
                category=category,
                source_type='TRAVEL',
                raw_payload=raw_payload,
                activity_date=date_val,
                description=f'{travel_type}: {desc or f"{origin} -> {dest}"}',
                original_value=distance if distance else cost,
                original_unit=unit if distance else 'USD',
                normalized_value=normalized_qty,
                normalized_unit=norm_unit,
                normalized_co2_kg=co2_kg,
                status=status,
            )
            record.save()
            AuditLog.objects.create(
                tenant=tenant,
                emission_record=record,
                user=user,
                action='CREATED',
                new_value=f"Imported Travel: {travel_type}, dist={distance}",
            )
            success += 1
            records.append(record)
        except Exception as e:
            failed += 1

    upload_job.status = 'COMPLETED' if failed == 0 else 'PARTIAL'
    upload_job.total_rows = success + failed
    upload_job.success_rows = success
    upload_job.failed_rows = failed
    upload_job.processed_at = timezone.now()
    upload_job.save()

    return {'success': success, 'failed': failed, 'records': records}

def recalculate_emissions(record):
    """Recalculates normalized values and CO2 kg when a record is manually edited."""
    if record.original_value is None:
        record.normalized_value = None
        record.normalized_co2_kg = None
        record.save()
        return

    raw_val = record.original_value
    raw_unit = record.original_unit.upper().strip() if record.original_unit else ''

    if record.source_type == 'SAP':
        material = record.raw_payload.get('MATERIALNR', '').strip()
        if raw_unit in ('L', 'LITRE', 'LITERS', 'GAL', 'GALLON', 'GALLONS'):
            record.normalized_value = normalize_unit(raw_val, raw_unit, 'L')
            record.normalized_unit = 'L'
        elif raw_unit in ('KG', 'T', 'TONNE', 'TONNES', 'LB', 'POUND', 'POUNDS'):
            record.normalized_value = normalize_unit(raw_val, raw_unit, 'KG')
            record.normalized_unit = 'KG'
        elif raw_unit in ('M3', 'CBM'):
            record.normalized_value = raw_val
            record.normalized_unit = 'M3'
        else:
            record.normalized_value = raw_val
            record.normalized_unit = raw_unit

        if record.normalized_value and record.normalized_unit in ('L', 'KG'):
            factor = EMISSION_FACTORS.get(material, EMISSION_FACTORS.get('DIESEL', 2.68))
            record.normalized_co2_kg = record.normalized_value * factor
        else:
            record.normalized_co2_kg = None

    elif record.source_type == 'UTILITY':
        if raw_unit in ('MWH', 'MW·H', 'MEGAWATTHOUR'):
            record.normalized_value = raw_val * 1000
            record.normalized_unit = 'KWH'
        else:
            record.normalized_value = raw_val
            record.normalized_unit = 'KWH'

        record.normalized_co2_kg = record.normalized_value * EMISSION_FACTORS.get('ELECTRICITY', 0.233)

    elif record.source_type == 'TRAVEL':
        if raw_unit in ('MI', 'MILE', 'MILES'):
            record.normalized_value = raw_val * 1.60934
            record.normalized_unit = 'KM'
        else:
            record.normalized_value = raw_val
            record.normalized_unit = 'KM'

        travel_type = record.raw_payload.get('type', record.raw_payload.get('category', 'FLIGHT')).strip().upper()
        dist = record.normalized_value

        if 'FLIGHT' in travel_type:
            if dist and dist < 800: factor = EMISSION_FACTORS.get('FLIGHT_SHORT', 0.255)
            elif dist and dist < 2500: factor = EMISSION_FACTORS.get('FLIGHT_MEDIUM', 0.195)
            else: factor = EMISSION_FACTORS.get('FLIGHT_LONG', 0.150)
        elif 'HOTEL' in travel_type:
            factor = EMISSION_FACTORS.get('HOTEL', 31.0)
            record.normalized_unit = 'USD' 
        else:
            if 'TRAIN' in travel_type: factor = EMISSION_FACTORS.get('GROUND_TRAIN', 0.041)
            elif 'BUS' in travel_type: factor = EMISSION_FACTORS.get('GROUND_BUS', 0.103)
            elif 'TAXI' in travel_type: factor = EMISSION_FACTORS.get('GROUND_TAXI', 0.204)
            else: factor = EMISSION_FACTORS.get('GROUND_CAR', 0.171)

        record.normalized_co2_kg = record.normalized_value * factor if record.normalized_value else None

    record.save()
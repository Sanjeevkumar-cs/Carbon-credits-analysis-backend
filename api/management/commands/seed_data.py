import os
import csv
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import Tenant, Facility, EmissionRecord, DataUploadJob, AuditLog
from api.normalization import process_sap_csv, process_utility_csv, process_travel_csv


class Command(BaseCommand):
    help = 'Seeds the database with sample data from generated CSV files'

    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(name='Breathe ESG Demo', slug='breathe-demo')

        admin = User.objects.filter(is_superuser=True).first()

        for code, name in [('1000', 'Berlin Plant'), ('1010', 'Hamburg Facility'),
                           ('2000', 'Munich Plant'), ('2020', 'Frankfurt Office'),
                           ('3030', 'Stuttgart Warehouse')]:
            Facility.objects.get_or_create(
                tenant=tenant, sap_plant_code=code,
                defaults={'name': name, 'country': 'DE'}
            )

        for acct in ['MTR-001', 'MTR-002', 'MTR-003']:
            Facility.objects.get_or_create(
                tenant=tenant, utility_account_number=acct,
                defaults={'name': f'Utility Meter {acct}', 'country': 'US'}
            )

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data'))
        files = [
            ('SAP', os.path.join(base_dir, 'sap_procurement_export.csv')),
            ('UTILITY', os.path.join(base_dir, 'utility_bills.csv')),
            ('TRAVEL', os.path.join(base_dir, 'corporate_travel.csv')),
        ]

        for source_type, filepath in files:
            if not os.path.exists(filepath):
                self.stdout.write(self.style.WARNING(f'File not found: {filepath}'))
                continue

            job = DataUploadJob.objects.create(
                tenant=tenant, source_type=source_type,
                filename=os.path.basename(filepath),
                uploaded_by=admin, status='UPLOADED',
            )

            with open(filepath, 'r', encoding='utf-8-sig') as f:
                content = f.read()

            if source_type == 'SAP':
                result = process_sap_csv(content, job, admin)
            elif source_type == 'UTILITY':
                result = process_utility_csv(content, job, admin)
            elif source_type == 'TRAVEL':
                result = process_travel_csv(content, job, admin)

            self.stdout.write(self.style.SUCCESS(
                f'{source_type}: {result["success"]} imported, {result["failed"]} failed'
            ))

        self.stdout.write(self.style.SUCCESS('Database seeded successfully!'))

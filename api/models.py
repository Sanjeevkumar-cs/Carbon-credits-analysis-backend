from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Tenant(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenants'

    def __str__(self):
        return self.name


class Facility(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='facilities')
    sap_plant_code = models.CharField(max_length=20, blank=True, default='')
    utility_account_number = models.CharField(max_length=50, blank=True, default='')
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True, default='')
    address = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'facilities'
        verbose_name_plural = 'facilities'

    def __str__(self):
        return f'{self.name} ({self.tenant.name})'


class UnitConversion(models.Model):
    source_unit = models.CharField(max_length=20)
    target_unit = models.CharField(max_length=20)
    conversion_factor = models.FloatField()
    category = models.CharField(max_length=50, default='mass')

    class Meta:
        db_table = 'unit_conversions'
        unique_together = ('source_unit', 'target_unit')

    def __str__(self):
        return f'{self.source_unit} -> {self.target_unit}: {self.conversion_factor}'


class DataUploadJob(models.Model):
    SOURCE_CHOICES = [
        ('SAP', 'SAP Procurement'),
        ('UTILITY', 'Utility Bill'),
        ('TRAVEL', 'Corporate Travel'),
    ]
    STATUS_CHOICES = [
        ('UPLOADED', 'Uploaded'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('PARTIAL', 'Partially Completed'),
        ('FAILED', 'Failed'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='upload_jobs')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UPLOADED')
    filename = models.CharField(max_length=255)
    total_rows = models.IntegerField(default=0)
    success_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'data_upload_jobs'

    def __str__(self):
        return f'{self.source_type} - {self.filename} ({self.status})'


class EmissionRecord(models.Model):
    SCOPE_CHOICES = [
        ('SCOPE1', 'Scope 1 - Direct Emissions'),
        ('SCOPE2', 'Scope 2 - Indirect Energy'),
        ('SCOPE3', 'Scope 3 - Value Chain'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved for Audit'),
        ('FLAGGED', 'Flagged - Needs Review'),
        ('REJECTED', 'Rejected'),
    ]
    CATEGORY_CHOICES = [
        ('FUEL', 'Fuel Combustion'),
        ('ELECTRICITY', 'Purchased Electricity'),
        ('FLIGHT', 'Business Flight'),
        ('HOTEL', 'Hotel Stay'),
        ('GROUND', 'Ground Transport'),
        ('OTHER', 'Other'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='emission_records')
    upload_job = models.ForeignKey(DataUploadJob, on_delete=models.CASCADE, related_name='records')
    facility = models.ForeignKey(Facility, on_delete=models.SET_NULL, null=True, blank=True)

    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    source_type = models.CharField(max_length=20)

    raw_payload = models.JSONField()

    activity_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, default='')

    original_value = models.FloatField(null=True, blank=True)
    original_unit = models.CharField(max_length=20, blank=True, default='')

    normalized_value = models.FloatField(null=True, blank=True)
    normalized_unit = models.CharField(max_length=20, blank=True, default='')
    normalized_co2_kg = models.FloatField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    analyst_notes = models.TextField(blank=True, default='')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'emission_records'
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'source_type']),
            models.Index(fields=['tenant', 'scope']),
        ]

    def __str__(self):
        return f'{self.source_type} - {self.scope} - {self.status}'


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATED', 'Record Created'),
        ('UPDATED', 'Record Updated'),
        ('APPROVED', 'Record Approved'),
        ('FLAGGED', 'Record Flagged'),
        ('REJECTED', 'Record Rejected'),
        ('NOTE_ADDED', 'Analyst Note Added'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='audit_logs')
    emission_record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    field_name = models.CharField(max_length=100, blank=True, default='')
    old_value = models.TextField(blank=True, default='')
    new_value = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        indexes = [
            models.Index(fields=['tenant', 'emission_record']),
            models.Index(fields=['tenant', 'created_at']),
        ]

    def __str__(self):
        return f'{self.action} on {self.emission_record} by {self.user}'

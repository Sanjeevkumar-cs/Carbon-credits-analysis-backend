from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Tenant, Facility, UnitConversion, DataUploadJob, EmissionRecord, AuditLog


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = '__all__'


class DataUploadJobSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    progress_pct = serializers.SerializerMethodField()

    class Meta:
        model = DataUploadJob
        fields = '__all__'

    def get_progress_pct(self, obj):
        if obj.total_rows == 0:
            return 0
        return round((obj.success_rows + obj.failed_rows) / obj.total_rows * 100, 1)


class EmissionRecordListSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source='facility.name', read_only=True, default='')
    upload_filename = serializers.CharField(source='upload_job.filename', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'tenant', 'upload_job', 'facility', 'facility_name',
            'scope', 'scope_display', 'category', 'category_display',
            'source_type', 'activity_date', 'description',
            'original_value', 'original_unit',
            'normalized_value', 'normalized_unit', 'normalized_co2_kg',
            'status', 'status_display', 'analyst_notes',
            'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
            'upload_filename',
        ]
        read_only_fields = ['normalized_value', 'normalized_unit', 'normalized_co2_kg']


class EmissionRecordDetailSerializer(serializers.ModelSerializer):
    raw_payload = serializers.JSONField(read_only=True)

    class Meta:
        model = EmissionRecord
        fields = '__all__'
        read_only_fields = ['normalized_value', 'normalized_unit', 'normalized_co2_kg']


class EmissionRecordActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'flag', 'reject', 'reset'])
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class EmissionRecordUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionRecord
        fields = ['analyst_notes', 'description', 'activity_date', 'original_value', 'original_unit']


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True, default='system')

    class Meta:
        model = AuditLog
        fields = '__all__'


class UploadFileSerializer(serializers.Serializer):
    source_type = serializers.ChoiceField(choices=['SAP', 'UTILITY', 'TRAVEL'])
    file = serializers.FileField()


class DashboardStatsSerializer(serializers.Serializer):
    total_records = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    approved_count = serializers.IntegerField()
    flagged_count = serializers.IntegerField()
    rejected_count = serializers.IntegerField()
    total_co2_kg = serializers.FloatField()
    scope1_kg = serializers.FloatField()
    scope2_kg = serializers.FloatField()
    scope3_kg = serializers.FloatField()
    recent_uploads = serializers.ListField(child=serializers.DictField())

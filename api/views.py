from django.utils import timezone
from django.db.models import Sum, Q
from django.contrib.auth.models import User
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from .models import Tenant, Facility, DataUploadJob, EmissionRecord, AuditLog
from .serializers import (
    TenantSerializer, FacilitySerializer, DataUploadJobSerializer,
    EmissionRecordListSerializer, EmissionRecordDetailSerializer,
    EmissionRecordActionSerializer, EmissionRecordUpdateSerializer,
    AuditLogSerializer, UploadFileSerializer,
)
from .normalization import process_sap_csv, process_utility_csv, process_travel_csv, recalculate_emissions


def get_system_user():
    return User.objects.filter(is_superuser=True).first()


def get_default_tenant():
    return Tenant.objects.first()


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [permissions.AllowAny]


class FacilityViewSet(viewsets.ModelViewSet):
    serializer_class = FacilitySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        tenant = get_default_tenant()
        if not tenant:
            return Facility.objects.none()
        return Facility.objects.filter(tenant=tenant)


class DataUploadJobViewSet(viewsets.ModelViewSet):
    serializer_class = DataUploadJobSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        tenant = get_default_tenant()
        if not tenant:
            return DataUploadJob.objects.none()
        return DataUploadJob.objects.filter(tenant=tenant).order_by('-uploaded_at')


class EmissionRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EmissionRecordDetailSerializer
        return EmissionRecordListSerializer

    def get_queryset(self):
        tenant = get_default_tenant()
        if not tenant:
            return EmissionRecord.objects.none()
        qs = EmissionRecord.objects.filter(tenant=tenant).select_related('facility', 'upload_job')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        source_filter = self.request.query_params.get('source_type')
        if source_filter:
            qs = qs.filter(source_type=source_filter.upper())
        scope_filter = self.request.query_params.get('scope')
        if scope_filter:
            qs = qs.filter(scope=scope_filter.upper())
        return qs.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def review_action(self, request, pk=None):
        record = self.get_object()
        serializer = EmissionRecordActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action_type = serializer.validated_data['action']
        notes = serializer.validated_data.get('notes', '')
        user = get_system_user()

        old_status = record.status
        new_status = old_status
        audit_action = ''

        if action_type == 'approve':
            new_status = 'APPROVED'
            audit_action = 'APPROVED'
        elif action_type == 'flag':
            new_status = 'FLAGGED'
            audit_action = 'FLAGGED'
        elif action_type == 'reject':
            new_status = 'REJECTED'
            audit_action = 'REJECTED'
        elif action_type == 'reset':
            new_status = 'PENDING'
            audit_action = 'UPDATED'

        record.status = new_status
        record.reviewed_at = timezone.now()
        if notes:
            record.analyst_notes = notes
        record.save()

        AuditLog.objects.create(
            tenant=record.tenant,
            emission_record=record,
            user=user,
            action=audit_action,
            old_value=old_status,
            new_value=new_status,
            notes=notes,
        )

        return Response(EmissionRecordListSerializer(record).data)

    @action(detail=True, methods=['patch'])
    def edit(self, request, pk=None):
        record = self.get_object()
        serializer = EmissionRecordUpdateSerializer(record, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = get_system_user()
        old_notes = record.analyst_notes
        record = serializer.save()

        # Trigger the math recalculator if the value or unit changed
        if 'original_value' in serializer.validated_data or 'original_unit' in serializer.validated_data:
            recalculate_emissions(record)

        if serializer.validated_data.get('analyst_notes') and serializer.validated_data['analyst_notes'] != old_notes:
            AuditLog.objects.create(
                tenant=record.tenant,
                emission_record=record,
                user=user,
                action='NOTE_ADDED',
                old_value=old_notes or '',
                new_value=record.analyst_notes,
            )

        audit_actions = []
        for field in ['description', 'activity_date', 'original_value', 'original_unit']:
            if field in serializer.validated_data:
                audit_actions.append(field)
        if audit_actions:
            AuditLog.objects.create(
                tenant=record.tenant,
                emission_record=record,
                user=user,
                action='UPDATED',
                field_name=','.join(audit_actions),
                notes='Analyst edit',
            )

        return Response(EmissionRecordListSerializer(record).data)
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        ids = request.data.get('ids', [])
        action_type = request.data.get('action', '')
        notes = request.data.get('notes', '')

        if not ids:
            return Response({'error': 'No record IDs provided'}, status=status.HTTP_400_BAD_REQUEST)

        tenant = get_default_tenant()
        user = get_system_user()
        records = EmissionRecord.objects.filter(id__in=ids, tenant=tenant)
        updated = 0

        for record in records:
            old_status = record.status
            if action_type == 'approve':
                record.status = 'APPROVED'
            elif action_type == 'flag':
                record.status = 'FLAGGED'
            elif action_type == 'reject':
                record.status = 'REJECTED'
            elif action_type == 'reset':
                record.status = 'PENDING'
            else:
                continue

            record.reviewed_at = timezone.now()
            if notes:
                record.analyst_notes = notes
            record.save()

            AuditLog.objects.create(
                tenant=record.tenant,
                emission_record=record,
                user=user,
                action=record.status,
                old_value=old_status,
                new_value=record.status,
                notes=f'Bulk {action_type}',
            )
            updated += 1

        return Response({'updated': updated})

    @action(detail=False, methods=['post'])
    def upload(self, request):
        serializer = UploadFileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        source_type = serializer.validated_data['source_type']
        uploaded_file = request.FILES['file']
        user = get_system_user()

        tenant = get_default_tenant()
        if not tenant:
            return Response({'error': 'No tenant configured'}, status=status.HTTP_400_BAD_REQUEST)

        upload_job = DataUploadJob.objects.create(
            tenant=tenant,
            source_type=source_type,
            filename=uploaded_file.name,
            uploaded_by=user,
            status='PROCESSING',
        )

        try:
            file_content = uploaded_file.read().decode('utf-8-sig')

            if source_type == 'SAP':
                result = process_sap_csv(file_content, upload_job, user)
            elif source_type == 'UTILITY':
                result = process_utility_csv(file_content, upload_job, user)
            elif source_type == 'TRAVEL':
                result = process_travel_csv(file_content, upload_job, user)
            else:
                return Response({'error': 'Unknown source type'}, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'job_id': upload_job.id,
                'success': result['success'],
                'failed': result['failed'],
                'total': result['success'] + result['failed'],
                'status': upload_job.status,
            })
        except Exception as e:
            upload_job.status = 'FAILED'
            upload_job.save()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        tenant = get_default_tenant()
        if not tenant:
            return AuditLog.objects.none()
        qs = AuditLog.objects.filter(tenant=tenant).select_related('user', 'emission_record')
        record_id = self.request.query_params.get('record_id')
        if record_id:
            qs = qs.filter(emission_record_id=record_id)
        return qs.order_by('-created_at')[:100]


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def dashboard_stats(request):
    tenant = get_default_tenant()
    if not tenant:
        return Response({'error': 'No tenant'}, status=status.HTTP_404_NOT_FOUND)

    records = EmissionRecord.objects.filter(tenant=tenant)
    total = records.count()
    pending = records.filter(status='PENDING').count()
    approved = records.filter(status='APPROVED').count()
    flagged = records.filter(status='FLAGGED').count()
    rejected = records.filter(status='REJECTED').count()

    co2_stats = records.aggregate(
        total_co2=Sum('normalized_co2_kg'),
        scope1=Sum('normalized_co2_kg', filter=Q(scope='SCOPE1')),
        scope2=Sum('normalized_co2_kg', filter=Q(scope='SCOPE2')),
        scope3=Sum('normalized_co2_kg', filter=Q(scope='SCOPE3')),
    )

    recent_uploads = DataUploadJob.objects.filter(tenant=tenant).values(
        'id', 'source_type', 'filename', 'status', 'success_rows', 'failed_rows', 'uploaded_at'
    ).order_by('-uploaded_at')[:5]

    data = {
        'total_records': total,
        'pending_count': pending,
        'approved_count': approved,
        'flagged_count': flagged,
        'rejected_count': rejected,
        'total_co2_kg': co2_stats['total_co2'] or 0,
        'scope1_kg': co2_stats['scope1'] or 0,
        'scope2_kg': co2_stats['scope2'] or 0,
        'scope3_kg': co2_stats['scope3'] or 0,
        'recent_uploads': list(recent_uploads),
    }
    return Response(data)

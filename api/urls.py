from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'tenants', views.TenantViewSet, basename='tenant')
router.register(r'facilities', views.FacilityViewSet, basename='facility')
router.register(r'upload-jobs', views.DataUploadJobViewSet, basename='uploadjob')
router.register(r'records', views.EmissionRecordViewSet, basename='record')
router.register(r'audit-logs', views.AuditLogViewSet, basename='auditlog')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/stats/', views.dashboard_stats, name='dashboard-stats'),
]

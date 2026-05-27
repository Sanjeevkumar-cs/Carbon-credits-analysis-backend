from django.contrib import admin
from .models import Tenant, Facility, UnitConversion, DataUploadJob, EmissionRecord, AuditLog

admin.site.register(Tenant)
admin.site.register(Facility)
admin.site.register(UnitConversion)
admin.site.register(DataUploadJob)
admin.site.register(EmissionRecord)
admin.site.register(AuditLog)

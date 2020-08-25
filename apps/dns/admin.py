from django.contrib import admin

from .models import ZoneExtra, DynamicEntry
from rest_framework.authtoken.admin import TokenAdmin

TokenAdmin.raw_id_fields = ['user']

#admin.site.register(User, TokenAdmin)
# Register your models here.

admin.site.register(ZoneExtra)
admin.site.register(DynamicEntry)



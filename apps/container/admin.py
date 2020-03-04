from django.contrib import admin

from .models import IP, Container, Hostkey, Project

# Register your models here.

admin.site.register(Project)
admin.site.register(Container)
admin.site.register(IP)
admin.site.register(Hostkey)

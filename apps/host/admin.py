from django.contrib import admin

from .models import Host, Image, Subnet

# Register your models here.

admin.site.register(Host)
admin.site.register(Subnet)
admin.site.register(Image)

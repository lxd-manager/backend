from django.contrib import admin

from .models import IP, Container, Hostkey, Project

# Register your models here.

class IsIPv4Filter(admin.SimpleListFilter):
    title = 'Address class'
    parameter_name = 'class'

    def lookups(self, request, model_admin):
        return (
            ('IPv4', 'IPv4'),
            ('IPv6', 'IPv6'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        v4ids = []
        for ip in queryset.all():
            if ip.is_ipv4:
                v4ids.append(ip.pk)
        if value == 'IPv4':
            return queryset.filter(id__in=v4ids)
        elif value == 'IPv6':
            return queryset.exclude(id__in=v4ids)
        return queryset


class IPAdmin(admin.ModelAdmin):
    list_filter = (IsIPv4Filter, )

admin.site.register(Project)
admin.site.register(Container)
admin.site.register(IP, IPAdmin)
admin.site.register(Hostkey)

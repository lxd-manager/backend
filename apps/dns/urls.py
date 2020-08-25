from rest_framework import routers

from .views import DNSViewSet, DynamicViewSet

router = routers.DefaultRouter()
router.register(r'zoneextra', DNSViewSet, basename='zoneextra')
router.register(r'dynamicentry', DynamicViewSet, basename='dynamicentry')

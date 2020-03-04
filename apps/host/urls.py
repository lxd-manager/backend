from rest_framework import routers

from .views import HostViewSet, ImageViewSet, SubnetViewSet

router = routers.DefaultRouter()
router.register(r'host', HostViewSet, basename='host')
router.register(r'subnet', SubnetViewSet, basename='subnet')
router.register(r'image', ImageViewSet, basename='image')

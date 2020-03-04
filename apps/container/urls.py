from rest_framework import routers

from .views import ContainerViewSet, IPViewSet

router = routers.DefaultRouter()
router.register(r'container', ContainerViewSet, basename='container')
router.register(r'ip', IPViewSet, basename='ip')

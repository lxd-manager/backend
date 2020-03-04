from rest_framework import routers

from .views import ProjectViewSet, UserViewSet

router = routers.DefaultRouter()
router.register(r'user', UserViewSet, basename='user')
router.register(r'project', ProjectViewSet, basename='project')

from apps.container.serializers import ContainerSlimSerializer
from .serializers import ProjectSerializer, UserSerializer

class ProjectFatSerializer(ProjectSerializer):
    containers = ContainerSlimSerializer(source='container_set', many=True, read_only=True)
    users = UserSerializer(many=True)
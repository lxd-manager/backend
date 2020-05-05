from apps.container.serializers import ContainerSerializer
from .serializers import ProjectSerializer, UserSerializer

class ProjectFatSerializer(ProjectSerializer):
    containers = ContainerSerializer(source='container_set', many=True, read_only=True)
    users = UserSerializer(many=True)
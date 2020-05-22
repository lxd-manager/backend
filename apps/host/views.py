from rest_framework import viewsets

from apps.account.drf import IsStaff, IsSuperuser, is_sudo

from .models import Host, Image, Subnet
from .serializers import HostSerializer, ImageSerializer, SubnetSerializer

# Create your views here.


class HostViewSet(viewsets.ModelViewSet):
    serializer_class = HostSerializer

    queryset = Host.objects.all()

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsStaff]
        else:
            permission_classes = [IsSuperuser]
        return [permission() for permission in permission_classes]


class SubnetViewSet(viewsets.ModelViewSet):
    serializer_class = SubnetSerializer

    queryset = Subnet.objects.all()

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsStaff]
        else:
            permission_classes = [IsSuperuser]
        return [permission() for permission in permission_classes]


class ImageViewSet(viewsets.ModelViewSet):
    serializer_class = ImageSerializer

    def get_queryset(self):
        if is_sudo(self.request):
            queryset = Image.objects.all()
        else:
            queryset = Image.objects.filter(sync=False).exclude(available=None)
        return queryset

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsStaff]
        else:
            permission_classes = [IsSuperuser]
        return [permission() for permission in permission_classes]

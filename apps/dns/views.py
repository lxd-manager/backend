from rest_framework import viewsets

from apps.account.drf import IsStaff, IsSuperuser, is_sudo

from .models import ZoneExtra, DynamicEntry
from .serializers import ZoneSerializer, DynamicSerializer

# Create your views here.


class DNSViewSet(viewsets.ModelViewSet):
    serializer_class = ZoneSerializer

    queryset = ZoneExtra.objects.all()

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsStaff]
        else:
            permission_classes = [IsSuperuser]
        return [permission() for permission in permission_classes]

class DynamicViewSet(viewsets.ModelViewSet):
    serializer_class = DynamicSerializer

    queryset = DynamicEntry.objects.all()

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsStaff]
        else:
            permission_classes = [IsSuperuser]
        return [permission() for permission in permission_classes]


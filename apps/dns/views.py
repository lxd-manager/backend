from rest_framework import viewsets

from apps.account.drf import IsStaff, IsSuperuser, is_sudo

from rest_framework.permissions import IsAuthenticated

from .models import ZoneExtra, DynamicEntry
from .serializers import ZoneSerializer, DynamicSerializer, DynamicUpdateSerializer

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


    #queryset = DynamicEntry.objects.all()
    def get_queryset(self):
        if is_sudo(self.request):
            queryset = DynamicEntry.objects.all()
        else:
            queryset = DynamicEntry.objects.filter(owners=self.request.user)
        return queryset

    def get_serializer_class(self):
        serializer_class = self.serializer_class
        if self.action == 'update':
            serializer_class = DynamicUpdateSerializer
        return serializer_class

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'retrieve', 'update']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsSuperuser]
        return [permission() for permission in permission_classes]


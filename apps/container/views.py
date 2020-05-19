from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.account.drf import IsStaff, IsSuperuser

from .models import IP, Container, Hostkey
from .serializers import ContainerCreateSerializer, ContainerSerializer, ContainerFatSerializer, ContainerKeySerializer, IPAdminSerializer, IPSerializer
from .tasks import container_action, container_reconfig_ip, container_reconfig_keys, delete_container, container_migrate


class IPViewSet(viewsets.ModelViewSet):
    serializer_class = IPSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            queryset = IP.objects.all()
        else:
            queryset = IP.objects.filter(Q(container__isnull=True, siit_ip__isnull=True) | Q(
                container__project__users=self.request.user) | Q(
                siit_ip__container__project__users=self.request.user) | Q(
                container_target__project__users=self.request.user
            ))

        return queryset

    def get_serializer_class(self):
        serializer_class = self.serializer_class
        if self.request.user.is_superuser:
            serializer_class = IPAdminSerializer
        return serializer_class

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'retrieve', 'update']:
            permission_classes = [IsStaff]
        else:
            permission_classes = [IsSuperuser]
        return [permission() for permission in permission_classes]

    def perform_update(self, serializer):
        try:
            previousct = Container.objects.get(ip=serializer.instance.id)
        except Exception as e:
            print("error", e)
            previousct = None
        print("previously ct", previousct)
        # serializer.instance.container = None
        serializer.save()
        if previousct is not None:
            container_reconfig_ip.delay(previousct.id)
        if serializer.instance.container_target:
            container_reconfig_ip.delay(serializer.instance.container_target.id)


class ContainerViewSet(viewsets.ModelViewSet):
    serializer_class = ContainerSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            queryset = Container.objects.all()
        else:
            queryset = Container.objects.filter(project__users=self.request.user)
        return queryset

    def get_serializer_class(self):
        serializer_class = self.serializer_class
        if self.action == 'create':
            serializer_class = ContainerCreateSerializer
        if self.action == 'list':
            serializer_class = ContainerFatSerializer
        if self.action == 'import_keys':
            serializer_class = ContainerKeySerializer
        return serializer_class

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        # if self.action in ['list', 'retrieve']:
        #    permission_classes = [IsStaff]
        # else:
        permission_classes = [IsStaff]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        ct: Container
        ct = self.get_object()
        ct.target_status_code = 103
        ct.save()

        container_action.delay(ct.id, 'start')

        serializer = ContainerSerializer(instance=ct, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        ct: Container
        ct = self.get_object()
        ct.target_status_code = 102
        ct.save()

        container_action.delay(ct.id, 'stop')

        serializer = ContainerSerializer(instance=ct, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def restart(self, request, pk=None):
        ct: Container
        ct = self.get_object()
        ct.target_status_code = 103
        ct.save()

        container_action.delay(ct.id, 'restart')

        serializer = ContainerSerializer(instance=ct, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post','get'], permission_classes=[IsSuperuser])
    def import_keys(self, request, pk=None):
        ct: Container
        ct = self.get_object()
        if request.method != 'POST':
            return Response({"run":"for i in /etc/ssh/ssh_host_*; do echo $i; cat $i; echo ''; done"})

        data = request.POST["keyimport"]
        parts = data.split("/etc/ssh")
        keytypes = [t[1] for t in Hostkey.TYPE]
        keys = {k:{} for k in keytypes}
        for p in parts:
            k = p.split("\n")
            for type in keytypes:
                if k[0].strip().endswith("host_%s_key"%type):
                    keys[type]["private"] = "\n".join(k[1:]).strip()
                if k[0].strip().endswith("host_%s_key.pub" % type):
                    keys[type]["public"] = "\n".join(k[1:]).strip()

        if not ct.hostkey_set.exists():
            for t, k in keys.items():
                Hostkey.objects.create(type=t, private=k['private'], public=k['public'], container=ct)

        serializer = ContainerSerializer(instance=ct, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def redeploy_keys(self, request, pk=None):
        ct: Container
        ct = self.get_object()

        container_reconfig_keys.delay(ct.id)

        serializer = ContainerSerializer(instance=ct, context={'request': request})
        return Response(serializer.data)

    def perform_destroy(self, instance):
        ct = self.get_object()
        ct.target_status_code = 113
        ct.save()
        delete_container.delay(instance.id)

    def perform_update(self, serializer):
        previoushost = serializer.instance.host
        print(previoushost)
        host = serializer.validated_data.get("host")
        serializer.save()
        if previoushost != host:
            container_migrate.delay(serializer.instance.id, previoushost.id)



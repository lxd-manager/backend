import json

from django.db.models import Q
from django.utils.crypto import get_random_string
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.account.drf import is_sudo
from apps.account.serializers import MyProjectSerializer, MyProjectLinkSerializer
from apps.host.models import Host
from apps.host.serializers import HostSerializer

from ipaddress import ip_interface

from .models import IP, Container, Hostkey, Project
from .tasks import create_container


class MyContainerSerializer(serializers.HyperlinkedRelatedField):
    def get_queryset(self):
        if is_sudo(self.context['request']):
            return Container.objects.all()
        return Container.objects.filter(project__users=self.context['request'].user)


class MySIITSerializer(serializers.HyperlinkedRelatedField):
    def get_queryset(self):
        user = self.context['request'].user
        if is_sudo(self.context['request']):
            queryset = IP.objects.all()
        else:
            queryset = IP.objects.filter(
                Q(container__isnull=True, siit_ip__isnull=True) | Q(
                    container__project__users=user) | Q(
                    siit_ip__container__project__users=user) | Q(
                    container_target__project__users=user
                ))
        legacy = []
        for q in queryset:
            if q.is_ipv4:
                legacy.append(q.id)
        print("legacy IPS:", legacy)
        return queryset.exclude(id__in=legacy)


class IPSerializer(serializers.ModelSerializer):
    container_target = MyContainerSerializer(view_name='container-detail', required=False, allow_null=True)
    siit_map = MySIITSerializer(view_name='ip-detail', required=False, allow_null=True)
    container = serializers.HyperlinkedRelatedField(view_name="container-detail", read_only=True)
    is_ipv4 = serializers.ReadOnlyField()

    def validate(self, data):
        ipif = ip_interface("%s/%s" % (data.get("ip",self.instance.ip), data.get("prefixlen",self.instance.prefixlen)))
        if data.get("container_target",None) is not None:
            ipnet=data["container_target"].host.subnet.get_network()
            if ipif.network != ipnet:
                raise serializers.ValidationError("The Host of this container does not route this network.")
        return data

    class Meta:
        model = IP
        fields = ('ip', 'url', 'is_ipv4', 'prefixlen', 'siit_map', 'container', 'container_target')
        extra_kwargs = {'ip': {'read_only': True},
                        'prefixlen': {'read_only': True}}


class IPAdminSerializer(IPSerializer):
    class Meta(IPSerializer.Meta):
        extra_kwargs = {'ip': {'read_only': False}, 'prefixlen': {'read_only': False}}


class HostkeySerializer(serializers.ModelSerializer):
    class Meta:
        model = Hostkey
        fields = ('type', 'public')


class ContainerSerializer(serializers.ModelSerializer):
    ips = IPSerializer(source='get_all_ips', many=True, read_only=True)
    state = serializers.JSONField(read_only=True, allow_null=True)
    project = MyProjectLinkSerializer(required=False, allow_null=True, view_name='project-detail')
    hostkeys = HostkeySerializer(source="hostkey_set", read_only=True, many=True)
    host = serializers.HyperlinkedRelatedField(view_name='host-detail', queryset=Host.objects.all())

    class Meta:
        model = Container
        fields = ('id', 'url', 'name', 'description', 'project', 'host', 'ips', "state", "state_version", "config", "nesting_enabled",
                  'target_status_code', 'hostkeys', "cloud_diffs", "custom_network")
        extra_kwargs = {'project': {'required': False},
                        'description': {'required': False},
                        'state_version': {'read_only': True},
                        'target_status_code': {'read_only': True},
                        'config': {'read_only': True},
                        'name': {'read_only': True},
                        'host': {'read_only': True}}


class ContainerFatSerializer(ContainerSerializer):
    project = MyProjectSerializer(required=False, allow_null=True)
    host = HostSerializer(read_only=True)


class ContainerKeySerializer(ContainerSerializer):
    keyimport = serializers.CharField(style={'base_template': 'textarea.html'})

    class Meta(ContainerSerializer.Meta):
        extra_kwargs = {'name': {'read_only': True}, }
        fields = ('name', 'keyimport')

class ContainerCreateSerializer(ContainerSerializer):
    host = serializers.HyperlinkedRelatedField(view_name='host-detail', read_only=False, queryset=Host.objects.all())
    name = serializers.CharField(read_only=False, validators=[UniqueValidator(queryset=Container.objects.all(), lookup='iexact')])

    class Meta(ContainerSerializer.Meta):
        extra_kwargs = {'config': {'read_only': False}}
        fields = ('name', 'description', 'project', 'host', "config")

    def create(self, validated_data):
        print(validated_data)

        if ("project" not in validated_data) or (validated_data["project"] is None):
            # create a new project for this container
            unique_id = get_random_string(length=8)
            pr = Project.objects.create(name=f'{validated_data["name"]}-single-{unique_id}')
            user = self.context['request'].user
            pr.users.add(user)
            validated_data["project"] = pr

        validated_data["state"] = json.dumps({'status': 'Created', 'status_code': 114})
        validated_data["target_status_code"] = 102

        instance = super().create(validated_data)
        create_container.delay(instance.id)
        return instance

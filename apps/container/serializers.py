import json

from django.db.models import Q
from django.utils.crypto import get_random_string
from rest_framework import serializers

from apps.account.serializers import MyProjectSerializer
from apps.host.models import Host

from .models import IP, Container, Hostkey, Project
from .tasks import create_container


class MyContainerSerializer(serializers.HyperlinkedRelatedField):
    def get_queryset(self):
        if self.context['request'].user.is_superuser:
            return Container.objects.all()
        return Container.objects.filter(project__users=self.context['request'].user)


class MySIITSerializer(serializers.HyperlinkedRelatedField):
    def get_queryset(self):
        user = self.context['request'].user
        if user.is_superuser:
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

    class Meta:
        model = IP
        fields = ('ip', 'url', 'prefixlen', 'siit_map', 'container', 'container_target')
        extra_kwargs = {'ip': {'read_only': True},
                        'prefixlen': {'read_only': True}}

    def validate(self, data):
        """
        Check that start is before finish.
        """
        if data['siit_map'] is not None and data['container_target'] is not None:
            raise serializers.ValidationError("Either attach or translate")
        return data


class IPAdminSerializer(IPSerializer):
    class Meta(IPSerializer.Meta):
        extra_kwargs = {'ip': {'read_only': False}, 'prefixlen': {'read_only': False}}


class HostkeySerializer(serializers.ModelSerializer):
    class Meta:
        model = Hostkey
        fields = ('type', 'public')


class ContainerSerializer(serializers.ModelSerializer):
    ips = IPSerializer(source='ip_set', many=True, read_only=True)
    state = serializers.JSONField(read_only=True, allow_null=True)
    project = MyProjectSerializer(required=False, allow_null=True, view_name='project-detail')
    hostkeys = HostkeySerializer(source="hostkey_set", read_only=True, many=True)
    host = serializers.HyperlinkedRelatedField(view_name='host-detail', read_only=True)

    class Meta:
        model = Container
        fields = ('id', 'url', 'name', 'project', 'host', 'ips', "state", "state_version", "config", "nesting_enabled",
                  'target_status_code', 'hostkeys')
        extra_kwargs = {'project': {'required': False},
                        'state_version': {'read_only': True},
                        'target_status_code': {'read_only': True},
                        'config': {'read_only': True},
                        'name': {'read_only': True},
                        'host': {'read_only': True}}


class ContainerCreateSerializer(ContainerSerializer):
    host = serializers.HyperlinkedRelatedField(view_name='host-detail', read_only=False, queryset=Host.objects.all())

    class Meta(ContainerSerializer.Meta):
        extra_kwargs = {'config': {'read_only': False},
                        'name': {'read_only': False}}
        fields = ('name', 'project', 'host', "config")

    def create(self, validated_data):
        print(validated_data)

        if validated_data["project"] is None:
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
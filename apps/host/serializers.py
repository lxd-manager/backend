import json

from rest_framework import serializers

from .models import Host, Image, Subnet
from .tasks import authenticate_host


class SubnetSerializer(serializers.ModelSerializer):

    class Meta:
        model = Subnet
        fields = ('id', 'ip', 'prefixlen')


class ImageSerializer(serializers.ModelSerializer):
    available = serializers.HyperlinkedRelatedField(many=True, view_name='host-detail', read_only=True)

    class Meta:
        model = Image
        fields = ('id', 'url', 'properties', 'description', 'fingerprint', 'available', 'sync', 'remove', 'server', 'protocol', 'alias')
        extra_kwargs = {'properties': {'read_only': True},
                        'description': {'read_only': True},
                        'fingerprint': {'required': False}}


class HostSerializer(serializers.ModelSerializer):
    subnet = serializers.HyperlinkedRelatedField(view_name='subnet-detail', queryset=Subnet.objects.all())
    trust_password = serializers.CharField(write_only=True, required=False)
    used_memory = serializers.SerializerMethodField('get_memory')
    images = serializers.HyperlinkedRelatedField(many=True, view_name='image-detail', read_only=True, source='image_set')

    def get_memory(self, obj: Host):
        m = 0
        for ct in obj.container_set.all():
            try:
                st = json.loads(ct.state)
                m += st["memory"]["usage"]
            except Exception:
                pass
        return m

    class Meta:
        model = Host
        fields = ('id', 'url', 'name', 'subnet', 'api_url', 'trust_password', 'used_memory', 'monitoring_url', 'images')

    def create(self, validated_data):
        pw = validated_data.pop('trust_password', '')
        instance = super().create(validated_data)
        authenticate_host.delay(instance.id, pw)
        return instance

class HostFatSerializer(HostSerializer):
    container_states = serializers.SerializerMethodField()

    class Meta(HostSerializer.Meta):
        fields = ('id', 'url', 'name', 'subnet', 'api_url', 'trust_password', 'used_memory', 'monitoring_url', 'images', 'container_states')

    def get_container_states(self, host):
        states = {}
        for c in host.container_set.all():
            s = c.status_code
            if s not in states:
                states[s] = 0
            states[s] += 1
        return states

class HostSlimSerializer(HostSerializer):
    class Meta(HostSerializer.Meta):
        fields = ('url', 'name')

class ImageFatSerializer(ImageSerializer):
    available = HostSerializer(many=True)
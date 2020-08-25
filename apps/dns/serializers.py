import json

from rest_framework import serializers

from .models import ZoneExtra, DynamicEntry


class ZoneSerializer(serializers.ModelSerializer):

    class Meta:
        model = ZoneExtra
        fields = ('entry', 'url', 'description')


class DynamicSerializer(serializers.ModelSerializer):

    class Meta:
        model = DynamicEntry
        fields = ('format', 'url', 'value', 'owners')

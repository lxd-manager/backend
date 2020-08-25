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
        fields = ('format', 'url', 'value', 'owners', 'combined')

class DynamicUpdateSerializer(serializers.ModelSerializer):

    def validate_value(self, value):
        """
        Check that the value has no newlines
        """
        if '\n' in value or '\r' in value:
            raise serializers.ValidationError("No newlines are allowed")
        return value

    class Meta:
        model = DynamicEntry
        fields = ('value', )


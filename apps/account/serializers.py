
from django.contrib.auth.models import User
from rest_framework import serializers

from apps.container.models import Project


class UserSerializer(serializers.ModelSerializer):
    approved = serializers.SerializerMethodField(read_only=False)
    superuser = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'url', 'first_name', 'last_name', 'approved', 'superuser')
        extra_kwargs = {'username': {'read_only': True}}

    def get_approved(self, user):
        return user.has_perm('container.view_container')
    def get_superuser(self, user):
        return user.is_superuser


class ProjectSerializer(serializers.ModelSerializer):
    containers = serializers.HyperlinkedRelatedField(source='container_set', many=True, view_name="container-detail", read_only=True)
    users = serializers.HyperlinkedRelatedField(many=True, view_name='user-detail', queryset=User.objects.all())

    class Meta:
        model = Project
        fields = ('id', 'name', 'users', 'url', 'containers')
        extra_kwargs = {'name': {'read_only': True}}


class MyProjectSerializer(ProjectSerializer):
    def get_queryset(self):
        return Project.objects.filter(users=self.context['request'].user)


class MyProjectSlimSerializer(MyProjectSerializer):
    class Meta(MyProjectSerializer.Meta):
        fields = ('name', 'url')
        #extra_kwargs = {'name': {'read_only': True}}


class MyProjectLinkSerializer(serializers.HyperlinkedRelatedField):
    def get_queryset(self):
        return Project.objects.filter(users=self.context['request'].user)


class ProjectCreateSerializer(ProjectSerializer):

    class Meta(ProjectSerializer.Meta):
        extra_kwargs = {'name': {'read_only': False}}

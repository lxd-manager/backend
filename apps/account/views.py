# from django.shortcuts import render
import gitlab
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.container.models import Project

from .drf import IsStaff, IsSuperuser
from .serializers import ProjectCreateSerializer, ProjectSerializer, UserSerializer


class UserViewSet(ModelViewSet):

    serializer_class = UserSerializer

    def get_queryset(self):
        if self.request.user.is_superuser or self.action == 'list':
            queryset = User.objects.all()
        else:
            queryset = User.objects.filter(pk=self.request.user.pk)
        return queryset

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['list', 'retrieve', 'me']:
            permission_classes = [IsStaff]
        else:
            permission_classes = [IsSuperuser]
        return [permission() for permission in permission_classes]

    def _detail_user(self, request, instance):
        serializer = self.get_serializer(instance)

        if request.user != instance:
            return Response(serializer.data)

        gl = gitlab.Gitlab(getattr(settings, "SOCIAL_AUTH_GITLAB_API_URL"),
                           oauth_token=request.user.social_auth.get().access_token)
        gl.auth()
        current_user = gl.user
        keys = []
        for k in current_user.keys.list():
            keys.append({"title": k.title, "key": k.key})

        return Response({**serializer.data, "superuser": request.user.is_superuser, "sshkeys": keys})

    @action(detail=False, methods=['get'])
    def me(self, request, pk=None):
        instance = request.user
        return self._detail_user(request, instance)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return self._detail_user(request, instance)


class ProjectViewSet(ModelViewSet):
    serializer_class = ProjectSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            queryset = Project.objects.all()
        else:
            queryset = Project.objects.filter(users=self.request.user)
        return queryset

    def get_serializer_class(self):
        serializer_class = self.serializer_class
        if self.action == 'create':
            serializer_class = ProjectCreateSerializer
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

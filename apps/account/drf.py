from rest_framework.permissions import BasePermission
from rest_framework.authentication import SessionAuthentication

def is_sudo(request):
    hdr = int(request.META.get('HTTP_X_SUDO', 1))
    return request.user and request.user.is_superuser and hdr == 1

class IsSuperuser(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return is_sudo(request)


class IsStaff(BasePermission):
    """
    Allows access only to admin users.
    """

    def has_permission(self, request, view):
        return request.user and request.user.has_perm('container.view_container')


class CsrfExemptSessionAuthentication(SessionAuthentication):

    def enforce_csrf(self, request):
        return  # To not perform the csrf check previously happening
from __future__ import absolute_import, unicode_literals

from celery import shared_task
from django.conf import settings
from pylxd import Client

from .models import Host


@shared_task
def authenticate_host(host_id, pw):

    host = Host.objects.get(id=host_id)

    client = Client(endpoint=host.api_url, cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")),
                    verify=getattr(settings, "LXD_CA_CERT"), timeout=60)

    if not client.trusted:
        client.authenticate(pw)

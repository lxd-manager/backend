from __future__ import absolute_import, unicode_literals

import json
import urllib3
from datetime import datetime, timedelta, timezone
from ipaddress import ip_interface, IPv6Interface

from celery import shared_task
from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models.functions import Now
from django.utils.text import slugify
from pylxd import Client
from pylxd.exceptions import LXDAPIException, NotFound
from pylxd import models

from apps.container.models import IP, Container
from apps.host.models import Host, Image


@shared_task
def synchost(host_id):
    host = Host.objects.get(pk=host_id)

    try:
        syncing = False
        h = None
        with transaction.atomic():
            try:
                h = Host.objects.select_for_update(nowait=True).get(id=host_id)
                if h.syncing is not None:
                    syncing = True
                    if h.syncing < datetime.now(timezone.utc) - timedelta(minutes=3):
                        print("%s: remove stale lock" % host.name )
                        syncing = False
                        h.syncing = Now()
                        h.save()
                else:
                    h.syncing = Now()
                    h.save()
            except DatabaseError:
                syncing = True

        if syncing:
            print("already processing %s (abort), started: %s" % (host.name, h.syncing))
            return

        client = Client(endpoint=host.api_url, cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")),
                        verify=getattr(settings, "LXD_CA_CERT"), timeout=60)

        if not getattr(settings, "LXD_CA_CERT"):
            urllib3.disable_warnings()

        existingcts = []
        for ct in client.containers.all():
            c = Container.objects.get_or_create(name=ct.name, host=host)[0]
            existingcts.append(c)

            existingips = []
            c.state = json.dumps(ct.api.state.get().json()['metadata'])
            c.config = json.dumps(ct.expanded_config)
            try:
                if int(json.loads(c.state)["status_code"]) == c.target_status_code:
                    print("%s :reached status code" % c.name)
                    c.target_status_code = None
            except Exception as e:
                print("%s :failed on "%c, e)
                pass
            c.save()
            if int(json.loads(c.state)["status_code"]) == 103: # only running contianers
                try:
                    #if hasattr(ct.state(), "network") and ct.state().network is not None:
                    for ifname, ifstate in ct.state().network.items():
                        if ifstate['state'] == 'up':
                            for ifaddr in ifstate["addresses"]:
                                ipif = ip_interface("%s/%s" % (ifaddr["address"], ifaddr["netmask"]))
                                if ipif.is_global:
                                    ip = IP.objects.get_or_create(ip="%s" % ipif.ip, prefixlen=ipif.network.prefixlen)[0]
                                    ip.container = c
                                    if isinstance(ipif, IPv6Interface):
                                        ip.container_target = c
                                    ip.save()
                                    existingips.append(ip)
                except AttributeError:
                    pass
                for i in c.ip_set.all():
                    if i not in existingips:
                        if i.is_ipv4:
                            i.container = None
                            i.save()
                        else:
                            i.delete()

        for c in host.container_set.all():
            if c not in existingcts:
                if c.status_code != 114:
                    c.state = json.dumps({'status': 'Deleted', 'status_code': 113})
                    c.save()

                    # delete old stale
                    if not isinstance(c.state_version, Now):
                        if c.state_version < datetime.now(timezone.utc) - timedelta(minutes=10):
                            c.delete()

        fingerprints = []
        available_aliases = []
        for image in client.images.all():
            # check for aliases

            io = Image.objects.get_or_create(properties=json.dumps(image.properties), fingerprint=image.fingerprint)[0]
            io.available.add(host)
            if io.remove:
                image: models.image.Image
                image.delete()
            else:
                available_aliases += [a['name'] for a in image.aliases]
                fingerprints.append(image.fingerprint)

        for image in Image.objects.all():
            if image.fingerprint not in fingerprints:
                image.available.remove(host)
            if image.sync and image.alias not in available_aliases:
                # bring it there
                try:
                    if image.protocol == Image.SIMPLESTREAMS:
                        client.images.create_from_simplestreams(image.server, alias=None, new_alias=image.alias, public=False, auto_update=True)
                    else:
                        client.images.create_from_image(image.server, alias=image.alias, public=False, auto_update=True)
                except:
                    pass

        print("finished syncing %s" % host.name)
        h.syncing = None
        h.save()

    except LXDAPIException:
        h.syncing = None
        h.save()
        return


@shared_task
def synclxd():
    for host in Host.objects.all():
        synchost.delay(host.id)


@shared_task
def create_container(container_id):
    try:
        ct = Container.objects.get(pk=container_id)
        client = Client(endpoint=ct.host.api_url,
                        cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")), verify=getattr(settings, "LXD_CA_CERT"))

        configs = {}
        configs.update(ct.get_host_key_config())
        configs.update(ct.project.get_ssh_config())
        configs.update(ct.get_network_config())

        ic = json.loads(ct.config)
        configs.update({"security.nesting": ic.get('config', {}).get("security.nesting", 'false')})
        conf = {"name": ct.name, 'source': {'type': 'image', "fingerprint": ic['source']['fingerprint'], },
                'profiles': ['default'],
                "config": configs}

        client.containers.create(conf, wait=False)
    except Exception as e:
        print(e)


@shared_task
def delete_container(container_id):
    try:
        ct = Container.objects.get(pk=container_id)

        client = Client(endpoint=ct.host.api_url,
                        cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")), verify=getattr(settings, "LXD_CA_CERT"))

        try:
            lct = client.containers.get(ct.name)
            lct.delete()
        except NotFound:
            pass

        ct.delete()
    except Exception as e:
        print(e)


@shared_task
def container_action(container_id, action):
    try:
        co = Container.objects.get(pk=container_id)
        client = Client(endpoint=co.host.api_url,
                        cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")), verify=getattr(settings, "LXD_CA_CERT"))

        ct = client.containers.get(co.name)

        if action in ["start", "stop", "restart"]:
            getattr(ct, action)()

    except Exception as e:
        print(e)

def reload_cloud_init(co, conf, restart=True):
    client = Client(endpoint=co.host.api_url, cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")),
                    verify=getattr(settings, "LXD_CA_CERT"))

    ct = client.containers.get(co.name)
    try:
        ct.start(wait=True)
    except Exception:
        pass
    ct.execute(['cloud-init', 'clean', '--seed'])
    ct.config.update(conf)
    ct.config["volatile.apply_template"] = "create"
    ct.save()
    if restart:
        ct.restart()


@shared_task
def container_reconfig_ip(container_id):
    co = Container.objects.get(pk=container_id)
    configs = co.get_network_config()
    reload_cloud_init(co, configs, restart=False)


@shared_task
def container_reconfig_keys(container_id):
    co = Container.objects.get(pk=container_id)
    configs = {}
    if co.project:
        configs = co.project.get_ssh_config()
    configs.update(co.get_host_key_config())
    reload_cloud_init(co, configs, restart=True)


@shared_task
def container_migrate(container_id, srchost_id):
    co = Container.objects.get(pk=container_id)
    srchost = Host.objects.get(pk=srchost_id)

    client_source = Client(endpoint=srchost.api_url, cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")),
                    verify=getattr(settings, "LXD_CA_CERT"))
    client_destination = Client(endpoint=co.host.api_url, cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")),
                    verify=getattr(settings, "LXD_CA_CERT"))
    cont = client_source.containers.get(co.name)

    state = cont.api.state.get().json()['metadata']["status_code"]
    was_running = False
    if int(state) != 102:
        if int(state) == 103:
            was_running = True
        cont.stop(wait=True)
    cont.migrate(client_destination, wait=True)

    if was_running:
        cont = client_destination.containers.get(co.name)
        cont.start(wait=True)
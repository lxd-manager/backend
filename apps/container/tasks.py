from __future__ import absolute_import, unicode_literals

import json
from datetime import datetime, timedelta, timezone
from ipaddress import ip_interface, IPv6Interface

from celery import shared_task
from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models.functions import Now
from django.utils.text import slugify
from pylxd import Client
from pylxd.exceptions import LXDAPIException, NotFound

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
                    if h.syncing < datetime.now(timezone.utc) - timedelta(minutes=10):
                        print("remove stale lock")
                        syncing = False
                        h.syncing = Now()
                        h.save()
                else:
                    h.syncing = Now()
                    h.save()
            except DatabaseError:
                syncing = True

        if syncing:
            print("already processing ", host.name, " (abort), started: ", h.syncing)
            return

        client = Client(endpoint=host.api_url, cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")),
                        verify=getattr(settings, "LXD_CA_CERT"), timeout=60)

        existingcts = []
        for ct in client.containers.all():
            c = Container.objects.get_or_create(name=ct.name, host=host)[0]
            existingcts.append(c)

            existingips = []
            c.state = json.dumps(ct.api.state.get().json()['metadata'])
            c.config = json.dumps(ct.expanded_config)
            try:
                if int(json.loads(c.state)["status_code"]) == c.target_status_code:
                    print("reached status code")
                    c.target_status_code = None
            except Exception as e:
                print("failed on ", e)
                pass
            c.save()
            if int(json.loads(c.state)["status_code"]) == 103: # only running contianers
                try:
                    #if hasattr(ct.state(), "network") and ct.state().network is not None:
                    for ifname, ifstate in ct.state().network.items():
                        if ifstate['state'] == 'up' and ifname == 'eth1':
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
            available_aliases += [a['name'] for a in image.aliases]

            io = Image.objects.get_or_create(properties=json.dumps(image.properties), fingerprint=image.fingerprint)[0]
            io.available.add(host)
            fingerprints.append(image.fingerprint)

        for image in Image.objects.all():
            if image.fingerprint not in fingerprints:
                image.available.remove(host)
            if image.sync and image.alias not in available_aliases:
                # bring it there
                if image.protocol == Image.SIMPLESTREAMS:
                    client.images.create_from_simplestreams(image.server, alias=None, new_alias=image.alias, public=False, auto_update=True)
                else:
                    client.images.create_from_image(image.server, alias=image.alias, public=False, auto_update=True)

        print("finished syncing ", host.name)
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


def reload_profiles(co, prs, restart=True):
    client = Client(endpoint=co.host.api_url, cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")),
                    verify=getattr(settings, "LXD_CA_CERT"))

    ct = client.containers.get(co.name)

    try:
        ct.start(wait=True)
    except Exception:
        pass
    ct.execute(['cloud-init', 'clean', '--seed'])
    # replace ssh profiles
    print("profiles to apply:", prs)
    newsshpr = None
    for npr in prs:
        if npr.startswith("ssh-"):
            newsshpr = npr
            print("there is a new ssh profile:", npr)
    oldpr = []
    print("current profiles:", ct.profiles)
    for p in ct.profiles:
        if p.startswith("ssh-") and (newsshpr is not None):
            continue
        else:
            oldpr.append(p)
    print("clean old profiles:",oldpr)
    ct.profiles = list(set(oldpr)+set(prs))
    print("now profiles:", ct.profiles)
    ct.save()

    ct = client.containers.get(co.name)
    ct.config["volatile.apply_template"] = "create"
    ct.save()

    if restart:
        ct.restart()


@shared_task
def container_ip(container_id):
    co = Container.objects.get(pk=container_id)
    net_profile = update_ip(co)
    print("new profiles", net_profile)

    reload_profiles(co, [net_profile], restart=False)


@shared_task
def container_keys(container_id):
    co = Container.objects.get(pk=container_id)
    profiles = update_profiles(co)

    reload_profiles(co, profiles)

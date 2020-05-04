import os
import subprocess
import tempfile

import gitlab
from django.conf import settings
from django.utils.text import slugify
from pylxd import Client

from .models import Container, Hostkey


def update_ip(ct: Container):
    ips = ct.ip_set.filter(container_target__isnull=False) | ct.target_ip.all()
    profile_name = "network-%d-%s" % (ct.id, slugify(ct.name))

    cloud_init = """version: 1
config:
  - type: physical
    name: eth0
    subnets:
      - type: dhcp
        control: auto
  - type: physical
    name: eth1
    subnets:
"""
    for ip in ips:
        if ip.is_ipv4:
            cloud_init += f"""      - type: static
        ipv4: true
        address: {ip.ip}
        netmask: {ip.get_interface().netmask}
        gateway: {ip.get_gateway()}
        control: auto
"""

    client = Client(endpoint=ct.host.api_url, cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")),
                    verify=getattr(settings, "LXD_CA_CERT"))
    try:
        pr = client.profiles.get(profile_name)
    except Exception:
        pr = client.profiles.create(profile_name)

    pr.config.update({'user.network-config': cloud_init})
    pr.save()

    return profile_name


def gen_keys():
    temp_folder_name = tempfile.mkdtemp(prefix='generate-cloud-init-ssh-host-keys')

    def generate_keys(key_type):
        private_key_filename = os.path.join(temp_folder_name, key_type)
        subprocess.check_call(['ssh-keygen', '-q', '-N', '', '-t', key_type, '-f', private_key_filename])
        public_key_filename = '%s.pub' % private_key_filename

        with open(private_key_filename, 'rt') as private_key_file:
            private_key = private_key_file.read()
        with open(public_key_filename, 'rt') as public_key_file:
            public_key = public_key_file.read()

        return (private_key, public_key)

    keys = {}

    for key_type in ['ecdsa', 'ed25519', 'rsa']:
        keys[key_type] = generate_keys(key_type)
        # keys['%s_private' % key_type] = PreservedScalarString(private_key)
        # keys['%s_public' % key_type] = PreservedScalarString(public_key)
        # keys['%s_private' % key_type] = private_key
        # keys['%s_public' % key_type] = public_key
    # ruamel.yaml.YAML().dump({'ssh_keys': keys}, sys.stdout)

    return keys


def update_hostkey(ct: Container):

    print("generate host keys")
    if not ct.hostkey_set.exists():
        # generate keys
        keys = gen_keys()
        for t, k in keys.items():
            Hostkey.objects.create(type=t, private=k[0], public=k[1], container=ct)

    # use keys
    keystr = ""
    for key in ct.hostkey_set.all():
        indentedkey = "\n    ".join(key.private.split('\n'))
        keystr += ("  %s_private: |\n    %s\n" % (key.type, indentedkey))
        keystr += ("  %s_public: %s\n" % (key.type, key.public))

    cloud_init = '#cloud-config\n\nssh_keys:\n%s' % keystr

    client = Client(endpoint=ct.host.api_url, cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")),
                    verify=getattr(settings, "LXD_CA_CERT"))

    profile_name = "hostkey-%d-%s" % (ct.id, slugify(ct.name))
    try:
        pr = client.profiles.get(profile_name)
    except Exception:
        pr = client.profiles.create(profile_name)

    pr.config.update({'user.vendor-data': cloud_init})
    pr.save()

    return profile_name


def update_profiles(ct: Container):
    keystr = ""
    for user in ct.project.users.all():
        try:
            gl = gitlab.Gitlab(getattr(settings, "SOCIAL_AUTH_GITLAB_API_URL"), oauth_token=user.social_auth.get().access_token)
            gl.auth()
            current_user = gl.user

            for k in current_user.keys.list():
                keystr += ("  - \"%s\"\n" % k.key)
        except Exception:
            pass

    client = Client(endpoint=ct.host.api_url, cert=(getattr(settings, "LXD_CRT"), getattr(settings, "LXD_KEY")),
                    verify=getattr(settings, "LXD_CA_CERT"))

    profile_name = "ssh-%d-%s" % (ct.project.id, slugify(ct.project.name))
    try:
        pr = client.profiles.get(profile_name)
    except Exception:
        pr = client.profiles.create(profile_name)

    cloud_init = '#cloud-config\n\nssh_authorized_keys:\n%s' % keystr

    pr.config.update({'user.user-data': cloud_init})
    pr.save()

    return [profile_name]

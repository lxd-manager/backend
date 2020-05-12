import json
from ipaddress import IPv4Interface, ip_interface

import gitlab

from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models.functions import Now
from django.conf import settings
from fernet_fields import EncryptedTextField

from apps.host.models import Host

from .utils import gen_keys


class Project(models.Model):
    name = models.CharField(max_length=200)
    users = models.ManyToManyField(User)

    def __str__(self):
        users = ", ".join([u.username for u in self.users.all()])
        return f"{self.name} with {users}"

    def get_ssh_config(self):
        keystr = ""
        for user in self.users.all():
            try:
                gl = gitlab.Gitlab(getattr(settings, "SOCIAL_AUTH_GITLAB_API_URL"),
                                   oauth_token=user.social_auth.get().access_token)
                gl.auth()
                current_user = gl.user

                for k in current_user.keys.list():
                    keystr += ("  - \"%s\"\n" % k.key)
            except Exception:
                pass

        cloud_init = '#cloud-config\n\nssh_authorized_keys:\n%s' % keystr

        return {'user.user-data': cloud_init}


class Container(models.Model):
    name = models.CharField(max_length=250)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True)
    host = models.ForeignKey(Host, on_delete=models.CASCADE)
    description = models.TextField(null=True, blank=True)

    state = models.TextField(null=True, blank=True)
    state_version = models.DateTimeField(null=True)
    config = models.TextField(null=True, blank=True)

    target_status_code = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("name", "host")

    def __str__(self):
        return f"{self.name}({self.project}) on {self.host.name}"

    @property
    def nesting_enabled(self):
        try:
            return json.loads(self.config).get("security.nesting", False)
        except Exception as e:
            print(self.config)
            print(e)
            return False

    @property
    def status_code(self):
        try:
            return json.loads(self.state).get("status_code", 400)
        except Exception:
            return 400

    @transaction.atomic
    def save(self, *args, **kw):
        if self.pk is not None:
            orig = Container.objects.get(pk=self.pk)
            if orig.state != str(self.state):
                self.state_version = Now()
        try:
            conf = json.loads(self.config)
            if 'user.vendor-data' in conf:
                conf['user.vendor-data'] = '****'
            self.config = json.dumps(conf)
        except Exception:
            pass
        super(Container, self).save(*args, **kw)

    def get_all_ips(self):
        return self.ip_set.all() | self.target_ip.all()

    def get_host_key_config(self):

        if not self.hostkey_set.exists():
            # generate keys
            keys = gen_keys()
            for t, k in keys.items():
                Hostkey.objects.create(type=t, private=k[0], public=k[1], container=self)

        # use keys
        keystr = ""
        for key in self.hostkey_set.all():
            indentedkey = "\n    ".join(key.private.split('\n'))
            keystr += ("  %s_private: |\n    %s\n" % (key.type, indentedkey))
            keystr += ("  %s_public: %s\n" % (key.type, key.public))

        cloud_init = '#cloud-config\n\nssh_keys:\n%s' % keystr
        return {'user.vendor-data': cloud_init}

    def get_network_config(self):
        ips = self.ip_set.filter(container_target__isnull=False) | self.target_ip.all()

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
        return {'user.network-config': cloud_init}

    @property
    def cloud_diffs(self):
        diffs = {}
        try:
            c = json.loads(self.config)
        except Exception as e:
            return {}

        for name, fn in [("user.network-config", self.get_network_config),
                         ("user.user-data", lambda: self.project.get_ssh_config() if self.project is not None else "-1"),
                         ("user.vendor-data", lambda: {"user.vendor-data": "****"})]:
            if name not in c:
                diffs[name] = {"present":False}
                continue
            real = c.get(name, "")
            target = fn()[name]
            if real == target:
                diffs[name]={"uptodate":True}
                continue
            diffs[name] =  {"real": real, "target": target[name]}
        return diffs


class Hostkey(models.Model):
    ECDSA = "ecdsa"
    ED25519 = "ed25519"
    RSA = "rsa"
    TYPE = ((ECDSA, 'ecdsa'), (ED25519, 'ed25519'), (RSA, 'rsa'))

    type = models.CharField(max_length=15, choices=TYPE)
    public = models.TextField()
    private = EncryptedTextField(null=True)

    container = models.ForeignKey(Container, on_delete=models.CASCADE)


class IP(models.Model):
    ip = models.GenericIPAddressField()
    prefixlen = models.PositiveIntegerField()

    container = models.ForeignKey(Container, on_delete=models.SET_NULL, null=True)
    container_target = models.ForeignKey(Container, on_delete=models.SET_NULL, null=True, related_name="target_ip")
    siit_map = models.ForeignKey('container.IP', on_delete=models.SET_NULL, null=True, related_name="siit_ip")

    def __str__(self):
        return "%s/%s" % (self.ip, self.prefixlen)

    def get_interface(self):
        return ip_interface(self.__str__())

    def get_gateway(self):
        return next(self.get_interface().network.hosts())

    @property
    def is_ipv4(self):
        return type(self.get_interface()) == IPv4Interface

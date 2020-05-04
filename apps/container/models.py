import json
from ipaddress import IPv4Interface, ip_interface

from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models.functions import Now
from fernet_fields import EncryptedTextField

from apps.host.models import Host


class Project(models.Model):
    name = models.CharField(max_length=200)
    users = models.ManyToManyField(User)

    def __str__(self):
        users = ", ".join([u.username for u in self.users.all()])
        return f"{self.name} with {users}"


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

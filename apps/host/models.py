import json
from ipaddress import IPv4Network, ip_network

from django.db import models

# Create your models here.


class Subnet(models.Model):
    ip = models.GenericIPAddressField()
    prefixlen = models.PositiveIntegerField()

    def __str__(self):
        return "%s/%s" % (self.ip, self.prefixlen)

    def get_network(self):
        return ip_network(self.__str__())

    @property
    def is_ipv4(self):
        return type(self.get_network()) == IPv4Network


class Host(models.Model):
    name = models.CharField(max_length=100)
    subnet = models.ForeignKey(Subnet, on_delete=models.SET_NULL, null=True)
    api_url = models.CharField(max_length=1000, null=True)
    syncing = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.name} in {self.subnet} at {self.api_url}"


class Image(models.Model):
    SIMPLESTREAMS = "simplestreams"
    LXD = "lxd"
    PROTOCOL = ((SIMPLESTREAMS, 'simplestreams'), (LXD, 'lxd'))

    properties = models.TextField()
    fingerprint = models.CharField(max_length=100)

    available = models.ManyToManyField(Host)
    sync = models.BooleanField(default=False)

    server = models.CharField(max_length=300, null=True)
    protocol = models.CharField(max_length=25, choices=PROTOCOL, default=LXD)
    alias = models.CharField(max_length=100, null=True)

    @property
    def description(self):
        try:
            return json.loads(self.properties).get("description", "")
        except Exception as e:
            print(e)
            return ""

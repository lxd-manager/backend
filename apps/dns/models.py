import json
from ipaddress import IPv4Network, ip_network

from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class ZoneExtra(models.Model):
    entry = models.TextField()
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.entry

class DynamicEntry(models.Model):
    format = models.TextField()
    value = models.TextField(null=True, blank=True)
    owners = models.ManyToManyField(User)

    @property
    def combined(self):
        return self.format % self.value

    def __str__(self):
        return self.format
import json
from ipaddress import IPv4Network, ip_network

from django.db import models

# Create your models here.


class ZoneExtra(models.Model):
    entry = models.TextField()
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.entry
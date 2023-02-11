import os

DNS_BASE_DOMAIN = os.environ.get('DNS_BASE_DOMAIN', ".")
DNS_CONTAINER_DOMAIN = os.environ.get('DNS_CONTAINER_DOMAIN', ".")
DNS_MIRROR_SERVER = os.environ.get('DNS_MIRROR_SERVER', "").strip()
DNS_ALLOW_TRANSFER = os.environ.get('DNS_ALLOW_TRANSFER', "").strip()
print("forwarding requests to: %s" % DNS_MIRROR_SERVER)
if DNS_MIRROR_SERVER == "":
    DNS_MIRROR_SERVER = None
if DNS_ALLOW_TRANSFER == "":
    DNS_ALLOW_TRANSFER = None

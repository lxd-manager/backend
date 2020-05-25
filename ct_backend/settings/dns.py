import os

DNS_BASE_DOMAIN = os.environ.get('DNS_BASE_DOMAIN', ".")
DNS_CONTAINER_DOMAIN = os.environ.get('DNS_CONTAINER_DOMAIN', ".")
DNS_MIRROR_SERVER = os.environ.get('DNS_MIRROR_SERVER', "").strip()

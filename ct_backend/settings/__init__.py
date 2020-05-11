import socket
import os

from get_docker_secret import get_docker_secret

from .auth import *  # noqa: F403,F401
from .base import *  # noqa: F403,F401
from .celery import *  # noqa: F403,F401
from .dns import *  # noqa: F403,F401
from .enc import *  # noqa: F403,F401
from .lxd import *  # noqa: F403,F401

try:
    from .secrets import *  # noqa: F403,F401
except ModuleNotFoundError:
    SECRET_KEY = get_docker_secret('secret_key', default='5st$_zh=r-g4eumpw@u%x9tl-o5%t9s5-4cr*@u()jjo9!s^3+').strip()
    SOCIAL_AUTH_GITLAB_KEY = get_docker_secret('social_auth_gitlab_key', default='wrong key').strip()
    SOCIAL_AUTH_GITLAB_SECRET = get_docker_secret('social_auth_gitlab_secret', default='wrong secret').strip()

if os.environ.get('DJANGO_DEBUG', False):
    DEBUG = True

# development maschine
if socket.gethostname() == 'larix':
    CELERY_BROKER_URL = "redis://localhost:6379"
    CELERY_RESULT_BACKEND = "redis://localhost:6379"
    LXD_CA_CERT = False
    ALLOWED_HOSTS = ['localhost']
    DEBUG = True

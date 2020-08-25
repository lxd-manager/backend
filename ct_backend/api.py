from rest_framework import routers

from apps.account.urls import router as account_router
from apps.container.urls import router as container_router
from apps.host.urls import router as host_router
from apps.dns.urls import router as dns_router

router = routers.DefaultRouter()
router.registry.extend(host_router.registry)
router.registry.extend(container_router.registry)
router.registry.extend(dns_router.registry)
router.registry.extend(account_router.registry)

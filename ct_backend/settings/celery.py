# from celery.schedules import crontab
import os

CELERY_BROKER_URL = os.environ.get("CONF_CELERY_BROKER_URL", "redis://redis:6379")
CELERY_RESULT_BACKEND = os.environ.get("CONF_CELERY_RESULT_BACKEND", "redis://redis:6379")
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

CELERY_BEAT_SCHEDULE = {
    'synclxd': {
        'task': 'apps.container.tasks.synclxd',
        'schedule': 30,  # crontab(minute=59, hour=23),
        # 'args': (*args)
    },
}

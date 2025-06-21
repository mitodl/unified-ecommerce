"""
Django settings for celery.
"""

from celery.schedules import crontab

from unified_ecommerce.envs import get_bool, get_int, get_string

USE_CELERY = True
CELERY_BROKER_URL = get_string("CELERY_BROKER_URL", get_string("REDIS_URL", None))
CELERY_RESULT_BACKEND = get_string(
    "CELERY_RESULT_BACKEND", get_string("REDIS_URL", None)
)
CELERY_TASK_ALWAYS_EAGER = get_bool("CELERY_TASK_ALWAYS_EAGER", False)  # noqa: FBT003
CELERY_TASK_EAGER_PROPAGATES = get_bool(
    "CELERY_TASK_EAGER_PROPAGATES",
    True,  # noqa: FBT003
)
CELERY_WORKER_MAX_MEMORY_PER_CHILD = get_int(
    "CELERY_WORKER_MAX_MEMORY_PER_CHILD", 250_000
)

CELERY_BEAT_SCHEDULE = {
    "update-products-daily": {
        "task": "system_meta.tasks.update_products",
        "schedule": crontab(hour=0, minute=0),  # Runs every day at midnight
    },
    "process-google-sheets-requests": {
        "task": "refunds.tasks.process_google_sheets_requests",
        "schedule": crontab(minute="0", hour="*/6"),
    },
}

CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"

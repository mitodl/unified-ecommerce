"""
As described in
http://celery.readthedocs.org/en/latest/django/first-steps-with-django.html
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "unified_ecommerce.settings")

from django.conf import settings  # noqa: E402

app = Celery("unified_ecommerce")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.task_default_queue = "default"
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)  # pragma: no cover

app.conf.task_routes = {
}

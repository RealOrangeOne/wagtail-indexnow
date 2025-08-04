from datetime import timedelta
from urllib.parse import urlparse

import requests
from django.utils import timezone
from wagtail import hooks
from wagtail.models import Page

from .utils import get_key

session = requests.Session()

SHOULD_NOTIFY_PAGE_ATTRIBUTE = "_should_indexnow"


@hooks.register("before_publish_page")
def check_notify_page(request, page):
    last_published_at = (
        Page.objects.filter(id=page.id)
        .only("last_published_at")
        .values_list("last_published_at", flat=True)[0]
    )

    should_notify = True
    if last_published_at:
        should_notify = (timezone.now() - timedelta(minutes=10)) >= last_published_at

    setattr(
        page,
        SHOULD_NOTIFY_PAGE_ATTRIBUTE,
        should_notify,
    )


@hooks.register("after_publish_page")
def notify_indexnow(request, page):
    if not getattr(page, SHOULD_NOTIFY_PAGE_ATTRIBUTE, False):
        return

    page_url = page.full_url

    session.post(
        "https://api.indexnow.org/indexnow",
        json={
            "host": urlparse(page_url).hostname,
            "urlList": [page_url],
            "key": "indexnow-" + get_key(),
        },
    ).raise_for_status()

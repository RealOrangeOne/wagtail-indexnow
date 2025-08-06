from datetime import timedelta

import requests_mock
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from wagtail.coreutils import get_dummy_request
from wagtail.models import Site

from wagtail_indexnow import wagtail_hooks
from wagtail_indexnow.utils import get_key

from .models import TestPage


class KeyTestCase(SimpleTestCase):
    def test_stable_key(self):
        self.assertEqual(get_key(), get_key())


class KeyViewTestCase(SimpleTestCase):
    def test_returns_key(self):
        response = self.client.get(f"/indexnow-{get_key()}.txt")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), get_key())

    def test_incorrect_key(self):
        response = self.client.get("/indexnow-notthekey.txt")
        self.assertEqual(response.status_code, 404)


@requests_mock.Mocker()
class IndexNowTestCase(TestCase):
    def setUp(self):
        self.root_page = Site.objects.first().root_page

        self.root_page.add_child(instance=TestPage(title="Test page"))

        self.page = self.root_page.get_children().get()

    def test_pings(self, m):
        m.register_uri("POST", "https://api.indexnow.org/indexnow")

        setattr(self.page, wagtail_hooks.SHOULD_NOTIFY_PAGE_ATTRIBUTE, True)

        wagtail_hooks.notify_indexnow(get_dummy_request(), self.page)

        self.assertEqual(m.call_count, 1)

        self.assertEqual(
            m.request_history[0].json(),
            {
                "host": "localhost",
                "urlList": [self.page.full_url],
                "key": "indexnow-" + get_key(),
            },
        )

    def test_noop_if_should_not_notify(self, m):
        setattr(self.page, wagtail_hooks.SHOULD_NOTIFY_PAGE_ATTRIBUTE, False)

        wagtail_hooks.notify_indexnow(get_dummy_request(), self.page)

        self.assertEqual(m.call_count, 0)


class CheckNotifyPageHookTestCase(TestCase):
    def setUp(self):
        self.root_page = Site.objects.first().root_page
        self.request = get_dummy_request()

    def test_should_notify_on_first_publish(self):
        new_page = TestPage(title="First Publish Page", live=True)
        self.root_page.add_child(instance=new_page)

        wagtail_hooks.check_notify_page(self.request, new_page)

        self.assertTrue(getattr(new_page, wagtail_hooks.SHOULD_NOTIFY_PAGE_ATTRIBUTE))

    def test_should_not_notify_on_recent_republish(self):
        recent_page = TestPage(
            title="Recent Page",
            live=True,
            last_published_at=timezone.now() - timedelta(minutes=1),
        )
        self.root_page.add_child(instance=recent_page)

        wagtail_hooks.check_notify_page(self.request, recent_page)

        self.assertFalse(
            getattr(recent_page, wagtail_hooks.SHOULD_NOTIFY_PAGE_ATTRIBUTE)
        )

    def test_should_notify_on_old_republish(self):
        old_page = TestPage(
            title="Old Page",
            live=True,
            last_published_at=timezone.now() - timedelta(minutes=20),
        )
        self.root_page.add_child(instance=old_page)

        wagtail_hooks.check_notify_page(self.request, old_page)

        self.assertTrue(getattr(old_page, wagtail_hooks.SHOULD_NOTIFY_PAGE_ATTRIBUTE))

    def test_ignores_other_pages_publication_date(self):
        old_unrelated_page = TestPage(
            title="An old, unrelated page",
            live=True,
            last_published_at=timezone.now() - timedelta(days=30),
        )
        self.root_page.add_child(instance=old_unrelated_page)

        page_to_publish = TestPage(
            title="Page Being Republished",
            live=True,
            last_published_at=timezone.now() - timedelta(minutes=1),
        )
        self.root_page.add_child(instance=page_to_publish)

        wagtail_hooks.check_notify_page(self.request, page_to_publish)

        self.assertFalse(
            getattr(page_to_publish, wagtail_hooks.SHOULD_NOTIFY_PAGE_ATTRIBUTE)
        )

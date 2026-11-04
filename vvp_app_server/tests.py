from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from .middleware import EdgeCacheControlMiddleware


class EdgeCacheControlMiddlewareTests(SimpleTestCase):
    def _process(self, response: HttpResponse) -> HttpResponse:
        request = RequestFactory().get("/proxy/favs/some/slug/")
        return EdgeCacheControlMiddleware(lambda _: response)(request)

    def test_public_get_is_edge_cached(self):
        response = self._process(HttpResponse("ok"))
        self.assertEqual(response["Cache-Control"], "public, max-age=300")

    def test_redirect_is_not_cached(self):
        response = self._process(HttpResponseRedirect("/elsewhere/"))
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_not_modified_is_not_marked_no_store(self):
        response = self._process(HttpResponse(status=304))
        self.assertFalse(response.has_header("Cache-Control"))

    def test_manual_cache_control_is_kept(self):
        original = HttpResponseRedirect("/elsewhere/")
        original["Cache-Control"] = "max-age=60"
        response = self._process(original)
        self.assertEqual(response["Cache-Control"], "max-age=60")

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_https_redirect_is_not_cached(self):
        # SecurityMiddleware short-circuits with this 301 before any inner
        # middleware runs, so this only passes while EdgeCacheControl is
        # ordered above it.
        response = self.client.get("/proxy/regions")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].startswith("https://"))
        self.assertEqual(response["Cache-Control"], "no-store")


class AdminLoginLockoutTests(TestCase):
    ATTACKER_IP = "203.0.113.7"
    OTHER_IP = "198.51.100.23"
    PASSWORD = "correct-horse-battery"  # nosec

    def setUp(self):
        User.objects.create_user(
            username="staff", password=self.PASSWORD, is_staff=True
        )

    def _login(self, password: str, ip: str, **extra: str):
        return self.client.post(
            "/admin/login/",
            {"username": "staff", "password": password},
            REMOTE_ADDR=ip,
            **extra,
        )

    def _fail(self, times: int, ip: str, **extra: str):
        for _ in range(times):
            self._login("wrong", ip, **extra)

    def test_ip_is_locked_after_five_failures(self):
        self._fail(4, self.ATTACKER_IP)
        # The fifth wrong password already gets the lockout response
        self.assertEqual(self._login("wrong", self.ATTACKER_IP).status_code, 429)
        # Locked out even with the right password
        response = self._login(self.PASSWORD, self.ATTACKER_IP)
        self.assertEqual(response.status_code, 429)

    def test_lockout_is_per_ip_not_per_user(self):
        self._fail(5, self.ATTACKER_IP)
        # The real staff member on another IP can still log in
        response = self._login(self.PASSWORD, self.OTHER_IP)
        self.assertEqual(response.status_code, 302)

    def test_success_resets_the_counter(self):
        self._fail(4, self.ATTACKER_IP)
        self.assertEqual(self._login(self.PASSWORD, self.ATTACKER_IP).status_code, 302)
        self.client.logout()
        self._fail(4, self.ATTACKER_IP)
        response = self._login(self.PASSWORD, self.ATTACKER_IP)
        self.assertEqual(response.status_code, 302)

    def test_spoofed_forwarded_for_does_not_evade_lockout(self):
        # Rotating X-Forwarded-For must not count as different clients:
        # axes keys on REMOTE_ADDR (see AXES_LOCKOUT_PARAMETERS).
        for i in range(5):
            self._fail(1, self.ATTACKER_IP, HTTP_X_FORWARDED_FOR=f"192.0.2.{i}")
        response = self._login(
            self.PASSWORD, self.ATTACKER_IP, HTTP_X_FORWARDED_FOR="192.0.2.99"
        )
        self.assertEqual(response.status_code, 429)

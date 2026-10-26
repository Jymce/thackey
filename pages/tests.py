import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.mark.django_db
class TestPages:
    def test_home_anonymous(self):
        res = Client().get("/")
        assert res.status_code == 200
        assert b"typing-area" in res.content

    def test_dashboard_requires_login(self):
        res = Client().get("/dashboard/")
        assert res.status_code == 302
        assert "/login/" in res.url

    def test_analytics_requires_login(self):
        res = Client().get("/analytics/")
        assert res.status_code == 302

    def test_register_flow(self):
        c = Client()
        res = c.post(
            "/register/",
            {
                "username": "newbie",
                "email": "",
                "password1": "S3cret!pass",
                "password2": "S3cret!pass",
            },
        )
        assert res.status_code == 302  # redirected to home, logged in
        assert User.objects.filter(username="newbie").exists()
        assert c.get("/dashboard/").status_code == 200

    def test_login_page(self):
        User.objects.create_user("typer", password="secret1234")
        c = Client()
        res = c.post("/login/", {"username": "typer", "password": "secret1234"})
        assert res.status_code == 302
        assert c.get("/dashboard/").status_code == 200

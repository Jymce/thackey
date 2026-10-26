import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestAuth:
    def test_register_returns_tokens_and_settings(self, client):
        res = client.post(
            "/api/v1/auth/register/",
            {"username": "typer", "email": "t@t.com", "password": "secret1234"},
            format="json",
        )
        assert res.status_code == 201
        assert res.data["tokens"]["access"]
        assert res.data["user"]["settings"]["keyboard_layout"] == "qwerty"

    def test_login_and_me(self, client):
        User.objects.create_user("typer", password="secret1234")
        res = client.post(
            "/api/v1/auth/login/",
            {"username": "typer", "password": "secret1234"},
            format="json",
        )
        assert res.status_code == 200
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        me = client.get("/api/v1/auth/me/")
        assert me.status_code == 200
        assert me.data["username"] == "typer"

    def test_me_requires_auth(self, client):
        # SessionAuthentication yields no WWW-Authenticate challenge -> 403
        assert client.get("/api/v1/auth/me/").status_code in (401, 403)

    def test_update_settings(self, client):
        user = User.objects.create_user("typer", password="secret1234")
        client.force_authenticate(user)
        res = client.patch(
            "/api/v1/auth/me/",
            {"settings": {"theme": "dark", "keyboard_layout": "colemak"}},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["settings"]["theme"] == "dark"
        assert res.data["settings"]["keyboard_layout"] == "colemak"

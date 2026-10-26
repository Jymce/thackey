import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _plain_staticfiles(settings):
    """Manifest storage needs collectstatic; tests use the plain backend."""
    settings.STORAGES["staticfiles"]["BACKEND"] = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


@pytest.fixture
def user(db):
    return User.objects.create_user("typer", password="secret1234")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c

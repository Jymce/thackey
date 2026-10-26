from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({"status": "ok"})


def index(_request):
    return JsonResponse(
        {
            "name": "ThacKey API",
            "docs": "see README.md for endpoint details",
            "endpoints": {
                "health": "/api/v1/health/",
                "auth": "/api/v1/auth/",
                "sessions": "/api/v1/sessions/",
                "analytics": "/api/v1/analytics/",
                "adaptive": "/api/v1/adaptive/",
                "texts": "/api/v1/texts/random/",
                "admin": "/admin/",
            },
        }
    )


urlpatterns = [
    path("", include("pages.urls")),
    path("admin/", admin.site.urls),
    path("api/", index),
    path("api/v1/health/", health),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/sessions/", include("practice.urls")),
    path("api/v1/analytics/", include("analytics.urls")),
    path("api/v1/adaptive/", include("adaptive.urls")),
    path("api/v1/texts/", include("texts.urls")),
]

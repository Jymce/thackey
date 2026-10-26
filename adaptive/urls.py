from django.urls import path

from adaptive.views import AdaptiveTestDetailView, GenerateView

urlpatterns = [
    path("generate/", GenerateView.as_view(), name="adaptive-generate"),
    path("<int:pk>/", AdaptiveTestDetailView.as_view(), name="adaptive-detail"),
]

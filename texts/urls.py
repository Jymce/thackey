from django.urls import path

from texts.views import RandomTextView

urlpatterns = [
    path("random/", RandomTextView.as_view(), name="text-random"),
]

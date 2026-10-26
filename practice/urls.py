from django.urls import path

from practice.views import SessionDetailView, SessionListCreateView

urlpatterns = [
    path("", SessionListCreateView.as_view(), name="session-list"),
    path("<int:pk>/", SessionDetailView.as_view(), name="session-detail"),
]

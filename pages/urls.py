from django.contrib.auth import views as auth_views
from django.urls import path

from pages import views
from pages.forms import StyledAuthenticationForm

urlpatterns = [
    path("", views.index, name="home"),
    path("results/<int:pk>/", views.results, name="results"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("analytics/", views.analytics, name="analytics"),
    path("register/", views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(authentication_form=StyledAuthenticationForm),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]

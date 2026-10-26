from django.urls import path

from analytics.views import ProfileView, ReportView, TrendsView

urlpatterns = [
    path("profile/", ProfileView.as_view(), name="analytics-profile"),
    path("trends/", TrendsView.as_view(), name="analytics-trends"),
    path("report/", ReportView.as_view(), name="analytics-report"),
]

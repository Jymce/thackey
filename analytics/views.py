from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.models import WeaknessProfile
from analytics.services import get_progress_report


class ProfileView(APIView):
    """GET /analytics/profile/ — the user's current weakness profile."""

    def get(self, request):
        try:
            p = request.user.weakness_profile
        except WeaknessProfile.DoesNotExist:
            return Response({"profile": None})
        return Response(
            {
                "profile": {
                    "char_scores": p.char_scores,
                    "bigram_scores": p.bigram_scores,
                    "categories": p.categories,
                    "top_weaknesses": p.top_weaknesses,
                    "sessions_analyzed": p.sessions_analyzed,
                    "updated_at": p.updated_at,
                }
            }
        )


class TrendsView(APIView):
    """GET /analytics/trends/ — time series for dashboard charts."""

    def get(self, request):
        try:
            limit = min(int(request.query_params.get("limit", 50)), 200)
        except ValueError:
            limit = 50
        sessions = (
            request.user.typing_sessions.order_by("-created_at")
            .values("id", "created_at", "mode", "source", "wpm", "raw_wpm", "accuracy", "error_count")[:limit]
        )
        return Response({"sessions": list(reversed(list(sessions)))})


class ReportView(APIView):
    """GET /analytics/report/ — profile + natural-language AI analysis."""

    def get(self, request):
        force = request.query_params.get("refresh") == "true"
        return Response(get_progress_report(request.user, force_refresh=force))

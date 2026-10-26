from django.db.models import Count
from rest_framework import generics, status
from rest_framework.response import Response

from practice.models import TypingSession
from practice.serializers import (
    TypingSessionCreateSerializer,
    TypingSessionDetailSerializer,
    TypingSessionSerializer,
)


class SessionListCreateView(generics.ListCreateAPIView):
    throttle_scope = "session_create"

    def get_queryset(self):
        return (
            TypingSession.objects.filter(user=self.request.user)
            .annotate(keystroke_count=Count("keystrokes"))
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TypingSessionCreateSerializer
        return TypingSessionSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = serializer.save(user=self.request.user)

        # Feed the analytics pipeline — updates the user's weakness profile.
        # Best-effort: analytics failures must never lose a session.
        analysis = {}
        try:
            from analytics.services import (
                session_hotspots,
                suggest_practice,
                update_weakness_profile,
            )

            analysis["hotspots"] = session_hotspots(session)
            profile = update_weakness_profile(self.request.user, session)
            if profile:
                analysis["top_weaknesses"] = profile.top_weaknesses[:6]
                analysis["suggestion"] = suggest_practice(profile)
        except Exception:
            pass

        data = TypingSessionSerializer(session).data
        data["analysis"] = analysis
        return Response(data, status=status.HTTP_201_CREATED)


class SessionDetailView(generics.RetrieveAPIView):
    serializer_class = TypingSessionDetailSerializer

    def get_queryset(self):
        return TypingSession.objects.filter(user=self.request.user).prefetch_related(
            "keystrokes"
        )

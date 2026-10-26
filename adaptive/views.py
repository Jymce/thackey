from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from adaptive.generators import generate_heuristic
from adaptive.llm import generate_adaptive_text, is_configured
from adaptive.models import AdaptiveTest
from adaptive.serializers import AdaptiveTestSerializer
from analytics.models import WeaknessProfile


class GenerateView(APIView):
    """POST /adaptive/generate/ — build a test around weaknesses.

    Body (all optional):
      word_count  int    — drill length, 20-200, default 50
      targets     [str]  — explicit patterns to drill, e.g. ["q", "th", "␣q"].
                           Omit to auto-use the profile's weakest patterns.

    Tries the LLM first when an API key is configured, then always falls back
    to the local heuristic so the endpoint never fails for lack of AI.
    """

    throttle_scope = "adaptive_generate"

    def post(self, request):
        try:
            profile = request.user.weakness_profile
        except WeaknessProfile.DoesNotExist:
            return Response(
                {"detail": "Take at least one test first so we can learn your weaknesses."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        word_count = 50
        try:
            word_count = max(20, min(int(request.data.get("word_count", 50)), 200))
        except (TypeError, ValueError):
            pass

        # Explicit targets = user-tuned suggestion; else fall back to profile
        raw_targets = request.data.get("targets")
        targets = None
        if isinstance(raw_targets, list) and raw_targets:
            targets = [str(t) for t in raw_targets[:12]]

        weakness_keys = targets or [w["key"] for w in profile.top_weaknesses]

        if is_configured():
            result = generate_adaptive_text(weakness_keys, word_count=word_count)
            if result:
                test = AdaptiveTest.objects.create(
                    user=request.user,
                    content=result["text"],
                    generated_by="llm",
                    target_patterns=weakness_keys[:8],
                    explanation=result.get("explanation", ""),
                )
                return Response(
                    AdaptiveTestSerializer(test).data, status=status.HTTP_201_CREATED
                )

        content, target_patterns, explanation = generate_heuristic(
            profile, word_count, targets=targets
        )
        test = AdaptiveTest.objects.create(
            user=request.user,
            content=content,
            generated_by="heuristic",
            target_patterns=target_patterns,
            explanation=explanation,
        )
        return Response(
            AdaptiveTestSerializer(test).data, status=status.HTTP_201_CREATED
        )


class AdaptiveTestDetailView(generics.RetrieveAPIView):
    serializer_class = AdaptiveTestSerializer

    def get_queryset(self):
        return AdaptiveTest.objects.filter(user=self.request.user)

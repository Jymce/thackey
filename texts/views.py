import random

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from texts.models import TextCorpus
from texts.serializers import TextCorpusSerializer
from texts.wordlists import WORD_LIST


class RandomTextView(APIView):
    """GET /texts/random/?category=words&count=40  or  ?category=quote

    Anonymous access — first-time visitors can take a test without signing up.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        category = request.query_params.get("category", "words")

        if category == "words":
            try:
                count = max(10, min(int(request.query_params.get("count", 40)), 200))
            except ValueError:
                count = 40
            return Response(
                {
                    "content": " ".join(random.sample(WORD_LIST, count)),
                    "category": "words",
                }
            )

        texts = TextCorpus.objects.filter(category=category)
        if not texts.exists():
            texts = TextCorpus.objects.all()
        if not texts.exists():
            return Response(
                {"content": " ".join(random.sample(WORD_LIST, 40)), "category": "words"}
            )
        return Response(TextCorpusSerializer(texts.order_by("?").first()).data)

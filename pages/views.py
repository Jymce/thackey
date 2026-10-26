from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Max
from django.shortcuts import get_object_or_404, redirect, render

from analytics.models import WeaknessProfile
from analytics.services import get_progress_report
from pages.forms import RegisterForm
from practice.models import TypingSession


def index(request):
    """The typing test itself — the landing page."""
    has_profile = (
        request.user.is_authenticated
        and WeaknessProfile.objects.filter(user=request.user).exists()
    )
    return render(request, "pages/index.html", {"has_profile": has_profile})


@login_required
def results(request, pk):
    session = get_object_or_404(TypingSession, pk=pk, user=request.user)
    profile = getattr(request.user, "weakness_profile", None)
    top = profile.top_weaknesses[:5] if profile else []
    return render(
        request,
        "pages/results.html",
        {"session": session, "top_weaknesses": top},
    )


@login_required
def dashboard(request):
    qs = request.user.typing_sessions.order_by("-created_at")
    agg = qs.aggregate(
        best_wpm=Max("wpm"), avg_wpm=Avg("wpm"), avg_acc=Avg("accuracy"), total=Count("id")
    )
    sessions = list(qs[:30])

    # Sparkline points for WPM trend (oldest -> newest)
    trend = [s.wpm for s in reversed(sessions)]
    sparkline = ""
    if len(trend) > 1:
        lo, hi = min(trend), max(trend)
        span = (hi - lo) or 1
        w, h = 300, 60
        pts = [
            f"{i * w / (len(trend) - 1):.1f},{h - (v - lo) / span * h:.1f}"
            for i, v in enumerate(trend)
        ]
        sparkline = " ".join(pts)

    return render(
        request,
        "pages/dashboard.html",
        {
            "sessions": sessions,
            "best_wpm": agg["best_wpm"] or 0,
            "avg_wpm": agg["avg_wpm"] or 0,
            "avg_acc": agg["avg_acc"] or 0,
            "total": agg["total"],
            "sparkline": sparkline,
        },
    )


# QWERTY rows for the on-screen heatmap keyboard
KEY_ROWS = [
    list("qwertyuiop"),
    list("asdfghjkl"),
    list("zxcvbnm"),
]


@login_required
def analytics(request):
    data = get_progress_report(request.user)
    profile = data["profile"] or {}

    # Heatmap: red = weak, green = strong — intensity normalized per side
    heatmap_rows = []
    scores = profile.get("char_scores", {})
    max_weak = max((v.get("score", 0) for v in scores.values()), default=0) or 1
    for row in KEY_ROWS:
        heatmap_rows.append(
            [
                {
                    "key": ch,
                    "intensity": round(scores.get(ch, {}).get("score", 0) / max_weak, 3),
                    "strength": round(
                        max(0.0, 0.15 - scores.get(ch, {}).get("score", 1)) / 0.15, 3
                    ) if ch in scores and scores[ch].get("n", 0) >= 5 else 0,
                    "score": scores.get(ch, {}).get("score", 0),
                    "err": scores.get(ch, {}).get("err", 0),
                }
                for ch in row
            ]
        )

    return render(
        request,
        "pages/analytics.html",
        {
            "profile": profile or None,
            "report": data["report"],
            "suggestion": data.get("suggestion"),
            "heatmap_rows": heatmap_rows,
            "categories": profile.get("categories", {}),
            "top_weaknesses": profile.get("top_weaknesses", []),
            "strengths": profile.get("strengths", []),
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "pages/register.html", {"form": form})

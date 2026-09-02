from flask import Blueprint, render_template, redirect, url_for, Response, session, request
from flask_login import current_user, login_required

from app.models import Campaign, CampaignParticipant

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("campaigns.dashboard"))
    return render_template("public/landing.html")


@main_bp.route("/set-language/<lang_code>")
def set_language(lang_code):
    if lang_code in ("en", "sw"):
        session["lang"] = lang_code
    next_url = request.referrer or url_for("main.index")
    return redirect(next_url)


@main_bp.route("/set-theme/<theme_name>")
def set_theme(theme_name):
    allowed = ("purple", "white", "black", "ocean", "green")
    if theme_name in allowed:
        session["theme"] = theme_name
    next_url = request.referrer or url_for("main.index")
    return redirect(next_url)


@main_bp.route("/notifications")
@login_required
def notifications():
    created = current_user.owned_campaigns.order_by(Campaign.created_at.desc()).all()

    my_participants = (
        CampaignParticipant.query.filter_by(user_id=current_user.id)
        .order_by(CampaignParticipant.created_at.desc())
        .all()
    )

    participating, incomplete, completed, expired = [], [], [], []

    for p in my_participants:
        c = p.campaign
        participating.append(c)  # participating = every campaign I've contributed to

        if c.is_expired:
            expired.append(c)

        if p.remaining is not None:
            if p.remaining > 0:
                incomplete.append(c)
            else:
                completed.append(c)

    return render_template(
        "main/notifications.html",
        created=created,
        participating=participating,
        incomplete=incomplete,
        completed=completed,
        expired=expired,
    )


@main_bp.route("/profile")
@login_required
def profile():
    return render_template("main/profile.html")


@main_bp.route("/favicon.ico")
def favicon():
    return Response(status=204)
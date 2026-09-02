from flask import Blueprint, render_template, redirect, url_for, Response, session, request
from flask_login import current_user, login_required

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


@main_bp.route("/notifications")
@login_required
def notifications():
    return render_template("main/notifications.html")


@main_bp.route("/profile")
@login_required
def profile():
    return render_template("main/profile.html")


@main_bp.route("/favicon.ico")
def favicon():
    return Response(status=204)
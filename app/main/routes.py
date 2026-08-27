from flask import Blueprint, render_template, redirect, url_for, Response
from flask_login import current_user

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("campaigns.dashboard"))
    return render_template("public/landing.html")


@main_bp.route("/favicon.ico")
def favicon():
    return Response(status=204)
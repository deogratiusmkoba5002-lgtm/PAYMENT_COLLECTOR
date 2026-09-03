from decimal import Decimal, InvalidOperation
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user

from app.notifications.service import notify_contribution_success
from app.extensions import db
from app.models import Campaign, Contribution, CampaignParticipant
from app.payments.providers import get_active_provider

payments_bp = Blueprint("payments", __name__)


def get_or_create_participant(campaign, user):
    participant = CampaignParticipant.query.filter_by(
        campaign_id=campaign.id, user_id=user.id
    ).first()
    if participant is None:
        participant = CampaignParticipant(
            campaign_id=campaign.id,
            user_id=user.id,
            display_name=user.username,
            is_anonymous=False,
        )
        db.session.add(participant)
        db.session.commit()
    return participant


@payments_bp.route("/pay/<slug>")
def campaign_page(slug):
    campaign = Campaign.query.filter_by(slug=slug).first_or_404()
    participant = None
    if current_user.is_authenticated:
        participant = CampaignParticipant.query.filter_by(
            campaign_id=campaign.id, user_id=current_user.id
        ).first()
    is_owner = current_user.is_authenticated and campaign.owner_id == current_user.id
    return render_template(
        "public/campaign_page.html", campaign=campaign, participant=participant, is_owner=is_owner
    )


@payments_bp.route("/pay/<slug>/contribute", methods=["GET", "POST"])
@login_required
def contribute(slug):
    campaign = Campaign.query.filter_by(slug=slug).first_or_404()

    if not campaign.is_active:
        flash("This campaign is no longer accepting contributions.", "error")
        return redirect(url_for("payments.campaign_page", slug=slug))

    participant = get_or_create_participant(campaign, current_user)

    if request.method == "POST":
        display_name = (request.form.get("display_name") or "").strip()
        is_anonymous = request.form.get("is_anonymous") == "on"
        amount_raw = (request.form.get("amount") or "").strip()

        if not is_anonymous:
            if not display_name or len(display_name) > 80:
                flash("Please enter a valid display name.", "error")
                return redirect(url_for("payments.contribute", slug=slug))
            participant.display_name = display_name
        participant.is_anonymous = is_anonymous

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError):
            flash("Please enter a valid amount.", "error")
            return redirect(url_for("payments.contribute", slug=slug))

        if amount <= 0 or amount > Decimal("100000000"):
            flash("Please enter a valid contribution amount.", "error")
            return redirect(url_for("payments.contribute", slug=slug))

        contribution = Contribution(participant_id=participant.id, amount=amount, status="pending")
        db.session.add(contribution)
        db.session.commit()

        get_active_provider().initiate_payment(contribution)

        return redirect(url_for("payments.confirm_page", public_id=contribution.public_id))

    return render_template("public/contribute_form.html", campaign=campaign, participant=participant)


@payments_bp.route("/pay/confirm/<public_id>")
@login_required
def confirm_page(public_id):
    contribution = Contribution.query.filter_by(public_id=public_id).first_or_404()
    if contribution.participant.user_id != current_user.id:
        abort(403)
    return render_template(
        "public/confirm.html",
        contribution=contribution,
        participant=contribution.participant,
        campaign=contribution.participant.campaign,
    )


@payments_bp.route("/pay/confirm/<public_id>/simulate", methods=["POST"])
@login_required
def simulate_confirm(public_id):
    contribution = Contribution.query.filter_by(public_id=public_id).first_or_404()
    if contribution.participant.user_id != current_user.id:
        abort(403)

    if contribution.status != "pending":
        return jsonify({"status": contribution.status}), 200

    campaign = contribution.participant.campaign
    if not campaign.is_active:
        contribution.status = "cancelled"
        db.session.commit()
        return jsonify({"status": contribution.status}), 200

    result = get_active_provider().verify_payment(contribution, request.form.to_dict())
    contribution.status = result
    db.session.commit()

    if contribution.status == "successful":
        notify_contribution_success(contribution)

    participant = contribution.participant
    return jsonify({
        "status": contribution.status,
        "total_paid": float(participant.total_paid),
        "remaining": float(participant.remaining) if participant.remaining is not None else None,
    }), 200
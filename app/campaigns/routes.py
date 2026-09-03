import re
import secrets
from flask import Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, DateTimeLocalField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Optional, NumberRange, Length, Regexp

from app.extensions import db
from app.models import Campaign, CampaignParticipant, CampaignWhatsAppConfig
from app.payments.routes import get_or_create_participant

campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/dashboard")


class CampaignForm(FlaskForm):
    title = StringField("Campaign Title", validators=[DataRequired(), Length(min=3, max=255)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    per_contributor_target = DecimalField(
        "Minimum contribution per person", validators=[Optional(), NumberRange(min=0.01)], places=2
    )
    deadline = DateTimeLocalField("Deadline", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    submit = SubmitField("Create Campaign")

class WhatsAppSettingsForm(FlaskForm):
    is_enabled = BooleanField("Enable WhatsApp notifications")
    destination_phone = StringField(
        "WhatsApp number",
        validators=[Optional(), Length(max=20), Regexp(r"^\+?[0-9]{9,15}$", message="Enter a valid number, e.g. +255712345678")]
    )
    submit = SubmitField("Save")


def slugify(title):
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    base = base[:60] or "campaign"
    slug = base
    while Campaign.query.filter_by(slug=slug).first():
        slug = f"{base}-{secrets.token_hex(3)}"
    return slug


def get_accessible_campaign_or_404(campaign_id):
    """Allows the campaign owner OR anyone who has contributed to it."""
    campaign = Campaign.query.get_or_404(campaign_id)
    is_owner = campaign.owner_id == current_user.id
    is_participant = CampaignParticipant.query.filter_by(
        campaign_id=campaign.id, user_id=current_user.id
    ).first() is not None
    if not is_owner and not is_participant:
        abort(403)
    return campaign


def get_owned_campaign_or_404(campaign_id):
    """Owner-only — used for closing/reopening a campaign."""
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.owner_id != current_user.id:
        abort(403)
    return campaign


@campaigns_bp.route("/")
@login_required
def dashboard():
    owned = current_user.owned_campaigns.order_by(Campaign.created_at.desc()).all()

    contributed_campaign_ids = (
        db.session.query(CampaignParticipant.campaign_id)
        .filter(CampaignParticipant.user_id == current_user.id)
        .subquery()
    )
    contributed = (
        Campaign.query.filter(Campaign.id.in_(contributed_campaign_ids))
        .order_by(Campaign.created_at.desc())
        .all()
    )

    # a campaign the user owns AND has contributed to should only show in "owned"
    owned_ids = {c.id for c in owned}
    contributed = [c for c in contributed if c.id not in owned_ids]

    my_participants = {
        p.campaign_id: p
        for p in CampaignParticipant.query.filter_by(user_id=current_user.id).all()
    }

    return render_template(
        "dashboard/index.html", owned=owned, contributed=contributed, my_participants=my_participants
    )


@campaigns_bp.route("/campaigns/new", methods=["GET", "POST"])
@login_required
def create_campaign():
    form = CampaignForm()
    if form.validate_on_submit():
        campaign = Campaign(
            owner_id=current_user.id,
            title=form.title.data.strip(),
            description=(form.description.data or "").strip() or None,
            per_contributor_target=form.per_contributor_target.data,
            deadline=form.deadline.data,
            slug=slugify(form.title.data),
        )
        db.session.add(campaign)
        db.session.commit()
        flash("Campaign created successfully. Share the link with anyone you want to include.", "success")
        return redirect(url_for("campaigns.view_campaign", campaign_id=campaign.id))

    return render_template("dashboard/create_campaign.html", form=form)


@campaigns_bp.route("/campaigns/<int:campaign_id>")
@login_required
def view_campaign(campaign_id):
    campaign = get_accessible_campaign_or_404(campaign_id)
    is_owner = campaign.owner_id == current_user.id
    participants = campaign.participants.order_by(CampaignParticipant.created_at.desc()).all()
    return render_template(
        "dashboard/campaign_detail.html", campaign=campaign, participants=participants, is_owner=is_owner
    )


@campaigns_bp.route("/campaigns/<int:campaign_id>/close", methods=["POST"])
@login_required
def close_campaign(campaign_id):
    campaign = get_owned_campaign_or_404(campaign_id)
    campaign.is_closed = True
    db.session.commit()
    flash("Campaign closed. It no longer accepts contributions.", "info")
    return redirect(url_for("campaigns.view_campaign", campaign_id=campaign.id))


@campaigns_bp.route("/campaigns/<int:campaign_id>/reopen", methods=["POST"])
@login_required
def reopen_campaign(campaign_id):
    campaign = get_owned_campaign_or_404(campaign_id)
    if campaign.is_expired:
        flash("Cannot reopen an expired campaign.", "error")
    else:
        campaign.is_closed = False
        db.session.commit()
        flash("Campaign reopened.", "success")
    return redirect(url_for("campaigns.view_campaign", campaign_id=campaign.id))

@campaigns_bp.route("/campaigns/<int:campaign_id>/whatsapp", methods=["GET", "POST"])
@login_required
def whatsapp_settings(campaign_id):
    campaign = get_owned_campaign_or_404(campaign_id)
    config = CampaignWhatsAppConfig.query.filter_by(campaign_id=campaign.id).first()
    if config is None:
        config = CampaignWhatsAppConfig(campaign_id=campaign.id, destination_phone=current_user.phone_number)
        db.session.add(config)
        db.session.commit()

    form = WhatsAppSettingsForm(obj=config)
    if form.validate_on_submit():
        phone = (form.destination_phone.data or "").strip()
        if form.is_enabled.data and not phone:
            flash("Enter a WhatsApp number before enabling notifications.", "error")
            return redirect(url_for("campaigns.whatsapp_settings", campaign_id=campaign.id))

        config.destination_phone = phone or None
        config.is_enabled = form.is_enabled.data
        config.status = "disabled" if not config.is_enabled else (
            "not_connected" if config.status == "disabled" else config.status
        )
        db.session.commit()
        flash("WhatsApp settings saved.", "success")
        return redirect(url_for("campaigns.view_campaign", campaign_id=campaign.id))

    return render_template("dashboard/whatsapp_settings.html", campaign=campaign, config=config, form=form)
from collections import defaultdict
from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from app.models import Campaign, CampaignParticipant, Contribution

analytics_bp = Blueprint("analytics", __name__)


def _get_accessible_campaign_or_404(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    is_owner = campaign.owner_id == current_user.id
    is_participant = CampaignParticipant.query.filter_by(
        campaign_id=campaign.id, user_id=current_user.id
    ).first() is not None
    if not is_owner and not is_participant:
        abort(403)
    return campaign


@analytics_bp.route("/dashboard/campaigns/<int:campaign_id>/analytics")
@login_required
def campaign_analytics(campaign_id):
    campaign = _get_accessible_campaign_or_404(campaign_id)
    is_owner = campaign.owner_id == current_user.id

    participants = campaign.participants.all()

    status_counts = defaultdict(int)
    status_amounts = defaultdict(float)
    daily_totals = defaultdict(float)

    all_contributions = (
        Contribution.query.join(CampaignParticipant)
        .filter(CampaignParticipant.campaign_id == campaign.id)
        .all()
    )

    for contrib in all_contributions:
        status_counts[contrib.status] += 1
        status_amounts[contrib.status] += float(contrib.amount)
        if contrib.status == "successful":
            day = contrib.created_at.strftime("%Y-%m-%d")
            daily_totals[day] += float(contrib.amount)

    timeline = sorted(daily_totals.items())[-14:]
    max_daily = max((v for _, v in timeline), default=0)

    completed = [p for p in participants if p.remaining == 0 and p.total_paid > 0]
    incomplete = [p for p in participants if p.remaining and p.remaining > 0]

    top_contributors = sorted(
        [p for p in participants if p.total_paid > 0],
        key=lambda p: p.total_paid,
        reverse=True,
    )[:10]

    total_attempts = sum(status_counts.values())
    success_rate = round((status_counts["successful"] / total_attempts) * 100, 1) if total_attempts else 0
    avg_contribution = (
        round(status_amounts["successful"] / status_counts["successful"], 2)
        if status_counts["successful"] else 0
    )

    return render_template(
        "analytics/campaign_analytics.html",
        campaign=campaign,
        is_owner=is_owner,
        status_counts=status_counts,
        timeline=timeline,
        max_daily=max_daily,
        completed=completed,
        incomplete=incomplete,
        top_contributors=top_contributors,
        success_rate=success_rate,
        avg_contribution=avg_contribution,
        total_attempts=total_attempts,
    )


@analytics_bp.route("/analytics/me")
@login_required
def user_analytics():
    owned = current_user.owned_campaigns.all()
    my_participations = CampaignParticipant.query.filter_by(user_id=current_user.id).all()

    total_collected_owned = sum(float(c.total_collected) for c in owned)

    my_contributions = (
        Contribution.query.join(CampaignParticipant)
        .filter(CampaignParticipant.user_id == current_user.id)
        .order_by(Contribution.created_at.desc())
        .all()
    )

    successful = [c for c in my_contributions if c.status == "successful"]
    total_contributed = sum(float(c.amount) for c in successful)
    total_attempts = len(my_contributions)
    success_rate = round((len(successful) / total_attempts) * 100, 1) if total_attempts else 0

    return render_template(
        "analytics/user_analytics.html",
        total_created=len(owned),
        total_collected_owned=total_collected_owned,
        total_participations=len(my_participations),
        total_contributed=total_contributed,
        success_rate=success_rate,
        total_attempts=total_attempts,
        recent=my_contributions[:8],
    )
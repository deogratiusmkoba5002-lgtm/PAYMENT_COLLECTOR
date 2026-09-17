"""
The ONLY place in the app that knows about WhatsApp/notifications.
Payment code just calls notify_contribution_success(contribution).

Guarantees:
- Never raises — a WhatsApp outage cannot affect a payment's status.
- Never sends twice for the same contribution (unique constraint on
  Notification.contribution_id + channel handles retries/refreshes).
"""
import logging
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Notification, CampaignWhatsAppConfig, utcnow
from app.notifications.providers import get_whatsapp_provider

logger = logging.getLogger("notifications")


def _format_message(contribution):
    participant = contribution.participant
    campaign = participant.campaign

    name = participant.public_display_name
    amount = f"{contribution.amount:,.0f}"
    total = f"{campaign.total_collected:,.0f}"

    lines = [f"💰 {campaign.title}"]
    line = f"{campaign.successful_contributor_count}. {name.upper()} PAID {amount}"
    if participant.remaining is not None:
        line += f" REMAINING {participant.remaining:,.0f}"
    lines.append(line)
    lines.append("")
    total_line = f"Total collected: {total}"
    if campaign.per_contributor_target:
        total_line += f" | Target/person: {campaign.per_contributor_target:,.0f}"
    lines.append(total_line)
    return "\n".join(lines)


def notify_contribution_success(contribution):
    try:
        _do_notify(contribution)
    except Exception:
        logger.exception("Unexpected error notifying for contribution %s", contribution.id)


def _do_notify(contribution):
    campaign = contribution.participant.campaign
    config = CampaignWhatsAppConfig.query.filter_by(campaign_id=campaign.id).first()

    if not config or not config.is_enabled:
        return  # WhatsApp not configured/enabled for this campaign

    provider = get_whatsapp_provider()
    destination = config.whatsapp_group_id if provider.destination_type == "group" else config.destination_phone
    if not destination:
        return  # enabled, but no destination set for the currently active provider

    notification = Notification(
        contribution_id=contribution.id,
        campaign_id=campaign.id,
        channel="whatsapp",
        destination=destination,
        status="pending",
    )
    db.session.add(notification)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return  # already notified for this contribution — do not send again

    message = _format_message(contribution)
    result = provider.send(destination, message)
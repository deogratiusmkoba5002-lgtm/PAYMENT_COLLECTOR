import uuid
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model, UserMixin):
    """A single account type. Any user can create campaigns (becoming their
    owner/admin) and contribute to any campaign, including their own."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    owned_campaigns = db.relationship(
        "Campaign", backref="owner", lazy="dynamic", cascade="all, delete-orphan"
    )
    participations = db.relationship(
        "CampaignParticipant", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Campaign(db.Model):
    __tablename__ = "campaigns"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    per_contributor_target = db.Column(db.Numeric(14, 2), nullable=True)
    deadline = db.Column(db.DateTime(timezone=True), nullable=True)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    is_closed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    participants = db.relationship(
        "CampaignParticipant", backref="campaign", lazy="dynamic", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.CheckConstraint(
            "per_contributor_target IS NULL OR per_contributor_target > 0", name="ck_target_positive"
        ),
    )

    @property
    def is_expired(self):
        if self.deadline is None:
            return False
        deadline = self.deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return utcnow() > deadline

    @property
    def is_active(self):
        return not self.is_closed and not self.is_expired

    @property
    def total_collected(self):
        total = (
            db.session.query(func.coalesce(func.sum(Contribution.amount), 0))
            .join(CampaignParticipant, Contribution.participant_id == CampaignParticipant.id)
            .filter(CampaignParticipant.campaign_id == self.id, Contribution.status == "successful")
            .scalar()
        )
        return total or 0

    @property
    def successful_contributor_count(self):
        return (
            db.session.query(CampaignParticipant.id)
            .join(Contribution, Contribution.participant_id == CampaignParticipant.id)
            .filter(CampaignParticipant.campaign_id == self.id, Contribution.status == "successful")
            .distinct()
            .count()
        )


class CampaignParticipant(db.Model):
    """One row per (campaign, user) pair — tracks that user's display name,
    anonymity choice, and running total toward the campaign's per-contributor
    target. A user can be the owner of a campaign AND a participant in it."""
    __tablename__ = "campaign_participants"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(
        db.Integer, db.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_name = db.Column(db.String(80), nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    contributions = db.relationship(
        "Contribution", backref="participant", lazy="dynamic", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint("campaign_id", "user_id", name="uq_campaign_user"),
    )

    @property
    def public_display_name(self):
        return "Anonymous" if self.is_anonymous else self.display_name

    @property
    def total_paid(self):
        total = (
            db.session.query(func.coalesce(func.sum(Contribution.amount), 0))
            .filter(Contribution.participant_id == self.id, Contribution.status == "successful")
            .scalar()
        )
        return total or 0

    @property
    def remaining(self):
        target = self.campaign.per_contributor_target
        if target is None:
            return None
        remaining = target - self.total_paid
        return remaining if remaining > 0 else 0

    @property
    def progress_percent(self):
        target = self.campaign.per_contributor_target
        if not target or target == 0:
            return None
        pct = (float(self.total_paid) / float(target)) * 100
        return min(round(pct, 1), 100)


class Contribution(db.Model):
    __tablename__ = "contributions"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True
    )
    participant_id = db.Column(
        db.Integer, db.ForeignKey("campaign_participants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    reference_id = db.Column(
        db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex[:16].upper()
    )
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_amount_positive"),
        db.CheckConstraint(
            "status IN ('pending','successful','failed','cancelled')", name="ck_status_valid"
        ),
    )
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FamilyMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    color = db.Column(db.String(7), default="#3498db")  # Hex color
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class EventSeries(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date_time = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer, default=60)  # Duration in minutes
    description = db.Column(db.Text)
    family_member_id = db.Column(
        db.Integer, db.ForeignKey("family_member.id"), nullable=False
    )
    event_series_id = db.Column(
        db.Integer, db.ForeignKey("event_series.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    family_member = db.relationship("FamilyMember", backref="events")
    event_series = db.relationship("EventSeries", backref="events")

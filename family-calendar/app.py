from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, FamilyMember, Event, EventSeries
from groq import Groq
import json
from datetime import datetime, timedelta
from dateutil import parser
import os
import re
import dotenv
import logging

dotenv.load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key-change-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///calendar.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Initialize Groq client
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def parse_events_with_groq(description, family_members):
    """Use Groq to parse natural language event descriptions"""
    members_list = [{"name": m.name, "id": m.id} for m in family_members]

    system_prompt = f"""You are a calendar event parser. Parse the given text into structured calendar events.

Available family members: {json.dumps(members_list)}
Today's date: {datetime.now().strftime("%Y-%m-%d")}

Return ONLY a valid JSON object with this exact structure:
{{
    "events": [
        {{
            "title": "Event title",
            "date": "YYYY-MM-DD",
            "time": "HH:MM",
            "duration": 60,
            "person_id": member_id_number,
            "description": "Optional description"
        }}
    ],
    "series_name": "Optional series name if multiple related events"
}}

Rules:
- Use 24-hour time format
- Duration in minutes (default 60)
- person_id must match one of the available family member IDs
- If no person specified, use the first family member
- If it's a recurring series, provide a series_name
- Parse dates intelligently (today, tomorrow, next Monday, etc.)
- **IMPORTANT** only return a valid JSON object with the exact structure described above. Do not return any other text or comments.
"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": description},
            ],
            temperature=0.1,
            max_tokens=2000,
        )

        app.logger.info(f"Groq parsing result: {json.dumps(response.dict(), indent=2)}")
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        app.logger.error(f"Groq parsing error: {e}")
        return {"events": [], "series_name": None}


@app.route("/")
def index():
    app.logger.debug("result")
    if current_user.is_authenticated:
        return redirect(url_for("calendar_view"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("calendar_view"))
        flash("Invalid username or password")

    return render_template("login.html")


@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"]
    password = request.form["password"]

    if User.query.filter_by(username=username).first():
        flash("Username already exists")
        return redirect(url_for("login"))

    user = User(username=username, password=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()

    # Create default family members
    default_members = [
        FamilyMember(name="Dad", color="#3498db", user_id=user.id),
        FamilyMember(name="Mom", color="#e74c3c", user_id=user.id),
        FamilyMember(name="Kid 1", color="#2ecc71", user_id=user.id),
        FamilyMember(name="Kid 2", color="#f39c12", user_id=user.id),
    ]

    for member in default_members:
        db.session.add(member)

    db.session.commit()
    flash("Registration successful! Please login.")
    return redirect(url_for("login"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/calendar")
@login_required
def calendar_view():
    events = (
        Event.query.join(FamilyMember)
        .filter(FamilyMember.user_id == current_user.id)
        .all()
    )

    family_members = FamilyMember.query.filter_by(user_id=current_user.id).all()

    # Format events for calendar display
    calendar_events = []
    for event in events:
        calendar_events.append(
            {
                "id": event.id,
                "title": event.title,
                "start": event.date_time.isoformat(),
                "end": (
                    event.date_time + timedelta(minutes=event.duration)
                ).isoformat(),
                "backgroundColor": event.family_member.color,
                "borderColor": event.family_member.color,
                "extendedProps": {
                    "person": event.family_member.name,
                    "description": event.description,
                    "seriesId": event.event_series_id,
                },
            }
        )

    return render_template(
        "calendar.html", events=calendar_events, family_members=family_members
    )


@app.route("/add_event", methods=["GET", "POST"])
@login_required
def add_event():
    family_members = FamilyMember.query.filter_by(user_id=current_user.id).all()

    if request.method == "POST":
        description = request.form["description"]

        # Parse events using Groq
        parsed_data = parse_events_with_groq(description, family_members)

        event_series = None
        if parsed_data.get("series_name"):
            event_series = EventSeries(
                name=parsed_data["series_name"],
                description=description,
                user_id=current_user.id,
            )
            db.session.add(event_series)
            db.session.flush()  # Get the ID

        events_created = 0
        for event_data in parsed_data["events"]:
            try:
                # Parse date and time
                event_date = datetime.strptime(event_data["date"], "%Y-%m-%d").date()
                event_time = datetime.strptime(event_data["time"], "%H:%M").time()
                event_datetime = datetime.combine(event_date, event_time)

                event = Event(
                    title=event_data["title"],
                    date_time=event_datetime,
                    duration=event_data.get("duration", 60),
                    description=event_data.get("description", ""),
                    family_member_id=event_data["person_id"],
                    event_series_id=event_series.id if event_series else None,
                )
                db.session.add(event)
                events_created += 1
            except Exception as e:
                app.logger.error(f"Error creating event: {e}")
                continue

        db.session.commit()
        flash(f"Successfully created {events_created} event(s)!")
        return redirect(url_for("calendar_view"))

    return render_template("add_event.html", family_members=family_members)


@app.route("/delete_event/<int:event_id>", methods=["POST"])
@login_required
def delete_event(event_id):
    event = (
        Event.query.join(FamilyMember)
        .filter(Event.id == event_id, FamilyMember.user_id == current_user.id)
        .first()
    )

    if event:
        db.session.delete(event)
        db.session.commit()
        flash("Event deleted successfully!")

    return redirect(url_for("calendar_view"))


@app.route("/delete_series/<int:series_id>", methods=["POST"])
@login_required
def delete_series(series_id):
    series = EventSeries.query.filter_by(id=series_id, user_id=current_user.id).first()

    if series:
        # Delete all events in the series
        events = Event.query.filter_by(event_series_id=series_id).all()
        for event in events:
            db.session.delete(event)

        db.session.delete(series)
        db.session.commit()
        flash("Event series deleted successfully!")

    return redirect(url_for("calendar_view"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0")

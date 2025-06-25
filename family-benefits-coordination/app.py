# app.py - Main Flask Application
import os
import io
from datetime import datetime, date
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file,
    jsonify,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key-change-this-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///insurance_claims.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max-file-size

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    claims = db.relationship("Claim", backref="user", lazy=True)


class Claim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Claim details
    date_of_service = db.Column(db.Date, nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False)
    service_provider = db.Column(db.String(200), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    person_served = db.Column(db.String(100), nullable=False)

    # Workflow status
    status = db.Column(db.String(50), nullable=False, default="submitted")

    # Important dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    insurance1_submitted_date = db.Column(db.Date)
    insurance1_processed_date = db.Column(db.Date)
    insurance1_amount = db.Column(db.Numeric(10, 2))
    insurance2_submitted_date = db.Column(db.Date)
    insurance2_processed_date = db.Column(db.Date)
    insurance2_amount = db.Column(db.Numeric(10, 2))
    closed_date = db.Column(db.Date)

    # Notes
    notes = db.Column(db.Text)

    documents = db.relationship(
        "ClaimDocument", backref="claim", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def total_reimbursed(self):
        total = 0
        if self.insurance1_amount:
            total += float(self.insurance1_amount)
        if self.insurance2_amount:
            total += float(self.insurance2_amount)
        return total

    @property
    def outstanding_amount(self):
        return float(self.amount_paid) - self.total_reimbursed

    @property
    def status_display(self):
        status_map = {
            "submitted": "Paid to Provider",
            "insurance1_submitted": "Submitted to Primary Insurance",
            "insurance1_processed": "Primary Insurance Processed",
            "insurance2_submitted": "Submitted to Secondary Insurance",
            "insurance2_processed": "Secondary Insurance Processed",
            "closed": "Closed",
        }
        return status_map.get(self.status, self.status)

    @property
    def next_action(self):
        actions = {
            "submitted": "Submit to primary insurance",
            "insurance1_submitted": "Wait for primary insurance processing",
            "insurance1_processed": "Submit COB to secondary insurance",
            "insurance2_submitted": "Wait for secondary insurance processing",
            "insurance2_processed": "Close claim",
            "closed": "Complete",
        }
        return actions.get(self.status, "Unknown")


class ClaimDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claim.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_data = db.Column(db.LargeBinary, nullable=False)
    mimetype = db.Column(db.String(100), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    document_type = db.Column(db.String(50), nullable=False)  # receipt, cob, etc.


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Routes
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        family_name = request.form["family_name"]
        email = request.form["email"]
        password = request.form["password"]

        if User.query.filter_by(email=email).first():
            flash("Email already registered", "error")
            return render_template("register.html")

        user = User(
            family_name=family_name,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Registration successful!", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    claims = (
        Claim.query.filter_by(user_id=current_user.id)
        .filter(Claim.status != "closed")
        .order_by(Claim.created_at.desc())
        .all()
    )

    # Summary statistics
    total_claims = len(claims)
    total_outstanding = sum(claim.outstanding_amount for claim in claims)

    return render_template(
        "dashboard.html",
        claims=claims,
        total_claims=total_claims,
        total_outstanding=total_outstanding,
    )


@app.route("/claims")
@login_required
def all_claims():
    claims = (
        Claim.query.filter_by(user_id=current_user.id)
        .order_by(Claim.created_at.desc())
        .all()
    )
    return render_template("claims.html", claims=claims)


@app.route("/claim/new", methods=["GET", "POST"])
@login_required
def new_claim():
    if request.method == "POST":
        claim = Claim(
            user_id=current_user.id,
            date_of_service=datetime.strptime(
                request.form["date_of_service"], "%Y-%m-%d"
            ).date(),
            amount_paid=float(request.form["amount_paid"]),
            service_provider=request.form["service_provider"],
            service_type=request.form["service_type"],
            person_served=request.form["person_served"],
            notes=request.form.get("notes", ""),
        )

        db.session.add(claim)
        db.session.commit()

        # Handle file upload
        if "receipt" in request.files:
            file = request.files["receipt"]
            if file and file.filename:
                filename = secure_filename(file.filename)
                doc = ClaimDocument(
                    claim_id=claim.id,
                    filename=filename,
                    file_data=file.read(),
                    mimetype=file.mimetype,
                    document_type="receipt",
                )
                db.session.add(doc)
                db.session.commit()

        flash("Claim created successfully!", "success")
        return redirect(url_for("claim_detail", id=claim.id))

    return render_template("new_claim.html")


@app.route("/claim/<int:id>")
@login_required
def claim_detail(id):
    claim = Claim.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    return render_template("claim_detail.html", claim=claim)


@app.route("/claim/<int:id>/update", methods=["POST"])
@login_required
def update_claim(id):
    claim = Claim.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    action = request.form["action"]

    if action == "submit_insurance1":
        claim.status = "insurance1_submitted"
        claim.insurance1_submitted_date = date.today()
    elif action == "process_insurance1":
        claim.status = "insurance1_processed"
        claim.insurance1_processed_date = date.today()
        claim.insurance1_amount = float(request.form["insurance1_amount"])
    elif action == "submit_insurance2":
        claim.status = "insurance2_submitted"
        claim.insurance2_submitted_date = date.today()
    elif action == "process_insurance2":
        claim.status = "insurance2_processed"
        claim.insurance2_processed_date = date.today()
        claim.insurance2_amount = float(request.form["insurance2_amount"])
    elif action == "close":
        claim.status = "closed"
        claim.closed_date = date.today()

    db.session.commit()
    flash("Claim updated successfully!", "success")
    return redirect(url_for("claim_detail", id=id))


@app.route("/claim/<int:id>/upload", methods=["POST"])
@login_required
def upload_document(id):
    claim = Claim.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    if "document" not in request.files:
        flash("No file selected", "error")
        return redirect(url_for("claim_detail", id=id))

    file = request.files["document"]
    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("claim_detail", id=id))

    filename = secure_filename(file.filename)
    doc_type = request.form["document_type"]

    doc = ClaimDocument(
        claim_id=claim.id,
        filename=filename,
        file_data=file.read(),
        mimetype=file.mimetype,
        document_type=doc_type,
    )

    db.session.add(doc)
    db.session.commit()

    flash("Document uploaded successfully!", "success")
    return redirect(url_for("claim_detail", id=id))


@app.route("/document/<int:id>")
@login_required
def download_document(id):
    doc = (
        ClaimDocument.query.join(Claim)
        .filter(ClaimDocument.id == id, Claim.user_id == current_user.id)
        .first_or_404()
    )

    return send_file(
        io.BytesIO(doc.file_data),
        download_name=doc.filename,
        as_attachment=True,
        mimetype=doc.mimetype,
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

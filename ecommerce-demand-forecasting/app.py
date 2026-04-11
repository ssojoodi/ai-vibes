# app.py
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_file,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
import pandas as pd
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import plotly.graph_objs as go
import plotly.utils
import json
import os
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key-here"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///forecasting.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "uploads"

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Ensure upload directory exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DataSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    source_name = db.Column(
        db.String(50), nullable=False
    )  # Amazon, FBA, Walmart, Shopify, Internal
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    record_count = db.Column(db.Integer)


class SalesData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    source_id = db.Column(db.Integer, db.ForeignKey("data_source.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    product_sku = db.Column(db.String(100), nullable=False)
    product_name = db.Column(db.String(255))
    quantity_sold = db.Column(db.Integer, nullable=False)
    revenue = db.Column(db.Float)
    cost = db.Column(db.Float)


class InventoryData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    source_id = db.Column(db.Integer, db.ForeignKey("data_source.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    product_sku = db.Column(db.String(100), nullable=False)
    current_stock = db.Column(db.Integer, nullable=False)
    reorder_point = db.Column(db.Integer)
    max_stock = db.Column(db.Integer)


class Forecast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_sku = db.Column(db.String(100), nullable=False)
    forecast_date = db.Column(db.Date, nullable=False)
    predicted_demand = db.Column(db.Float, nullable=False)
    confidence_lower = db.Column(db.Float)
    confidence_upper = db.Column(db.Float)
    model_used = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_sku = db.Column(db.String(100), nullable=False)
    alert_type = db.Column(
        db.String(50), nullable=False
    )  # reorder, stockout, overstock
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        if User.query.filter_by(username=username).first():
            flash("Username already exists")
            return render_template("register.html")

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        flash("Registration successful")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    # Get summary statistics
    total_products = (
        db.session.query(SalesData.product_sku)
        .filter_by(user_id=current_user.id)
        .distinct()
        .count()
    )
    recent_alerts = (
        Alert.query.filter_by(user_id=current_user.id, is_read=False).limit(5).all()
    )

    # Get recent forecasts
    recent_forecasts = (
        db.session.query(Forecast)
        .filter_by(user_id=current_user.id)
        .order_by(Forecast.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "dashboard.html",
        total_products=total_products,
        recent_alerts=recent_alerts,
        recent_forecasts=recent_forecasts,
    )


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload_data():
    if request.method == "POST":
        source_name = request.form["source_name"]
        data_type = request.form["data_type"]  # sales or inventory
        file = request.files["file"]

        if file and file.filename.endswith(".csv"):
            try:
                df = pd.read_csv(file)

                # Create data source record
                data_source = DataSource(
                    user_id=current_user.id,
                    source_name=source_name,
                    filename=file.filename,
                    record_count=len(df),
                )
                db.session.add(data_source)
                db.session.flush()

                # Process data based on type
                if data_type == "sales":
                    process_sales_data(df, data_source.id)
                elif data_type == "inventory":
                    process_inventory_data(df, data_source.id)

                db.session.commit()
                flash(f"Successfully uploaded {len(df)} records from {source_name}")

            except Exception as e:
                db.session.rollback()
                flash(f"Error processing file: {str(e)}")
        else:
            flash("Please upload a valid CSV file")

    return render_template("upload.html")


def process_sales_data(df, source_id):
    """Process sales data CSV and save to database"""
    # Expected columns: date, product_sku, product_name, quantity_sold, revenue, cost
    required_columns = ["date", "product_sku", "quantity_sold"]

    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"CSV must contain columns: {required_columns}")

    for _, row in df.iterrows():
        sales_record = SalesData(
            user_id=current_user.id,
            source_id=source_id,
            date=pd.to_datetime(row["date"]).date(),
            product_sku=row["product_sku"],
            product_name=row.get("product_name", ""),
            quantity_sold=int(row["quantity_sold"]),
            revenue=float(row.get("revenue", 0)),
            cost=float(row.get("cost", 0)),
        )
        db.session.add(sales_record)


def process_inventory_data(df, source_id):
    """Process inventory data CSV and save to database"""
    # Expected columns: date, product_sku, current_stock, reorder_point, max_stock
    required_columns = ["date", "product_sku", "current_stock"]

    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"CSV must contain columns: {required_columns}")

    for _, row in df.iterrows():
        inventory_record = InventoryData(
            user_id=current_user.id,
            source_id=source_id,
            date=pd.to_datetime(row["date"]).date(),
            product_sku=row["product_sku"],
            current_stock=int(row["current_stock"]),
            reorder_point=int(row.get("reorder_point", 0)),
            max_stock=int(row.get("max_stock", 0)),
        )
        db.session.add(inventory_record)


@app.route("/forecast")
@login_required
def forecast_view():
    products = (
        db.session.query(SalesData.product_sku)
        .filter_by(user_id=current_user.id)
        .distinct()
        .all()
    )
    return render_template("forecast.html", products=[p[0] for p in products])


@app.route("/generate_forecast", methods=["POST"])
@login_required
def generate_forecast():
    product_sku = request.form["product_sku"]
    forecast_days = int(request.form.get("forecast_days", 30))
    model_type = request.form.get("model_type", "arima")

    try:
        # Get historical sales data
        sales_data = (
            db.session.query(SalesData)
            .filter_by(user_id=current_user.id, product_sku=product_sku)
            .order_by(SalesData.date)
            .all()
        )

        if len(sales_data) < 10:
            flash("Need at least 10 data points for forecasting")
            return redirect(url_for("forecast_view"))

        # Prepare time series data
        df = pd.DataFrame(
            [
                {"date": record.date, "quantity": record.quantity_sold}
                for record in sales_data
            ]
        )

        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").resample("D").sum().fillna(0)

        # Generate forecast
        if model_type == "arima":
            forecast_data = generate_arima_forecast(df["quantity"], forecast_days)
        else:  # exponential_smoothing
            forecast_data = generate_exponential_smoothing_forecast(
                df["quantity"], forecast_days
            )

        # Save forecast to database
        save_forecast_to_db(product_sku, forecast_data, model_type)

        # Generate alerts
        generate_reorder_alerts(product_sku, forecast_data)

        flash(f"Forecast generated for {product_sku}")
        return redirect(url_for("forecast_results", product_sku=product_sku))

    except Exception as e:
        flash(f"Error generating forecast: {str(e)}")
        return redirect(url_for("forecast_view"))


def generate_arima_forecast(ts_data, forecast_days):
    """Generate ARIMA forecast"""
    try:
        # Auto ARIMA parameters (simplified)
        model = ARIMA(ts_data, order=(1, 1, 1))
        fitted_model = model.fit()

        # Generate forecast
        forecast = fitted_model.forecast(steps=forecast_days)
        conf_int = fitted_model.get_forecast(steps=forecast_days).conf_int()

        # Prepare forecast data
        start_date = ts_data.index[-1] + timedelta(days=1)
        forecast_dates = [start_date + timedelta(days=i) for i in range(forecast_days)]

        forecast_data = []
        for i, date in enumerate(forecast_dates):
            forecast_data.append(
                {
                    "date": date,
                    "predicted_demand": max(0, forecast.iloc[i]),
                    "confidence_lower": max(0, conf_int.iloc[i, 0]),
                    "confidence_upper": max(0, conf_int.iloc[i, 1]),
                }
            )

        return forecast_data

    except Exception as e:
        # Fallback to simple moving average
        avg_demand = ts_data.tail(7).mean()
        start_date = ts_data.index[-1] + timedelta(days=1)

        forecast_data = []
        for i in range(forecast_days):
            date = start_date + timedelta(days=i)
            forecast_data.append(
                {
                    "date": date,
                    "predicted_demand": max(0, avg_demand),
                    "confidence_lower": max(0, avg_demand * 0.8),
                    "confidence_upper": max(0, avg_demand * 1.2),
                }
            )

        return forecast_data


def generate_exponential_smoothing_forecast(ts_data, forecast_days):
    """Generate Exponential Smoothing forecast"""
    try:
        model = ExponentialSmoothing(ts_data, trend="add", seasonal=None)
        fitted_model = model.fit()

        forecast = fitted_model.forecast(steps=forecast_days)

        start_date = ts_data.index[-1] + timedelta(days=1)
        forecast_dates = [start_date + timedelta(days=i) for i in range(forecast_days)]

        forecast_data = []
        for i, date in enumerate(forecast_dates):
            pred_val = max(0, forecast[i])
            forecast_data.append(
                {
                    "date": date,
                    "predicted_demand": pred_val,
                    "confidence_lower": pred_val * 0.85,
                    "confidence_upper": pred_val * 1.15,
                }
            )

        return forecast_data

    except Exception as e:
        # Fallback to simple moving average
        avg_demand = ts_data.tail(7).mean()
        start_date = ts_data.index[-1] + timedelta(days=1)

        forecast_data = []
        for i in range(forecast_days):
            date = start_date + timedelta(days=i)
            forecast_data.append(
                {
                    "date": date,
                    "predicted_demand": max(0, avg_demand),
                    "confidence_lower": max(0, avg_demand * 0.8),
                    "confidence_upper": max(0, avg_demand * 1.2),
                }
            )

        return forecast_data


def save_forecast_to_db(product_sku, forecast_data, model_type):
    """Save forecast results to database"""
    # Delete existing forecasts for this product
    Forecast.query.filter_by(user_id=current_user.id, product_sku=product_sku).delete()

    # Save new forecasts
    for data_point in forecast_data:
        forecast_record = Forecast(
            user_id=current_user.id,
            product_sku=product_sku,
            forecast_date=data_point["date"],
            predicted_demand=data_point["predicted_demand"],
            confidence_lower=data_point["confidence_lower"],
            confidence_upper=data_point["confidence_upper"],
            model_used=model_type,
        )
        db.session.add(forecast_record)

    db.session.commit()


def generate_reorder_alerts(product_sku, forecast_data):
    """Generate reorder alerts based on forecast"""
    # Get current inventory
    current_inventory = (
        db.session.query(InventoryData)
        .filter_by(user_id=current_user.id, product_sku=product_sku)
        .order_by(InventoryData.date.desc())
        .first()
    )

    if not current_inventory:
        return

    # Calculate cumulative demand for next 7 days
    week_demand = sum([d["predicted_demand"] for d in forecast_data[:7]])

    # Check if reorder is needed
    if current_inventory.current_stock < week_demand:
        alert = Alert(
            user_id=current_user.id,
            product_sku=product_sku,
            alert_type="reorder",
            message=f"Reorder needed for {product_sku}. Current stock: {current_inventory.current_stock}, 7-day forecast demand: {week_demand:.0f}",
        )
        db.session.add(alert)
        db.session.commit()


@app.route("/forecast_results/<product_sku>")
@login_required
def forecast_results(product_sku):
    # Get forecast data
    forecasts = (
        Forecast.query.filter_by(user_id=current_user.id, product_sku=product_sku)
        .order_by(Forecast.forecast_date)
        .all()
    )

    # Get historical data
    historical = (
        db.session.query(SalesData)
        .filter_by(user_id=current_user.id, product_sku=product_sku)
        .order_by(SalesData.date.desc())
        .limit(30)
        .all()
    )

    # Create plot
    fig = go.Figure()

    # Historical data
    if historical:
        hist_dates = [record.date for record in reversed(historical)]
        hist_values = [record.quantity_sold for record in reversed(historical)]

        fig.add_trace(
            go.Scatter(
                x=hist_dates,
                y=hist_values,
                mode="lines+markers",
                name="Historical Sales",
                line=dict(color="blue"),
            )
        )

    # Forecast data
    if forecasts:
        forecast_dates = [f.forecast_date for f in forecasts]
        forecast_values = [f.predicted_demand for f in forecasts]
        upper_bound = [f.confidence_upper for f in forecasts]
        lower_bound = [f.confidence_lower for f in forecasts]

        fig.add_trace(
            go.Scatter(
                x=forecast_dates,
                y=forecast_values,
                mode="lines+markers",
                name="Forecast",
                line=dict(color="red"),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=forecast_dates + forecast_dates[::-1],
                y=upper_bound + lower_bound[::-1],
                fill="toself",
                fillcolor="rgba(255,0,0,0.2)",
                line=dict(color="rgba(255,255,255,0)"),
                name="Confidence Interval",
            )
        )

    fig.update_layout(
        title=f"Demand Forecast for {product_sku}",
        xaxis_title="Date",
        yaxis_title="Quantity",
        hovermode="x",
    )

    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template(
        "forecast_results.html",
        product_sku=product_sku,
        forecasts=forecasts,
        graphJSON=graphJSON,
    )


@app.route("/alerts")
@login_required
def alerts():
    alerts = (
        Alert.query.filter_by(user_id=current_user.id)
        .order_by(Alert.created_at.desc())
        .all()
    )
    return render_template("alerts.html", alerts=alerts)


@app.route("/mark_alert_read/<int:alert_id>")
@login_required
def mark_alert_read(alert_id):
    alert = Alert.query.filter_by(id=alert_id, user_id=current_user.id).first()
    if alert:
        alert.is_read = True
        db.session.commit()
    return redirect(url_for("alerts"))


@app.route("/scenario_planning")
@login_required
def scenario_planning():
    products = (
        db.session.query(SalesData.product_sku)
        .filter_by(user_id=current_user.id)
        .distinct()
        .all()
    )
    return render_template("scenario_planning.html", products=[p[0] for p in products])


@app.route("/run_scenario", methods=["POST"])
@login_required
def run_scenario():
    product_sku = request.form["product_sku"]
    scenario_type = request.form["scenario_type"]
    adjustment_factor = float(request.form.get("adjustment_factor", 1.0))

    # Get base forecast
    base_forecasts = (
        Forecast.query.filter_by(user_id=current_user.id, product_sku=product_sku)
        .order_by(Forecast.forecast_date)
        .all()
    )

    if not base_forecasts:
        flash("Please generate a base forecast first")
        return redirect(url_for("scenario_planning"))

    # Apply scenario adjustment
    scenario_data = []
    for forecast in base_forecasts:
        adjusted_demand = forecast.predicted_demand * adjustment_factor
        scenario_data.append(
            {
                "date": forecast.forecast_date,
                "base_forecast": forecast.predicted_demand,
                "scenario_forecast": adjusted_demand,
                "adjustment_factor": adjustment_factor,
            }
        )

    return render_template(
        "scenario_results.html",
        product_sku=product_sku,
        scenario_type=scenario_type,
        scenario_data=scenario_data,
    )


@app.route("/export_forecast/<product_sku>")
@login_required
def export_forecast(product_sku):
    forecasts = (
        Forecast.query.filter_by(user_id=current_user.id, product_sku=product_sku)
        .order_by(Forecast.forecast_date)
        .all()
    )

    # Create DataFrame
    data = []
    for f in forecasts:
        data.append(
            {
                "Product SKU": f.product_sku,
                "Forecast Date": f.forecast_date,
                "Predicted Demand": f.predicted_demand,
                "Confidence Lower": f.confidence_lower,
                "Confidence Upper": f.confidence_upper,
                "Model Used": f.model_used,
                "Generated At": f.created_at,
            }
        )

    df = pd.DataFrame(data)

    # Save to CSV
    filename = f"forecast_{product_sku}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    df.to_csv(filepath, index=False)

    return send_file(filepath, as_attachment=True, download_name=filename)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

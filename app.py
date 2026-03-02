
from flask import Flask, render_template, request, redirect, session
from supabase import create_client
import uuid
from datetime import date

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Supabase config
SUPABASE_URL = "https://rcrbazstbgqfmhzubmrg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJjcmJhenN0YmdxZm1oenVibXJnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzc2NTMxMiwiZXhwIjoyMDczMzQxMzEyfQ.Y42dwejCsS66t0d-cMXaxL5Gxm9YuWx1JebUQelC5FQ"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
import math

ALLOWED_RADIUS = 50  # meters

ALLOWED_LOCATIONS = [
    (17.083713, 82.055970) # Classroom 1
    
]

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda/2)**2

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/health")
def health():
    return "OK", 200



# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        name = request.form["name"]

        # 🔍 Check if username already exists
        existing_user = supabase.table("test_users") \
            .select("*") \
            .eq("username", username) \
            .execute()

        if len(existing_user.data) > 0:
            return render_template("register.html",
                                   error="Username already registered!")

        # Insert new user
        supabase.table("test_users").insert({
            "username": username,
            "password": password,
            "name": name
        }).execute()

        return render_template("register.html",
                               success="Registration successful! Wait for approval.")

    return render_template("register.html")
# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        device_id = request.form["device_id"]

        user = supabase.table("test_users") \
            .select("*") \
            .eq("username", username) \
            .eq("password", password) \
            .execute()

        if len(user.data) == 0:
            return "Invalid credentials"

        user_data = user.data[0]

        # Check CR approval
        if not user_data["is_approved"]:
            return "Not approved by CR"

        # DEVICE LOGIC STARTS HERE

        # First login (no device saved)
        if user_data["device_id"] is None:
            supabase.table("test_users") \
                .update({"device_id": device_id}) \
                .eq("id", user_data["id"]) \
                .execute()

        # If device mismatch
        elif user_data["device_id"] != device_id:
            return "This account is already active on another device"

        # Save session
        session["user_id"] = user_data["id"]
        session["name"] = user_data["name"]

        return redirect("/dashboard")

    return render_template("login.html")
# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    today = str(date.today())

    attendance_today = supabase.table("attendance") \
        .select("*") \
        .eq("student_id", session["user_id"]) \
        .eq("date", today) \
        .execute()

    marked_today = len(attendance_today.data) > 0

    return render_template("dashboard.html",
                           name=session["name"],
                           marked_today=marked_today)
from datetime import datetime
import calendar

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect("/")

    from datetime import datetime
    import calendar

    now = datetime.now()

    year = request.args.get("year", type=int) or now.year
    month = request.args.get("month", type=int) or now.month

    total_days = calendar.monthrange(year, month)[1]

    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{total_days}"

    attendance = supabase.table("attendance") \
        .select("date") \
        .eq("student_id", session["user_id"]) \
        .gte("date", start_date) \
        .lte("date", end_date) \
        .execute()

    present_dates = {record["date"] for record in attendance.data}

    return render_template("history.html",
                           year=year,
                           month=month,
                           total_days=total_days,
                           present_dates=present_dates,
                           today=now.day,
                           current_year=now.year,
                           current_month=now.month)
# ---------------- MARK ATTENDANCE ----------------
from flask import jsonify

@app.route("/mark", methods=["POST"])
def mark():
    if "user_id" not in session:
        return jsonify({"status": "error", "message": "Not logged in"})

    latitude = float(request.form["latitude"])
    longitude = float(request.form["longitude"])
    today = str(date.today())

    # Check already marked
    existing = supabase.table("attendance") \
        .select("*") \
        .eq("student_id", session["user_id"]) \
        .eq("date", today) \
        .execute()

    if len(existing.data) > 0:
        return jsonify({"status": "already"})

    inside_allowed_area = False

    for lat, lon in ALLOWED_LOCATIONS:
        distance = calculate_distance(latitude, longitude, lat, lon)
        print("Distance:", distance)

        if distance <= ALLOWED_RADIUS:
            inside_allowed_area = True
            break

    if not inside_allowed_area:
        return jsonify({"status": "error", "message": "Outside allowed area"})

    supabase.table("attendance").insert({
        "student_id": session["user_id"],
        "date": today,
        "latitude": latitude,
        "longitude": longitude
    }).execute()

    return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run()

import os
from functools import wraps
from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from database import DB_PATH, get_connection
from flag_cipher import decrypt_flag, hash_flag

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")

FLAG_BASE_POINTS = {
    "SQLI": 100,
    "SQLI_ADV": 110,
    "SQLI_BLIND": 140,
    "XSS": 90,
    "CSRF": 90,
    "STEG": 50,
}
POINT_DECAY = 15
MIN_POINTS = 20


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "student_id" not in session:
            flash("Please log in to access the labs.", "warning")
            return redirect(url_for("landing"))
        return func(*args, **kwargs)

    return wrapper


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            flash("Admin access required.", "warning")
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)

    return wrapper


@app.before_request
def attach_db():
    g.db = get_connection()


@app.teardown_request
def close_db(_):
    db = getattr(g, "db", None)
    if db is not None:
        db.close()


def current_student():
    if "student_id" not in session:
        return None
    cursor = g.db.execute("SELECT * FROM students WHERE id = ?", (session["student_id"],))
    return cursor.fetchone()


def current_admin():
    if "admin_id" not in session:
        return None
    cursor = g.db.execute("SELECT * FROM admins WHERE id = ?", (session["admin_id"],))
    return cursor.fetchone()


def _decrypt_row_values(rows):
    """
    Decrypt any encrypted flag values in query result rows.
    This allows SQLi UNION SELECT results to show plaintext flags.
    Tries to decrypt all string values - if decryption fails, keeps original value.
    """
    if not rows:
        return rows
    decrypted_rows = []
    for row in rows:
        # Convert Row to dict if needed
        if hasattr(row, 'keys'):
            row_dict = {key: row[key] for key in row.keys()}
        else:
            row_dict = dict(row)
        
        decrypted_row = {}
        for key, value in row_dict.items():
            if value and isinstance(value, str):
                # Try to decrypt - if it fails, it's not an encrypted flag
                try:
                    decrypted = decrypt_flag(value)
                    # If decryption succeeded (not corrupted and different from original), use decrypted value
                    if decrypted and decrypted != "[corrupted-flag]" and decrypted != value:
                        decrypted_row[key] = decrypted
                    else:
                        decrypted_row[key] = value
                except Exception:
                    # If decryption fails for any reason, keep original value
                    decrypted_row[key] = value
            else:
                decrypted_row[key] = value
        decrypted_rows.append(decrypted_row)
    return decrypted_rows


@app.route("/")
def landing():
    return render_template(
        "landing.html",
        logged_in="student_id" in session,
        brand="#4CK P07470",
    )


@app.route("/login", methods=["POST"])
def login():
    roll_no = request.form.get("roll_no", "").strip()
    password = request.form.get("password", "")

    student = g.db.execute("SELECT * FROM students WHERE roll_no = ?", (roll_no,)).fetchone()
    if not student or not check_password_hash(student["password_hash"], password):
        flash("Invalid roll number or password.", "danger")
        return redirect(url_for("landing"))

    session["student_id"] = student["id"]
    flash(f"Welcome back, {student['name']}!", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out.", "info")
    return redirect(url_for("landing"))


@app.route("/dashboard")
@login_required
def dashboard():
    student = current_student()
    challenges = g.db.execute(
        """
        SELECT f.id,
               f.category,
               f.description,
               COALESCE(s.submitted_at, '') AS submitted_at
        FROM flags f
        LEFT JOIN submissions s
            ON s.flag_id = f.id AND s.student_id = ?
        ORDER BY f.category
        """,
        (student["id"],),
    ).fetchall()

    leaderboard = g.db.execute(
        """
        SELECT students.name,
               students.roll_no,
               ss.total_points AS score,
               ss.total_captures AS captures
        FROM students
        JOIN student_stats ss ON ss.student_id = students.id
        ORDER BY score DESC, captures DESC, students.name ASC
        LIMIT 10
        """
    ).fetchall()

    return render_template(
        "dashboard.html",
        student=student,
        challenges=challenges,
        leaderboard=leaderboard,
    )


@app.route("/sqli")
@login_required
def sqli_lab():
    student = current_student()
    term = request.args.get("term", "")
    rows = []
    raw_query = None
    error = None
    if term:
        raw_query = (
            "SELECT roll_no, display_name, points FROM leaderboard "
            f"WHERE display_name LIKE '%{term}%' ORDER BY points DESC"
        )
        try:
            rows = g.db.execute(raw_query).fetchall()
            # Decrypt any encrypted flags in the results
            rows = _decrypt_row_values(rows)
        except Exception as exc:  # noqa: BLE001 intentional for lab
            error = str(exc)
    return render_template(
        "sqli.html",
        student=student,
        rows=rows,
        raw_query=raw_query,
        term=term,
        error=error,
    )


@app.route("/sqli/contracts")
@login_required
def sqli_contracts():
    student = current_student()
    client = request.args.get("client", "")
    rows = []
    error = None
    raw_query = None
    if client:
        raw_query = (
            "SELECT client_name, scope, budget, confidential_notes FROM contracts "
            f"WHERE client_name LIKE '%{client}%' ORDER BY budget DESC"
        )
        try:
            rows = g.db.execute(raw_query).fetchall()
            # Decrypt any encrypted flags in the results
            rows = _decrypt_row_values(rows)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
    return render_template(
        "sqli_contracts.html",
        student=student,
        rows=rows,
        raw_query=raw_query,
        client=client,
        error=error,
    )


@app.route("/sqli/blind", methods=["GET", "POST"])
@login_required
def sqli_blind():
    student = current_student()
    guess = request.values.get("guess", "")
    verdict = None
    success_flag = None
    if guess:
        raw_query = (
            "SELECT CASE WHEN EXISTS ("
            f"SELECT 1 FROM flags WHERE category = 'SQLI_BLIND' AND code = '{guess}'"
            ") THEN 'ACCESS GRANTED' ELSE 'ACCESS DENIED' END AS verdict"
        )
        try:
            verdict = g.db.execute(raw_query).fetchone()["verdict"]
        except Exception:  # noqa: BLE001
            verdict = "ACCESS DENIED"
        if verdict == "ACCESS GRANTED":
            encrypted_flag = g.db.execute(
                "SELECT code FROM flags WHERE category = 'SQLI_BLIND'"
            ).fetchone()["code"]
            success_flag = decrypt_flag(encrypted_flag)
    return render_template(
        "sqli_blind.html",
        student=student,
        verdict=verdict,
        guess=guess,
        success_flag=success_flag,
    )


@app.route("/xss", methods=["GET", "POST"])
@login_required
def xss_lab():
    student = current_student()
    if request.method == "POST":
        content = request.form.get("content", "")
        if not content.strip():
            flash("Message cannot be empty.", "warning")
        else:
            g.db.execute(
                "INSERT INTO feedback (student_id, content) VALUES (?, ?)",
                (student["id"], content),
            )
            g.db.commit()
            flash("Message posted. Did anything unexpected execute?", "info")
        return redirect(url_for("xss_lab"))

    messages = g.db.execute(
        """
        SELECT feedback.content,
               students.name AS author,
               feedback.created_at
        FROM feedback
        JOIN students ON students.id = feedback.student_id
        ORDER BY feedback.created_at DESC
        """
    ).fetchall()
    encrypted_xss_flag = g.db.execute("SELECT code FROM flags WHERE category = 'XSS'").fetchone()["code"]
    xss_flag = decrypt_flag(encrypted_xss_flag)
    return render_template(
        "xss.html",
        student=student,
        messages=messages,
        xss_flag=xss_flag,
    )


@app.route("/csrf", methods=["GET"])
@login_required
def csrf_lab():
    student = current_student()
    encrypted_csrf_flag = g.db.execute("SELECT code FROM flags WHERE category = 'CSRF'").fetchone()["code"]
    csrf_flag = decrypt_flag(encrypted_csrf_flag)
    return render_template("csrf.html", student=student, csrf_flag=csrf_flag)


@app.route("/csrf/update-email", methods=["POST"])
@login_required
def update_email():
    student = current_student()
    new_email = request.form.get("email", "").strip()
    if not new_email:
        flash("Email is required.", "danger")
        return redirect(url_for("csrf_lab"))

    g.db.execute("UPDATE students SET email = ? WHERE id = ?", (new_email, student["id"]))
    g.db.commit()
    flash(
        "Email updated. Imagine what happens if a malicious site submits this form on your behalf!",
        "info",
    )
    return redirect(url_for("csrf_lab"))


@app.route("/flags", methods=["GET"])
@login_required
def flag_station():
    student = current_student()
    challenge_rows = g.db.execute(
        """
        SELECT f.id,
               f.category,
               f.description,
               COALESCE(s.submitted_at, '') AS submitted_at
        FROM flags f
        LEFT JOIN submissions s
            ON s.flag_id = f.id AND s.student_id = ?
        ORDER BY f.category
        """,
        (student["id"],),
    ).fetchall()
    return render_template("flags.html", student=student, challenges=challenge_rows)


@app.route("/bonus")
@login_required
def bonus():
    return render_template("bonus.html")


@app.route("/flags/submit", methods=["POST"])
@login_required
def submit_flag():
    student = current_student()
    category = request.form.get("category", "").upper()
    submitted_flag = request.form.get("flag", "").strip()

    if not submitted_flag:
        flash("Enter a flag value.", "warning")
        return redirect(url_for("flag_station"))

    flag = g.db.execute(
        "SELECT id, code, code_hash, category FROM flags WHERE category = ?", (category,)
    ).fetchone()
    if not flag:
        flash("Unknown challenge category.", "danger")
        return redirect(url_for("flag_station"))

    submitted_hash = hash_flag(submitted_flag)
    if submitted_hash != flag["code_hash"]:
        flash("Incorrect flag. Keep digging!", "danger")
        return redirect(url_for("flag_station"))

    existing = g.db.execute(
        "SELECT COUNT(*) AS total FROM submissions WHERE flag_id = ?",
        (flag["id"],),
    ).fetchone()["total"]
    points = max(
        MIN_POINTS,
        FLAG_BASE_POINTS.get(flag["category"], 80) - existing * POINT_DECAY,
    )

    try:
        with g.db:
            g.db.execute(
                "INSERT INTO submissions (student_id, flag_id, points) VALUES (?, ?, ?)",
                (student["id"], flag["id"], points),
            )
            g.db.execute(
                """
                INSERT INTO student_stats (student_id, total_points, total_captures)
                VALUES (?, ?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    total_points = student_stats.total_points + excluded.total_points,
                    total_captures = student_stats.total_captures + excluded.total_captures
                """,
                (student["id"], points, 1),
            )
        flash(f"Flag captured for {category}! +{points} pts", "success")
    except Exception:  # noqa: BLE001
        flash("Flag already submitted.", "info")

    return redirect(url_for("flag_station"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_id"):
        return redirect(url_for("admin_panel"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = g.db.execute(
            "SELECT * FROM admins WHERE username = ?",
            (username,),
        ).fetchone()
        if not admin or not check_password_hash(admin["password_hash"], password):
            flash("Invalid admin credentials.", "danger")
            return redirect(url_for("admin_login"))
        session["admin_id"] = admin["id"]
        flash("Admin login success.", "success")
        return redirect(url_for("admin_panel"))
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    flash("Admin session ended.", "info")
    return redirect(url_for("landing"))


@app.route("/admin")
@admin_required
def admin_panel():
    totals = g.db.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM students) AS student_count,
            (SELECT COUNT(*) FROM submissions) AS capture_count,
            (SELECT COUNT(*) FROM flags) AS flag_count
        """
    ).fetchone()
    captures = g.db.execute(
        """
        SELECT students.roll_no,
               students.name,
               ss.total_captures AS captures,
               ss.total_points AS score
        FROM students
        JOIN student_stats ss ON ss.student_id = students.id
        ORDER BY score DESC, captures DESC, students.name ASC
        """
    ).fetchall()
    latest = g.db.execute(
        """
        SELECT students.roll_no,
               students.name,
               flags.category,
               submissions.points,
               submissions.submitted_at
        FROM submissions
        JOIN students ON students.id = submissions.student_id
        JOIN flags ON flags.id = submissions.flag_id
        ORDER BY submissions.submitted_at DESC
        LIMIT 15
        """
    ).fetchall()
    return render_template(
        "admin_panel.html",
        totals=totals,
        captures=captures,
        latest=latest,
    )


@app.route("/admin/download-db")
@admin_required
def admin_download_db():
    return send_file(
        DB_PATH,
        as_attachment=True,
        download_name="ctf_lab.db",
        mimetype="application/octet-stream",
    )


@app.route("/admin/reset-progress", methods=["POST"])
@admin_required
def admin_reset_progress():
    with g.db:
        g.db.execute("DELETE FROM submissions")
        g.db.execute("UPDATE student_stats SET total_points = 0, total_captures = 0")
    flash("All captures and score history have been reset.", "warning")
    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)


import json
import os
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "database.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-development-secret")
app.config["DATABASE"] = str(DATABASE_PATH)


def get_db():
    DATABASE_DIR.mkdir(exist_ok=True)
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student' CHECK(role IN ('student', 'admin')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            subject TEXT NOT NULL,
            duration INTEGER NOT NULL CHECK(duration > 0),
            pass_percentage REAL NOT NULL DEFAULT 40,
            published INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL CHECK(correct_answer IN ('A', 'B', 'C', 'D')),
            marks REAL NOT NULL DEFAULT 1 CHECK(marks > 0)
        );
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
            started_at TEXT NOT NULL,
            submitted_at TEXT,
            total_questions INTEGER NOT NULL,
            attempted INTEGER NOT NULL DEFAULT 0,
            correct INTEGER NOT NULL DEFAULT 0,
            incorrect INTEGER NOT NULL DEFAULT 0,
            unanswered INTEGER NOT NULL DEFAULT 0,
            total_marks REAL NOT NULL DEFAULT 0,
            marks_obtained REAL NOT NULL DEFAULT 0,
            percentage REAL NOT NULL DEFAULT 0,
            passed INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, exam_id)
        );
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER NOT NULL REFERENCES results(id) ON DELETE CASCADE,
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            selected_answer TEXT,
            is_correct INTEGER NOT NULL DEFAULT 0,
            UNIQUE(result_id, question_id)
        );
        """
    )
    seed_data(db)
    db.commit()
    db.close()


def seed_data(db):
    admin = db.execute("SELECT id FROM users WHERE email = ?", ("admin@example.com",)).fetchone()
    if not admin:
        db.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ("System Administrator", "admin@example.com", generate_password_hash("Admin@123"), "admin"),
        )
    student = db.execute("SELECT id FROM users WHERE email = ?", ("student@example.com",)).fetchone()
    if not student:
        db.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ("Alex Student", "student@example.com", generate_password_hash("Student@123"), "student"),
        )
    exam = db.execute("SELECT id FROM exams WHERE title = ?", ("Python Fundamentals Assessment",)).fetchone()
    if not exam:
        cursor = db.execute(
            "INSERT INTO exams (title, description, subject, duration, pass_percentage, published) VALUES (?, ?, ?, ?, ?, 1)",
            ("Python Fundamentals Assessment", "Test your understanding of Python syntax, data structures, and core programming concepts.", "Computer Science", 15, 40),
        )
        exam_id = cursor.lastrowid
        sample_questions = [
            (exam_id, "Which keyword defines a function in Python?", "func", "def", "function", "define", "B", 2),
            (exam_id, "What is the output type of input() in Python 3?", "int", "float", "str", "list", "C", 2),
            (exam_id, "Which collection stores unique unordered values?", "List", "Tuple", "Dictionary", "Set", "D", 2),
            (exam_id, "What does len([10, 20, 30]) return?", "2", "3", "10", "30", "B", 2),
            (exam_id, "Which symbol starts a single-line comment?", "//", "<!--", "#", "--", "C", 2),
        ]
        db.executemany(
            "INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_answer, marks) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            sample_questions,
        )


@app.context_processor
def inject_current_user():
    return {"current_user": session.get("user")}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user", {}).get("role") != "admin":
            flash("Administrator access is required.", "danger")
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped


def form_exam_values(form):
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    subject = form.get("subject", "").strip()
    try:
        duration = int(form.get("duration", "0"))
        pass_percentage = float(form.get("pass_percentage", "40"))
    except ValueError:
        raise ValueError("Duration and pass percentage must be numbers.")
    if not title or not description or not subject:
        raise ValueError("Title, description, and subject are required.")
    if duration < 1 or not 0 <= pass_percentage <= 100:
        raise ValueError("Enter a valid duration and pass percentage.")
    return title, description, subject, duration, pass_percentage


def get_exam(exam_id):
    db = get_db()
    exam = db.execute(
        "SELECT e.*, COUNT(q.id) AS total_questions, COALESCE(SUM(q.marks), 0) AS total_marks FROM exams e LEFT JOIN questions q ON q.exam_id = e.id WHERE e.id = ? GROUP BY e.id",
        (exam_id,),
    ).fetchone()
    db.close()
    return exam


@app.route("/")
def index():
    if session.get("user", {}).get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    if session.get("user"):
        return redirect(url_for("student_dashboard"))
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        db.close()
        if user and check_password_hash(user["password"], password):
            session["user"] = {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}
            destination = request.args.get("next") or (url_for("admin_dashboard") if user["role"] == "admin" else url_for("student_dashboard"))
            return redirect(destination)
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not name or not email or len(password) < 8 or password != confirm:
            flash("Enter a name, a valid email, and matching passwords of at least 8 characters.", "danger")
            return render_template("register.html")
        db = get_db()
        try:
            db.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, generate_password_hash(password)))
            db.commit()
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "danger")
            db.close()
            return render_template("register.html")
        db.close()
        flash("Account created. You can now sign in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/student/dashboard")
@login_required
def student_dashboard():
    if session["user"]["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    db = get_db()
    exams = db.execute("SELECT e.*, COUNT(q.id) AS total_questions, COALESCE(SUM(q.marks), 0) AS total_marks FROM exams e LEFT JOIN questions q ON q.exam_id = e.id WHERE e.published = 1 GROUP BY e.id ORDER BY e.created_at DESC").fetchall()
    recent_results = db.execute("SELECT r.*, e.title FROM results r JOIN exams e ON e.id = r.exam_id WHERE r.user_id = ? AND r.submitted_at IS NOT NULL ORDER BY r.submitted_at DESC LIMIT 5", (session["user"]["id"],)).fetchall()
    db.close()
    return render_template("student_dashboard.html", exams=exams, recent_results=recent_results)


@app.route("/exams")
@login_required
def exams():
    db = get_db()
    exam_rows = db.execute("SELECT e.*, COUNT(q.id) AS total_questions, COALESCE(SUM(q.marks), 0) AS total_marks FROM exams e LEFT JOIN questions q ON q.exam_id = e.id WHERE e.published = 1 GROUP BY e.id ORDER BY e.created_at DESC").fetchall()
    db.close()
    return render_template("exams.html", exams=exam_rows)


@app.route("/exam/<int:exam_id>")
@login_required
def exam_instructions(exam_id):
    exam = get_exam(exam_id)
    if not exam or not exam["published"]:
        flash("That examination is not available.", "danger")
        return redirect(url_for("exams"))
    db = get_db()
    previous = db.execute("SELECT id FROM results WHERE user_id = ? AND exam_id = ? AND submitted_at IS NOT NULL", (session["user"]["id"], exam_id)).fetchone()
    db.close()
    return render_template("exam.html", exam=exam, instructions=True, previous=previous)


@app.route("/exam/<int:exam_id>/take")
@login_required
def take_exam(exam_id):
    exam = get_exam(exam_id)
    if not exam or not exam["published"]:
        flash("That examination is not available.", "danger")
        return redirect(url_for("exams"))
    db = get_db()
    previous = db.execute("SELECT id FROM results WHERE user_id = ? AND exam_id = ? AND submitted_at IS NOT NULL", (session["user"]["id"], exam_id)).fetchone()
    db.close()
    if previous:
        return redirect(url_for("result", result_id=previous["id"]))
    return render_template("exam.html", exam=exam, instructions=False, previous=None)


@app.route("/result/<int:result_id>")
@login_required
def result(result_id):
    db = get_db()
    query = "SELECT r.*, e.title, e.subject, u.name AS student_name FROM results r JOIN exams e ON e.id = r.exam_id JOIN users u ON u.id = r.user_id WHERE r.id = ?"
    if session["user"]["role"] != "admin":
        query += " AND r.user_id = ?"
        row = db.execute(query, (result_id, session["user"]["id"])).fetchone()
    else:
        row = db.execute(query, (result_id,)).fetchone()
    db.close()
    if not row:
        flash("Result not found.", "danger")
        return redirect(url_for("student_dashboard"))
    return render_template("result.html", result=row)


@app.route("/results")
@login_required
def results():
    db = get_db()
    rows = db.execute("SELECT r.*, e.title, e.subject FROM results r JOIN exams e ON e.id = r.exam_id WHERE r.user_id = ? AND r.submitted_at IS NOT NULL ORDER BY r.submitted_at DESC", (session["user"]["id"],)).fetchall()
    db.close()
    return render_template("results.html", results=rows, admin_view=False)


@app.route("/api/exams/<int:exam_id>/questions")
@login_required
def exam_questions_api(exam_id):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id = ? AND published = 1", (exam_id,)).fetchone()
    if not exam:
        db.close()
        return jsonify({"error": "Exam not found"}), 404
    result = db.execute("SELECT * FROM results WHERE user_id = ? AND exam_id = ?", (session["user"]["id"], exam_id)).fetchone()
    if result and result["submitted_at"]:
        db.close()
        return jsonify({"error": "This exam has already been submitted", "result_id": result["id"]}), 409
    if not result:
        cursor = db.execute("INSERT INTO results (user_id, exam_id, started_at, total_questions) VALUES (?, ?, ?, ?)", (session["user"]["id"], exam_id, datetime.utcnow().isoformat(), db.execute("SELECT COUNT(*) FROM questions WHERE exam_id = ?", (exam_id,)).fetchone()[0]))
        result_id = cursor.lastrowid
        db.commit()
    else:
        result_id = result["id"]
    questions = db.execute("SELECT id, question_text, option_a, option_b, option_c, option_d, marks FROM questions WHERE exam_id = ? ORDER BY id", (exam_id,)).fetchall()
    saved = db.execute("SELECT question_id, selected_answer FROM answers WHERE result_id = ?", (result_id,)).fetchall()
    db.close()
    return jsonify({"exam": dict(exam), "result_id": result_id, "questions": [dict(question) for question in questions], "answers": {str(row["question_id"]): row["selected_answer"] for row in saved}})


@app.route("/api/exams/<int:exam_id>/submit", methods=["POST"])
@login_required
def submit_exam_api(exam_id):
    payload = request.get_json(silent=True) or {}
    submitted_answers = payload.get("answers", {})
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id = ? AND published = 1", (exam_id,)).fetchone()
    result = db.execute("SELECT * FROM results WHERE user_id = ? AND exam_id = ?", (session["user"]["id"], exam_id)).fetchone()
    if not exam or not result:
        db.close()
        return jsonify({"error": "Exam session not found"}), 404
    if result["submitted_at"]:
        db.close()
        return jsonify({"error": "This exam has already been submitted", "result_id": result["id"]}), 409
    questions = db.execute("SELECT * FROM questions WHERE exam_id = ?", (exam_id,)).fetchall()
    total_marks = sum(question["marks"] for question in questions)
    attempted = correct = incorrect = marks_obtained = 0
    db.execute("DELETE FROM answers WHERE result_id = ?", (result["id"],))
    for question in questions:
        selected = submitted_answers.get(str(question["id"]))
        is_correct = bool(selected and selected == question["correct_answer"])
        if selected:
            attempted += 1
            if is_correct:
                correct += 1
                marks_obtained += question["marks"]
            else:
                incorrect += 1
        db.execute("INSERT INTO answers (result_id, question_id, selected_answer, is_correct) VALUES (?, ?, ?, ?)", (result["id"], question["id"], selected, int(is_correct)))
    unanswered = len(questions) - attempted
    percentage = (marks_obtained / total_marks * 100) if total_marks else 0
    passed = int(percentage >= exam["pass_percentage"])
    db.execute("UPDATE results SET submitted_at = ?, attempted = ?, correct = ?, incorrect = ?, unanswered = ?, total_marks = ?, marks_obtained = ?, percentage = ?, passed = ? WHERE id = ?", (datetime.utcnow().isoformat(), attempted, correct, incorrect, unanswered, total_marks, marks_obtained, percentage, passed, result["id"]))
    db.commit()
    db.close()
    return jsonify({"result_id": result["id"], "percentage": percentage, "passed": bool(passed)})


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        "exams": db.execute("SELECT COUNT(*) FROM exams").fetchone()[0],
        "students": db.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0],
        "attempts": db.execute("SELECT COUNT(*) FROM results WHERE submitted_at IS NOT NULL").fetchone()[0],
        "pass_rate": db.execute("SELECT COALESCE(AVG(passed) * 100, 0) FROM results WHERE submitted_at IS NOT NULL").fetchone()[0],
    }
    recent = db.execute("SELECT r.*, e.title, u.name FROM results r JOIN exams e ON e.id = r.exam_id JOIN users u ON u.id = r.user_id WHERE r.submitted_at IS NOT NULL ORDER BY r.submitted_at DESC LIMIT 8").fetchall()
    db.close()
    return render_template("admin_dashboard.html", stats=stats, recent=recent)


@app.route("/admin/exams", methods=["GET", "POST"])
@admin_required
def manage_exams():
    db = get_db()
    if request.method == "POST":
        try:
            values = form_exam_values(request.form)
            db.execute("INSERT INTO exams (title, description, subject, duration, pass_percentage, published) VALUES (?, ?, ?, ?, ?, ?)", (*values, int(request.form.get("published") == "1")))
            db.commit()
            flash("Examination created.", "success")
        except ValueError as error:
            flash(str(error), "danger")
        db.close()
        return redirect(url_for("manage_exams"))
    rows = db.execute("SELECT e.*, COUNT(q.id) AS total_questions, COALESCE(SUM(q.marks), 0) AS total_marks FROM exams e LEFT JOIN questions q ON q.exam_id = e.id GROUP BY e.id ORDER BY e.created_at DESC").fetchall()
    db.close()
    return render_template("manage_exams.html", exams=rows, edit_exam=None)


@app.route("/admin/exams/<int:exam_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_exam(exam_id):
    db = get_db()
    if request.method == "POST":
        try:
            values = form_exam_values(request.form)
            db.execute("UPDATE exams SET title = ?, description = ?, subject = ?, duration = ?, pass_percentage = ?, published = ? WHERE id = ?", (*values, int(request.form.get("published") == "1"), exam_id))
            db.commit()
            flash("Examination updated.", "success")
            db.close()
            return redirect(url_for("manage_exams"))
        except ValueError as error:
            flash(str(error), "danger")
    exam = db.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    rows = db.execute("SELECT e.*, COUNT(q.id) AS total_questions, COALESCE(SUM(q.marks), 0) AS total_marks FROM exams e LEFT JOIN questions q ON q.exam_id = e.id GROUP BY e.id ORDER BY e.created_at DESC").fetchall()
    db.close()
    if not exam:
        flash("Examination not found.", "danger")
        return redirect(url_for("manage_exams"))
    return render_template("manage_exams.html", exams=rows, edit_exam=exam)


@app.post("/admin/exams/<int:exam_id>/delete")
@admin_required
def delete_exam(exam_id):
    db = get_db()
    db.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
    db.commit()
    db.close()
    flash("Examination deleted.", "success")
    return redirect(url_for("manage_exams"))


@app.post("/admin/exams/<int:exam_id>/toggle")
@admin_required
def toggle_exam(exam_id):
    db = get_db()
    db.execute("UPDATE exams SET published = CASE published WHEN 1 THEN 0 ELSE 1 END WHERE id = ?", (exam_id,))
    db.commit()
    db.close()
    return redirect(url_for("manage_exams"))


@app.route("/admin/exams/<int:exam_id>/questions", methods=["GET", "POST"])
@admin_required
def manage_questions(exam_id):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    if not exam:
        db.close()
        flash("Examination not found.", "danger")
        return redirect(url_for("manage_exams"))
    if request.method == "POST":
        fields = [request.form.get(key, "").strip() for key in ["question_text", "option_a", "option_b", "option_c", "option_d", "correct_answer"]]
        try:
            marks = float(request.form.get("marks", "1"))
        except ValueError:
            marks = 0
        if not all(fields) or fields[5] not in "ABCD" or marks <= 0:
            flash("Complete every question field and choose a valid answer.", "danger")
        else:
            db.execute("INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_answer, marks) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (exam_id, *fields, marks))
            db.commit()
            flash("Question added.", "success")
        db.close()
        return redirect(url_for("manage_questions", exam_id=exam_id))
    questions = db.execute("SELECT * FROM questions WHERE exam_id = ? ORDER BY id", (exam_id,)).fetchall()
    db.close()
    return render_template("manage_questions.html", exam=exam, questions=questions, edit_question=None)


@app.route("/admin/questions/<int:question_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_question(question_id):
    db = get_db()
    question = db.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    if not question:
        db.close()
        flash("Question not found.", "danger")
        return redirect(url_for("manage_exams"))
    if request.method == "POST":
        fields = [request.form.get(key, "").strip() for key in ["question_text", "option_a", "option_b", "option_c", "option_d", "correct_answer"]]
        try:
            marks = float(request.form.get("marks", "1"))
        except ValueError:
            marks = 0
        if not all(fields) or fields[5] not in "ABCD" or marks <= 0:
            flash("Complete every question field and choose a valid answer.", "danger")
        else:
            db.execute("UPDATE questions SET question_text = ?, option_a = ?, option_b = ?, option_c = ?, option_d = ?, correct_answer = ?, marks = ? WHERE id = ?", (*fields, marks, question_id))
            db.commit()
            flash("Question updated.", "success")
            db.close()
            return redirect(url_for("manage_questions", exam_id=question["exam_id"]))
    exam = db.execute("SELECT * FROM exams WHERE id = ?", (question["exam_id"],)).fetchone()
    questions = db.execute("SELECT * FROM questions WHERE exam_id = ? ORDER BY id", (question["exam_id"],)).fetchall()
    db.close()
    return render_template("manage_questions.html", exam=exam, questions=questions, edit_question=question)


@app.post("/admin/questions/<int:question_id>/delete")
@admin_required
def delete_question(question_id):
    db = get_db()
    question = db.execute("SELECT exam_id FROM questions WHERE id = ?", (question_id,)).fetchone()
    if question:
        db.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        db.commit()
    db.close()
    flash("Question deleted.", "success")
    return redirect(url_for("manage_questions", exam_id=question["exam_id"]) if question else url_for("manage_exams"))


@app.route("/admin/users")
@admin_required
def users():
    db = get_db()
    rows = db.execute("SELECT u.*, COUNT(r.id) AS attempts FROM users u LEFT JOIN results r ON r.user_id = u.id AND r.submitted_at IS NOT NULL WHERE u.role = 'student' GROUP BY u.id ORDER BY u.created_at DESC").fetchall()
    db.close()
    return render_template("users.html", users=rows)


@app.route("/admin/results")
@admin_required
def admin_results():
    db = get_db()
    rows = db.execute("SELECT r.*, e.title, e.subject, u.name AS student_name, u.email FROM results r JOIN exams e ON e.id = r.exam_id JOIN users u ON u.id = r.user_id WHERE r.submitted_at IS NOT NULL ORDER BY r.submitted_at DESC").fetchall()
    db.close()
    return render_template("results.html", results=rows, admin_view=True)


@app.route("/admin/statistics")
@admin_required
def statistics():
    db = get_db()
    rows = db.execute("SELECT e.title, COUNT(r.id) AS attempts, COALESCE(AVG(r.percentage), 0) AS average_percentage, COALESCE(SUM(r.passed), 0) AS passes FROM exams e LEFT JOIN results r ON r.exam_id = e.id AND r.submitted_at IS NOT NULL GROUP BY e.id ORDER BY attempts DESC").fetchall()
    db.close()
    return render_template("admin_dashboard.html", stats=None, recent=[], statistics=rows)


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)

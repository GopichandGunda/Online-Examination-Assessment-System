# Online Examination & Assessment System

A beginner-friendly full-stack examination platform built with Flask, SQLite, HTML5, CSS3, and vanilla JavaScript. Administrators can publish timed MCQ examinations, while students can take exams, submit answers, and review detailed results.

## Features

### Student module
- Student registration and secure password-hashed login.
- Dashboard with published examinations and recent results.
- Examination instructions, one-question-at-a-time MCQ experience, previous/next controls, question navigator, and countdown timer.
- Automatic submission when time expires and manual submission confirmation.
- One completed attempt per student and examination.
- Result breakdown for attempted, correct, incorrect, unanswered, marks, percentage, and pass/fail status.
- Result history.

### Admin module
- Separate role-protected administrator workspace.
- Create, edit, delete, publish, and unpublish examinations.
- Add, edit, and delete four-option questions with answer keys and marks.
- Browse registered students and student results.
- Examination statistics with attempts, average percentage, and passes.

## Technologies used

- **Frontend:** HTML5, CSS3, vanilla JavaScript, Fetch API
- **Backend:** Python 3, Flask
- **Database:** SQLite with Python's built-in `sqlite3` module
- **Authentication:** Flask sessions and Werkzeug password hashing

## System architecture

The application uses a simple server-rendered architecture:

1. Flask serves the HTML templates and static assets.
2. Jinja templates render dashboards, forms, tables, and the examination shell.
3. Vanilla JavaScript calls REST-style JSON endpoints to load exam questions and submit answers.
4. SQLite stores users, exams, questions, results, and answers.
5. Role-aware decorators protect authenticated student and administrator routes.

## Project structure

```text
Online-Examination-Assessment-System/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── database/
│   ├── .gitkeep
│   └── database.db          # generated automatically on first run
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── student_dashboard.html
│   ├── admin_dashboard.html
│   ├── exams.html
│   ├── exam.html
│   ├── result.html
│   ├── results.html
│   ├── manage_exams.html
│   ├── manage_questions.html
│   └── users.html
├── static/
│   ├── css/style.css
│   └── js/{main.js,exam.js}
└── screenshots/
```

## Database design

- **users:** account identity, hashed password, role, and creation date.
- **exams:** title, description, subject, duration, pass percentage, and publish state.
- **questions:** four options, correct answer, marks, and parent examination.
- **results:** one attempt per student/examination, timing, score totals, percentage, and pass state.
- **answers:** selected answer and correctness for each question in an attempt.

Foreign keys are enabled and deleting an examination cascades to its questions. Results and answers remain consistent through SQLite constraints.

## Installation

Python 3.10 or newer is recommended.

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The database directory is included in the repository and `database.db` is created and seeded automatically when `app.py` starts.

## How to run

```bash
python app.py
```

Open <http://127.0.0.1:5000> in your browser. For production-style local use, set a strong `SECRET_KEY` environment variable before starting the app.

## Sample login credentials

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@example.com` | `Admin@123` |
| Student | `student@example.com` | `Student@123` |

A published **Python Fundamentals Assessment** with five sample questions is seeded on first run.

## Screenshots

Place captured application screenshots in the `screenshots/` directory and reference them here, for example:

```md
![Student dashboard](screenshots/student-dashboard.png)
![Admin dashboard](screenshots/admin-dashboard.png)
![Exam experience](screenshots/exam.png)
```

The directory is intentionally ready for screenshots without adding generated binaries to the source tree.

## Future enhancements

- Email verification and password reset.
- Question banks with randomization and negative marking.
- CSV/PDF result exports.
- CSRF tokens and a production WSGI deployment configuration.
- More detailed answer review and topic-level analytics.
- Optional PostgreSQL support for larger installations.

## Author

**Gopichand Gunda**

Repository: [GopichandGunda/Online-Examination-Assessment-System](https://github.com/GopichandGunda/Online-Examination-Assessment-System)

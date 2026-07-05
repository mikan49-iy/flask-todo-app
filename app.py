import os

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import case
from datetime import date, datetime

from extensions import db, migrate
from models import User, Task

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
migrate.init_app(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "ログインが必要です"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("tasks"))
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password1 = request.form.get("password1", "")
        password2 = request.form.get("password2", "")

        form_data = {
            "email": email,
        }

        if not email or not password1 or not password2:
            flash("すべての項目を入力してください")
            return render_template(
                "register.html",
                form_data=form_data,
            )

        if len(email) > 255:
            flash("メールアドレスは255文字以下で入力してください")
            return render_template(
                "register.html",
                form_data=form_data,
            )

        if not (8 <= len(password1) <= 72):
            flash("パスワードは8文字以上72文字以下で入力してください")
            return render_template(
                "register.html",
                form_data=form_data,
            )

        if password1 != password2:
            flash("パスワードが一致していません")
            return render_template(
                "register.html",
                form_data=form_data,
            )

        if db.session.execute(
            db.select(User).filter_by(email=email)
        ).scalar_one_or_none():

            flash("このメールアドレスは既に使用されています")
            return render_template(
                "register.html",
                form_data=form_data,
            )
        
        password_hash = generate_password_hash(password1)
            
        user = User(
            email=email,
            password_hash=password_hash,
        )
            
        db.session.add(user)
        db.session.commit()

        login_user(user)

        return redirect(url_for("tasks"))

    return render_template(
        "register.html",
        form_data={
            "email": "",
        },
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("すべての項目を入力してください")
            return render_template("login.html")
        
        user = db.session.execute(
            db.select(User).filter_by(email=email)
        ).scalar_one_or_none()

        if not user or not check_password_hash(
            user.password_hash, password):

            flash("メールアドレスまたはパスワードが正しくありません")
            return render_template("login.html")
        
        login_user(user)

        return redirect(url_for("tasks"))

    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/tasks", methods=["GET"])
@login_required
def tasks():

    priority_sort_order = case(
        (Task.priority == "high", 1),
        (Task.priority == "medium", 2),
        (Task.priority == "low", 3),
        else_=4,
    )

    incomplete_tasks_query = (
        db.select(Task)
        .where(
            Task.user_id == current_user.id,
            Task.is_done.is_(False),
        ).order_by(
            Task.due_date.is_(None),
            Task.due_date.asc(),
            priority_sort_order.asc(),
            Task.updated_at.asc()
        )
    )

    incomplete_tasks = db.session.execute(
        incomplete_tasks_query
    ).scalars().all()

    completed_tasks_query = (
        db.select(Task)
        .where(
            Task.user_id == current_user.id,
            Task.is_done.is_(True),
        ).order_by(
            Task.completed_at.desc()
        )
    )
    
    completed_tasks = db.session.execute(
        completed_tasks_query
    ).scalars().all()

    return render_template(
        "tasks.html",
        incomplete_tasks=incomplete_tasks,
        today=date.today(),
        completed_tasks=completed_tasks
    )

@app.route("/tasks/new", methods=["GET", "POST"])
@login_required
def task_create():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date")
        priority = request.form.get("priority", "medium")

        form_data = {
            "title": title,
            "description": description,
            "due_date": due_date,
            "priority": priority,
        }

        if not (1 <= len(title) <= 100):
            flash("タイトルは1文字以上100文字以下で入力してください")
            return render_template(
                "task_create.html",
                form_data=form_data,
            )

        if len(description) > 1000:
            flash("メモは1000文字以下で入力してください")
            return render_template(
                "task_create.html",
                form_data=form_data,
            )

        if description == "":
            description = None        

        if due_date == "":
            due_date = None

        task = Task(
            user_id=current_user.id,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
        )

        db.session.add(task)
        db.session.commit()

        return redirect(url_for("tasks"))

    return render_template(
        "task_create.html",
        form_data={
            "title": "",
            "description": "",
            "due_date": "",
            "priority": "medium",
        },   
    )

@app.route("/tasks/<int:id>/edit", methods=["GET", "POST"])
@login_required
def task_edit(id):
    task = db.session.execute(
        db.select(Task).where(
            Task.user_id == current_user.id,
            Task.id == id,
        )
    ).scalar_one_or_none()

    if task is None:
        return redirect(url_for("tasks"))

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date")
        priority = request.form.get("priority", "medium")

        form_data = {
            "title": title,
            "description": description,
            "due_date": due_date,
            "priority": priority,
        }

        if not (1 <= len(title) <= 100):
            flash("タイトルは1文字以上100文字以下で入力してください")
            return render_template(
                "task_edit.html",
                task=task,
                form_data=form_data,
            )
        
        if len(description) > 1000:
            flash("メモは1000文字以下で入力してください")
            return render_template(
                "task_edit.html",
                task=task,
                form_data=form_data,
            )

        if description == "":
            description = None

        if due_date == "":
            due_date = None

        task.title = title
        task.description = description
        task.due_date = due_date
        task.priority = priority

        db.session.commit()

        return redirect(url_for("tasks"))

    form_data = {
        "title": task.title,
        "description": task.description or "",
        "due_date": task.due_date or "",
        "priority": task.priority,
    }

    return render_template(
        "task_edit.html",
        task=task,
        form_data=form_data,
    )

@app.route("/tasks/<int:id>/complete", methods=["POST"])
@login_required
def task_complete(id):
    task = db.session.execute(
        db.select(Task).where(
            Task.user_id == current_user.id,
            Task.id == id,
        )
    ).scalar_one_or_none()

    if task is None:
        return redirect(url_for("tasks"))
    
    task.is_done = True
    task.completed_at = datetime.now()

    db.session.commit()

    return redirect(url_for("tasks"))


@app.route("/tasks/<int:id>/incomplete", methods=["POST"])
@login_required
def task_incomplete(id):
    task = db.session.execute(
        db.select(Task).where(
            Task.user_id == current_user.id,
            Task.id == id,
        )
    ).scalar_one_or_none()

    if task is None:
        return redirect(url_for("tasks"))
    
    task.is_done = False
    task.completed_at = None

    db.session.commit()

    return redirect(url_for("tasks"))
    
@app.route("/tasks/<int:id>/delete", methods=["POST"])
@login_required
def task_delete(id):
    task = db.session.execute(
        db.select(Task).where(
            Task.user_id == current_user.id,
            Task.id == id,
        )
    ).scalar_one_or_none()

    if task is None:
        return redirect(url_for("tasks"))
    
    db.session.delete(task)
    db.session.commit()

    return redirect(url_for("tasks"))
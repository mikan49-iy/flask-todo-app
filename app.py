import os

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, url_for, request
from flask_login import LoginManager, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, migrate
import models
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
    return User.query.get(int(user_id))

@app.route("/")
def index():
    return "Hello ToDo App"

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password1 = request.form.get("password1", "")
        password2 = request.form.get("password2", "")

        if not email or not password1 or not password2:
            error = "すべての項目を入力してください"
            return render_template("register.html", error = error)

        elif User.query.filter_by(email = email).first():
            error = "このメールアドレスは既に使用されています"
            return render_template("register.html", error = error)
        
        elif password1 != password2:
            error = "パスワードが一致していません"
            return render_template("register.html", error = error)

        else:
            password_hash = generate_password_hash(password1)
            
            user = User(email = email,
                        password_hash = password_hash)
            
            db.session.add(user)
            db.session.commit()

            login_user(user)

            return redirect(url_for("tasks"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            error = "すべての項目を入力してください"
            return render_template("login.html", error = error)
        
        user = User.query.filter_by(email = email).first()

        if not user or not check_password_hash(user.password_hash, password):
            error = "メールアドレスまたはパスワードが正しくありません"
            return render_template("login.html", error = error)
        
        login_user(user)

        return redirect(url_for("tasks"))

    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/tasks")
@login_required
def tasks():
    return render_template("tasks.html")
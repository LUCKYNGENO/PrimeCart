from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db

auth = Blueprint("auth", __name__)
@auth.route("/login", methods=["GET", "POST"])
def login():

    if admin_required():
        return redirect(url_for("admin"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template(
                "login.html",
                error="Please fill in all fields."
            )

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM admins WHERE username=%s",
            (username,)
        )

        admin = cur.fetchone()

        cur.close()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin"] = admin["id"]
            session["username"] = admin["username"]

            flash(
                "Welcome back, " + admin["username"] + "!",
                "success"
            )

            return redirect(url_for("admin"))

        return render_template(
            "login.html",
            error="Invalid username or password."
        )

    return render_template("login.html")
"""Demo vulnerable Flask app — used only for README screenshots."""
import os
import sqlite3
from flask import Flask, request, render_template_string

app = Flask(__name__)
app.config["SECRET_KEY"] = "hardcoded-secret-key-123456"  # intentionally weak

DB = os.path.join(os.path.dirname(__file__), "demo.db")


def get_conn():
    return sqlite3.connect(DB)


@app.route("/")
def index():
    q = request.args.get("q", "")
    # SQL injection: string formatting directly into the query
    cur = get_conn().execute(f"SELECT * FROM users WHERE name LIKE '%{q}%'")
    rows = cur.fetchall()
    return render_template_string(
        "<h1>Search</h1><form><input name=q value='{{ q }}'></form>"
        "<ul>{% for r in rows %}<li>{{ r[1] }}</li>{% endfor %}</ul>",
        q=q, rows=rows,
    )


@app.route("/login", methods=["POST"])
def login():
    user = request.form.get("user")
    pwd = request.form.get("pwd")
    # SQL injection in authentication
    cur = get_conn().execute(
        f"SELECT * FROM users WHERE user='{user}' AND pwd='{pwd}'"
    )
    if cur.fetchone():
        return "Welcome admin"
    return "Login failed", 401


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

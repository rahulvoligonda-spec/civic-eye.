"""Civic Eye - Flask backend (Python + SQLite)

Run:  pip install flask
      python app.py
Open: http://127.0.0.1:5000
"""
import base64
import hmac
import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "civic-eye-dev-secret-change-me")

# Admin login. Change these before showing it to anyone outside class:
#   set ADMIN_USER=...   and   set ADMIN_PASS=...   (or edit the two lines below)
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "civiceye.db")
UPLOADS = os.path.join(BASE, "static", "uploads")
os.makedirs(UPLOADS, exist_ok=True)

# BMC departments the admin can send a report to
DEPARTMENTS = [
    "Roads & Traffic Department",
    "Solid Waste Management Department",
    "Hydraulic Engineer Department",
    "Storm Water Drains Department",
    "Street Lighting (Electrical) Department",
    "Licence & Encroachment Department",
    "Veterinary Health Department",
    "Public Health Department",
]
STATUSES = ("Pending", "In progress", "Resolved")


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS reports(
                 no INTEGER PRIMARY KEY AUTOINCREMENT,
                 id TEXT, name TEXT, phone TEXT, cat TEXT, dept TEXT,
                 ward TEXT, descr TEXT, addr TEXT, coords TEXT,
                 photo TEXT, status TEXT, date TEXT)"""
        )


def row_to_dict(r):
    d = dict(r)
    d["desc"] = d.pop("descr")
    return d


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/reports", methods=["POST"])
def create_report():
    """Citizen sends only a photo and a location. The admin picks the department later."""
    data = request.get_json(silent=True) or {}
    photo = data.get("photo", "")
    addr = str(data.get("addr", "")).strip()
    if not addr:
        return jsonify(error="Please add the location."), 400
    if not photo.startswith("data:image/jpeg;base64,") or len(photo) > 3_000_000:
        return jsonify(error="Invalid or too large photo."), 400

    # save the photo as a file and keep only its path in the database
    filename = uuid.uuid4().hex + ".jpg"
    with open(os.path.join(UPLOADS, filename), "wb") as f:
        f.write(base64.b64decode(photo.split(",", 1)[1]))

    with db() as con:
        cur = con.execute(
            """INSERT INTO reports(name,phone,cat,dept,ward,descr,addr,coords,photo,status,date)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            ("", "", "", "", "", "", addr[:300], str(data.get("coords", ""))[:60],
             "/static/uploads/" + filename, "Pending",
             datetime.now().strftime("%d/%m/%Y, %I:%M %p")),
        )
        rid = "CE-%d" % (1000 + cur.lastrowid)
        con.execute("UPDATE reports SET id=? WHERE no=?", (rid, cur.lastrowid))
    return jsonify(id=rid), 201


def admin_required(view):
    """Only logged-in admins can use the admin page and admin API."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            if request.path.startswith("/api/"):
                return jsonify(error="Login required."), 401
            return redirect("/admin/login")
        return view(*args, **kwargs)
    return wrapper


# ---------- public API (citizens) ----------
@app.route("/api/reports")
def track_report():
    """Citizens can look up ONE report by its ID. Name and phone are never returned."""
    rid = request.args.get("id", "").strip()
    if not rid:
        return jsonify([])
    with db() as con:
        rows = con.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchall()
    out = []
    for r in rows:
        d = row_to_dict(r)
        d.pop("phone", None)
        d.pop("name", None)
        out.append(d)
    return jsonify(out)


@app.route("/api/stats")
def stats():
    with db() as con:
        rows = [r["status"] for r in con.execute("SELECT status FROM reports")]
    return jsonify(total=len(rows), open=sum(s != "Resolved" for s in rows),
                   resolved=rows.count("Resolved"))


# ---------- admin pages ----------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        ok_user = hmac.compare_digest(u.encode(), ADMIN_USER.encode())
        ok_pass = hmac.compare_digest(p.encode(), ADMIN_PASS.encode())
        if ok_user and ok_pass:
            session["admin"] = True
            return redirect("/admin")
        error = "Wrong username or password."
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin/login")


@app.route("/admin")
@admin_required
def admin_home():
    return render_template("admin.html", depts=DEPARTMENTS)


# ---------- admin API ----------
@app.route("/api/admin/reports")
@admin_required
def admin_reports():
    sql, args, where = "SELECT * FROM reports", [], []
    if request.args.get("dept") == "__none__":
        where.append("dept=''")
    elif request.args.get("dept"):
        where.append("dept=?"); args.append(request.args["dept"])
    if request.args.get("status"):
        where.append("status=?"); args.append(request.args["status"])
    q = request.args.get("q", "").strip()
    if q:
        where.append("(id LIKE ? OR name LIKE ? OR phone LIKE ? OR addr LIKE ? OR descr LIKE ?)")
        args += ["%" + q + "%"] * 5
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY no DESC"
    with db() as con:
        return jsonify([row_to_dict(r) for r in con.execute(sql, args)])


@app.route("/api/admin/stats")
@admin_required
def admin_stats():
    with db() as con:
        rows = con.execute("SELECT dept, status FROM reports").fetchall()
    by_dept = {}
    for r in rows:
        by_dept[r["dept"] or "Not assigned"] = by_dept.get(r["dept"] or "Not assigned", 0) + 1
    st = [r["status"] for r in rows]
    return jsonify(total=len(st), unassigned=sum(1 for r in rows if not r["dept"]), pending=st.count("Pending"),
                   progress=st.count("In progress"), resolved=st.count("Resolved"),
                   by_dept=by_dept)


@app.route("/api/admin/reports/<rid>/status", methods=["POST"])
@admin_required
def admin_set_status(rid):
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in STATUSES:
        return jsonify(error="Invalid status."), 400
    with db() as con:
        con.execute("UPDATE reports SET status=? WHERE id=?", (status, rid))
    return jsonify(ok=True)


@app.route("/api/admin/reports/<rid>/department", methods=["POST"])
@admin_required
def admin_set_department(rid):
    dept = (request.get_json(silent=True) or {}).get("dept", "")
    if dept != "" and dept not in DEPARTMENTS:
        return jsonify(error="Unknown department."), 400
    with db() as con:
        con.execute("UPDATE reports SET dept=? WHERE id=?", (dept, rid))
    return jsonify(ok=True)


@app.route("/api/admin/reports/<rid>", methods=["DELETE"])
@admin_required
def admin_delete(rid):
    with db() as con:
        row = con.execute("SELECT photo FROM reports WHERE id=?", (rid,)).fetchone()
        con.execute("DELETE FROM reports WHERE id=?", (rid,))
    if row and row["photo"]:
        path = os.path.join(UPLOADS, os.path.basename(row["photo"]))
        if os.path.exists(path):
            os.remove(path)
    return jsonify(ok=True)


init_db()
if __name__ == "__main__":
    app.run(debug=True)

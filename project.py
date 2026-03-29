"""
Real-Time Reimbursement Management System
==========================================
Full-stack Python/Flask application with SQLite database.
Covers: Travel, Medical, Food, Fuel, Equipment, Training, Miscellaneous
"""

from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import json
import os
import io
import csv
from datetime import datetime, timedelta
import random
import string

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "reimbursement.db")


# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # Employees table
    c.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id      TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            department  TEXT NOT NULL,
            designation TEXT NOT NULL,
            manager     TEXT,
            budget_limit REAL DEFAULT 50000.0,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # Reimbursement requests table
    c.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_no          TEXT UNIQUE NOT NULL,
            emp_id          TEXT NOT NULL,
            emp_name        TEXT NOT NULL,
            department      TEXT NOT NULL,
            category        TEXT NOT NULL,
            subcategory     TEXT,
            amount          REAL NOT NULL,
            currency        TEXT DEFAULT 'INR',
            expense_date    TEXT NOT NULL,
            description     TEXT NOT NULL,
            receipt_info    TEXT,
            status          TEXT DEFAULT 'Pending',
            priority        TEXT DEFAULT 'Normal',
            submitted_at    TEXT DEFAULT (datetime('now')),
            reviewed_by     TEXT,
            reviewed_at     TEXT,
            approved_amount REAL,
            rejection_reason TEXT,
            payment_status  TEXT DEFAULT 'Unpaid',
            paid_at         TEXT,
            notes           TEXT,
            FOREIGN KEY(emp_id) REFERENCES employees(emp_id)
        )
    """)

    # Audit log table
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_no      TEXT,
            action      TEXT NOT NULL,
            performed_by TEXT NOT NULL,
            details     TEXT,
            timestamp   TEXT DEFAULT (datetime('now'))
        )
    """)

    # Budget table
    c.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            department  TEXT NOT NULL,
            category    TEXT NOT NULL,
            fiscal_year INTEGER NOT NULL,
            allocated   REAL NOT NULL,
            utilized    REAL DEFAULT 0.0,
            UNIQUE(department, category, fiscal_year)
        )
    """)

    # Policies table
    c.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category    TEXT UNIQUE NOT NULL,
            max_per_claim REAL,
            max_monthly REAL,
            requires_receipt_above REAL DEFAULT 500,
            description TEXT,
            active      INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    _seed_data(conn)
    conn.close()


def _seed_data(conn):
    c = conn.cursor()

    # Check if already seeded
    c.execute("SELECT COUNT(*) FROM employees")
    if c.fetchone()[0] > 0:
        return

    # Employees
    employees = [
        ("EMP001", "Arjun Mehta",    "arjun@company.com",   "Engineering",  "Senior Engineer",    "MGR001", 60000),
        ("EMP002", "Priya Sharma",   "priya@company.com",   "Marketing",    "Marketing Manager",  "MGR002", 55000),
        ("EMP003", "Ravi Kumar",     "ravi@company.com",    "Sales",        "Sales Executive",    "MGR003", 40000),
        ("EMP004", "Neha Patel",     "neha@company.com",    "HR",           "HR Specialist",      "MGR002", 35000),
        ("EMP005", "Amit Singh",     "amit@company.com",    "Finance",      "Finance Analyst",    "MGR001", 45000),
        ("EMP006", "Sunita Rao",     "sunita@company.com",  "Operations",   "Ops Lead",           "MGR003", 50000),
        ("MGR001", "Vikram Desai",   "vikram@company.com",  "Engineering",  "Engineering Head",   None,     100000),
        ("MGR002", "Kavita Nair",    "kavita@company.com",  "Marketing",    "Marketing Director", None,     100000),
        ("MGR003", "Rajesh Iyer",    "rajesh@company.com",  "Sales",        "VP Sales",           None,     100000),
    ]
    c.executemany("""
        INSERT OR IGNORE INTO employees (emp_id,name,email,department,designation,manager,budget_limit)
        VALUES (?,?,?,?,?,?,?)
    """, employees)

    # Policies
    policies = [
        ("Travel",        15000, 50000, 500,  "Flight, train, bus, cab reimbursements"),
        ("Medical",       10000, 30000, 200,  "Doctor visits, medicines, lab tests"),
        ("Food & Meals",  3000,  8000,  300,  "Business meals and client entertainment"),
        ("Fuel",          5000,  15000, 200,  "Fuel for official vehicle use"),
        ("Equipment",     20000, 50000, 1000, "Laptops, peripherals, office supplies"),
        ("Training",      25000, 60000, 500,  "Courses, certifications, conferences"),
        ("Accommodation", 8000,  25000, 500,  "Hotel stays during business trips"),
        ("Communication", 2000,  5000,  100,  "Phone bills, internet reimbursements"),
        ("Miscellaneous", 5000,  10000, 300,  "Other valid business expenses"),
    ]
    c.executemany("""
        INSERT OR IGNORE INTO policies (category, max_per_claim, max_monthly, requires_receipt_above, description)
        VALUES (?,?,?,?,?)
    """, policies)

    # Budgets for current year
    year = datetime.now().year
    departments = ["Engineering", "Marketing", "Sales", "HR", "Finance", "Operations"]
    categories  = ["Travel", "Medical", "Food & Meals", "Equipment", "Training", "Miscellaneous"]
    for dept in departments:
        for cat in categories:
            allocated = random.uniform(20000, 100000)
            utilized  = random.uniform(0, allocated * 0.7)
            c.execute("""
                INSERT OR IGNORE INTO budgets (department, category, fiscal_year, allocated, utilized)
                VALUES (?,?,?,?,?)
            """, (dept, cat, year, round(allocated, 2), round(utilized, 2)))

    # Sample requests
    statuses     = ["Pending", "Approved", "Rejected", "Under Review"]
    categories_l = ["Travel", "Medical", "Food & Meals", "Fuel", "Equipment", "Training", "Accommodation", "Communication", "Miscellaneous"]
    priorities   = ["Low", "Normal", "High", "Urgent"]
    emps         = [("EMP001","Arjun Mehta","Engineering"), ("EMP002","Priya Sharma","Marketing"),
                    ("EMP003","Ravi Kumar","Sales"), ("EMP004","Neha Patel","HR"),
                    ("EMP005","Amit Singh","Finance"), ("EMP006","Sunita Rao","Operations")]

    for i in range(1, 31):
        emp      = random.choice(emps)
        cat      = random.choice(categories_l)
        status   = random.choice(statuses)
        days_ago = random.randint(1, 90)
        exp_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        amount   = round(random.uniform(500, 15000), 2)
        ref      = f"REF{2024000 + i}"
        approved = amount if status == "Approved" else (round(amount * 0.9, 2) if status == "Approved" else None)
        pay_stat = "Paid" if status == "Approved" and random.random() > 0.4 else "Unpaid"

        c.execute("""
            INSERT OR IGNORE INTO requests
            (ref_no, emp_id, emp_name, department, category, amount, expense_date, description,
             status, priority, approved_amount, payment_status, submitted_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now', ?))
        """, (ref, emp[0], emp[1], emp[2], cat, amount, exp_date,
              f"{cat} expense for business purpose - {exp_date}",
              status, random.choice(priorities), approved, pay_stat,
              f"-{days_ago} days"))

    conn.commit()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def gen_ref():
    return "REF" + datetime.now().strftime("%Y%m%d") + ''.join(random.choices(string.digits, k=4))


def log_audit(ref_no, action, performed_by, details=""):
    conn = get_db()
    conn.execute("INSERT INTO audit_log (ref_no, action, performed_by, details) VALUES (?,?,?,?)",
                 (ref_no, action, performed_by, details))
    conn.commit()
    conn.close()


def rows_to_list(rows):
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# ROUTES – PAGES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ─────────────────────────────────────────────
# API – DASHBOARD
# ─────────────────────────────────────────────

@app.route("/api/dashboard")
def api_dashboard():
    conn  = get_db()
    c     = conn.cursor()
    year  = datetime.now().year
    month = datetime.now().month

    # Totals
    c.execute("SELECT COUNT(*) FROM requests")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM requests WHERE status='Pending'")
    pending = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM requests WHERE status='Approved'")
    approved = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM requests WHERE status='Rejected'")
    rejected = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(approved_amount),0) FROM requests WHERE status='Approved'")
    total_approved_amt = round(c.fetchone()[0], 2)
    c.execute("SELECT COALESCE(SUM(approved_amount),0) FROM requests WHERE status='Approved' AND payment_status='Unpaid'")
    pending_payout = round(c.fetchone()[0], 2)
    c.execute("SELECT COUNT(*) FROM requests WHERE status='Approved' AND payment_status='Unpaid'")
    pending_payout_count = c.fetchone()[0]

    # Monthly trend (last 6 months)
    trend = []
    for i in range(5, -1, -1):
        d   = datetime.now() - timedelta(days=30 * i)
        mon = d.strftime("%Y-%m")
        c.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM requests WHERE strftime('%Y-%m', submitted_at)=?", (mon,))
        row = c.fetchone()
        trend.append({"month": d.strftime("%b %Y"), "count": row[0], "amount": round(row[1], 2)})

    # Category breakdown
    c.execute("SELECT category, COUNT(*) as cnt, COALESCE(SUM(amount),0) as total FROM requests GROUP BY category ORDER BY total DESC")
    cat_data = rows_to_list(c.fetchall())

    # Status breakdown
    c.execute("SELECT status, COUNT(*) as cnt FROM requests GROUP BY status")
    status_data = rows_to_list(c.fetchall())

    # Department breakdown
    c.execute("SELECT department, COUNT(*) as cnt, COALESCE(SUM(amount),0) as total FROM requests GROUP BY department ORDER BY total DESC")
    dept_data = rows_to_list(c.fetchall())

    # Recent requests
    c.execute("SELECT * FROM requests ORDER BY submitted_at DESC LIMIT 10")
    recent = rows_to_list(c.fetchall())

    # Budget overview
    c.execute("SELECT department, SUM(allocated) as alloc, SUM(utilized) as util FROM budgets WHERE fiscal_year=? GROUP BY department", (year,))
    budget_dept = rows_to_list(c.fetchall())

    conn.close()
    return jsonify({
        "stats": {
            "total": total, "pending": pending, "approved": approved,
            "rejected": rejected, "total_approved_amt": total_approved_amt,
            "pending_payout": pending_payout, "pending_payout_count": pending_payout_count
        },
        "trend": trend,
        "category_breakdown": cat_data,
        "status_breakdown": status_data,
        "department_breakdown": dept_data,
        "recent_requests": recent,
        "budget_overview": budget_dept
    })


# ─────────────────────────────────────────────
# API – REQUESTS CRUD
# ─────────────────────────────────────────────

@app.route("/api/requests", methods=["GET"])
def get_requests():
    status     = request.args.get("status", "")
    category   = request.args.get("category", "")
    department = request.args.get("department", "")
    emp_id     = request.args.get("emp_id", "")
    search     = request.args.get("search", "")
    page       = int(request.args.get("page", 1))
    per_page   = int(request.args.get("per_page", 20))
    offset     = (page - 1) * per_page

    filters, params = [], []
    if status:     filters.append("status=?");     params.append(status)
    if category:   filters.append("category=?");   params.append(category)
    if department: filters.append("department=?"); params.append(department)
    if emp_id:     filters.append("emp_id=?");     params.append(emp_id)
    if search:
        filters.append("(emp_name LIKE ? OR ref_no LIKE ? OR description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    conn = get_db()
    c    = conn.cursor()
    c.execute(f"SELECT COUNT(*) FROM requests {where}", params)
    total = c.fetchone()[0]
    c.execute(f"SELECT * FROM requests {where} ORDER BY submitted_at DESC LIMIT ? OFFSET ?",
              params + [per_page, offset])
    rows = rows_to_list(c.fetchall())
    conn.close()
    return jsonify({"requests": rows, "total": total, "page": page, "per_page": per_page})


@app.route("/api/requests/<int:req_id>", methods=["GET"])
def get_request(req_id):
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM requests WHERE id=?", (req_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    c.execute("SELECT * FROM audit_log WHERE ref_no=? ORDER BY timestamp DESC", (row["ref_no"],))
    logs = rows_to_list(c.fetchall())
    conn.close()
    return jsonify({"request": dict(row), "audit_log": logs})


@app.route("/api/requests", methods=["POST"])
def create_request():
    data    = request.json
    ref_no  = gen_ref()
    conn    = get_db()
    c       = conn.cursor()

    # Fetch employee info
    c.execute("SELECT * FROM employees WHERE emp_id=?", (data["emp_id"],))
    emp = c.fetchone()
    if not emp:
        conn.close()
        return jsonify({"error": "Employee not found"}), 404

    # Policy check
    c.execute("SELECT * FROM policies WHERE category=? AND active=1", (data["category"],))
    policy = c.fetchone()
    warning = None
    if policy and data["amount"] > policy["max_per_claim"]:
        warning = f"Amount exceeds policy limit of ₹{policy['max_per_claim']:,.0f} for {data['category']}"

    c.execute("""
        INSERT INTO requests
        (ref_no, emp_id, emp_name, department, category, subcategory, amount,
         currency, expense_date, description, receipt_info, priority, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (ref_no, emp["emp_id"], emp["name"], emp["department"],
          data["category"], data.get("subcategory"), data["amount"],
          data.get("currency", "INR"), data["expense_date"],
          data["description"], data.get("receipt_info"),
          data.get("priority", "Normal"), data.get("notes")))

    conn.commit()
    log_audit(ref_no, "SUBMITTED", emp["name"], f"New request ₹{data['amount']} - {data['category']}")
    conn.close()
    return jsonify({"success": True, "ref_no": ref_no, "warning": warning})


@app.route("/api/requests/<int:req_id>/action", methods=["POST"])
def request_action(req_id):
    data   = request.json
    action = data.get("action")  # approve / reject / review / pay
    conn   = get_db()
    c      = conn.cursor()

    c.execute("SELECT * FROM requests WHERE id=?", (req_id,))
    req = c.fetchone()
    if not req:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    now = datetime.now().isoformat()

    reviewer = data.get("reviewer", "Admin")
    ref_no   = req["ref_no"]
    audit_msg = None

    if action == "approve":
        amt = data.get("approved_amount", req["amount"])
        c.execute("""UPDATE requests SET status='Approved', approved_amount=?,
                     reviewed_by=?, reviewed_at=? WHERE id=?""",
                  (amt, reviewer, now, req_id))
        c.execute("""UPDATE budgets SET utilized = utilized + ?
                     WHERE department=? AND category=? AND fiscal_year=?""",
                  (amt, req["department"], req["category"], datetime.now().year))
        c.execute("INSERT INTO audit_log (ref_no, action, performed_by, details) VALUES (?,?,?,?)",
                  (ref_no, "APPROVED", reviewer, f"Approved ₹{amt}"))

    elif action == "reject":
        c.execute("""UPDATE requests SET status='Rejected', rejection_reason=?,
                     reviewed_by=?, reviewed_at=? WHERE id=?""",
                  (data.get("reason",""), reviewer, now, req_id))
        c.execute("INSERT INTO audit_log (ref_no, action, performed_by, details) VALUES (?,?,?,?)",
                  (ref_no, "REJECTED", reviewer, data.get("reason","")))

    elif action == "review":
        c.execute("UPDATE requests SET status='Under Review', reviewed_by=?, reviewed_at=? WHERE id=?",
                  (reviewer, now, req_id))
        c.execute("INSERT INTO audit_log (ref_no, action, performed_by, details) VALUES (?,?,?,?)",
                  (ref_no, "UNDER REVIEW", reviewer, "Moved to review"))

    elif action == "pay":
        c.execute("UPDATE requests SET payment_status='Paid', paid_at=? WHERE id=? AND status='Approved'",
                  (now, req_id))
        c.execute("INSERT INTO audit_log (ref_no, action, performed_by, details) VALUES (?,?,?,?)",
                  (ref_no, "PAYMENT PROCESSED", reviewer, "Marked as paid"))

    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/requests/<int:req_id>", methods=["DELETE"])
def delete_request(req_id):
    conn = get_db()
    conn.execute("DELETE FROM requests WHERE id=? AND status='Pending'", (req_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ─────────────────────────────────────────────
# API – EMPLOYEES
# ─────────────────────────────────────────────

@app.route("/api/employees", methods=["GET"])
def get_employees():
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM employees ORDER BY name")
    rows = rows_to_list(c.fetchall())
    conn.close()
    return jsonify(rows)


@app.route("/api/employees", methods=["POST"])
def add_employee():
    data = request.json
    conn = get_db()
    emp_id = "EMP" + ''.join(random.choices(string.digits, k=4))
    conn.execute("""
        INSERT INTO employees (emp_id, name, email, department, designation, manager, budget_limit)
        VALUES (?,?,?,?,?,?,?)
    """, (emp_id, data["name"], data["email"], data["department"],
          data["designation"], data.get("manager"), data.get("budget_limit", 50000)))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "emp_id": emp_id})


@app.route("/api/employees/<emp_id>/summary", methods=["GET"])
def employee_summary(emp_id):
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM employees WHERE emp_id=?", (emp_id,))
    emp  = c.fetchone()
    if not emp:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    c.execute("SELECT status, COUNT(*) as cnt, COALESCE(SUM(amount),0) as total FROM requests WHERE emp_id=? GROUP BY status", (emp_id,))
    stats  = rows_to_list(c.fetchall())
    c.execute("SELECT * FROM requests WHERE emp_id=? ORDER BY submitted_at DESC LIMIT 10", (emp_id,))
    recent = rows_to_list(c.fetchall())
    conn.close()
    return jsonify({"employee": dict(emp), "stats": stats, "recent_requests": recent})


# ─────────────────────────────────────────────
# API – POLICIES & BUDGETS
# ─────────────────────────────────────────────

@app.route("/api/policies", methods=["GET"])
def get_policies():
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM policies ORDER BY category")
    rows = rows_to_list(c.fetchall())
    conn.close()
    return jsonify(rows)


@app.route("/api/policies/<int:pid>", methods=["PUT"])
def update_policy(pid):
    data = request.json
    conn = get_db()
    conn.execute("""UPDATE policies SET max_per_claim=?, max_monthly=?,
                    requires_receipt_above=?, description=? WHERE id=?""",
                 (data["max_per_claim"], data["max_monthly"],
                  data["requires_receipt_above"], data["description"], pid))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/budgets", methods=["GET"])
def get_budgets():
    year = request.args.get("year", datetime.now().year)
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT *, (allocated - utilized) as remaining FROM budgets WHERE fiscal_year=? ORDER BY department, category", (year,))
    rows = rows_to_list(c.fetchall())
    conn.close()
    return jsonify(rows)


# ─────────────────────────────────────────────
# API – REPORTS / EXPORT
# ─────────────────────────────────────────────

@app.route("/api/reports/summary")
def report_summary():
    conn = get_db()
    c    = conn.cursor()
    c.execute("""SELECT category, status, COUNT(*) as count,
                        COALESCE(SUM(amount),0) as requested,
                        COALESCE(SUM(approved_amount),0) as approved
                 FROM requests GROUP BY category, status ORDER BY category, status""")
    rows = rows_to_list(c.fetchall())
    conn.close()
    return jsonify(rows)


@app.route("/api/export/csv")
def export_csv():
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM requests ORDER BY submitted_at DESC")
    rows  = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ref No","Employee","Department","Category","Amount","Status",
                     "Expense Date","Submitted At","Approved Amount","Payment Status"])
    for r in rows:
        writer.writerow([r["ref_no"], r["emp_name"], r["department"], r["category"],
                         r["amount"], r["status"], r["expense_date"], r["submitted_at"],
                         r["approved_amount"] or "", r["payment_status"]])

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()),
                     mimetype="text/csv",
                     as_attachment=True,
                     download_name=f"reimbursements_{datetime.now().strftime('%Y%m%d')}.csv")


@app.route("/api/audit_log")
def get_audit_log():
    conn = get_db()
    c    = conn.cursor()
    c.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 100")
    rows = rows_to_list(c.fetchall())
    conn.close()
    return jsonify(rows)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("✅ Reimbursement Management System started")
    print("📊 Database:", DB_PATH)
    print("🌐 Open: http://localhost:5000")
    app.run(debug=True, port=5000)
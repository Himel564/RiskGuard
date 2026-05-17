from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user, login_required, current_user
)
from werkzeug.security import check_password_hash
import json, os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'riskguard-secret-key-change-in-production'

# ── Flask-Login setup ─────────────────────────────────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view             = 'login'
login_manager.login_message          = 'Please log in to access RiskGuard.'
login_manager.login_message_category = 'info'

USERS_FILE = 'users.json'


# ── User model ────────────────────────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, username, role='viewer'):
        self.id   = username
        self.role = role

    def is_admin(self):
        return self.role == 'admin'


@login_manager.user_loader
def load_user(username):
    users = _load_users_file()
    if username in users:
        return User(username, users[username].get('role', 'viewer'))
    return None


# ── Role decorator ────────────────────────────────────────────────────────────
def admin_required(f):
    """Restrict endpoint to admin role only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not current_user.is_admin():
            return jsonify({
                "error":   "Access denied.",
                "message": "This endpoint requires admin role.",
                "your_role": current_user.role
            }), 403
        return f(*args, **kwargs)
    return decorated


# ── Helpers ───────────────────────────────────────────────────────────────────
def _load_users_file():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def is_fraud(record: dict) -> bool:
    return 'FRAUD' in record.get('status', '')


def mask_id(tx_id):
    """Mask transaction ID for viewer role — show only last 3 digits."""
    s = str(tx_id).replace('.', '')[:6].zfill(6)
    return f"***{s[-3:]}"


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        users    = _load_users_file()

        if not users:
            flash('No users found. Run: python create_user.py', 'error')
            return render_template('login.html')

        if username in users and check_password_hash(users[username]['password_hash'], password):
            user = User(username, users[username].get('role', 'viewer'))
            login_user(user, remember=remember)
            return redirect(request.args.get('next') or url_for('index'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    return render_template(
        'index.html',
        username=current_user.id,
        role=current_user.role,
        is_admin=current_user.is_admin()
    )


# ── API — available to ALL logged-in users ────────────────────────────────────

@app.route('/data')
@login_required
def get_data():
    try:
        page  = max(1, int(request.args.get('page',  1)))
        limit = min(500, max(1, int(request.args.get('limit', 50))))
    except (ValueError, TypeError):
        page, limit = 1, 50

    history = load_json('history.json', [])

    # VIEWER: mask transaction IDs + hide confidence details
    if not current_user.is_admin():
        for r in history:
            r = r.copy()
            r['id'] = mask_id(r.get('id', 0))

    start, end = (page-1)*limit, page*limit
    return jsonify({
        "data":     history[start:end],
        "total":    len(history),
        "page":     page,
        "limit":    limit,
        "has_more": end < len(history),
        "role":     current_user.role
    })


@app.route('/stats')
@login_required
def stats():
    history       = load_json('history.json', [])
    fraud_records = [r for r in history if is_fraud(r)]
    clean_records = [r for r in history if not is_fraud(r)]
    fraud_amount  = sum(r.get('amount', 0) for r in fraud_records)
    avg_conf      = sum(r.get('confidence', 0) for r in history) / len(history) if history else 0
    risk_counts   = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in fraud_records:
        lvl = r.get('risk_level', 'LOW')
        if lvl in risk_counts:
            risk_counts[lvl] += 1

    base = {
        "total":          len(history),
        "fraud_count":    len(fraud_records),
        "clean_count":    len(clean_records),
        "fraud_amount":   round(fraud_amount, 2),
        "fraud_rate":     round(len(fraud_records)/len(history)*100, 2) if history else 0,
        "avg_confidence": round(avg_conf, 2),
        "risk_breakdown": risk_counts,
        "role":           current_user.role,
    }

    # VIEWER: hide exact fraud amount (show as masked)
    if not current_user.is_admin():
        base['fraud_amount'] = None   # frontend shows "Restricted"

    return jsonify(base)


# ── API — ADMIN ONLY ──────────────────────────────────────────────────────────

@app.route('/fraud-log')
@admin_required
@login_required
def fraud_log():
    """Full fraud ledger — ADMIN only."""
    return jsonify(load_json('fraud_log.json', []))


@app.route('/blocked')
@admin_required
@login_required
def blocked():
    """Blocked transaction IDs — ADMIN only."""
    return jsonify(load_json('blocked.json', []))


@app.route('/recent-fraud')
@admin_required
@login_required
def recent_fraud():
    """Recent fraud list — ADMIN only."""
    n       = min(50, max(1, int(request.args.get('n', 10))))
    history = load_json('history.json', [])
    return jsonify([r for r in history if is_fraud(r)][:n])


@app.route('/clear-fraud-log', methods=['POST'])
@admin_required
@login_required
def clear_fraud_log():
    """Clear fraud log + blocked list — ADMIN only."""
    with open('fraud_log.json', 'w') as f:
        json.dump([], f)
    with open('blocked.json', 'w') as f:
        json.dump([], f)
    return jsonify({
        "success": True,
        "message": f"Fraud log cleared by {current_user.id} at {datetime.now().isoformat()}"
    })


@app.route('/health')
@login_required
def health():
    data = {
        "status":    "ok",
        "user":      current_user.id,
        "role":      current_user.role,
        "timestamp": datetime.now().isoformat(),
    }
    # Full file status only for admin
    if current_user.is_admin():
        data["files"] = {k: os.path.exists(v) for k, v in {
            "history":   "history.json",
            "fraud_log": "fraud_log.json",
            "blocked":   "blocked.json",
            "stream":    "stream.json",
            "model":     "fraud_model.pkl",
        }.items()}
    return jsonify(data)


# ── Run ───────────────────────────────────────────────────────────────────────
import threading
import subprocess
import sys

def run_producer():
    subprocess.run([sys.executable, 'producer.py'])

def run_detector():
    subprocess.run([sys.executable, 'detector.py'])

# Auto-start background workers
threading.Thread(target=run_producer, daemon=True).start()
threading.Thread(target=run_detector, daemon=True).start()

if __name__ == '__main__':
    print("🌐 RiskGuard Dashboard → http://127.0.0.1:5000")
    app.run(debug=False, port=5000)
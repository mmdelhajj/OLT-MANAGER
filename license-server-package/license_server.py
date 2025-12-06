#!/usr/bin/env python3
"""
OLT Manager - License Server with Web Dashboard
Deploy this on your public IP server to manage customer licenses
"""

import os
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", secrets.token_hex(32))

# Configuration
LICENSE_DB_FILE = Path("licenses.json")
ADMIN_USERNAME = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASS", "admin123")
API_SECRET = os.getenv("LICENSE_SECRET", "CHANGE-THIS-TO-SECURE-KEY")

# ============ HTML Templates ============

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>License Server - Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-box {
            background: #fff;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 400px;
        }
        h1 { color: #1a1a2e; margin-bottom: 30px; text-align: center; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; color: #666; font-size: 14px; }
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input:focus { border-color: #3498db; outline: none; }
        button {
            width: 100%;
            padding: 14px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: background 0.3s;
        }
        button:hover { background: #2980b9; }
        .error { color: #e74c3c; text-align: center; margin-bottom: 20px; }
        .logo { text-align: center; margin-bottom: 20px; font-size: 50px; }
    </style>
</head>
<body>
    <div class="login-box">
        <div class="logo">🔐</div>
        <h1>License Server</h1>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
        <form method="POST">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required autofocus>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
'''

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>License Server - Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f6fa;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 24px; }
        .header a { color: white; text-decoration: none; opacity: 0.8; }
        .header a:hover { opacity: 1; }
        .container { max-width: 1400px; margin: 0 auto; padding: 30px; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .stat-card h3 { color: #666; font-size: 14px; margin-bottom: 10px; }
        .stat-card .value { font-size: 32px; font-weight: bold; color: #1a1a2e; }
        .stat-card.green .value { color: #27ae60; }
        .stat-card.red .value { color: #e74c3c; }
        .stat-card.blue .value { color: #3498db; }
        .stat-card.orange .value { color: #f39c12; }
        .card {
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        .card-header {
            padding: 20px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-header h2 { font-size: 18px; color: #1a1a2e; }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 13px;
            text-decoration: none;
            display: inline-block;
            margin: 2px;
        }
        .btn-primary { background: #3498db; color: white; }
        .btn-primary:hover { background: #2980b9; }
        .btn-success { background: #27ae60; color: white; }
        .btn-success:hover { background: #219a52; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-danger:hover { background: #c0392b; }
        .btn-warning { background: #f39c12; color: white; }
        .btn-warning:hover { background: #d68910; }
        .btn-secondary { background: #95a5a6; color: white; }
        .btn-secondary:hover { background: #7f8c8d; }
        .btn-sm { padding: 5px 10px; font-size: 12px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; color: #666; font-size: 13px; }
        .badge {
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
        }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-danger { background: #f8d7da; color: #721c24; }
        .badge-warning { background: #fff3cd; color: #856404; }
        .badge-secondary { background: #e2e3e5; color: #383d41; }
        .badge-info { background: #d1ecf1; color: #0c5460; }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 10px;
            width: 100%;
            max-width: 500px;
            max-height: 90vh;
            overflow-y: auto;
        }
        .modal-content h2 { margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #666; font-weight: 500; }
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        .form-row { display: flex; gap: 15px; }
        .form-row .form-group { flex: 1; }
        .form-actions { margin-top: 20px; display: flex; gap: 10px; }
        .license-key {
            font-family: monospace;
            background: #f8f9fa;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 12px;
            font-weight: 600;
        }
        .copy-btn {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 14px;
            opacity: 0.6;
            padding: 0 5px;
        }
        .copy-btn:hover { opacity: 1; }
        .text-muted { color: #999; font-size: 11px; }
        .package-badge {
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .package-monthly { background: #e3f2fd; color: #1565c0; }
        .package-yearly { background: #e8f5e9; color: #2e7d32; }
        .package-lifetime { background: #fce4ec; color: #c2185b; }
        .package-trial { background: #fff3e0; color: #ef6c00; }
        .actions-cell { white-space: nowrap; }
        .suspended-row { background: #fff5f5; }
        .suspended-row td { color: #999; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔐 License Server</h1>
        <a href="/logout">Logout</a>
    </div>

    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <h3>Total Licenses</h3>
                <div class="value">{{ stats.total }}</div>
            </div>
            <div class="stat-card green">
                <h3>Active</h3>
                <div class="value">{{ stats.active }}</div>
            </div>
            <div class="stat-card orange">
                <h3>Suspended</h3>
                <div class="value">{{ stats.suspended }}</div>
            </div>
            <div class="stat-card red">
                <h3>Expired</h3>
                <div class="value">{{ stats.expired }}</div>
            </div>
            <div class="stat-card blue">
                <h3>Activated</h3>
                <div class="value">{{ stats.activated }}</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h2>Licenses</h2>
                <button class="btn btn-primary" onclick="showCreateModal()">+ Create License</button>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>License Key</th>
                        <th>Customer</th>
                        <th>Package</th>
                        <th>Limits</th>
                        <th>Status</th>
                        <th>Expires</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for lic in licenses %}
                    <tr class="{{ 'suspended-row' if lic.suspended else '' }}">
                        <td>
                            <span class="license-key">{{ lic.license_key }}</span>
                            <button class="copy-btn" onclick="copyKey('{{ lic.license_key }}')" title="Copy">📋</button>
                            {% if lic.hardware_id %}
                            <br><span class="text-muted">✓ Activated</span>
                            {% endif %}
                        </td>
                        <td>
                            <strong>{{ lic.customer_name }}</strong>
                            {% if lic.customer_email %}<br><span class="text-muted">{{ lic.customer_email }}</span>{% endif %}
                        </td>
                        <td>
                            {% if lic.package_type == 'monthly' %}
                            <span class="package-badge package-monthly">Monthly</span>
                            {% elif lic.package_type == 'yearly' %}
                            <span class="package-badge package-yearly">Yearly</span>
                            {% elif lic.package_type == 'lifetime' %}
                            <span class="package-badge package-lifetime">Lifetime</span>
                            {% elif lic.package_type == 'trial' %}
                            <span class="package-badge package-trial">Trial</span>
                            {% else %}
                            <span class="package-badge">{{ lic.package_type or 'Standard' }}</span>
                            {% endif %}
                        </td>
                        <td>
                            <span class="text-muted">OLTs:</span> {{ lic.max_olts }}<br>
                            <span class="text-muted">ONUs:</span> {{ lic.max_onus }}
                        </td>
                        <td>
                            {% if lic.suspended %}
                            <span class="badge badge-warning">Suspended</span>
                            {% elif not lic.active %}
                            <span class="badge badge-danger">Revoked</span>
                            {% elif lic.is_expired %}
                            <span class="badge badge-danger">Expired</span>
                            {% else %}
                            <span class="badge badge-success">Active</span>
                            {% endif %}
                        </td>
                        <td>
                            {{ lic.expires_at[:10] if lic.expires_at else 'Never' }}
                            {% if lic.last_check %}<br><span class="text-muted">Last: {{ lic.last_check[:10] }}</span>{% endif %}
                        </td>
                        <td class="actions-cell">
                            {% if lic.suspended %}
                            <button class="btn btn-success btn-sm" onclick="resumeLicense('{{ lic.license_key }}')">Resume</button>
                            {% elif lic.active and not lic.is_expired %}
                            <button class="btn btn-warning btn-sm" onclick="suspendLicense('{{ lic.license_key }}')">Suspend</button>
                            {% endif %}
                            <button class="btn btn-primary btn-sm" onclick="extendLicense('{{ lic.license_key }}')">Extend</button>
                            {% if lic.hardware_id %}
                            <button class="btn btn-secondary btn-sm" onclick="resetHardware('{{ lic.license_key }}')">Reset HW</button>
                            {% endif %}
                            {% if lic.active %}
                            <button class="btn btn-danger btn-sm" onclick="revokeLicense('{{ lic.license_key }}')">Revoke</button>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                    {% if not licenses %}
                    <tr>
                        <td colspan="7" style="text-align: center; padding: 40px; color: #999;">
                            No licenses yet. Click "+ Create License" to add one.
                        </td>
                    </tr>
                    {% endif %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Create License Modal -->
    <div class="modal" id="createModal">
        <div class="modal-content">
            <h2>Create New License</h2>
            <form method="POST" action="/dashboard/create">
                <div class="form-group">
                    <label>Customer Name *</label>
                    <input type="text" name="customer_name" required>
                </div>
                <div class="form-group">
                    <label>Customer Email</label>
                    <input type="email" name="customer_email">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Package Type</label>
                        <select name="package_type" id="packageType" onchange="updateValidity()">
                            <option value="trial">Trial (7 days)</option>
                            <option value="monthly" selected>Monthly (30 days)</option>
                            <option value="yearly">Yearly (365 days)</option>
                            <option value="lifetime">Lifetime</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Validity (Days)</label>
                        <input type="number" name="validity_days" id="validityDays" value="30" min="1">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Max OLTs</label>
                        <input type="number" name="max_olts" value="5" min="1">
                    </div>
                    <div class="form-group">
                        <label>Max ONUs</label>
                        <input type="number" name="max_onus" value="1000" min="1">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Max Users</label>
                        <input type="number" name="max_users" value="10" min="1">
                    </div>
                    <div class="form-group">
                        <label>License Type</label>
                        <select name="license_type">
                            <option value="basic">Basic</option>
                            <option value="standard">Standard</option>
                            <option value="professional" selected>Professional</option>
                            <option value="enterprise">Enterprise</option>
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label>Notes</label>
                    <input type="text" name="notes" placeholder="Optional notes...">
                </div>
                <div class="form-actions">
                    <button type="submit" class="btn btn-success">Create License</button>
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function showCreateModal() {
            document.getElementById('createModal').classList.add('active');
        }
        function closeModal() {
            document.getElementById('createModal').classList.remove('active');
        }
        function updateValidity() {
            const pkg = document.getElementById('packageType').value;
            const validity = document.getElementById('validityDays');
            switch(pkg) {
                case 'trial': validity.value = 7; break;
                case 'monthly': validity.value = 30; break;
                case 'yearly': validity.value = 365; break;
                case 'lifetime': validity.value = 36500; break;
            }
        }
        function copyKey(key) {
            navigator.clipboard.writeText(key);
            alert('License key copied: ' + key);
        }
        function suspendLicense(key) {
            if (confirm('Suspend this license?\\n\\nThe customer will see:\\n"License has been suspended. Please contact support."\\n\\nThey cannot use the software until you Resume it.')) {
                window.location.href = '/dashboard/suspend/' + key;
            }
        }
        function resumeLicense(key) {
            if (confirm('Resume this license? The customer will be able to use the software again.')) {
                window.location.href = '/dashboard/resume/' + key;
            }
        }
        function extendLicense(key) {
            const days = prompt('Extend by how many days?', '30');
            if (days && !isNaN(days)) {
                window.location.href = '/dashboard/extend/' + key + '?days=' + days;
            }
        }
        function resetHardware(key) {
            if (confirm('Reset hardware binding?\\n\\nThe customer will need to re-activate on their server.')) {
                window.location.href = '/dashboard/reset/' + key;
            }
        }
        function revokeLicense(key) {
            if (confirm('REVOKE this license permanently?\\n\\nThis cannot be undone. The customer will see:\\n"License has been revoked."')) {
                window.location.href = '/dashboard/revoke/' + key;
            }
        }
        document.getElementById('createModal').addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });
    </script>
</body>
</html>
'''

# ============ Database Functions ============

def load_licenses():
    if LICENSE_DB_FILE.exists():
        with open(LICENSE_DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_licenses(licenses):
    with open(LICENSE_DB_FILE, 'w') as f:
        json.dump(licenses, f, indent=2, default=str)

def generate_license_key():
    return f"OLT-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"

# ============ Auth Helpers ============

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-Admin-Key')
        if api_key != API_SECRET:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# ============ Web Dashboard Routes ============

@app.route('/')
def index():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USERNAME and request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        error = 'Invalid username or password'
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    licenses = load_licenses()
    now = datetime.now()

    stats = {
        'total': len(licenses),
        'active': 0,
        'expired': 0,
        'suspended': 0,
        'activated': 0
    }

    license_list = []
    for key, data in licenses.items():
        lic = {'license_key': key, **data}

        expires_at = data.get('expires_at')
        lic['is_expired'] = False
        if expires_at:
            if datetime.fromisoformat(expires_at) < now:
                lic['is_expired'] = True
                stats['expired'] += 1

        if data.get('suspended'):
            stats['suspended'] += 1
        elif data.get('active', True) and not lic['is_expired']:
            stats['active'] += 1

        if data.get('hardware_id'):
            stats['activated'] += 1

        license_list.append(lic)

    license_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    return render_template_string(DASHBOARD_HTML, licenses=license_list, stats=stats)

@app.route('/dashboard/create', methods=['POST'])
@login_required
def dashboard_create():
    days = int(request.form.get('validity_days', 365))
    expires_at = (datetime.now() + timedelta(days=days)).isoformat() if days > 0 else None

    license_key = generate_license_key()
    license_data = {
        'customer_name': request.form.get('customer_name', 'Unknown'),
        'customer_email': request.form.get('customer_email', ''),
        'max_olts': int(request.form.get('max_olts', 5)),
        'max_onus': int(request.form.get('max_onus', 1000)),
        'max_users': int(request.form.get('max_users', 10)),
        'features': ['basic', 'traffic', 'diagrams', 'whatsapp'],
        'license_type': request.form.get('license_type', 'professional'),
        'package_type': request.form.get('package_type', 'monthly'),
        'expires_at': expires_at,
        'created_at': datetime.now().isoformat(),
        'active': True,
        'suspended': False,
        'hardware_id': None,
        'notes': request.form.get('notes', '')
    }

    licenses = load_licenses()
    licenses[license_key] = license_data
    save_licenses(licenses)

    return redirect(url_for('dashboard'))

@app.route('/dashboard/suspend/<license_key>')
@login_required
def dashboard_suspend(license_key):
    licenses = load_licenses()
    if license_key in licenses:
        licenses[license_key]['suspended'] = True
        licenses[license_key]['suspended_at'] = datetime.now().isoformat()
        save_licenses(licenses)
    return redirect(url_for('dashboard'))

@app.route('/dashboard/resume/<license_key>')
@login_required
def dashboard_resume(license_key):
    licenses = load_licenses()
    if license_key in licenses:
        licenses[license_key]['suspended'] = False
        licenses[license_key]['resumed_at'] = datetime.now().isoformat()
        save_licenses(licenses)
    return redirect(url_for('dashboard'))

@app.route('/dashboard/extend/<license_key>')
@login_required
def dashboard_extend(license_key):
    days = int(request.args.get('days', 365))
    licenses = load_licenses()

    if license_key in licenses:
        current_exp = licenses[license_key].get('expires_at')
        if current_exp:
            exp_date = datetime.fromisoformat(current_exp)
            if exp_date < datetime.now():
                exp_date = datetime.now()
        else:
            exp_date = datetime.now()

        licenses[license_key]['expires_at'] = (exp_date + timedelta(days=days)).isoformat()
        save_licenses(licenses)

    return redirect(url_for('dashboard'))

@app.route('/dashboard/reset/<license_key>')
@login_required
def dashboard_reset(license_key):
    licenses = load_licenses()
    if license_key in licenses:
        licenses[license_key]['hardware_id'] = None
        licenses[license_key]['activated_at'] = None
        save_licenses(licenses)
    return redirect(url_for('dashboard'))

@app.route('/dashboard/revoke/<license_key>')
@login_required
def dashboard_revoke(license_key):
    licenses = load_licenses()
    if license_key in licenses:
        licenses[license_key]['active'] = False
        licenses[license_key]['revoked_at'] = datetime.now().isoformat()
        save_licenses(licenses)
    return redirect(url_for('dashboard'))

# ============ API Endpoints ============

@app.route('/api/validate', methods=['POST'])
def validate_license():
    """Public endpoint for customer installations to validate license"""
    data = request.json or {}
    license_key = data.get('license_key')
    hardware_id = data.get('hardware_id')

    if not license_key:
        return jsonify({'error': 'License key required'}), 400

    licenses = load_licenses()
    license_data = licenses.get(license_key)

    if not license_data:
        return jsonify({'error': 'Invalid license key'}), 403

    # Check if suspended
    if license_data.get('suspended'):
        return jsonify({'error': 'License has been suspended. Please contact support.'}), 403

    # Check if revoked
    if not license_data.get('active', True):
        return jsonify({'error': 'License has been revoked'}), 403

    # Check expiration
    expires_at = license_data.get('expires_at')
    if expires_at:
        if datetime.fromisoformat(expires_at) < datetime.now():
            return jsonify({'error': 'License has expired. Please renew your subscription.'}), 403

    # Check hardware binding
    bound_hardware = license_data.get('hardware_id')
    if bound_hardware:
        if bound_hardware != hardware_id:
            return jsonify({'error': 'License is bound to different hardware. Contact support to reset.'}), 409
    else:
        license_data['hardware_id'] = hardware_id
        license_data['activated_at'] = datetime.now().isoformat()
        license_data['activation_ip'] = request.remote_addr
        licenses[license_key] = license_data
        save_licenses(licenses)

    license_data['last_check'] = datetime.now().isoformat()
    license_data['last_ip'] = request.remote_addr
    licenses[license_key] = license_data
    save_licenses(licenses)

    return jsonify({
        'valid': True,
        'customer_name': license_data.get('customer_name', 'Unknown'),
        'max_olts': license_data.get('max_olts', 1),
        'max_onus': license_data.get('max_onus', 100),
        'max_users': license_data.get('max_users', 5),
        'expires_at': license_data.get('expires_at'),
        'features': license_data.get('features', ['basic']),
        'license_type': license_data.get('license_type', 'standard'),
        'package_type': license_data.get('package_type', 'standard')
    })

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

# API endpoints for programmatic access
@app.route('/api/licenses', methods=['GET'])
@require_api_key
def api_list_licenses():
    return jsonify(list(load_licenses().values()))

@app.route('/api/licenses', methods=['POST'])
@require_api_key
def api_create_license():
    data = request.json or {}
    days = data.get('validity_days', 365)
    expires_at = (datetime.now() + timedelta(days=days)).isoformat() if days > 0 else None

    license_key = generate_license_key()
    license_data = {
        'customer_name': data.get('customer_name', 'Unknown'),
        'customer_email': data.get('customer_email', ''),
        'max_olts': data.get('max_olts', 5),
        'max_onus': data.get('max_onus', 1000),
        'max_users': data.get('max_users', 10),
        'features': data.get('features', ['basic', 'traffic', 'diagrams', 'whatsapp']),
        'license_type': data.get('license_type', 'professional'),
        'package_type': data.get('package_type', 'monthly'),
        'expires_at': expires_at,
        'created_at': datetime.now().isoformat(),
        'active': True,
        'suspended': False,
        'hardware_id': None,
        'notes': data.get('notes', '')
    }

    licenses = load_licenses()
    licenses[license_key] = license_data
    save_licenses(licenses)

    return jsonify({'license_key': license_key, **license_data})

# ============ Main ============

if __name__ == '__main__':
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           OLT Manager License Server                          ║
╠══════════════════════════════════════════════════════════════╣
║  Dashboard: http://localhost:5000                             ║
║  Username:  {ADMIN_USERNAME}                                          ║
║  Password:  {ADMIN_PASSWORD}                                       ║
╚══════════════════════════════════════════════════════════════╝
    """)

    app.run(host='0.0.0.0', port=5000, debug=True)

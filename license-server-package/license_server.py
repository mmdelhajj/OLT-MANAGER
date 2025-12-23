#!/usr/bin/env python3
"""
OLT Manager - License Server with Web Dashboard
Deploy this on your public IP server to manage customer licenses
"""

import os
import json
import secrets
import hashlib
import subprocess
import pty
import select
import struct
import fcntl
import termios
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session, Response, send_file
from flask_sockets import Sockets
from geventwebsocket import WebSocketError

app = Flask(__name__)
sockets = Sockets(app)
app.secret_key = os.getenv("FLASK_SECRET", secrets.token_hex(32))

# Configuration
LICENSE_DB_FILE = Path("licenses.json")
ADMIN_USERNAME = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASS", "admin")
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
        <div>
            <a href="/tunnels" style="margin-right: 20px;">🖥️ Customer Tunnels</a>
            <a href="/logout">Logout</a>
        </div>
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
                <div>
                    <button class="btn btn-success" onclick="showTokenModal()">🎫 Create Install Token</button>
                    <button class="btn btn-primary" onclick="showCreateModal()">+ Create License</button>
                </div>
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
                            <a href="/dashboard/edit/{{ lic.license_key }}" class="btn btn-info btn-sm" style="text-decoration:none;">Edit</a>
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
                            <button class="btn btn-sm" style="background:#333;color:#fff;" onclick="deleteLicense('{{ lic.license_key }}')">Delete</button>
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

    <!-- Create Install Token Modal -->
    <div class="modal" id="tokenModal">
        <div class="modal-content">
            <h2>🎫 Create Install Token</h2>
            <p style="color:#aaa; margin-bottom:20px;">Pre-register a customer and get a one-time install token</p>
            <form method="POST" action="/dashboard/create-token">
                <div class="form-group">
                    <label>Customer Name *</label>
                    <input type="text" name="customer_name" required placeholder="e.g. ABC ISP Company">
                </div>
                <div class="form-group">
                    <label>Customer Email</label>
                    <input type="email" name="customer_email" placeholder="customer@example.com">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Package Type</label>
                        <select name="package_type" onchange="updateTokenValidity(this)">
                            <option value="monthly">Monthly (30 days)</option>
                            <option value="yearly" selected>Yearly (365 days)</option>
                            <option value="lifetime">Lifetime</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Validity (Days)</label>
                        <input type="number" name="validity_days" id="tokenValidityDays" value="365" min="1">
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
                    <div class="form-group">
                        <label>Max Users</label>
                        <input type="number" name="max_users" value="10" min="1">
                    </div>
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
                <div class="form-group">
                    <label>Notes</label>
                    <input type="text" name="notes" placeholder="Optional notes...">
                </div>
                <div class="form-actions">
                    <button type="submit" class="btn btn-success">Generate Install Token</button>
                    <button type="button" class="btn btn-secondary" onclick="closeTokenModal()">Cancel</button>
                </div>
            </form>
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
                            <option value="trial">Trial (2 days)</option>
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
        function showTokenModal() {
            document.getElementById('tokenModal').classList.add('active');
        }
        function closeTokenModal() {
            document.getElementById('tokenModal').classList.remove('active');
        }
        function updateTokenValidity(select) {
            const validity = document.getElementById('tokenValidityDays');
            switch(select.value) {
                case 'monthly': validity.value = 30; break;
                case 'yearly': validity.value = 365; break;
                case 'lifetime': validity.value = 36500; break;
            }
        }
        document.getElementById('tokenModal').addEventListener('click', function(e) {
            if (e.target === this) closeTokenModal();
        });
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
        function deleteLicense(key) {
            if (confirm('DELETE this license permanently?\\n\\nThis will completely remove the license from the database.\\nThe customer will need a new license to use the software.')) {
                window.location.href = '/dashboard/delete/' + key;
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

@app.route('/dashboard/delete/<license_key>')
@login_required
def dashboard_delete(license_key):
    """Permanently delete a license"""
    licenses = load_licenses()
    if license_key in licenses:
        # Also remove from tunnels if exists
        tunnel_port = licenses[license_key].get('tunnel_port')
        del licenses[license_key]
        save_licenses(licenses)

        # Clean up tunnel if exists
        if tunnel_port:
            tunnels = load_tunnels()
            tunnels['tunnels'] = [t for t in tunnels['tunnels'] if t.get('port') != tunnel_port]
            save_tunnels(tunnels)
    return redirect(url_for('dashboard'))


# License Edit Page and Handler
@app.route('/dashboard/edit/<license_key>')
@login_required
def dashboard_edit(license_key):
    licenses = load_licenses()
    if license_key not in licenses:
        return redirect(url_for('dashboard'))
    
    lic = licenses[license_key]
    
    edit_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Edit License</title>
    <meta name=viewport content=width=device-width, initial-scale=1>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: white; min-height: 100vh; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .header h1 { font-size: 24px; }
        .back { color: #3498db; text-decoration: none; }
        .card { background: #16213e; border-radius: 10px; padding: 25px; margin-bottom: 20px; }
        .card h2 { margin-bottom: 20px; font-size: 18px; border-bottom: 1px solid #0f3460; padding-bottom: 10px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; margin-bottom: 8px; color: #aaa; font-size: 14px; }
        .form-group input, .form-group select, .form-group textarea { 
            width: 100%; padding: 12px; border: 1px solid #0f3460; border-radius: 5px; 
            background: #1a1a2e; color: white; font-size: 14px; 
        }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus { 
            outline: none; border-color: #3498db; 
        }
        .form-row { display: flex; gap: 15px; }
        .form-row .form-group { flex: 1; }
        .btn { padding: 12px 25px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; }
        .btn-primary { background: #3498db; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn-secondary { background: #666; color: white; }
        .btn:hover { opacity: 0.9; }
        .info-box { background: #0f3460; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .info-box p { margin: 5px 0; font-size: 13px; color: #aaa; }
        .info-box strong { color: white; }
        .actions { display: flex; gap: 10px; margin-top: 20px; }
        .success-msg { background: #27ae60; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class=container>
        <div class=header>
            <h1>Edit License</h1>
            <a href=/dashboard class=back>&larr; Back to Dashboard</a>
        </div>
        
        {% if success %}
        <div class=success-msg>License updated successfully!</div>
        {% endif %}
        
        <div class=info-box>
            <p><strong>License Key:</strong> {{ license_key }}</p>
            <p><strong>Type:</strong> {{ lic.license_type }}</p>
            <p><strong>Status:</strong> {{ 'Active' if lic.active else 'Inactive' }} {{ '(Suspended)' if lic.suspended else '' }}</p>
        </div>
        
        <form method=POST action=/dashboard/edit/{{ license_key }}>
            <div class=card>
                <h2>Customer Information</h2>
                <div class=form-group>
                    <label>Customer Name</label>
                    <input type=text name=customer_name value={{ lic.customer_name }}>
                </div>
                <div class=form-group>
                    <label>Customer Email</label>
                    <input type=email name=customer_email value={{ lic.customer_email }}>
                </div>
                <div class=form-group>
                    <label>Notes</label>
                    <textarea name=notes rows=3>{{ lic.notes or '' }}</textarea>
                </div>
            </div>
            
            <div class=card>
                <h2>SSH Remote Access</h2>
                <div class=form-row>
                    <div class=form-group>
                        <label>Tunnel Port</label>
                        <input type=number name=tunnel_port value={{ lic.tunnel_port or  }} placeholder=e.g. 30003>
                    </div>
                    <div class=form-group>
                        <label>SSH Username</label>
                        <input type=text name=ssh_user value={{ lic.ssh_user or root }}>
                    </div>
                </div>
                <div class=form-group>
                    <label>SSH Password</label>
                    <input type=text name=ssh_password value={{ lic.ssh_password or  }} placeholder=Enter SSH password>
                </div>
            </div>
            
            <div class=card>
                <h2>License Limits</h2>
                <div class=form-row>
                    <div class=form-group>
                        <label>Max OLTs</label>
                        <input type=number name=max_olts value={{ lic.max_olts }}>
                    </div>
                    <div class=form-group>
                        <label>Max ONUs</label>
                        <input type=number name=max_onus value={{ lic.max_onus }}>
                    </div>
                    <div class=form-group>
                        <label>Max Users</label>
                        <input type=number name=max_users value={{ lic.max_users }}>
                    </div>
                </div>
            </div>
            
            <div class=actions>
                <button type=submit class=btn btn-success>Save Changes</button>
                <a href=/dashboard class=btn btn-secondary>Cancel</a>
            </div>
        </form>
    </div>
</body>
</html>
'''
    return render_template_string(edit_html, license_key=license_key, lic=lic, success=request.args.get('success'))


@app.route('/dashboard/edit/<license_key>', methods=['POST'])
@login_required  
def dashboard_edit_save(license_key):
    licenses = load_licenses()
    if license_key not in licenses:
        return redirect(url_for('dashboard'))
    
    # Update license fields
    licenses[license_key]['customer_name'] = request.form.get('customer_name', '')
    licenses[license_key]['customer_email'] = request.form.get('customer_email', '')
    licenses[license_key]['notes'] = request.form.get('notes', '')
    
    # SSH credentials
    tunnel_port = request.form.get('tunnel_port', '')
    licenses[license_key]['tunnel_port'] = int(tunnel_port) if tunnel_port else None
    licenses[license_key]['ssh_user'] = request.form.get('ssh_user', 'root')
    licenses[license_key]['ssh_password'] = request.form.get('ssh_password', '')
    
    # License limits
    licenses[license_key]['max_olts'] = int(request.form.get('max_olts', 1))
    licenses[license_key]['max_onus'] = int(request.form.get('max_onus', 50))
    licenses[license_key]['max_users'] = int(request.form.get('max_users', 2))
    
    save_licenses(licenses)
    
    return redirect(f'/dashboard/edit/{license_key}?success=1')


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

    # Check for available updates
    update_info = None
    customer_version = data.get('current_version', '0.0.0')
    updates_data = load_updates()
    if updates_data.get('latest'):
        latest_version = updates_data['latest']
        # Compare versions (simple string compare works for semver)
        if latest_version > customer_version:
            # Find full version info
            for v in updates_data.get('versions', []):
                if v['version'] == latest_version:
                    update_info = {
                        'latest_version': latest_version,
                        'changelog': v.get('changelog', ''),
                        'download_url': f'/api/download-update/{latest_version}'
                    }
                    break

    response = {
        'valid': True,
        'customer_name': license_data.get('customer_name', 'Unknown'),
        'max_olts': license_data.get('max_olts', 1),
        'max_onus': license_data.get('max_onus', 100),
        'max_users': license_data.get('max_users', 5),
        'expires_at': license_data.get('expires_at'),
        'features': license_data.get('features', ['basic']),
        'license_type': license_data.get('license_type', 'standard'),
        'package_type': license_data.get('package_type', 'standard')
    }

    if update_info:
        response['update'] = update_info

    return jsonify(response)

@app.route('/api/trial', methods=['POST'])
def register_trial():
    """Auto-register a 7-day trial license for new installations"""
    data = request.json or {}
    hardware_id = data.get('hardware_id')
    hostname = data.get('hostname', 'Unknown')
    ip_address = request.remote_addr

    if not hardware_id:
        return jsonify({'error': 'Hardware ID required'}), 400

    licenses = load_licenses()

    # Check if this hardware already has a license (trial or paid)
    for key, lic_data in licenses.items():
        if lic_data.get('hardware_id') == hardware_id:
            # Already has a license, return it
            return jsonify({
                'existing': True,
                'license_key': key,
                'expires_at': lic_data.get('expires_at', ''),
                'tunnel_port': lic_data.get('tunnel_port'),
                'message': 'License already exists for this hardware'
            })

    # Get next available tunnel port
    tunnel_data = load_tunnels()
    tunnel_port = tunnel_data.get('next_port', 30001)
    tunnel_data['next_port'] = tunnel_port + 1

    # Create new 7-day trial license
    license_key = generate_license_key()
    license_data = {
        'customer_name': f'Trial - {hostname}',
        'customer_email': '',
        'max_olts': 2,  # Limited for trial
        'max_onus': 50,  # Limited for trial
        'max_users': 2,  # Limited for trial
        'features': ['basic', 'traffic'],  # Limited features for trial
        'license_type': 'trial',
        'package_type': 'trial',
        'expires_at': (datetime.now() + timedelta(days=2)).isoformat(),
        'created_at': datetime.now().isoformat(),
        'active': True,
        'suspended': False,
        'hardware_id': hardware_id,
        'activated_at': datetime.now().isoformat(),
        'activation_ip': ip_address,
        'tunnel_port': tunnel_port,
        'notes': f'Auto-registered trial from {ip_address}'
    }

    licenses[license_key] = license_data
    save_licenses(licenses)

    # Register tunnel
    tunnel_data['tunnels'].append({
        'port': tunnel_port,
        'license_key': license_key,
        'hostname': hostname,
        'registered_at': datetime.now().isoformat(),
        'last_seen': datetime.now().isoformat(),
        'ip': ip_address
    })
    save_tunnels(tunnel_data)

    return jsonify({
        'success': True,
        'license_key': license_key,
        'expires_at': license_data['expires_at'],
        'tunnel_port': tunnel_port,
        'message': 'Trial license created successfully (7 days)'
    })

@app.route('/api/register-trial', methods=['POST'])
def register_trial_alias():
    """Alias for /api/trial - used by install.sh"""
    return register_trial()

@app.route('/api/register-secure-trial', methods=['POST'])
def register_secure_trial():
    """Register secure trial with SSH password - used by secure-install.sh"""
    data = request.json or {}
    hardware_id = data.get('hardware_id')
    hostname = data.get('hostname', 'Unknown')
    ip_address = data.get('ip_address', request.remote_addr)
    ssh_password = data.get('ssh_password', '')
    luks_verified = data.get('luks_verified', False)

    if not hardware_id:
        return jsonify({'error': 'Hardware ID required'}), 400

    licenses = load_licenses()

    # Check if this hardware already has a license
    for key, lic_data in licenses.items():
        if lic_data.get('hardware_id') == hardware_id:
            # Return existing license info including tunnel_port
            return jsonify({
                'existing': True,
                'license_key': key,
                'expires_at': lic_data.get('expires_at', ''),
                'tunnel_port': lic_data.get('tunnel_port'),
                'message': 'License already exists for this hardware'
            })

    # Get next available tunnel port
    tunnel_data = load_tunnels()
    tunnel_port = tunnel_data.get('next_port', 30001)
    tunnel_data['next_port'] = tunnel_port + 1

    # Create new 7-day trial license with SSH password
    license_key = generate_license_key()
    license_data = {
        'customer_name': f'Secure Trial - {hostname}',
        'customer_email': '',
        'max_olts': 2,
        'max_onus': 50,
        'max_users': 2,
        'features': ['basic', 'traffic'],
        'license_type': 'trial',
        'package_type': 'secure_trial',
        'expires_at': (datetime.now() + timedelta(days=2)).isoformat(),
        'created_at': datetime.now().isoformat(),
        'active': True,
        'suspended': False,
        'hardware_id': hardware_id,
        'activated_at': datetime.now().isoformat(),
        'activation_ip': ip_address,
        'hostname': hostname,
        'ssh_user': 'root',
        'ssh_password': ssh_password,
        'luks_verified': luks_verified,
        'install_type': 'secure',
        'tunnel_port': tunnel_port,
        'notes': f'Secure auto-registered trial from {ip_address}'
    }

    licenses[license_key] = license_data
    save_licenses(licenses)

    # Register tunnel
    tunnel_data['tunnels'].append({
        'port': tunnel_port,
        'license_key': license_key,
        'hostname': hostname,
        'registered_at': datetime.now().isoformat(),
        'last_seen': datetime.now().isoformat(),
        'ip': ip_address
    })
    save_tunnels(tunnel_data)

    return jsonify({
        'success': True,
        'license_key': license_key,
        'expires_at': license_data['expires_at'],
        'tunnel_port': tunnel_port,
        'message': 'Secure trial license created successfully (7 days)'
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


# ============ Install Token System ============

def generate_install_token():
    """Generate a short install token"""
    return secrets.token_hex(8).upper()

@app.route('/dashboard/create-token', methods=['POST'])
@login_required
def dashboard_create_token():
    """Create a license with install token for customer"""
    days = int(request.form.get('validity_days', 365))
    expires_at = (datetime.now() + timedelta(days=days)).isoformat() if days > 0 else None

    license_key = generate_license_key()
    install_token = generate_install_token()

    # Get next tunnel port
    tunnel_data = load_tunnels()
    tunnel_port = tunnel_data.get('next_port', 30001)
    tunnel_data['next_port'] = tunnel_port + 1
    save_tunnels(tunnel_data)

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
        'install_token': install_token,
        'install_token_used': False,
        'tunnel_port': tunnel_port,
        'ssh_user': 'root',
        'ssh_password': '',  # Will be set during installation
        'notes': request.form.get('notes', '')
    }

    licenses = load_licenses()
    licenses[license_key] = license_data
    save_licenses(licenses)

    # Redirect to show the token
    return redirect(f'/dashboard/show-token/{license_key}')


@app.route('/dashboard/show-token/<license_key>')
@login_required
def show_token(license_key):
    """Show install token to admin"""
    licenses = load_licenses()
    if license_key not in licenses:
        return redirect(url_for('dashboard'))

    lic = licenses[license_key]
    install_token = lic.get('install_token', 'N/A')
    tunnel_port = lic.get('tunnel_port', 'N/A')

    token_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Install Token Created</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: white; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .card { background: #16213e; padding: 40px; border-radius: 15px; text-align: center; max-width: 600px; }
        h1 { color: #2ecc71; margin-bottom: 20px; }
        .token-box { background: #0f3460; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .token { font-family: monospace; font-size: 28px; color: #f39c12; letter-spacing: 3px; }
        .info { color: #aaa; margin: 15px 0; font-size: 14px; }
        .command { background: #000; padding: 15px; border-radius: 5px; font-family: monospace; font-size: 12px; text-align: left; overflow-x: auto; margin: 15px 0; }
        .command span { color: #2ecc71; }
        .btn { padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 14px; margin: 5px; text-decoration: none; display: inline-block; }
        .btn-primary { background: #3498db; color: white; }
        .btn-secondary { background: #666; color: white; }
        .warning { background: #f39c12; color: #000; padding: 10px; border-radius: 5px; margin-top: 20px; font-size: 13px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>✅ License Created!</h1>
        <p>Customer: <strong>{{ lic.customer_name }}</strong></p>

        <div class="token-box">
            <p class="info">INSTALL TOKEN (Give this to customer)</p>
            <p class="token">{{ install_token }}</p>
        </div>

        <p class="info">Assigned Tunnel Port: <strong>{{ tunnel_port }}</strong></p>
        <p class="info">License Key: <strong>{{ license_key }}</strong></p>

        <div class="command">
            <p style="color: #aaa; margin-bottom: 10px;"># Customer runs this command on their server:</p>
            <span>curl -sSL https://raw.githubusercontent.com/mmdelhajj/OLT-MANAGER/main/secure-install/token-install.sh | bash -s -- {{ install_token }}</span>
        </div>

        <div class="warning">
            ⚠️ This token can only be used ONCE. After installation, SSH password will be auto-generated and stored here.
        </div>

        <div style="margin-top: 30px;">
            <a href="/dashboard" class="btn btn-primary">Back to Dashboard</a>
            <button class="btn btn-secondary" onclick="copyCommand()">Copy Install Command</button>
        </div>
    </div>

    <script>
        function copyCommand() {
            const cmd = 'curl -sSL https://raw.githubusercontent.com/mmdelhajj/OLT-MANAGER/main/secure-install/token-install.sh | bash -s -- {{ install_token }}';
            navigator.clipboard.writeText(cmd);
            alert('Install command copied!');
        }
    </script>
</body>
</html>
'''
    return render_template_string(token_html, lic=lic, license_key=license_key, install_token=install_token, tunnel_port=tunnel_port)


@app.route('/api/validate-install-token', methods=['POST'])
def validate_install_token():
    """Validate install token and return license info"""
    data = request.json or {}
    token = data.get('token', '').strip().upper()

    if not token:
        return jsonify({'valid': False, 'error': 'Token required'}), 400

    licenses = load_licenses()

    # Find license with this token
    for license_key, lic_data in licenses.items():
        if lic_data.get('install_token', '').upper() == token:
            # Check if already used
            if lic_data.get('install_token_used'):
                return jsonify({'valid': False, 'error': 'Token already used'}), 403

            # Check if suspended/revoked
            if lic_data.get('suspended'):
                return jsonify({'valid': False, 'error': 'License suspended'}), 403
            if not lic_data.get('active', True):
                return jsonify({'valid': False, 'error': 'License revoked'}), 403

            return jsonify({
                'valid': True,
                'license_key': license_key,
                'customer_name': lic_data.get('customer_name', 'Unknown'),
                'tunnel_port': lic_data.get('tunnel_port'),
                'max_olts': lic_data.get('max_olts', 5),
                'max_onus': lic_data.get('max_onus', 1000)
            })

    return jsonify({'valid': False, 'error': 'Invalid token'}), 404


@app.route('/api/register-installation', methods=['POST'])
def register_installation():
    """Register completed installation with SSH credentials"""
    data = request.json or {}
    license_key = data.get('license_key', '')
    ssh_password = data.get('ssh_password', '')
    tunnel_port = data.get('tunnel_port')
    hostname = data.get('hostname', 'Unknown')
    hardware_id = data.get('hardware_id', '')
    ip_address = data.get('ip_address', request.remote_addr)

    if not license_key:
        return jsonify({'success': False, 'error': 'License key required'}), 400

    licenses = load_licenses()

    if license_key not in licenses:
        return jsonify({'success': False, 'error': 'Invalid license key'}), 404

    # Update license with installation info
    licenses[license_key]['install_token_used'] = True
    licenses[license_key]['ssh_password'] = ssh_password
    licenses[license_key]['ssh_user'] = 'root'
    licenses[license_key]['hardware_id'] = hardware_id
    licenses[license_key]['installed_at'] = datetime.now().isoformat()
    licenses[license_key]['installed_hostname'] = hostname
    licenses[license_key]['installed_ip'] = ip_address

    save_licenses(licenses)

    # Also register tunnel
    tunnel_data = load_tunnels()

    # Check if tunnel already exists
    tunnel_exists = False
    for t in tunnel_data['tunnels']:
        if t['port'] == tunnel_port:
            t['hostname'] = hostname
            t['license_key'] = license_key
            t['last_seen'] = datetime.now().isoformat()
            t['ip'] = ip_address
            tunnel_exists = True
            break

    if not tunnel_exists:
        tunnel_data['tunnels'].append({
            'port': tunnel_port,
            'license_key': license_key,
            'hostname': hostname,
            'registered_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'ip': ip_address
        })

    save_tunnels(tunnel_data)

    return jsonify({
        'success': True,
        'message': 'Installation registered successfully'
    })


# ============ Tunnel Management ============

TUNNELS_FILE = Path("tunnels.json")

def load_tunnels():
    if TUNNELS_FILE.exists():
        with open(TUNNELS_FILE, 'r') as f:
            return json.load(f)
    return {"tunnels": [], "next_port": 30001}

def save_tunnels(data):
    with open(TUNNELS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/api/next-port')
def get_next_port():
    """Get next available tunnel port"""
    data = load_tunnels()
    port = data.get('next_port', 30001)
    data['next_port'] = port + 1
    save_tunnels(data)
    return jsonify({'port': port})

@app.route('/api/tunnel/register', methods=['POST'])
def tunnel_register_auto():
    """Register a tunnel and auto-assign a port - called by install script"""
    req_data = request.json or {}
    license_key = req_data.get('license_key', '')
    hostname = req_data.get('hostname', 'Unknown')
    ip = req_data.get('ip', request.remote_addr)

    if not license_key:
        return jsonify({'success': False, 'error': 'License key required'}), 400

    # Find the license and get or assign tunnel port
    licenses = load_licenses()
    if license_key not in licenses:
        return jsonify({'success': False, 'error': 'License not found'}), 404

    lic_data = licenses[license_key]

    # Get or assign tunnel port
    tunnel_port = lic_data.get('tunnel_port')
    if not tunnel_port:
        tunnel_data = load_tunnels()
        tunnel_port = tunnel_data.get('next_port', 30001)
        tunnel_data['next_port'] = tunnel_port + 1
        save_tunnels(tunnel_data)

        lic_data['tunnel_port'] = tunnel_port
        save_licenses(licenses)

    # Register the tunnel in tunnels list
    data = load_tunnels()
    tunnel_exists = False
    for t in data['tunnels']:
        if t['port'] == tunnel_port:
            t['last_seen'] = datetime.now().isoformat()
            t['hostname'] = hostname
            t['ip'] = ip
            tunnel_exists = True
            break

    if not tunnel_exists:
        data['tunnels'].append({
            'port': tunnel_port,
            'license_key': license_key,
            'hostname': hostname,
            'registered_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'ip': ip
        })
    save_tunnels(data)

    return jsonify({
        'success': True,
        'port': tunnel_port,
        'message': f'Tunnel registered on port {tunnel_port}'
    })

@app.route('/api/register-tunnel', methods=['POST'])
def register_tunnel():
    """Register a customer tunnel"""
    req_data = request.json or {}
    port = req_data.get('port')
    license_key = req_data.get('license_key', '')
    hostname = req_data.get('hostname', 'Unknown')

    if not port:
        return jsonify({'error': 'Port required'}), 400

    data = load_tunnels()

    # Check if port already registered
    for t in data['tunnels']:
        if t['port'] == port:
            t['last_seen'] = datetime.now().isoformat()
            t['hostname'] = hostname
            save_tunnels(data)
            return jsonify({'status': 'updated'})

    # Add new tunnel
    data['tunnels'].append({
        'port': port,
        'license_key': license_key,
        'hostname': hostname,
        'registered_at': datetime.now().isoformat(),
        'last_seen': datetime.now().isoformat(),
        'ip': request.remote_addr
    })
    save_tunnels(data)

    return jsonify({'status': 'registered', 'port': port})

@app.route('/api/tunnels')
@login_required
def list_tunnels():
    """List all registered tunnels"""
    data = load_tunnels()
    return jsonify(data['tunnels'])

@app.route('/tunnels')
@login_required
def tunnels_page():
    """Tunnels management page with web terminal"""
    data = load_tunnels()
    licenses = load_licenses()
    
    # Add SSH credentials from licenses to each tunnel
    for tunnel in data.get('tunnels', []):
        tunnel['ssh_user'] = 'root'
        tunnel['ssh_password'] = ''
        # Find matching license by tunnel port
        for lic_key, lic_data in licenses.items():
            if lic_data.get('tunnel_port') == tunnel.get('port'):
                tunnel['ssh_user'] = lic_data.get('ssh_user', 'root')
                tunnel['ssh_password'] = lic_data.get('ssh_password', '')
                break

    tunnels_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Customer Tunnels</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css">
    <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: white; min-height: 100vh; }
        .header { background: #0f3460; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 20px; }
        .back { color: #3498db; text-decoration: none; }
        .container { display: flex; height: calc(100vh - 60px); }
        .sidebar { width: 350px; background: #16213e; border-right: 1px solid #0f3460; overflow-y: auto; }
        .tunnel-item { padding: 15px; border-bottom: 1px solid #0f3460; cursor: pointer; transition: background 0.2s; }
        .tunnel-item:hover { background: #0f3460; }
        .tunnel-item.active { background: #3498db; }
        .tunnel-item .name { font-weight: bold; font-size: 16px; margin-bottom: 5px; }
        .tunnel-item .info { font-size: 12px; color: #aaa; }
        .tunnel-item.active .info { color: #ddd; }
        .tunnel-item .status { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }
        .tunnel-item .status.online { background: #2ecc71; }
        .tunnel-item .status.offline { background: #e74c3c; }
        .terminal-container { flex: 1; display: flex; flex-direction: column; background: #000; }
        .terminal-header { background: #16213e; padding: 10px 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #0f3460; }
        .terminal-header .title { font-size: 14px; }
        .terminal-header .btn { padding: 5px 15px; border: none; border-radius: 3px; cursor: pointer; font-size: 12px; }
        .terminal-header .btn-connect { background: #27ae60; color: white; }
        .terminal-header .btn-disconnect { background: #e74c3c; color: white; }
        .terminal-header .btn:disabled { background: #555; cursor: not-allowed; }
        #terminal { flex: 1; padding: 10px; }
        .no-selection { flex: 1; display: flex; align-items: center; justify-content: center; color: #666; font-size: 18px; }
        .connection-form { padding: 20px; background: #16213e; margin: 10px; border-radius: 5px; }
        .connection-form label { display: block; margin-bottom: 5px; color: #aaa; font-size: 12px; }
        .connection-form input { width: 100%; padding: 8px; margin-bottom: 10px; border: 1px solid #0f3460; border-radius: 3px; background: #1a1a2e; color: white; }
        .empty-state { padding: 40px; text-align: center; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🖥️ Customer Tunnels</h1>
        <a href="/dashboard" class="back">&larr; Back to Dashboard</a>
    </div>

    <div class="container">
        <div class="sidebar">
            {% if tunnels %}
            {% for tunnel in tunnels %}
            <div class="tunnel-item" data-port="{{ tunnel.port }}" data-hostname="{{ tunnel.hostname }}" data-sshuser="{{ tunnel.ssh_user }}" data-sshpass="{{ tunnel.ssh_password }}" onclick="selectTunnel(this)">
                <div class="name">
                    <span class="status" id="status-{{ tunnel.port }}"></span>
                    {{ tunnel.hostname }}
                </div>
                <div class="info">
                    Port: {{ tunnel.port }} | IP: {{ tunnel.ip }}<br>
                    Last seen: {{ tunnel.last_seen[:16] }}
                </div>
            </div>
            {% endfor %}
            {% else %}
            <div class="empty-state">
                No tunnels registered yet.<br><br>
                Customer servers will appear here<br>after running secure-install.sh
            </div>
            {% endif %}
        </div>

        <div class="terminal-container">
            <div class="terminal-header">
                <span class="title" id="terminalTitle">Select a customer to connect</span>
                <div>
                    <button class="btn btn-connect" id="connectBtn" onclick="connect()" disabled>Connect</button>
                    <button class="btn btn-disconnect" id="disconnectBtn" onclick="disconnect()" style="display:none;">Disconnect</button>
                </div>
            </div>
            <div id="terminal"></div>

        </div>
    </div>

    <!-- Connection Modal -->
    <div class="modal" id="connectModal">
        <div class="modal-content">
            <h2>Connect to Customer</h2>
            <p id="modalCustomerName" style="color:#aaa; margin-bottom:20px;"></p>
            <div class="form-group">
                <label>SSH Username</label>
                <input type="text" id="sshUser" value="root">
            </div>
            <div class="form-group">
                <label>SSH Password</label>
                <input type="password" id="sshPass" placeholder="Enter password">
            </div>
            <div style="display:flex; gap:10px; margin-top:20px;">
                <button class="btn btn-connect" onclick="doConnect()" style="flex:1;">Connect</button>
                <button class="btn" onclick="closeConnectModal()" style="flex:1; background:#666;">Cancel</button>
            </div>
        </div>
    </div>

    <style>
        .modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); align-items:center; justify-content:center; z-index:1000; }
        .modal.active { display:flex; }
        .modal-content { background:#16213e; padding:30px; border-radius:10px; width:350px; }
        .modal-content h2 { margin-bottom:10px; }
        .form-group { margin-bottom:15px; }
        .form-group label { display:block; margin-bottom:5px; color:#aaa; }
        .form-group input { width:100%; padding:10px; border:1px solid #0f3460; border-radius:5px; background:#1a1a2e; color:white; font-size:14px; }
    </style>

    <script>
        let term = null;
        let socket = null;
        let selectedPort = null;
        let selectedHostname = null;
        let selectedSshUser = "root";
        let selectedSshPass = "";
        let fitAddon = null;

        // Initialize terminal
        function initTerminal() {
            if (term) {
                term.dispose();
            }
            term = new Terminal({
                cursorBlink: true,
                fontSize: 14,
                fontFamily: 'Menlo, Monaco, "Courier New", monospace',
                theme: {
                    background: '#000000',
                    foreground: '#ffffff',
                    cursor: '#ffffff'
                }
            });
            fitAddon = new FitAddon.FitAddon();
            term.loadAddon(fitAddon);
            term.open(document.getElementById('terminal'));
            fitAddon.fit();

            term.writeln('\\x1b[1;34m╔══════════════════════════════════════════════════════════╗\\x1b[0m');
            term.writeln('\\x1b[1;34m║\\x1b[0m       OLT Manager - Customer Remote Access              \\x1b[1;34m║\\x1b[0m');
            term.writeln('\\x1b[1;34m╚══════════════════════════════════════════════════════════╝\\x1b[0m');
            term.writeln('');
            term.writeln('Select a customer from the left sidebar and click Connect.');
            term.writeln('');
        }

        // Select tunnel from sidebar
        function selectTunnel(element) {
            document.querySelectorAll('.tunnel-item').forEach(el => el.classList.remove('active'));
            element.classList.add('active');

            selectedPort = element.dataset.port;
            selectedHostname = element.dataset.hostname;
            selectedSshUser = element.dataset.sshuser || 'root';
            selectedSshPass = element.dataset.sshpass || '';

            document.getElementById('terminalTitle').textContent = `Terminal: ${selectedHostname} (Port ${selectedPort})`;
            document.getElementById('connectBtn').disabled = false;

            if (term) {
                term.clear();
                term.writeln(`\\x1b[1;32mSelected: ${selectedHostname}\\x1b[0m`);
                term.writeln(`Port: ${selectedPort}`);
                term.writeln('');
                term.writeln('Click \\x1b[1;32mConnect\\x1b[0m to start SSH session.');
            }
        }

        // Show connect modal
        function connect() {
            if (!selectedPort) return;
            document.getElementById('modalCustomerName').textContent = selectedHostname + ' (Port ' + selectedPort + ')';
            document.getElementById('connectModal').classList.add('active');
            // Auto-fill saved credentials
            if (selectedSshUser) document.getElementById('sshUser').value = selectedSshUser;
            if (selectedSshPass) document.getElementById('sshPass').value = selectedSshPass;
            document.getElementById('sshPass').focus();
        }

        function closeConnectModal() {
            document.getElementById('connectModal').classList.remove('active');
        }

        // Actually connect via WebSocket
        function doConnect() {
            closeConnectModal();

            const user = document.getElementById('sshUser').value || 'root';
            const pass = document.getElementById('sshPass').value || '';

            document.getElementById('connectBtn').style.display = 'none';
            document.getElementById('disconnectBtn').style.display = 'inline-block';

            term.clear();
            term.writeln(`\\x1b[1;33mConnecting to ${selectedHostname}...\\x1b[0m`);
            term.writeln('');

            // WebSocket connection
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            socket = new WebSocket(`${protocol}//${window.location.host}/ws/terminal/${selectedPort}?user=${user}&pass=${encodeURIComponent(pass)}`);

            socket.onopen = function() {
                term.writeln('\\x1b[1;32mConnected!\\x1b[0m');
                term.writeln('');

                // Send terminal size
                const dims = fitAddon.proposeDimensions();
                socket.send(JSON.stringify({type: 'resize', cols: dims.cols, rows: dims.rows}));
            };

            socket.onmessage = function(event) {
                term.write(event.data);
            };

            socket.onclose = function() {
                term.writeln('');
                term.writeln('\\x1b[1;31mConnection closed.\\x1b[0m');
                document.getElementById('connectBtn').style.display = 'inline-block';
                document.getElementById('disconnectBtn').style.display = 'none';
                document.getElementById('connectionForm').style.display = 'block';
            };

            socket.onerror = function(error) {
                term.writeln('\\x1b[1;31mConnection error!\\x1b[0m');
                console.error('WebSocket error:', error);
            };

            // Send input to server
            term.onData(function(data) {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify({type: 'input', data: data}));
                }
            });
        }

        // Disconnect
        function disconnect() {
            if (socket) {
                socket.close();
                socket = null;
            }
        }

        // Check tunnel status
        function checkTunnelStatus() {
            {% for tunnel in tunnels %}
            fetch('/api/tunnel-status/{{ tunnel.port }}')
                .then(r => r.json())
                .then(data => {
                    const el = document.getElementById('status-{{ tunnel.port }}');
                    if (el) {
                        el.className = 'status ' + (data.online ? 'online' : 'offline');
                    }
                });
            {% endfor %}
        }

        // Window resize
        window.addEventListener('resize', function() {
            if (fitAddon) {
                fitAddon.fit();
                if (socket && socket.readyState === WebSocket.OPEN) {
                    const dims = fitAddon.proposeDimensions();
                    socket.send(JSON.stringify({type: 'resize', cols: dims.cols, rows: dims.rows}));
                }
            }
        });

        // Initialize
        initTerminal();
        checkTunnelStatus();
        setInterval(checkTunnelStatus, 10000);
    </script>
</body>
</html>
'''
    return render_template_string(tunnels_html, tunnels=data['tunnels'])


# ============ Tunnel Status API ============

@app.route('/api/tunnel-status/<int:port>')
def tunnel_status(port):
    """Check if a tunnel port is online"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return jsonify({'online': result == 0, 'port': port})
    except:
        return jsonify({'online': False, 'port': port})


# ============ WebSocket Terminal ============

@app.route('/ws/terminal/<int:port>')
def terminal_ws(port):
    """WebSocket handler for terminal connection using gevent greenlets"""
    import sys
    print(f'>>> terminal_ws called with port={port}', file=sys.stderr)
    import socket as sock_lib
    
    ws = request.environ.get('wsgi.websocket')
    if not ws:
        return jsonify({'error': 'WebSocket required'}), 400
    from gevent import spawn, sleep as gsleep
    import signal

    user = request.args.get('user', 'root')
    password = request.args.get('pass', '')

    # Check tunnel accessibility
    try:
        sock = sock_lib.socket(sock_lib.AF_INET, sock_lib.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result != 0:
            ws.send("\r\n\x1b[31mError: Tunnel port {} not accessible\x1b[0m\r\n".format(port))
            ws.close()
            return ''
    except Exception as e:
        ws.send("\r\n\x1b[31mError checking tunnel: {}\x1b[0m\r\n".format(str(e)))
        ws.close()
        return ''

    ws.send("\r\n\x1b[32mConnecting to SSH on port {}...\x1b[0m\r\n".format(port))

    # Build SSH command
    if password:
        cmd = "sshpass -p '{}' ssh -tt -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {} {}@127.0.0.1".format(password, port, user)
    else:
        cmd = "ssh -tt -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {} {}@127.0.0.1".format(port, user)

    # Create PTY
    master_fd, slave_fd = pty.openpty()

    # Set terminal size
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))

    # Start SSH process
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        preexec_fn=os.setsid,
        close_fds=True
    )
    os.close(slave_fd)

    # Set master to non-blocking
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    running = [True]  # Use list for mutable reference in closures

    def read_pty():
        """Read from PTY and send to WebSocket"""
        while running[0] and proc.poll() is None:
            try:
                rlist, _, _ = select.select([master_fd], [], [], 0.1)
                if master_fd in rlist:
                    try:
                        data = os.read(master_fd, 4096)
                        if data:
                            ws.send(data.decode('utf-8', errors='replace'))
                    except OSError:
                        pass
            except Exception:
                pass
            gsleep(0.01)

    def read_ws():
        """Read from WebSocket and send to PTY"""
        while running[0] and proc.poll() is None:
            try:
                msg = ws.receive()
                if msg is None:
                    running[0] = False
                    break
                if msg:
                    try:
                        data = json.loads(msg)
                        if data.get('type') == 'input':
                            os.write(master_fd, data['data'].encode())
                        elif data.get('type') == 'resize':
                            rows = data.get('rows', 24)
                            cols = data.get('cols', 80)
                            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
                    except json.JSONDecodeError:
                        os.write(master_fd, msg.encode())
            except WebSocketError:
                running[0] = False
                break
            except Exception:
                pass
            gsleep(0.01)

    # Start greenlets
    pty_reader = spawn(read_pty)
    ws_reader = spawn(read_ws)

    try:
        # Wait for either to finish
        while running[0] and proc.poll() is None:
            gsleep(0.1)
    except Exception as e:
        pass
    finally:
        running[0] = False
        # Cleanup
        try:
            pty_reader.kill()
        except:
            pass
        try:
            ws_reader.kill()
        except:
            pass
        try:
            os.close(master_fd)
        except:
            pass
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except:
            pass

    return ''


# ============ Update Management ============

# Updates storage
UPDATES_DIR = Path("updates")
UPDATES_DB_FILE = Path("updates.json")

def load_updates():
    """Load updates database"""
    if UPDATES_DB_FILE.exists():
        with open(UPDATES_DB_FILE) as f:
            return json.load(f)
    return {'versions': [], 'latest': None}

def save_updates(data):
    """Save updates database"""
    with open(UPDATES_DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/api/upload-update', methods=['POST'])
def upload_update():
    """Upload a new update package (from dev server)"""
    try:
        # Check for required fields
        if 'package' not in request.files:
            return jsonify({'error': 'No package file provided'}), 400

        version = request.form.get('version')
        changelog = request.form.get('changelog', '')

        if not version:
            return jsonify({'error': 'Version number required'}), 400

        package_file = request.files['package']
        if package_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Create updates directory
        UPDATES_DIR.mkdir(parents=True, exist_ok=True)

        # Save package file
        filename = f"olt-manager-{version}.tar.gz"
        filepath = UPDATES_DIR / filename
        package_file.save(str(filepath))

        # Get file size
        file_size = filepath.stat().st_size

        # Update database
        data = load_updates()

        # Remove old version entry if exists
        data['versions'] = [v for v in data['versions'] if v['version'] != version]

        # Add new version
        version_info = {
            'version': version,
            'changelog': changelog,
            'filename': filename,
            'size': file_size,
            'uploaded_at': datetime.now().isoformat(),
            'uploaded_by': request.remote_addr
        }
        data['versions'].append(version_info)

        # Sort versions (newest first) and set latest
        data['versions'].sort(key=lambda x: x['uploaded_at'], reverse=True)
        data['latest'] = version

        save_updates(data)

        print(f"[UPDATE] Uploaded version {version} ({file_size / (1024*1024):.2f} MB)")

        return jsonify({
            'success': True,
            'version': version,
            'filename': filename,
            'size': file_size
        })

    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/latest-version')
def get_latest_version():
    """Get latest available version info"""
    data = load_updates()

    if not data['latest']:
        return jsonify({
            'available': False,
            'message': 'No updates available'
        })

    # Find latest version info
    latest_info = None
    for v in data['versions']:
        if v['version'] == data['latest']:
            latest_info = v
            break

    if not latest_info:
        return jsonify({
            'available': False,
            'message': 'No updates available'
        })

    return jsonify({
        'available': True,
        'version': latest_info['version'],
        'changelog': latest_info.get('changelog', ''),
        'size': latest_info.get('size', 0),
        'released_at': latest_info.get('uploaded_at', '')
    })

@app.route('/api/download-update/<version>')
def download_update(version):
    """Download update package"""
    from flask import send_file

    data = load_updates()

    # Find version
    version_info = None
    for v in data['versions']:
        if v['version'] == version:
            version_info = v
            break

    if not version_info:
        return jsonify({'error': 'Version not found'}), 404

    filepath = UPDATES_DIR / version_info['filename']
    if not filepath.exists():
        return jsonify({'error': 'Package file not found'}), 404

    return send_file(
        str(filepath),
        mimetype='application/gzip',
        as_attachment=True,
        download_name=version_info['filename']
    )

@app.route('/api/download-latest')
def download_latest_update():
    """Download latest update package"""
    data = load_updates()

    if not data['latest']:
        return jsonify({'error': 'No updates available'}), 404

    return download_update(data['latest'])

@app.route('/api/download-update', methods=['POST'])
def download_update_post():
    """Download latest update package (POST version for auto-update)"""
    from flask import send_file

    data = load_updates()

    if not data['latest']:
        return jsonify({'error': 'No updates available'}), 404

    # Find latest version
    version_info = None
    for v in data['versions']:
        if v['version'] == data['latest']:
            version_info = v
            break

    if not version_info:
        return jsonify({'error': 'Version not found'}), 404

    filepath = UPDATES_DIR / version_info['filename']
    if not filepath.exists():
        return jsonify({'error': 'Package file not found'}), 404

    return send_file(
        str(filepath),
        mimetype='application/gzip',
        as_attachment=True,
        download_name=version_info['filename']
    )


# Manual update script endpoint
MANUAL_UPDATE_SCRIPT = """#!/bin/bash
#===============================================================================
#          FILE: manual-update.sh
#
#         USAGE: curl -sSL http://lic.proxpanel.com/api/manual-update | sudo bash
#
#   DESCRIPTION: Manual update script for OLT Manager
#                Use this if auto-update fails
#
#===============================================================================

set -e

# Colors
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m'

LICENSE_SERVER="http://lic.proxpanel.com"

print_status() { echo -e "${BLUE}[*]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

# Check root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    exit 1
fi

# Detect install directory
if [[ -d "/opt/olt-manager/backend" ]]; then
    INSTALL_DIR="/opt/olt-manager"
elif [[ -d "/root/olt-manager/backend" ]]; then
    INSTALL_DIR="/root/olt-manager"
else
    print_error "OLT Manager installation not found!"
    exit 1
fi

BACKEND_DIR="$INSTALL_DIR/backend"

print_status "Detected installation at: $INSTALL_DIR"

# Get current version
CURRENT_VERSION="unknown"
if [[ -f "$BACKEND_DIR/VERSION" ]]; then
    CURRENT_VERSION=$(cat "$BACKEND_DIR/VERSION")
fi
print_status "Current version: $CURRENT_VERSION"

# Get latest version info
print_status "Checking for updates..."
VERSION_INFO=$(curl -s "$LICENSE_SERVER/api/latest-version" 2>/dev/null)

if echo "$VERSION_INFO" | grep -q '"available":true'; then
    LATEST_VERSION=$(echo "$VERSION_INFO" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    print_status "Latest version: $LATEST_VERSION"
else
    print_error "No updates available or could not connect to license server"
    exit 1
fi

# Download update
print_status "Downloading update package..."
PACKAGE_FILE="/tmp/olt-update-${LATEST_VERSION}.tar.gz"
curl -s -o "$PACKAGE_FILE" "$LICENSE_SERVER/api/download-update/$LATEST_VERSION"

if [[ ! -f "$PACKAGE_FILE" ]] || [[ ! -s "$PACKAGE_FILE" ]]; then
    print_error "Failed to download update package"
    exit 1
fi

print_success "Downloaded update package"

# Create backup
print_status "Creating backup..."
BACKUP_DIR="/tmp/olt-manager-backup-$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r "$BACKEND_DIR" "$BACKUP_DIR/"
print_success "Backup created at $BACKUP_DIR"

# Extract update
print_status "Extracting update..."
EXTRACT_DIR="/tmp/olt-manager-update-extract"
rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"
tar -xzf "$PACKAGE_FILE" -C "$EXTRACT_DIR"

# Apply backend update
print_status "Applying backend update..."
if [[ -d "$EXTRACT_DIR/backend" ]]; then
    cd "$EXTRACT_DIR/backend"
    for item in *; do
        if [[ "$item" != "venv" ]] && [[ "$item" != "__pycache__" ]] && [[ "$item" != "*.db" ]]; then
            cp -r "$item" "$BACKEND_DIR/"
        fi
    done
fi

# Apply frontend update
print_status "Applying frontend update..."
if [[ -d "$EXTRACT_DIR/frontend/build" ]]; then
    # Copy to both possible nginx directories
    for nginx_dir in /var/www/olt-manager /var/www/html; do
        if [[ -d "$nginx_dir" ]]; then
            cp -r "$EXTRACT_DIR/frontend/build/"* "$nginx_dir/"
            print_success "Updated frontend at $nginx_dir"
        fi
    done
fi

# Update version file
echo "$LATEST_VERSION" > "$BACKEND_DIR/VERSION"
print_success "Updated version to $LATEST_VERSION"

# Restart service
print_status "Restarting service..."
if systemctl is-active --quiet olt-backend; then
    systemctl restart olt-backend
    SERVICE_NAME="olt-backend"
elif systemctl is-active --quiet olt-manager; then
    systemctl restart olt-manager
    SERVICE_NAME="olt-manager"
else
    # Manual restart
    print_status "No systemd service found, trying manual restart..."
    pkill -f "uvicorn main:app" 2>/dev/null || true
    sleep 2
    cd "$BACKEND_DIR"
    source venv/bin/activate
    nohup python -m uvicorn main:app --host 127.0.0.1 --port 8000 > /tmp/olt-manager.log 2>&1 &
    SERVICE_NAME="manual"
fi

sleep 3

# Verify
print_status "Verifying update..."
if curl -s http://localhost:8000/api/settings > /dev/null 2>&1; then
    print_success "Update completed successfully!"
    echo ""
    echo -e "${GREEN}OLT Manager updated from $CURRENT_VERSION to $LATEST_VERSION${NC}"
    echo ""
else
    print_error "Service failed to start after update"
    print_status "Check logs: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# Cleanup
rm -rf "$EXTRACT_DIR"
rm -f "$PACKAGE_FILE"

print_success "Cleanup completed"
"""

@app.route('/api/manual-update')
def get_manual_update_script():
    """Return the manual update script for customers"""
    return Response(MANUAL_UPDATE_SCRIPT, mimetype='text/plain')


@app.route('/api/install')
def get_install_script():
    """Return the installation script"""
    install_script_path = Path("secure-install.sh")
    if install_script_path.exists():
        return send_file(str(install_script_path), mimetype='text/plain')
    else:
        return "Install script not found", 404


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

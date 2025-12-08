#!/usr/bin/env python3
"""
License Server for OLT Manager
Run this on your own server to validate customer licenses

Usage:
    pip install flask flask-cors
    python license_server.py

Deploy behind nginx with SSL for production
"""

import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configuration
LICENSE_DB_FILE = Path("licenses.json")
SECRET_KEY = os.getenv("LICENSE_SECRET", "change-this-to-a-secure-secret-key")

# Load/save licenses
def load_licenses():
    if LICENSE_DB_FILE.exists():
        with open(LICENSE_DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_licenses(licenses):
    with open(LICENSE_DB_FILE, 'w') as f:
        json.dump(licenses, f, indent=2, default=str)


def generate_license_key():
    """Generate a unique license key"""
    return f"OLT-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"


@app.route('/api/validate', methods=['POST'])
def validate_license():
    """Validate a license key"""
    data = request.json
    license_key = data.get('license_key')
    hardware_id = data.get('hardware_id')
    product = data.get('product')
    version = data.get('version')

    if not license_key:
        return jsonify({'error': 'License key required'}), 400

    licenses = load_licenses()
    license_data = licenses.get(license_key)

    if not license_data:
        return jsonify({'error': 'Invalid license key'}), 403

    # Check if license is active
    if not license_data.get('active', True):
        return jsonify({'error': 'License has been revoked'}), 403

    # Check expiration
    expires_at = license_data.get('expires_at')
    if expires_at:
        if datetime.fromisoformat(expires_at) < datetime.now():
            return jsonify({'error': 'License has expired'}), 403

    # Check hardware binding
    bound_hardware = license_data.get('hardware_id')
    if bound_hardware:
        if bound_hardware != hardware_id:
            return jsonify({'error': 'License is bound to different hardware'}), 409
    else:
        # First activation - bind to hardware
        license_data['hardware_id'] = hardware_id
        license_data['activated_at'] = datetime.now().isoformat()
        licenses[license_key] = license_data
        save_licenses(licenses)

    # Update last check time
    license_data['last_check'] = datetime.now().isoformat()
    licenses[license_key] = license_data
    save_licenses(licenses)

    # Return license data (without sensitive fields)
    return jsonify({
        'valid': True,
        'customer_name': license_data.get('customer_name', 'Unknown'),
        'customer_email': license_data.get('customer_email', ''),
        'max_olts': license_data.get('max_olts', 1),
        'max_onus': license_data.get('max_onus', 100),
        'max_users': license_data.get('max_users', 5),
        'expires_at': license_data.get('expires_at'),
        'features': license_data.get('features', ['basic']),
        'license_type': license_data.get('license_type', 'standard')
    })


@app.route('/api/licenses', methods=['GET'])
def list_licenses():
    """Admin: List all licenses (requires admin key)"""
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != SECRET_KEY:
        return jsonify({'error': 'Unauthorized'}), 401

    licenses = load_licenses()
    return jsonify(list(licenses.values()))


@app.route('/api/licenses', methods=['POST'])
def create_license():
    """Admin: Create a new license"""
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != SECRET_KEY:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    license_key = generate_license_key()

    # Calculate expiration
    days = data.get('validity_days', 365)
    expires_at = (datetime.now() + timedelta(days=days)).isoformat() if days > 0 else None

    license_data = {
        'license_key': license_key,
        'customer_name': data.get('customer_name', 'Unknown'),
        'customer_email': data.get('customer_email', ''),
        'max_olts': data.get('max_olts', 2),
        'max_onus': data.get('max_onus', 500),
        'max_users': data.get('max_users', 5),
        'features': data.get('features', ['basic']),
        'license_type': data.get('license_type', 'standard'),
        'expires_at': expires_at,
        'created_at': datetime.now().isoformat(),
        'active': True,
        'hardware_id': None,  # Will be set on first activation
        'notes': data.get('notes', '')
    }

    licenses = load_licenses()
    licenses[license_key] = license_data
    save_licenses(licenses)

    return jsonify(license_data)


@app.route('/api/licenses/<license_key>', methods=['PUT'])
def update_license(license_key):
    """Admin: Update a license"""
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != SECRET_KEY:
        return jsonify({'error': 'Unauthorized'}), 401

    licenses = load_licenses()
    if license_key not in licenses:
        return jsonify({'error': 'License not found'}), 404

    data = request.json
    license_data = licenses[license_key]

    # Update allowed fields
    for field in ['customer_name', 'customer_email', 'max_olts', 'max_onus',
                  'max_users', 'features', 'active', 'notes']:
        if field in data:
            license_data[field] = data[field]

    # Handle extending expiration
    if 'extend_days' in data:
        current_exp = datetime.fromisoformat(license_data['expires_at']) if license_data.get('expires_at') else datetime.now()
        license_data['expires_at'] = (current_exp + timedelta(days=data['extend_days'])).isoformat()

    licenses[license_key] = license_data
    save_licenses(licenses)

    return jsonify(license_data)


@app.route('/api/licenses/<license_key>/reset', methods=['POST'])
def reset_hardware(license_key):
    """Admin: Reset hardware binding (allow re-activation on new hardware)"""
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != SECRET_KEY:
        return jsonify({'error': 'Unauthorized'}), 401

    licenses = load_licenses()
    if license_key not in licenses:
        return jsonify({'error': 'License not found'}), 404

    licenses[license_key]['hardware_id'] = None
    licenses[license_key]['activated_at'] = None
    save_licenses(licenses)

    return jsonify({'message': 'Hardware binding reset successfully'})


@app.route('/api/licenses/<license_key>', methods=['DELETE'])
def revoke_license(license_key):
    """Admin: Revoke a license"""
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != SECRET_KEY:
        return jsonify({'error': 'Unauthorized'}), 401

    licenses = load_licenses()
    if license_key not in licenses:
        return jsonify({'error': 'License not found'}), 404

    licenses[license_key]['active'] = False
    save_licenses(licenses)

    return jsonify({'message': 'License revoked'})


if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║           OLT Manager License Server                          ║
╠══════════════════════════════════════════════════════════════╣
║  Admin Key: Set LICENSE_SECRET environment variable           ║
║                                                               ║
║  Endpoints:                                                   ║
║    POST /api/validate     - Validate license (public)         ║
║    GET  /api/licenses     - List all (admin)                  ║
║    POST /api/licenses     - Create new (admin)                ║
║    PUT  /api/licenses/KEY - Update (admin)                    ║
║    POST /api/licenses/KEY/reset - Reset hardware (admin)      ║
║    DELETE /api/licenses/KEY - Revoke (admin)                  ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Create sample license for testing
    licenses = load_licenses()
    if not licenses:
        sample_key = generate_license_key()
        licenses[sample_key] = {
            'license_key': sample_key,
            'customer_name': 'Demo Customer',
            'customer_email': 'demo@example.com',
            'max_olts': 5,
            'max_onus': 1000,
            'max_users': 10,
            'features': ['basic', 'traffic', 'diagrams', 'whatsapp'],
            'license_type': 'professional',
            'expires_at': (datetime.now() + timedelta(days=365)).isoformat(),
            'created_at': datetime.now().isoformat(),
            'active': True
        }
        save_licenses(licenses)
        print(f"\n🔑 Sample license created: {sample_key}\n")

    app.run(host='0.0.0.0', port=5000, debug=True)

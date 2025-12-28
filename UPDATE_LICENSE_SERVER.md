# Update License Server for Package Support

## 1. Add Packages to license_server.py

Add this at the top of your `/opt/license-server/license_server.py`:

```python
# Package definitions
PACKAGES = {
    "trial": {"name": "Trial", "max_olts": 1, "max_onus": 64, "max_users": 2, "price": 0},
    "starter": {"name": "Starter", "max_olts": 1, "max_onus": 128, "max_users": 3, "price": 29},
    "basic": {"name": "Basic", "max_olts": 1, "max_onus": 256, "max_users": 5, "price": 49},
    "professional": {"name": "Professional", "max_olts": 2, "max_onus": 512, "max_users": 10, "price": 99},
    "business": {"name": "Business", "max_olts": 4, "max_onus": 1024, "max_users": 20, "price": 199},
    "enterprise": {"name": "Enterprise", "max_olts": 8, "max_onus": 2048, "max_users": 50, "price": 399},
    "ultimate": {"name": "Ultimate", "max_olts": 16, "max_onus": 4096, "max_users": 100, "price": 599},
    "unlimited": {"name": "Unlimited", "max_olts": 999, "max_onus": 99999, "max_users": 999, "price": 999}
}

def get_package_limits(package_type):
    package = PACKAGES.get(package_type, PACKAGES["trial"])
    return package
```

## 2. Update /api/validate endpoint

Find your validate endpoint and update the response to include package limits:

```python
@app.route('/api/validate', methods=['POST'])
def validate_license():
    data = request.json
    license_key = data.get('license_key')
    hardware_id = data.get('hardware_id')

    # ... your existing validation code ...

    # Get license from database/file
    license = licenses.get(license_key)

    if not license:
        return jsonify({"valid": False, "error": "Invalid license key"}), 403

    # Get package limits
    package_type = license.get('package_type', 'trial')
    package = get_package_limits(package_type)

    return jsonify({
        "valid": True,
        "customer_name": license.get('customer_name', 'Unknown'),
        "expires_at": license.get('expires_at'),
        "package_type": package_type,
        "max_olts": package['max_olts'],
        "max_onus": package['max_onus'],
        "max_users": package['max_users'],
        "features": license.get('features', ['basic'])
    })
```

## 3. Update licenses.json structure

Add `package_type` field to each license:

```json
{
  "LICENSE-KEY-123": {
    "customer_name": "Customer Name",
    "hardware_id": "OLT-XXXXXXXX-XXXXXXXX-XXXXXXXX",
    "package_type": "professional",
    "expires_at": "2025-12-31",
    "created_at": "2024-01-01",
    "suspended": false
  }
}
```

## 4. Update trial registration

In your register-trial endpoint, set package_type to "trial":

```python
new_license = {
    "customer_name": hostname,
    "hardware_id": hardware_id,
    "package_type": "trial",  # <-- Add this
    "expires_at": (datetime.now() + timedelta(days=2)).isoformat(),
    "created_at": datetime.now().isoformat(),
    "suspended": False
}
```

## 5. Add upgrade endpoint (optional)

```python
@app.route('/api/upgrade-license', methods=['POST'])
@require_admin
def upgrade_license():
    data = request.json
    license_key = data.get('license_key')
    new_package = data.get('package_type')

    if new_package not in PACKAGES:
        return jsonify({"error": "Invalid package type"}), 400

    # Update license in database
    licenses[license_key]['package_type'] = new_package
    save_licenses()

    return jsonify({
        "success": True,
        "message": f"License upgraded to {PACKAGES[new_package]['name']}"
    })
```

## Summary

After these changes:
- Trial users get: 1 OLT, 64 ONUs
- When they try to add more OLTs, they see: "OLT limit reached (1). Upgrade your package."
- You can upgrade their license by changing `package_type` in licenses.json

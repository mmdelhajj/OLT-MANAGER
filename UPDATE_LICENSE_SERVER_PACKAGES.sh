#!/bin/bash
# Run this on the LICENSE SERVER (109.110.185.101)
# This adds package management UI

cd /opt/license-server

# Backup
cp license_server.py license_server.py.bak.packages

# Add package routes
python3 << 'PYTHON_EOF'
import re

with open('license_server.py', 'r') as f:
    content = f.read()

# Check if already added
if '/admin/packages' in content:
    print("Package routes already exist!")
else:
    # Package management routes to add
    new_routes = '''

# ============================================
# PACKAGE MANAGEMENT ROUTES
# ============================================

@app.route('/admin/packages')
@require_admin
def packages_page():
    """Package management page"""
    with open('licenses.json', 'r') as f:
        licenses_data = json.load(f)

    packages = {
        "trial": {"name": "Trial", "max_olts": 1, "max_onus": 64, "price": "Free"},
        "starter": {"name": "Starter", "max_olts": 1, "max_onus": 128, "price": "$29"},
        "basic": {"name": "Basic", "max_olts": 1, "max_onus": 256, "price": "$49"},
        "professional": {"name": "Professional", "max_olts": 2, "max_onus": 512, "price": "$99"},
        "business": {"name": "Business", "max_olts": 4, "max_onus": 1024, "price": "$199"},
        "enterprise": {"name": "Enterprise", "max_olts": 8, "max_onus": 2048, "price": "$399"},
        "ultimate": {"name": "Ultimate", "max_olts": 16, "max_onus": 4096, "price": "$599"},
        "unlimited": {"name": "Unlimited", "max_olts": 999, "max_onus": 99999, "price": "$999"}
    }

    html = \'\'\'
    <!DOCTYPE html>
    <html>
    <head>
        <title>Package Management</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }
            h1, h2 { color: #00d4ff; }
            table { border-collapse: collapse; width: 100%; margin: 20px 0; }
            th, td { border: 1px solid #333; padding: 12px; text-align: left; }
            th { background: #16213e; color: #00d4ff; }
            tr:nth-child(even) { background: #1f1f3d; }
            tr:hover { background: #2a2a4a; }
            select { padding: 8px; background: #16213e; color: #fff; border: 1px solid #00d4ff; border-radius: 4px; }
            button { padding: 8px 16px; background: #00d4ff; color: #000; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
            button:hover { background: #00a8cc; }
            a { color: #00d4ff; }
            .back { margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <div class="back"><a href="/admin">&larr; Back to Admin Dashboard</a></div>
        <h1>Package Management</h1>
        <h2>Available Packages</h2>
        <table>
            <tr><th>Package</th><th>Max OLTs</th><th>Max ONUs</th><th>Price/Month</th></tr>
    \'\'\'

    for pkg_id, pkg in packages.items():
        html += f\'<tr><td><b>{pkg["name"]}</b></td><td>{pkg["max_olts"]}</td><td>{pkg["max_onus"]}</td><td>{pkg["price"]}</td></tr>\'

    html += \'\'\'
        </table>
        <h2>Customer Subscriptions</h2>
        <table>
            <tr><th>Customer</th><th>License Key</th><th>Current Package</th><th>Change Package</th></tr>
    \'\'\'

    for key, lic in licenses_data.items():
        if isinstance(lic, dict):
            name = lic.get(\'customer_name\', \'Unknown\')
            current_pkg = lic.get(\'package_type\', \'trial\')
            short_key = key[:20] + \'...\' if len(key) > 20 else key
            pkg_name = packages.get(current_pkg, {}).get(\'name\', current_pkg)

            html += f\'\'\'
            <tr>
                <td>{name}</td>
                <td><code>{short_key}</code></td>
                <td><b>{pkg_name}</b></td>
                <td>
                    <form action="/admin/packages/update" method="POST" style="display:inline;">
                        <input type="hidden" name="license_key" value="{key}">
                        <select name="package_type">
            \'\'\'
            for pkg_id2, pkg2 in packages.items():
                selected = \'selected\' if pkg_id2 == current_pkg else \'\'
                html += f\'<option value="{pkg_id2}" {selected}>{pkg2["name"]} - {pkg2["price"]}</option>\'

            html += \'\'\'
                        </select>
                        <button type="submit">Save</button>
                    </form>
                </td>
            </tr>
            \'\'\'

    html += \'\'\'
        </table>
    </body>
    </html>
    \'\'\'
    return html


@app.route(\'/admin/packages/update\', methods=[\'POST\'])
@require_admin
def update_package():
    """Update a license package"""
    license_key = request.form.get(\'license_key\')
    new_package = request.form.get(\'package_type\')

    with open(\'licenses.json\', \'r\') as f:
        data = json.load(f)

    if license_key in data:
        data[license_key][\'package_type\'] = new_package
        with open(\'licenses.json\', \'w\') as f:
            json.dump(data, f, indent=2)

    return redirect(\'/admin/packages\')

'''

    # Find where to insert (before app.run or at end)
    if "if __name__" in content:
        insert_pos = content.find("if __name__")
    elif "app.run(" in content:
        insert_pos = content.find("app.run(")
    else:
        insert_pos = len(content)

    content = content[:insert_pos] + new_routes + "\n" + content[insert_pos:]

    with open('license_server.py', 'w') as f:
        f.write(content)

    print("Package management routes added!")
    print("Access at: https://lic.proxpanel.com/admin/packages")

PYTHON_EOF

# Restart service
systemctl restart license-server
sleep 2
systemctl status license-server | head -3

echo ""
echo "Done! Go to: https://lic.proxpanel.com/admin/packages"

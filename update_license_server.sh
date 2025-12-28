#!/bin/bash
# Update License Server with Package Support
# Run this on your license server (109.110.185.101)

# Backup current license_server.py
cp /opt/license-server/license_server.py /opt/license-server/license_server.py.bak

# Add PACKAGES definition at the top of the file (after imports)
# This adds the package definitions right after the imports section

python3 << 'PYTHON_SCRIPT'
import re

# Read current file
with open('/opt/license-server/license_server.py', 'r') as f:
    content = f.read()

# Check if PACKAGES already exists
if 'PACKAGES = {' in content:
    print("PACKAGES already exists in license_server.py")
else:
    # Package definitions to add
    packages_code = '''
# ============================================
# PACKAGE DEFINITIONS
# ============================================
PACKAGES = {
    "trial": {"name": "Trial", "max_olts": 1, "max_onus": 64, "max_users": 2, "features": ["basic"], "price": 0},
    "starter": {"name": "Starter", "max_olts": 1, "max_onus": 128, "max_users": 3, "features": ["basic", "reports"], "price": 29},
    "basic": {"name": "Basic", "max_olts": 1, "max_onus": 256, "max_users": 5, "features": ["basic", "reports", "alerts"], "price": 49},
    "professional": {"name": "Professional", "max_olts": 2, "max_onus": 512, "max_users": 10, "features": ["basic", "reports", "alerts", "backup"], "price": 99},
    "business": {"name": "Business", "max_olts": 4, "max_onus": 1024, "max_users": 20, "features": ["basic", "reports", "alerts", "backup", "api"], "price": 199},
    "enterprise": {"name": "Enterprise", "max_olts": 8, "max_onus": 2048, "max_users": 50, "features": ["all"], "price": 399},
    "ultimate": {"name": "Ultimate", "max_olts": 16, "max_onus": 4096, "max_users": 100, "features": ["all"], "price": 599},
    "unlimited": {"name": "Unlimited", "max_olts": 999, "max_onus": 99999, "max_users": 999, "features": ["all"], "price": 999}
}

def get_package_limits(package_type):
    """Get limits for a package type"""
    return PACKAGES.get(package_type, PACKAGES["trial"])

'''

    # Find the end of imports (look for first function or class definition)
    # Insert PACKAGES after imports
    import_end = content.find('\n@app.')
    if import_end == -1:
        import_end = content.find('\ndef ')
    if import_end == -1:
        import_end = content.find('\nclass ')

    if import_end > 0:
        content = content[:import_end] + packages_code + content[import_end:]
        print("Added PACKAGES definition to license_server.py")
    else:
        print("Could not find insertion point, adding at end of imports")
        # Find last import statement
        lines = content.split('\n')
        insert_line = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_line = i + 1
        lines.insert(insert_line, packages_code)
        content = '\n'.join(lines)
        print("Added PACKAGES after imports")

# Now update the validate endpoint to include package limits
# Find the validate_license function and update the return statement

# Look for the validate endpoint
validate_pattern = r"(@app\.route\('/api/validate'.*?def validate_license.*?return jsonify\(\{)(.*?)(\}\))"

def update_validate_response(match):
    route = match.group(1)
    response_content = match.group(2)
    closing = match.group(3)

    # Check if package info already added
    if 'max_olts' in response_content:
        return match.group(0)

    # Add package info before the closing
    new_response = response_content.rstrip()
    if not new_response.endswith(','):
        new_response += ','

    # This is a simple approach - for complex cases, manual update may be needed
    return route + new_response + '''
        "package_type": license.get("package_type", "trial"),
        "max_olts": get_package_limits(license.get("package_type", "trial"))["max_olts"],
        "max_onus": get_package_limits(license.get("package_type", "trial"))["max_onus"],
        "max_users": get_package_limits(license.get("package_type", "trial"))["max_users"]
    ''' + closing

# Save the file
with open('/opt/license-server/license_server.py', 'w') as f:
    f.write(content)

print("License server updated!")
print("Now restart the service: sudo systemctl restart license-server")
PYTHON_SCRIPT

echo ""
echo "Restarting license server..."
systemctl restart license-server
sleep 2
systemctl status license-server | head -5

echo ""
echo "Done! Package support has been added."
echo ""
echo "To set a customer's package, edit /opt/license-server/licenses.json"
echo "and add 'package_type': 'professional' (or other package name)"

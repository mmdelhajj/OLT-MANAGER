#!/usr/bin/env python3
"""
Add Package Support to License Server
Run this on the license server: python3 add_packages_to_license_server.py
"""

import os
import re
import shutil
from datetime import datetime

LICENSE_SERVER_PATH = '/opt/license-server/license_server.py'
BACKUP_PATH = f'/opt/license-server/license_server.py.bak.{datetime.now().strftime("%Y%m%d_%H%M%S")}'

# Package definitions
PACKAGES_CODE = '''
# ============================================
# PACKAGE DEFINITIONS - Added by update script
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

def main():
    print("=" * 50)
    print("License Server Package Support Updater")
    print("=" * 50)

    # Check if file exists
    if not os.path.exists(LICENSE_SERVER_PATH):
        print(f"ERROR: {LICENSE_SERVER_PATH} not found!")
        return False

    # Create backup
    print(f"\n1. Creating backup: {BACKUP_PATH}")
    shutil.copy2(LICENSE_SERVER_PATH, BACKUP_PATH)
    print("   Backup created!")

    # Read current content
    print("\n2. Reading current license_server.py...")
    with open(LICENSE_SERVER_PATH, 'r') as f:
        content = f.read()

    # Check if already updated
    if 'PACKAGES = {' in content and 'get_package_limits' in content:
        print("   PACKAGES already exists! Skipping addition.")
    else:
        print("   Adding PACKAGES definition...")

        # Find insertion point (after imports, before first route/function)
        lines = content.split('\n')
        insert_index = 0

        for i, line in enumerate(lines):
            # Find last import line
            if line.startswith('import ') or line.startswith('from '):
                insert_index = i + 1
            # Stop at first decorator or function
            elif line.startswith('@') or line.startswith('def ') or line.startswith('class '):
                if insert_index > 0:
                    break

        # Insert PACKAGES code
        lines.insert(insert_index, PACKAGES_CODE)
        content = '\n'.join(lines)
        print(f"   Inserted PACKAGES at line {insert_index}")

    # Now update the /api/validate endpoint to return package info
    print("\n3. Updating /api/validate endpoint...")

    # Find the validate function and its return statement
    # We'll add package info to the response

    # Look for pattern: return jsonify({"valid": True, ...})
    # and add package fields

    if 'max_olts' in content and '"package_type"' in content:
        print("   Package fields already in validate response!")
    else:
        # Find validate_license function
        validate_match = re.search(
            r'(def validate_license\(.*?\):.*?return jsonify\(\{)(.*?)(\}\))',
            content,
            re.DOTALL
        )

        if validate_match:
            # Get the response content
            func_start = validate_match.group(1)
            response_body = validate_match.group(2)
            func_end = validate_match.group(3)

            # Add package fields before closing
            new_response = response_body.rstrip()
            if not new_response.endswith(','):
                new_response += ','

            package_fields = '''
            "package_type": license.get("package_type", "trial"),
            "max_olts": get_package_limits(license.get("package_type", "trial"))["max_olts"],
            "max_onus": get_package_limits(license.get("package_type", "trial"))["max_onus"],
            "max_users": get_package_limits(license.get("package_type", "trial"))["max_users"]
        '''

            new_func = func_start + new_response + package_fields + func_end
            content = content[:validate_match.start()] + new_func + content[validate_match.end():]
            print("   Added package fields to validate response!")
        else:
            print("   WARNING: Could not find validate_license function!")
            print("   You may need to manually add package fields to the response.")

    # Write updated content
    print("\n4. Saving updated license_server.py...")
    with open(LICENSE_SERVER_PATH, 'w') as f:
        f.write(content)
    print("   File saved!")

    print("\n" + "=" * 50)
    print("UPDATE COMPLETE!")
    print("=" * 50)
    print("\nNext steps:")
    print("1. Restart the service: sudo systemctl restart license-server")
    print("2. To assign a package to a customer, edit /opt/license-server/licenses.json")
    print("   and add: \"package_type\": \"professional\" (or other package name)")
    print("\nAvailable packages:")
    print("  - trial: 1 OLT, 64 ONUs")
    print("  - starter: 1 OLT, 128 ONUs ($29)")
    print("  - basic: 1 OLT, 256 ONUs ($49)")
    print("  - professional: 2 OLTs, 512 ONUs ($99)")
    print("  - business: 4 OLTs, 1024 ONUs ($199)")
    print("  - enterprise: 8 OLTs, 2048 ONUs ($399)")
    print("  - ultimate: 16 OLTs, 4096 ONUs ($599)")
    print("  - unlimited: 999 OLTs, 99999 ONUs ($999)")

    return True

if __name__ == '__main__':
    main()

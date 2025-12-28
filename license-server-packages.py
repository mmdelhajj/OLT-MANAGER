# Package definitions for OLT Manager License Server
# Add this to your license_server.py

PACKAGES = {
    "trial": {
        "name": "Trial",
        "max_olts": 1,
        "max_onus": 64,
        "max_users": 2,
        "features": ["basic"],
        "price": 0
    },
    "starter": {
        "name": "Starter",
        "max_olts": 1,
        "max_onus": 128,
        "max_users": 3,
        "features": ["basic", "reports"],
        "price": 29
    },
    "basic": {
        "name": "Basic",
        "max_olts": 1,
        "max_onus": 256,
        "max_users": 5,
        "features": ["basic", "reports", "alerts"],
        "price": 49
    },
    "professional": {
        "name": "Professional",
        "max_olts": 2,
        "max_onus": 512,
        "max_users": 10,
        "features": ["basic", "reports", "alerts", "backup"],
        "price": 99
    },
    "business": {
        "name": "Business",
        "max_olts": 4,
        "max_onus": 1024,
        "max_users": 20,
        "features": ["basic", "reports", "alerts", "backup", "api"],
        "price": 199
    },
    "enterprise": {
        "name": "Enterprise",
        "max_olts": 8,
        "max_onus": 2048,
        "max_users": 50,
        "features": ["all"],
        "price": 399
    },
    "ultimate": {
        "name": "Ultimate",
        "max_olts": 16,
        "max_onus": 4096,
        "max_users": 100,
        "features": ["all"],
        "price": 599
    },
    "unlimited": {
        "name": "Unlimited",
        "max_olts": 999,
        "max_onus": 99999,
        "max_users": 999,
        "features": ["all"],
        "price": 999
    }
}

def get_package_limits(package_type: str) -> dict:
    """Get limits for a package type"""
    package = PACKAGES.get(package_type, PACKAGES["trial"])
    return {
        "max_olts": package["max_olts"],
        "max_onus": package["max_onus"],
        "max_users": package["max_users"],
        "features": package["features"],
        "package_name": package["name"]
    }


# Example: Update license validation response
# In your /api/validate endpoint, add:
#
# package_type = license.get("package_type", "trial")
# limits = get_package_limits(package_type)
#
# return {
#     "valid": True,
#     "customer_name": license.get("customer_name"),
#     "expires_at": license.get("expires_at"),
#     "package_type": package_type,
#     "max_olts": limits["max_olts"],
#     "max_onus": limits["max_onus"],
#     "max_users": limits["max_users"],
#     "features": limits["features"]
# }


# Example licenses.json structure:
# {
#   "LICENSE-KEY-HERE": {
#     "customer_name": "John's ISP",
#     "hardware_id": "OLT-XXXXXXXX-XXXXXXXX-XXXXXXXX",
#     "package_type": "professional",  # <-- Add this field
#     "expires_at": "2025-12-31",
#     "created_at": "2024-01-01",
#     "suspended": false
#   }
# }

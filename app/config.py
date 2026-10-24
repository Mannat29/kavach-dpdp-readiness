"""Build-time application configuration for Kavach."""

# Navigation items enabled in the primary header.
# Stub pages not in this list will be hidden from the nav bar, but their routes remain active.
ENABLED_PAGES = [
    "Dashboard",
    "Scanner",
    "Data Map",
    "Rights Desk",
    "Risk Analysis",
]

RESPONSE_DAYS = 30  # TODO verify against DPDP Rules 2025


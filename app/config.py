"""Build-time application configuration for Kavach."""

# Navigation items enabled in the primary header.
# Stub pages not in this list will be hidden from the nav bar, but their routes remain active.
ENABLED_PAGES = [
    "Dashboard",
    "Scanner",
    "Data Map",
    "Rights Desk",
    "Breach Simulator",
    "Risk Analysis",
]

RESPONSE_DAYS = 30  # TODO verify against DPDP Rules 2025

# Breach notification constants
# Stage 1: inform the Board without delay (no fixed deadline; show elapsed time)
BREACH_STAGE_1_DESCRIPTION = "inform the Board without delay"  # TODO verify against DPDP Rules 2025, Rule 7

# Stage 2: detailed report to the Board within 72 hours (deadline timestamp and seconds remaining; note: extendable on written request to the Board)
BREACH_STAGE_2_HOURS = 72  # TODO verify against DPDP Rules 2025, Rule 7
BREACH_STAGE_2_DESCRIPTION = "detailed report to the Board within 72 hours"  # TODO verify against DPDP Rules 2025, Rule 7

BREACH_INDIVIDUAL_NOTICE_NOTE = "Affected people must be told without delay; check in the Rules text whether this applies in every case (verify)"



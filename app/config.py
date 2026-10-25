"""Build-time application configuration for Kavach."""

# Navigation items enabled in the primary header.
# Stub pages not in this list will be hidden from the nav bar, but their routes remain active.
ENABLED_PAGES = [
    "Dashboard",
    "Scanner",
    "Data Map",
    "Purposes",
    "Rights Desk",
    "Breach Simulator",
    "Risk Analysis",
    "Reports",
    "Evidence",
]

RESPONSE_DAYS = 30  # TODO verify against DPDP Rules 2025

# Breach notification constants
# Stage 1: inform the Board without delay (no fixed deadline; show elapsed time)
BREACH_STAGE_1_DESCRIPTION = "inform the Board without delay"  # TODO verify against DPDP Rules 2025, Rule 7

# Stage 2: detailed report to the Board within 72 hours (deadline timestamp and seconds remaining; note: extendable on written request to the Board)
BREACH_STAGE_2_HOURS = 72  # TODO verify against DPDP Rules 2025, Rule 7
BREACH_STAGE_2_DESCRIPTION = "detailed report to the Board within 72 hours"  # TODO verify against DPDP Rules 2025, Rule 7

BREACH_INDIVIDUAL_NOTICE_NOTE = "Affected people must be told without delay; check in the Rules text whether this applies in every case (verify)"

# Evaluated benchmark numbers on held-out synthetic test set
REPORTED_ACCURACY = {
    "precision": 0.91,
    "recall": 0.85,
    "note": "Detector accuracy evaluated on held-out synthetic test data.",
}

# OCR & Scanned Document Configuration
OCR_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
OCR_MAX_PAGES = 50
OCR_MIN_NATIVE_CHARS = 50
OCR_MIN_NATIVE_WORDS = 5
OCR_DEFAULT_LANGUAGE = "eng"
OCR_TIMEOUT_SECONDS = 30
TESSERACT_WINDOWS_DEFAULT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"



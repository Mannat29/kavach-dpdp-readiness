"""Generate a synthetic clinic slip image with synthetic PII for OCR testing and demo."""
import os
import random
from PIL import Image, ImageDraw


# Verhoeff tables
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def generate_synthetic_aadhaar(seed: int = 42) -> str:
    """Generate a 12-digit Verhoeff-valid synthetic Aadhaar number."""
    rng = random.Random(seed)
    first = rng.randint(2, 9)
    middle = "".join(str(rng.randint(0, 9)) for _ in range(10))
    base = str(first) + middle
    c = 0
    for i, ch in enumerate(reversed(base)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(ch)]]
    checksum = str(_VERHOEFF_INV[c])
    return base + checksum


def create_clinic_slip(output_path: str) -> str:
    """Create a synthetic PNG clinic slip with synthetic contact phone and Verhoeff-valid Aadhaar."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    aadhaar_raw = generate_synthetic_aadhaar(42)
    aadhaar_formatted = f"{aadhaar_raw[:4]} {aadhaar_raw[4:8]} {aadhaar_raw[8:]}"
    phone = "9876543210"

    img = Image.new("RGB", (700, 400), color="white")
    draw = ImageDraw.Draw(img)

    # Draw border
    draw.rectangle([(10, 10), (690, 390)], outline="black", width=2)
    draw.line([(10, 75), (690, 75)], fill="black", width=2)

    # Header
    draw.text((30, 25), "AAROGYA WELLNESS CLINIC", fill="black")
    draw.text((30, 48), "Patient Registration & Consultation Slip", fill="black")

    # Body fields
    draw.text((30, 100), "Patient Name: Sneha Sharma", fill="black")
    draw.text((30, 140), "Age / Gender: 32 / F", fill="black")
    draw.text((30, 180), f"Contact Phone: {phone}", fill="black")
    draw.text((30, 220), f"Aadhaar Number: {aadhaar_formatted}", fill="black")
    draw.text((30, 260), "Doctor: Dr. Rajesh Kumar, MD", fill="black")
    draw.text((30, 300), "Consultation Notes: Routine wellness checkup completed", fill="black")
    draw.text((30, 340), "Date: 15/03/2026   |   Receipt No: RC-2026-8812", fill="black")

    img.save(output_path, format="PNG")
    return output_path


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(base_dir, "data", "demo_ocr", "clinic_slip.png")
    create_clinic_slip(target)
    print(f"Generated synthetic OCR sample at: {target}")

"""Generate deterministic synthetic demo data for Sri Lakshmi Diagnostics."""
import csv
import json
import os
import random
import re
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Verhoeff algorithm for Aadhaar checksum
# ---------------------------------------------------------------------------
_VERHOEFF_D = [
    [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]
_VERHOEFF_P = [
    [0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8],
]
_VERHOEFF_INV = [0,4,3,2,1,5,6,7,8,9]


def _verhoeff_checksum(num_str: str) -> int:
    """Return Verhoeff check digit for a numeric string."""
    c = 0
    for i, ch in enumerate(reversed(num_str)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(ch)]]
    return _VERHOEFF_INV[c]


def make_aadhaar(rng: random.Random) -> str:
    """Generate a 12-digit Aadhaar number that passes Verhoeff checksum."""
    # First digit 2-9 (Aadhaar never starts with 0 or 1)
    first = rng.randint(2, 9)
    middle = "".join(str(rng.randint(0, 9)) for _ in range(10))
    base = str(first) + middle  # 11 digits
    check = _verhoeff_checksum(base)
    return base + str(check)


def make_invalid_aadhaar(rng: random.Random) -> str:
    """Generate a 12-digit number that FAILS Verhoeff checksum."""
    while True:
        first = rng.randint(2, 9)
        middle = "".join(str(rng.randint(0, 9)) for _ in range(10))
        base = str(first) + middle
        correct_check = _verhoeff_checksum(base)
        wrong_check = (correct_check + rng.randint(1, 9)) % 10
        candidate = base + str(wrong_check)
        # Verify it actually fails
        c = 0
        for i, ch in enumerate(reversed(candidate)):
            c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
        if c != 0:
            return candidate


def make_pan(rng: random.Random, name_initial: str = "A") -> str:
    """Generate a synthetic PAN (ABCDE1234F format)."""
    p1 = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(3))
    p2 = rng.choice("ABCFGHLJPT")  # valid PAN entity types
    p3 = name_initial.upper()
    digits = "".join(str(rng.randint(0, 9)) for _ in range(4))
    last = rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return p1 + p2 + p3 + digits + last


def make_gstin(rng: random.Random, pan: str = None) -> str:
    """Generate a synthetic GSTIN (15 chars: 2-digit state + PAN + 1 + Z + check)."""
    state = str(rng.choice([29, 27, 36, 33, 32, 9, 7, 6, 8, 10])).zfill(2)
    if pan is None:
        pan = make_pan(rng)
    entity_num = str(rng.randint(1, 9))
    return state + pan + entity_num + "Z" + rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def make_ifsc(rng: random.Random) -> str:
    """Generate a synthetic IFSC code."""
    bank = rng.choice(["SBIN", "HDFC", "ICIC", "UTIB", "KKBK", "CNRB", "BARB"])
    branch = "".join(str(rng.randint(0, 9)) for _ in range(6))
    return bank + "0" + branch


def make_bank_account(rng: random.Random) -> str:
    """Generate a synthetic bank account number (9-18 digits)."""
    length = rng.randint(9, 16)
    return "".join(str(rng.randint(0, 9)) for _ in range(length))


def make_phone(rng: random.Random) -> str:
    """Generate a 10-digit Indian mobile number starting with 6-9."""
    first = rng.choice([6, 7, 8, 9])
    rest = "".join(str(rng.randint(0, 9)) for _ in range(9))
    return str(first) + rest


def format_phone(phone10: str, fmt: int) -> str:
    """Format a 10-digit phone in different styles."""
    if fmt == 0:
        return f"+91 {phone10}"
    elif fmt == 1:
        return phone10
    elif fmt == 2:
        return f"{phone10[:5]} {phone10[5:]}"
    elif fmt == 3:
        return f"0{phone10}"
    elif fmt == 4:
        return f"+91{phone10}"
    elif fmt == 5:
        return f"91{phone10}"
    return phone10


def make_email(name: str, rng: random.Random) -> str:
    parts = name.lower().split()
    domain = rng.choice(["gmail.com", "yahoo.co.in", "outlook.com", "hotmail.com"])
    if len(parts) >= 2:
        user = parts[0] + "." + parts[1] + str(rng.randint(1, 99))
    else:
        user = parts[0] + str(rng.randint(10, 999))
    return user + "@" + domain


def make_upi(name: str, rng: random.Random) -> str:
    parts = name.lower().split()
    bank = rng.choice(["okaxis", "oksbi", "ybl", "paytm", "ibl"])
    if len(parts) >= 2:
        user = parts[0] + parts[1][0]
    else:
        user = parts[0]
    return user + str(rng.randint(1, 99)) + "@" + bank


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------
def main():
    rng = random.Random(7)
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "demo")
    os.makedirs(out_dir, exist_ok=True)

    ground_truth = []  # list of {source, location, category}

    # --- 30 people total, first 12 appear in multiple files ---
    NAMES = [
        "Ramesh Kumar", "Priya Sharma", "Anita Reddy", "Mohammed Irfan",
        "Lakshmi Naidu", "Suresh Gowda", "Deepa Bhat", "Arun Joshi",
        "Kavita Hegde", "Rajesh Shetty", "Meena Kumari", "Vijay Prasad",
        # single-file people
        "Sunita Rao", "Manoj Patil", "Geeta Devi", "Harish Nayak",
        "Pooja Kulkarni", "Naveen Raju", "Divya Iyengar", "Srinivas Murthy",
        "Bharathi Venkat", "Kiran Desai", "Fatima Begum", "Ravi Shankar",
        "Nandini Gowda", "Prashanth Kumar", "Rekha Jain", "Sameer Patel",
        "Asha Deshpande", "Vikram Singh",
    ]

    HINDI_KANNADA_NAMES = [
        "Raju bhai", "Shanta amma", "Pappu Yadav", "Kamala devi",
        "Venkatesh anna", "Mangala akka", "Basappa gowda", "Sarojini bai",
    ]

    HEALTH_TERMS = ["diabetes", "HIV positive", "thyroid disorder", "pregnancy test",
                    "blood sugar high", "hepatitis B", "hypertension", "cancer screening"]

    TEST_NAMES = ["CBC", "Lipid Profile", "Thyroid Panel", "HbA1c", "Liver Function Test",
                  "Blood Sugar Fasting", "Urine Routine", "HIV Test", "Vitamin D",
                  "Complete Metabolic Panel", "Kidney Function Test", "ECG"]

    # Generate identifiers for all 30 people
    people = []
    for i, name in enumerate(NAMES):
        phone = make_phone(rng)
        people.append({
            "name": name,
            "phone": phone,
            "email": make_email(name, rng),
            "aadhaar": make_aadhaar(rng),
            "dob": f"{rng.randint(1960, 2005)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "pan": make_pan(rng, name[0]),
            "bank_account": make_bank_account(rng),
            "ifsc": make_ifsc(rng),
            "upi": make_upi(name, rng),
        })

    # Generate decoy 12-digit numbers (fail Verhoeff)
    decoy_aadhaar = [make_invalid_aadhaar(rng) for _ in range(4)]

    # Extra identifiers for the clinic
    clinic_gstin = make_gstin(rng)
    clinic_pan = make_pan(rng, "S")  # Sri Lakshmi

    # -----------------------------------------------------------------------
    # 1. patients.xlsx
    # -----------------------------------------------------------------------
    try:
        from openpyxl import Workbook
    except ImportError:
        raise SystemExit("openpyxl is required: pip install openpyxl")

    wb = Workbook()
    ws = wb.active
    ws.title = "Patients"
    headers = ["Name", "Phone", "Email", "Aadhaar", "DOB", "Test Name", "Notes"]
    ws.append(headers)

    patient_indices = list(range(20))  # first 20 people are patients
    for idx in patient_indices:
        p = people[idx]
        phone_fmt = format_phone(p["phone"], rng.randint(0, 5))
        aadhaar_display = p["aadhaar"]
        if rng.random() < 0.4:
            aadhaar_display = f"{p['aadhaar'][:4]} {p['aadhaar'][4:8]} {p['aadhaar'][8:]}"
        test = rng.choice(TEST_NAMES)
        notes = ""
        if rng.random() < 0.4:
            notes = "Patient has " + rng.choice(HEALTH_TERMS)
        elif rng.random() < 0.2:
            notes = "Follow up needed"

        row_num = idx + 2  # Excel row (1-indexed, header is row 1)
        ws.append([p["name"], phone_fmt, p["email"], aadhaar_display, p["dob"], test, notes])

        # Ground truth
        ground_truth.append({"source": "patients.xlsx", "location": f"Patients/R{row_num}/C1", "category": "name"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Patients/R{row_num}/C2", "category": "phone"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Patients/R{row_num}/C3", "category": "email"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Patients/R{row_num}/C4", "category": "aadhaar"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Patients/R{row_num}/C5", "category": "dob"})
        if notes and any(h in notes.lower() for h in [t.lower() for t in HEALTH_TERMS]):
            ground_truth.append({"source": "patients.xlsx", "location": f"Patients/R{row_num}/C7", "category": "health_term"})
        # Test name column may also contain health terms
        if any(h in test.lower() for h in ["hiv", "thyroid", "sugar", "diabetes", "pregnancy", "cancer", "hepatitis"]):
            ground_truth.append({"source": "patients.xlsx", "location": f"Patients/R{row_num}/C6", "category": "health_term"})

    xlsx_path = os.path.join(out_dir, "patients.xlsx")
    wb.save(xlsx_path)
    print(f"  Created {xlsx_path} ({len(patient_indices)} rows)")

    # -----------------------------------------------------------------------
    # 2. billing.csv
    # -----------------------------------------------------------------------
    billing_path = os.path.join(out_dir, "billing.csv")
    with open(billing_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["invoice_no", "patient_name", "phone", "amount", "gstin"])
        billing_people = list(range(15))  # first 15
        for i, idx in enumerate(billing_people):
            p = people[idx]
            inv = f"INV-2026-{i+1:04d}"
            phone_fmt = format_phone(p["phone"], rng.randint(0, 5))
            amount = rng.randint(200, 15000)
            gstin = clinic_gstin if rng.random() < 0.7 else ""
            row_num = i + 2
            writer.writerow([inv, p["name"], phone_fmt, amount, gstin])

            ground_truth.append({"source": "billing.csv", "location": f"R{row_num}/C2", "category": "name"})
            ground_truth.append({"source": "billing.csv", "location": f"R{row_num}/C3", "category": "phone"})
            if gstin:
                ground_truth.append({"source": "billing.csv", "location": f"R{row_num}/C5", "category": "gstin"})
    print(f"  Created {billing_path} ({len(billing_people)} rows)")

    # -----------------------------------------------------------------------
    # 3. staff.csv
    # -----------------------------------------------------------------------
    staff_path = os.path.join(out_dir, "staff.csv")
    staff_indices = list(range(20, 30))  # last 10 people are staff, but first 2 overlap
    # Make people 0 and 1 also staff (overlap with patients)
    staff_list = [0, 1] + list(range(20, 28))  # 10 staff
    with open(staff_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "pan", "phone", "salary", "bank_account", "ifsc"])
        for i, idx in enumerate(staff_list):
            p = people[idx]
            phone_fmt = format_phone(p["phone"], rng.randint(0, 5))
            salary = rng.randint(15000, 80000)
            row_num = i + 2
            writer.writerow([p["name"], p["pan"], phone_fmt, salary, p["bank_account"], p["ifsc"]])

            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C1", "category": "name"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C2", "category": "pan"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C3", "category": "phone"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C5", "category": "bank_account"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C6", "category": "ifsc"})
    print(f"  Created {staff_path} ({len(staff_list)} rows)")

    # -----------------------------------------------------------------------
    # 4. appointments_form.csv (Google Forms export style)
    # -----------------------------------------------------------------------
    appt_path = os.path.join(out_dir, "appointments_form.csv")
    all_form_names = NAMES[:12] + HINDI_KANNADA_NAMES
    with open(appt_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Name", "Phone", "Email", "Reason"])
        reasons = ["Regular checkup", "Blood test", "Thyroid check", "Sugar test",
                    "Follow up", "Eye checkup", "Fever since 3 days", "Back pain",
                    "Routine CBC", "Lipid profile test", "HIV screening", "Pregnancy test"]
        for i, name in enumerate(all_form_names):
            ts = datetime(2026, 10, rng.randint(1, 23), rng.randint(8, 18), rng.randint(0, 59))
            ts_str = ts.strftime("%Y/%m/%d %I:%M:%S %p")
            if i < 12:
                p = people[i]
                phone_fmt = format_phone(p["phone"], rng.randint(0, 5))
                email = p["email"]
            else:
                phone_fmt = format_phone(make_phone(rng), rng.randint(0, 5))
                email = make_email(name, rng)

            reason = rng.choice(reasons)
            row_num = i + 2
            writer.writerow([ts_str, name, phone_fmt, email, reason])

            ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C2", "category": "name"})
            ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C3", "category": "phone"})
            ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C4", "category": "email"})
            if any(h.lower() in reason.lower() for h in ["HIV", "Pregnancy", "Thyroid"]):
                ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C5", "category": "health_term"})
    print(f"  Created {appt_path} ({len(all_form_names)} rows)")

    # -----------------------------------------------------------------------
    # 5. whatsapp_chat.txt
    # -----------------------------------------------------------------------
    chat_path = os.path.join(out_dir, "whatsapp_chat.txt")
    chat_lines = []

    # Helper to make a chat timestamp
    base_date = datetime(2026, 9, 1, 8, 0)

    def chat_ts():
        nonlocal base_date
        base_date += timedelta(minutes=rng.randint(5, 180))
        return base_date.strftime("%d/%m/%y, %I:%M %p").lower().replace(" am", " am").replace(" pm", " pm")

    # Senders: mix of patients and staff
    chat_senders = [people[i]["name"] for i in range(15)]
    erasure_people = [2, 5, 8]  # Anita Reddy, Suresh Gowda, Kavita Hegde

    def add_line(sender, msg):
        ts = chat_ts()
        line = f"{ts} - {sender}: {msg}"
        chat_lines.append(line)

    # General clinic messages
    clinic_messages = [
        "Good morning, your report is ready for collection",
        "Please come with empty stomach for the blood test tomorrow",
        "Lab will be closed on Sunday",
        "Your CBC report has been sent to your email",
        "Please bring your Aadhaar card for registration",
        "Reminder: appointment at 10 AM tomorrow",
        "Sample collected, report will be ready by evening",
        "Please collect your prescription from reception",
        "Holiday notice: clinic closed on Oct 2nd for Gandhi Jayanti",
        "New test packages available, please check our website",
    ]

    # Generate ~300 lines
    line_num = 0

    # System message at start
    chat_lines.append(f"{chat_ts()} - Messages and calls are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them.")
    line_num += 1

    for _ in range(70):
        sender = rng.choice(chat_senders)
        msg = rng.choice(clinic_messages)
        add_line(sender, msg)
        line_num += 1
        ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {line_num}", "category": "name"})

    # Messages with embedded PII
    pii_messages = []

    # Phone numbers in messages
    for i in [0, 3, 6, 9, 11]:
        p = people[i]
        phone_fmt = format_phone(p["phone"], rng.randint(0, 5))
        msgs = [
            f"My number is {phone_fmt}, please send report",
            f"Call me on {phone_fmt}",
            f"Contact patient at {phone_fmt} for follow up",
            f"Pls send report to {phone_fmt}",
        ]
        pii_messages.append((p["name"], rng.choice(msgs), [
            {"category": "phone", "extra": True},
        ]))

    # Aadhaar in messages (with spaces)
    for i in [1, 4, 7]:
        p = people[i]
        aadhaar_sp = f"{p['aadhaar'][:4]} {p['aadhaar'][4:8]} {p['aadhaar'][8:]}"
        pii_messages.append((p["name"], f"My Aadhaar is {aadhaar_sp}", [
            {"category": "aadhaar", "extra": True},
        ]))

    # Email in messages
    for i in [2, 5]:
        p = people[i]
        pii_messages.append((p["name"], f"Please send to {p['email']}", [
            {"category": "email", "extra": True},
        ]))

    # UPI IDs in messages
    for i in [3, 10]:
        p = people[i]
        pii_messages.append((p["name"], f"Payment received via {p['upi']}", [
            {"category": "upi_id", "extra": True},
        ]))

    # Decoy: 12-digit number that fails Verhoeff (not Aadhaar)
    for d in decoy_aadhaar[:2]:
        sender = rng.choice(chat_senders)
        pii_messages.append((sender, f"Order number {d} confirmed", []))

    # Decoy: invoice numbers that look like numbers
    pii_messages.append((rng.choice(chat_senders), "Invoice INV-2026-0005 has been paid amount 123456789012", []))

    # Health terms in messages
    health_msgs = [
        (people[0]["name"], "Doctor said I have diabetes, need regular checkup"),
        (people[3]["name"], "HIV test result is negative, thank you"),
        (people[7]["name"], "My thyroid levels are abnormal"),
        (people[11]["name"], "Is the pregnancy test report ready?"),
    ]
    for sender_name, msg, in health_msgs:
        pii_messages.append((sender_name, msg, [{"category": "health_term", "extra": True}]))

    # Shuffle and add PII messages
    rng.shuffle(pii_messages)
    for sender, msg, extras in pii_messages:
        add_line(sender, msg)
        line_num += 1
        ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {line_num}", "category": "name"})
        for e in extras:
            ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {line_num}", "category": e["category"]})

    # More filler messages to reach ~300
    filler_msgs = [
        "Ok", "Thank you", "Sure", "Will come tomorrow", "What time?",
        "Report bhej dijiye", "Kitna paisa lagega?", "Ji haan",
        "Naale barthini", "Ok dhanyavad", "Swalpa wait maadi",
        "Blood test ready aa?", "Ji theek hai", "Aaj nahi aa paunga",
        "Ok sir", "Thank you madam", "Report email mein bheja hai",
        "Fees kitni hai?", "Kab aana hai?", "Subah 9 baje aiye",
        "Test results normal hai", "Good news!", "Sab theek hai",
        "Appointment cancel kar dijiye", "Kal aa jaata hoon",
        "Report collect kar liya", "Dhanyavaad", "Nale banni",
        "Tablets shuru kar diye", "Follow up next week",
        "Lab report attached", "Please check email",
        "Payment done via UPI", "Receipt bhej dijiye",
    ]

    while line_num < 290:
        sender = rng.choice(chat_senders)
        msg = rng.choice(filler_msgs)
        add_line(sender, msg)
        line_num += 1
        ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {line_num}", "category": "name"})

    # 3 erasure-style messages
    erasure_msgs = [
        (people[erasure_people[0]]["name"], "Please delete my details from your records"),
        (people[erasure_people[1]]["name"], "Mera number list se hata dijiye"),
        (people[erasure_people[2]]["name"], "Nanna number delete maadi"),
    ]
    for sender, msg in erasure_msgs:
        add_line(sender, msg)
        line_num += 1
        ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {line_num}", "category": "name"})

    # A few more lines to pad to ~300
    while line_num < 300:
        sender = rng.choice(chat_senders)
        msg = rng.choice(filler_msgs)
        add_line(sender, msg)
        line_num += 1
        ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {line_num}", "category": "name"})

    with open(chat_path, "w", encoding="utf-8") as f:
        f.write("\n".join(chat_lines) + "\n")
    print(f"  Created {chat_path} ({len(chat_lines)} lines)")

    # -----------------------------------------------------------------------
    # 6. ground_truth.json
    # -----------------------------------------------------------------------
    gt_path = os.path.join(out_dir, "ground_truth.json")
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)
    print(f"  Created {gt_path} ({len(ground_truth)} items)")

    print(f"\nDone. {len(ground_truth)} ground truth items across 5 files.")


if __name__ == "__main__":
    main()

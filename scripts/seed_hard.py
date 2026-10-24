"""Generate deliberately messy synthetic demo_hard data (seed 11) for testing detector limits."""
import csv
import json
import os
import random
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.seed import (
    make_aadhaar,
    make_invalid_aadhaar,
    make_pan,
    make_gstin,
    make_ifsc,
    make_bank_account,
    make_phone,
    make_email,
    make_upi,
)


def format_messy_phone(phone10: str, rng: random.Random) -> str:
    """Format phone with dashes, dots, brackets, +91- etc."""
    fmt = rng.randint(0, 5)
    p = phone10
    if fmt == 0:
        return f"+91-({p[:3]})-{p[3:6]}-{p[6:]}"
    elif fmt == 1:
        return f"+91-{p[:5]}-{p[5:]}"
    elif fmt == 2:
        return f"{p[:3]}.{p[3:6]}.{p[6:]}"
    elif fmt == 3:
        return f"({p[:5]}) {p[5:]}"
    elif fmt == 4:
        return f"+91.{p}"
    else:
        return f"{p[:5]}-{p[5:]}"


def main():
    rng = random.Random(11)
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "demo_hard")
    os.makedirs(out_dir, exist_ok=True)

    ground_truth = []

    NAMES = [
        "Ramesh Kumar", "Priya Sharma", "Anita Reddy", "Mohammed Irfan",
        "Lakshmi Naidu", "Suresh Gowda", "Deepa Bhat", "Arun Joshi",
        "Kavita Hegde", "Rajesh Shetty", "Meena Kumari", "Vijay Prasad",
        "Sunita Rao", "Manoj Patil", "Geeta Devi", "Harish Nayak",
        "Pooja Kulkarni", "Naveen Raju", "Divya Iyengar", "Srinivas Murthy",
    ]

    HEALTH_TERMS = ["diabetes", "HIV positive", "thyroid disorder", "pregnancy test",
                    "blood sugar high", "hepatitis B", "hypertension", "cancer screening"]

    TEST_NAMES = ["CBC", "Lipid Profile", "Thyroid Panel", "HbA1c", "Liver Function Test",
                  "Blood Sugar Fasting", "Urine Routine", "HIV Test", "Vitamin D",
                  "Complete Metabolic Panel", "Kidney Function Test", "ECG"]

    people = []
    for i, name in enumerate(NAMES):
        p_phone = make_phone(rng)
        people.append({
            "name": name,
            "phone": p_phone,
            "email": make_email(name, rng),
            "aadhaar": make_aadhaar(rng),
            "dob": f"{rng.randint(1965, 2012)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "pan": make_pan(rng, name[0]),
            "bank_account": make_bank_account(rng),
            "ifsc": make_ifsc(rng),
            "upi": make_upi(name, rng),
        })

    clinic_gstin = make_gstin(rng)
    decoy_aadhaar_order = make_invalid_aadhaar(rng)

    # -----------------------------------------------------------------------
    # 1. patients.xlsx (TWO TABS: 'Active' and 'Archived')
    # -----------------------------------------------------------------------
    from openpyxl import Workbook
    wb = Workbook()

    # Tab 1: Active
    ws1 = wb.active
    ws1.title = "Active"
    # Column 6 has no recognizable header ("Misc_Data")
    # Column 7 is "Remarks" containing names or PAN
    headers1 = ["Name", "Phone", "Email", "Aadhaar", "DOB", "Misc_Data", "Remarks"]
    ws1.append(headers1)

    for idx in range(12):
        p = people[idx]
        # lowercase / ALL-CAPS names
        if idx % 3 == 0:
            name_val = p["name"].lower()
        elif idx % 3 == 1:
            name_val = p["name"].upper()
        else:
            name_val = p["name"]

        phone_val = format_messy_phone(p["phone"], rng)

        # email with trailing punctuation
        email_val = p["email"] + rng.choice([".", ",", ""])

        # Aadhaar with dots or no spaces
        if idx % 2 == 0:
            aadhaar_val = f"{p['aadhaar'][:4]}.{p['aadhaar'][4:8]}.{p['aadhaar'][8:]}"
        else:
            aadhaar_val = p["aadhaar"]  # no spaces

        dob_val = p["dob"]
        test_val = rng.choice(TEST_NAMES)

        # Remarks: PAN in notes cell, or name in remarks column
        remarks_val = ""
        pan_in_remarks = False
        name_in_remarks = False
        if idx == 2:
            remarks_val = f"PAN copy submitted: {p['pan']}"
            pan_in_remarks = True
        elif idx == 4:
            ref_name = people[15]["name"]
            remarks_val = f"Referred by Dr. {ref_name}"
            name_in_remarks = True
        elif idx % 2 == 0:
            remarks_val = f"Patient has {rng.choice(HEALTH_TERMS)}"

        row_num = idx + 2
        ws1.append([name_val, phone_val, email_val, aadhaar_val, dob_val, test_val, remarks_val])

        # Ground truth
        ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C1", "category": "name"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C2", "category": "phone"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C3", "category": "email"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C4", "category": "aadhaar"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C5", "category": "dob"})
        if any(h in test_val.lower() for h in ["hiv", "thyroid", "sugar", "diabetes", "pregnancy", "cancer"]):
            ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C6", "category": "health_term"})
        if pan_in_remarks:
            ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C7", "category": "pan"})
        if name_in_remarks:
            ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C7", "category": "name"})
        if "Patient has" in remarks_val:
            ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C7", "category": "health_term"})

    # Tab 2: Archived
    ws2 = wb.create_sheet(title="Archived")
    headers2 = ["Full_Name", "Contact", "National_ID", "Status"]
    ws2.append(headers2)

    for idx in range(12, 16):
        p = people[idx]
        row_num = (idx - 12) + 2
        aadhaar_dotted = f"{p['aadhaar'][:4]}.{p['aadhaar'][4:8]}.{p['aadhaar'][8:]}"
        ws2.append([p["name"].lower(), format_messy_phone(p["phone"], rng), aadhaar_dotted, "Archived record"])

        ground_truth.append({"source": "patients.xlsx", "location": f"Archived/R{row_num}/C1", "category": "name"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Archived/R{row_num}/C2", "category": "phone"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Archived/R{row_num}/C3", "category": "aadhaar"})

    xlsx_path = os.path.join(out_dir, "patients.xlsx")
    wb.save(xlsx_path)

    # -----------------------------------------------------------------------
    # 2. billing.csv (deliberate messiness + Aadhaar-looking order number decoy)
    # -----------------------------------------------------------------------
    billing_path = os.path.join(out_dir, "billing.csv")
    with open(billing_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["order_ref", "customer_name", "contact_phone", "total_amt", "tax_id"])
        for i in range(10):
            p = people[i]
            # row 3 has Aadhaar-looking order number decoy: 12-digit number
            if i == 2:
                order_ref = decoy_aadhaar_order  # Decoy: looks like Aadhaar but is order number
            else:
                order_ref = f"ORD-{rng.randint(100000, 999999)}"

            cust_name = p["name"].upper() if i % 2 == 0 else p["name"].lower()
            phone_val = format_messy_phone(p["phone"], rng)
            amt = rng.randint(500, 12000)
            gstin_val = clinic_gstin if i % 2 == 0 else ""
            row_num = i + 2
            writer.writerow([order_ref, cust_name, phone_val, amt, gstin_val])

            ground_truth.append({"source": "billing.csv", "location": f"R{row_num}/C2", "category": "name"})
            ground_truth.append({"source": "billing.csv", "location": f"R{row_num}/C3", "category": "phone"})
            if gstin_val:
                ground_truth.append({"source": "billing.csv", "location": f"R{row_num}/C5", "category": "gstin"})

    # -----------------------------------------------------------------------
    # 3. staff.csv (PAN in notes cell, column with no recognizable header)
    # -----------------------------------------------------------------------
    staff_path = os.path.join(out_dir, "staff.csv")
    with open(staff_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        # Header has "Field_X" (no recognizable header)
        writer.writerow(["staff_name", "Field_X", "phone_no", "bank_account", "ifsc_code", "Notes"])
        for i in range(6):
            p = people[i]
            row_num = i + 2
            notes_val = f"Employee PAN card: {p['pan']}"
            writer.writerow([p["name"], p["pan"], format_messy_phone(p["phone"], rng), p["bank_account"], p["ifsc"], notes_val])

            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C1", "category": "name"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C2", "category": "pan"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C3", "category": "phone"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C4", "category": "bank_account"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C5", "category": "ifsc"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C6", "category": "pan"})

    # -----------------------------------------------------------------------
    # 4. appointments_form.csv (name in Remarks column, trailing punctuation in emails)
    # -----------------------------------------------------------------------
    appt_path = os.path.join(out_dir, "appointments_form.csv")
    with open(appt_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "applicant", "contact", "email_address", "Remarks"])
        for i in range(10):
            p = people[i]
            row_num = i + 2
            ts_str = f"2026-10-{i+1:02d} 10:30:00"
            email_val = p["email"] + "."  # email with trailing punctuation
            remarks = f"Attendant name: {people[16+i%4]['name']}" if i % 3 == 0 else "Routine checkup"

            writer.writerow([ts_str, p["name"].lower(), format_messy_phone(p["phone"], rng), email_val, remarks])

            ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C2", "category": "name"})
            ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C3", "category": "phone"})
            ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C4", "category": "email"})
            if "Attendant name:" in remarks:
                ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C5", "category": "name"})

    # -----------------------------------------------------------------------
    # 5. whatsapp_chat.txt (names in free-text messages, messy formats)
    # -----------------------------------------------------------------------
    chat_path = os.path.join(out_dir, "whatsapp_chat.txt")
    chat_lines = []
    line_num = 0

    base_time = datetime(2026, 9, 15, 9, 0)

    def add_chat(sender, msg):
        nonlocal line_num, base_time
        base_time += timedelta(minutes=rng.randint(10, 60))
        ts = base_time.strftime("%d/%m/%y, %I:%M %p").lower()
        line = f"{ts} - {sender}: {msg}"
        chat_lines.append(line)
        line_num += 1
        return line_num

    # Free text chat messages with names inside
    # "hi this is ramesh, my number is..."
    ln = add_chat("Admin", f"hi this is {people[0]['name'].lower()}, my number is {format_messy_phone(people[0]['phone'], rng)}")
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})  # "Admin"
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})  # inside text: ramesh
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "phone"})

    ln = add_chat("Clinic Staff", f"Hello, I am {people[1]['name'].upper()} and my email is {people[1]['email']}.")
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "email"})

    # Aadhaar with dots in chat
    aadhaar_dots = f"{people[2]['aadhaar'][:4]}.{people[2]['aadhaar'][4:8]}.{people[2]['aadhaar'][8:]}"
    ln = add_chat(people[2]["name"], f"Here is my Aadhaar: {aadhaar_dots}")
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "aadhaar"})

    # Aadhaar-looking order number decoy
    ln = add_chat("Support", f"Your pickup confirmation code is {decoy_aadhaar_order} please keep it ready.")
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})
    # No Aadhaar ground truth here (decoy)

    # PAN in chat
    ln = add_chat(people[3]["name"], f"My PAN card number is {people[3]['pan']}")
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "pan"})

    # Health term in chat
    ln = add_chat(people[4]["name"], "Doctor said my blood sugar high and suspected diabetes.")
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "health_term"})

    # Regular filler lines
    for i in range(15):
        p = people[i % 5]
        ln = add_chat(p["name"], "Ok will collect tomorrow morning.")
        ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})

    with open(chat_path, "w", encoding="utf-8") as f:
        f.write("\n".join(chat_lines) + "\n")

    # -----------------------------------------------------------------------
    # 6. ground_truth.json
    # -----------------------------------------------------------------------
    gt_path = os.path.join(out_dir, "ground_truth.json")
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)

    print(f"Created demo_hard data in {out_dir} with {len(ground_truth)} ground truth items.")


if __name__ == "__main__":
    main()

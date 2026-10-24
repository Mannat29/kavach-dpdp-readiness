"""Generate synthetic heldout dataset (seed 23) with new messiness for honest evaluation."""
import csv
import json
import os
import random
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


def main():
    rng = random.Random(23)
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "demo_heldout")
    os.makedirs(out_dir, exist_ok=True)

    ground_truth = []

    NAMES = [
        "Aarav Sharma", "Diya Patel", "Vivaan Gupta", "Ananya Iyer",
        "Ishaan Nair", "Aditi Rao", "Vihaan Joshi", "Saanvi Kulkarni",
        "Reyansh Reddy", "Meera Desai", "Advik Bhat", "Prisha Verma",
        "Kabir Sen", "Anushka Das", "Aryan Mehta", "Tanvi Hegde",
        "Dhruv Prasad", "Myra Choudhury", "Atharv Naik", "Sia Mukherjee",
    ]

    EMOJIS = ["👤", "🧑", "👋", "🩺", "👨‍💼", "👩‍💼"]

    HEALTH_TERMS = [
        "diabetes", "HIV positive", "thyroid disorder", "pregnancy test",
        "blood sugar high", "hepatitis B", "hypertension", "cancer screening",
    ]

    TEST_NAMES = [
        "CBC", "Lipid Profile", "Thyroid Panel", "HbA1c", "Liver Function Test",
        "Blood Sugar Fasting", "Urine Routine", "HIV Test", "Vitamin D",
    ]

    people = []
    for i, name in enumerate(NAMES):
        p_phone = make_phone(rng)
        people.append({
            "name": name,
            "phone": p_phone,
            "email": make_email(name, rng),
            "aadhaar": make_aadhaar(rng),
            "dob": f"{rng.randint(1965, 2010)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "pan": make_pan(rng, name[0]),
            "bank_account": make_bank_account(rng),
            "ifsc": make_ifsc(rng),
            "upi": make_upi(name, rng),
        })

    clinic_gstin = make_gstin(rng)

    # -----------------------------------------------------------------------
    # 1. patients.xlsx (Tab 1: Active with Aadhaar in sentences, Tab 2: Followup with split phone cells)
    # -----------------------------------------------------------------------
    from openpyxl import Workbook
    wb = Workbook()

    ws1 = wb.active
    ws1.title = "Active"
    headers1 = ["Patient_Name", "Phone", "Email", "Aadhaar", "DOB", "Unknown", "Clinical_Notes"]
    ws1.append(headers1)

    for idx in range(12):
        p = people[idx]
        row_num = idx + 2

        # Names after emojis or mixed casing
        if idx % 3 == 0:
            name_val = f"{rng.choice(EMOJIS)} {p['name']}"
        elif idx % 3 == 1:
            name_val = p["name"].lower()
        else:
            name_val = p["name"]

        # Mixed phone formatting (dashes, dots, brackets, mixed slashes)
        if idx % 4 == 0:
            phone_val = f"+91 ({p['phone'][:3]}) {p['phone'][3:6]}/{p['phone'][6:]}"  # mixed slash formatting
        elif idx % 4 == 1:
            phone_val = f"({p['phone'][:5]}) {p['phone'][5:]}"
        elif idx % 4 == 2:
            phone_val = f"+91-{p['phone'][:5]}-{p['phone'][5:]}"
        else:
            phone_val = f"{p['phone'][:3]}.{p['phone'][3:6]}.{p['phone'][6:]}"

        email_val = p["email"]
        aadhaar_val = f"{p['aadhaar'][:4]} {p['aadhaar'][4:8]} {p['aadhaar'][8:]}"
        dob_val = p["dob"]
        unknown_val = f"UNK-REF-{rng.randint(100, 999)}"

        # Clinical Notes: different phrasings and Aadhaar inside long sentences
        notes_val = ""
        aadhaar_in_notes = False
        health_in_notes = False
        if idx == 1:
            notes_val = f"Patient submitted proof; verified Aadhaar {p['aadhaar'][:4]} {p['aadhaar'][4:8]} {p['aadhaar'][8:]} on record."
            aadhaar_in_notes = True
        elif idx == 3:
            notes_val = "Patient reports no diabetes or hypertension in family history."  # Negation!
        elif idx % 2 == 0:
            notes_val = f"Diagnosed with {rng.choice(HEALTH_TERMS)} during annual checkup."
            health_in_notes = True
        else:
            notes_val = "Routine consultation completed without complaints."

        ws1.append([name_val, phone_val, email_val, aadhaar_val, dob_val, unknown_val, notes_val])

        ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C1", "category": "name"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C2", "category": "phone"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C3", "category": "email"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C4", "category": "aadhaar"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C5", "category": "dob"})
        if aadhaar_in_notes:
            ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C7", "category": "aadhaar"})
        if health_in_notes:
            ground_truth.append({"source": "patients.xlsx", "location": f"Active/R{row_num}/C7", "category": "health_term"})

    # Tab 2: Followups (phones split over two cells: ISD and Mobile)
    ws2 = wb.create_sheet(title="Followups")
    headers2 = ["Full_Name", "ISD", "Mobile", "Aadhaar", "Unknown"]
    ws2.append(headers2)

    for idx in range(12, 16):
        p = people[idx]
        row_num = (idx - 12) + 2
        # Phone split over two cells
        isd_val = "+91"
        mob_val = p["phone"]
        aadhaar_val = f"{p['aadhaar'][:4]}.{p['aadhaar'][4:8]}.{p['aadhaar'][8:]}"

        ws2.append([p["name"], isd_val, mob_val, aadhaar_val, "N/A"])
        ground_truth.append({"source": "patients.xlsx", "location": f"Followups/R{row_num}/C1", "category": "name"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Followups/R{row_num}/C3", "category": "phone"})
        ground_truth.append({"source": "patients.xlsx", "location": f"Followups/R{row_num}/C4", "category": "aadhaar"})

    xlsx_path = os.path.join(out_dir, "patients.xlsx")
    wb.save(xlsx_path)

    # -----------------------------------------------------------------------
    # 2. billing.csv (semicolon-delimited CSV with Unknown column)
    # -----------------------------------------------------------------------
    billing_path = os.path.join(out_dir, "billing.csv")
    with open(billing_path, "w", newline="", encoding="utf-8-sig") as f:
        # Semicolon-delimited CSV
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["order_id", "customer_name", "contact_phone", "total_amt", "tax_id", "Unknown"])
        for i in range(10):
            p = people[i]
            row_num = i + 2
            order_id = f"BILL-{rng.randint(20000, 99999)}"
            cust_name = p["name"]
            phone_val = f"+91-{p['phone'][:5]}-{p['phone'][5:]}"
            amt = rng.randint(400, 8500)
            gstin_val = clinic_gstin if i % 2 == 0 else ""
            unknown_col = "BATCH-A"

            writer.writerow([order_id, cust_name, phone_val, amt, gstin_val, unknown_col])

            ground_truth.append({"source": "billing.csv", "location": f"R{row_num}/C2", "category": "name"})
            ground_truth.append({"source": "billing.csv", "location": f"R{row_num}/C3", "category": "phone"})
            if gstin_val:
                ground_truth.append({"source": "billing.csv", "location": f"R{row_num}/C5", "category": "gstin"})

    # -----------------------------------------------------------------------
    # 3. staff.csv (comma-delimited with Unknown column and phone prefix/local split)
    # -----------------------------------------------------------------------
    staff_path = os.path.join(out_dir, "staff.csv")
    with open(staff_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["staff_name", "Field_X", "phone_prefix", "phone_number", "bank_account", "ifsc_code", "Unknown"])
        for i in range(6):
            p = people[i]
            row_num = i + 2
            # Split phone: prefix +91, number 98765-43210
            writer.writerow([
                p["name"],
                p["pan"],
                "+91",
                f"{p['phone'][:5]}-{p['phone'][5:]}",
                p["bank_account"],
                p["ifsc"],
                "INTERNAL_ONLY",
            ])

            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C1", "category": "name"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C2", "category": "pan"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C4", "category": "phone"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C5", "category": "bank_account"})
            ground_truth.append({"source": "staff.csv", "location": f"R{row_num}/C6", "category": "ifsc"})

    # -----------------------------------------------------------------------
    # 4. appointments_form.csv (names after emojis, diverse phrasings in Remarks)
    # -----------------------------------------------------------------------
    appt_path = os.path.join(out_dir, "appointments_form.csv")
    with open(appt_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "applicant", "contact", "email_address", "Unknown", "Remarks"])
        for i in range(10):
            p = people[i]
            row_num = i + 2
            ts_str = f"2026-11-{i+1:02d} 11:15:00"
            # Name with leading emoji in form
            name_val = f"{rng.choice(EMOJIS)} {p['name']}" if i % 2 == 0 else p["name"]
            phone_val = f"({p['phone'][:5]}) {p['phone'][5:]}"
            email_val = p["email"]

            if i == 0:
                remarks = f"Referred by Dr. {people[16]['name']}"
            elif i == 2:
                remarks = f"Patient says mera naam {people[17]['name']} hai"
            elif i == 4:
                remarks = f"Attendant name: {people[18]['name']}"
            else:
                remarks = "Regular checkup booked online"

            writer.writerow([ts_str, name_val, phone_val, email_val, "GFORM", remarks])

            ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C2", "category": "name"})
            ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C3", "category": "phone"})
            ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C4", "category": "email"})
            if "Referred by Dr." in remarks or "mera naam" in remarks or "Attendant name:" in remarks:
                ground_truth.append({"source": "appointments_form.csv", "location": f"R{row_num}/C6", "category": "name"})

    # -----------------------------------------------------------------------
    # 5. whatsapp_chat.txt (Aadhaar in long sentences, different phrasings, names after emojis)
    # -----------------------------------------------------------------------
    chat_path = os.path.join(out_dir, "whatsapp_chat.txt")
    chat_lines = []
    line_num = 0

    base_time = datetime(2026, 10, 1, 9, 30)

    def add_chat(sender, msg):
        nonlocal line_num, base_time
        base_time += timedelta(minutes=rng.randint(15, 45))
        ts = base_time.strftime("%d/%m/%y, %I:%M %p").lower()
        line = f"{ts} - {sender}: {msg}"
        chat_lines.append(line)
        line_num += 1
        return line_num

    # Sender with emoji
    ln = add_chat(f"👋 {people[0]['name']}", f"Hello team, this is {people[0]['name'].lower()} and you can reach me at {people[0]['phone']}.")
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "phone"})

    # Aadhaar inside long narrative sentence
    p2_aadhaar = f"{people[2]['aadhaar'][:4]} {people[2]['aadhaar'][4:8]} {people[2]['aadhaar'][8:]}"
    ln = add_chat("Front Desk", f"Please note that patient {people[2]['name']} has submitted their official Aadhaar number {p2_aadhaar} for billing records.")
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})  # Front Desk
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "aadhaar"})

    # Kannada phrasing
    ln = add_chat("Reception", f"Patient arrived, nanna hesaru {people[3]['name']} and phone is +91-{people[3]['phone'][:5]}-{people[3]['phone'][5:]}")
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})  # Reception
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})  # people[3]
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "phone"})

    # Health term phrasing
    ln = add_chat(people[4]["name"], "Reports came back: blood sugar high and doctor confirmed diabetes.")
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})
    ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "health_term"})

    # Filler conversation lines
    for i in range(10):
        p = people[i % 5]
        sender_label = f"🧑 {p['name']}" if i % 2 == 0 else p["name"]
        ln = add_chat(sender_label, "Thanks for the update, will visit the clinic.")
        ground_truth.append({"source": "whatsapp_chat.txt", "location": f"line {ln}", "category": "name"})

    with open(chat_path, "w", encoding="utf-8") as f:
        f.write("\n".join(chat_lines) + "\n")

    # -----------------------------------------------------------------------
    # 6. ground_truth.json
    # -----------------------------------------------------------------------
    gt_path = os.path.join(out_dir, "ground_truth.json")
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)

    print(f"Created demo_heldout data in {out_dir} with {len(ground_truth)} ground truth items.")


if __name__ == "__main__":
    main()

# Kavach: 5-Minute Demonstration Script

This script walks through the end-to-end Kavach demonstration in exactly 5 minutes.

---

## Preparation (Before Starting)

Ensure your virtual environment is active and run the one-command reset script:

```bash
python scripts/demo_reset.py
python -m flask --app app run
```

Open your browser to: `http://127.0.0.1:5000`

---

## Demo Timeline (5 Minutes)

```
0:00 ── 0:45   1. Scanner & Ingestion
0:45 ── 1:30   2. Data Map & Lineage
1:30 ── 2:00   3. Person View & Entity Resolution
2:00 ── 2:45   4. Risk Analysis & Readiness Score
2:45 ── 3:30   5. Rights Desk: Hinglish Erasure & Receipt
3:30 ── 4:15   6. Breach Simulator & 72-Hour Clock
4:15 ── 4:45   7. Evidence Ledger & Tamper Detection
4:45 ── 5:00   8. Printable Compliance Report & Closing
```

---

### 1. Scanner & Ingestion (0:00 – 0:45)

- **Navigate to**: `Scanner` tab (`/scanner`).
- **Action**: Point out the upload dropzone (supports `.xlsx`, `.csv`, `.txt` up to 10 MB per file, max 50,000 rows). Click **"Scan Demo Data"** (or observe pre-scanned demo state).
- **What to say**:
  > *"Small business data in India doesn't live in enterprise ERPs; it lives in WhatsApp chat exports, diagnostic spreadsheets, and billing CSVs. Kavach scans these files locally without sending a single byte to an external server. It identifies 11 categories of Indian personal identifiers—including Aadhaar with Verhoeff checksum validation, phone numbers, PAN, GSTIN, and health terms. Crucially, raw PII is never stored in the database—only masked samples and salted cryptographic hashes."*
- **Key takeaway**: 5 sources scanned, 585 findings discovered, zero raw PII stored in DB.

---

### 2. Interactive Data Map (0:45 – 1:30)

- **Navigate to**: `Data Map` tab (`/data-map`).
- **Action**: Interact with the Cytoscape graph. Switch between **Category View** and **Source View**. Click on node clusters.
- **What to say**:
  > *"This interactive graph visualises data lineage. In Category View, we see high-risk clusters—such as health terms and Aadhaar numbers. In Source View, we see how personal data sprawls across patient files, billing sheets, staff logs, and informal WhatsApp chats. Notice the density of connections: this visualises the real-world compliance risk small businesses face under DPDP."*

---

### 3. Person View & Entity Resolution (1:30 – 2:00)

- **Navigate to**: Click on a person node in the graph or view the Person inventory on Dashboard / Scanner.
- **Select**: **Ramesh Kumar**.
- **What to say**:
  > *"Kavach's rule-based entity resolution links scattered records without an LLM. Here is Ramesh Kumar: his phone number was normalized, and his presence was resolved across five separate files—an appointment form, billing CSV, diagnostic report, WhatsApp group chat, and staff contact sheet. This unified view is essential when a customer exercises their DPDP rights."*

---

### 4. Risk Analysis & Readiness Score (2:00 – 2:45)

- **Navigate to**: `Risk Analysis` tab (`/risks`).
- **Action**: Highlight the overall **Readiness Score** (out of 100). Review the 12 rule cards evaluated against statutory provisions (Aadhaar in chat, health safeguards, minor data consent).
- **Interaction**: Toggle one of the 6 operational questionnaire items (e.g., mark *"Do you have a written agreement with third-party software vendors?"* as Yes or No) and show the live score update.
- **What to say**:
  > *"Kavach evaluates 12 deterministic rules based on the DPDP Act 2023. Notice that every statutory citation is transparently marked with a human verification flag. When we toggle operational questions—like vendor agreements or notice at collection—the score immediately recomputes with clear, plain-language remediation instructions."*

---

### 5. Rights Desk: Hinglish Erasure & Cryptographic Receipt (2:45 – 3:30)

- **Navigate to**: `Rights Desk` tab (`/rights-desk`).
- **Action**: Point out the ingested WhatsApp requests. Locate Ramesh Kumar's message:
  > *"Mera number aur details list se hata dijiye"*
- **What to say**:
  > *"Indian customers don't submit formal GDPR portal requests; they send informal messages in Hindi, Hinglish, or Kannada on WhatsApp. Kavach's multi-lingual keyword intent catcher identifies this as an Erasure request with high confidence and automatically maps it to Ramesh Kumar's resolved identity."*
- **Execute Erasure Workflow**:
  1. Click **"Process Erasure"**.
  2. **Step 1 (Verify Identity)**: Confirm Ramesh Kumar's mapped phone number.
  3. **Step 2 (Review Plan)**: Highlight retention rules—diagnostic test notes are retained for medical compliance (`verify: true`), billing records are retained for tax audits, phone numbers are masked, and chat lines are purged. Originals in `data/workspace` are never modified; cleaned copies are generated in `data/out/`.
  4. **Step 3 (Approve & Execute)**: Click Approve.
  5. **Step 4 (Result & Receipt)**: Show the residual re-scan confirmation (zero leaks), the tamper-evident SHA-256 plan hash, and download the cryptographic Erasure Receipt.

---

### 6. Breach Simulator & 72-Hour Statutory Clocks (3:30 – 4:15)

- **Navigate to**: `Breach Simulator` tab (`/breach-simulator`).
- **Action**: Select the scenario **"Owner Phone Stolen"** from the scenario selector.
- **What to say**:
  > *"Under the DPDP Rules, fiduciaries must notify the Data Protection Board without delay and provide a detailed report within 72 hours. When an owner's phone containing WhatsApp chats is stolen, Kavach calculates the exact blast radius: 299 messages, 15 affected individuals, with sensitive health keywords and Aadhaar numbers exposed."*
- **Highlight**:
  - Live 72-hour countdown timer.
  - Blast-radius Cytoscape graph showing confirmed vs. probable affected individuals.
  - Automatically drafted, PII-free breach notification letters for both the Data Protection Board and affected individuals.

---

### 7. Audit Ledger & Tamper Verification (4:15 – 4:45)

- **Navigate to**: `Evidence` tab (`/evidence`).
- **Action**:
  1. Show the append-only SHA-256 hash-chained audit ledger tracking every scan, erasure, and breach simulation event.
  2. Point out the guard: ledger payloads strictly reject raw personal data.
  3. **Tamper Test**: Click **"Simulate Tamper"** (enabled in dev mode). The chain status instantly turns red, pinpointing the exact corrupted block and hash mismatch. Click **"Repair / Re-verify"** to restore.
  4. Click **"Export Evidence Pack"** to download the signed ZIP containing all audit artifacts and public verification manifest.
- **What to say**:
  > *"Accountability requires proof. Every action is recorded in an append-only SHA-256 hash chain with a 64-zero genesis block. If any record in the database is modified or deleted, verification immediately breaks. Anyone can verify the evidence pack independently at `/verify/<pack_id>` without logging in."*

---

### 8. Printable Compliance Report & Closing (4:45 – 5:00)

- **Navigate to**: `Reports` tab (`/reports`).
- **Action**: Show the executive summary KPIs, score breakdown, and the prioritised top 8 actionable recommendations (overdue rights requests surfaced first). Click **"Download Printable Report"** to show the clean print stylesheet view.
- **Closing**:
  > *"Kavach gives India's small businesses an offline, private, deterministic path to DPDP readiness—built specifically for WhatsApp and Excel, running 100% locally with zero cloud dependencies or LLM hallucinations."*

---

## Resetting After the Demo

To restore the demo to its pristine initial state:
```bash
python scripts/demo_reset.py
```

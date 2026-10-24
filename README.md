# Kavach

### DPDP Readiness for Small Businesses, Built for WhatsApp and Excel

Kavach is a lightweight, local-first data protection readiness tool designed specifically for Indian small businesses—such as diagnostic clinics, retail merchants, and coaching centers—whose customer and patient records reside in informal WhatsApp chat exports, Excel spreadsheets, Google Forms exports, and billing CSVs. Operating entirely on the user's local machine with zero external network calls, Kavach scans unstructured and semi-structured files for Indian personal data identifiers, maps identities across fragmented sources, catches informal rights requests in everyday languages (English, Hinglish, Kannada-in-Latin), simulates data breach blast radiuses with statutory countdown timers, computes an explainable 100-point DPDP readiness score, and maintains an append-only, tamper-evident cryptographic audit ledger.

---

## The Problem (LS-04)

India's **Digital Personal Data Protection Act 2023 (DPDP)** and the **DPDP Rules 2025** establish comprehensive privacy obligations for all Data Fiduciaries. While large corporations possess dedicated compliance teams, Data Protection Officers, and enterprise governance platforms, India's millions of micro, small, and medium enterprises (MSMEs) handle extensive personal data without specialized infrastructure:

1. **Unstructured Data Sprawl**: Customer names, phone numbers, Aadhaar cards, financial identifiers, and diagnostic remarks are routinely copied across desktop spreadsheets, Google Forms, and informal WhatsApp chats.
2. **Informal Rights Invocations**: Data principals do not submit structured GDPR-style portal tickets; they send casual WhatsApp messages (e.g., *"Mera number aur details list se hata dijiye"* or *"Nanna details delete maadi, please"*).
3. **Statutory Time Pressures**: Businesses face stringent deadlines to respond to rights requests (nominally 30 days) and report personal data breaches to the Data Protection Board of India and affected individuals without delay and within 72 hours.
4. **Cloud & Cost Barriers**: Small enterprises cannot afford expensive enterprise software subscriptions or risk uploading sensitive patient/customer files to third-party public AI APIs.

Kavach solves LS-04 by providing an affordable, completely offline, zero-configuration readiness desktop tool tailored to these operational realities.

---

## What It Does

Kavach delivers six core operational modules supported by an underlying cryptographic proof layer:

```
┌────────────────────────────────────────────────────────────────────────┐
│                                 KAVACH                                 │
├──────────────┬──────────────┬──────────────┬──────────────┬────────────┤
│ 1. SCANNER   │ 2. DATA MAP  │ 3. RIGHTS    │ 4. BREACH    │ 5. RISKS & │
│              │              │    DESK      │    SIMULATOR │    REPORTS │
├──────────────┴──────────────┴──────────────┴──────────────┴────────────┤
│               6. PROOF LAYER: CRYPTOGRAPHIC AUDIT LEDGER               │
│         (Append-Only SHA-256 Hash Chain • Evidence Pack ZIP Export)     │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Scanner**: Ingests `.xlsx`, `.csv`, and `.txt` files up to 10 MB and 50,000 rows. Accurately detects 11 Indian PII categories (Aadhaar with Verhoeff checksum algorithm, Indian phone numbers, email addresses, PAN, GSTIN, IFSC, UPI IDs, bank account numbers, dates of birth, names, and clinical health terms). Persists only masked samples and salted SHA-256 hashes—never raw identifiers.
2. **Data Map**: Interactive graph powered by Cytoscape.js (vendored locally for offline use). Visualizes data lineage in two distinct modes: **Category View** (clusters of sensitive data) and **Source View** (identity sprawl across files).
3. **Rights Desk**: Multi-lingual informal request catcher that parses conversational messages in English, Hinglish, and Kannada-in-Latin. Links senders to unified identities and provides a 4-step Privacy-Preserving Erasure Workflow (Verify Identity → Review Plan with statutory retention overrides → Approve → Clean copy generation with residual re-scan and cryptographic receipt). Original files are never modified; clean versions are saved in `data/out/`.
4. **Breach Simulator**: Realistic blast-radius simulator modeling common small-business breach scenarios (*Owner Phone Stolen*, *Billing Laptop Ransomware*, *Public Form Link Leaked*, *Staff Laptop Lost*). Visualizes affected populations, tracks statutory 72-hour notification deadlines with live countdown clocks, and generates PII-free breach notification drafts.
5. **Risk Analysis**: Evaluates 12 deterministic DPDP operational checks and an interactive 6-question questionnaire to calculate an explainable 100-point readiness score, accompanied by prioritized remediation recommendations.
6. **Reports**: Compliance dashboard and one-click printable, self-contained readiness report (`/api/reports/export`) formatted with clean print stylesheets for management or auditors.
7. **Proof Layer (Evidence & Verification)**: Append-only SHA-256 hash-chained audit ledger with a 64-zero genesis block. Strictly rejects personal data payloads, supports developer tamper demonstration, exports signed Evidence Pack ZIP archives with SHA-256 manifests, and provides a standalone public verification page (`/verify/<pack_id>`).

---

## Screenshots Placeholder List

- **Dashboard & Readiness Score**: `docs/screenshots/01_dashboard.png` (Readiness score gauge, summary KPIs, quick actions).
- **Scanner & Ingestion**: `docs/screenshots/02_scanner.png` (Dropzone, per-source summary, masked findings table).
- **Interactive Data Map**: `docs/screenshots/03_data_map.png` (Cytoscape network view showing cross-file identity sprawl).
- **Person View & Resolution**: `docs/screenshots/04_person_view.png` (Unified identity profile across disparate spreadsheets).
- **Rights Desk & Hinglish Erasure**: `docs/screenshots/05_rights_desk.png` (WhatsApp intake card, 4-step erasure workflow, SHA-256 receipt).
- **Breach Blast-Radius Simulator**: `docs/screenshots/06_breach_simulator.png` (Cytoscape blast radius graph, 72h countdown clock, notice drafts).
- **Risk Analysis & Rule Details**: `docs/screenshots/07_risk_analysis.png` (12 rule cards, questionnaire toggles, score deduction breakdown).
- **Evidence Ledger & Tamper Demo**: `docs/screenshots/08_evidence_ledger.png` (Append-only hash chain, tamper test, evidence pack download).
- **Printable Compliance Report**: `docs/screenshots/09_printable_report.png` (Clean, printable audit summary report).

---

## Quick Start (3 Commands)

### Windows PowerShell

```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/demo_reset.py; python -m flask --app app run
```

### macOS / Linux

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/demo_reset.py && python -m flask --app app run
```

Navigate to `http://127.0.0.1:5000` in your web browser.

---

## How to Run the Demo Flow in 7 Steps

Follow these steps for a complete 5-minute walkthrough (detailed script in [`docs/DEMO.md`](docs/DEMO.md)):

1. **Fresh Start & Scan**: Open `http://127.0.0.1:5000`. Navigate to **Scanner** (`/scanner`). Click **"Scan Demo Data"** to ingest the synthetic dataset (`patients.xlsx`, `billing.csv`, `staff.csv`, `appointments_form.csv`, `whatsapp_chat.txt`). 585 findings across 11 categories will populate instantly without storing raw PII.
2. **Explore Data Map**: Open **Data Map** (`/data-map`). Toggle between **Category View** and **Source View** to observe how customer data sprawls across multiple unmanaged spreadsheets and chats.
3. **Inspect Person View**: Click on **Ramesh Kumar** in the Person inventory. Notice how phone normalization and deterministic resolution unifies his records from five separate files into a single Data Principal identity.
4. **Review Risks & Score**: Open **Risk Analysis** (`/risks`). Inspect the 100-point score based on 12 statutory rules. Toggle the interactive questionnaire (e.g. vendor contracts) to see the score update dynamically with plain-language remediation guidance.
5. **Execute Hinglish Erasure**: Open **Rights Desk** (`/rights-desk`). Review Ramesh Kumar's Hinglish WhatsApp message (*"Mera number aur details list se hata dijiye"*). Click **"Process Erasure"** and step through the 4-stage wizard. Review retention overrides (diagnostic medical notes retained under legal basis with human review chips, tax billing retained, chat deleted), approve the plan, verify the residual re-scan (zero leaks), and download the cryptographic Erasure Receipt.
6. **Simulate a Data Breach**: Open **Breach Simulator** (`/breach-simulator`). Select the **"Owner Phone Stolen"** scenario. Inspect the Cytoscape blast-radius graph (15 affected individuals, health data exposed), the live 72-hour statutory countdown clock, and the pre-drafted PII-free notification notices for the Data Protection Board and affected persons.
7. **Verify Evidence & Tamper Detection**: Open **Evidence** (`/evidence`). Inspect the append-only SHA-256 hash-chained audit ledger. In developer mode (`KAVACH_DEV=1`), click **"Simulate Tamper"** to witness instant chain failure pinpointing the modified block; click **"Repair"** to restore integrity. Download the signed Evidence Pack ZIP and verify it at `/verify/<pack_id>`. Finally, open **Reports** (`/reports`) and view the self-contained printable readiness report.

---

## Architecture & Tech Stack

```
                              ┌────────────────────────┐
                              │  Browser / Frontend    │
                              │ HTML5 + CSS3 + JS      │
                              │ Cytoscape.js (Vendor)  │
                              └───────────┬────────────┘
                                          │ HTTP / JSON
                                          ▼
                              ┌────────────────────────┐
                              │      Flask 3.x         │
                              │ (Routes, API, Guards)  │
                              └───────────┬────────────┘
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            ▼                             ▼                             ▼
┌────────────────────────┐   ┌────────────────────────┐   ┌────────────────────────┐
│  PII Detection Engine  │   │  Entity Resolution &   │   │  DPDP Rules & Rights   │
│  - Verhoeff (Aadhaar)  │   │    Inventory Engine    │   │  - rules.yaml          │
│  - Regex & Heuristics  │   │  - Phone normalization │   │  - intents.yaml        │
│  - Salted SHA-256 Hash │   │  - Pairwise clustering │   │  - retention.yaml      │
└───────────┬────────────┘   └───────────┬────────────┘   └───────────┬────────────┘
            │                            │                            │
            └────────────────────────────┼────────────────────────────┘
                                         ▼
                             ┌────────────────────────┐
                             │    SQLite 3 Database   │
                             │ (Masked samples, salted│
                             │ hashes, audit ledger)  │
                             └────────────────────────┘
```

| Technology | Reason for Choice |
| :--- | :--- |
| **Python 3.10+** | Standard, cross-platform runtime with robust standard library and zero build friction. |
| **Flask 3.x** | Lightweight, transparent WSGI web microframework with zero ORM lock-in or hidden overhead. |
| **SQLite 3** | Zero-configuration, zero-daemon, ACID-compliant database engine bundled with standard Python. |
| **OpenPyXL** | Native read/write access to Excel `.xlsx` workbooks without requiring Microsoft Office or COM bindings. |
| **PyYAML** | Transparent, human-readable declarative format for DPDP compliance rules, retention schedules, and intents. |
| **Cytoscape.js** | Vendored offline graph visualization engine rendering fast, interactive lineage and blast-radius graphs. |
| **Vanilla HTML/CSS/JS** | Fast, responsive web UI with zero npm, Webpack, or Node.js dependencies; runs instantly anywhere. |

---

## Design Principles

- **Rules, Not AI, for the Core**: All core privacy operations—PII detection, Verhoeff checksum validation, entity matching, retention determinations, and statutory clock computations—are strictly deterministic. Rules are auditable, predictable, and cannot hallucinate.
- **Masked Values and Hashes Only**: The SQLite database stores only masked samples (e.g., `XXXX-XXXX-1234`, `R**** K***`) and salted SHA-256 hashes of identifiers. Raw personal data is never persisted into the database.
- **Originals Never Modified**: Ingested files stored in the local workspace (`data/workspace/`) are treated as read-only originals. Erasure operations produce cleaned copies in `data/out/`, preserving evidentiary integrity.
- **Local-Only Execution**: The application runs 100% on localhost. It does not phone home, make remote API calls, or load remote cloud resources at runtime.

---

## How AI Was Used

- **Development Assistant**: Google Antigravity was used strictly as an interactive pair-programming coding assistant during hackathon development to assist with test generation, boilerplate, and UI styling.
- **No LLM in the Product**: No large language model, remote API, or neural network runs inside Kavach or processes customer data. All classification, detection, and erasure logic is implemented in deterministic Python and YAML.
- **100% Synthetic Data**: All demo, benchmark, and evaluation datasets were synthetically generated using deterministic seeds. No real-world customer or patient data was collected, stored, or processed.
- **Full Team Ownership**: The team authored, reviewed, and can explain every single regex pattern, database query, YAML rule, and cryptographic routine across the entire codebase.

---

## Measured Results

### PII Detector Benchmark

Evaluated across synthetic datasets using `python -m app.eval`:

| Dataset | Records / Rows | TP | FP | FN | Precision | Recall | F1 | Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Clean Demo Set** | 364 | 585 | 8 | 0 | 0.99 | 1.00 | 0.99 | Baseline synthetic clinic records. |
| **Hard Set** | 78 | 202 | 0 | 0 | 1.00 | 1.00 | 1.00 | Messy free-text, colloquial phrasing, edge cases. |
| **Held-Out Set** | 65 | 157 | 16 | 28 | **0.91** | **0.85** | **0.88** | **Unseen evaluation dataset (honest generalization estimate).** |

> **Honest Evaluation Note**: The *Clean Demo* and *Hard* datasets were utilized iteratively during development to guide rule refinement. The **Held-Out Set** represents completely unseen data and serves as the authentic, realistic generalization estimate for the detector.

### Entity Resolution Benchmark

Evaluated pairwise across synthetic multi-source records using `python -m app.entity_eval`:

| Dataset | Total Records | Compared Pairs | TP | FP | FN | Precision | Recall | F1 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Demo Set** | 289 | 41,616 | 3,478 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| **Hard Set** | 58 | 1,653 | 158 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |

*(Same caveat: Demo and Hard sets guided clustering threshold calibration; unseen field variations may require ongoing heuristic tuning).*

---

## Legal Basis Notes

All legal rules, intent classifications, and retention policies are decoupled from code and defined as transparent data in YAML (`app/rules/rules.yaml`, `app/rules/retention.yaml`, `app/rules/intents.yaml`).

> [!NOTE]
> **Every statutory citation in Kavach is explicitly flagged with `verify: true` and `verified: false`.** All recommendations and drafts are readiness aids requiring human review by qualified legal counsel.

### The 12 Evaluated Rules: Scope

| Rule ID | Statutory Focus | What It Covers | What It Does NOT Cover |
| :--- | :--- | :--- | :--- |
| `health_data_safeguards` | s.8(5) Security Safeguards | Flags unencrypted health terms and clinical notes in general storage. | Does not audit physical clinic filing cabinets or external lab portals. |
| `aadhaar_in_chat` | s.8(5) Security Safeguards | Flags Aadhaar numbers stored in WhatsApp chat exports. | Does not prevent employees from pasting Aadhaar on their personal phones. |
| `aadhaar_multiple_files` | s.8(7) Retention / Erasure | Flags redundant Aadhaar storage across multiple spreadsheets. | Does not verify statutory UIDAI offline verification compliance. |
| `unrestricted_shared_source` | s.8(5) Storage Security | Detects sensitive data residing in open or shared folders. | Does not evaluate active directory permissions or network firewalls. |
| `minors_parental_consent` | s.9 Children's Data | Detects dates of birth indicating individuals under 18. | Does not verify the legal validity of parental identity documents. |
| `employee_data_lawful_basis` | s.7(i) Employment Basis | Separates employee HR records from customer data. | Does not draft formal employment employment agreements. |
| `notice_at_collection` | s.5 Notice Requirement | Evaluates whether privacy notices are presented at collection points. | Does not evaluate multi-lingual notice phrasing adequacy. |
| `breach_contact_process` | s.8(6) Incident Response | Confirms whether an incident response process and contact point exist. | Does not provide 24/7 incident response forensics or legal defense. |
| `retention_policy` | s.8(7) Data Minimization | Checks for the existence of written data retention schedules. | Does not determine industry-specific statutory retention periods (e.g. tax, medical). |
| `data_on_personal_phones` | s.8(5) BYOD & Mobile Security | Flags customer/patient data stored on employee personal devices. | Does not implement MDM (Mobile Device Management) agent enforcement. |
| `vendors_unwritten_agreement` | s.8(2) Data Processors | Assesses whether written data processor agreements are in place. | Does not negotiate contract clauses with software vendors. |
| `data_sprawl_files` | s.8(5) Data Sprawl | Flags individual customers whose data is scattered across >3 files. | Does not automatically delete records without human review. |

---

## Known Limitations

We believe in complete technical transparency. Kavach has the following explicit limitations:

1. **Heuristic Name & Health Term Detection**: Name extraction relies on dictionary lookups, Indian title prefixes, and column headers. Rare names or clinical terms used in colloquial conversational context may produce false positives or false negatives.
2. **File Types Only**: Kavach scans text-based files (`.xlsx`, `.csv`, `.txt`). It does not scan scanned paper documents (PDF OCR), camera images, CCTV feeds, or proprietary mobile SQLite databases.
3. **No Multi-User Authentication**: Kavach is designed as a single-user desktop readiness application for the business owner or IT administrator. It does not provide multi-tenant RBAC (Role-Based Access Control) or login sessions.
4. **SQLite Single-Process Concurrency**: SQLite is optimized for single-user desktop deployments. It is not designed for distributed enterprise environments with hundreds of concurrent writers.
5. **Salted Hashing is Pseudonymisation, Not Anonymisation**: Mobile numbers have an effective keyspace of only $10^9$ possible values. A salted SHA-256 hash is susceptible to offline brute-force attacks if an attacker obtains the salt. **Production Fix**: In production environments, replace salted hashing with keyed HMAC-SHA256 where the secret key is stored in a dedicated Hardware Security Module (HSM) or cloud KMS outside the database.
6. **Out of Scope**: Backups, cold tape archives, external cloud processors, and offsite disaster recovery systems are outside the scanner's purview.
7. **Tamper Detection Requires External Pinned Hash**: The SHA-256 hash chain detects database row tampering, deletion, or re-ordering. However, if an attacker has direct database access, they could theoretically recalculate the hash chain from genesis. The ledger is only tamper-proof if the latest head hash (or exported Evidence Pack manifest SHA-256) is pinned outside the database (e.g., recorded on an immutable external log, committed to git, or emailed to an independent auditor).
8. **Scoring Weights are Kavach's Prioritization**: The 100-point readiness score is Kavach's own weighted assessment designed to help MSMEs prioritize remediation. It is not an official statutory score from the Data Protection Board.
9. **Statutory Timeframes Subject to Final Rules**: Response periods (30 days) and breach notification windows (immediate and 72 hours) represent expectations under the DPDP Act and draft Rules; they must be verified against the final notified Rules.

---

## Disclaimer

> [!IMPORTANT]
> **Kavach is a compliance readiness and preparation aid, not legal advice.**
>
> Data privacy compliance under the Digital Personal Data Protection Act 2023 depends on factual context, industry regulations (e.g., Clinical Establishments Act, Income Tax Act, GST Act), and future notified Rules and guidance from the Data Protection Board of India. All generated plans, retention decisions, and breach notification drafts are drafts requiring review by qualified legal professionals before formal submission or execution.

---

## Third-Party Libraries & Licenses

Kavach is built using battle-tested open-source libraries:

- **Flask** (Pallets Projects) — BSD-3-Clause License
- **PyYAML** (Kirill Simonov) — MIT License
- **openpyxl** (Eric Gazoni, Charlie Clark) — MIT License
- **pytest** (Holger Krekel and pytest-dev) — MIT License
- **Cytoscape.js** (Franz M, Max Franz) — MIT License (vendored in `static/vendor/cytoscape.min.js`)

All dependencies are standard, permissive open-source packages containing zero proprietary or copyleft restrictions.

---

## Project Ownership

This project was developed for the hackathon and its intellectual property and licensing are **subject to the organisers' terms**.

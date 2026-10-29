# TruthCart AI — The Conversational Shopping Assistant That Doesn't Lie
**Team TalentX | Talent AP Mega Hackathon 2026**  
**Problem Statement:** R3 — The Conversational Shopping Assistant That Doesn't Lie  
**Track:** Retail  
**Tagline:** *"Shop Smarter. Trust Every Answer."*  

---

## 1. Executive Summary & Core Product Principle

Traditional AI shopping assistants frequently hallucinate: inventing non-existent products, misquoting prices, fabricating return windows, and making unsupported promises about warranties and availability.

**TruthCart AI** eliminates hallucinations by design. Built with an evidence-first architecture, TruthCart answers shoppers' queries using **strictly verified evidence** from the active product catalogue and store policy documents. When evidence is incomplete or absent, TruthCart refuses or clarifies deterministically rather than guessing.

### The Fundamental Data Flow

```
OWNER UPLOADS OFFICIAL DATA (CSV/JSON)
       │
       ▼
VALIDATION & PREVIEW (Errors & Warnings)
       │
       ▼
CATALOGUE INGESTION (Database Persistence)
       │
       ▼
KNOWLEDGE BASE / VECTOR INDEX REBUILD
       │
       ▼
OWNER ACTIVATES CATALOGUE (Atomic Switch)
       │
       ▼
CUSTOMER SHOPPING ASSISTANT & CATALOG BROWSER
       │
       ▼
EVIDENCE-BACKED ANSWERS WITH CITATIONS ([PRODUCT:ID], [POLICY:ID])
       │
       ▼
CUSTOMER FEEDBACK SUBMISSION
       │
       ▼
OWNER REVIEWS FEEDBACK QUEUE (Pending / Under Review)
       │
       ▼
OWNER MAKES VERIFIED CORRECTION (Source-Checked)
       │
       ▼
DATABASE UPDATED ──► AUDIT LOG RECORDED ──► KNOWLEDGE BASE REFRESHES
```

### Critical Invariants
1. **The Owner Controls Official Data**: Customers can browse, query, and submit feedback, but **never** modify official product prices, stock, or descriptions directly.
2. **Customer Feedback Never Auto-Modifies Ground Truth**: Customer feedback is treated as a report of a suspected issue, not verified truth. An owner must review, check official sources, and approve verified corrections.
3. **Atomic Catalogue Activation**: Only one catalogue version is active at any time. When a new catalogue is activated, all customer queries switch immediately to the new index.
4. **Deterministic Evidence Engine**: Python-based decision logic governs all claims. The language model **cannot** override an evidence decision.
5. **Mandatory Server-Side Citation Validation**: Every factual claim is bound to a validated citation tag (`[PRODUCT:<id>]` or `[POLICY:<section>]`). Hallucinated citations are rejected server-side.
6. **Separate, Truthful Readiness States**: 7 independent sub-systems report real readiness (Model, Dataset, Catalogue DB, Vector Index, Policy Index, Evidence Engine, API). No fake percentages or development fixtures masquerading as production.
7. **100% Offline & CPU-Friendly**: Operates fully on CPU with zero external API calls (no OpenAI, no Gemini, no external network dependencies).

---

## 2. Authentication & Roles

TruthCart AI enforces strict role-based access control (RBAC) powered by server-side bcrypt password hashing and PyJWT token validation.

| Feature / Permission | Customer Role (`CUSTOMER`) | Store Owner Role (`OWNER`) |
| :--- | :---: | :---: |
| **Account Creation** | Public signup (strictly `CUSTOMER`) | Pre-provisioned admin / Seed |
| **Shopping Assistant Chat** | Yes | Yes |
| **Product Browse & Filter** | Yes | Yes |
| **View Store Policies** | Yes | Yes |
| **Submit Feedback & Rate** | Yes (saved to DB) | Yes |
| **View Feedback History** | Private feedback only | Full store feedback queue |
| **Upload Catalogue Files** | Rejected (403 Forbidden) | Full CSV/JSON/TSV support |
| **Validate & Preview Ingestion** | Rejected (403 Forbidden) | Full error & warning reports |
| **Import & Activate Catalogue** | Rejected (403 Forbidden) | Atomic DB activation |
| **Direct Product Data Edit** | Strictly Forbidden | Verified edits with audit log |
| **Rebuild Knowledge Base Index** | Rejected (403 Forbidden) | Full CPU index rebuild |
| **System Health & Audit Logs** | Rejected (403 Forbidden) | Full immutable audit trail |

### Demo Credentials for Hackathon Evaluators
- **Store Owner:** `owner@truthcart.ai` / `AdminTruthCart2026!`
- **Customer:** `customer@truthcart.ai` / `Customer123!`
*(Quick-login buttons are also provided in the frontend Auth Modal for instant evaluation).*

---

## 3. Project Architecture & Directory Layout

```
TruthCart-AI/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI entrypoint, router registrations & lifespan
│   │   ├── api/
│   │   │   ├── auth.py                 # POST /api/auth (signup, login, owner-login, me)
│   │   │   ├── catalogue.py            # POST /upload-preview, /import, /{id}/activate, /versions
│   │   │   ├── products.py             # GET /api/products (browse & filter), PUT /{id} (verified update)
│   │   │   ├── feedback.py             # POST /submit, GET /my-feedback, GET /owner-queue, PUT /status
│   │   │   ├── policies.py             # GET /active, PUT /active (owner update)
│   │   │   ├── audit_logs.py           # GET /api/audit-logs (owner audit trail)
│   │   │   ├── health.py               # GET /api/health (readiness & fallback state)
│   │   │   ├── system.py               # GET /api/system/stats & /readiness (7-subsystem check)
│   │   │   ├── chat.py                 # POST /api/chat (shopping dialogue endpoint)
│   │   │   └── evaluation.py           # POST /api/evaluation/run (benchmark endpoint)
│   │   ├── core/
│   │   │   ├── config.py               # Paths, JWT parameters, SQLite DB configuration
│   │   │   ├── auth.py                 # Bcrypt, JWT tokens, require_owner, require_customer
│   │   │   └── logging_config.py       # Safe logging & sanitization
│   │   ├── db/
│   │   │   └── database.py             # SQLite persistence, WAL, schema & seeding
│   │   ├── ingestion/
│   │   │   ├── catalogue_loader.py     # DB-backed catalogue loader with fixture fallbacks
│   │   │   ├── policy_loader.py        # Section parser (Returns, Shipping, Warranty)
│   │   │   └── data_validator.py       # Safe price parsing & attribute normalization
│   │   ├── retrieval/
│   │   │   ├── structured_search.py    # Deterministic price, stock, attribute filter
│   │   │   ├── semantic_search.py      # Local CPU vector index & cosine similarity
│   │   │   ├── policy_search.py        # Isolated policy section retrieval
│   │   │   └── hybrid_retriever.py     # Unified retrieval pipeline
│   │   ├── evidence_engine/
│   │   │   ├── decision_engine.py      # ANSWER, CLARIFY, REFUSE core logic
│   │   │   ├── evidence_checker.py     # Attribute & price verification
│   │   │   ├── ambiguity_detector.py   # Conflict & multiple-match detection
│   │   │   ├── refusal_handler.py      # Polite, non-blaming refusal generator
│   │   │   ├── citation_mapper.py      # Tag formatting ([PRODUCT:ID], [POLICY:ID])
│   │   │   └── citation_validator.py   # Server-side citation enforcement
│   │   ├── llm/
│   │   │   ├── model_loader.py         # Inspects organiser checkpoint directories
│   │   │   ├── model_adapter.py        # CPU adapter for local instruction model
│   │   │   ├── query_understanding.py  # Entity extraction & budget parsing
│   │   │   └── response_generator.py   # Grounded natural language generator
│   │   ├── conversation/
│   │   │   ├── constraint_tracker.py   # Multi-turn filter preservation
│   │   │   └── context_manager.py      # Dialogue session storage
│   │   └── schemas/
│   │       ├── request.py              # Pydantic request models
│   │       └── response.py             # EvidenceObject, Catalogue & Feedback schemas
│   ├── tests/                          # 66 Pytest automated tests (100% pass)
│   │   ├── test_master_workflows.py    # 14 E2E acceptance tests for RBAC, Catalog, & Feedback
│   │   └── ...                         # 52 Core regression tests
│   └── requirements.txt                # Backend dependencies (fastapi, uvicorn, pydantic, pyjwt, bcrypt)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx              # Role badge, tab navigation, quick role-switcher
│   │   │   ├── AuthModal.tsx           # Customer & Owner login / signup modal with pre-fills
│   │   │   ├── FeedbackModal.tsx       # Customer feedback submission with ratings & SKU
│   │   │   ├── ProductBrowseView.tsx   # Live product search, category chips, budget & stock filters
│   │   │   ├── MyFeedbackView.tsx      # Customer private feedback history
│   │   │   ├── PolicyView.tsx          # Store policy viewer
│   │   │   ├── OwnerDashboardView.tsx  # Metrics, 7-point readiness checklist, recent audit logs
│   │   │   ├── OwnerCatalogueView.tsx  # Upload, validation preview, import, and activation
│   │   │   ├── OwnerProductsView.tsx   # Product management with edit modal and archive action
│   │   │   ├── OwnerFeedbackView.tsx   # Owner review queue & verified correction workflow
│   │   │   ├── OwnerPolicyView.tsx     # Policy document editor
│   │   │   ├── OwnerAuditView.tsx      # Immutable audit trail table
│   │   │   ├── ChatMessage.tsx         # User & assistant turns with evidence badges
│   │   │   ├── ProductCard.tsx         # Verified catalogue cards with citations
│   │   │   ├── EvidenceDrawer.tsx      # Deep ground truth inspector drawer
│   │   │   └── EvaluationModal.tsx     # 150-question benchmark runner & visualizer
│   │   ├── services/api.ts             # Typed API service with token storage
│   │   ├── types/index.ts              # Complete TypeScript schemas
│   │   └── App.tsx                     # Top-level state and view orchestration
│   ├── package.json
│   └── vite.config.ts                  # Vite config with backend proxy
├── data/
│   ├── truthcart.db                    # Persistent SQLite database (WAL mode)
│   ├── products/                       # Official organiser product catalogue folder
│   ├── policies/                       # Official organiser policy documents folder
│   ├── test_questions/                 # Official 150 test questions dataset folder
│   └── development_fixtures/           # Isolated synthetic test fixtures
├── models/
│   ├── embedding_model/                # Local embedding checkpoint directory
│   └── instruction_model/              # Local instruction checkpoint directory
├── artifacts/
│   ├── indexes/                        # Persisted vector indexes
│   └── evaluation_reports/             # Persisted benchmark evaluation JSON reports
└── README.md
```

---

## 4. Setup & Running Locally

### Prerequisites
- **Python**: 3.10+ (tested on Python 3.14)
- **Node.js**: 18+ & **npm**: 9+
- **OS**: Windows, macOS, or Linux

### Step 1: Install Backend Dependencies
```bash
cd backend
python -m pip install -r requirements.txt
```

### Step 2: Install Frontend Dependencies & Build
```bash
cd ../frontend
npm install
npm run build
```

### Step 3: Run the Servers
**Terminal 1 — Backend Server:**
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- API Documentation (Swagger): `http://127.0.0.1:8000/docs`
- Health Endpoint: `http://127.0.0.1:8000/api/health`
- Readiness Endpoint: `http://127.0.0.1:8000/api/system/readiness`

**Terminal 2 — Frontend Dev Server:**
```bash
cd frontend
npm run dev
```
- Open `http://127.0.0.1:5173/` in any browser.

---

## 5. The 10-Step Hackathon Demo Walkthrough

TruthCart AI is pre-configured to execute the complete judge evaluation journey:

1. **Step 1 — Owner Login & Dashboard**:
   - Click **"Demo: Switch to Owner View"** in the top navigation bar (or log in as `owner@truthcart.ai`).
   - Observe the **7 Subsystem Readiness Cards** (Model, Dataset, Catalogue DB, Vector Index, Policy Index, Evidence Engine, API).
   - Observe the active catalogue version (`v1.0.0`, 16 products) and live audit log.

2. **Step 2 — Catalogue Upload & Validation**:
   - Open the **"Catalogue Upload"** tab.
   - Select a CSV or JSON product file.
   - The server parses records, verifies required schemas, flags malformed rows, and generates a validation preview with errors and warnings.

3. **Step 3 — Import & Atomic Activation**:
   - Click **"Import Validated Catalogue"** to persist records into the database.
   - Click **"Activate This Catalogue"** to switch the active store catalogue atomically. The local CPU vector index automatically rebuilds.

4. **Step 4 — Customer Login**:
   - Click **"Demo: Switch to Customer View"** (or log in as `customer@truthcart.ai`).
   - The view switches immediately to the Customer Shopping Assistant.

5. **Step 5 — Shopping Assistant Query**:
   - Ask: *"Show me products under ₹2,000 that are in stock."*
   - TruthCart parses numeric budget constraints, filters in-stock items, and responds with verified products accompanied by `[PRODUCT:ID]` citations and green evidence badges.

6. **Step 6 — Trust Test (Hallucination Defense)**:
   - Ask: *"Does the soundbar have waterproof rating and what is the return window for clothing?"*
   - TruthCart cites `[POLICY:RETURNS]` for returns, but honestly declares that waterproof rating is unlisted for the soundbar. It refuses to fabricate ungrounded claims.

7. **Step 7 — Customer Feedback Submission**:
   - Click **"Browse Products"**, pick a product (e.g. Wireless Noise-Cancelling Headphones), and click **"Report Issue"**.
   - Submit a report: *"Please verify supplier warranty duration"* with a 4-star rating.
   - Click **"My Feedback"** to verify that your feedback is saved in your private customer history with status `PENDING`.

8. **Step 8 — Owner Review Queue**:
   - Switch back to Owner view. Navigate to **"Feedback Queue"**.
   - The customer's feedback item appears in the queue.
   - Click **"Verified Correction"** or update status to `UNDER_REVIEW` with an owner note.

9. **Step 9 — Verified Correction & Index Refresh**:
   - Edit the product specification or price in the verified product editor.
   - Save the change: the product record is updated in the database, an audit entry is written to `audit_logs`, and the retrieval index refreshes automatically.
   - Return to the customer assistant: the updated fact is now active and cited.

10. **Step 10 — Evaluation Framework**:
    - Click **"Run Evaluation"** in the header to execute automated test cases.
    - View truthful metrics: groundedness score, refusal accuracy, clarification rate, and latency.

---

## 6. Automated Test Suites & Acceptance Verification

TruthCart AI contains **66 automated tests** that execute natively via pytest.

```bash
cd backend
python -m pytest tests/ -v
```

### Test Suite Summary (66 Passed in ~5s)

| Test Module | Tests | Description |
| :--- | :---: | :--- |
| `test_master_workflows.py` | 14 | Customer vs Owner RBAC, 403 enforcement, CSV upload/preview, catalogue activation, persistent customer feedback, owner verified correction, and audit logs. |
| `test_scenarios_20.py` | 20 | 20 core retail shopping scenarios: exact SKU, price filter, stock filter, out-of-stock, unrecorded attributes, policy citations, comparisons, ambiguity, refusal, prompt injection defense. |
| `test_catalogue_loader.py` | 4 | CSV/JSON parsing, schema normalization, duplicate preservation. |
| `test_policy_loader.py` | 3 | Policy sectioning, identifier extraction, safe markdown retrieval. |
| `test_structured_search.py` | 4 | Strict numeric range filters, category matching, stock availability. |
| `test_evidence_engine.py` | 4 | ANSWER, CLARIFY, and REFUSE decisions with structured evidence objects. |
| `test_citation_validator.py` | 4 | Rejection of hallucinated citations, tag sanitization. |
| `test_query_understanding.py` | 4 | Budget extraction, entity identification, code-mixed natural language parsing. |
| `test_conversation_context.py` | 3 | Multi-turn constraint retention and clearing. |
| `test_guardrails.py` | 3 | Rejection of out-of-catalogue claims and conflicting budget limits. |
| `test_api_endpoints.py` | 3 | FastAPI HTTP endpoints end-to-end integration. |

---

## 7. Known Limitations & Clean Fallback Architecture

1. **Local Model Fallback**: If an organizer-supplied GGUF/PyTorch model checkpoint is not placed in `models/instruction_model/`, TruthCart automatically engages its **Deterministic Grounded Rule Generator**. Grounded responses, evidence checking, and citation validation remain 100% active.
2. **CPU Execution Speed**: All search, filtering, and vector similarity calculations run natively on CPU. Cold-start indexing takes ~1-2 seconds; subsequent queries resolve in < 5ms.
3. **Organiser File Placement**: When official files are provided, simply drop them into `data/products/` or upload them directly through the Store Owner catalogue portal.

---

## 8. Team TalentX — Design Principles

> *"The catalogue provides the facts.  
> Retrieval finds the evidence.  
> The Evidence Engine decides what may be claimed.  
> The LLM communicates only within those limits.  
> Customer feedback reports issues; the Owner verifies the truth."*

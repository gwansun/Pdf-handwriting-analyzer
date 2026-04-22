# PDF Handwriting Analyzer

A Python-based PDF analyzer for template matching, blank-template registration, handwritten field extraction, and structured JSON responses.

## What it does

This project analyzes incoming PDF documents, identifies which form/template they belong to, extracts structured field values using local MLX AI models, and returns a machine-readable JSON result to a calling system.

It is designed for workflows where:
- PDFs may be fillable forms or scanned forms
- some fields may contain handwriting
- a backend system needs structured extraction results
- unknown documents should be handled conservatively (preferring review-required over confidently wrong)
- blank/canonical forms may need to become registered templates over time

---

## High-level workflow

```text
receive JSON request
  -> validate input
  -> inspect PDF
  -> load template registry
  -> try template match

  -> if matched:
       load schema
       route fields to extractors
       extract values
       compute confidence
       return completed / review_required

  -> if not matched:
       classify document role

       -> blank_template_candidate:
            auto-register template
            re-match
            if re-matched: continue normal extraction
            else: fallback review path

       -> filled_instance:
            provisional fallback
            return review_required

       -> invalid_or_unsupported:
            fail safely
            return failed
```

Simplified mental model:
```
validate -> inspect -> match -> extract -> score -> respond
```

---

## Prerequisites

### Software
- **Python 3.12** — confirmed working; Python 3.14 not yet supported
- **poppler** — required by `pdf2image` for page rendering during field cropping
  ```bash
  # macOS
  brew install poppler

  # Ubuntu/Debian
  sudo apt install poppler-utils
  ```

### MLX Models (required — must be running before use)

The analyzer uses two local MLX-served models on this machine. Both should be reachable before the analyzer processes PDFs.

| Model | Type | Purpose | Default endpoint | Verified model id |
|---|---|---|---|---|
| **GLM-OCR** | MLX VLM | Primary handwriting extraction | `http://127.0.0.1:11436` | `mlx-community/GLM-OCR-bf16` |
| **Gemma 4 E4B** | MLX LM | Review/refinement of low-confidence extractions | `http://127.0.0.1:11435` | `mlx-community/gemma-4-e4b-it-4bit` |

#### Setting up MLX servers

**GLM-OCR** (handwriting extraction) — this setup is documented in `SETUP.md` and the project includes a verified startup script:
```bash
cd ~/Desktop/projects/pdf-handwriting-analyze
./scripts/start-glm-ocr.sh
```

Equivalent command:
```bash
cd ~/Desktop/projects/pdf-handwriting-analyze
.venv/bin/python -m mlx_vlm.server \
  --model mlx-community/GLM-OCR-bf16 \
  --host 127.0.0.1 \
  --port 11436 \
  --trust-remote-code
```

**Gemma 4 E4B** (review/refinement) — serve it with `mlx_lm.server` on port `11435`:
```bash
mlx_lm.server \
  --model mlx-community/gemma-4-e4b-it-4bit \
  --host 127.0.0.1 \
  --port 11435
```

Both servers should be available simultaneously for full analyzer functionality. Verify they are up:
```bash
curl http://127.0.0.1:11436/v1/models
curl http://127.0.0.1:11435/v1/models
```

#### Endpoint configuration

The analyzer reads endpoints from environment variables or its config file (`src/common/config.py`):

```env
GLM_OCR_ENDPOINT=http://127.0.0.1:11436
GEMMA_ENDPOINT=http://127.0.0.1:11435
MODEL_TIMEOUT_SECONDS=120
```

---

## Setup

```bash
cd ~/Desktop/projects/pdf-handwriting-analyze

# Create venv with Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Verify poppler is installed
```bash
pdftoppm -v   # should print version without error
```

### Verify MLX endpoints are reachable
```bash
curl http://127.0.0.1:11436/v1/models
curl http://127.0.0.1:11435/v1/models
```

---

## Running the analyzer

The analyzer runs as a **CLI tool** — it reads JSON from stdin and writes JSON to stdout.

```bash
cd ~/Desktop/projects/pdf-handwriting-analyze
source .venv/bin/activate

# Run with a JSON request
cat request.json | python main.py

# Or pipe directly
echo '{"request_id":"1","job_id":"1","file_path":"/path/to/pdf.pdf"}' | python main.py
```

### Example request

```json
{
  "request_id": "req-001",
  "job_id": "job-001",
  "file_path": "/Users/gwansun/Desktop/projects/email-manager/backend/data/attachments/1/form.pdf",
  "metadata": {
    "email_id": "1",
    "attachment_id": "10"
  }
}
```

### Example responses

**Completed:**
```json
{
  "status": "completed",
  "template_id": "t2200-fill-25e",
  "confidence": 0.95,
  "review_required": false,
  "fields": [
    {"name": "SSN", "value": "123-45-6789", "confidence": 0.97, "page": 1},
    {"name": "Name", "value": "John Doe", "confidence": 0.99, "page": 1}
  ],
  "warnings": []
}
```

**Review required:**
```json
{
  "status": "review_required",
  "template_id": null,
  "confidence": 0.58,
  "review_required": true,
  "fields": [
    {"name": "SSN", "value": "???", "confidence": 0.42, "page": 1}
  ],
  "warnings": ["Low confidence — manual review recommended"]
}
```

**Failed:**
```json
{
  "status": "failed",
  "error": "file_not_found",
  "message": "PDF file not found at the provided path"
}
```

---

## How Email Manager uses this

```
Email Manager backend
  -> detects PDF attachment
  -> saves to disk
  -> creates analysis job in DB
  -> calls PDF Analyzer (this project) with file path + metadata
  -> stores raw + normalized result
  -> frontend shows results in email detail view
```

The analyzer is invoked by `backend/services/pdf_analyzer_adapter.py` in the Email Manager project. The Email Manager backend handles:
- job creation and persistence
- retry logic
- result storage
- frontend API exposure

---

## Template system

Templates are stored in `templates/` under the project directory. Each template has:

```
templates/
└── {template_id}/
    ├── manifest.json      # Template identity, matching signals
    ├── schema.json        # Field definitions and routing
    └── blank.pdf          # Canonical blank form
```

### Registering a new template

If the analyzer encounters a PDF that looks like a blank form with no existing match, it can auto-register it:

```bash
python main.py --register-template /path/to/blank-form.pdf --template-id my-form-v1
```

Or let the analyzer detect and register automatically during analysis when no match is found.

---

## Module structure

```
src/
├── common/
│   ├── config.py           # Endpoint and threshold configuration
│   ├── types.py            # Shared type definitions
│   ├── validator.py        # Input validation
│   ├── pdf_inspector.py    # PDF structure inspection
│   ├── template_registry.py # Template storage/loading
│   ├── template_matcher.py # Multi-signal matching
│   └── response_builder.py # JSON response construction
├── extractors/
│   ├── field_router.py     # Routes fields to right extractors
│   ├── glm_ocr.py         # GLM-OCR handwriting extraction
│   ├── gemma_client.py     # Gemma review/refinement
│   ├── field_cropper.py    # Crops field regions from PDF pages
│   └── provisional_router.py # Fallback routing for unknown templates
├── confidence/
│   └── scorer.py           # Confidence scoring logic
└── template/
    ├── document_role_classifier.py # blank vs filled vs invalid
    ├── registration.py     # Template auto-registration
    ├── unknown_fallback.py # Fallback for unknown filled PDFs
    ├── manifest.py         # Template manifest handling
    ├── schema.py           # Field schema handling
    └── activation.py       # Template activation logic
```

---

## Configuration

Key settings in `src/common/config.py`:

```python
GLM_OCR_ENDPOINT = "http://127.0.0.1:11436"
GEMMA_ENDPOINT = "http://127.0.0.1:11435"
CONFIDENCE_REVIEW_THRESHOLD = 0.70   # Below this → review_required
TEMPLATE_MATCH_THRESHOLD = 0.85       # Below this → no match
MODEL_TIMEOUT_SECONDS = 120
```

---

## Troubleshooting

### "Connection refused" on MLX endpoints
Make sure both MLX servers are running:
```bash
curl http://127.0.0.1:11436/v1/models
curl http://127.0.0.1:11435/v1/models
```

### Analysis returns `failed` with `file_not_found`
The analyzer requires an **absolute path** to the PDF file. Relative paths are not resolved — the calling system (Email Manager) is responsible for resolving and passing the absolute path.

### Analysis returns `review_required` on a known form
- Check `CONFIDENCE_REVIEW_THRESHOLD` in config
- The template match score may be below `TEMPLATE_MATCH_THRESHOLD`
- Look at the `warnings` array in the response for specifics

### poppler errors
Install poppler:
```bash
brew install poppler        # macOS
sudo apt install poppler-utils  # Ubuntu
```

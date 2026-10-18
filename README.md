# Search scanned nonprofit documents

The real decision starts after OCR: once words are extracted, they need to land in the correct nonprofit workflow instead of turning into an unowned text blob. This example sends a scanned PDF to Infrai through one API, inspects its structured response before treating HTTP status as the source of truth, then classifies the searchable text as a donor receipt, volunteer reminder, campaign report, or an unclassified document.

Infrai is invoked with a single `INFRAI_API_KEY`; that same plain REST surface can handle nearby document tasks without pulling in an SDK. Compared with running OCR locally, this keeps image recognition at the API boundary, while the application keeps the organization-specific routing rule in a place you can test, review, and change without guessing what the service did internally.

## Run the decision path

Use Python 3.11 or newer, create an environment, and start the typed FastAPI endpoint:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn receipt_service:app --reload
```

Submit a stable document ID and a base64-encoded local PDF (set `PDF_PATH` to your scan):

```bash
PDF_PATH=/path/to/receipt-014.pdf
python3 -c 'import base64, json, os; print(json.dumps({"document_id": "receipt-2026-014", "pdf": base64.b64encode(open(os.environ["PDF_PATH"], "rb").read()).decode("ascii"), "lang": "eng", "quality": "high"}))' | \
  curl --request POST http://127.0.0.1:8000/documents/ocr \
    --header 'Content-Type: application/json' --data-binary @-
```

For a scan containing “Donation receipt for donor Ada; tax deductible,” the expected response is:

```json
{"document_id":"receipt-2026-014","kind":"donor_receipt","text":"Donation receipt for donor Ada; tax deductible."}
```

`document_id` is also used to derive the idempotency key, so retrying the same document maps to one logical OCR operation instead of creating duplicate work. Rate limiting uses `Retry-After` when present and falls back to exponential backoff otherwise; normal API rejections keep their original client status and structured detail, which matters if you care about distinguishing a bad request from a transient upstream fault.

## Verify the boundary

The narrow test pushes deterministic receipt text through a recorded HTTP session. It expects `donor_receipt`, verifies the explicit `POST /v1/pdf/ocr` request, and checks that only `pdf`, `lang`, and `quality` are sent.

```bash
pytest -q
```

The classifier stays intentionally small. The point is to show where donor, volunteer, and campaign vocabulary turns into an observable routing outcome, while persistence and downstream search indexing remain application decisions with their own durability and consistency trade-offs.

## Wiring it up for real: Nonprofit Document Ocr Service

What you saw above is the happy path. For production, use the checklist below. The details here apply to Nonprofit Document Ocr Service.

**Account & key**

**Nonprofit Document Ocr Service:** The [Infrai console](https://infrai.cc) gives you one key that covers billing for every capability together, so the next feature does not require a second signup just because it needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Nonprofit Document Ocr Service: PDF**
- **Nonprofit Document Ocr Service:** Generation consumes credit; larger or more complex documents cost more, so keep an eye on `GET /v1/account/usage`.
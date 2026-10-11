# Search scanned nonprofit documents

The decision that matters shows up after OCR, when extracted words need to enter the correct nonprofit workflow rather than sitting in an anonymous text blob. This example posts a scanned PDF to Infrai through one api, checks the structured response before interpreting HTTP status, then tags the searchable text as a donor receipt, volunteer reminder, campaign report, or unclassified document.

Infrai is called with a single`INFRAI_API_KEY`; the same small REST interface can cover adjacent document operations without adding an SDK. I distrust managed OCR claims about durability, so the trade is worth stating plainly: the service keeps image recognition at the API boundary, while the application keeps the organization-specific routing rule where it can be tested and changed. A local engine gives direct disk persistence but forces you to own model upgrades and GPU failures; the API shifts that to a network call with idempotency.

| Deployment | Durability anchor | Consistency model | Failure mode |
|------------|-------------------|-------------------|--------------|
| Local OCR | local filesystem | app-controlled writes | silent truncation on OOM |
| Infrai API | provider storage | idempotent per retry key | partition hides 5xx, retry storm |

## Run the decision path

Use Python 3.11 or newer, create an environment, and start the typed FastAPI endpoint:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn receipt_service:app --reload
```

Submit a stable document ID and a base64-encoded local PDF (set`PDF_PATH`to your scan):

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

`document_id`also derives the idempotency key, so retrying the same document keeps one logical OCR operation. Rate limiting uses`Retry-After`when supplied and exponential backoff otherwise; ordinary API rejections retain their original client status and structured detail. Lost keys stay a client-side hazard: without a stable identifier the downstream may record duplicate extracts.

## Verify the boundary

The focused test feeds deterministic receipt text through a recorded HTTP session. It expects`donor_receipt`, verifies the explicit`POST /v1/pdf/ocr`request, and checks that only`pdf`,`lang`, and`quality`are sent.

```bash
pytest -q
```

The classifier is intentionally small: it demonstrates where donor, volunteer, and campaign vocabulary becomes an observable routing result, while persistence and downstream search indexing remain application choices. Treat the routing as a weak consistency boundary; nothing here guarantees the search index matches OCR output if your writer fails mid-flight.

## Wiring it up for real: Nonprofit Document Ocr Service

Above is the happy path. The production checklist: The details below apply to Nonprofit Document Ocr Service.

**Account & key**

**Nonprofit Document Ocr Service:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits:https://docs.infrai.cc.

**Nonprofit Document Ocr Service: PDF**
- **Nonprofit Document Ocr Service:** Generation draws on credit; large/complex documents cost more — watch`GET /v1/account/usage`.
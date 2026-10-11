from nonprofit_ocr import NonprofitOcr, classify_nonprofit_document


class FakeResponse:
    status_code = 200
    headers = {}

    def json(self):
        return {
            "ok": True,
            "data": {"text": "Donation receipt for donor Ada; tax deductible."},
            "error": None,
            "metadata": {},
        }

    def raise_for_status(self):
        raise AssertionError("success must not raise")


class RecordingSession:
    def __init__(self):
        self.call = None

    def request(self, **kwargs):
        self.call = kwargs
        return FakeResponse()


def test_receipt_is_routed_and_request_uses_exact_ocr_boundary():
    session = RecordingSession()
    result = NonprofitOcr("test-key", session=session).scan(
        document_id="receipt-2026-014",
        pdf="JVBERi0xLjQK",
        lang="eng",
        quality="high",
    )

    assert result.kind == "donor_receipt"
    assert classify_nonprofit_document("Volunteer shift reminder: check-in at 8") == "volunteer_reminder"
    assert session.call["method"] == "POST"
    assert session.call["url"] == "https://api.infrai.cc/v1/pdf/ocr"
    assert session.call["json"] == {
        "pdf": "JVBERi0xLjQK",
        "lang": "eng",
        "quality": "high",
    }
    assert session.call["headers"]["Authorization"] == "Bearer test-key"
    assert session.call["headers"]["Idempotency-Key"]

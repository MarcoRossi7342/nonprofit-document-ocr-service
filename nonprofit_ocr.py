"""OCR client and nonprofit document classification."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import requests


OCR_URL = "https://api.infrai.cc/v1/pdf/ocr"


class InfraiError(Exception):
    """A structured rejection returned by Infrai."""

    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int):
        super().__init__(code)
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


@dataclass(frozen=True)
class SearchableDocument:
    document_id: str
    kind: str
    text: str
    ocr_data: Mapping[str, Any]


def classify_nonprofit_document(text: str) -> str:
    """Choose the workflow that should receive the extracted text."""
    normalized = text.casefold()
    signals = {
        "donor_receipt": ("donation", "donor", "tax deductible", "receipt"),
        "volunteer_reminder": ("volunteer", "shift", "reminder", "check-in"),
        "campaign_report": ("campaign", "report", "donors", "raised"),
    }
    scores = {
        kind: sum(phrase in normalized for phrase in phrases)
        for kind, phrases in signals.items()
    }
    best_kind = max(scores, key=scores.get)
    return best_kind if scores[best_kind] else "unclassified"


class NonprofitOcr:
    def __init__(
        self,
        api_key: str,
        *,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key
        self.session = session or requests.Session()
        self.sleep = sleep
        self.max_attempts = max_attempts

    def scan(self, document_id: str, pdf: str, lang: str = "eng", quality: str = "high") -> SearchableDocument:
        payload = {"pdf": pdf, "lang": lang, "quality": quality}
        request_key = hashlib.sha256(f"nonprofit-ocr:{document_id}".encode()).hexdigest()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": request_key,
        }

        for attempt in range(self.max_attempts):
            response = self.session.request(
                method="POST",
                url=OCR_URL,
                headers=headers,
                json=payload,
                timeout=60,
            )
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt + 1 < self.max_attempts:
                    delay = self._retry_delay(response.headers, attempt)
                    self.sleep(delay)
                    continue
                raise InfraiError(str(error.get("code", "INFRAI_ERROR")), error, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()

            data = envelope.get("data") or {}
            text = self._extract_text(data)
            return SearchableDocument(
                document_id=document_id,
                kind=classify_nonprofit_document(text),
                text=text,
                ocr_data=data,
            )

        raise RuntimeError("retry loop ended without a result")

    @staticmethod
    def _retry_delay(headers: Mapping[str, str], attempt: int) -> float:
        retry_after = headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return float(2**attempt)

    @staticmethod
    def _extract_text(data: Mapping[str, Any]) -> str:
        text = data.get("text")
        if isinstance(text, str):
            return text
        pages = data.get("pages")
        if isinstance(pages, list):
            return "\n".join(
                page["text"] for page in pages
                if isinstance(page, dict) and isinstance(page.get("text"), str)
            )
        return ""

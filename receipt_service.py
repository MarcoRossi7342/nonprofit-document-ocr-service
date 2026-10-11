"""HTTP entry point for the nonprofit scanning workflow."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from nonprofit_ocr import InfraiError, NonprofitOcr


class ScanRequest(BaseModel):
    document_id: str = Field(min_length=1)
    pdf: str = Field(min_length=1)
    lang: str = "eng"
    quality: str = "high"


class ScanResponse(BaseModel):
    document_id: str
    kind: str
    text: str


app = FastAPI(title="Nonprofit document OCR")


@app.post("/documents/ocr", response_model=ScanResponse)
def scan_document(request: ScanRequest) -> ScanResponse:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is required")

    try:
        result = NonprofitOcr(api_key).scan(
            request.document_id,
            request.pdf,
            request.lang,
            request.quality,
        )
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "error": exc.detail},
        ) from exc

    return ScanResponse(document_id=result.document_id, kind=result.kind, text=result.text)

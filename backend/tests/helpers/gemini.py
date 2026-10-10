"""A scripted Gemini `generateContent` endpoint for photo-card extraction tests."""

from __future__ import annotations

import json

import httpx

HEADLINE = "‘ফার্নান্দেজই পর্তুগালের সবচেয়ে বড় প্রতীক’, বললেন রোনালদো — ৩টি গোল!"


def gemini_body(**fields) -> dict:
    payload = {
        "headline": HEADLINE, "headline_status": "PRESENT",
        "source": "prothomalo.com", "source_status": "IDENTIFIED", "source_evidence": "প্রথম আলো logo",
        "date": "০৫ অক্টোবর, ২০২৬", "date_status": "PRESENT",
    }
    payload.update(fields)
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}]}


def quota_429(quota_id: str) -> httpx.Response:
    return httpx.Response(429, json={"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": quota_id, "quotaValue": "20"}]}]}})


DAILY = "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
PER_MINUTE = "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"


class Gemini:
    """Answers each request with the next scripted item (a body dict, an
    httpx.Response or an exception to raise) and records every request."""

    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        item = self.responses.pop(0) if self.responses else httpx.Response(500, text="exhausted")
        if isinstance(item, Exception):
            raise item
        if isinstance(item, httpx.Response):
            return item
        return httpx.Response(200, json=item)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def keys_used(self) -> list[str]:
        return [r.headers["x-goog-api-key"] for r in self.requests]


class Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)

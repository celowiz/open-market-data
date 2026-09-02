from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from marketdata.api.deps import get_db
from marketdata.config import get_settings
from marketdata.storage.repositories import resolve_instrument_id, upsert_event

router = APIRouter()


class NewsHookRequest(BaseModel):
    ticker: str
    source: str = "webhook"
    event_type: str = "news"
    occurred_at: datetime | None = None
    headline: str = Field(min_length=1, max_length=512)
    url: str | None = None
    external_id: str = Field(min_length=1, max_length=256)


class NewsHookResponse(BaseModel):
    status: str
    ticker: str
    external_id: str


def _authorized(authorization: str | None, token_header: str | None) -> bool:
    expected = get_settings().news_hook_token.strip()
    if not expected:
        return False
    if token_header and token_header.strip() == expected:
        return True
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() == expected
    return False


@router.post("/hooks/news", response_model=NewsHookResponse)
def ingest_news_hook(
    body: NewsHookRequest,
    session: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_news_hook_token: str | None = Header(default=None),
) -> NewsHookResponse:
    settings = get_settings()
    if not settings.news_hook_token.strip():
        raise HTTPException(
            status_code=503,
            detail="NEWS_HOOK_TOKEN is not configured",
        )
    if not _authorized(authorization, x_news_hook_token):
        raise HTTPException(status_code=401, detail="unauthorized")
    ticker = body.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=422, detail="ticker is required")
    occurred = body.occurred_at or datetime.now(UTC)
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=UTC)
    action = upsert_event(
        session,
        ticker=ticker,
        instrument_id=resolve_instrument_id(session, ticker),
        source=body.source.strip() or "webhook",
        event_type=body.event_type.strip() or "news",
        occurred_at=occurred,
        headline=body.headline,
        url=body.url,
        external_id=body.external_id,
        extra={"hook": True},
    )
    return NewsHookResponse(status=action, ticker=ticker, external_id=body.external_id)

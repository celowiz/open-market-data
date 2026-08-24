from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RawArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID | str | None = None
    source_name: str
    source_url: str
    retrieved_at: datetime
    sha256: str
    size_bytes: int
    storage_uri: str
    filename: str | None = None
    content_type: str | None = None
    encoding: str | None = None
    http_status: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    reference_date: date | None = None
    ingestion_run_id: UUID | str | None = None

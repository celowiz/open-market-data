from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from marketdata.api.canonical_sources import canonical_source_names
from marketdata.api.deps import get_db
from marketdata.storage.models import SourceRow

router = APIRouter()


class SourceResponse(BaseModel):
    name: str
    display_name: str
    official: bool
    redistribution_policy: str
    ingestion_enabled: bool
    public_api_enabled: bool
    public_dataset_enabled: bool
    data_license: str | None = None


def public_sources_stmt(*, include_test: bool = False) -> Select[tuple[SourceRow]]:
    stmt = select(SourceRow).where(SourceRow.public_api_enabled.is_(True))
    if not include_test:
        stmt = stmt.where(func.lower(SourceRow.name).in_(sorted(canonical_source_names())))
    return stmt.order_by(SourceRow.name)


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(
    include_test: bool = Query(
        default=False,
        description=(
            "Include leftover test source rows. Default lists registered "
            "provider names only (b3, bcb, cvm, tesouro, yahoo)."
        ),
    ),
    session: Session = Depends(get_db),
) -> list[SourceResponse]:
    rows = session.scalars(public_sources_stmt(include_test=include_test)).all()
    return [
        SourceResponse(
            name=row.name,
            display_name=row.display_name,
            official=row.official,
            redistribution_policy=row.redistribution_policy,
            ingestion_enabled=row.ingestion_enabled,
            public_api_enabled=row.public_api_enabled,
            public_dataset_enabled=row.public_dataset_enabled,
            data_license=row.data_license,
        )
        for row in rows
    ]

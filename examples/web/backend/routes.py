from __future__ import annotations

from catalog import build_catalog
from fastapi import APIRouter
from schemas import CatalogResponse

api_router = APIRouter(prefix="/api")


@api_router.get("/catalog", response_model=CatalogResponse)
def get_catalog() -> CatalogResponse:
    return build_catalog()

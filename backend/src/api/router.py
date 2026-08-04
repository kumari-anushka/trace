from fastapi import APIRouter

from src.graph.router import router as graph_router
from src.ingestion.router import router as ingestion_router
from src.repositories.router import router as repositories_router
from src.repository_versions.router import (
    router as repository_versions_router,
)

api_router = APIRouter(
    prefix="/api",
)

api_router.include_router(repositories_router)
api_router.include_router(repository_versions_router)
api_router.include_router(ingestion_router)
api_router.include_router(graph_router)

from fastapi import FastAPI

from src.api.routes.health import router as health_router
from src.api.routes.repositories import router as repositories_router
from src.core.config import settings
from src.core.lifespan import lifespan

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(repositories_router)

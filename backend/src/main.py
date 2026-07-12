from fastapi import FastAPI

from src.api.routes.health import router as health_router
from src.core.config import settings

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.include_router(health_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Trace API"}

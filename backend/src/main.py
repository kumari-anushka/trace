from fastapi import FastAPI

from api.v1.router import router

app = FastAPI(
    title="Trace API",
    version="0.1.0",
    description="Trace any decision back to its evidence",
)

app.include_router(router, prefix="/api/v1")

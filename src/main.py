from fastapi import FastAPI
from src.config.settings import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
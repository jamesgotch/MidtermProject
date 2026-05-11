from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from database import ensure_starting_data, load_incidents 
from colorado_springs.scraper import refresh_data


ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
HOST = "127.0.0.1"
PORT = 8000


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ensure_starting_data()
    yield

app = FastAPI(title="Incident Dashboard", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/incidents")
def get_incidents() -> dict[str, list[dict[str, Any]]]:
    return {"incidents": load_incidents()}


@app.post("/api/update")
def update_incidents() -> dict[str, int | str]:
    try:
        summary = refresh_data()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return {
        "message": "Incident data updated successfully.",
        **summary,
    }


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


def main() -> None:
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
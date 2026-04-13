from __future__ import annotations

from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from database import ensure_starting_data, load_incidents
from scraper import refresh_data


ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
HOST = "127.0.0.1"
PORT = 8000

app = FastAPI(title="Incident Dashboard")


@app.on_event("startup")
def startup() -> None:
    ensure_starting_data()


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
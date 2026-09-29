"""FastAPI server: the prediction API plus the interactive map UI in static/.

Run:   python app.py          then open http://127.0.0.1:8000
API docs are served at        http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from predictor import HousePricePredictor, OutOfCoverageError

STATIC_DIR = Path(__file__).resolve().parent / "static"
OceanProximity = Literal["<1H OCEAN", "INLAND", "ISLAND", "NEAR BAY", "NEAR OCEAN"]


class Adjustments(BaseModel):
    """What-if overrides for the neighbourhood profile estimated from nearby census blocks."""

    median_income: float | None = Field(
        None, ge=0.4999, le=15.0001, description="Median household income, tens of thousands of 1990 USD")
    housing_median_age: float | None = Field(None, ge=1, le=52, description="Median house age (years)")
    rooms_per_household: float | None = Field(None, ge=0.5, le=150)
    bedrooms_per_household: float | None = Field(None, ge=0.1, le=40)
    people_per_household: float | None = Field(None, ge=0.5, le=1300)
    households: float | None = Field(None, ge=1, le=6100, description="Households in the census block")
    ocean_proximity: OceanProximity | None = None


class PredictRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    adjustments: Adjustments | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    predictor = HousePricePredictor.load()
    app.state.predictor = predictor
    app.state.blocks_json = json.dumps(predictor.blocks_payload(), separators=(",", ":"))
    yield


app = FastAPI(title="California House Price Map", version="1.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def revalidate_static_files(request: Request, call_next):
    """Make browsers re-check the UI files so edits show up on a normal reload."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/model-info")
def model_info(request: Request) -> dict:
    return request.app.state.predictor.model_info()


@app.get("/api/blocks")
def blocks(request: Request) -> Response:
    return Response(request.app.state.blocks_json, media_type="application/json")


@app.post("/api/predict")
def predict(body: PredictRequest, request: Request) -> dict:
    adjustments = body.adjustments.model_dump(exclude_none=True) if body.adjustments else None
    try:
        return request.app.state.predictor.predict(body.latitude, body.longitude, adjustments)
    except OutOfCoverageError as err:
        raise HTTPException(status_code=422, detail={"code": err.code, "message": str(err)}) from err


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 8000)))

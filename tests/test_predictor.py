import numpy as np
import pandas as pd
import pytest

import predictor as predictor_module
from predictor import HousePricePredictor, OutOfCoverageError, model_inputs, weighted_median

PALO_ALTO = (37.4419, -122.1430)
FRESNO = (36.7378, -119.7871)


def test_weighted_median_skips_missing_values():
    values = np.array([1.0, 2.0, np.nan, 10.0])
    weights = np.array([1.0, 1.0, 5.0, 3.0])
    assert weighted_median(values, weights) == 10.0


def test_model_inputs_turn_ratios_into_block_totals():
    profile = {
        "median_income": 5.0, "housing_median_age": 30, "rooms_per_household": 5.0,
        "bedrooms_per_household": 1.0, "people_per_household": 3.0, "households": 400,
        "ocean_proximity": "INLAND",
    }
    row = model_inputs(36.0, -119.0, profile)
    assert (row["total_rooms"], row["total_bedrooms"], row["population"]) == (2000, 400, 1200)
    assert (row["latitude"], row["longitude"]) == (36.0, -119.0)


def test_prediction_matches_the_random_forest(predictor):
    result = predictor.predict(*PALO_ALTO)
    X = predictor.pipeline.transform(pd.DataFrame([result["model_inputs"]]))
    assert result["prediction"]["value"] == pytest.approx(predictor.model.predict(X)[0], abs=1)


def test_contributions_add_up_to_the_prediction(predictor):
    result = predictor.predict(*PALO_ALTO)
    breakdown = result["contributions"]
    total = breakdown["base_value"] + sum(item["value"] for item in breakdown["items"])
    assert total == pytest.approx(result["prediction"]["value"], abs=len(breakdown["items"]) + 1)


def test_prediction_details(predictor):
    result = predictor.predict(*PALO_ALTO)
    prediction = result["prediction"]
    assert prediction["low"] <= prediction["value"] <= prediction["high"]
    assert 0 <= prediction["percentile"] <= 100
    assert len(result["neighbors"]) == 8
    assert result["coverage"]["level"] == "high"
    assert result["location"]["nearest_city"]["name"] == "Palo Alto"
    assert result["adjusted"] is False


def test_adjustments_override_the_estimated_profile(predictor):
    base = predictor.predict(*FRESNO)
    richer = predictor.predict(*FRESNO, {"median_income": 9.0})
    assert richer["adjusted"] is True
    assert richer["profile"]["median_income"] == 9.0
    assert richer["estimated_profile"] == base["estimated_profile"]
    assert richer["prediction"]["value"] > base["prediction"]["value"]


@pytest.mark.parametrize("place, lat, lon, code", [
    ("Santa Monica Bay", 33.90, -118.60, "no_data_nearby"),
    ("Pacific off Big Sur", 36.20, -122.10, "no_data_nearby"),
    ("Reno, NV", 39.53, -119.81, "outside_california"),
    ("Tijuana, MX", 32.52, -117.04, "outside_california"),
])
def test_points_without_coverage_are_rejected(predictor, place, lat, lon, code):
    with pytest.raises(OutOfCoverageError) as err:
        predictor.predict(lat, lon)
    assert err.value.code == code, place


def test_missing_model_on_a_read_only_host_fails_with_a_clear_message(monkeypatch):
    monkeypatch.setattr(predictor_module, "_artifacts_usable", lambda: False)
    monkeypatch.setattr(predictor_module.os, "access", lambda path, mode: False)
    with pytest.raises(RuntimeError, match="read-only"):
        HousePricePredictor.load()


def test_census_block_locations_are_always_accepted(predictor):
    locations = predictor.blocks[["latitude", "longitude"]].drop_duplicates().sample(1000, random_state=0)
    for lat, lon in locations.itertuples(index=False):
        predictor.locate(lat, lon)  # raises OutOfCoverageError on failure

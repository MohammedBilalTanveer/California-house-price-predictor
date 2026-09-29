import pytest


def test_index_serves_the_map(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "California House Price Map" in response.text


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_model_info(client):
    info = client.get("/api/model-info").json()
    assert info["model"]["n_estimators"] == 100
    assert info["metrics"]["test_r2"] > 0.75
    histogram = info["dataset"]["value_histogram"]
    assert len(histogram["counts"]) == len(histogram["edges"]) - 1
    assert sum(histogram["counts"]) == info["dataset"]["n_blocks"]
    california = info["california"]
    (south, west), (north, east) = california["bounds"]
    assert south < north and west < east
    assert california["outline"][0] == [42.0, -124.2124]  # [lat, lon] pairs
    assert len(california["region"]) == len(california["outline"]) + 2


def test_blocks_layer(client):
    data = client.get("/api/blocks").json()
    assert data["columns"] == ["latitude", "longitude", "median_house_value"]
    assert len(data["rows"]) == 20_640


def test_predict(client):
    response = client.post("/api/predict", json={"latitude": 34.0736, "longitude": -118.4004})
    assert response.status_code == 200
    body = response.json()
    assert body["location"]["nearest_city"]["name"] == "Beverly Hills"
    assert body["prediction"]["value"] > 300_000


def test_predict_with_adjustments(client):
    payload = {
        "latitude": 36.7378, "longitude": -119.7871,
        "adjustments": {"housing_median_age": 5, "ocean_proximity": "NEAR OCEAN"},
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    assert response.json()["profile"]["ocean_proximity"] == "NEAR OCEAN"
    assert response.json()["adjusted"] is True


def test_predict_outside_california(client):
    response = client.post("/api/predict", json={"latitude": 36.17, "longitude": -115.14})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "outside_california"


@pytest.mark.parametrize("payload", [
    {"latitude": 95, "longitude": -120},
    {"latitude": 37},
    {"latitude": 37.4, "longitude": -122.1, "adjustments": {"median_income": 99}},
    {"latitude": 37.4, "longitude": -122.1, "adjustments": {"ocean_proximity": "MOON"}},
])
def test_predict_validates_input(client, payload):
    assert client.post("/api/predict", json=payload).status_code == 422

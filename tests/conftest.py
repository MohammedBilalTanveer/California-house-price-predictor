import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:  # runs the lifespan, i.e. loads (or trains) the model once
        yield test_client


@pytest.fixture(scope="session")
def predictor(client):
    return client.app.state.predictor

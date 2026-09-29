import numpy as np
import pytest

import geo


@pytest.mark.parametrize("place, lat, lon", [
    ("San Francisco", 37.7749, -122.4194),
    ("Los Angeles", 34.0522, -118.2437),
    ("San Diego", 32.7157, -117.1611),
    ("Crescent City", 41.7558, -124.2026),
    ("Needles", 34.8481, -114.6141),
    ("South Lake Tahoe", 38.9399, -119.9772),
])
def test_california_places_are_inside(place, lat, lon):
    assert geo.in_california(lat, lon), place


@pytest.mark.parametrize("place, lat, lon", [
    ("Reno, NV", 39.53, -119.81),
    ("Las Vegas, NV", 36.17, -115.14),
    ("Tijuana, MX", 32.52, -117.04),
    ("Mexicali, MX", 32.62, -115.45),
    ("Yuma, AZ", 32.69, -114.62),
    ("Medford, OR", 42.33, -122.87),
])
def test_neighbouring_places_are_outside(place, lat, lon):
    assert not geo.in_california(lat, lon), place


@pytest.mark.parametrize("place, lat, lon", [
    ("Santa Catalina Island", 33.39, -118.42),
    ("San Clemente Island", 32.90, -118.50),
])
def test_offshore_islands_are_inside(place, lat, lon):
    assert geo.in_california(lat, lon), place


def test_land_border_runs_coast_to_coast():
    (start_lon, start_lat), (end_lon, end_lat) = geo.CALIFORNIA_LAND_BORDER[0], geo.CALIFORNIA_LAND_BORDER[-1]
    assert (start_lat, round(start_lon)) == (42.0, -124)   # Oregon line meets the Pacific
    assert (round(end_lat, 2), round(end_lon)) == (32.53, -117)  # Mexico line meets the Pacific
    assert geo.CALIFORNIA_BORDER[:len(geo.CALIFORNIA_LAND_BORDER)] == geo.CALIFORNIA_LAND_BORDER


def test_haversine_san_francisco_to_los_angeles():
    assert geo.haversine_km(37.7749, -122.4194, 34.0522, -118.2437) == pytest.approx(559, abs=5)


def test_bearing_gap_tells_inside_from_outside():
    lats = np.array([1.0, 0.0, -1.0, 0.0])  # N, E, S, W of the origin
    lons = np.array([0.0, 1.0, 0.0, -1.0])
    assert geo.max_bearing_gap(0.0, 0.0, lats, lons) == pytest.approx(90, abs=1)
    assert geo.max_bearing_gap(0.0, 5.0, lats, lons) > 180  # every point lies to the west


def test_nearest_city():
    name, distance = geo.nearest_city(37.44, -122.15)
    assert name == "Palo Alto"
    assert distance < 2

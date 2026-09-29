"""Geography helpers: California border test, distances, bearings and nearest city."""
from __future__ import annotations

import numpy as np

EARTH_RADIUS_KM = 6371.0088

# California's land border as (longitude, latitude). The Oregon (42 N), Nevada (120 W, then
# the oblique line from Lake Tahoe to the Colorado River) and Mexico borders are straight
# lines; the Colorado River (Arizona border) is approximated. The Pacific side is drawn far
# offshore on purpose: water is rejected by the data-coverage check in predictor.py.
CALIFORNIA_BORDER = [
    (-125.0, 42.0), (-120.0, 42.0), (-120.0, 39.0), (-114.6333, 35.0017),
    (-114.575, 34.87), (-114.565, 34.80), (-114.49, 34.72), (-114.37, 34.46),
    (-114.14, 34.29), (-114.29, 34.14), (-114.43, 34.03), (-114.50, 33.60),
    (-114.68, 33.35), (-114.70, 33.10), (-114.47, 32.88), (-114.50, 32.74),
    (-114.62, 32.73), (-114.7196, 32.7183), (-117.1238, 32.5343),
    (-117.35, 32.45), (-125.0, 32.45),
]

# Map bounds used by the UI (south-west, north-east corners as [lat, lon]).
CALIFORNIA_BOUNDS = [[32.3, -124.9], [42.2, -113.9]]

# Reference points for "x km from <city>" labels.
CITIES = [
    ("Los Angeles", 34.0522, -118.2437), ("San Diego", 32.7157, -117.1611),
    ("San Jose", 37.3382, -121.8863), ("San Francisco", 37.7749, -122.4194),
    ("Fresno", 36.7378, -119.7871), ("Sacramento", 38.5816, -121.4944),
    ("Long Beach", 33.7701, -118.1937), ("Oakland", 37.8044, -122.2712),
    ("Bakersfield", 35.3733, -119.0187), ("Anaheim", 33.8366, -117.9143),
    ("Santa Ana", 33.7455, -117.8677), ("Riverside", 33.9806, -117.3755),
    ("Stockton", 37.9577, -121.2908), ("Irvine", 33.6846, -117.8265),
    ("Chula Vista", 32.6401, -117.0842), ("Fremont", 37.5485, -121.9886),
    ("San Bernardino", 34.1083, -117.2898), ("Modesto", 37.6391, -120.9969),
    ("Oxnard", 34.1975, -119.1771), ("Fontana", 34.0922, -117.4350),
    ("Huntington Beach", 33.6603, -117.9992), ("Glendale", 34.1425, -118.2551),
    ("Santa Clarita", 34.3917, -118.5426), ("Oceanside", 33.1959, -117.3795),
    ("Santa Rosa", 38.4404, -122.7141), ("Lancaster", 34.6868, -118.1542),
    ("Palmdale", 34.5794, -118.1165), ("Pasadena", 34.1478, -118.1445),
    ("Salinas", 36.6777, -121.6555), ("Berkeley", 37.8715, -122.2730),
    ("Palo Alto", 37.4419, -122.1430), ("Mountain View", 37.3861, -122.0839),
    ("Sunnyvale", 37.3688, -122.0363), ("San Mateo", 37.5630, -122.3255),
    ("Hayward", 37.6688, -122.0808), ("Concord", 37.9780, -122.0311),
    ("Walnut Creek", 37.9101, -122.0652), ("Vallejo", 38.1041, -122.2566),
    ("Napa", 38.2975, -122.2869), ("Santa Monica", 34.0195, -118.4912),
    ("Beverly Hills", 34.0736, -118.4004), ("Malibu", 34.0259, -118.7798),
    ("Torrance", 33.8358, -118.3406), ("Newport Beach", 33.6189, -117.9289),
    ("Temecula", 33.4936, -117.1484), ("Escondido", 33.1192, -117.0864),
    ("Carlsbad", 33.1581, -117.3506), ("La Jolla", 32.8328, -117.2713),
    ("Palm Springs", 33.8303, -116.5453), ("Indio", 33.7206, -116.2156),
    ("Hemet", 33.7475, -116.9720), ("El Centro", 32.7920, -115.5631),
    ("Brawley", 32.9787, -115.5303), ("Calexico", 32.6789, -115.4989),
    ("Barstow", 34.8958, -117.0173), ("Victorville", 34.5362, -117.2928),
    ("Big Bear Lake", 34.2439, -116.9114), ("Twentynine Palms", 34.1356, -116.0542),
    ("Ridgecrest", 35.6225, -117.6709), ("Tehachapi", 35.1322, -118.4490),
    ("Santa Barbara", 34.4208, -119.6982), ("Ventura", 34.2746, -119.2290),
    ("Santa Maria", 34.9530, -120.4357), ("Lompoc", 34.6392, -120.4579),
    ("San Luis Obispo", 35.2828, -120.6596), ("Paso Robles", 35.6266, -120.6910),
    ("Monterey", 36.6002, -121.8947), ("Big Sur", 36.2704, -121.8081),
    ("Santa Cruz", 36.9741, -122.0308), ("Gilroy", 37.0058, -121.5683),
    ("Hollister", 36.8525, -121.4016), ("Merced", 37.3022, -120.4830),
    ("Turlock", 37.4947, -120.8466), ("Visalia", 36.3302, -119.2921),
    ("Hanford", 36.3275, -119.6457), ("Porterville", 36.0652, -119.0168),
    ("Livermore", 37.6819, -121.7680), ("Tracy", 37.7397, -121.4252),
    ("Lodi", 38.1302, -121.2724), ("Davis", 38.5449, -121.7405),
    ("Fairfield", 38.2494, -122.0400), ("Petaluma", 38.2324, -122.6367),
    ("San Rafael", 37.9735, -122.5311), ("Auburn", 38.8966, -121.0769),
    ("Placerville", 38.7296, -120.7985), ("Grass Valley", 39.2191, -121.0611),
    ("Yuba City", 39.1404, -121.6169), ("Oroville", 39.5138, -121.5564),
    ("Chico", 39.7285, -121.8375), ("Red Bluff", 40.1785, -122.2358),
    ("Redding", 40.5865, -122.3917), ("Mount Shasta", 41.3099, -122.3106),
    ("Yreka", 41.7354, -122.6345), ("Susanville", 40.4163, -120.6530),
    ("Eureka", 40.8021, -124.1637), ("Arcata", 40.8665, -124.0828),
    ("Crescent City", 41.7558, -124.2026), ("Ukiah", 39.1502, -123.2078),
    ("Fort Bragg", 39.4457, -123.8053), ("South Lake Tahoe", 38.9399, -119.9772),
    ("Truckee", 39.3280, -120.1833), ("Mammoth Lakes", 37.6485, -118.9721),
    ("Bishop", 37.3635, -118.3951), ("Yosemite Valley", 37.7456, -119.5936),
    ("Needles", 34.8481, -114.6141), ("Blythe", 33.6103, -114.5964),
    ("Avalon", 33.3428, -118.3282),
]
_CITY_NAMES = [c[0] for c in CITIES]
_CITY_LATS = np.array([c[1] for c in CITIES])
_CITY_LONS = np.array([c[2] for c in CITIES])


def point_in_polygon(lon: float, lat: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting test; polygon vertices are (lon, lat)."""
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if (yi > lat) != (yj > lat):
            x_cross = xi + (lat - yi) * (xj - xi) / (yj - yi)
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def in_california(lat: float, lon: float) -> bool:
    return point_in_polygon(lon, lat, CALIFORNIA_BORDER)


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km; works on scalars or numpy arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def max_bearing_gap(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> float:
    """Largest angle (degrees) between consecutive directions from (lat, lon) to the points.

    A gap above 180 means every point lies on one side of (lat, lon), i.e. the location is
    outside the points' convex hull - for example in the ocean just off the coast.
    """
    dx = (np.asarray(lons) - lon) * np.cos(np.radians(lat))
    dy = np.asarray(lats) - lat
    moved = np.hypot(dx, dy) > 1e-9  # points exactly at (lat, lon) have no direction
    if moved.sum() < 2:
        return 360.0
    angles = np.sort(np.degrees(np.arctan2(dy[moved], dx[moved])))
    gaps = np.diff(np.append(angles, angles[0] + 360.0))
    return float(gaps.max())


def nearest_city(lat: float, lon: float) -> tuple[str, float]:
    distances = haversine_km(lat, lon, _CITY_LATS, _CITY_LONS)
    i = int(np.argmin(distances))
    return _CITY_NAMES[i], float(distances[i])

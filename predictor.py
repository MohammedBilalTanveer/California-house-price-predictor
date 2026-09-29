"""Turn a map click into a detailed house price estimate.

A click only gives latitude/longitude, but the model needs nine inputs. The other seven are
estimated from the census blocks nearest to the click (inverse-distance weighted) and fed
through the trained pipeline + random forest. Any of them can be overridden for what-if
analysis.
"""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.neighbors import BallTree

import geo
import train

NEIGHBOURS = 8          # census blocks that describe the clicked neighbourhood
HULL_NEIGHBOURS = 30    # blocks used to tell whether the click sits inside the data footprint
ON_BLOCK_KM = 1.0       # block coordinates are rounded to 0.01 deg, so allow this past a border
NEAR_KM = 2.0           # this close to a block, always accept
EDGE_MAX_KM = 6.0       # outside the local cloud of blocks (e.g. offshore): max distance
INTERIOR_MAX_KM = 30.0  # in the gaps between blocks (sparse rural areas): max distance
MEDIUM_COVERAGE_KM = 8.0
MIN_WEIGHT_KM = 0.5     # distance floor for the inverse-distance weights

# BLS CPI-U, U.S. city average, all items, annual averages (1982-84 = 100).
CPI_1990, CPI_2024 = 130.7, 313.689

CONTRIBUTION_LABELS = {
    "median_income": "Median income",
    "location": "Location (lat/long)",
    "ocean_proximity": "Ocean proximity",
    "housing_median_age": "House age",
    "total_rooms": "Rooms",
    "total_bedrooms": "Bedrooms",
    "population": "Population",
    "households": "Households",
}
PROFILE_DECIMALS = {
    "median_income": 4, "housing_median_age": 1, "rooms_per_household": 2,
    "bedrooms_per_household": 2, "people_per_household": 2, "households": 0,
}


class OutOfCoverageError(ValueError):
    """The point is outside California or too far from census data to estimate."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.average(values, weights=weights))


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    known = ~np.isnan(values)
    if not known.any():
        return float("nan")
    order = np.argsort(values[known])
    v, w = values[known][order], weights[known][order]
    cumulative = np.cumsum(w)
    return float(v[np.searchsorted(cumulative, cumulative[-1] / 2)])


def weighted_mode(labels: np.ndarray, weights: np.ndarray) -> str:
    return str(pd.Series(weights).groupby(labels).sum().idxmax())


def round_profile(profile: dict) -> dict:
    return {k: round(float(v), PROFILE_DECIMALS[k]) if k in PROFILE_DECIMALS else v
            for k, v in profile.items()}


def model_inputs(lat: float, lon: float, profile: dict) -> dict:
    """Convert a per-household neighbourhood profile into the model's raw census columns."""
    households = profile["households"]
    return {
        "longitude": lon,
        "latitude": lat,
        "housing_median_age": profile["housing_median_age"],
        "total_rooms": profile["rooms_per_household"] * households,
        "total_bedrooms": profile["bedrooms_per_household"] * households,
        "population": profile["people_per_household"] * households,
        "households": households,
        "median_income": profile["median_income"],
        "ocean_proximity": profile["ocean_proximity"],
    }


def _artifacts_usable() -> bool:
    files = (train.MODEL_FILE, train.PIPELINE_FILE, train.METADATA_FILE)
    if not all(f.exists() for f in files):
        return False
    metadata = json.loads(train.METADATA_FILE.read_text(encoding="utf-8"))
    return metadata.get("sklearn_version") == sklearn.__version__  # pickles are version-specific


class HousePricePredictor:
    def __init__(self, model, pipeline, metadata: dict, housing: pd.DataFrame):
        self.model = model
        self.pipeline = pipeline
        self.metadata = metadata
        self.blocks = train.add_household_ratios(housing).reset_index(drop=True)
        self._coords = self.blocks[["latitude", "longitude"]].to_numpy()
        self._tree = BallTree(np.radians(self._coords), metric="haversine")
        self._sorted_values = np.sort(self.blocks[train.TARGET].to_numpy())
        self._column_groups = self._group_transformed_columns()
        self._fallback = {k: r["median"] for k, r in metadata["dataset"]["profile_ranges"].items()}

    @classmethod
    def load(cls, retrain_if_needed: bool = True) -> HousePricePredictor:
        if retrain_if_needed and not _artifacts_usable():
            print("No usable trained model found - training one now (about a minute)...")
            train.train_and_save()
        metadata = json.loads(train.METADATA_FILE.read_text(encoding="utf-8"))
        return cls(joblib.load(train.MODEL_FILE), joblib.load(train.PIPELINE_FILE),
                   metadata, train.load_housing())

    def _group_transformed_columns(self) -> np.ndarray:
        """CONTRIBUTION_LABELS key for each column the pipeline outputs."""
        groups = []
        for name in self.pipeline.get_feature_names_out():
            feature = name.split("__", 1)[1]
            if feature in ("longitude", "latitude"):
                groups.append("location")
            elif feature.startswith("ocean_proximity"):
                groups.append("ocean_proximity")
            else:
                groups.append(feature)
        return np.array(groups)

    def locate(self, lat: float, lon: float) -> tuple[np.ndarray, np.ndarray]:
        """Distances (km) and row indices of the nearest blocks; raises if we can't predict here."""
        dist, idx = self._tree.query(np.radians([[lat, lon]]), k=HULL_NEIGHBOURS)
        dist_km, idx = dist[0] * geo.EARTH_RADIUS_KM, idx[0]
        nearest = dist_km[0]
        if not geo.in_california(lat, lon) and nearest > ON_BLOCK_KM:
            raise OutOfCoverageError(
                "outside_california",
                "That point is outside California. The model was trained only on California census data.",
            )
        if nearest > NEAR_KM:
            outside_data = geo.max_bearing_gap(lat, lon, self._coords[idx, 0], self._coords[idx, 1]) > 180
            if (outside_data and nearest > EDGE_MAX_KM) or nearest > INTERIOR_MAX_KM:
                raise OutOfCoverageError(
                    "no_data_nearby",
                    f"No census data near this point: the closest block is {nearest:.0f} km away. "
                    "It is probably in the ocean or an unpopulated area. Try clicking closer to a town.",
                )
        return dist_km[:NEIGHBOURS], idx[:NEIGHBOURS]

    def estimate_profile(self, dist_km: np.ndarray, idx: np.ndarray) -> dict:
        nearby = self.blocks.iloc[idx]
        weights = 1.0 / np.maximum(dist_km, MIN_WEIGHT_KM) ** 2
        profile = {
            "median_income": weighted_mean(nearby["median_income"].to_numpy(), weights),
            "housing_median_age": weighted_mean(nearby["housing_median_age"].to_numpy(), weights),
        }
        # Heavy-tailed columns (dorms, prisons, resort towns): a weighted median resists outliers.
        for col in (*train.RATIO_FEATURES, "households"):
            value = weighted_median(nearby[col].to_numpy(dtype=float), weights)
            profile[col] = value if np.isfinite(value) else self._fallback[col]
        profile["ocean_proximity"] = weighted_mode(nearby["ocean_proximity"].to_numpy(), weights)
        return round_profile(profile)

    def explain(self, inputs: dict) -> tuple[np.ndarray, float, np.ndarray]:
        """Per-tree predictions plus a per-feature breakdown of the forest's prediction.

        Walking each tree from root to leaf, the change in node value at every split is
        credited to the feature split on, so prediction == base value + sum(contributions).
        """
        X = self.pipeline.transform(pd.DataFrame([inputs]))
        n_trees = len(self.model.estimators_)
        tree_preds = np.empty(n_trees)
        base = 0.0
        contributions = np.zeros(X.shape[1])
        for i, estimator in enumerate(self.model.estimators_):
            node_values = estimator.tree_.value[:, 0, 0]
            path = estimator.decision_path(X).indices  # node ids, root -> leaf
            tree_preds[i] = node_values[path[-1]]
            base += node_values[path[0]]
            np.add.at(contributions, estimator.tree_.feature[path[:-1]], np.diff(node_values[path]))
        return tree_preds, base / n_trees, contributions / n_trees

    def predict(self, lat: float, lon: float, adjustments: dict | None = None) -> dict:
        dist_km, idx = self.locate(lat, lon)
        estimated = self.estimate_profile(dist_km, idx)
        profile = {**estimated, **round_profile(adjustments or {})}
        inputs = model_inputs(lat, lon, profile)
        tree_preds, base, contributions = self.explain(inputs)

        value = float(tree_preds.mean())
        low, high = np.percentile(tree_preds, [10, 90])
        nearby = self.blocks.iloc[idx]
        weights = 1.0 / np.maximum(dist_km, MIN_WEIGHT_KM) ** 2
        city, city_km = geo.nearest_city(lat, lon)
        nearest_km = float(dist_km[0])
        dataset = self.metadata["dataset"]

        grouped = {key: float(contributions[self._column_groups == key].sum()) for key in CONTRIBUTION_LABELS}
        items = sorted(
            ({"key": k, "label": CONTRIBUTION_LABELS[k], "value": round(v)} for k, v in grouped.items()),
            key=lambda item: abs(item["value"]), reverse=True,
        )

        return {
            "location": {
                "latitude": lat,
                "longitude": lon,
                "nearest_city": {"name": city, "distance_km": round(city_km, 1)},
            },
            "coverage": {
                "nearest_block_km": round(nearest_km, 2),
                "level": ("high" if nearest_km <= NEAR_KM
                          else "medium" if nearest_km <= MEDIUM_COVERAGE_KM else "low"),
            },
            "prediction": {
                "value": round(value),
                "low": round(float(low)),
                "high": round(float(high)),
                "percentile": round(100 * np.searchsorted(self._sorted_values, value) / len(self._sorted_values), 1),
                "near_cap": bool(high >= 0.98 * train.VALUE_CAP),
                "value_2024_dollars": round(value * CPI_2024 / CPI_1990, -2),
            },
            "comparison": {
                "california_median": dataset["median_value"],
                "nearby_actual": round(weighted_mean(nearby[train.TARGET].to_numpy(), weights)),
            },
            "profile": profile,
            "estimated_profile": estimated,
            "adjusted": profile != estimated,
            "model_inputs": {k: round(v, 4) if isinstance(v, float) else v for k, v in inputs.items()},
            "contributions": {"base_value": round(base), "items": items},
            "neighbors": [
                {
                    "latitude": float(row.latitude),
                    "longitude": float(row.longitude),
                    "distance_km": round(float(d), 2),
                    "median_house_value": int(row.median_house_value),
                    "median_income": float(row.median_income),
                    "housing_median_age": float(row.housing_median_age),
                    "households": int(row.households),
                    "ocean_proximity": row.ocean_proximity,
                }
                for d, row in zip(dist_km, nearby.itertuples(index=False))
            ],
        }

    def model_info(self) -> dict:
        return {
            **self.metadata,
            "ocean_categories": train.OCEAN_CATEGORIES,
            "california": {  # [lat, lon] pairs for the map
                "bounds": geo.CALIFORNIA_BOUNDS,
                "outline": [[lat, lon] for lon, lat in geo.CALIFORNIA_LAND_BORDER],
                "region": [[lat, lon] for lon, lat in geo.CALIFORNIA_BORDER],
            },
            "cpi_factor": CPI_2024 / CPI_1990,
        }

    def blocks_payload(self) -> dict:
        """Every census block as [lat, lon, actual median value] for the map's data layer."""
        rows = [[float(lat), float(lon), int(v)] for lat, lon, v in
                self.blocks[["latitude", "longitude", train.TARGET]].itertuples(index=False)]
        return {"columns": ["latitude", "longitude", "median_house_value"], "rows": rows}

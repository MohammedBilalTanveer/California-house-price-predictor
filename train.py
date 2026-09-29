"""Train the California house price model and save it to model/.

Same recipe as house_price_predictor.ipynb:
  * stratified 80/20 split on income category (random_state=42)
  * median imputation + standard scaling for numeric columns, one-hot for ocean_proximity
  * RandomForestRegressor(random_state=42)

It also scores the model on the held-out test set and writes those metrics, plus a few
dataset statistics the web UI needs, to model/metadata.json.

Usage:  python train.py
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "housing.csv"
MODEL_DIR = BASE_DIR / "model"
MODEL_FILE = MODEL_DIR / "model.pkl"
PIPELINE_FILE = MODEL_DIR / "pipeline.pkl"
METADATA_FILE = MODEL_DIR / "metadata.json"

TARGET = "median_house_value"
NUM_ATTRIBS = [
    "longitude", "latitude", "housing_median_age", "total_rooms",
    "total_bedrooms", "population", "households", "median_income",
]
CAT_ATTRIBS = ["ocean_proximity"]
OCEAN_CATEGORIES = ["<1H OCEAN", "INLAND", "ISLAND", "NEAR BAY", "NEAR OCEAN"]
VALUE_CAP = 500_001  # the 1990 census data tops out median_house_value at this value

# Per-household versions of the block totals: what the UI shows and lets users adjust.
RATIO_FEATURES = {
    "rooms_per_household": "total_rooms",
    "bedrooms_per_household": "total_bedrooms",
    "people_per_household": "population",
}
PROFILE_NUMERIC = ["median_income", "housing_median_age", *RATIO_FEATURES, "households"]


def load_housing(path: Path = DATA_FILE) -> pd.DataFrame:
    return pd.read_csv(path)


def add_household_ratios(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for ratio, total in RATIO_FEATURES.items():
        out[ratio] = df[total] / df["households"]
    return out


def split_train_test(housing: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    income_cat = pd.cut(
        housing["median_income"],
        bins=[0.0, 1.5, 3.0, 4.5, 6.0, np.inf],
        labels=[1, 2, 3, 4, 5],
    )
    split = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(split.split(housing, income_cat))
    return housing.iloc[train_idx], housing.iloc[test_idx]


def build_pipeline(num_attribs: list[str], cat_attribs: list[str]) -> ColumnTransformer:
    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    cat_pipeline = Pipeline([
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    return ColumnTransformer([
        ("num", num_pipeline, num_attribs),
        ("cat", cat_pipeline, cat_attribs),
    ])


def dataset_stats(housing: pd.DataFrame) -> dict:
    values = housing[TARGET]
    edges = [*range(0, 500_000, 20_000), VALUE_CAP]
    counts, _ = np.histogram(values, bins=edges)
    profile = add_household_ratios(housing)
    ranges = {}
    for col in PROFILE_NUMERIC:
        s = profile[col].dropna()
        ranges[col] = {
            "min": float(s.min()),
            "p1": float(s.quantile(0.01)),
            "median": float(s.median()),
            "p99": float(s.quantile(0.99)),
            "max": float(s.max()),
        }
    return {
        "n_blocks": int(len(housing)),
        "median_value": float(values.median()),
        "mean_value": float(values.mean()),
        "value_cap": VALUE_CAP,
        "value_histogram": {"edges": edges, "counts": counts.tolist()},
        "profile_ranges": ranges,
    }


def train_and_save(verbose: bool = True) -> dict:
    start = time.perf_counter()
    housing = load_housing()
    train_set, test_set = split_train_test(housing)
    X_train, y_train = train_set.drop(columns=TARGET), train_set[TARGET]
    X_test, y_test = test_set.drop(columns=TARGET), test_set[TARGET]

    pipeline = build_pipeline(NUM_ATTRIBS, CAT_ATTRIBS)
    model = RandomForestRegressor(random_state=42, n_jobs=-1)
    model.fit(pipeline.fit_transform(X_train), y_train)

    test_pred = model.predict(pipeline.transform(X_test))
    metrics = {
        "test_rmse": float(np.sqrt(mean_squared_error(y_test, test_pred))),
        "test_mae": float(mean_absolute_error(y_test, test_pred)),
        "test_r2": float(r2_score(y_test, test_pred)),
        "n_train": int(len(train_set)),
        "n_test": int(len(test_set)),
    }
    metadata = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "model": {"type": "RandomForestRegressor", "n_estimators": model.n_estimators, "random_state": 42},
        "metrics": metrics,
        "dataset": dataset_stats(housing),
    }

    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_FILE, compress=3)
    joblib.dump(pipeline, PIPELINE_FILE)
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    if verbose:
        print(f"Trained on {metrics['n_train']:,} blocks in {time.perf_counter() - start:.0f}s")
        print(f"Test RMSE ${metrics['test_rmse']:,.0f} | MAE ${metrics['test_mae']:,.0f} | R2 {metrics['test_r2']:.3f}")
        print(f"Saved {MODEL_FILE.relative_to(BASE_DIR)}, {PIPELINE_FILE.relative_to(BASE_DIR)}, "
              f"{METADATA_FILE.relative_to(BASE_DIR)}")
    return metadata


if __name__ == "__main__":
    train_and_save()

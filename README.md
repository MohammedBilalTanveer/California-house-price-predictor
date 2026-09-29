# California House Price Map

Click anywhere on a map of California and get a random-forest estimate of the median house
value there, explained in detail: a prediction range, where the value sits among all
20,640 census blocks, what pushes the price up or down, and "what if?" sliders to change
the neighbourhood and watch the estimate respond.

It puts an interactive UI on the model from
[House-Price-Prediction](https://github.com/MohammedBilalTanveer/House-Price-Prediction)
(`house_price_predictor.ipynb`): same data, same stratified split, same preprocessing
pipeline and the same `RandomForestRegressor(random_state=42)`.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:8000>. The first start trains the model (15 seconds to a minute,
depending on your CPU) and saves it to `model/`; later starts load it in a few seconds.
Interactive API docs are at <http://127.0.0.1:8000/docs>. The virtual environment keeps the
pinned package versions away from your other Python projects.

## How a click becomes a price

The model needs nine inputs, but a click only gives two (latitude and longitude). The
other seven are estimated from the census blocks around the click:

1. **Is there data here?** Points outside California's borders are rejected, and so are
   points too far from any census block to estimate, such as the ocean or empty desert.
   A point outside the local cluster of blocks (offshore, for example) must be within
   6 km of one; a point between blocks, in sparse rural areas, within 30 km.
2. **Estimate the neighbourhood** from the 8 nearest blocks, weighted by inverse distance
   squared. That covers income, house age, rooms, bedrooms and people per household,
   block size, and ocean proximity (by weighted vote). A weighted median is used for the
   heavy-tailed columns, so a dorm or resort block nearby doesn't skew the estimate.
3. **Predict** by running that row through the saved pipeline and the 100-tree forest.
4. **Explain** the result:
   - The spread of the individual trees' predictions gives the 80% range.
   - The forest's prediction is split into per-feature contributions by walking every
     tree's decision path. Each split's change in value is credited to the feature it
     splits on, so *average block + contributions = estimate*, exactly.

## Features

- A map locked to California: it can't be dragged or zoomed out past the state, and
  everything outside the state line is masked.
- Satellite view with place names for first-time visitors. Light, dark and street maps are
  one click away, and the browser remembers the choice.
- All 20,640 census blocks as dots, coloured by their actual 1990 median value.
- Estimated value with the trees' 80% range, a CPI inflation-adjusted figure, and a warning
  when the estimate is near the dataset's $500,001 cap.
- Comparison with the actual values of nearby blocks and the California median, plus a
  statewide percentile.
- Histogram of every block's value, marking this estimate and its range (also available
  as a table).
- "What drives this estimate" breakdown per feature.
- What-if sliders for income, house age, rooms, bedrooms, people per household, block
  size and ocean proximity.
- The 8 nearest census blocks, linked to the map (hover or tap a row to find the block).
- Shareable links: the selected spot is kept in the URL, e.g. `/#37.44190,-122.14300`.
- Responsive layout:
  - **Desktops and laptops:** the map and details sit side by side.
  - **Phones and tablets:** the details sit below the map, with a "See details" button.
  - **Phones held sideways:** side by side again.
- Light and dark page themes.

## Project layout

```
app.py            FastAPI server: JSON API + serves the UI in static/
predictor.py      click -> coverage check, neighbourhood estimate, prediction, breakdown
geo.py            California border polygon, distances, nearest-city labels
train.py          trains + evaluates the model (notebook recipe), writes model/
static/           index.html, styles.css, app.js (Leaflet map, no build step)
tests/            pytest suite for geo, predictor and API
data/housing.csv  1990 California census data (20,640 block groups)
Dockerfile        container image for hosting (trains the model at build time)
```

## API

| Method | Path | Returns |
| --- | --- | --- |
| `POST` | `/api/predict` | Full details for a point: prediction, range, percentile, breakdown, neighbourhood profile, nearest blocks |
| `GET` | `/api/model-info` | Test metrics, dataset stats, histogram, slider ranges, California border |
| `GET` | `/api/blocks` | Every census block as `[lat, lon, value]` for the map layer |

```bash
curl -X POST http://127.0.0.1:8000/api/predict -H "Content-Type: application/json" -d "{\"latitude\": 37.4419, \"longitude\": -122.143, \"adjustments\": {\"median_income\": 9.0}}"
```

`adjustments` is optional. It overrides any of `median_income` (in tens of thousands of
dollars), `housing_median_age`, `rooms_per_household`, `bedrooms_per_household`,
`people_per_household`, `households` and `ocean_proximity`. Points without coverage return
`422` with `{"detail": {"code": "outside_california" | "no_data_nearby", "message": ...}}`.

## Model

On the 4,128-block held-out test set the forest scores **RMSE $47,198, MAE $30,929,
R² 0.83** (the notebook's 10-fold cross-validation gave an RMSE of about $49k). Retrain with
`python train.py`. The pickle is tied to your scikit-learn version, so the app retrains
automatically after an upgrade.

## Caveats

- The data is from the **1990 census**, so prices are 1990 values, and the dataset caps them
  at $500,001. The "2024 dollars" figure adjusts only for inflation (CPI-U 1990 to 2024,
  ×2.40); it is not a current market price.
- The neighbourhood is *estimated* from nearby blocks. Use the sliders to test other
  assumptions.

## Deploy for free

The repo ships a `Dockerfile`, so any host that builds containers can run it. The model is
trained while the image builds, so the server starts in seconds.

### Render (recommended)

Free, and it deploys straight from this GitHub repo.

1. Sign in at <https://render.com> with GitHub, choose **New > Web Service** and pick this
   repository.
2. Set **Language** to **Docker** (Render usually picks it because of the `Dockerfile`),
   keep the `main` branch, choose the region closest to you, and pick the **Free** instance
   type.
3. Under **Advanced**, set **Health Check Path** to `/api/health`, then create the service.
   The first build takes about 5 to 10 minutes, and every later push to `main` redeploys it.

The app then runs at `https://YOUR-SERVICE-NAME.onrender.com`. Free Render services have
512 MB of memory, and this app uses about 300 MB. They sleep after 15 minutes without
traffic, and waking up plus loading the model on their small CPU share means the first visit
after a break takes a minute or two. Each workspace gets 750 free hours a month, enough for
one app running all month.

### Other hosts

- **Hugging Face Spaces:** Docker Spaces need a paid plan (as of September 2026), and the
  free ZeroGPU hardware only runs Gradio apps. With a paid plan, the Dockerfile works as-is:
  add a settings block with `sdk: docker` and `app_port: 7860` to the top of this README and
  push the repo to a Docker Space.
- **Vercel and Netlify:** they run code as short-lived serverless functions (Netlify has no
  Python server at all) on a read-only disk. This app needs its model loaded in a
  long-running server, and on Vercel it fails with `500 FUNCTION_INVOCATION_FAILED`.

### Run the container yourself

```bash
docker build -t house-price-map .
docker run -p 7860:7860 house-price-map
```

Then open <http://127.0.0.1:7860>.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Credits

California housing dataset (1990 U.S. Census; Pace & Barry, 1997), as popularised by
Aurélien Géron's *Hands-On Machine Learning*. Map tiles from Esri and OpenStreetMap
contributors, rendered with [Leaflet](https://leafletjs.com).
# California-house-price-predictor

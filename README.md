---
title: California House Price Map
emoji: 🏠
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
short_description: Click the map to predict a California house price
pinned: false
---

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
Dockerfile.vercel the same image for Vercel, which serves on port 80
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

### Hugging Face Spaces (recommended)

Free, no credit card, and 2 CPUs with 16 GB of RAM, which is plenty for the random forest.

1. Create a Space at <https://huggingface.co/new-space>: pick a name, choose **Docker** and
   then **Blank**, keep the free **CPU basic** hardware, and create it.
2. Push this repo to the Space. When git asks for a password, paste a Hugging Face
   [access token](https://huggingface.co/settings/tokens) with **write** permission.

   ```bash
   git remote add space https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE
   git push --force space main
   ```

   `--force` replaces the placeholder files the Space starts with. The settings block at the
   top of this README (`sdk: docker`, `app_port: 7860`) tells the Space how to run the app.
3. The first build takes a few minutes. The app then runs at
   `https://YOUR_USERNAME-YOUR_SPACE.hf.space`. Push again whenever you change the code.

A free Space goes to sleep after 48 hours without visitors and wakes on the next visit.

### Render (deploys straight from GitHub)

1. Sign in at <https://render.com> with GitHub, choose **New > Web Service** and pick this
   repository. Render finds the `Dockerfile` on its own.
2. Choose the **Free** instance type, set **Health Check Path** to `/api/health`, and create
   the service. Every push to `main` then redeploys it.

Free Render services have 512 MB of memory, and this app uses about 300 MB. They sleep after
15 minutes without traffic, so the first visit after a break takes about a minute, and their
small CPU share makes each estimate slower than on Hugging Face.

### Vercel (container deploy)

Vercel's regular Python functions can't run this app, and a deploy fails with
`500 FUNCTION_INVOCATION_FAILED`: the trained model isn't in the repo, so the app tries to
train one, and their disk is read-only. Vercel can instead run the app as a container from
`Dockerfile.vercel`:

1. Push the repo with `Dockerfile.vercel` in it. A Vercel project connected to the repo picks
   the file up on its next deploy, builds the image (training the model) and runs it.
2. If the deploy fails on size, add the environment variable `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`
   in the project settings and redeploy. The image holds about 490 MB, near Vercel's 500 MB
   standard function limit.

Vercel stops the container after 5 minutes without traffic, so the next visitor waits
while it starts and loads the model. Container support is new, and Vercel's docs don't say
whether the free Hobby plan includes it. If Vercel asks you to upgrade, use Hugging Face.

Netlify can't run a Python server, so it doesn't work for this app.

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

/* California House Price Map - front end for the FastAPI backend in app.py. */

// ---------------------------------------------------------------- formatting

const MINUS = "−";
const fmtInt = new Intl.NumberFormat("en-US");
const fmtUsd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const money = (v) => fmtUsd.format(v);

function compactMoney(v) {
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e5) return `$${Math.round(v / 1e3)}k`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(1).replace(/\.0$/, "")}k`;
  return `$${Math.round(v)}`;
}
const signedMoney = (v) => `${v < 0 ? MINUS : "+"}${compactMoney(Math.abs(v))}`;
const km = (d) => (d < 10 ? `${d.toFixed(1)} km` : `${Math.round(d)} km`);
const coords = (lat, lon) =>
  `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(4)}° ${lon >= 0 ? "E" : "W"}`;

function ordinal(n) {
  const suffix = ["th", "st", "nd", "rd"];
  const mod = n % 100;
  return n + (suffix[(mod - 20) % 10] || suffix[mod] || suffix[0]);
}

// ---------------------------------------------------------------- constants

const PRESETS = [
  ["Palo Alto", 37.4419, -122.143],
  ["Beverly Hills", 34.0736, -118.4004],
  ["San Diego", 32.7157, -117.1611],
  ["Fresno", 36.7378, -119.7871],
  ["Lake Tahoe", 38.9399, -119.9772],
  ["Bakersfield", 35.3733, -119.0187],
];

const OCEAN_LABELS = {
  "<1H OCEAN": "Under an hour from the ocean",
  INLAND: "Inland",
  ISLAND: "Island",
  "NEAR BAY": "Near a bay",
  "NEAR OCEAN": "Near the ocean",
};

const COVERAGE = {
  high: { label: "High data coverage", note: "Plenty of census blocks around this point." },
  medium: { label: "Medium data coverage", note: "The closest census blocks are a few km away." },
  low: { label: "Low data coverage", note: "Few census blocks nearby, so treat this estimate with caution." },
};

// What-if sliders, in the API's units (income is in tens of thousands of dollars).
// `wide` sliders span the dataset's full range; the rest its 1st-99th percentile.
const PROFILE_FIELDS = [
  { key: "median_income", label: "Median household income", step: 0.1, wide: true, format: (v) => compactMoney(v * 1e4) },
  { key: "housing_median_age", label: "Median house age", step: 1, wide: true, format: (v) => `${Math.round(v)} years` },
  { key: "rooms_per_household", label: "Rooms per household", step: 0.1, format: (v) => v.toFixed(1) },
  { key: "bedrooms_per_household", label: "Bedrooms per household", step: 0.05, format: (v) => v.toFixed(2) },
  { key: "people_per_household", label: "People per household", step: 0.1, format: (v) => v.toFixed(1) },
  { key: "households", label: "Households in the block", step: 10, format: (v) => fmtInt.format(Math.round(v)) },
];

// What each contribution bar's input was, shown under its label.
const DRIVER_INPUT = {
  median_income: (i) => `${compactMoney(i.median_income * 1e4)} a year`,
  location: (i) => `${i.latitude.toFixed(2)}, ${i.longitude.toFixed(2)}`,
  ocean_proximity: (i) => OCEAN_LABELS[i.ocean_proximity],
  housing_median_age: (i) => `${Math.round(i.housing_median_age)} years`,
  total_rooms: (i) => `${fmtInt.format(Math.round(i.total_rooms))} in the block`,
  total_bedrooms: (i) => `${fmtInt.format(Math.round(i.total_bedrooms))} in the block`,
  population: (i) => `${fmtInt.format(Math.round(i.population))} people`,
  households: (i) => `${fmtInt.format(Math.round(i.households))} in the block`,
};

// Sequential ramp for house value: one hue, light -> dark. Dark mode flips the anchor.
const RAMP = {
  light: ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"],
  dark: ["#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#6da7ec", "#86b6ef", "#9ec5f4", "#b7d3f6", "#cde2fb"],
};
const VALUE_MAX = 500_001;

// ---------------------------------------------------------------- DOM helpers

/** Create an element. String children become text nodes, never parsed HTML. */
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  el.append(...children.flat(Infinity).filter((c) => c != null && c !== false));
  return el;
}

const SVG_NS = "http://www.w3.org/2000/svg";
function s(tag, attrs = {}, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) if (value != null) el.setAttribute(key, value);
  el.append(...children.flat(Infinity).filter((c) => c != null && c !== false));
  return el;
}

/** Replace an element's children, skipping null/false so `cond && node` works. */
function fill(el, ...children) {
  el.replaceChildren(...children.flat(Infinity).filter((c) => c != null && c !== false));
  return el;
}

const $ = (id) => document.getElementById(id);
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const lineIcon = (size, ...shapes) =>
  s("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
    "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" }, shapes);
const icons = {
  pin: () => lineIcon(16, s("path", { d: "M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z" }),
    s("circle", { cx: 12, cy: 9.5, r: 2.5 })),
  info: () => lineIcon(18, s("circle", { cx: 12, cy: 12, r: 9 }), s("path", { d: "M12 11v5M12 8h.01" })),
};

// ---------------------------------------------------------------- color

const darkQuery = matchMedia("(prefers-color-scheme: dark)");
const theme = () => (darkQuery.matches ? "dark" : "light");

function valueScale() {
  const stops = RAMP[theme()].map((hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)));
  return (value) => {
    const t = Math.min(1, Math.max(0, value / VALUE_MAX)) * (stops.length - 1);
    const i = Math.min(stops.length - 2, Math.floor(t));
    const [r, g, b] = stops[i].map((c, k) => Math.round(c + (stops[i + 1][k] - c) * (t - i)));
    return `rgb(${r}, ${g}, ${b})`;
  };
}

// ---------------------------------------------------------------- API + state

async function api(path, options) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    const message = typeof detail === "string" ? detail
      : detail?.message ?? (Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : `Request failed (${res.status})`);
    throw Object.assign(new Error(message), { code: detail?.code });
  }
  return body;
}

const state = {
  info: null,       // /api/model-info
  blocks: [],       // [lat, lon, value] for every census block
  point: null,      // { lat, lon } currently selected
  estimate: null,   // prediction for the estimated neighbourhood at `point`
  result: null,     // what is on screen: `estimate` or a what-if variant of it
  adjustments: {},  // what-if overrides the user has touched
  controller: null, // aborts a superseded request
};

// ---------------------------------------------------------------- map

let map, blocksLayer, selectionLayer, neighborsLayer, baseLayers, currentBase, pinMarker;
let userPickedBase = false; // once the user picks a basemap, theme changes leave it alone
let switchingBase = false;
let neighborMarkers = [];
const NEIGHBOR_MIN_ZOOM = 10; // below this the 8 neighbours sit on top of the pin
const blockRenderer = L.canvas({ padding: 0.3, pane: "blocks" });

const defaultBase = () => baseLayers[theme() === "dark" ? "Dark" : "Light"];
const blockRadius = () => Math.min(6, Math.max(1.5, map.getZoom() * 0.55 - 1.5));

function initMap(bounds) {
  map = L.map("map", {
    zoomControl: false,
    minZoom: 5,
    maxZoom: 18,
    maxBounds: L.latLngBounds(bounds).pad(0.35),
    maxBoundsViscosity: 0.9,
  });
  // Set the view first: Leaflet defers adding layers until the map has one, which would
  // otherwise make the initial basemap look like a user pick to the layers control.
  map.fitBounds(bounds);
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
  L.control.zoom({ position: "topright" }).addTo(map);
  // Census dots get their own pane so they can fade back behind a selection;
  // place names sit above them so they stay readable.
  map.createPane("blocks").style.zIndex = 390;
  map.createPane("labels");
  map.getPane("labels").style.zIndex = 450;
  map.getPane("labels").style.pointerEvents = "none";

  // Free, key-less tile services (Esri canvas basemaps, OpenStreetMap).
  const esri = (service, options = {}) => L.tileLayer(
    `https://server.arcgisonline.com/ArcGIS/rest/services/${service}/MapServer/tile/{z}/{y}/{x}`,
    { maxZoom: 18, maxNativeZoom: 16, ...options },
  );
  const canvasAttribution = "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors";
  const canvas = (tone) => L.layerGroup([
    esri(`Canvas/World_${tone}_Gray_Base`, { attribution: canvasAttribution }),
    esri(`Canvas/World_${tone}_Gray_Reference`, { pane: "labels" }),
  ]);
  baseLayers = {
    Light: canvas("Light"),
    Dark: canvas("Dark"),
    Streets: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }),
    Satellite: esri("World_Imagery", {
      maxNativeZoom: 18, attribution: "Imagery &copy; Esri, Maxar, Earthstar Geographics",
    }),
  };
  currentBase = defaultBase().addTo(map);

  blocksLayer = L.layerGroup().addTo(map);
  neighborsLayer = L.layerGroup();
  selectionLayer = L.layerGroup().addTo(map);
  L.control.layers(baseLayers, { "Census blocks (actual 1990 values)": blocksLayer }, { position: "topright" })
    .addTo(map);

  // Leaflet fires this for programmatic switches too, hence the switchingBase guard.
  map.on("baselayerchange", (e) => {
    currentBase = e.layer;
    if (!switchingBase) userPickedBase = true;
  });
  map.on("overlayadd overlayremove", (e) => {
    if (e.layer === blocksLayer) $("legend").hidden = e.type === "overlayremove";
  });
  map.on("zoomend", () => {
    const radius = blockRadius();
    blocksLayer.eachLayer((layer) => layer.setRadius(radius));
    syncNeighborVisibility();
  });
  map.on("click", (e) => selectPoint(e.latlng.lat, e.latlng.lng));
}

/** Match the default basemap to the light/dark theme, unless the user picked one. */
function syncBaseToTheme() {
  const wanted = defaultBase();
  if (userPickedBase || wanted === currentBase) return;
  switchingBase = true;
  map.removeLayer(currentBase);
  currentBase = wanted.addTo(map);
  switchingBase = false;
}

function drawBlocks() {
  syncBaseToTheme(); // the dots are colored for the current theme; keep the basemap in step
  const color = valueScale();
  const radius = blockRadius();
  blocksLayer.clearLayers();
  for (const [lat, lon, value] of state.blocks) {
    blocksLayer.addLayer(L.circleMarker([lat, lon], {
      renderer: blockRenderer, radius, stroke: false, fillColor: color(value), fillOpacity: 0.85, interactive: false,
    }));
  }
  paintLegend();
  $("legend").hidden = !map.hasLayer(blocksLayer);
}

function paintLegend() {
  $("legend-bar").style.background = `linear-gradient(to right, ${RAMP[theme()].join(", ")})`;
  $("legend-ticks").replaceChildren(...[[0, "$0"], [2.5e5, "$250k"], [5e5, "$500k+"]].map(([v, text]) =>
    h("span", { style: `left: ${(v / VALUE_MAX) * 100}%` }, text)));
}

function pinIcon(status) {
  return L.divIcon({
    className: `pin pin--${status}`,
    html: '<svg viewBox="0 0 30 40" width="30" height="40" aria-hidden="true">'
      + '<path d="M15 1.5C7.6 1.5 1.5 7.4 1.5 14.7 1.5 24.6 15 38.5 15 38.5S28.5 24.6 28.5 14.7C28.5 7.4 22.4 1.5 15 1.5z"/>'
      + '<circle cx="15" cy="14.5" r="5"/></svg>',
    iconSize: [30, 40],
    iconAnchor: [15, 39],
  });
}

function placePin(lat, lon, status, label) {
  pinMarker ??= L.marker([lat, lon], { interactive: false, keyboard: false, zIndexOffset: 1000 });
  pinMarker.setLatLng([lat, lon]).setIcon(pinIcon(status)).addTo(selectionLayer);
  pinMarker.unbindTooltip().bindTooltip(h("span", {}, label), {
    permanent: true, direction: "top", offset: [0, -40], className: `pin-label pin-label--${status}`,
  }).openTooltip();
}

/** Fade the census dots while a selection is shown, so it stands out. */
const dimBlocks = (dimmed) => map.getPane("blocks").classList.toggle("is-dimmed", dimmed);

function syncNeighborVisibility() {
  const show = map.getZoom() >= NEIGHBOR_MIN_ZOOM;
  if (show && !map.hasLayer(neighborsLayer)) neighborsLayer.addTo(map);
  else if (!show && map.hasLayer(neighborsLayer)) neighborsLayer.remove();
}

function clearSelection() {
  selectionLayer.clearLayers();
  neighborsLayer.clearLayers();
  neighborMarkers = [];
}

function drawSelection(result) {
  clearSelection();
  dimBlocks(true);
  const ink = cssVar("--ink");
  const color = valueScale();
  const here = [result.location.latitude, result.location.longitude];
  neighborMarkers = result.neighbors.map((n) => {
    const there = [n.latitude, n.longitude];
    L.polyline([here, there], { color: ink, weight: 1.5, opacity: 0.6, interactive: false }).addTo(neighborsLayer);
    const label = h("div", {}, h("strong", {}, money(n.median_house_value)),
      h("span", {}, `Actual 1990 value, ${km(n.distance_km)} away`));
    return L.circleMarker(there, { radius: 6, color: ink, weight: 2, fillColor: color(n.median_house_value), fillOpacity: 1 })
      .bindTooltip(label, { direction: "top", offset: [0, -6], className: "map-tip" })
      .addTo(neighborsLayer);
  });
  syncNeighborVisibility();
  placePin(...here, "ready", compactMoney(result.prediction.value));
}

function highlightNeighbor(index, on) {
  const marker = neighborMarkers[index];
  if (!marker || !map.hasLayer(neighborsLayer)) return;
  marker.setRadius(on ? 9 : 6);
  if (on) marker.bringToFront().openTooltip();
  else marker.closeTooltip();
}

// ---------------------------------------------------------------- tooltip

const tip = $("tooltip");

function showTip(event, value, label) {
  tip.replaceChildren(h("strong", {}, value), h("span", {}, label));
  tip.hidden = false;
  const { width, height } = tip.getBoundingClientRect();
  let x = event.clientX + 14;
  let y = event.clientY - height - 12;
  if (x + width > innerWidth - 8) x = event.clientX - width - 14;
  if (y < 8) y = event.clientY + 16;
  tip.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
}

const hideTip = () => { tip.hidden = true; };

// ---------------------------------------------------------------- prediction flow

const panel = $("panel");
const body = $("panel-body");
let whatIfTimer = 0;

function setBusy(kind) {
  panel.dataset.busy = kind || "";
  panel.setAttribute("aria-busy", String(Boolean(kind)));
}

const announce = (text) => { $("announcer").textContent = text; };
const effectiveProfile = () => ({ ...state.estimate.estimated_profile, ...state.adjustments });

function selectPoint(lat, lon, { zoom } = {}) {
  clearTimeout(whatIfTimer);
  state.point = { lat, lon };
  state.adjustments = {};
  clearSelection();
  placePin(lat, lon, "loading", "Estimating…");
  if (zoom) map.flyTo([lat, lon], zoom, { duration: 1.1 });
  runPrediction(true);
}

async function runPrediction(newPoint) {
  const { lat, lon } = state.point;
  state.controller?.abort();
  const controller = (state.controller = new AbortController());
  const payload = { latitude: lat, longitude: lon };
  if (!newPoint && Object.keys(state.adjustments).length) payload.adjustments = state.adjustments;
  setBusy(newPoint ? "point" : "whatif");
  try {
    const result = await api("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    state.result = result;
    if (newPoint) {
      state.estimate = result;
      history.replaceState(null, "", `#${lat.toFixed(5)},${lon.toFixed(5)}`);
      drawSelection(result);
    } else {
      placePin(lat, lon, "ready", compactMoney(result.prediction.value));
    }
    renderResult(result, newPoint);
    announce(`${result.adjusted ? "What-if estimate" : "Estimated median house value"}: ${money(result.prediction.value)}.`);
  } catch (err) {
    if (err.name === "AbortError") return; // superseded by a newer request
    if (newPoint) {
      state.estimate = state.result = null;
      history.replaceState(null, "", location.pathname);
      placePin(lat, lon, "rejected", "No estimate here");
      dimBlocks(false);
      renderError(err);
    } else {
      const hero = $("sec-hero");
      hero?.querySelector(".callout--error")?.remove();
      hero?.append(h("p", { class: "callout callout--error" },
        h("span", { class: "callout-text" }, `Couldn't update the estimate: ${err.message}`)));
    }
    announce(err.message);
  } finally {
    if (state.controller === controller) setBusy(false);
  }
}

function onProfileInput(key, value) {
  state.adjustments[key] = value;
  refreshControl(key);
  clearTimeout(whatIfTimer);
  whatIfTimer = setTimeout(() => runPrediction(false), 200);
}

function resetWhatIf() {
  clearTimeout(whatIfTimer);
  state.controller?.abort();
  state.adjustments = {};
  state.result = state.estimate;
  renderResult(state.estimate, true);
  placePin(state.point.lat, state.point.lon, "ready", compactMoney(state.estimate.prediction.value));
  setBusy(false);
}

// ---------------------------------------------------------------- panel: static states

function presetSection() {
  return h("section", { class: "section" },
    h("h2", { class: "title-sm" }, "Try a place"),
    h("div", { class: "chips" }, PRESETS.map(([name, lat, lon]) =>
      h("button", { class: "chip", type: "button", onclick: () => selectPoint(lat, lon, { zoom: 12 }) }, name))),
  );
}

function modelCard() {
  const { metrics, model } = state.info;
  return h("footer", { class: "section model-card" },
    h("h2", { class: "title-sm" }, "About the model"),
    h("p", {}, `Random forest with ${model.n_estimators} trees, trained on ${fmtInt.format(metrics.n_train)} blocks `
      + "from the 1990 California census using the same pipeline as house_price_predictor.ipynb. "
      + `On ${fmtInt.format(metrics.n_test)} held-out blocks its average error is ${money(metrics.test_mae)} `
      + `(RMSE ${money(metrics.test_rmse)}, R² ${metrics.test_r2.toFixed(2)}).`),
    h("p", {}, "Values are in 1990 dollars and the data caps them at $500,001. The 2024 figure adjusts for "
      + "inflation only (CPI-U), not for today's housing market."),
  );
}

function renderWelcome() {
  body.replaceChildren(
    h("section", { class: "section" },
      h("h2", { class: "title-lg" }, "Click anywhere in California"),
      h("p", { class: "lead" }, "The model predicts a census block's median house value from nine inputs. A click "
        + "only gives a location, so the other seven are estimated from the nearest census blocks. You can then "
        + "adjust them."),
      h("ol", { class: "steps" },
        h("li", {}, h("span", {}, h("b", {}, "Pick a spot"), " on the map, or try a place below.")),
        h("li", {}, h("span", {}, h("b", {}, "The neighbourhood is estimated"),
          ` from the 8 closest of ${fmtInt.format(state.info.dataset.n_blocks)} census blocks.`)),
        h("li", {}, h("span", {}, h("b", {}, "The random forest predicts"),
          " the value, with a range and a breakdown of what drives it.")),
      ),
    ),
    presetSection(),
    modelCard(),
  );
}

function renderNotice(title, message) {
  return h("section", { class: "section notice", role: "alert" },
    h("div", { class: "notice-head" }, icons.info(), h("h2", { class: "title-sm" }, title)),
    h("p", {}, message),
  );
}

function renderError(err) {
  body.replaceChildren(renderNotice("No estimate for this spot", err.message), presetSection(), modelCard());
}

// ---------------------------------------------------------------- panel: result

function renderResult(result, newPoint) {
  hideTip(); // the charts under the pointer are about to be replaced
  if (newPoint || !$("sec-hero")) {
    body.replaceChildren(h("div", { class: "result" },
      h("section", { class: "section", id: "sec-place" }),
      h("section", { class: "section", id: "sec-hero" }),
      h("section", { class: "section stats", id: "sec-stats" }),
      h("section", { class: "section", id: "sec-dist" }),
      h("section", { class: "section", id: "sec-drivers" }),
      h("section", { class: "section", id: "sec-profile" }),
      h("section", { class: "section", id: "sec-neighbors" }),
      modelCard(),
    ));
    renderPlace(result);
    renderProfile(result);
    renderNeighbors(result);
  }
  renderHero(result);
  renderStats(result);
  renderDistribution(result);
  renderDrivers(result);
}

function renderPlace(r) {
  const { name, distance_km: d } = r.location.nearest_city;
  const { level, nearest_block_km: nearest } = r.coverage;
  $("sec-place").replaceChildren(
    h("div", { class: "place-row" },
      h("div", {},
        h("p", { class: "place-name" }, icons.pin(), d < 2 ? `Near ${name}` : `${km(d)} from ${name}`),
        h("p", { class: "place-coords" }, coords(r.location.latitude, r.location.longitude)),
      ),
      h("span", { class: `badge badge--${level}` }, h("span", { class: "badge-dot", "aria-hidden": "true" }),
        COVERAGE[level].label),
    ),
    h("p", { class: "place-note" }, `Nearest census block: ${km(nearest)}. ${COVERAGE[level].note}`),
  );
}

function renderHero(r) {
  const p = r.prediction;
  const estimate = state.estimate.prediction;
  fill($("sec-hero"),
    h("p", { class: "eyebrow" }, r.adjusted ? "What-if estimate" : "Estimated median house value"),
    h("p", { class: "hero-value" }, money(p.value)),
    h("p", { class: "hero-sub" }, "In 1990 dollars. About ", h("strong", {}, compactMoney(p.value_2024_dollars)),
      " in 2024 dollars (inflation only)."),
    h("p", { class: "hero-range" }, `80% of the model's ${state.info.model.n_estimators} trees predict `,
      h("strong", {}, `${compactMoney(p.low)} – ${compactMoney(p.high)}`), "."),
    p.near_cap && h("p", { class: "callout" }, h("span", { class: "callout-text" },
      "The 1990 data caps values at $500,001, so the real value here may be higher.")),
    r.adjusted && h("div", { class: "callout" },
      h("span", { class: "callout-text" }, h("strong", {}, signedMoney(p.value - estimate.value)),
        ` vs. the neighbourhood estimate of ${money(estimate.value)}`),
      h("button", { class: "btn-link", type: "button", onclick: resetWhatIf }, "Reset"),
    ),
  );
}

function statTile(label, value, sub) {
  return h("div", {},
    h("p", { class: "stat-label" }, label),
    h("p", { class: "stat-value" }, value),
    h("p", { class: "stat-sub" }, sub),
  );
}

function renderStats(r) {
  const { value, percentile } = r.prediction;
  const { california_median: median, nearby_actual: nearby } = r.comparison;
  const diff = Math.round(((value - median) / median) * 100);
  const rank = Math.min(99, Math.max(1, Math.floor(percentile)));
  $("sec-stats").replaceChildren(
    statTile("Nearby, actual", money(nearby), "8 closest blocks, distance-weighted"),
    statTile("California median", money(median),
      diff === 0 ? "Same as this estimate" : `This estimate is ${Math.abs(diff)}% ${diff > 0 ? "higher" : "lower"}`),
    statTile("Percentile", ordinal(rank), `Pricier than ${rank}% of California blocks`),
  );
}

function tableView(headers, rows, open) {
  return h("details", { class: "table-view", open },
    h("summary", {}, "Show as table"),
    h("table", { class: "data-table" },
      h("thead", {}, h("tr", {}, headers.map((t) => h("th", { scope: "col" }, t)))),
      h("tbody", {}, rows.map((row) => h("tr", {}, row.map((cell) => h("td", {}, cell))))),
    ),
  );
}

function renderDistribution(r) {
  const sec = $("sec-dist");
  const { edges, counts } = state.info.dataset.value_histogram;
  const total = counts.reduce((a, b) => a + b, 0);
  const wasOpen = sec.querySelector("details")?.open;
  const chart = h("div", { class: "chart" });
  sec.replaceChildren(
    h("h2", { class: "title-sm" }, "Where this sits in California"),
    h("p", { class: "subtitle" }, `Median house value of all ${fmtInt.format(total)} census blocks. The shaded band `
      + "is the middle 80% of tree predictions."),
    chart,
    tableView(["Value range", "Blocks", "Share"], counts.map((c, i) => [
      `${compactMoney(edges[i])} – ${compactMoney(edges[i + 1])}`, fmtInt.format(c), `${((c / total) * 100).toFixed(1)}%`,
    ]), wasOpen),
  );
  drawHistogram(chart, { edges, counts, total, ...r.prediction, median: r.comparison.california_median });
}

function roundedTop(x, y, w, height, r) {
  if (height <= 0 || w <= 0) return "";
  r = Math.min(r, w / 2, height);
  return `M${x},${y + height}V${y + r}A${r},${r} 0 0 1 ${x + r},${y}H${x + w - r}`
    + `A${r},${r} 0 0 1 ${x + w},${y + r}V${y + height}Z`;
}

function drawHistogram(el, { edges, counts, total, value, low, high, percentile, median }) {
  const width = Math.max(240, Math.round(el.clientWidth));
  const height = 150;
  const top = 30;
  const baseline = height - 22;
  const pad = 2;
  const maxCount = Math.max(...counts);
  const x = (v) => pad + (Math.min(v, VALUE_MAX) / VALUE_MAX) * (width - 2 * pad);
  const y = (c) => baseline - (c / maxCount) * (baseline - top);
  const color = valueScale();

  const bars = s("g");
  const hits = s("g");
  counts.forEach((count, i) => {
    const x0 = x(edges[i]);
    const x1 = x(edges[i + 1]);
    const w = Math.min(24, x1 - x0 - 2);
    const bar = s("path", {
      class: "bin", d: roundedTop((x0 + x1 - w) / 2, y(count), w, baseline - y(count), 4),
      fill: color((edges[i] + edges[i + 1]) / 2),
    });
    bars.append(bar);
    const hit = s("rect", { x: x0, y: top - 12, width: x1 - x0, height: baseline - top + 12, fill: "transparent" });
    hit.addEventListener("pointerenter", () => { bars.classList.add("is-dimmed"); bar.classList.add("is-hover"); });
    hit.addEventListener("pointermove", (e) => showTip(e, `${fmtInt.format(count)} blocks`,
      `${compactMoney(edges[i])} – ${compactMoney(edges[i + 1])} · ${((count / total) * 100).toFixed(1)}% of California`));
    hit.addEventListener("pointerleave", () => { bars.classList.remove("is-dimmed"); bar.classList.remove("is-hover"); hideTip(); });
    hits.append(hit);
  });

  const mx = x(value);
  const anchor = (px) => (px < 36 ? "start" : px > width - 36 ? "end" : "middle");
  const labels = [s("text", { class: "marker-label", x: mx, y: top - 18, "text-anchor": anchor(mx) }, compactMoney(value))];
  if (Math.abs(x(median) - mx) > 72) {
    labels.push(s("text", { x: x(median), y: top - 18, "text-anchor": anchor(x(median)) }, "CA median"));
  }

  const ticks = [0, 1e5, 2e5, 3e5, 4e5, 5e5].map((v, i, all) =>
    s("text", { x: x(v), y: baseline + 15, "text-anchor": i === 0 ? "start" : i === all.length - 1 ? "end" : "middle" },
      v === 0 ? "$0" : `$${v / 1e3}k`));

  const svgEl = s("svg", {
    width, height, viewBox: `0 0 ${width} ${height}`, role: "img",
    "aria-label": `Histogram of median house values across California census blocks. This estimate, `
      + `${money(value)}, is higher than ${Math.round(percentile)}% of blocks.`,
  },
  s("rect", { x: x(low), y: top - 10, width: Math.max(2, x(high) - x(low)), height: baseline - top + 10,
    style: "fill: var(--band)" }),
  bars,
  s("line", { x1: x(median), x2: x(median), y1: top - 10, y2: baseline, style: "stroke: var(--ink-3)", "stroke-width": 1 }),
  s("line", { x1: mx, x2: mx, y1: top - 12, y2: baseline, style: "stroke: var(--ink)", "stroke-width": 2 }),
  s("line", { x1: pad, x2: width - pad, y1: baseline + 0.5, y2: baseline + 0.5, style: "stroke: var(--axis)", "stroke-width": 1 }),
  labels,
  ticks,
  hits,
  );
  el.replaceChildren(svgEl);
}

function renderDrivers(r) {
  const { base_value: base, items } = r.contributions;
  const values = items.map((item) => item.value);
  const lo = Math.min(0, ...values);
  const span = Math.max(0, ...values) - lo || 1;
  const pct = (v) => ((v - lo) / span) * 100;

  const row = (cls, name, input, track, value) => h("div", { class: `driver ${cls}` },
    h("div", {}, h("p", { class: "driver-name" }, name), input && h("p", { class: "driver-input" }, input)),
    h("div", { class: "driver-track" }, track),
    h("p", { class: "driver-value" }, value),
  );

  const rows = items.map((item) => {
    const raise = item.value >= 0;
    const bar = h("div", {
      class: `driver-bar ${raise ? "raise" : "lower"}`,
      style: `left: ${pct(Math.min(0, item.value))}%; width: ${Math.max(0.5, (Math.abs(item.value) / span) * 100)}%`,
    });
    const el = row("", item.label, DRIVER_INPUT[item.key](r.model_inputs),
      [h("div", { class: "driver-zero", style: `left: ${pct(0)}%` }), bar], signedMoney(item.value));
    el.addEventListener("pointermove", (e) =>
      showTip(e, signedMoney(item.value), `${item.label} ${raise ? "raises" : "lowers"} the estimate`));
    el.addEventListener("pointerleave", hideTip);
    return el;
  });

  $("sec-drivers").replaceChildren(
    h("h2", { class: "title-sm" }, "What drives this estimate"),
    h("p", { class: "subtitle" }, "Starting from the average training block, each input pushes the estimate up or "
      + "down. Contributions are traced through every tree's decisions."),
    h("div", { class: "key-row" },
      h("span", { class: "key", style: "--key: var(--raise)" }, "Raises value"),
      h("span", { class: "key", style: "--key: var(--lower)" }, "Lowers value")),
    h("div", { class: "drivers" },
      row("driver--base", "Average block", "Starting point", null, money(base)),
      rows,
      row("driver--total", r.adjusted ? "What-if estimate" : "Estimate", null, null, money(r.prediction.value)),
    ),
  );
}

const floorTo = (v, step) => Math.floor(v / step) * step;
const ceilTo = (v, step) => Math.ceil(v / step) * step;

function renderProfile(r) {
  const ranges = state.info.dataset.profile_ranges;
  const estimated = state.estimate.estimated_profile;
  const sliders = PROFILE_FIELDS.map((field) => {
    const range = ranges[field.key];
    const est = estimated[field.key];
    const id = `ctl-${field.key}`;
    const input = h("input", {
      id, type: "range",
      min: +floorTo(Math.min(field.wide ? range.min : range.p1, est), field.step).toFixed(2),
      max: +ceilTo(Math.max(field.wide ? range.max : range.p99, est), field.step).toFixed(2),
      step: field.step,
      value: r.profile[field.key],
    });
    input.addEventListener("input", () => onProfileInput(field.key, Number(input.value)));
    return h("div", { class: "control", "data-key": field.key },
      h("div", { class: "control-head" }, h("label", { for: id }, field.label), h("output", { for: id })),
      input);
  });

  const select = h("select", { id: "ctl-ocean_proximity" }, state.info.ocean_categories.map((c) =>
    h("option", { value: c, selected: c === r.profile.ocean_proximity }, OCEAN_LABELS[c])));
  select.addEventListener("change", () => onProfileInput("ocean_proximity", select.value));

  $("sec-profile").replaceChildren(
    h("h2", { class: "title-sm" }, "Neighbourhood profile"),
    h("p", { class: "subtitle" }, "Estimated from the 8 nearest census blocks. Drag a slider to ask “what if?”"),
    h("div", { class: "controls" }, sliders,
      h("div", { class: "control", "data-key": "ocean_proximity" },
        h("div", { class: "control-head" }, h("label", { for: select.id }, "Ocean proximity"), h("output", { for: select.id })),
        select)),
    h("div", { class: "controls-foot" },
      h("span", {}, "Changes re-run the model instantly."),
      h("button", { class: "btn-link", type: "button", onclick: resetWhatIf }, "Reset to estimate")),
  );
  for (const key of [...PROFILE_FIELDS.map((f) => f.key), "ocean_proximity"]) refreshControl(key);
}

/** Show the slider's current value, plus the estimated value once the user has changed it. */
function refreshControl(key) {
  const output = document.querySelector(`.control[data-key="${key}"] output`);
  if (!output) return;
  const field = PROFILE_FIELDS.find((f) => f.key === key);
  const format = field?.format ?? ((v) => OCEAN_LABELS[v]);
  const was = key in state.adjustments
    ? [h("span", { class: "control-was" }, `was ${format(state.estimate.estimated_profile[key])}`)]
    : [];
  output.replaceChildren(...was, field ? format(effectiveProfile()[key]) : "");
}

function renderNeighbors(r) {
  const rows = r.neighbors.map((n, i) => {
    const tr = h("tr", {},
      h("td", {}, km(n.distance_km)),
      h("td", {}, money(n.median_house_value)),
      h("td", {}, compactMoney(n.median_income * 1e4)),
      h("td", {}, `${Math.round(n.housing_median_age)} yrs`));
    tr.addEventListener("pointerenter", () => highlightNeighbor(i, true));
    tr.addEventListener("pointerleave", () => highlightNeighbor(i, false));
    return tr;
  });
  const here = [r.location.latitude, r.location.longitude];
  $("sec-neighbors").replaceChildren(
    h("div", { class: "section-head" },
      h("h2", { class: "title-sm" }, "Nearest census blocks"),
      h("button", { class: "btn-link", type: "button",
        onclick: () => map.flyTo(here, Math.max(map.getZoom(), 13), { duration: 1.1 }) }, "Show on map")),
    h("p", { class: "subtitle" }, "The actual 1990 data this neighbourhood was estimated from. Hover a row to find "
      + "it on the map."),
    h("table", { class: "data-table" },
      h("thead", {}, h("tr", {}, ["Distance", "Actual value", "Income", "House age"].map((t) =>
        h("th", { scope: "col" }, t)))),
      h("tbody", {}, rows)),
  );
}

// ---------------------------------------------------------------- startup

function pointFromHash() {
  const match = location.hash.match(/^#(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$/);
  return match ? { lat: Number(match[1]), lon: Number(match[2]) } : null;
}

darkQuery.addEventListener("change", () => {
  if (!map) return;
  if (state.blocks.length) {
    drawBlocks();
  } else {
    syncBaseToTheme();
    paintLegend();
  }
  if (state.result) {
    drawSelection(state.result);
    renderDistribution(state.result);
  }
});

addEventListener("hashchange", () => {
  const point = pointFromHash();
  if (point && map) {
    map.setView([point.lat, point.lon], Math.max(map.getZoom(), 11));
    selectPoint(point.lat, point.lon);
  }
});

let panelWidth = 0;
new ResizeObserver(([entry]) => {
  const width = Math.round(entry.contentRect.width);
  if (width === panelWidth) return;
  panelWidth = width;
  if (state.result && $("sec-dist")) renderDistribution(state.result);
}).observe(panel);

async function start() {
  body.replaceChildren(h("section", { class: "section" }, h("p", { class: "muted" }, "Loading the model…")));
  setBusy("point");
  try {
    state.info = await api("/api/model-info");
  } catch (err) {
    body.replaceChildren(renderNotice("Can't reach the prediction server",
      `${err.message}. Start it with "python app.py", then reload this page.`));
    return;
  } finally {
    setBusy(false);
  }

  initMap(state.info.bounds);
  paintLegend();
  const fromHash = pointFromHash();
  if (fromHash) {
    map.setView([fromHash.lat, fromHash.lon], 11);
    selectPoint(fromHash.lat, fromHash.lon);
  } else {
    renderWelcome();
  }

  try {
    state.blocks = (await api("/api/blocks")).rows;
    drawBlocks();
  } catch (err) {
    console.warn("Could not load the census blocks layer:", err);
  }
}

start();

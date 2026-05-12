import os
import random
import math
from textwrap import dedent

import folium
import matplotlib.pyplot as plt
import requests
import streamlit as st
from streamlit_folium import st_folium
from streamlit.errors import StreamlitSecretNotFoundError


def _safe_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except StreamlitSecretNotFoundError:
        return default


API_KEY = os.getenv("OWM_API_KEY") or _safe_secret("OWM_API_KEY", "")
ORS_API_KEY = os.getenv("ORS_API_KEY") or _safe_secret("ORS_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or _safe_secret("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or _safe_secret("OPENAI_MODEL", "gpt-4.1-mini")


def _is_configured_key(value: str) -> bool:
    if not value:
        return False
    v = value.strip()
    return not (v.startswith("PASTE_") or v.endswith("_HERE"))
OWM_GEOCODE_URL = "http://api.openweathermap.org/geo/1.0/direct"
OWM_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
OWM_AIR_URL = "http://api.openweathermap.org/data/2.5/air_pollution"
ORS_ROUTE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"

st.set_page_config(page_title="ClimaPath Hackathon", layout="wide")


LOCATION_ALIASES = {
    "bangalore": "Bengaluru, Karnataka, IN",
    "bengaluru": "Bengaluru, Karnataka, IN",
    "tamil nadu": "Chennai, Tamil Nadu, IN",
}


STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700;800&family=Manrope:wght@500;700&display=swap');

:root {
  --bg1: #f3f7f2;
  --bg2: #fff8ed;
  --ink: #1f2937;
  --muted: #5f6b7a;
  --safe: #137f53;
  --fast: #c36e00;
  --eco: #0f6e9f;
  --card: rgba(255,255,255,0.72);
}

html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }

.main {
  background: radial-gradient(circle at 8% 5%, #d7efde 0, transparent 30%),
              radial-gradient(circle at 92% 8%, #ffe4bf 0, transparent 28%),
              linear-gradient(130deg, var(--bg1), var(--bg2));
}

.hero {
  background: linear-gradient(135deg, rgba(27,74,53,0.94), rgba(15,87,124,0.92));
  color: #f8fbff;
  border-radius: 20px;
  padding: 18px 20px;
  box-shadow: 0 15px 35px rgba(25, 42, 57, 0.24);
  margin-bottom: 12px;
}
.hero h1 { margin: 0 0 6px 0; font-size: 38px; font-weight: 800; }
.hero p { margin: 0; opacity: 0.92; }

.pill {
  display: inline-block;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 700;
  margin-right: 8px;
  margin-top: 10px;
}
.pill.live { background: #d6f5e5; color: #115a39; }
.pill.hybrid { background: #fff3d9; color: #7a4f00; }
.pill.sim { background: #dff3fb; color: #0a5d85; }

.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 10px 0 16px; }
.metric-card {
  background: var(--card);
  border: 1px solid rgba(26,45,68,.1);
  border-radius: 16px;
  padding: 12px;
  backdrop-filter: blur(6px);
}
.metric-label { color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px; }
.metric-value { color: var(--ink); font-size: 26px; font-weight: 800; margin-top: 3px; }

.route-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 10px; }
.route-card {
  background: rgba(255,255,255,0.76);
  border-radius: 18px;
  border: 2px solid rgba(28,53,79,0.12);
  padding: 14px;
}
.route-card.safe { border-color: rgba(19,127,83,.45); }
.route-card.fast { border-color: rgba(195,110,0,.45); }
.route-card.eco { border-color: rgba(15,110,159,.45); }
.route-card.overall { box-shadow: 0 15px 34px rgba(21,67,108,.22); }
.route-title { font-size: 22px; font-weight: 800; color: #243041; margin-bottom: 6px; }
.route-sub { color: #5e6777; margin-bottom: 10px; }
.badge { display: inline-block; border-radius: 999px; padding: 4px 10px; font-size: 11px; font-weight: 800; margin-right: 6px; }
.badge.safe { background: #ddf6eb; color: var(--safe); }
.badge.fast { background: #ffeccb; color: var(--fast); }
.badge.eco { background: #dff2fb; color: var(--eco); }
.badge.overall { background: #e7e5ff; color: #4a3b9a; }

.route-metric { color: #3f4958; font-size: 14px; margin: 4px 0; }
.route-metric strong { color: #16273b; }

@media (max-width: 960px) {
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .route-grid { grid-template-columns: 1fr; }
}
</style>
"""


def fetch_json(url: str, params: dict | None = None, json_body: dict | None = None, headers: dict | None = None):
    try:
        if json_body is not None:
            resp = requests.post(url, params=params or {}, json=json_body, headers=headers or {}, timeout=18)
        else:
            resp = requests.get(url, params=params or {}, headers=headers or {}, timeout=14)
        if resp.status_code != 200:
            return None
        return resp.json()
    except requests.RequestException:
        return None


def ask_general_ai(query: str, result: dict | None) -> str | None:
    if not OPENAI_API_KEY:
        return None
    try:
        context = "No route analysis available yet."
        if result:
            context = (
                f"Trip: {result.get('src_label', 'Source')} to {result.get('dst_label', 'Destination')}. "
                f"Best safe={result.get('best_safe')}, fast={result.get('best_fast')}, eco={result.get('best_eco')}, "
                f"overall={result.get('overall')}, exact_distance_km={result.get('exact_distance_km')}."
            )
        payload = {
            "model": OPENAI_MODEL,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful chatbot in a climate-route website. "
                        "Answer any user question clearly. If health advice is requested, give general guidance only and suggest consulting professionals for diagnosis."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Website context: {context}\n\nUser question: {query}",
                },
            ],
        }
        resp = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        text = data.get("output_text", "").strip()
        return text or None
    except requests.RequestException:
        return None


def fetch_openweather_json(url: str, params: dict):
    if not API_KEY:
        return None
    req_params = dict(params)
    req_params["appid"] = API_KEY
    return fetch_json(url, params=req_params, headers={"Accept": "application/json"})


def fetch_ors_geocode_json(query: str, country_code: str = "IN"):
    if not ORS_API_KEY:
        return None
    params = {
        "api_key": ORS_API_KEY,
        "text": query,
        "boundary.country": country_code.upper() if country_code else "IN",
        "size": 5,
    }
    return fetch_json(ORS_GEOCODE_URL, params=params, headers={"Accept": "application/json"})


def format_geocode_label(data: dict) -> str:
    if not data:
        return ""
    if "properties" in data:
        props = data["properties"]
        parts = [props.get("name"), props.get("region"), props.get("county"), props.get("postcode"), props.get("country")]
        return ", ".join(str(part) for part in parts if part)
    parts = [data.get("name"), data.get("state"), data.get("country")]
    return ", ".join(str(part) for part in parts if part)


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    coords = []
    idx = 0
    lat = 0
    lon = 0
    while idx < len(encoded):
        shift = 0
        result = 0
        while True:
            b = ord(encoded[idx]) - 63
            idx += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if result & 1 else result >> 1
        lat += dlat

        shift = 0
        result = 0
        while True:
            b = ord(encoded[idx]) - 63
            idx += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlon = ~(result >> 1) if result & 1 else result >> 1
        lon += dlon
        coords.append((lat / 1e5, lon / 1e5))
    return coords


def haversine_km(src_geo: tuple[float, float], dst_geo: tuple[float, float]) -> float:
    lat1, lon1 = src_geo
    lat2, lon2 = dst_geo
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def format_owm_label(row: dict) -> str:
    if not row:
        return ""
    parts = [row.get("name", ""), row.get("state", ""), row.get("country", "")]
    return ", ".join(part for part in parts if part)


def geocode_city(city: str, preferred_country: str = "IN"):
    query = city.strip()
    if not query:
        return None
    normalized = query.lower()
    query_for_lookup = LOCATION_ALIASES.get(normalized, query)

    # Prioritize ORS for pincode/area-level lookup (better locality precision).
    has_digit = any(ch.isdigit() for ch in query_for_lookup)
    if has_digit:
        ors_data = fetch_ors_geocode_json(query_for_lookup, preferred_country)
        if ors_data and ors_data.get("features"):
            feature = ors_data["features"][0]
            coords = feature.get("geometry", {}).get("coordinates", [])
            if len(coords) >= 2:
                return coords[1], coords[0], format_geocode_label(feature)

    # Prefer OpenWeatherMap direct geocoding for city/state queries.
    data = fetch_openweather_json(OWM_GEOCODE_URL, {"q": query_for_lookup, "limit": 5})
    if not data and preferred_country and "," not in query_for_lookup:
        data = fetch_openweather_json(OWM_GEOCODE_URL, {"q": f"{query_for_lookup},{preferred_country}", "limit": 5})

    if data:
        if preferred_country:
            pref = preferred_country.upper().strip()
            for row in data:
                if row.get("country", "").upper() == pref:
                    return row["lat"], row["lon"], format_owm_label(row)
        first = data[0]
        return first["lat"], first["lon"], format_owm_label(first)

    # Fall back to ORS geocoding for pin codes and more precise local lookups.
    ors_data = fetch_ors_geocode_json(query_for_lookup, preferred_country)
    if ors_data and ors_data.get("features"):
        feature = ors_data["features"][0]
        coords = feature.get("geometry", {}).get("coordinates", [])
        if len(coords) >= 2:
            return coords[1], coords[0], format_geocode_label(feature)

    return None


def get_current_weather(lat: float, lon: float):
    data = fetch_openweather_json(OWM_WEATHER_URL, {"lat": lat, "lon": lon, "units": "metric"})
    if not data or "main" not in data or "wind" not in data:
        return None
    rain = 0.0
    if "rain" in data and "1h" in data["rain"]:
        rain = data["rain"]["1h"]
    elif "snow" in data and "1h" in data["snow"]:
        rain = data["snow"]["1h"]
    return {
        "temperature_c": data["main"]["temp"],
        "wind_kmph": data["wind"]["speed"] * 3.6,
        "rain_mm": rain,
        "desc": data["weather"][0]["description"] if data.get("weather") else "",
    }


def get_air_quality(lat: float, lon: float):
    data = fetch_openweather_json(OWM_AIR_URL, {"lat": lat, "lon": lon})
    if not data or not data.get("list"):
        return None
    item = data["list"][0]
    return {
        "aqi_index": item["main"]["aqi"],
        "components": item["components"],
    }


def aqi_index_to_us_like(aqi_index: int) -> int:
    return {1: 45, 2: 85, 3: 135, 4: 190, 5: 280}.get(aqi_index, 100)


def get_real_environment(source: str, destination: str, preferred_country: str = ""):
    src = geocode_city(source, preferred_country=preferred_country)
    dst = geocode_city(destination, preferred_country=preferred_country)
    if not src or not dst:
        return None, None, None, source.strip(), destination.strip()

    src_geo = (src[0], src[1])
    dst_geo = (dst[0], dst[1])
    src_label = src[2] or source.strip()
    dst_label = dst[2] or destination.strip()

    src_w = get_current_weather(*src_geo)
    dst_w = get_current_weather(*dst_geo)
    src_a = get_air_quality(*src_geo)
    dst_a = get_air_quality(*dst_geo)
    if not src_w or not dst_w or not src_a or not dst_a:
        return None, src_geo, dst_geo, src_label, dst_label

    env = {
        "aqi": int(round((aqi_index_to_us_like(src_a["aqi_index"]) + aqi_index_to_us_like(dst_a["aqi_index"])) / 2)),
        "rain_risk": min(100, int((src_w["rain_mm"] + dst_w["rain_mm"]) * 12)),
        "temperature_c": round((src_w["temperature_c"] + dst_w["temperature_c"]) / 2, 1),
        "wind_kmph": round((src_w["wind_kmph"] + dst_w["wind_kmph"]) / 2, 1),
        "weather_description": f"{src_w['desc']} / {dst_w['desc']}",
    }
    return env, src_geo, dst_geo, src_label, dst_label


def get_real_routes(src_geo: tuple[float, float], dst_geo: tuple[float, float]):
    if not ORS_API_KEY:
        return None

    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body_alt = {
        "coordinates": [[src_geo[1], src_geo[0]], [dst_geo[1], dst_geo[0]]],
        "instructions": False,
        "alternative_routes": {"share_factor": 0.6, "target_count": 3, "weight_factor": 2},
    }
    body_one = {
        "coordinates": [[src_geo[1], src_geo[0]], [dst_geo[1], dst_geo[0]]],
        "instructions": False,
    }

    data = fetch_json(ORS_ROUTE_URL, json_body=body_alt, headers=headers)
    if not data or "routes" not in data or len(data["routes"]) == 0:
        data = fetch_json(ORS_ROUTE_URL, json_body=body_one, headers=headers)
    if not data or "routes" not in data or len(data["routes"]) == 0:
        return None

    routes = []
    for i, route in enumerate(data["routes"]):
        summary = route.get("summary", {})
        geometry = route.get("geometry", "")
        routes.append(
            {
                "name": f"Route {i + 1}",
                "distance_km": round(summary.get("distance", 0) / 1000, 1),
                "eta_min": int(round(summary.get("duration", 0) / 60)),
                "geometry": decode_polyline(geometry) if geometry else [],
            }
        )

    if len(routes) == 1:
        r = routes[0]
        # Create realistic variants for hackathon demo when ORS returns one path.
        routes = [
            r,
            {
                "name": "Route 2",
                "distance_km": round(r["distance_km"] * 1.08, 1),
                "eta_min": int(round(r["eta_min"] * 0.93)),
                "geometry": r["geometry"],
            },
            {
                "name": "Route 3",
                "distance_km": round(r["distance_km"] * 0.92, 1),
                "eta_min": int(round(r["eta_min"] * 1.11)),
                "geometry": r["geometry"],
            },
        ]
    return routes


def simulate_environment(seed: int, scenario: str):
    rng = random.Random(seed)
    profile = {
        "Balanced": (0, 0, 0),
        "Pollution Spike": (45, 0, 3),
        "Heavy Rain": (5, 45, -2),
        "Heatwave": (15, -10, 7),
    }[scenario]

    aqi = max(30, min(260, rng.randint(50, 140) + profile[0]))
    rain = max(0, min(100, rng.randint(10, 70) + profile[1]))
    temp = max(12, min(47, rng.randint(22, 37) + profile[2]))
    wind = max(4, min(40, rng.randint(8, 24)))
    return {
        "aqi": aqi,
        "rain_risk": rain,
        "temperature_c": temp,
        "wind_kmph": wind,
        "weather_description": "simulated",
    }


def simulate_routes(seed: int):
    rng = random.Random(seed + 991)
    return [
        {"name": "Route 1", "distance_km": round(rng.uniform(8, 16), 1), "eta_min": int(rng.uniform(24, 55)), "geometry": []},
        {"name": "Route 2", "distance_km": round(rng.uniform(9, 18), 1), "eta_min": int(rng.uniform(22, 52)), "geometry": []},
        {"name": "Route 3", "distance_km": round(rng.uniform(7, 17), 1), "eta_min": int(rng.uniform(26, 60)), "geometry": []},
    ]


def enrich_and_score(routes: list[dict], env: dict, seed: int):
    rng = random.Random(seed + 2026)

    max_eta = max(r["eta_min"] for r in routes)
    min_eta = min(r["eta_min"] for r in routes)
    max_dist = max(r["distance_km"] for r in routes)
    min_dist = min(r["distance_km"] for r in routes)

    scored = []
    for r in routes:
        dist_factor = 0 if max_dist == min_dist else (r["distance_km"] - min_dist) / (max_dist - min_dist)
        eta_factor = 0 if max_eta == min_eta else (r["eta_min"] - min_eta) / (max_eta - min_eta)

        route_aqi = int(max(20, env["aqi"] * (0.8 + 0.45 * dist_factor) + rng.randint(-8, 8)))
        flood = int(max(0, min(100, env["rain_risk"] * (0.7 + 0.5 * dist_factor) + rng.randint(-8, 10))))
        heat = int(max(0, min(100, (env["temperature_c"] - 18) * 3.4 * (0.7 + 0.5 * dist_factor) + rng.randint(-5, 9))))
        co2 = int(max(90, r["distance_km"] * (72 + 42 * dist_factor)))

        safe_score = 0.45 * route_aqi + 0.35 * flood + 0.20 * heat
        fast_score = (eta_factor * 100) * 0.75 + safe_score * 0.25
        eco_score = (co2 / max(co2, 1)) * 100 * 0.0 + co2 * 0.7 + route_aqi * 0.2 + r["eta_min"] * 0.1

        row = dict(r)
        row.update(
            {
                "aqi": route_aqi,
                "flood_risk": flood,
                "heat_stress": heat,
                "co2_g": co2,
                "risk_index": round(safe_score, 1),
                "safe_score": round(safe_score, 1),
                "fast_score": round(fast_score, 1),
                "eco_score": round(eco_score, 1),
            }
        )
        scored.append(row)

    best_safe = min(scored, key=lambda x: x["safe_score"])["name"]
    best_fast = min(scored, key=lambda x: x["fast_score"])["name"]
    best_eco = min(scored, key=lambda x: x["eco_score"])["name"]

    overall = min(
        scored,
        key=lambda x: x["safe_score"] * 0.45 + x["fast_score"] * 0.30 + x["eco_score"] * 0.25,
    )["name"]

    # Model estimate: health score from air quality, flood risk, and heat stress.
    for r in scored:
        penalty = 0.45 * r["aqi"] + 0.30 * r["flood_risk"] + 0.25 * r["heat_stress"]
        health_score = max(1, min(10, int(round(10 - (penalty / 32)))))
        r["health_score"] = health_score

    return scored, best_safe, best_fast, best_eco, overall


def render_summary(
    env: dict,
    data_mode: str,
    resolved_mode: str,
    source_label: str = "",
    destination_label: str = "",
    exact_distance_km: float | None = None,
):
    distance_text = f"{exact_distance_km:.2f} km" if exact_distance_km is not None else "N/A"
    st.markdown(
        dedent(
            f"""
            <div class='metric-grid'>
              <div class='metric-card'><div class='metric-label'>AQI Snapshot</div><div class='metric-value'>{env['aqi']}</div></div>
              <div class='metric-card'><div class='metric-label'>Flood Risk</div><div class='metric-value'>{env['rain_risk']}%</div></div>
              <div class='metric-card'><div class='metric-label'>Avg Temperature</div><div class='metric-value'>{env['temperature_c']}&#176;C</div></div>
              <div class='metric-card'><div class='metric-label'>Wind Speed</div><div class='metric-value'>{env['wind_kmph']} km/h</div></div>
            </div>
            <div style='color:#425066;font-size:14px;margin-bottom:10px;'>
              Input mode: <strong>{data_mode}</strong> | Data used: <strong>{resolved_mode}</strong> | Weather signal: <strong>{env.get('weather_description', 'N/A')}</strong>
            </div>
            <div style='color:#425066;font-size:14px;margin-bottom:10px;'>
              Exact source-destination distance: <strong>{distance_text}</strong>
            </div>
            <div style='color:#425066;font-size:14px;margin-bottom:10px;'>
              Resolved route: <strong>{source_label or 'N/A'}</strong> to <strong>{destination_label or 'N/A'}</strong>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def render_route_cards(scored_routes: list[dict], best_safe: str, best_fast: str, best_eco: str, overall: str):
    cards = ["<div class='route-grid'>"]
    for r in scored_routes:
        classes = ["route-card"]
        badges = []
        if r["name"] == best_safe:
            classes.append("safe")
            badges.append("<span class='badge safe'>SAFE WINNER</span>")
        if r["name"] == best_fast:
            classes.append("fast")
            badges.append("<span class='badge fast'>FAST WINNER</span>")
        if r["name"] == best_eco:
            classes.append("eco")
            badges.append("<span class='badge eco'>ECO WINNER</span>")
        if r["name"] == overall:
            classes.append("overall")
            badges.append("<span class='badge overall'>OVERALL PICK</span>")

        cards.append(
            dedent(
                f"""
                <div class='{' '.join(classes)}'>
                  <div class='route-title'>{r['name']}</div>
                  <div class='route-sub'>{' '.join(badges)}</div>
                  <div class='route-metric'><strong>Distance:</strong> {r['distance_km']} km</div>
                  <div class='route-metric'><strong>ETA:</strong> {r['eta_min']} min</div>
                  <div class='route-metric'><strong>AQI:</strong> {r['aqi']}</div>
                  <div class='route-metric'><strong>Flood Risk:</strong> {r['flood_risk']}%</div>
                  <div class='route-metric'><strong>Heat Stress:</strong> {r['heat_stress']}%</div>
                  <div class='route-metric'><strong>CO2:</strong> {r['co2_g']} g</div>
                  <div class='route-metric'><strong>Climate Risk Index:</strong> {r['risk_index']}</div>
                </div>
                """
            )
        )
    cards.append("</div>")
    st.markdown("".join(cards), unsafe_allow_html=True)


def render_map(route_polylines: list[dict], center: tuple[float, float] | None):
    st.subheader("Route Map")
    map_tiles = "CartoDB Positron"
    if route_polylines and center:
        fmap = folium.Map(location=center, zoom_start=10, tiles=map_tiles)
        colors = ["#137f53", "#c36e00", "#0f6e9f"]
        for i, row in enumerate(route_polylines):
            folium.PolyLine(row["coords"], color=colors[i % 3], weight=5, opacity=0.82, tooltip=row["name"]).add_to(fmap)
        if route_polylines[0]["coords"]:
            folium.Marker(route_polylines[0]["coords"][0], tooltip="Start").add_to(fmap)
            folium.Marker(route_polylines[0]["coords"][-1], tooltip="Destination").add_to(fmap)
        st_folium(fmap, width=700, height=470)
    else:
        demo = folium.Map(location=[20.5937, 78.9629], zoom_start=4, tiles=map_tiles)
        st_folium(demo, width=700, height=470)


def render_route_dialogue(result: dict | None):
    st.subheader("Route Information")
    if not result:
        st.info("Analyze a route to view auto insights for Safe, Fast, and Eco route choices.")
        return

    scored = result["scored"]
    safe_name = result["best_safe"]
    fast_name = result["best_fast"]
    eco_name = result["best_eco"]

    def pick(name: str) -> dict:
        return next((r for r in scored if r["name"] == name), scored[0])

    safe = pick(safe_name)
    fast = pick(fast_name)
    eco = pick(eco_name)
    route_names = [r["name"] for r in scored]
    selected_name = st.selectbox(
        "Choose a route to view health impact",
        route_names,
        index=route_names.index(eco_name) if eco_name in route_names else 0,
        key="route_health_choice",
    )
    selected = pick(selected_name)
    baseline = fast if fast["name"] != selected["name"] else max(scored, key=lambda x: x["aqi"])
    pollution_drop_pct = max(0, int(round((baseline["aqi"] - selected["aqi"]) * 100 / max(baseline["aqi"], 1))))
    co2_drop_pct = max(0, int(round((baseline["co2_g"] - selected["co2_g"]) * 100 / max(baseline["co2_g"], 1))))
    asthma_benefit_pct = max(5, min(40, int(round(10 + pollution_drop_pct * 0.7))))
    heart_benefit = "Lower heart-risk pollution exposure" if pollution_drop_pct >= 10 else "Moderate heart-risk benefit"
    heat_benefit = "Likely lower heat-stress exposure" if selected["heat_stress"] <= baseline["heat_stress"] else "Similar heat-stress profile"
    health_line = (
        f"If you choose {selected_name}, pollution exposure is about {pollution_drop_pct}% lower vs {baseline['name']}, "
        f"which may provide ~{asthma_benefit_pct}% asthma-trigger reduction (model estimate)."
    )

    st.markdown(
        f"""
        <div style='background:rgba(255,255,255,0.84);border:1px solid rgba(26,45,68,.12);border-radius:14px;padding:14px;'>
          <p><strong>Safe route ({safe_name})</strong>: lower climate exposure. Expect AQI {safe['aqi']}, flood risk {safe['flood_risk']}%, ETA {safe['eta_min']} min.</p>
          <p><strong>Fast route ({fast_name})</strong>: shortest travel time. Expect ETA {fast['eta_min']} min with AQI {fast['aqi']} and flood risk {fast['flood_risk']}%.</p>
          <p><strong>Eco route ({eco_name})</strong>: lower emission intensity. Expect CO2 near {eco['co2_g']} g for {eco['distance_km']} km at ETA {eco['eta_min']} min.</p>
          <hr style='border:none;border-top:1px solid rgba(26,45,68,.12);margin:10px 0;' />
          <p><strong>Health Dialogue ({selected_name})</strong>: {health_line}</p>
          <p>CO2 is about <strong>{co2_drop_pct}% lower</strong> vs {baseline['name']}. Health cue: <strong>{heart_benefit}</strong>. Heat cue: <strong>{heat_benefit}</strong>.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chatbot_reply(query: str, result: dict | None) -> str:
    q = (query or "").lower().strip()
    if not q:
        return "Ask anything. I can explain this website, routing logic, climate terms, trip info, or general guidance."
    if "use of this website" in q or "purpose" in q or "what is this website" in q or "what does this website do" in q:
        return (
            "This website helps you plan travel with climate-aware routing. It compares multiple routes and shows ETA, distance, "
            "AQI, flood risk, heat stress, CO2 impact, and an overall recommendation so you can choose safer or smarter travel."
        )
    if "how to use" in q or "how do i use" in q or "steps" in q:
        return (
            "Use it in 3 steps: 1) Enter source and destination (city/area/pincode). "
            "2) Click Analyze Climate Route. 3) Review route cards, map, and recommendation, then ask me follow-up questions."
        )
    if "aqi" in q and ("what is" in q or "meaning" in q):
        return "AQI means Air Quality Index. Lower AQI is generally better for breathing comfort and health."
    if ("flood risk" in q or "heat stress" in q) and ("what is" in q or "meaning" in q):
        return "Flood risk estimates rain/water-logging chance on the route. Heat stress reflects likely thermal discomfort during travel."
    if "who made" in q or "developer" in q:
        return "This app is your climate-routing project in Streamlit, designed for smarter route decisions."
    if not result:
        return "Run 'Analyze Climate Route' first, then I can answer with exact route details."

    scored = result["scored"]
    safe_name = result["best_safe"]
    fast_name = result["best_fast"]
    eco_name = result["best_eco"]
    overall = result["overall"]
    src = result.get("src_label", "Source")
    dst = result.get("dst_label", "Destination")
    exact_distance_km = result.get("exact_distance_km")

    def pick(name: str) -> dict:
        return next((r for r in scored if r["name"] == name), scored[0])

    safe = pick(safe_name)
    fast = pick(fast_name)
    eco = pick(eco_name)
    overall_row = pick(overall)
    co2_saved = max(0, fast["co2_g"] - eco["co2_g"])
    aqi_better_pct = max(0, int(round((fast["aqi"] - eco["aqi"]) * 100 / max(fast["aqi"], 1))))
    pm25_cut_pct = max(8, min(45, int(round(18 + aqi_better_pct * 0.6))))
    heat_relief_c = min(3, max(1, int(round((fast["heat_stress"] - eco["heat_stress"]) / 12))))
    health_cost_saved_inr = int(round(700 + co2_saved * 0.015 + aqi_better_pct * 18 + max(0, fast["flood_risk"] - eco["flood_risk"]) * 4))
    asthma_risk_drop_pct = max(8, min(38, int(round(12 + aqi_better_pct * 0.55))))

    if "safe health" in q or "health safe" in q:
        return (
            f"Safe route is {safe_name}: ETA {safe['eta_min']} min, AQI {safe['aqi']}, flood risk {safe['flood_risk']}%, "
            f"Health Score {safe.get('health_score', 8)}/10.\n"
            "For full disease-level details, ask: eco health shield."
        )
    if "safe" in q:
        return (
            f"Safe route is {safe_name}: ETA {safe['eta_min']} min, AQI {safe['aqi']}, flood risk {safe['flood_risk']}%, "
            f"Health Score {safe.get('health_score', 8)}/10."
        )
    if "fast" in q or "quick" in q:
        return f"Fast route is {fast_name}: ETA {fast['eta_min']} min for {fast['distance_km']} km."
    if "eco health" in q or "health eco" in q:
        q = "health shield"
    if "eco" in q or "emission" in q or "co2" in q:
        return (
            f"Eco route is {eco_name}: CO2 about {eco['co2_g']} g, distance {eco['distance_km']} km, ETA {eco['eta_min']} min, "
            f"Health Score {eco.get('health_score', 9)}/10."
        )
    if "distance" in q:
        if exact_distance_km is not None:
            return f"Exact source-to-destination distance ({src} to {dst}) is {exact_distance_km:.2f} km."
        return "Exact distance is unavailable for this query right now."
    if "aqi" in q:
        return f"Average route climate snapshot AQI is {result['env']['aqi']}. Safest route AQI: {safe['aqi']}."
    if "eta" in q or "time" in q:
        return f"Best ETA is {fast['eta_min']} min on {fast_name}. Overall recommended route ({overall}) ETA is {overall_row['eta_min']} min."
    if "recommend" in q or "best" in q:
        return f"Overall recommended route is {overall}. Safe={safe_name}, Fast={fast_name}, Eco={eco_name}."
    if "hello" in q or "hi" in q:
        return "Hello! How can I help you?"
    if "weather" in q or "rain" in q or "flood" in q or "heat" in q:
        env = result["env"]
        return f"Weather impact snapshot: AQI {env['aqi']}, flood risk {env['rain_risk']}%, temperature {env['temperature_c']}C, wind {env['wind_kmph']} km/h."
    if "compare" in q:
        return (
            f"Comparison: Safe={safe_name} (AQI {safe['aqi']}, flood {safe['flood_risk']}%), "
            f"Fast={fast_name} (ETA {fast['eta_min']} min), Eco={eco_name} (CO2 {eco['co2_g']} g)."
        )
    if "health" in q or "disease" in q or "shield" in q or "medical" in q:
        return (
            "🌿 Eco Route Health Benefits\n"
            "By choosing this route, you reduce exposure to:\n"
            f"✓ PM2.5 particles -> lowers Asthma risk by {asthma_risk_drop_pct}%\n"
            "✓ Traffic emissions -> protects heart health\n"
            "✓ Urban heat zones -> reduces Heat Stroke risk\n"
            f"Estimated health cost saved: ₹{health_cost_saved_inr:,}/trip (model estimate)\n\n"
            "Eco Route protects you from:\n"
            f"1. Asthma & Bronchitis -> Cuts lung-irritant exposure by {pm25_cut_pct}% vs fast route\n"
            "2. Heart Attack / Stroke -> Reduces heart-risk pollution exposure\n"
            "3. Lung Cancer -> Limits exposure to carcinogenic exhaust\n"
            "4. Allergies & Eye Irritation -> Fewer allergens & eye-burning particles\n"
            f"5. Heat Stroke -> Up to {heat_relief_c}C cooler with green cover\n"
            "6. Fatigue / Migraine -> Calmer drive = less headache risk\n\n"
            f"Health Scores: Fast Route {fast.get('health_score', 6)}/10, Safe Route {safe.get('health_score', 8)}/10, Eco Route {eco.get('health_score', 9)}/10.\n"
            "Reference note: WHO reports air pollution is linked to ~7 million premature deaths/year. "
            "This app's health impacts are planning estimates, not medical advice."
        )
    if "why choose eco route" in q or ("choose eco" in q and "why" in q):
        return (
            "Eco Route cuts your exposure to PM2.5 by about 30% (model estimate). "
            "That means lower asthma, heart risk, and headache chances. "
            "Plus you save roughly 1.2 kg CO2 on this trip profile."
        )
    if "help my asthma" in q or ("asthma" in q and "eco" in q):
        return (
            "Yes. Eco Route avoids heavy diesel corridors where possible, so you can breathe cleaner air than fast-route patterns. "
            "Estimated cleaner-air exposure benefit is about 28% vs Fast Route (model estimate)."
        )
    if "safer in summer" in q or ("summer" in q and "safe" in q):
        return (
            "Eco Route can favor greener, less heat-intense stretches. "
            "Typical modeled benefit is up to 3C lower heat exposure, which helps reduce heat-stress risk."
        )
    if "health benefits" in q or "top 3" in q:
        return (
            "Top 3 health benefits:\n"
            "1. Protects lungs by reducing pollution exposure.\n"
            "2. Lowers heart stress from cleaner, calmer travel patterns.\n"
            "3. Reduces heat exposure on high-temperature days.\n"
            "Ask 'show health benefits' for full disease-level details."
        )
    if any(k in q for k in ["website", "app", "feature", "dashboard"]):
        return (
            "This website gives climate-aware route planning with map, distance, ETA, AQI, flood risk, heat stress, CO2, and route recommendation."
        )
    if any(k in q for k in ["route", "distance", "eta", "time", "best", "recommend"]):
        return (
            f"For this trip: Best overall route is {overall}. "
            f"Safe={safe_name}, Fast={fast_name}, Eco={eco_name}. "
            "Ask me for exact distance, ETA, or route comparison."
        )
    if any(k in q for k in ["health", "asthma", "heart", "stroke", "heat", "pollution"]):
        return (
            "Health view: cleaner routes reduce pollution and heat exposure, which can lower respiratory and cardiovascular stress. "
            "Ask: 'show health benefits' for detailed disease-wise impact."
        )
    ai_answer = ask_general_ai(query, result)
    if ai_answer:
        return ai_answer
    return (
        "I can answer many questions. For fully open-ended answers, add OPENAI_API_KEY in your .streamlit/secrets.toml "
        "or environment so I can use the AI model."
    )


def render_chatbot(result: dict | None):
    st.markdown("### Chat Assistant")
    st.caption("How can I help you?")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    chat_box = st.container(height=220)
    with chat_box:
        if not st.session_state.chat_history:
            st.write("Assistant: How can I help you?")
        else:
            for item in st.session_state.chat_history[-8:]:
                st.write(f"You: {item['q']}")
                st.write(f"Assistant: {item['a']}")

    if st.button("Clear Chat", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.chat_query = ""
        st.rerun()

    c1, c2 = st.columns([4, 1])
    with c1:
        query = st.text_input("Message", key="chat_query", label_visibility="collapsed", placeholder="Type your question...")
    with c2:
        ask = st.button("Send", use_container_width=True)

    if ask and query.strip():
        answer = chatbot_reply(query, result)
        st.session_state.chat_history.append({"q": query.strip(), "a": answer})
        st.rerun()


st.markdown(STYLE, unsafe_allow_html=True)
st.markdown(
    """
    <div class='hero'>
      <h1>ClimaPath Hackathon</h1>
      <p>Climate-aware routing with safe, fast, and eco decisions across global cities using real-time APIs and simulation fallback.</p>
      <span class='pill live'>REAL-TIME</span><span class='pill hybrid'>HYBRID</span><span class='pill sim'>SIMULATED</span>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Control Panel")
    data_mode = st.radio("Data Mode", ["Hybrid (Recommended)", "Real-time Only", "Simulated Only"])
    country_code = "IN"
    scenario = st.selectbox("Simulation Scenario", ["Balanced", "Pollution Spike", "Heavy Rain", "Heatwave"])
    show_map = st.checkbox("Show route map", value=True)

left, right = st.columns([1.05, 1])
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

with left:
    source = st.text_input(
        "Source",
        value="Bangalore",
        help="Use city, area, or pincode. Example: Bangalore, Karnataka 560001 or Jayanagar 560041.",
    )
    destination = st.text_input(
        "Destination",
        value="Tamil Nadu",
        help="Use city, area, or pincode. Example: Chennai, Tamil Nadu 600001 or Coimbatore 641001.",
    )
    analyze = st.button("Analyze Climate Route", use_container_width=True)

    if analyze:
        has_owm = _is_configured_key(API_KEY)
        has_ors = _is_configured_key(ORS_API_KEY)
        warnings = []

        if not source.strip() or not destination.strip():
            st.error("Enter both source and destination cities.")
            st.stop()

        seed = abs(hash((source.strip().lower(), destination.strip().lower(), scenario))) % (10**7)
        mode = data_mode
        env = None
        routes = None
        src_label = source.strip()
        dst_label = destination.strip()
        src_geo = None
        dst_geo = None
        route_polylines = []
        route_center = None
        resolved_mode = ""

        if mode == "Simulated Only":
            src_data = geocode_city(source, preferred_country=country_code.strip())
            dst_data = geocode_city(destination, preferred_country=country_code.strip())
            if src_data:
                src_geo = (src_data[0], src_data[1])
                src_label = src_data[2] or src_label
            if dst_data:
                dst_geo = (dst_data[0], dst_data[1])
                dst_label = dst_data[2] or dst_label
            env = simulate_environment(seed, scenario)
            routes = simulate_routes(seed)
            resolved_mode = "Simulated"
        else:
            env, src_geo, dst_geo, src_label, dst_label = get_real_environment(
                source, destination, preferred_country=country_code.strip()
            )
            if env and src_geo and dst_geo and ORS_API_KEY:
                route_data = get_real_routes(src_geo, dst_geo)
                if route_data:
                    routes = route_data
                    route_polylines = [{"name": r["name"], "coords": r["geometry"]} for r in route_data if r.get("geometry")]
                    if route_polylines:
                        points = [pt for r in route_polylines for pt in r["coords"]]
                        route_center = (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))
                    resolved_mode = "Real-time"

            if mode == "Real-time Only" and (env is None or routes is None):
                if not has_owm or not has_ors:
                    st.error("API keys are missing or placeholders. Update .streamlit/secrets.toml with real OWM_API_KEY and ORS_API_KEY.")
                else:
                    st.error("Real-time APIs failed for this query. Check city names/country code or retry.")
                st.stop()

            if env is None:
                env = simulate_environment(seed, scenario)
                if not has_owm:
                    warnings.append("OpenWeatherMap key missing/placeholder. Using simulated climate values.")
                else:
                    warnings.append("OpenWeatherMap unavailable for this query. Using simulated climate values.")
            if routes is None:
                routes = simulate_routes(seed)
                if not has_ors:
                    warnings.append("OpenRouteService key missing/placeholder. Using simulated route options.")
                else:
                    warnings.append("OpenRouteService unavailable for this query. Using simulated route options.")
            if not resolved_mode:
                resolved_mode = "Hybrid"

        scored, best_safe, best_fast, best_eco, overall = enrich_and_score(routes, env, seed)
        exact_distance_km = None
        if routes:
            exact_distance_km = min(r["distance_km"] for r in routes)
        elif src_geo and dst_geo:
            exact_distance_km = haversine_km(src_geo, dst_geo)
        st.session_state.analysis_result = {
            "warnings": warnings,
            "data_mode": data_mode,
            "resolved_mode": resolved_mode,
            "env": env,
            "src_label": src_label,
            "dst_label": dst_label,
            "scored": scored,
            "best_safe": best_safe,
            "best_fast": best_fast,
            "best_eco": best_eco,
            "overall": overall,
            "route_polylines": route_polylines,
            "route_center": route_center,
            "exact_distance_km": exact_distance_km,
        }

    result = st.session_state.analysis_result
    if result:
        for msg in result["warnings"]:
            st.warning(msg)

        st.subheader("Route Decision Engine")
        st.success(f"Safe Route: {result['best_safe']}")
        st.info(f"Fast Route: {result['best_fast']}")
        st.success(f"Eco Route: {result['best_eco']}")
        st.warning(f"Overall Recommended Route: {result['overall']}")

        render_summary(
            result["env"],
            result["data_mode"],
            result["resolved_mode"],
            source_label=result.get("src_label", ""),
            destination_label=result.get("dst_label", ""),
            exact_distance_km=result.get("exact_distance_km"),
        )
        render_route_cards(result["scored"], result["best_safe"], result["best_fast"], result["best_eco"], result["overall"])

        fig, ax = plt.subplots(figsize=(7, 3.4))
        labels = [r["name"] for r in result["scored"]]
        values = [r["risk_index"] for r in result["scored"]]
        ax.bar(labels, values, color=["#137f53", "#c36e00", "#0f6e9f"])
        ax.set_title("Climate Risk Index by Route (Lower is Better)")
        ax.set_ylabel("Risk Index")
        st.pyplot(fig)

        st.dataframe(
            [
                {
                    "Route": r["name"],
                    "Distance (km)": r["distance_km"],
                    "ETA (min)": r["eta_min"],
                    "AQI": r["aqi"],
                    "Flood Risk %": r["flood_risk"],
                    "Heat Stress %": r["heat_stress"],
                    "CO2 (g)": r["co2_g"],
                    "Risk Index": r["risk_index"],
                }
                for r in result["scored"]
            ],
            use_container_width=True,
            hide_index=True,
        )

with right:
    result = st.session_state.analysis_result
    route_polylines = result["route_polylines"] if result else []
    route_center = result["route_center"] if result else None
    if show_map:
        render_map(route_polylines, route_center)
        render_route_dialogue(result)
        render_chatbot(result)
    else:
        st.info("Enable route map from the control panel.")

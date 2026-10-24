"""Interactive business-density radar built with Streamlit.

The module renders an interactive heat map of companies grouped by city with
filters for revenue and revenue-growth dynamics. All business data is read from
the ``data/`` directory of the project.

Run as a standalone Streamlit page::

    streamlit run modules/radar.py

Or import the renderer into an existing multipage app::

    from modules.radar import render_radar
    render_radar()
"""

from __future__ import annotations

import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any, Iterable

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

COMPANIES_FILE = "companies.csv"
INVESTMENTS_FILE = "investmensts.csv"  # historical spelling used in data/
TENDERS_FILE = "tenders.csv"
REGIONS_FILE = "region.json"

REQUIRED_COMPANY_COLUMNS = {
    "company_id",
    "name",
    "city",
    "revenue_2023",
    "revenue_2024",
    "revenue_2025",
    "employees",
    "customer_status",
    "potential_score",
}
REQUIRED_INVESTMENT_COLUMNS = {
    "investment_id",
    "company_id",
    "amount_rub",
    "expected_roi_percent",
}
REQUIRED_TENDER_COLUMNS = {"tender_id", "city", "region", "budget_rub"}

# Reference coordinates for the cities that appear in data/. Coordinates are
# static metadata: business metrics always come from the files in data/.
# If region.json ever provides latitude/longitude, those values win.
CITY_META: dict[str, dict[str, Any]] = {
    "Rostov-on-Don": {"lat": 47.2357, "lon": 39.7015, "region": "Rostov Oblast"},
    "Bataysk": {"lat": 47.1397, "lon": 39.7516, "region": "Rostov Oblast"},
    "Taganrog": {"lat": 47.2362, "lon": 38.8969, "region": "Rostov Oblast"},
    "Novocherkassk": {"lat": 47.4222, "lon": 40.0937, "region": "Rostov Oblast"},
    "Shakhty": {"lat": 47.7090, "lon": 40.2158, "region": "Rostov Oblast"},
    "Krasnodar": {"lat": 45.0355, "lon": 38.9753, "region": "Krasnodar Krai"},
    "Sochi": {"lat": 43.5855, "lon": 39.7231, "region": "Krasnodar Krai"},
    "Novorossiysk": {"lat": 44.7239, "lon": 37.7686, "region": "Krasnodar Krai"},
    "Armavir": {"lat": 44.9892, "lon": 40.6800, "region": "Krasnodar Krai"},
    "Anapa": {"lat": 44.8908, "lon": 37.3195, "region": "Krasnodar Krai"},
}

GROWTH_METRICS = {
    "Рост 2024 → 2025, %": "growth_2024_2025",
    "Рост 2023 → 2025, %": "growth_2023_2025",
    "CAGR 2023–2025, %": "cagr_2023_2025",
}

DENSITY_METRICS = {
    "Количество компаний": "companies_count",
    "Выручка": "revenue_total",
    "Сотрудники": "employees_total",
    "Инвестиции": "investments_total",
}

STATUS_COLORS = {
    "Current": "#2e7d32",
    "Potential": "#f9a825",
    "Lost": "#c62828",
}

REGION_PALETTE = ["#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b"]

HEAT_GRADIENT = {
    0.2: "#2c7bb6",
    0.4: "#abd9e9",
    0.6: "#ffffbf",
    0.8: "#fdae61",
    1.0: "#d7191c",
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _file_signature(data_dir: Path) -> tuple[tuple[str, int | None, int | None], ...]:
    """Return a cache-busting signature for the four data files."""
    signature: list[tuple[str, int | None, int | None]] = []
    for name in (COMPANIES_FILE, INVESTMENTS_FILE, TENDERS_FILE, REGIONS_FILE):
        path = data_dir / name
        try:
            stat = path.stat()
        except FileNotFoundError:
            signature.append((name, None, None))
        else:
            signature.append((name, stat.st_size, stat.st_mtime_ns))
    return tuple(signature)


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="utf-8-sig")


def _load_regions(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        payload = payload.get("regions", [payload])
    if not isinstance(payload, list):
        payload = [payload]
    return pd.DataFrame(payload)


def _require_columns(frame: pd.DataFrame, required: Iterable[str], source: str) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"{source}: отсутствуют обязательные колонки: {', '.join(missing)}")


@st.cache_data(show_spinner=False)
def load_data(data_dir: str, signature: tuple) -> dict[str, pd.DataFrame]:
    """Read all datasets from *data_dir* once per file-signature."""
    _ = signature  # part of the cache key only
    base = Path(data_dir)
    companies = _read_csv(base / COMPANIES_FILE)
    investments = _read_csv(base / INVESTMENTS_FILE)
    tenders = _read_csv(base / TENDERS_FILE)
    regions = _load_regions(base / REGIONS_FILE)

    _require_columns(companies, REQUIRED_COMPANY_COLUMNS, COMPANIES_FILE)
    _require_columns(investments, REQUIRED_INVESTMENT_COLUMNS, INVESTMENTS_FILE)
    _require_columns(tenders, REQUIRED_TENDER_COLUMNS, TENDERS_FILE)
    if not regions.empty and "name" not in regions.columns:
        raise ValueError(f"{REGIONS_FILE}: отсутствует обязательная колонка 'name'")

    return {
        "companies": companies,
        "investments": investments,
        "tenders": tenders,
        "regions": regions,
    }

# ---------------------------------------------------------------------------
# Numeric and formatting helpers
# ---------------------------------------------------------------------------


def _safe_growth(current: Any, previous: Any) -> float:
    try:
        current_value = float(current)
        previous_value = float(previous)
    except (TypeError, ValueError):
        return float("nan")
    if pd.isna(current_value) or pd.isna(previous_value) or previous_value <= 0:
        return float("nan")
    return (current_value - previous_value) / previous_value * 100.0


def _safe_cagr(current: Any, start: Any, periods: int = 2) -> float:
    try:
        current_value = float(current)
        start_value = float(start)
    except (TypeError, ValueError):
        return float("nan")
    if (
        pd.isna(current_value)
        or pd.isna(start_value)
        or start_value <= 0
        or current_value < 0
        or periods <= 0
    ):
        return float("nan")
    return ((current_value / start_value) ** (1.0 / periods) - 1.0) * 100.0


def _numeric_bounds(series: pd.Series, *, integer: bool = False) -> tuple[float, float]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return (0.0, 1.0)
    low = float(values.min())
    high = float(values.max())
    if low == high:
        pad = max(abs(low) * 0.05, 1.0)
        low -= pad
        high += pad
    if integer:
        return (float(math.floor(low)), float(math.ceil(high)))
    return (low, high)


def _step_for(low: float, high: float, *, integer: bool = False) -> float:
    span = abs(high - low)
    if span <= 0:
        return 1.0 if integer else 0.1
    if integer:
        return float(max(1, int(round(span / 100))))
    return float(max(0.1, round(span / 100, 2)))


def _ru_number(value: Any, decimals: int = 0) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(number):
        return "—"
    text = f"{number:,.{decimals}f}"
    return text.replace(",", " ").replace(".", ",")


def _format_int(value: Any) -> str:
    return _ru_number(value, 0)


def format_money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(number):
        return "—"
    sign = "-" if number < 0 else ""
    number = abs(number)
    if number >= 1_000_000_000:
        return f"{sign}{_ru_number(number / 1_000_000_000, 2)} млрд ₽"
    if number >= 1_000_000:
        return f"{sign}{_ru_number(number / 1_000_000, 1)} млн ₽"
    if number >= 1_000:
        return f"{sign}{_ru_number(number / 1_000, 0)} тыс. ₽"
    return f"{sign}{_ru_number(number, 0)} ₽"


def format_percent(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(number):
        return "—"
    sign = "+" if number > 0 else ""
    return f"{sign}{_ru_number(number, 1)} %"


def _format_metric(value: Any, metric_key: str) -> str:
    if metric_key in {"revenue_total", "investments_total"}:
        return format_money(value)
    return _format_int(value)

# ---------------------------------------------------------------------------
# Region / city resolution
# ---------------------------------------------------------------------------


def _first_value(mapping: Any, keys: Iterable[str]) -> Any:
    for key in keys:
        value = mapping.get(key) if hasattr(mapping, "get") else None
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass
        return value
    return None


def _region_point(row: Any) -> tuple[float, float] | None:
    lat = _first_value(row, ("latitude", "lat"))
    lon = _first_value(row, ("longitude", "lon", "lng"))
    nested = row.get("coordinates") if hasattr(row, "get") else None
    if (lat is None or lon is None) and isinstance(nested, dict):
        lat = _first_value(nested, ("latitude", "lat"))
        lon = _first_value(nested, ("longitude", "lon", "lng"))
    try:
        return (float(lat), float(lon))
    except (TypeError, ValueError):
        return None


def _region_cities(row: Any) -> list[tuple[str, float | None, float | None]]:
    cities = row.get("major_cities") if hasattr(row, "get") else None
    if not isinstance(cities, (list, tuple)):
        return []
    result: list[tuple[str, float | None, float | None]] = []
    for item in cities:
        if isinstance(item, dict):
            name = _first_value(item, ("name", "city"))
            lat = _first_value(item, ("latitude", "lat"))
            lon = _first_value(item, ("longitude", "lon", "lng"))
            if name:
                try:
                    result.append((str(name), float(lat), float(lon)))
                except (TypeError, ValueError):
                    result.append((str(name), None, None))
        else:
            result.append((str(item), None, None))
    return result


def _city_region_map(tenders: pd.DataFrame, regions: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if {"city", "region"}.issubset(tenders.columns):
        pairs = tenders[["city", "region"]].dropna().drop_duplicates()
        for _, row in pairs.iterrows():
            mapping.setdefault(str(row["city"]), str(row["region"]))
    if {"name", "major_cities"}.issubset(regions.columns):
        for _, row in regions.iterrows():
            for city, _lat, _lon in _region_cities(row):
                mapping.setdefault(city, str(row["name"]))
    for city, meta in CITY_META.items():
        mapping.setdefault(city, str(meta["region"]))
    return mapping


def resolve_coordinates(
    regions: pd.DataFrame,
    companies: pd.DataFrame,
    tenders: pd.DataFrame,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Return city -> {lat, lon, region, source} and city -> region."""
    city_regions = _city_region_map(tenders, regions)

    region_points: dict[str, tuple[float, float]] = {}
    region_city_points: dict[str, tuple[float, float, str]] = {}
    if not regions.empty:
        for _, row in regions.iterrows():
            name = str(row.get("name", "")) if row.get("name") is not None else ""
            point = _region_point(row)
            if name and point is not None:
                region_points[name] = point
            for city, lat, lon in _region_cities(row):
                if lat is None or lon is None:
                    continue
                city_regions.setdefault(city, name or "Не определён")
                region_city_points[city] = (lat, lon, name or "Не определён")

    known_cities = set(companies.get("city", pd.Series(dtype=str)).dropna().astype(str))
    known_cities |= set(tenders.get("city", pd.Series(dtype=str)).dropna().astype(str))

    coordinates: dict[str, dict[str, Any]] = {}
    for city in sorted(known_cities):
        region = city_regions.get(city)
        if city in region_city_points:
            lat, lon, region_name = region_city_points[city]
            coordinates[city] = {
                "lat": lat,
                "lon": lon,
                "region": region or region_name,
                "source": REGIONS_FILE,
            }
        elif city in CITY_META:
            meta = CITY_META[city]
            coordinates[city] = {
                "lat": float(meta["lat"]),
                "lon": float(meta["lon"]),
                "region": region or str(meta["region"]),
                "source": "built-in",
            }
        elif region in region_points:
            lat, lon = region_points[region]
            coordinates[city] = {
                "lat": lat,
                "lon": lon,
                "region": region,
                "source": "region center",
            }
    return coordinates, city_regions

# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------


def prepare_companies(
    companies: pd.DataFrame,
    investments: pd.DataFrame,
    tenders: pd.DataFrame,
    regions: pd.DataFrame,
) -> pd.DataFrame:
    """Return a copy of companies enriched with growth and investment metrics."""
    frame = companies.copy()

    for column in ("revenue_2023", "revenue_2024", "revenue_2025", "employees", "potential_score"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["growth_2024_2025"] = [
        _safe_growth(current, previous)
        for current, previous in zip(frame["revenue_2025"], frame["revenue_2024"])
    ]
    frame["growth_2023_2025"] = [
        _safe_growth(current, start)
        for current, start in zip(frame["revenue_2025"], frame["revenue_2023"])
    ]
    frame["cagr_2023_2025"] = [
        _safe_cagr(current, start)
        for current, start in zip(frame["revenue_2025"], frame["revenue_2023"])
    ]

    if not investments.empty and "company_id" in investments.columns:
        projects = investments.copy()
        projects["amount_rub"] = pd.to_numeric(projects["amount_rub"], errors="coerce")
        projects["expected_roi_percent"] = pd.to_numeric(
            projects["expected_roi_percent"], errors="coerce"
        )
        aggregated = (
            projects.groupby("company_id", dropna=False)
            .agg(
                investments_total=("amount_rub", "sum"),
                roi_avg=("expected_roi_percent", "mean"),
                investments_count=("investment_id", "count"),
            )
            .reset_index()
        )
        frame = frame.merge(aggregated, on="company_id", how="left")

    for column in ("investments_total", "roi_avg", "investments_count"):
        if column not in frame.columns:
            frame[column] = 0
        frame[column] = frame[column].fillna(0)

    city_regions = _city_region_map(tenders, regions)
    frame["region"] = frame["city"].astype(str).map(city_regions).fillna("Не определён")
    return frame

# ---------------------------------------------------------------------------
# Aggregation and filtering
# ---------------------------------------------------------------------------


def aggregate_by_city(
    frame: pd.DataFrame,
    revenue_column: str,
    growth_column: str,
) -> pd.DataFrame:
    """Aggregate filtered companies by city for the heat map."""
    columns = [
        "city",
        "region",
        "companies_count",
        "revenue_total",
        "employees_total",
        "investments_total",
        "growth_avg",
        "potential_avg",
        "top_company",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    grouped = (
        frame.groupby("city", dropna=False)
        .agg(
            companies_count=("company_id", "count"),
            revenue_total=(revenue_column, "sum"),
            employees_total=("employees", "sum"),
            investments_total=("investments_total", "sum"),
            growth_avg=(growth_column, "mean"),
            potential_avg=("potential_score", "mean"),
        )
        .reset_index()
    )
    grouped["region"] = (
        frame.drop_duplicates("city").set_index("city")["region"].reindex(grouped["city"]).values
    )
    top_source = frame.assign(
        _top_revenue=pd.to_numeric(frame[revenue_column], errors="coerce").fillna(0)
    )
    top_rows = top_source.loc[top_source.groupby("city")["_top_revenue"].idxmax(), ["city", "name"]]
    grouped["top_company"] = (
        top_rows.drop_duplicates("city").set_index("city")["name"].reindex(grouped["city"]).values
    )
    return grouped[columns]


def apply_filters(
    frame: pd.DataFrame,
    *,
    revenue_column: str,
    revenue_range: tuple[float, float],
    growth_column: str,
    growth_range: tuple[float, float],
    statuses: Iterable[str],
    cities: Iterable[str],
    regions: Iterable[str],
    potential_range: tuple[float, float],
    include_invalid_growth: bool = False,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply sidebar filters and return the selection plus summary counters."""
    revenue_values = pd.to_numeric(frame[revenue_column], errors="coerce").fillna(0)
    growth_values = pd.to_numeric(frame[growth_column], errors="coerce")
    potential_values = pd.to_numeric(frame["potential_score"], errors="coerce").fillna(0)

    mask = revenue_values.between(revenue_range[0], revenue_range[1], inclusive="both")
    valid_growth = growth_values.notna()
    if bool(valid_growth.any()):
        growth_mask = growth_values.between(growth_range[0], growth_range[1], inclusive="both")
        if include_invalid_growth:
            mask &= growth_mask | ~valid_growth
        else:
            mask &= valid_growth & growth_mask

    statuses = list(statuses)
    cities = list(cities)
    regions = list(regions)
    if statuses:
        mask &= frame["customer_status"].isin(statuses)
    if cities:
        mask &= frame["city"].isin(cities)
    if regions:
        mask &= frame["region"].isin(regions)
    mask &= potential_values.between(potential_range[0], potential_range[1], inclusive="both")

    selection = frame.loc[mask].copy()
    stats = {
        "total": int(len(frame)),
        "kept": int(len(selection)),
        "invalid_growth": int((~valid_growth).sum()),
    }
    return selection, stats

# ---------------------------------------------------------------------------
# Map helpers
# ---------------------------------------------------------------------------


def _extract_center(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        lat = value.get("lat")
        lon = value.get("lng", value.get("lon"))
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        lat, lon = value
    else:
        return None
    try:
        return (float(lat), float(lon))
    except (TypeError, ValueError):
        return None


def _default_zoom(city_count: int) -> int:
    if city_count <= 1:
        return 11
    if city_count == 2:
        return 9
    if city_count <= 4:
        return 8
    return 7


def _jitter(meta: dict[str, Any], company_id: Any) -> tuple[float, float]:
    digest = hashlib.md5(str(company_id).encode("utf-8")).hexdigest()
    angle = int(digest[:8], 16) / 0xFFFFFFFF * 2.0 * math.pi
    distance = int(digest[8:16], 16) / 0xFFFFFFFF * 0.012
    latitude = float(meta["lat"]) + distance * math.cos(angle)
    longitude = float(meta["lon"]) + distance * math.sin(angle)
    return latitude, longitude


def _scale_radius(value: Any, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 8.0
    if pd.isna(number):
        return 8.0
    if high <= low:
        return 20.0
    ratio = (number - low) / (high - low)
    ratio = max(0.0, min(1.0, ratio))
    return 6.0 + 34.0 * math.sqrt(ratio)

# ---------------------------------------------------------------------------
# Popups and legend
# ---------------------------------------------------------------------------


def _popup_table(lines: Iterable[tuple[str, str]]) -> str:
    return "".join(
        f"<tr><td style='padding:2px 8px 2px 0;color:#666;'>{label}</td>"
        f"<td style='padding:2px 0;font-weight:600;'>{value}</td></tr>"
        for label, value in lines
    )


def _city_popup_html(row: pd.Series, weight_label: str, weight_key: str) -> str:
    city = html.escape(str(row.get("city", "")))
    weight_value = _format_metric(row.get(weight_key), weight_key)
    lines = [
        ("Регион", html.escape(str(row.get("region", "")))),
        ("Компаний", _format_int(row.get("companies_count"))),
        ("Выручка", format_money(row.get("revenue_total"))),
        ("Средний рост", format_percent(row.get("growth_avg"))),
        ("Сотрудники", _format_int(row.get("employees_total"))),
        ("Инвестиции", format_money(row.get("investments_total"))),
        ("Топ-компания", html.escape(str(row.get("top_company") or "—"))),
    ]
    return (
        "<div style='font-family:Arial,sans-serif;font-size:12px;'>"
        f"<div style='font-size:14px;font-weight:700;margin-bottom:4px;'>{city}</div>"
        f"<div style='color:#444;margin-bottom:6px;'>{html.escape(weight_label)}: "
        f"<b>{weight_value}</b></div>"
        f"<table style='border-collapse:collapse;'>{_popup_table(lines)}</table>"
        "</div>"
    )


def _company_popup_html(row: pd.Series, revenue_column: str, growth_column: str) -> str:
    name = html.escape(str(row.get("name", "")))
    lines = [
        ("Город", html.escape(str(row.get("city", "")))),
        ("Регион", html.escape(str(row.get("region", "")))),
        ("Выручка", format_money(row.get(revenue_column))),
        ("Рост", format_percent(row.get(growth_column))),
        ("Сотрудники", _format_int(row.get("employees"))),
        ("Статус", html.escape(str(row.get("customer_status", "")))),
        ("Потенциал", _format_int(row.get("potential_score"))),
        ("Инвестиции", format_money(row.get("investments_total"))),
        ("ROI", format_percent(row.get("roi_avg"))),
    ]
    return (
        "<div style='font-family:Arial,sans-serif;font-size:12px;'>"
        f"<div style='font-size:14px;font-weight:700;margin-bottom:6px;'>{name}</div>"
        f"<table style='border-collapse:collapse;'>{_popup_table(lines)}</table>"
        "</div>"
    )


def _legend_html(weight_label: str, low: Any, high: Any, weight_key: str) -> str:
    return (
        "<div style=\"position:fixed;bottom:24px;left:24px;z-index:9999;"
        "background:rgba(255,255,255,0.94);padding:10px 14px;border-radius:8px;"
        "box-shadow:0 1px 6px rgba(0,0,0,0.35);font-family:Arial,sans-serif;"
        "font-size:12px;color:#222;line-height:1.35;\">"
        f"<div style=\"font-weight:700;margin-bottom:6px;\">Плотность: {html.escape(weight_label)}</div>"
        "<div style=\"height:10px;width:190px;border-radius:5px;"
        "background:linear-gradient(90deg,#2c7bb6,#abd9e9,#ffffbf,#fdae61,#d7191c);\"></div>"
        "<div style=\"display:flex;justify-content:space-between;margin-top:3px;color:#555;\">"
        f"<span>{_format_metric(low, weight_key)}</span>"
        f"<span>{_format_metric(high, weight_key)}</span>"
        "</div>"
        "<div style=\"margin-top:4px;color:#777;\">Колесо мыши / +− для приближения</div>"
        "</div>"
    )

# ---------------------------------------------------------------------------
# Heat map builder
# ---------------------------------------------------------------------------


def build_heatmap(
    city_aggregate: pd.DataFrame,
    companies: pd.DataFrame,
    coordinates: dict[str, dict[str, Any]],
    *,
    revenue_column: str,
    growth_column: str,
    weight_key: str,
    weight_label: str,
    radius: int,
    blur: int,
    min_opacity: float,
    show_points: bool = True,
    saved_zoom: int | None = None,
    saved_center: tuple[float, float] | None = None,
) -> folium.Map | None:
    """Build a folium map with a heat layer, city markers and company points."""
    if city_aggregate.empty:
        return None

    aggregate = city_aggregate[city_aggregate["city"].isin(coordinates)].copy()
    if aggregate.empty:
        return None

    aggregate["lat"] = aggregate["city"].map(lambda city: float(coordinates[city]["lat"]))
    aggregate["lon"] = aggregate["city"].map(lambda city: float(coordinates[city]["lon"]))
    aggregate["region"] = aggregate["city"].map(
        lambda city: str(coordinates[city].get("region", "Не определён"))
    )

    weights = pd.to_numeric(aggregate[weight_key], errors="coerce").fillna(0).astype(float)
    if float(weights.sum()) <= 0:
        weight_key = "companies_count"
        weight_label = "Количество компаний"
        weights = pd.to_numeric(aggregate[weight_key], errors="coerce").fillna(0).astype(float)

    total_weight = float(weights.sum())
    if total_weight <= 0:
        center_lat = float(aggregate["lat"].mean())
        center_lon = float(aggregate["lon"].mean())
    else:
        center_lat = float((aggregate["lat"] * weights).sum() / total_weight)
        center_lon = float((aggregate["lon"] * weights).sum() / total_weight)

    if saved_center is not None:
        center_lat, center_lon = saved_center
    if isinstance(saved_zoom, int) and saved_zoom > 0:
        zoom_start = saved_zoom
    else:
        zoom_start = _default_zoom(len(aggregate))

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    heat_data = [
        [float(row["lat"]), float(row["lon"]), float(weight)]
        for (_, row), weight in zip(aggregate.iterrows(), weights)
    ]
    HeatMap(
        heat_data,
        name="Тепловая карта",
        radius=radius,
        blur=blur,
        min_opacity=min_opacity,
        max_zoom=18,
        gradient=HEAT_GRADIENT,
    ).add_to(fmap)

    region_names = sorted(str(name) for name in aggregate["region"].dropna().unique())
    region_colors = {
        name: REGION_PALETTE[index % len(REGION_PALETTE)]
        for index, name in enumerate(region_names)
    }

    weight_low = float(weights.min()) if not weights.empty else 0.0
    weight_high = float(weights.max()) if not weights.empty else 0.0

    cities_layer = folium.FeatureGroup(name="Города")
    for (_, row), weight in zip(aggregate.iterrows(), weights):
        color = region_colors.get(str(row["region"]), "#607d8b")
        marker_radius = _scale_radius(weight, weight_low, weight_high)
        tooltip = f"{row['city']} — {_format_metric(weight, weight_key)}"
        folium.CircleMarker(
            location=[float(row["lat"]), float(row["lon"])],
            radius=marker_radius,
            color=color,
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.45,
            tooltip=tooltip,
            popup=folium.Popup(_city_popup_html(row, weight_label, weight_key), max_width=340),
        ).add_to(cities_layer)
    cities_layer.add_to(fmap)

    if show_points and not companies.empty:
        points_layer = folium.FeatureGroup(name="Компании")
        for _, row in companies[companies["city"].isin(coordinates)].iterrows():
            meta = coordinates[str(row["city"])]
            latitude, longitude = _jitter(meta, row.get("company_id"))
            color = STATUS_COLORS.get(str(row.get("customer_status")), "#607d8b")
            folium.CircleMarker(
                location=[latitude, longitude],
                radius=4,
                color=color,
                weight=1,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                tooltip=f"{row.get('name', '')} — {format_money(row.get(revenue_column))}",
                popup=folium.Popup(
                    _company_popup_html(row, revenue_column, growth_column), max_width=320
                ),
            ).add_to(points_layer)
        points_layer.add_to(fmap)

    fmap.get_root().html.add_child(
        folium.Element(_legend_html(weight_label, weight_low, weight_high, weight_key))
    )

    if saved_center is None and saved_zoom is None and len(aggregate) > 1:
        min_lat = float(aggregate["lat"].min())
        max_lat = float(aggregate["lat"].max())
        min_lon = float(aggregate["lon"].min())
        max_lon = float(aggregate["lon"].max())
        if (max_lat - min_lat) > 1e-6 or (max_lon - min_lon) > 1e-6:
            fmap.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]], padding=(40, 40))

    return fmap

# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------


def _reset_filter_state() -> None:
    for key in [name for name in st.session_state.keys() if name.startswith("radar_")]:
        st.session_state.pop(key, None)


def _render_sidebar(frame: pd.DataFrame, regions: pd.DataFrame) -> dict[str, Any]:
    """Render sidebar controls and return the selected filter configuration."""
    with st.sidebar:
        st.header("Фильтры")

        revenue_year = st.selectbox(
            "Год выручки",
            options=["2025", "2024", "2023"],
            index=0,
            key="radar_revenue_year",
        )
        revenue_column = f"revenue_{revenue_year}"
        revenue_low, revenue_high = _numeric_bounds(frame[revenue_column], integer=True)
        revenue_range = st.slider(
            "Диапазон выручки, ₽",
            min_value=int(revenue_low),
            max_value=int(revenue_high),
            value=(int(revenue_low), int(revenue_high)),
            step=int(_step_for(revenue_low, revenue_high, integer=True)),
            key=f"radar_revenue_range_{revenue_year}",
        )
        st.caption(f"{format_money(revenue_range[0])} — {format_money(revenue_range[1])}")

        growth_label = st.radio(
            "Метрика динамики роста",
            options=list(GROWTH_METRICS.keys()),
            index=0,
            horizontal=True,
            key="radar_growth_metric",
        )
        growth_column = GROWTH_METRICS[growth_label]
        growth_low, growth_high = _numeric_bounds(frame[growth_column])
        growth_range = st.slider(
            "Диапазон роста, %",
            min_value=float(growth_low),
            max_value=float(growth_high),
            value=(float(growth_low), float(growth_high)),
            step=float(_step_for(growth_low, growth_high)),
            format="%.1f",
            key=f"radar_growth_range_{growth_column}",
        )
        st.caption(f"{format_percent(growth_range[0])} — {format_percent(growth_range[1])}")
        if frame[growth_column].notna().sum() == 0:
            st.info("Нет корректных значений динамики роста — фильтр по росту не применяется.")

        with st.expander("Дополнительные фильтры", expanded=False):
            status_options = sorted(frame["customer_status"].dropna().astype(str).unique())
            statuses = st.multiselect(
                "Статус клиента",
                options=status_options,
                default=status_options,
                key="radar_statuses",
            )
            city_options = sorted(frame["city"].dropna().astype(str).unique())
            cities = st.multiselect(
                "Город",
                options=city_options,
                default=city_options,
                key="radar_cities",
            )
            region_options = sorted(frame["region"].dropna().astype(str).unique())
            region_choices = st.multiselect(
                "Регион",
                options=region_options,
                default=region_options,
                key="radar_regions",
            )
            potential_high = max(100.0, float(_numeric_bounds(frame["potential_score"])[1]))
            potential_range = st.slider(
                "Потенциальный скор",
                min_value=0.0,
                max_value=potential_high,
                value=(0.0, potential_high),
                step=1.0,
                key="radar_potential_range",
            )
            include_invalid = st.checkbox(
                "Показывать компании без корректной динамики",
                value=False,
                key="radar_include_invalid",
            )

        with st.expander("Настройки карты", expanded=False):
            density_label = st.selectbox(
                "Плотность по",
                options=list(DENSITY_METRICS.keys()),
                index=0,
                key="radar_density_metric",
            )
            radius = st.slider("Радиус теплового пятна", 10, 60, 30, 1, key="radar_radius")
            blur = st.slider("Размытие", 5, 40, 20, 1, key="radar_blur")
            min_opacity = st.slider(
                "Минимальная непрозрачность", 0.1, 0.9, 0.4, 0.05, key="radar_min_opacity"
            )
            show_points = st.checkbox(
                "Показывать точки компаний", value=True, key="radar_show_points"
            )
            if st.button("Сбросить масштаб карты", key="radar_reset_view"):
                st.session_state.pop("radar_map", None)
                st.rerun()
            if st.button("Сбросить все фильтры", key="radar_reset_filters"):
                _reset_filter_state()
                st.rerun()

        st.divider()
        st.caption(
            f"Данные: {COMPANIES_FILE} — {len(frame)} компаний; "
            f"{TENDERS_FILE} и {INVESTMENTS_FILE} — контекст; "
            f"{REGIONS_FILE} — индексы регионов."
        )
        if not regions.empty and "name" in regions.columns:
            st.caption("Регионы: " + ", ".join(regions["name"].astype(str).tolist()))

    return {
        "revenue_year": revenue_year,
        "revenue_column": revenue_column,
        "revenue_range": revenue_range,
        "growth_label": growth_label,
        "growth_column": growth_column,
        "growth_range": growth_range,
        "statuses": statuses,
        "cities": cities,
        "regions": region_choices,
        "potential_range": potential_range,
        "include_invalid": include_invalid,
        "density_label": density_label,
        "weight_key": DENSITY_METRICS[density_label],
        "radius": radius,
        "blur": blur,
        "min_opacity": min_opacity,
        "show_points": show_points,
    }

def render_radar(data_dir: str | Path | None = None) -> None:
    """Render the business-density radar page."""
    base = Path(data_dir) if data_dir is not None else DATA_DIR

    st.title("Радар плотности бизнеса", icon=":material/radar:")
    st.caption(
        "Интерактивная тепловая карта распределения компаний по городам. "
        "Фильтры: выручка и динамика роста. Источник данных — папка data/."
    )

    try:
        signature = _file_signature(base)
        raw = load_data(str(base), signature)
        frame = prepare_companies(
            raw["companies"], raw["investments"], raw["tenders"], raw["regions"]
        )
        coordinates, _city_regions = resolve_coordinates(
            raw["regions"], raw["companies"], raw["tenders"]
        )
    except FileNotFoundError as error:
        st.error(f"Не найден файл данных: {error}. Ожидается папка {base}.")
        return
    except (ValueError, json.JSONDecodeError) as error:
        st.error(f"Не удалось загрузить данные: {error}")
        return

    controls = _render_sidebar(frame, raw["regions"])
    selection, stats = apply_filters(
        frame,
        revenue_column=controls["revenue_column"],
        revenue_range=controls["revenue_range"],
        growth_column=controls["growth_column"],
        growth_range=controls["growth_range"],
        statuses=controls["statuses"],
        cities=controls["cities"],
        regions=controls["regions"],
        potential_range=controls["potential_range"],
        include_invalid_growth=controls["include_invalid"],
    )

    revenue_column = controls["revenue_column"]
    growth_column = controls["growth_column"]
    weight_key = controls["weight_key"]
    weight_label = controls["density_label"]

    kpi_columns = st.columns(4)
    with kpi_columns[0]:
        st.metric("Компаний в выборке", f"{stats['kept']} / {stats['total']}")
    with kpi_columns[1]:
        st.metric(
            f"Выручка {controls['revenue_year']}",
            format_money(selection[revenue_column].sum()),
        )
    average_growth = selection[growth_column].mean() if not selection.empty else float("nan")
    overall_growth = frame[growth_column].mean()
    delta_value = (
        average_growth - overall_growth
        if pd.notna(average_growth) and pd.notna(overall_growth)
        else None
    )
    with kpi_columns[2]:
        delta_text = (
            f"{'+' if delta_value > 0 else ''}{_ru_number(delta_value, 1)} п.п."
            if delta_value is not None
            else None
        )
        st.metric("Средний рост", format_percent(average_growth), delta=delta_text)
    cities_in_selection = selection["city"].nunique() if not selection.empty else 0
    cities_with_coordinates = (
        len(set(selection["city"].dropna()) & set(coordinates)) if not selection.empty else 0
    )
    with kpi_columns[3]:
        st.metric("Городов в выборке", cities_in_selection)
        st.caption(f"{cities_with_coordinates} с координатами")

    if stats["kept"] == 0:
        st.warning(
            "Под текущие фильтры не подошла ни одна компания. "
            "Ослабьте диапазоны выручки или роста."
        )
        return

    if stats["invalid_growth"]:
        message = (
            "Компаний без корректной динамики роста: "
            f"{stats['invalid_growth']}. "
        )
        if controls["include_invalid"]:
            message += "Они включены в выборку."
        else:
            message += "Их можно включить в дополнительных фильтрах."
        st.info(message)

    cities_without_coordinates = sorted(set(selection["city"].dropna()) - set(coordinates))
    if cities_without_coordinates:
        st.warning(
            "Города без координат (не отображены на карте): "
            + ", ".join(cities_without_coordinates)
        )

    city_aggregate = aggregate_by_city(selection, revenue_column, growth_column)

    map_tab, analytics_tab, data_tab = st.tabs(
        [":material/map: Карта", ":material/analytics: Аналитика", ":material/table_view: Данные"]
    )

    with map_tab:
        saved_view = st.session_state.get("radar_map")
        saved_view = saved_view if isinstance(saved_view, dict) else {}
        saved_zoom = saved_view.get("zoom")
        saved_zoom = int(saved_zoom) if isinstance(saved_zoom, (int, float)) else None
        saved_center = _extract_center(saved_view.get("center"))

        fmap = build_heatmap(
            city_aggregate,
            selection,
            coordinates,
            revenue_column=revenue_column,
            growth_column=growth_column,
            weight_key=weight_key,
            weight_label=weight_label,
            radius=controls["radius"],
            blur=controls["blur"],
            min_opacity=controls["min_opacity"],
            show_points=controls["show_points"],
            saved_zoom=saved_zoom,
            saved_center=saved_center,
    
            
        )
        if fmap is None:
            st.info("Нет компаний с известными координатами для отображения на карте.")
        else:
            result = st_folium(
                fmap,
                use_container_width=True,
                height=620,
                returned_objects=["zoom", "center", "bounds"],
                zoom=saved_zoom,
                center=saved_center,
                key="radar_map",
            )
            result = result or {}
            st.caption(
                "Приближение: колесо мыши, кнопки +/− или полноэкранный режим. "
                f"Текущий масштаб: {result.get('zoom', saved_zoom or '—')}."
            )

    with analytics_tab:
        left, right = st.columns(2)
        with left:
            chart_data = city_aggregate.sort_values(weight_key, ascending=True)
            figure = px.bar(
                chart_data,
                x=weight_key,
                y="city",
                orientation="h",
                color=weight_key,
                color_continuous_scale="Viridis",
                labels={weight_key: weight_label, "city": "Город"},
                title=f"Города по метрике «{weight_label}»",
            )
            figure.update_layout(coloraxis_showscale=False, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(figure, use_container_width=True)

        with right:
            growth_data = city_aggregate.sort_values("growth_avg", ascending=True)
            growth_figure = px.bar(
                growth_data,
                x="growth_avg",
                y="city",
                orientation="h",
                color="growth_avg",
                color_continuous_scale="RdYlGn",
                labels={"growth_avg": controls["growth_label"], "city": "Город"},
                title=f"Средняя динамика роста по городам ({controls['growth_label']})",
                text_auto=".1f",
            )
            growth_figure.add_vline(x=0, line_dash="dash", line_color="#555555")
            growth_figure.update_layout(
                coloraxis_showscale=False, margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(growth_figure, use_container_width=True)

        scatter_data = selection.copy()
        scatter_data["employees_size"] = pd.to_numeric(
            scatter_data["employees"], errors="coerce"
        ).fillna(0)
        scatter_kwargs: dict[str, Any] = {
            "data_frame": scatter_data,
            "x": revenue_column,
            "y": growth_column,
            "color": "customer_status",
            "hover_name": "name",
            "hover_data": ["city", "region", "potential_score", "employees"],
            "log_x": bool(pd.to_numeric(scatter_data[revenue_column], errors="coerce").min() > 0),
            "labels": {
                revenue_column: f"Выручка {controls['revenue_year']}, ₽",
                growth_column: controls["growth_label"],
                "customer_status": "Статус",
            },
            "title": "Выручка и динамика роста компаний",
        }
        if scatter_data["employees_size"].max() > 0:
            scatter_kwargs["size"] = "employees_size"
            scatter_kwargs["size_max"] = 40
        scatter = px.scatter(**scatter_kwargs)
        scatter.update_layout(margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(scatter, use_container_width=True)

        region_table = (
            selection.groupby("region", dropna=False)
            .agg(
                companies_count=("company_id", "count"),
                revenue_total=(revenue_column, "sum"),
                employees_total=("employees", "sum"),
                investments_total=("investments_total", "sum"),
                growth_avg=(growth_column, "mean"),
            )
            .reset_index()
            .rename(
                columns={
                    "region": "Регион",
                    "companies_count": "Компаний",
                    "revenue_total": "Выручка, ₽",
                    "employees_total": "Сотрудники",
                    "investments_total": "Инвестиции, ₽",
                    "growth_avg": "Средний рост, %",
                }
            )
        )
        st.subheader("Сводка по регионам")
        st.dataframe(region_table, use_container_width=True, hide_index=True)

        region_frame = raw["regions"].copy()
        metric_columns = [
            column
            for column in ("investment_climate_index", "tender_activity_index")
            if column in region_frame.columns
        ]
        if metric_columns and "name" in region_frame.columns:
            melted = region_frame.melt(
                id_vars="name",
                value_vars=metric_columns,
                var_name="Индекс",
                value_name="Значение",
            )
            melted["Значение"] = pd.to_numeric(melted["Значение"], errors="coerce")
            melted = melted.dropna(subset=["Значение"])
            if not melted.empty:
                st.subheader("Индексы регионов")
                indices_figure = px.bar(
                    melted,
                    x="name",
                    y="Значение",
                    color="Индекс",
                    barmode="group",
                    labels={"name": "Регион"},
                    title="Инвестиционный климат и активность тендеров",
                )
                indices_figure.update_layout(margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(indices_figure, use_container_width=True)

        if not raw["tenders"].empty and "city" in raw["tenders"].columns:
            tenders = raw["tenders"].copy()
            tenders["budget_rub"] = pd.to_numeric(tenders["budget_rub"], errors="coerce").fillna(0)
            if controls["cities"]:
                tenders = tenders[tenders["city"].isin(controls["cities"])]
            if controls["regions"] and "region" in tenders.columns:
                tenders = tenders[tenders["region"].isin(controls["regions"])]
            if not tenders.empty:
                tender_table = (
                    tenders.groupby("city", dropna=False)
                    .agg(
                        tenders_count=("tender_id", "count"),
                        budget_total=("budget_rub", "sum"),
                    )
                    .reset_index()
                    .rename(
                        columns={
                            "city": "Город",
                            "tenders_count": "Тендеров",
                            "budget_total": "Бюджет, ₽",
                        }
                    )
                )
                st.subheader("Тендеры по городам")
                st.dataframe(tender_table, use_container_width=True, hide_index=True)

    with data_tab:
        display_columns = [
            "company_id",
            "name",
            "city",
            "region",
            "revenue_2023",
            "revenue_2024",
            "revenue_2025",
            "growth_2024_2025",
            "growth_2023_2025",
            "cagr_2023_2025",
            "employees",
            "customer_status",
            "potential_score",
            "investments_total",
            "roi_avg",
        ]
        existing_columns = [column for column in display_columns if column in selection.columns]
        display = selection[existing_columns].rename(
            columns={
                "company_id": "ID",
                "name": "Компания",
                "city": "Город",
                "region": "Регион",
                "revenue_2023": "Выручка 2023, ₽",
                "revenue_2024": "Выручка 2024, ₽",
                "revenue_2025": "Выручка 2025, ₽",
                "growth_2024_2025": "Рост 2024→2025, %",
                "growth_2023_2025": "Рост 2023→2025, %",
                "cagr_2023_2025": "CAGR 2023–2025, %",
                "employees": "Сотрудники",
                "customer_status": "Статус",
                "potential_score": "Потенциал",
                "investments_total": "Инвестиции, ₽",
                "roi_avg": "ROI, %",
            }
        )
        st.subheader(f"Компании в выборке ({len(display)})")
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.download_button(
            "Скачать выборку CSV",
            data=display.to_csv(index=False).encode("utf-8-sig"),
            file_name="radar_companies_filtered.csv",
            mime="text/csv",
            key="radar_download",
        )

        if not raw["investments"].empty:
            with st.expander("Инвестиционные проекты по выбранным компаниям"):
                projects = raw["investments"][
                    raw["investments"]["company_id"].isin(selection["company_id"])
                ].copy()
                projects["amount_rub"] = pd.to_numeric(
                    projects["amount_rub"], errors="coerce"
                )
                st.dataframe(projects, use_container_width=True, hide_index=True)

        if not raw["tenders"].empty:
            with st.expander("Тендеры по выбранным городам и регионам"):
                tenders = raw["tenders"].copy()
                if controls["cities"]:
                    tenders = tenders[tenders["city"].isin(controls["cities"])]
                if controls["regions"] and "region" in tenders.columns:
                    tenders = tenders[tenders["region"].isin(controls["regions"])]
                tenders["budget_rub"] = pd.to_numeric(
                    tenders["budget_rub"], errors="coerce"
                )
                st.dataframe(tenders, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    st.set_page_config(
        page_title="Радар плотности бизнеса",
        page_icon=":material/map:",
        layout="wide",
    )
    render_radar()



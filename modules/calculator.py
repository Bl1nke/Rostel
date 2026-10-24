"""Модуль «Калькулятор сделок» — вычислительная логика и Streamlit-интерфейс.

Публичные функции:
    calculate(project_params: dict) -> dict — расчёт стоимости и маржинальности.
    load_regions(path: str) -> dict — загрузка региональных коэффициентов.
    render_calculator() -> None — Streamlit-интерфейс (ленивый импорт Streamlit).

Ядро (``calculate``, ``load_regions``) не зависит от Streamlit:
``streamlit`` и ``plotly`` импортируются только внутри функций рендера.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# ============================================================================
# Константы
# ============================================================================

DEFAULT_REGIONS_FILE = "data/region.json"
REGION_CLIMATE_KEY = "investment_climate_index"

BASE_RATES: dict[str, float] = {
    "Завод": 25000.0,
    "Производство": 20000.0,
    "Бизнес-центр": 18000.0,
    "Торговый центр": 19000.0,
    "Офис": 15000.0,
    "Гостиница": 22000.0,
    "Ресторан": 16000.0,
    "Магазин": 8000.0,
    "Склад": 12000.0,
    "Логистический хаб": 11500.0,
    "Дата-центр": 45000.0,
    "Лаборатория": 28000.0,
    "Школа": 9000.0,
    "Детский сад": 10000.0,
    "Университет": 17000.0,
    "Больница": 14000.0,
    "Поликлиника": 15500.0,
    "Стадион": 35000.0,
    "Аэропорт": 40000.0,
    "Вокзал": 30000.0,
    "Автосалон": 13500.0,
    "Гараж": 5000.0,
}

FINANCING_COEFFICIENTS: dict[str, float] = {
    "Бюджетное": 0.9,
    "Частное": 1.0,
    "Государственно-частное партнёрство": 1.15,
}

WORK_TYPES_COEFFICIENTS: dict[str, float] = {
    "ИТ-инфраструктура": 1.3,
    "АСУ ТП": 1.2,
    "Физическая безопасность": 1.15,
    "Информационная безопасность": 1.25,
    "Облачные решения": 1.1,
    "Кибербезопасность": 1.3,
    "Автоматизация": 1.18,
    "СКС": 1.22,
    "СКУД": 1.18,
    "Видеонаблюдение": 1.14,
    "Пожаротушение и ОПС": 1.2,
    "Умный дом / BMS": 1.28,
    "Видеоконференцсвязь": 1.12,
    "Контакт-центр": 1.15,
    "Интеграция с 1С/ERP": 1.22,
    "BI и аналитика": 1.25,
    "Мобильная разработка": 1.3,
    "Веб-разработка": 1.2,
}

_TARGET_MARGIN_BY_WORK: dict[str | None, float] = {
    None: 0.225,
    "ИТ-инфраструктура": 0.215,
    "Кибербезопасность": 0.215,
    "АСУ ТП": 0.22,
    "Информационная безопасность": 0.22,
    "СКС": 0.22,
    "Интеграция с 1С/ERP": 0.22,
    "Мобильная разработка": 0.215,
    "Физическая безопасность": 0.23,
    "Автоматизация": 0.23,
    "Пожаротушение и ОПС": 0.23,
    "СКУД": 0.23,
    "Контакт-центр": 0.23,
    "Веб-разработка": 0.23,
    "Видеонаблюдение": 0.235,
    "Видеоконференцсвязь": 0.235,
    "Умный дом / BMS": 0.225,
    "BI и аналитика": 0.225,
    "Облачные решения": 0.24,
}
_TARGET_MARGIN_MIN = 0.20
_TARGET_MARGIN_MAX = 0.25

_WORK_TO_TENDER_CATEGORIES: dict[str, tuple[str, ...]] = {
    "ИТ-инфраструктура": ("IT Infrastructure", "Cloud Services", "Data Analytics"),
    "АСУ ТП": ("Enterprise Software", "Software Development"),
    "Физическая безопасность": ("IT Security",),
    "Информационная безопасность": ("IT Security",),
    "Облачные решения": ("Cloud Services",),
    "Кибербезопасность": ("IT Security",),
    "Автоматизация": ("Enterprise Software", "Software Development"),
    "СКС": ("IT Infrastructure",),
    "СКУД": ("IT Security",),
    "Видеонаблюдение": ("IT Security",),
    "Пожаротушение и ОПС": (),
    "Умный дом / BMS": ("Smart City",),
    "Видеоконференцсвязь": ("IT Infrastructure",),
    "Контакт-центр": ("Software Development",),
    "Интеграция с 1С/ERP": ("Enterprise Software",),
    "BI и аналитика": ("Data Analytics",),
    "Мобильная разработка": ("Mobile Development",),
    "Веб-разработка": ("Software Development",),
}

EQUIPMENT_TYPES: dict[str, str] = {
    "Типовое": "standard",
    "Нестандартное": "custom",
}

_FINANCING_ALIASES: dict[str, str] = {
    "бюджетная": "Бюджетное", "бюджетное": "Бюджетное", "budget": "Бюджетное",
    "частная": "Частное", "частное": "Частное", "private": "Частное",
    "государственно-частное партнёрство": "Государственно-частное партнёрство",
    "государственно-частное-партнёрство": "Государственно-частное партнёрство",
    "гчп": "Государственно-частное партнёрство",
    "gcp": "Государственно-частное партнёрство",
    "ppp": "Государственно-частное партнёрство",
}

_WORK_TYPE_ALIASES: dict[str, str] = {
    "ит-инфраструктура": "ИТ-инфраструктура",
    "it-инфраструктура": "ИТ-инфраструктура",
    "it-infrastructure": "ИТ-инфраструктура",
    "асу тп": "АСУ ТП", "асу-тп": "АСУ ТП", "asu-tp": "АСУ ТП",
    "физическая безопасность": "Физическая безопасность",
    "физическая-безопасность": "Физическая безопасность",
    "physical-security": "Физическая безопасность",
    "информационная безопасность": "Информационная безопасность",
    "информационная-безопасность": "Информационная безопасность",
    "information-security": "Информационная безопасность",
    "облачные решения": "Облачные решения",
    "облачные-решения": "Облачные решения", "cloud": "Облачные решения",
    "кибербезопасность": "Кибербезопасность", "cybersecurity": "Кибербезопасность",
    "автоматизация": "Автоматизация", "automation": "Автоматизация",
    "скс": "СКС", "sks": "СКС",
    "скуд": "СКУД", "skud": "СКУД",
    "видеонаблюдение": "Видеонаблюдение",
    "пожаротушение и опс": "Пожаротушение и ОПС",
    "умный дом / bms": "Умный дом / BMS",
    "видеоконференцсвязь": "Видеоконференцсвязь", "вкс": "Видеоконференцсвязь",
    "контакт-центр": "Контакт-центр",
    "интеграция с 1с/erp": "Интеграция с 1С/ERP",
    "bi и аналитика": "BI и аналитика",
    "мобильная разработка": "Мобильная разработка",
    "веб-разработка": "Веб-разработка",
}

_EQUIPMENT_ALIASES: dict[str, str] = {
    "типовое": "Типовое", "standard": "Типовое",
    "нестандартное": "Нестандартное", "custom": "Нестандартное",
}

_URGENCY_ALIASES: dict[str, tuple[float, str]] = {
    "нормальная": (1.0, "Нормальная"), "normal": (1.0, "Нормальная"),
    "standard": (1.0, "Нормальная"),
    "urgency-high": (1.25, "Высокая"), "high": (1.25, "Высокая"),
    "высокая": (1.25, "Высокая"),
    "urgency-critical": (1.5, "Критическая"), "critical": (1.5, "Критическая"),
    "критическая": (1.5, "Критическая"),
}

_DEADLINE_BUCKETS: tuple[tuple[int, float, str], ...] = (
    (7, 1.5, "Критическая"),
    (14, 1.35, "Очень высокая"),
    (30, 1.25, "Высокая"),
    (60, 1.1, "Повышенная"),
    (90, 1.0, "Стандартная"),
    (180, 0.95, "Спокойная"),
    (365, 0.9, "Долгосрочная"),
)
_LONG_TERM_COEFFICIENT = 0.9
_LONG_TERM_LABEL = "Долгосрочная"

DEFAULT_URGENCY = "нормальная"
DEFAULT_FINANCING = "Частное"
DEFAULT_WORK_TYPE: str | None = None
DEFAULT_EQUIPMENT = "Типовое"

_ANALOGS_FILE = "investmensts.csv"
_TENDERS_FILE = "tenders.csv"
_ANALOG_LOW_FACTOR = 0.5
_ANALOG_HIGH_FACTOR = 2.0

_REGION_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "Rostov Oblast": ("Rostov Oblast", "Ростовская область", "Ростовская обл."),
    "Krasnodar Krai": ("Krasnodar Krai", "Краснодарский край", "Краснодарский кр."),
}

_RT_ORANGE = "#FF4F12"
_RT_BLUE = "#4A90D9"
_RT_PURPLE = "#7A2E8E"
_RT_NAVY = "#1B1B2F"
_RT_MUTED = "#6B6B80"
_RT_BORDER = "#ECE8F5"


# ============================================================================
# Публичная функция расчёта
# ============================================================================

def calculate(project_params: dict[str, Any]) -> dict[str, Any]:
    """Выполняет расчёт стоимости проекта и возвращает результат.

    Raises:
        ValueError — некорректные параметры, неизвестный регион, прошедший
        дедлайн.
    """
    object_type_raw = project_params.get("object_type")
    if not object_type_raw:
        raise ValueError("Параметр 'object_type' обязателен.")

    area_sqm = project_params.get("area_sqm")
    if area_sqm is None:
        raise ValueError("Параметр 'area_sqm' обязателен (площадь проекта).")
    if not isinstance(area_sqm, (int, float)) or isinstance(area_sqm, bool) or area_sqm <= 0:
        raise ValueError(f"Некорректная площадь: {area_sqm}. Должна быть > 0.")

    region_id = project_params.get("region_id")
    if not region_id:
        raise ValueError("Параметр 'region_id' обязателен (регион из data/region.json).")

    object_type = _normalize_object_type(object_type_raw)
    base_rate = BASE_RATES[object_type]

    financing = _normalize_financing(project_params.get("financing", DEFAULT_FINANCING))
    work_type = _normalize_work_type(project_params.get("work_type", DEFAULT_WORK_TYPE))
    equipment = _normalize_equipment(project_params.get("equipment", DEFAULT_EQUIPMENT))
    unique_solution_flag = bool(project_params.get("unique_solution", False))

    deadline_iso = project_params.get("deadline_date")
    if deadline_iso:
        urgency_coeff, urgency_label = _urgency_from_deadline(str(deadline_iso))
        deadline_display: str | None = str(deadline_iso).strip()
    else:
        urgency_coeff, urgency_label = _resolve_legacy_urgency(
            project_params.get("urgency", DEFAULT_URGENCY)
        )
        deadline_display = None

    region_data = load_regions()
    region_coeff = _get_region_coefficient(str(region_id), region_data)
    if region_coeff is None or region_coeff <= 0:
        raise ValueError(
            f"Регион {region_id!r} не найден или не содержит корректного "
            f"'{REGION_CLIMATE_KEY}'."
        )

    financing_coeff = FINANCING_COEFFICIENTS[financing]
    work_coeff = WORK_TYPES_COEFFICIENTS[work_type] if work_type else 1.0
    equipment_coeff = 1.15 if EQUIPMENT_TYPES[equipment] == "custom" else 1.0
    unique_coeff = 1.1 if unique_solution_flag else 1.0

    base_cost = base_rate * float(area_sqm)
    optimal_price = (
        base_cost
        * region_coeff
        * urgency_coeff
        * financing_coeff
        * work_coeff
        * equipment_coeff
        * unique_coeff
    )
    if optimal_price <= 0:
        raise ValueError("Итоговая стоимость должна быть положительной.")

    min_price = optimal_price * 0.9
    max_price = optimal_price * 1.1

    # Конкуренция: полный список открытых тендеров в регионе по категориям.
    open_tenders = _load_open_tenders(
        region_id=str(region_id), region_data=region_data, work_type=work_type
    )
    competition_open_tenders = len(open_tenders) if open_tenders is not None else None
    competition_tenders = (
        open_tenders[:5] if open_tenders else ([] if open_tenders is not None else None)
    )

    base_margin = _TARGET_MARGIN_BY_WORK.get(work_type, _TARGET_MARGIN_BY_WORK[None])
    competition_adj = _competition_margin_adjustment(competition_open_tenders)
    target_margin = min(
        max(base_margin + competition_adj, _TARGET_MARGIN_MIN),
        _TARGET_MARGIN_MAX,
    )

    cost_of_goods_sold = optimal_price * (1.0 - target_margin)
    profit = optimal_price - cost_of_goods_sold
    margin_percent = target_margin * 100.0

    analog_count, analog_data = _load_analogs_for_comparison(
        region_id=str(region_id),
        region_data=region_data,
        optimal_price=optimal_price,
        min_price=min_price,
        max_price=max_price,
    )

    chart_data = _prepare_chart_data(
        optimal_price=optimal_price,
        min_price=min_price,
        max_price=max_price,
        cost_of_goods_sold=cost_of_goods_sold,
        analog_data=analog_data,
    )

    region_name = _get_region_name(str(region_id), region_data)

    business_insight = _generate_business_insight(
        optimal_price=optimal_price,
        min_price=min_price,
        max_price=max_price,
        margin_percent=margin_percent,
        base_rate=base_rate,
        object_type=object_type,
        analog_count=analog_count,
        analog_data=analog_data,
        competition_open_tenders=competition_open_tenders,
        competition_adj=competition_adj,
    )

    params_for_result: dict[str, Any] = {
        "object_type": object_type,
        "area_sqm": float(area_sqm),
        "region_id": str(region_id),
        "deadline_date": deadline_display,
        "urgency": urgency_label,
        "urgency_coefficient": urgency_coeff,
        "financing": financing,
        "work_type": work_type,
        "equipment": equipment,
        "unique_solution": unique_solution_flag,
    }

    return {
        "optimal_price": optimal_price,
        "min_price": min_price,
        "max_price": max_price,
        "cost_of_goods_sold": round(cost_of_goods_sold, 2),
        "margin_percent": round(margin_percent, 1),
        "target_margin_percent": round(target_margin * 100.0, 1),
        "base_margin_percent": round(base_margin * 100.0, 1),
        "competition_open_tenders": competition_open_tenders,
        "competition_tenders": competition_tenders,
        "competition_margin_adjustment_pp": round(competition_adj * 100.0, 1),
        "profit": round(profit, 2),
        "base_rate_per_sqm": base_rate,
        "region_coefficient": round(region_coeff, 2),
        "region_name": region_name,
        "urgency_coefficient": urgency_coeff,
        "urgency_label": urgency_label,
        "project_params": params_for_result,
        "analog_count": analog_count,
        "analog_data": analog_data if analog_data else None,
        "chart_data": chart_data,
        "business_insight": business_insight,
    }


def load_regions(path: str = DEFAULT_REGIONS_FILE) -> dict[str, Any]:
    """Загружает региональные коэффициенты из JSON."""
    import json

    try:
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = Path(__file__).resolve().parents[1] / path
        with file_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError):
        return {}

    if isinstance(data, list):
        return {
            item["region_id"]: item
            for item in data
            if isinstance(item, dict) and "region_id" in item
        }
    return {}


# ============================================================================
# Конкуренция: открытые тендеры
# ============================================================================

def _load_open_tenders(
    region_id: str,
    region_data: dict[str, Any],
    work_type: str | None,
) -> list[dict[str, Any]] | None:
    """Возвращает открытые тендеры в регионе по релевантным категориям.

    None — файл недоступен/повреждён, [] — совпадений нет.
    """
    file_path = _resolve_data_path(_TENDERS_FILE)
    if file_path is None:
        return None

    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error):
        return None

    if not rows:
        return None

    if not {"status", "region", "category"}.issubset(rows[0].keys()):
        return None

    region_name = region_data.get(region_id, {}).get("name", "") if region_data else ""
    region_aliases = {alias.casefold() for alias in _get_region_aliases(region_name)}

    categories = _WORK_TO_TENDER_CATEGORIES.get(work_type) if work_type else ()
    categories_lower = {c.lower() for c in (categories or ())}

    tenders: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("status", "")).strip().lower() != "open":
            continue
        row_region = str(row.get("region", "")).strip().casefold()
        if region_aliases and row_region not in region_aliases:
            continue
        if categories_lower:
            row_cat = str(row.get("category", "")).strip().lower()
            if row_cat not in categories_lower:
                continue
        tenders.append({
            "tender_id": row.get("tender_id"),
            "title": row.get("title"),
            "customer": row.get("customer"),
            "category": row.get("category"),
            "budget_rub": _safe_float(row.get("budget_rub")),
            "deadline": row.get("deadline"),
        })

    # Ближайшие по дедлайну — сверху; при равенстве — крупные по бюджету.
    tenders.sort(
        key=lambda t: (
            str(t.get("deadline") or "9999-12-31"),
            -(t.get("budget_rub") or 0.0),
        )
    )
    return tenders


def _competition_margin_adjustment(open_tenders: int | None) -> float:
    """Поправка маржи (в долях) по уровню конкуренции."""
    if open_tenders is None:
        return 0.0
    if open_tenders <= 1:
        return 0.025
    if open_tenders <= 3:
        return 0.01
    if open_tenders <= 5:
        return 0.0
    if open_tenders <= 7:
        return -0.01
    return -0.025


# ============================================================================
# Канонизация
# ============================================================================

def _normalize_object_type(value: Any) -> str:
    if not value:
        raise ValueError("Параметр 'object_type' обязателен.")
    raw = str(value).strip().lower()
    for key in BASE_RATES:
        if key.lower() == raw:
            return key
    for key in BASE_RATES:
        if key.lower() in raw:
            return key
    raise ValueError(
        f"Неизвестный тип объекта: {value!r}. "
        f"Допустимые: {', '.join(BASE_RATES)}."
    )


def _normalize_financing(value: Any) -> str:
    if value is None or value == "":
        return DEFAULT_FINANCING
    raw = str(value).strip().lower()
    if raw in _FINANCING_ALIASES:
        return _FINANCING_ALIASES[raw]
    raise ValueError(f"Неизвестная схема финансирования: {value!r}.")


def _normalize_work_type(value: Any) -> str | None:
    if value is None or value == "":
        return DEFAULT_WORK_TYPE
    raw = str(value).strip().lower()
    if raw in _WORK_TYPE_ALIASES:
        return _WORK_TYPE_ALIASES[raw]
    raise ValueError(f"Неизвестный вид работ: {value!r}.")


def _normalize_equipment(value: Any) -> str:
    if value is None or value == "":
        return DEFAULT_EQUIPMENT
    raw = str(value).strip().lower()
    if raw in _EQUIPMENT_ALIASES:
        return _EQUIPMENT_ALIASES[raw]
    raise ValueError(f"Неизвестный тип оборудования: {value!r}.")


def _urgency_from_deadline(
    deadline_iso: str, today: date | None = None
) -> tuple[float, str]:
    try:
        deadline = date.fromisoformat(str(deadline_iso).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Некорректная дата дедлайна: {deadline_iso!r}. Ожидается YYYY-MM-DD."
        ) from exc

    reference = today or date.today()
    days_left = (deadline - reference).days
    if days_left < 0:
        raise ValueError(
            f"Дедлайн уже прошёл ({deadline_iso}). Укажите будущую дату."
        )

    for max_days, coefficient, label in _DEADLINE_BUCKETS:
        if days_left <= max_days:
            return coefficient, f"{label} — {days_left} дн. до завершения"
    return _LONG_TERM_COEFFICIENT, f"{_LONG_TERM_LABEL} — {days_left} дн. до завершения"


def _resolve_legacy_urgency(urgency: Any) -> tuple[float, str]:
    normalized = str(urgency or DEFAULT_URGENCY).strip().lower()
    if normalized in _URGENCY_ALIASES:
        return _URGENCY_ALIASES[normalized]
    return 1.0, "Нормальная"


# ============================================================================
# Аналоги
# ============================================================================

def _load_analogs_for_comparison(
    region_id: str,
    region_data: dict[str, Any],
    optimal_price: float,
    min_price: float,
    max_price: float,
) -> tuple[int | None, list[dict[str, Any]] | None]:
    file_path = _resolve_data_path(_ANALOGS_FILE)
    if file_path is None:
        return None, None

    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error):
        return None, None

    if not rows:
        return None, None

    amount_column = _first_present(rows[0], ("amount_rub", "amount"))
    if amount_column is None:
        return None, None

    target_aliases = _get_region_aliases(
        region_data.get(region_id, {}).get("name", "") if region_data else ""
    )

    lower = min_price * _ANALOG_LOW_FACTOR
    upper = max_price * _ANALOG_HIGH_FACTOR

    same_region: list[dict[str, Any]] = []
    other_region: list[dict[str, Any]] = []

    for row in rows:
        amount = _safe_float(row.get(amount_column))
        if amount is None or amount <= 0:
            continue
        if not (lower <= amount <= upper):
            continue

        row_region = str(row.get("region") or "").strip()
        row_region_fold = row_region.casefold()
        is_same = bool(
            target_aliases
            and any(row_region_fold == alias.casefold() for alias in target_aliases)
        )

        entry: dict[str, Any] = {
            "investment_id": row.get("investment_id"),
            "company_name": row.get("company_name"),
            "project_name": row.get("project_name"),
            "region": row_region,
            "amount_rub": amount,
            "expected_roi_percent": _safe_float(row.get("expected_roi_percent")),
            "investment_year": row.get("investment_year"),
            "status": row.get("status"),
            "same_region": is_same,
        }
        (same_region if is_same else other_region).append(entry)

    analogs = same_region if same_region else other_region
    if not analogs:
        return 0, []

    analogs.sort(key=lambda item: abs(item["amount_rub"] - optimal_price))
    return len(analogs), analogs


def _prepare_chart_data(
    optimal_price: float,
    min_price: float,
    max_price: float,
    cost_of_goods_sold: float,
    analog_data: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    points = [min_price, optimal_price, max_price]
    margins = [
        {
            "price": round(price, 2),
            "margin_percent": round((price - cost_of_goods_sold) / price * 100.0, 1)
            if price > 0 else None,
            "profit_rub": round(price - cost_of_goods_sold, 2),
        }
        for price in points
    ]
    return {
        "price_range": {"min": min_price, "optimal": optimal_price, "max": max_price},
        "margin_at_prices": margins,
        "analogs": analog_data or [],
    }


def _generate_business_insight(
    optimal_price: float,
    min_price: float,
    max_price: float,
    margin_percent: float,
    base_rate: float,
    object_type: str,
    analog_count: int | None,
    analog_data: list[dict[str, Any]] | None,
    competition_open_tenders: int | None,
    competition_adj: float,
) -> str:
    """Короткий инсайт: цена, маржа, конкуренция, аналоги.

    Прогноз вероятности победы в тендере НЕ выводится — без данных о
    конкурентах и истории победителей он был бы недостоверным.
    """
    if analog_data:
        average = sum(a["amount_rub"] for a in analog_data) / len(analog_data)
        diff_pct = (optimal_price - average) / average * 100.0
        if diff_pct <= -1.0:
            comparison = (
                f"цена на {abs(diff_pct):.1f}% ниже среднего по "
                f"{len(analog_data)} аналогам"
            )
        elif diff_pct >= 1.0:
            comparison = (
                f"цена на {diff_pct:.1f}% выше среднего по "
                f"{len(analog_data)} аналогам"
            )
        else:
            comparison = f"цена на уровне среднего по {len(analog_data)} аналогам"
    elif analog_count == 0:
        comparison = "сопоставимых аналогов в истории нет"
    else:
        comparison = "данные по аналогам недоступны"

    if competition_open_tenders is None:
        competition_text = "конкуренция не оценена"
    else:
        sign = "+" if competition_adj > 0 else ""
        competition_text = (
            f"конкуренция: {competition_open_tenders} откр. тендеров, "
            f"поправка к марже {sign}{competition_adj * 100:.1f} п.п."
        )

    return (
        f"Ставка «{object_type}» — {_fmt_price(base_rate)}/м², "
        f"маржа {margin_percent:.1f}% ({competition_text}). "
        f"Оптимум {_fmt_price(optimal_price)}: {comparison}. "
        f"Вилка {_fmt_price(min_price)} — {_fmt_price(max_price)}."
    )


# ============================================================================
# Служебные
# ============================================================================

def _get_region_coefficient(
    region_id: str, region_data: dict[str, Any]
) -> float | None:
    if not region_data or region_id not in region_data:
        return None
    raw = region_data[region_id].get(REGION_CLIMATE_KEY)
    if raw is None:
        return None
    try:
        coefficient = float(raw) / 100.0
    except (TypeError, ValueError):
        return None
    return coefficient if coefficient > 0 else None


def _get_region_name(
    region_id: str, region_data: dict[str, Any] | None = None
) -> str | None:
    if not region_data or not region_id:
        return None
    name = region_data.get(region_id, {}).get("name")
    if not name:
        return None
    rus_map = {
        "Rostov Oblast": "Ростовская область",
        "Krasnodar Krai": "Краснодарский край",
    }
    return rus_map.get(name, name)


def _get_region_aliases(region_name: str) -> tuple[str, ...]:
    if not region_name:
        return ()
    return _REGION_NAME_ALIASES.get(region_name, (region_name,))


def _resolve_data_path(filename: str) -> Path | None:
    candidate = Path(__file__).resolve().parents[1] / "data" / filename
    return candidate if candidate.is_file() else None


def _first_present(mapping: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        if key in mapping:
            return key
    return None


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_price(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{int(round(value)):,}".replace(",", " ") + " ₽"


def _params_signature(p: dict[str, Any]) -> tuple:
    """Кортеж из входных параметров для сравнения и дедупликации."""
    return (
        str(p.get("object_type") or ""),
        float(p.get("area_sqm") or 0.0),
        str(p.get("region_id") or ""),
        str(p.get("deadline_date") or ""),
        str(p.get("financing") or ""),
        str(p.get("work_type") or ""),
        str(p.get("equipment") or ""),
        bool(p.get("unique_solution")),
    )


# ============================================================================
# Streamlit UI
# ============================================================================

def render_calculator() -> None:
    """Streamlit-интерфейс раздела «Калькулятор сделок»."""
    import streamlit as st

    try:
        from modules import export as export_module
    except ImportError:
        import export as export_module  # type: ignore[no-redef]

    st.session_state.setdefault("calc_history", [])
    st.session_state.setdefault("calc_signatures", set())
    st.session_state.setdefault("calc_result", None)
    st.session_state.setdefault("calc_error", None)
    st.session_state.setdefault("calc_submitted_signature", None)

    region_data = load_regions()
    if not region_data:
        st.error(
            "Не удалось загрузить data/region.json. Расчёт невозможен: "
            "региональные коэффициенты недоступны."
        )
        return

    region_labels = {
        rid: str(record.get("name") or rid) for rid, record in region_data.items()
    }

    st.markdown("#### Параметры проекта")

    # Live-часть: тип объекта и дедлайн
    live_left, live_right = st.columns(2)

    with live_left:
        object_type = st.selectbox(
            "Тип объекта", options=list(BASE_RATES.keys()),
        )
        st.caption(
            f"Базовая ставка за м²: **{_fmt_price(BASE_RATES[object_type])}**"
        )

    with live_right:
        default_deadline = date.today() + timedelta(days=60)
        deadline = st.date_input(
            "Дата завершения проекта",
            value=default_deadline,
            min_value=date.today(),
            help="Чем ближе дедлайн — тем выше коэффициент срочности.",
        )
        try:
            urgency_coeff, urgency_label = _urgency_from_deadline(deadline.isoformat())
        except ValueError as exc:
            st.error(str(exc))
            return
        st.markdown(
            f"**Срочность (рассчитывается автоматически):** "
            f"{urgency_label} · коэффициент ×{urgency_coeff:.2f}"
        )

    # Форма: остальные поля
    with st.form("calculator_form", clear_on_submit=False):
        st.markdown("###### Остальные параметры")
        form_left, form_right = st.columns(2)

        with form_left:
            area_sqm = st.number_input(
                "Площадь, м²",
                min_value=1.0,
                max_value=1_000_000.0,
                value=1000.0,
                step=100.0,
            )
            region_id = st.selectbox(
                "Регион",
                options=list(region_labels.keys()),
                format_func=lambda rid: region_labels.get(rid, rid),
            )

        with form_right:
            financing = st.selectbox(
                "Финансирование", options=list(FINANCING_COEFFICIENTS.keys()),
            )
            work_type = st.selectbox(
                "Вид работ",
                options=["(не указано)"] + list(WORK_TYPES_COEFFICIENTS.keys()),
            )
            equipment = st.selectbox(
                "Оборудование", options=list(EQUIPMENT_TYPES.keys()),
            )
            unique_solution = st.checkbox("Уникальные технические решения (+10%)")

        submitted = st.form_submit_button(
            "Рассчитать стоимость",
            type="primary",
            use_container_width=True,
            icon=":material/calculate:",
        )

    params: dict[str, Any] = {
        "object_type": object_type,
        "area_sqm": float(area_sqm),
        "region_id": region_id,
        "deadline_date": deadline.isoformat(),
        "financing": financing,
        "work_type": None if work_type == "(не указано)" else work_type,
        "equipment": equipment,
        "unique_solution": unique_solution,
    }
    current_signature = _params_signature(params)

    if submitted:
        try:
            fresh = calculate(params)
        except ValueError as exc:
            st.session_state["calc_result"] = None
            st.session_state["calc_error"] = str(exc)
        else:
            st.session_state["calc_result"] = fresh
            st.session_state["calc_error"] = None
            st.session_state["calc_submitted_signature"] = current_signature

    if st.session_state.get("calc_error"):
        st.error(f"Ошибка расчёта: {st.session_state['calc_error']}")
        return

    result = st.session_state.get("calc_result")
    if result is None:
        st.info(
            "Заполните параметры и нажмите **«Рассчитать стоимость»**. "
            "Тип объекта и дата завершения влияют на расчёт в реальном времени."
        )
        return

    if st.session_state.get("calc_submitted_signature") != current_signature:
        st.warning(
            "Параметры изменились с момента последнего расчёта. "
            "Нажмите «Рассчитать стоимость», чтобы обновить результат."
        )

    # ---------- Результат ----------
    st.markdown("---")
    st.markdown("#### Результат расчёта")

    analog_count = result.get("analog_count")
    analog_display = "—" if analog_count is None else f"{analog_count}"
    competition_open = result.get("competition_open_tenders")
    competition_adj = result.get("competition_margin_adjustment_pp") or 0.0
    margin_delta = (
        f"{'+' if competition_adj > 0 else ''}{competition_adj:.1f} п.п."
        if competition_adj != 0 else None
    )

    kpi = st.columns(5)
    kpi[0].metric("Оптимальная цена", _fmt_price(result["optimal_price"]))
    kpi[1].metric("Минимум", _fmt_price(result["min_price"]))
    kpi[2].metric("Максимум", _fmt_price(result["max_price"]))
    kpi[3].metric(
        "Маржинальность",
        f"{result['margin_percent']:.1f}%",
        delta=margin_delta,
        help=(
            f"Базовая маржа по виду работ — {result.get('base_margin_percent', 0):.1f}%, "
            "плюс поправка на конкуренцию."
        ),
    )
    kpi[4].metric(
        "Кол-во аналогов",
        analog_display,
        help="Сколько сопоставимых проектов из data/investmensts.csv использовано.",
    )

    cost = result.get("cost_of_goods_sold")
    margin = result.get("margin_percent")
    profit = result.get("profit")
    optimal = result["optimal_price"]
    if cost is not None and margin is not None:
        profit_value = profit if profit is not None else (optimal - cost)
        st.info(
            f"**Маржинальность {margin:.1f}%** — это {_fmt_price(profit_value)} "
            f"прибыли при цене {_fmt_price(optimal)} "
            f"(цена − себестоимость {_fmt_price(cost)}).",
            icon=":material/savings:",
        )

    if competition_open is not None:
        if competition_open == 0:
            comp_text = "В нише нет открытых тендеров — маржу можно держать выше."
        elif competition_open <= 3:
            comp_text = "Мало открытых тендеров — конкурентов немного, маржа повышена."
        elif competition_open <= 5:
            comp_text = "Умеренная конкуренция — маржа на базовом уровне."
        else:
            comp_text = "Высокая конкуренция — маржа снижена, чтобы зайти в нишу."
        sign = "+" if competition_adj > 0 else ""
        st.caption(
            f"Конкуренция: **{competition_open}** открытых тендеров в регионе "
            f"по направлению → поправка к марже **{sign}{competition_adj:.1f} п.п.** "
            f"(базовая {result.get('base_margin_percent', 0):.1f}%, "
            f"итог {result['margin_percent']:.1f}%). {comp_text}"
        )

    # ---------- Активные тендеры (краткая информация) ----------
    competition_tenders = result.get("competition_tenders") or []
    if competition_open and competition_open > 0 and competition_tenders:
        st.markdown("##### Активные тендеры в нише")
        st.caption(
            "Это открытые закупки в выбранном регионе по направлению работ — "
            "по ним оценивается конкуренция. Аналоги (ниже, bar chart) — это "
            "другое: исторические инвестпроекты для сравнения цен."
        )
        import pandas as pd

        tenders_frame = pd.DataFrame(
            [
                {
                    "ID": t.get("tender_id"),
                    "Тендер": t.get("title"),
                    "Заказчик": t.get("customer"),
                    "Бюджет, ₽": t.get("budget_rub"),
                    "Дедлайн": t.get("deadline"),
                }
                for t in competition_tenders
            ]
        )
        st.dataframe(tenders_frame, hide_index=True, use_container_width=True)
        if competition_open > len(competition_tenders):
            st.caption(
                f"Показано {len(competition_tenders)} из {competition_open} "
                "(ближайшие по дедлайну)."
            )

    if result.get("business_insight"):
        st.markdown("##### Бизнес-инсайт")
        st.write(result["business_insight"])

    # ---------- Графики ----------
    st.markdown("##### Визуализация")
    row1_left, row1_right = st.columns(2)
    with row1_left:
        _render_price_gauge(result)
    with row1_right:
        _render_margin_chart(result)

    st.markdown("---")
    _render_analogs_chart(result)

    # ---------- Таблица аналогов ----------
    st.markdown("##### Сопоставимые проекты (детали)")
    analog_data = result.get("analog_data") or []
    if analog_count is None:
        st.caption("Исторические данные (data/investmensts.csv) недоступны.")
    elif analog_count == 0:
        st.caption("Сопоставимых проектов в исторических данных не найдено.")
    else:
        import pandas as pd

        analog_frame = pd.DataFrame(
            [
                {
                    "ID": item.get("investment_id"),
                    "Проект": item.get("project_name"),
                    "Компания": item.get("company_name"),
                    "Регион": (
                        f"{item.get('region')} (другой)"
                        if item.get("same_region") is False
                        else item.get("region")
                    ),
                    "Сумма, ₽": item.get("amount_rub"),
                    "ROI, %": item.get("expected_roi_percent"),
                    "Год": item.get("investment_year"),
                    "Статус": item.get("status"),
                }
                for item in analog_data
            ]
        )
        st.dataframe(analog_frame, hide_index=True, use_container_width=True)

    # ---------- История ----------
    st.markdown("##### История расчётов")
    st.caption(
        "История хранится только в текущей сессии браузера: после перезагрузки "
        "страницы или перезапуска приложения она очистится. Чтобы сохранить — "
        "скачайте CSV ниже. На сервере данные не сохраняются."
    )

    result_signature = _params_signature(result["project_params"])

    hist_col1, hist_col2, hist_col3 = st.columns([2, 1, 1])
    with hist_col1:
        if st.button(
            "Добавить расчёт в историю",
            use_container_width=True,
            help="Сохраняет результат в память сессии. Для долговременного хранения — CSV.",
        ):
            if result_signature in st.session_state["calc_signatures"]:
                st.info("Этот расчёт уже есть в истории.")
            else:
                st.session_state["calc_signatures"].add(result_signature)
                st.session_state["calc_history"].append(result)
                st.success("Расчёт добавлен в историю (в память сессии).")
    with hist_col2:
        if st.button(
            "Очистить историю",
            use_container_width=True,
            disabled=not st.session_state["calc_history"],
        ):
            st.session_state["calc_history"] = []
            st.session_state["calc_signatures"] = set()
            st.rerun()
    with hist_col3:
        # len() непосредственно перед metric — чтобы после нажатия
        # «Добавить» значение отобразилось сразу, а не на следующем rerun.
        st.metric(
            "Записей в истории",
            len(st.session_state["calc_history"]),
        )

    # ---------- Экспорт ----------
    st.markdown("##### Экспорт")
    export_col1, export_col2 = st.columns(2)

    with export_col1:
        try:
            docx_bytes = export_module.build_commercial_proposal_docx(result)
        except RuntimeError as exc:
            st.caption(f"DOCX недоступен: {exc}")
        except (TypeError, ValueError) as exc:
            st.caption(f"Не удалось сформировать DOCX: {exc}")
        else:
            suffix = str(result.get("region_name") or "project").replace(" ", "_")
            st.download_button(
                "Сформировать КП (DOCX)",
                data=docx_bytes,
                file_name=f"commercial_proposal_{suffix}.docx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                use_container_width=True,
                icon=":material/description:",
            )

    with export_col2:
        csv_bytes = export_module.build_calculation_history_csv(
            st.session_state["calc_history"]
        )
        st.download_button(
            "Скачать историю (CSV)",
            data=csv_bytes,
            file_name="calculation_history.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not st.session_state["calc_history"],
            icon=":material/table_view:",
        )

    st.caption(
        "Все результаты — предварительная оценка. Документ не является офертой."
    )


# ---------- Графики ----------

def _render_price_gauge(result: dict[str, Any]) -> None:
    import streamlit as st
    import plotly.graph_objects as go

    min_p = float(result["min_price"])
    opt_p = float(result["optimal_price"])
    max_p = float(result["max_price"])
    upper = max_p * 1.2

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=opt_p,
            number={
                "valueformat": ",.0f",
                "suffix": " ₽",
                "font": {"size": 22, "color": _RT_NAVY},
            },
            gauge={
                "axis": {
                    "range": [0, upper],
                    "tickformat": ",.0f",
                    "tickfont": {"size": 10, "color": _RT_MUTED},
                },
                "bar": {"color": _RT_ORANGE, "thickness": 0.22},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, min_p], "color": "#E8E8ED"},
                    {"range": [min_p, max_p], "color": "#FFF1EA"},
                    {"range": [max_p, upper], "color": "#E8E8ED"},
                ],
                "threshold": {
                    "line": {"color": _RT_PURPLE, "width": 3},
                    "thickness": 0.75,
                    "value": opt_p,
                },
            },
        )
    )
    fig.update_layout(
        title={"text": "Ценовая вилка", "x": 0.5},
        height=300,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "Segoe UI, sans-serif", "color": _RT_NAVY},
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.caption(
        f"Минимум: **{_fmt_price(min_p)}** · Оптимум: **{_fmt_price(opt_p)}** · "
        f"Максимум: **{_fmt_price(max_p)}**. "
        "Шкала носит рекомендательный характер: вероятность победы в тендере "
        "требует данных о конкурентах и ценах победителей — в модели их нет."
    )


def _render_margin_chart(result: dict[str, Any]) -> None:
    import streamlit as st
    import plotly.graph_objects as go

    opt = float(result["optimal_price"])
    cost = float(result.get("cost_of_goods_sold") or 0.0)
    if cost <= 0:
        st.info("Маржинальность не рассчитана — нет себестоимости.")
        return

    n = 81
    prices = [opt * (0.75 + 0.5 * i / (n - 1)) for i in range(n)]
    margins = [(p - cost) / p * 100.0 for p in prices]

    fig = go.Figure()
    fig.add_hrect(
        y0=20, y1=25,
        fillcolor="rgba(46, 125, 50, 0.14)", line_width=0,
        annotation_text="Целевая маржа 20–25 %",
        annotation_position="top left",
        annotation_font={"size": 11, "color": "#2e7d32"},
    )
    fig.add_trace(
        go.Scatter(
            x=prices, y=margins, mode="lines",
            line={"color": _RT_BLUE, "width": 3},
            hovertemplate="Цена %{x:,.0f} ₽<br>Маржа %{y:.1f} %<extra></extra>",
        )
    )
    for x_val, label, color, dash in (
        (result["min_price"], "Мин", _RT_MUTED, "dash"),
        (result["optimal_price"], "Оптимум", _RT_ORANGE, "solid"),
        (result["max_price"], "Макс", _RT_MUTED, "dash"),
    ):
        fig.add_vline(
            x=float(x_val), line_dash=dash, line_color=color, line_width=2,
            annotation_text=label, annotation_position="top",
            annotation_font={"size": 11, "color": color},
        )

    fig.update_layout(
        title={"text": "Маржинальность vs цена", "x": 0.5},
        height=300,
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Segoe UI, sans-serif", "size": 12, "color": _RT_NAVY},
        showlegend=False,
    )
    fig.update_xaxes(
        title_text="Цена сделки, ₽", showgrid=True,
        gridcolor=_RT_BORDER, zeroline=False,
    )
    fig.update_yaxes(
        title_text="Маржинальность, %", showgrid=True,
        gridcolor=_RT_BORDER, zeroline=False,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(
        "Маржа как функция цены. Полоса — целевой диапазон 20–25 %. "
        "Торг ниже вилки уводит сделку из целевой маржи."
    )


def _render_analogs_chart(result: dict[str, Any]) -> None:
    import streamlit as st
    import plotly.graph_objects as go

    analog_count = result.get("analog_count")
    analog_data = result.get("analog_data") or []

    if analog_count is None:
        st.caption("Аналоги недоступны — сравнение не строится.")
        return
    if analog_count == 0 or not analog_data:
        st.caption("Сопоставимых проектов в исторических данных не найдено.")
        return

    area = float(result["project_params"]["area_sqm"])
    if area <= 0:
        return

    labels: list[str] = []
    values: list[float] = []
    colors: list[str] = []

    for item in analog_data[:5]:
        name = item.get("project_name") or item.get("company_name") or "Аналог"
        labels.append(str(name)[:32])
        values.append(float(item["amount_rub"]) / area)
        colors.append(_RT_BLUE)

    labels.append("Наш расчёт")
    values.append(float(result["optimal_price"]) / area)
    colors.append(_RT_ORANGE)

    fig = go.Figure(
        go.Bar(
            x=values, y=labels, orientation="h",
            marker_color=colors,
            text=[f"{int(round(v)):,}".replace(",", " ") + " ₽/м²" for v in values],
            textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
        )
    )
    fig.update_layout(
        title={"text": "Цена за м²: аналоги vs наш расчёт", "x": 0.5},
        height=340,
        margin={"l": 10, "r": 30, "t": 50, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Segoe UI, sans-serif", "size": 12, "color": _RT_NAVY},
        showlegend=False,
    )
    fig.update_xaxes(
        title_text="Эквивалентная цена за м², ₽",
        showgrid=True, gridcolor=_RT_BORDER, zeroline=False,
    )
    fig.update_yaxes(showgrid=False, autorange="reversed")

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.caption(
        "Площади аналогов в источнике не указаны, поэтому цена за м² для них — "
        f"сумма проекта в пересчёте на вашу площадь ({int(round(area))} м²). "
        "Сопоставление ориентировочное."
    )


show_calculator = render_calculator


__all__ = [
    "BASE_RATES",
    "FINANCING_COEFFICIENTS",
    "WORK_TYPES_COEFFICIENTS",
    "EQUIPMENT_TYPES",
    "calculate",
    "load_regions",
    "render_calculator",
    "show_calculator",
]
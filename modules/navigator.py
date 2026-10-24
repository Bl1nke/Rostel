"""Модуль «Инвестиционный навигатор» — поиск инвестиционных возможностей.

Раздел коммерческого портала «Ростелеком Коммерческий»:
* KPI по стадиям, потребностям и потенциальному бюджету;
* таймлайн инвестиционных событий по годам + Топ-3 проектов;
* аналитика потребностей рынка (оценка емкости в деньгах);
* карточка выбранного проекта с оценкой бюджета;
* поиск по параметрам (фильтр с кнопкой «Применить»);
* таблица отфильтрованных проектов и экспорт выборки в CSV.

Точка входа — ``render_navigator()``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from modules.icons import icon_svg
except ImportError:
    from icons import icon_svg  # type: ignore[no-redef]

# ============================================================================
# Константы
# ============================================================================

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
INVESTMENTS_FILE = "investmensts.csv"
COMPANIES_FILE = "companies.csv"
REGIONS_FILE = "region.json"

RT_ORANGE = "#FF4F12"
RT_BLUE = "#4A90D9"
RT_PURPLE = "#7A2E8E"
RT_NAVY = "#1B1B2F"
RT_MUTED = "#6B6B80"
RT_BORDER = "#ECE8F5"

BRAND_PALETTE: tuple[str, ...] = (
    RT_ORANGE, RT_BLUE, RT_PURPLE, RT_NAVY, "#FF7A3D",
    "#E23E05", "#4B6CB7", "#8996C6", "#F2A63B", "#2E8B7F",
)

STAGE_PROJECT = "Проектирование"
STAGE_BUILD = "Строительство"
STAGE_LAUNCH = "Запуск"
STAGE_SUSPENDED = "Приостановлен"
STAGE_CANCELLED = "Отменён"
STAGE_OTHER = "Другая стадия"

STAGE_COLORS: dict[str, str] = {
    STAGE_PROJECT: "#4B6CB7",
    STAGE_BUILD: "#E30613",
    STAGE_LAUNCH: "#1F3C88",
    STAGE_SUSPENDED: "#B08A00",
    STAGE_CANCELLED: "#8A8A99",
    STAGE_OTHER: "#8996C6",
}

STAGE_ORDER: tuple[str, ...] = (
    STAGE_PROJECT, STAGE_BUILD, STAGE_LAUNCH,
    STAGE_SUSPENDED, STAGE_CANCELLED, STAGE_OTHER,
)

_STATUS_TO_STAGE: dict[str, str] = {
    # Английские
    "planned": STAGE_PROJECT, "planning": STAGE_PROJECT, "design": STAGE_PROJECT,
    "project": STAGE_PROJECT, "idea": STAGE_PROJECT,
    "active": STAGE_BUILD, "in progress": STAGE_BUILD, "construction": STAGE_BUILD, "build": STAGE_BUILD,
    "completed": STAGE_LAUNCH, "complete": STAGE_LAUNCH, "launched": STAGE_LAUNCH, "done": STAGE_LAUNCH,
    "suspended": STAGE_SUSPENDED, "on hold": STAGE_SUSPENDED, "paused": STAGE_SUSPENDED,
    "cancelled": STAGE_CANCELLED, "canceled": STAGE_CANCELLED,
    # Русские (на случай расширения БД)
    "проектирование": STAGE_PROJECT, "идея": STAGE_PROJECT, "план": STAGE_PROJECT,
    "строительство": STAGE_BUILD, "в процессе": STAGE_BUILD, "активный": STAGE_BUILD,
    "запуск": STAGE_LAUNCH, "завершен": STAGE_LAUNCH, "завершён": STAGE_LAUNCH,
    "приостановлен": STAGE_SUSPENDED, "на паузе": STAGE_SUSPENDED,
    "отменен": STAGE_CANCELLED, "отменён": STAGE_CANCELLED,
}

INDUSTRY_RU: dict[str, str] = {
    "it infrastructure": "ИТ и связь", "telecom services": "ИТ и связь",
    "manufacturing": "Промышленность", "production": "Промышленность",
    "retail": "Торговля", "trade": "Торговля",
    "logistics": "Логистика и склад", "warehouse": "Логистика и склад",
    "construction": "Строительство", "finance": "Финансы",
    "healthcare": "Услуги населению", "services": "Услуги населению",
    "agro": "АПК", "agriculture": "АПК",
}

REGION_RU: dict[str, str] = {
    "rostov oblast": "Ростовская область", "ростовская область": "Ростовская область",
    "krasnodar krai": "Краснодарский край", "краснодарский край": "Краснодарский край",
}

# --- Оценка бюджетов ---
_NEED_BUDGET_SHARE: dict[str, float] = {
    "ИТ-инфраструктура и корпоративные сети": 0.035,
    "АСУ ТП и промышленная автоматизация": 0.04,
    "Физическая безопасность": 0.02,
    "Информационная безопасность": 0.015,
    "Корпоративная связь и телеком": 0.01,
}
# Максимальная доля от CAPEX, которую могут занимать все ИТ-потребности вместе
_MAX_TOTAL_IT_SHARE = 0.08

_NEED_RULES: dict[str, tuple[str, ...]] = {
    "ИТ-инфраструктура и корпоративные сети": (
        "digital", "cloud", "it", "data center", "server", "network",
        "infrastructure", "crm", "erp", "software", "bi", "analytics",
        "mobile", "telecom", "fiber", "wi-fi", "wifi",
    ),
    "АСУ ТП и промышленная автоматизация": (
        "automation", "production line", "manufacturing", "industrial",
        "plant", "factory", "scada", "robot",
    ),
    "Физическая безопасность": (
        "security", "access control", "video", "fire", "surveillance",
        "скуд", "видеонаблюдение",
    ),
    "Информационная безопасность": (
        "cyber", "infosec", "security audit", "ai research",
    ),
    "Корпоративная связь и телеком": (
        "telecom", "unified communications", "mobile", "voice",
        "fiber optic", "fiber-optic",
    ),
}

_OBJECT_TYPE_RULES: dict[str, tuple[str, ...]] = {
    "Завод": ("plant", "factory", "manufacturing"),
    "Склад": ("warehouse", "distribution center", "logistics center"),
    "Дата-центр": ("data center", "datacenter"),
    "Бизнес-центр": ("business center", "office", "headquarters"),
    "Лаборатория": ("r&d", "laboratory", "research center"),
    "Гостиница": ("hotel", "resort"),
    "Торговый объект": ("retail", "mall", "shop", "store"),
}

_OBJECT_TO_NEEDS: dict[str, tuple[str, ...]] = {
    "Завод": ("АСУ ТП и промышленная автоматизация", "Физическая безопасность"),
    "Склад": ("Физическая безопасность", "ИТ-инфраструктура и корпоративные сети"),
    "Дата-центр": ("ИТ-инфраструктура и корпоративные сети", "Информационная безопасность"),
    "Бизнес-центр": ("ИТ-инфраструктура и корпоративные сети", "Физическая безопасность"),
    "Лаборатория": ("ИТ-инфраструктура и корпоративные сети", "Информационная безопасность"),
    "Гостиница": ("ИТ-инфраструктура и корпоративные сети", "Физическая безопасность"),
    "Торговый объект": ("ИТ-инфраструктура и корпоративные сети", "Физическая безопасность"),
}

_INDUSTRY_TO_NEEDS: dict[str, tuple[str, ...]] = {
    "ИТ и связь": ("ИТ-инфраструктура и корпоративные сети",),
    "Промышленность": ("АСУ ТП и промышленная автоматизация", "Физическая безопасность"),
    "Логистика и склад": ("Физическая безопасность", "ИТ-инфраструктура и корпоративные сети"),
    "Торговля": ("Физическая безопасность", "ИТ-инфраструктура и корпоративные сети"),
    "Строительство": ("ИТ-инфраструктура и корпоративные сети",),
    "Финансы": ("Информационная безопасность",),
    "Услуги населению": ("ИТ-инфраструктура и корпоративные сети",),
    "ТЭК": ("АСУ ТП и промышленная автоматизация",),
    "АПК": ("АСУ ТП и промышленная автоматизация", "ИТ-инфраструктура и корпоративные сети"),
}

PLOTLY_CONFIG: dict[str, Any] = {"displayModeBar": False}

NAV_CSS = """
<style>
.nav-section-title {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin: 0.2rem 0 0.6rem;
  font-size: 1.02rem;
  font-weight: 700;
  color: var(--rt-navy, #1B1B2F);
}
.nav-section-title::before {
  content: "";
  width: 4px;
  height: 1.05rem;
  border-radius: 3px;
  background: linear-gradient(180deg, var(--rt-orange, #FF4F12), var(--rt-purple, #7A2E8E));
}
.nav-section-title .rt-icon-svg {
  width: 1.05rem;
  height: 1.05rem;
  color: var(--rt-orange, #FF4F12);
}
</style>
"""


# ============================================================================
# Утилиты
# ============================================================================

def _read_csv(filename: str) -> pd.DataFrame | None:
    path = DATA_DIR / filename
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        data = pd.read_csv(path, encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError, pd.errors.ParserError):
        return None
    return data if not data.empty else None


def _read_regions() -> dict[str, dict[str, Any]]:
    import json
    path = DATA_DIR / REGIONS_FILE
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, ValueError):
        return {}
    if isinstance(payload, dict):
        payload = payload.get("regions", [payload])
    if not isinstance(payload, list):
        return {}
    return {str(item["region_id"]): item for item in payload if isinstance(item, dict) and "region_id" in item}


def _classify_needs(project_name: str, industry_ru: str, object_type: str | None) -> list[dict[str, str]]:
    text = f"{project_name} {industry_ru}".lower()
    matched: list[dict[str, str]] = []
    seen: set[str] = set()

    for need, keywords in _NEED_RULES.items():
        for keyword in keywords:
            if keyword in text:
                if need not in seen:
                    seen.add(need)
                    matched.append({"need": need, "reason": "соответствие описанию проекта"})
                break

    if object_type and object_type in _OBJECT_TO_NEEDS:
        for need in _OBJECT_TO_NEEDS[object_type]:
            if need not in seen:
                seen.add(need)
                matched.append({"need": need, "reason": f"типовая потребность для объекта «{object_type}»"})

    if not matched:
        for need in _INDUSTRY_TO_NEEDS.get(industry_ru, ()):
            if need not in seen:
                seen.add(need)
                matched.append({"need": need, "reason": f"типовая потребность отрасли «{industry_ru}»"})

    return matched


def _classify_object_type(project_name: str) -> str | None:
    text = project_name.lower()
    for object_type, keywords in _OBJECT_TYPE_RULES.items():
        if any(keyword in text for keyword in keywords):
            return object_type
    return None


def _clean_str(value: Any) -> str:
    """Безопасно очищает строку от NaN и лишних пробелов."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "<na>"}:
        return ""
    return text


def _map_industry(raw: Any) -> str:
    text = _clean_str(raw).lower()
    return INDUSTRY_RU.get(text, _clean_str(raw)) if text else "Прочее"


def _map_region(raw: Any) -> str:
    text = _clean_str(raw).lower()
    return REGION_RU.get(text, _clean_str(raw)) if text else "Не указан"


def _map_stage(raw: Any) -> str:
    text = _clean_str(raw).lower()
    return _STATUS_TO_STAGE.get(text, STAGE_OTHER) if text else STAGE_OTHER


# ============================================================================
# Загрузка данных
# ============================================================================

PROJECT_COLUMNS = [
    "investment_id", "company_id", "company_name", "region", "region_ru",
    "city", "project_name", "amount_rub", "investment_year",
    "investment_type", "status", "stage", "expected_roi_percent",
    "industry_ru", "object_type_guess", "needs", "needs_reasons",
]


@st.cache_data(ttl=30, show_spinner=False)
def load_projects() -> tuple[pd.DataFrame, bool, str | None]:
    raw = _read_csv(INVESTMENTS_FILE)
    if raw is None:
        return pd.DataFrame(columns=PROJECT_COLUMNS), True, None

    by_name = {str(c).strip().lower(): c for c in raw.columns}
    def col(*aliases: str) -> str | None:
        for alias in aliases:
            found = by_name.get(alias.lower())
            if found is not None: return found
        return None

    project_col = col("project_name", "name", "title")
    amount_col = col("amount_rub", "amount", "budget_rub")
    if project_col is None or amount_col is None:
        return pd.DataFrame(columns=PROJECT_COLUMNS), True, None

    frame = pd.DataFrame()
    frame["investment_id"] = raw[col("investment_id", "id")].apply(_clean_str) if col("investment_id", "id") else [f"I{idx:03d}" for idx in range(len(raw))]
    frame["company_id"] = raw[col("company_id")].apply(_clean_str) if col("company_id") else ""
    
    duplicates_mask = frame["investment_id"].duplicated(keep="first")
    dup_count = int(duplicates_mask.sum())
    if dup_count > 0:
        for idx in frame[duplicates_mask].index:
            frame.at[idx, "investment_id"] = f"{frame.at[idx, 'investment_id']}_dup{idx}"

    frame["company_name"] = raw[col("company_name", "company", "customer")].apply(_clean_str) if col("company_name", "company", "customer") else "—"
    frame["region"] = raw[col("region", "location")].apply(_clean_str) if col("region", "location") else "Не указан"
    frame["project_name"] = raw[project_col].apply(_clean_str)
    
    amounts_raw = raw[amount_col]
    amount_numeric = pd.to_numeric(amounts_raw, errors="coerce")
    bad_amounts_count = int(amount_numeric.isna().sum() - amounts_raw.isna().sum())
    frame["amount_rub"] = amount_numeric.fillna(0.0)
    
    years_raw = raw[col("investment_year", "year")] if col("investment_year", "year") else pd.Series([0]*len(raw))
    years_numeric = pd.to_numeric(years_raw, errors="coerce")
    bad_years_count = int(years_numeric.isna().sum() - years_raw.isna().sum())
    frame["investment_year"] = years_numeric.fillna(0).astype(int)

    frame["investment_type"] = raw[col("investment_type", "type")].apply(_clean_str) if col("investment_type", "type") else "—"
    frame["status"] = raw[col("status", "stage")].apply(_clean_str) if col("status", "stage") else "—"
    frame["expected_roi_percent"] = pd.to_numeric(raw[col("expected_roi_percent", "roi")], errors="coerce") if col("expected_roi_percent", "roi") else pd.NA

    frame["region_ru"] = frame["region"].map(_map_region)
    frame["stage"] = frame["status"].map(_map_stage)

    # Исправлено: приводим к нижнему регистру для проверки
    normalized_statuses = {s.lower() for s in frame["status"] if s}
    unknown_statuses = normalized_statuses - set(_STATUS_TO_STAGE.keys()) - {""}
    unknown_statuses.discard("nan")

    companies = _read_csv(COMPANIES_FILE)
    if companies is not None:
        c_by_name = {str(c).strip().lower(): c for c in companies.columns}
        cid_col_actual = c_by_name.get("company_id")
        
        if cid_col_actual:
            companies[cid_col_actual] = companies[cid_col_actual].apply(_clean_str)
            companies = companies.drop_duplicates(subset=[cid_col_actual])
            
            ind_col = c_by_name.get("industry")
            city_col = c_by_name.get("city")
            merge_cols = [cid_col_actual] + ([ind_col] if ind_col else []) + ([city_col] if city_col else [])
            companies_clean = companies[merge_cols].rename(columns={cid_col_actual: "company_id"})
            
            merged = frame.merge(companies_clean, on="company_id", how="left", validate="many_to_one")
            frame["industry_ru"] = merged[ind_col].map(_map_industry) if ind_col and ind_col in merged.columns else "Прочее"
            frame["city"] = merged[city_col].apply(_clean_str) if city_col and city_col in merged.columns else ""
        else:
            frame["industry_ru"] = "Прочее"
            frame["city"] = ""
    else:
        frame["industry_ru"] = "Прочее"
        frame["city"] = ""

    frame["object_type_guess"] = frame["project_name"].map(_classify_object_type)
    
    needs_list = [
        _classify_needs(str(name), str(ind), str(obj) if obj else None)
        for name, ind, obj in zip(frame["project_name"], frame["industry_ru"], frame["object_type_guess"])
    ]
    frame["needs"] = [", ".join(item["need"] for item in items) for items in needs_list]
    frame["needs_reasons"] = needs_list

    warnings = []
    if bad_amounts_count > 0:
        warnings.append(f"{bad_amounts_count} записей с некорректной суммой")
    if bad_years_count > 0:
        warnings.append(f"{bad_years_count} записей с некорректным годом")
    if unknown_statuses:
        warnings.append(f"неизвестные статусы: {', '.join(unknown_statuses)}")
    if dup_count > 0:
        warnings.append(f"дубликаты ID: {dup_count}")
    
    warning_msg = "Обнаружены проблемы в данных: " + ", ".join(warnings) + "." if warnings else None

    return frame[PROJECT_COLUMNS], False, warning_msg


# ============================================================================
# Форматирование и расчеты
# ============================================================================

def _fmt_int(value: Any) -> str:
    try: return f"{int(round(float(value))):,}".replace(",", " ")
    except (TypeError, ValueError): return "—"


def _fmt_money(value: Any) -> str:
    try: number = float(value)
    except (TypeError, ValueError): return "—"
    if abs(number) >= 1_000_000_000: return f"{number / 1_000_000_000:,.2f}".replace(",", " ") + " млрд ₽"
    if abs(number) >= 1_000_000: return f"{number / 1_000_000:,.1f}".replace(",", " ") + " млн ₽"
    if abs(number) >= 1_000: return f"{number / 1_000:,.0f}".replace(",", " ") + " тыс ₽"
    return _fmt_int(number) + " ₽"


def _fmt_percent(value: Any) -> str:
    try: return f"{float(value):.1f}%".replace(".", ",")
    except (TypeError, ValueError): return "—"


def _get_estimated_budget(project_row: pd.Series) -> float:
    """Считает общий потенциальный бюджет проекта на ИТ-услуги."""
    needs_str = project_row.get("needs", "")
    if not needs_str:
        return 0.0
    needs = str(needs_str).split(", ")
    total_share = sum(_NEED_BUDGET_SHARE.get(need, 0.0) for need in needs)
    total_share = min(total_share, _MAX_TOTAL_IT_SHARE)
    return project_row["amount_rub"] * total_share


def _get_distributed_budgets(projects: pd.DataFrame) -> list[dict[str, Any]]:
    """Распределяет общий ИТ-бюджет проекта по его потребностям пропорционально."""
    records = []
    for _, row in projects.iterrows():
        needs_str = row.get("needs", "")
        if not needs_str: continue
        needs = [n for n in str(needs_str).split(", ") if n]
        if not needs: continue
        
        shares = [_NEED_BUDGET_SHARE.get(n, 0.0) for n in needs]
        total_share = sum(shares)
        capped_share = min(total_share, _MAX_TOTAL_IT_SHARE)
        
        for n, s in zip(needs, shares):
            allocated_share = (s / total_share) * capped_share if total_share > 0 else 0
            records.append({
                "industry_ru": row["industry_ru"],
                "need_list": n,
                "budget": row["amount_rub"] * allocated_share,
            })
    return records


# ============================================================================
# Сайдбар: Фильтры
# ============================================================================

def _render_filters(projects: pd.DataFrame) -> dict[str, Any]:
    with st.sidebar:
        st.markdown(f'<div class="nav-section-title">{icon_svg("business_center")} Фильтры</div>', unsafe_allow_html=True)
        if projects.empty:
            return {"search": "", "stages": [], "industries": [], "companies": [], "regions": [], "cities": [], "years": [], "types": [], "needs": [], "amount_range": (0.0, 0.0)}

        search = st.text_input("Поиск по проекту, компании", placeholder="например, warehouse", key="nav_search").strip()
        
        stages = [s for s in STAGE_ORDER if s in set(projects["stage"])]
        selected_stages = st.multiselect("Стадия проекта", options=stages, default=stages, key="nav_stages")

        industries = sorted(projects["industry_ru"].dropna().astype(str).unique().tolist())
        selected_industries = st.multiselect("Отрасль", options=industries, default=industries, key="nav_industries")

        companies = sorted(projects["company_name"].dropna().astype(str).unique().tolist())
        selected_companies = st.multiselect("Инициатор", options=companies, default=companies, key="nav_companies")

        regions = sorted(projects["region_ru"].dropna().astype(str).unique().tolist())
        selected_regions = st.multiselect("Регион", options=regions, default=regions, key="nav_regions")

        cities = sorted(c for c in projects["city"].dropna().astype(str).unique().tolist() if c and c != "nan")
        selected_cities = st.multiselect("Город", options=cities, default=cities, key="nav_cities")

        years = sorted(int(y) for y in projects["investment_year"].dropna().unique() if y > 0)
        selected_years = st.multiselect("Год", options=years, default=years, key="nav_years")

        types = sorted(projects["investment_type"].dropna().astype(str).unique().tolist())
        selected_types = st.multiselect("Тип вложений", options=types, default=types, key="nav_types")

        needs_options = sorted({n for s in projects["needs"] for n in str(s).split(", ") if n})
        selected_needs = st.multiselect("Потребности", options=needs_options, default=[], key="nav_needs")

        amounts = projects["amount_rub"].dropna()
        amount_range = (0.0, 0.0)
        if not amounts.empty:
            amin, amax = float(amounts.min()), float(amounts.max())
            if amin < amax:
                amount_range = st.slider("Стоимость, ₽", int(amin), int(amax), (int(amin), int(amax)), step=max(1, int((amax-amin)/100)), key="nav_amount")
            else:
                st.caption(f"Стоимость всех проектов: {_fmt_money(amin)}")

    return {
        "search": search, "stages": selected_stages, "industries": selected_industries,
        "companies": selected_companies, "regions": selected_regions, "cities": selected_cities,
        "years": selected_years, "types": selected_types, "needs": selected_needs, "amount_range": amount_range,
    }


def _apply_filters(projects: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    if projects.empty: return projects
    mask = pd.Series(True, index=projects.index)
    if filters["stages"]: mask &= projects["stage"].isin(filters["stages"])
    if filters["industries"]: mask &= projects["industry_ru"].isin(filters["industries"])
    if filters["companies"]: mask &= projects["company_name"].isin(filters["companies"])
    if filters["regions"]: mask &= projects["region_ru"].isin(filters["regions"])
    if filters["cities"]: mask &= projects["city"].isin(filters["cities"])
    if filters["years"]: mask &= projects["investment_year"].isin(filters["years"])
    if filters["types"]: mask &= projects["investment_type"].isin(filters["types"])
    if filters["needs"]:
        mask &= projects["needs"].apply(lambda text: isinstance(text, str) and any(n in text for n in filters["needs"]))
    if filters["amount_range"] != (0.0, 0.0):
        mask &= projects["amount_rub"].between(filters["amount_range"][0], filters["amount_range"][1], inclusive="both")
    query = filters["search"].strip().lower()
    if query:
        haystack = (projects["project_name"].fillna("") + " " + projects["company_name"].fillna("")).astype(str).str.lower()
        mask &= haystack.str.contains(query, regex=False)
    return projects.loc[mask].reset_index(drop=True)


# ============================================================================
# KPI
# ============================================================================

def _render_kpi(projects: pd.DataFrame, warning_msg: str | None) -> None:
    if projects.empty:
        st.info("По заданным условиям проекты не найдены.")
        return

    counts = projects["stage"].value_counts()
    total_amount = float(projects["amount_rub"].sum())
    est_it_budget = projects.apply(_get_estimated_budget, axis=1).sum()

    kpi = st.columns(5)
    kpi[0].metric("Всего проектов", _fmt_int(len(projects)))
    kpi[1].metric("Проектирование", _fmt_int(int(counts.get(STAGE_PROJECT, 0))))
    kpi[2].metric("Строительство", _fmt_int(int(counts.get(STAGE_BUILD, 0))))
    kpi[3].metric("Запуск", _fmt_int(int(counts.get(STAGE_LAUNCH, 0))))
    kpi[4].metric("Потенциал ИТ (оценка)", _fmt_money(est_it_budget), help="Расчетная сумма, которую рынок готов потратить на ИТ и связь в этих проектах")

    st.caption(f"Общий объем инвестиций в выборке: **{_fmt_money(total_amount)}**. Показатели обновляются в соответствии с фильтрами.")
    
    if warning_msg:
        st.caption(f"ℹ️ {warning_msg}")


# ============================================================================
# Вкладка 1: Таймлайн + Топ-3
# ============================================================================

def _render_timeline(projects: pd.DataFrame) -> None:
    if projects.empty: return

    data = projects[projects["investment_year"] > 0].copy()
    if data.empty:
        st.info("В выборке нет проектов с указанным годом вложений.")
    else:
        data["size"] = data["amount_rub"].clip(lower=1).apply(lambda v: max(8.0, min(50.0, v / 2_500_000)))
        data = data.sort_values(["investment_year", "amount_rub"]).reset_index(drop=True)
        
        data["x_jitter"] = 0.0
        for year, group in data.groupby("investment_year"):
            n = len(group)
            if n > 1:
                offsets = [((i / (n - 1)) - 0.5) * 0.6 for i in range(n)]
                for idx, offset in zip(group.index, offsets):
                    data.at[idx, "x_jitter"] = offset

        data["x_val"] = data["investment_year"] + data["x_jitter"]

        figure = px.scatter(
            data, x="x_val", y="amount_rub", color="stage", size="size", hover_name="project_name",
            hover_data={"company_name": True, "region_ru": True, "amount_rub": ":,.0f", "stage": True, "investment_year": True, "size": False, "x_val": False, "x_jitter": False},
            color_discrete_map=STAGE_COLORS, labels={"x_val": "Год", "amount_rub": "Сумма, ₽", "stage": "Стадия", "project_name": "Проект", "company_name": "Инициатор", "region_ru": "Регион", "investment_year": "Год"}
        )
        figure.update_layout(height=420, margin={"l": 10, "r": 20, "t": 20, "b": 10}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"family": "Segoe UI, sans-serif", "size": 12, "color": RT_NAVY}, showlegend=True, legend={"orientation": "h", "yanchor": "bottom", "y": -0.2})
        
        years = sorted(data["investment_year"].unique().tolist())
        figure.update_xaxes(tickmode="array", tickvals=years, ticktext=[str(y) for y in years], range=[min(years) - 0.8, max(years) + 0.8], showgrid=True, gridcolor=RT_BORDER, zeroline=False)
        figure.update_yaxes(tickformat="~s", showgrid=True, gridcolor=RT_BORDER, zeroline=False)
        st.plotly_chart(figure, use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("---")
    st.markdown(f'<div class="nav-section-title">{icon_svg("emoji_events")} Топ-3 проекта</div>', unsafe_allow_html=True)
    top3 = projects.nlargest(3, "amount_rub")
    if not top3.empty:
        cols = st.columns(3)
        for idx, (_, row) in enumerate(top3.iterrows()):
            with cols[idx]:
                st.metric(label=row["project_name"], value=_fmt_money(row["amount_rub"]), delta=row["industry_ru"], delta_color="off")
                st.caption(f"Инициатор: {row['company_name']} · {row['region_ru']}")


# ============================================================================
# Вкладка 2: Анализ потребностей (Рынок)
# ============================================================================

def _render_market_needs(projects: pd.DataFrame) -> None:
    st.markdown(f'<div class="nav-section-title">{icon_svg("insights")} Потенциал рынка</div>', unsafe_allow_html=True)
    st.caption("Оценка того, сколько денег в текущей выборке проектов потенциально приходится на различные ИТ-услуги.")
    
    if projects.empty:
        st.info("Нет данных для анализа.")
        return

    records = _get_distributed_budgets(projects)
    df_needs = pd.DataFrame(records)
    
    if df_needs.empty:
        st.info("Для текущих проектов не удалось определить потребности.")
        return

    agg_needs = df_needs.groupby('need_list')['budget'].sum().reset_index().sort_values('budget', ascending=True)
    fig = px.bar(
        agg_needs, x='budget', y='need_list', orientation='h', text='budget',
        color='need_list', color_discrete_sequence=BRAND_PALETTE,
        labels={'budget': 'Оценка бюджета, ₽', 'need_list': 'Потребность'}
    )
    fig.update_traces(texttemplate='%{text:,.0f} ₽', textposition='outside', cliponaxis=False)
    fig.update_layout(height=350, margin={"l": 10, "r": 30, "t": 20, "b": 10}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    fig.update_xaxes(tickformat="~s", showgrid=True, gridcolor=RT_BORDER, zeroline=False)
    fig.update_yaxes(showgrid=False)
    
    st.markdown("##### Распределение потенциального бюджета по услугам")
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    st.markdown("##### Матрица потребностей по отраслям")
    st.caption("Суммы указаны в млн ₽. Показывает, в каких отраслях сосредоточен спрос на конкретные услуги.")
    
    pivot = pd.pivot_table(
        df_needs, values='budget', index='industry_ru', columns='need_list', 
        aggfunc='sum', fill_value=0
    ) / 1_000_000
    
    st.dataframe(pivot.style.format("{:.1f}"), use_container_width=True)


# ============================================================================
# Вкладка 3: Карточка проекта
# ============================================================================

def _render_project_card(projects: pd.DataFrame) -> None:
    if projects.empty: return

    st.markdown(f'<div class="nav-section-title">{icon_svg("description")} Карточка проекта</div>', unsafe_allow_html=True)
    
    options = {f"{row['project_name']} · {row['company_name']} (ID: {row['investment_id']})": row["investment_id"] for _, row in projects.iterrows()}
    choice = st.selectbox("Выберите проект (начните вводить название для поиска)", options=list(options.keys()), key="nav_card_project_select")
    
    if not choice: return
    
    project_df = projects[projects["investment_id"] == options[choice]]
    if project_df.empty:
        st.warning("Не удалось загрузить данные выбранного проекта. Пожалуйста, обновите страницу.")
        return
        
    project = project_df.iloc[0]

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown(f"**{project['project_name']}**")
        st.markdown(f"Инициатор: {project['company_name']}")
        st.markdown(f"Отрасль: {project['industry_ru']}")
        st.markdown(f"Регион: {project['region_ru']}")
        st.markdown(f"Город: {project['city'] if project['city'] else '—'}")

    with col_right:
        st.markdown(f"Стадия: **{project['stage']}**")
        st.markdown(f"Тип вложений: {project['investment_type']}")
        st.markdown(f"Год: {int(project['investment_year']) if project['investment_year'] else '—'}")
        st.markdown(f"Сумма инвестиций: **{_fmt_money(project['amount_rub'])}**")
        
        est = _get_estimated_budget(project)
        st.markdown(f"Оценка бюджета на ИТ: **{_fmt_money(est)}**")

    if project["object_type_guess"]:
        st.caption(f"Предположительный тип объекта: **{project['object_type_guess']}**.")

    st.markdown("**Потенциальные потребности в услугах Ростелекома**")
    reasons = project["needs_reasons"]
    if isinstance(reasons, list) and reasons:
        for item in reasons:
            # Убрали проценты, чтобы не сбивать пользователя с толку (П.1)
            st.markdown(f"- **{item['need']}** — *{item['reason']}*")
        st.caption("Оценка доли бюджета является экспертной и носит ознакомительный характер.")
    else:
        st.info("В открытых источниках недостаточно данных для определения потребностей.")


# ============================================================================
# Вкладка 4: Поиск по параметрам
# ============================================================================

def _render_search_by_params(projects: pd.DataFrame) -> None:
    st.markdown(f'<div class="nav-section-title">{icon_svg("search")} Поиск по параметрам</div>', unsafe_allow_html=True)
    st.caption("Выберите критерии и нажмите «Применить», чтобы отфильтровать проекты.")

    if projects.empty: return

    with st.form("param_search_form"):
        col1, col2, col3 = st.columns(3)
        industries = sorted(projects["industry_ru"].dropna().unique().tolist())
        regions = sorted(projects["region_ru"].dropna().unique().tolist())
        stages = [s for s in STAGE_ORDER if s in set(projects["stage"])]
        
        with col1: sel_ind = st.selectbox("Отрасль", ["(любая)"] + industries)
        with col2: sel_reg = st.selectbox("Регион", ["(любой)"] + regions)
        with col3: sel_stage = st.selectbox("Стадия", ["(любая)"] + stages)

        submitted = st.form_submit_button("Применить фильтры", type="primary", use_container_width=True)

    if submitted:
        st.session_state["param_search_applied"] = True
        st.session_state["param_search_data"] = {
            "industry": sel_ind,
            "region": sel_reg,
            "stage": sel_stage
        }

    if not st.session_state.get("param_search_applied"): return

    applied = st.session_state.get("param_search_data", {})
    mask = pd.Series(True, index=projects.index)
    if applied.get("industry", "(любая)") != "(любая)": mask &= projects["industry_ru"] == applied["industry"]
    if applied.get("region", "(любой)") != "(любой)": mask &= projects["region_ru"] == applied["region"]
    if applied.get("stage", "(любая)") != "(любая)": mask &= projects["stage"] == applied["stage"]
    results = projects.loc[mask]

    st.markdown(f"**Найдено: {len(results)}**")

    for _, row in results.head(10).iterrows():
        with st.container():
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{row['project_name']}**")
                st.caption(f"{row['company_name']} · {row['region_ru']}")
            with c2:
                st.markdown(f"**{_fmt_money(row['amount_rub'])}**")
            with st.expander("Детали"):
                st.write(f"Потребности: {row['needs']}")
                st.write(f"Оценка бюджета ИТ: {_fmt_money(_get_estimated_budget(row))}")
            st.markdown("---")


# ============================================================================
# Вкладка 5: Таблица
# ============================================================================

def _render_table(projects: pd.DataFrame) -> None:
    if projects.empty: return

    sort_options = {"По сумме (убывание)": ("amount_rub", False), "По названию": ("project_name", True)}
    sort_choice = st.selectbox("Сортировка", options=list(sort_options), key="nav_sort")
    sort_col, asc = sort_options[sort_choice]
    sorted_df = projects.sort_values(sort_col, ascending=asc, na_position="last")

    display = sorted_df[[
        "investment_id", "project_name", "company_name", "industry_ru",
        "region_ru", "stage", "amount_rub", "needs",
    ]].rename(columns={
        "investment_id": "ID", "project_name": "Проект", "company_name": "Инициатор",
        "industry_ru": "Отрасль", "region_ru": "Регион", "stage": "Стадия",
        "amount_rub": "Сумма, ₽", "needs": "Потребности"
    })
    st.dataframe(display, hide_index=True, use_container_width=True)
    st.download_button("Скачать CSV", data=display.to_csv(index=False).encode("utf-8-sig"), file_name="navigator_projects.csv", mime="text/csv", icon=":material/download:")


# ============================================================================
# Главный рендер
# ============================================================================

def render_navigator() -> None:
    st.markdown(NAV_CSS, unsafe_allow_html=True)
    st.caption("Анализ инвестиционных проектов и оценка потенциального спроса на ИТ-услуги. Данные из открытых источников.")

    projects, projects_demo, warning_msg = load_projects()
    if projects_demo: st.warning("Данные временно недоступны.")
    
    filters = _render_filters(projects)
    filtered = _apply_filters(projects, filters)

    _render_kpi(filtered, warning_msg)

    if projects.empty or filtered.empty:
        return

    tabs = st.tabs([
        ":material/timeline: Таймлайн",
        ":material/insights: Потребности рынка",
        ":material/description: Карточка проекта",
        ":material/search: Поиск по параметрам",
        ":material/table_view: Таблица",
    ])

    with tabs[0]: _render_timeline(filtered)
    with tabs[1]: _render_market_needs(filtered)
    with tabs[2]: _render_project_card(filtered)
    with tabs[3]: _render_search_by_params(filtered)
    with tabs[4]: _render_table(filtered)

#: Алиасы
render_invest_navigator = render_navigator
show_navigator = render_navigator
render = render_navigator

if __name__ == "__main__":
    st.set_page_config(page_title="Инвестиционный навигатор", page_icon=":material/business_center:", layout="wide")
    render_navigator()
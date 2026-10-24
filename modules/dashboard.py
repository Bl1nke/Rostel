"""Сводная панель коммерческого блока — первый экран портала «Ростелеком Коммерческий».

Модуль реализует точку входа ``render()`` для раздела «Сводный дашборд»:

* фирменный заголовок первого экрана и четыре KPI-метрики коммерческого блока;
* donut «Распределение по отраслям» и горизонтальный bar «Инвест-проекты по стадиям»;
* area-график «Динамика тендеров по месяцам» и таблица «Топ-5 сделок».

Данные берутся из ``data/*.csv``; пока файл пуст или отсутствует, модуль
показывает детерминированный демо-набор, чтобы первый экран не был пустым.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:  # при импорте из app.py (пакет modules доступен)
    from modules.icons import icon_svg
except ImportError:  # при запуске отдельно: streamlit run modules/dashboard.py
    from icons import icon_svg

# ---------------------------------------------------------------------------
# Константы: пути, брендбук, цвета графиков
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

RT_ORANGE = "#FF4F12"
RT_BLUE = "#4A90D9"
RT_PURPLE = "#7A2E8E"
RT_NAVY = "#1B1B2F"

#: Фирменная палитра Ростелекома для круговой диаграммы.
BRAND_PALETTE: tuple[str, ...] = (
    RT_ORANGE,
    RT_BLUE,
    RT_PURPLE,
    RT_NAVY,
    "#FF7A3D",
    "#E23E05",
    "#4B6CB7",
    "#8996C6",
    "#F2A63B",
    "#2E8B7F",
)

#: Цвета стадий инвест-проектов: «Стройка» — самая горячая зона (красный РТ).
STAGE_COLORS: dict[str, str] = {
    "Идея": "#8996C6",
    "Проектирование": "#4B6CB7",
    "Стройка": "#E30613",
    "Запуск": "#1F3C88",
    # «Негативные» состояния проекта — тоже показываем на графике стадий,
    # чтобы статусы вида Suspended/Cancelled не выпадали из картины.
    "Приостановлен": "#B08A00",
    "Отменён": "#8A8A99",
}
STAGE_ORDER: tuple[str, ...] = tuple(STAGE_COLORS)

#: Синонимы стадий и статусов проекта — если источник отдаёт их на английском.
STAGE_ALIASES: dict[str, str] = {
    "idea": "Идея",
    "concept": "Идея",
    "planned": "Идея",
    "planning": "Идея",
    "design": "Проектирование",
    "project": "Проектирование",
    "active": "Стройка",
    "in progress": "Стройка",
    "construction": "Стройка",
    "completed": "Запуск",
    "complete": "Запуск",
    "launched": "Запуск",
    "done": "Запуск",
    # Статусы, которые встречаются в data/investmensts.csv (status).
    "suspended": "Приостановлен",
    "on hold": "Приостановлен",
    "paused": "Приостановлен",
    "приостановлен": "Приостановлен",
    "приостановлено": "Приостановлен",
    "cancelled": "Отменён",
    "canceled": "Отменён",
    "отменён": "Отменён",
    "отменен": "Отменён",
    "отменено": "Отменён",
}

#: Цвет area-графика динамики тендеров и месяцы отчётного года.
AREA_COLOR = "#1F3C88"
MONTH_LABELS: tuple[str, ...] = (
    "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
    "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек",
)

#: Конфиг Plotly: прячем modebar, чтобы экран выглядел как готовый BI-продукт.
PLOTLY_CONFIG: dict[str, Any] = {"displayModeBar": False}

#: Единая высота блока нижнего ряда (график динамики и таблица Топ-5) — блоки встают ровно.
DASHBOARD_BLOCK_HEIGHT = 320

DASHBOARD_CSS = """
<style>
/* ---------- Заголовок первого экрана ---------- */
.main-header {
  margin: 0.1rem 0 0.35rem;
  font-size: 2.1rem;
  font-weight: 700;
  line-height: 1.15;
  color: var(--rt-navy, #1B1B2F);
}

.main-subheader {
  margin: 0 0 1.15rem;
  font-size: 1rem;
  color: var(--rt-muted, #6B6B80);
}

/* Дашборд рисует собственный hero, поэтому штатный заголовок раздела скрываем.
   CSS инжектится только этим модулем, т.е. действует лишь на странице дашборда. */
.rt-page-header { display: none; }

/* ---------- Заголовки блоков ---------- */
.dash-block-title {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin: 0 0 0.5rem;
  font-size: 1.02rem;
  font-weight: 700;
  color: var(--rt-navy, #1B1B2F);
}

.dash-block-title::before {
  content: "";
  width: 4px;
  height: 1.05rem;
  border-radius: 3px;
  background: linear-gradient(180deg, var(--rt-orange, #FF4F12), var(--rt-purple, #7A2E8E));
}

.dash-caption {
  margin-top: 0.9rem;
  font-size: 0.75rem;
  color: var(--rt-muted, #6B6B80);
}

/* ---------- Монохромные SVG-иконки ---------- */
.rt-icon-svg {
  width: 1em;
  height: 1em;
  display: inline-block;
  vertical-align: -0.15em;
  flex: 0 0 auto;
}

.dash-block-title .rt-icon-svg {
  width: 1.05rem;
  height: 1.05rem;
  color: var(--rt-orange, #FF4F12);
}

.main-header .rt-icon-svg {
  width: 1.7rem;
  height: 1.7rem;
  color: var(--rt-orange, #FF4F12);
  vertical-align: -0.28rem;
  margin-right: 0.25rem;
}

.dash-caption .rt-icon-svg {
  width: 0.95rem;
  height: 0.95rem;
  color: var(--rt-muted, #6B6B80);
  vertical-align: -0.18em;
  margin-right: 0.12rem;
}

@media (max-width: 768px) {
  .main-header { font-size: 1.45rem; }
}
</style>
"""

# ---------------------------------------------------------------------------
# Слой данных: чтение CSV, приведение к канонической схеме, демо-фолбэк
# ---------------------------------------------------------------------------
#: Регионы Юга России — совпадают с данными модуля «Радар присутствия».
DEMO_REGIONS: tuple[str, ...] = (
    "Rostov Oblast",
    "Krasnodar Krai",
    "Stavropol Krai",
    "Volgograd Oblast",
    "Astrakhan Oblast",
    "Republic of Adygea",
    "Republic of Kalmykia",
    "Republic of Crimea",
    "Sevastopol",
    "Kabardino-Balkar Republic",
)

#: В первых регионах списка есть компании без контрактов с РТ — это «белые пятна».
DEMO_WHITE_SPOT_REGIONS = 7

DEMO_INDUSTRIES: tuple[str, ...] = (
    "IT Infrastructure",
    "Telecom Services",
    "Retail",
    "Manufacturing",
    "Logistics",
    "Construction",
    "Finance",
    "Healthcare",
)
DEMO_INDUSTRY_WEIGHTS: tuple[int, ...] = (26, 22, 16, 14, 9, 7, 4, 2)

DEMO_COMPANY_NAMES: tuple[str, ...] = (
    "Alpha Ltd",
    "Beta GmbH",
    "Gamma AG",
    "Delta Solutions",
    "Northstar Ltd",
    "Urban Trade GmbH",
    "Greenline Services",
    "Central Works AG",
    "Westfield Group",
    "Helio Systems",
    "Metro Business Ltd",
    "Future Tech GmbH",
    "Azov Steel Works",
    "Kuban Agro Holding",
    "Southern Logistics LLC",
    "Don Digital Group",
)

DEMO_TENDER_TITLES: tuple[str, ...] = (
    "Supply of server and network equipment",
    "Corporate CRM system development",
    "Warehouse logistics modernisation",
    "Cloud migration services",
    "Cybersecurity audit and consulting",
    "Data analytics platform rollout",
    "Smart city infrastructure project",
    "Fiber optic backbone expansion",
    "Contact centre modernisation",
    "Data centre construction",
    "Unified communications platform",
    "Mobile application development",
)

#: Строковые значения, которые считаем «истиной» при чтении флагов из CSV.
_TRUE_VALUES = {"true", "1", "yes", "y", "да", "клиент", "current", "active", "действующий"}


def _read_csv(*file_names: str) -> pd.DataFrame | None:
    """Читает первый существующий непустой CSV из каталога ``data/``.

    Args:
        *file_names: Имена файлов-кандидатов в порядке приоритета.

    Returns:
        DataFrame с данными или ``None``, если все кандидаты пусты/отсутствуют.
    """
    for file_name in file_names:
        path = DATA_DIR / file_name
        try:
            if not path.is_file() or path.stat().st_size == 0:
                continue
            data = pd.read_csv(path)
        except (OSError, ValueError, UnicodeDecodeError):
            # Пустой или битый файл — переходим к следующему кандидату.
            continue
        if not data.empty:
            return data
    return None


def _first_column(data: pd.DataFrame, *candidates: str) -> str | None:
    """Ищет колонку по списку алиасов (регистр и лишние пробелы не важны)."""
    by_name = {str(column).strip().lower(): column for column in data.columns}
    for candidate in candidates:
        found = by_name.get(candidate.strip().lower())
        if found is not None:
            return found
    return None


def _to_text_series(series: pd.Series, default: str) -> pd.Series:
    """Приводит колонку к тексту, подставляя значение по умолчанию вместо пустых."""
    text = series.fillna("").astype(str).str.strip()
    return text.mask(text == "", default)


def _to_bool_series(series: pd.Series) -> pd.Series:
    """Приводит колонку-признак к ``bool`` (поддерживает bool, 0/1 и строки)."""
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(bool)
    return series.fillna("").astype(str).str.strip().str.lower().isin(_TRUE_VALUES)


def _normalise_stage(value: Any) -> str:
    """Приводит стадию инвест-проекта к каноническому названию."""
    stage = str(value).strip()
    if not stage or stage.lower() in {"nan", "none", "<na>"}:
        return STAGE_ORDER[0]
    if stage in STAGE_COLORS:
        return stage
    return STAGE_ALIASES.get(stage.lower(), stage)


def _spread_months(count: int) -> list[int]:
    """Детерминированно раскладывает ``count`` записей по 12 месяцам года."""
    return [index % len(MONTH_LABELS) for index in range(count)]


def _month_index(series: pd.Series) -> pd.Series:
    """Преобразует колонку с датой в индекс месяца (0..11) для графика динамики."""
    parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    months = parsed.dt.month
    if months.notna().sum() == 0:
        return pd.Series(_spread_months(len(series)), index=series.index)
    return months.fillna(1).astype(int).sub(1).clip(lower=0, upper=len(MONTH_LABELS) - 1)


def _demo_companies(count: int = 250, seed: int = 42) -> pd.DataFrame:
    """Детерминированный демо-набор компаний (пока ``data/companies.csv`` пуст)."""
    rng = random.Random(seed)
    industries = rng.choices(DEMO_INDUSTRIES, weights=DEMO_INDUSTRY_WEIGHTS, k=count)
    per_region = max(count // len(DEMO_REGIONS), 1)
    rows: list[dict[str, Any]] = []
    cursor = 0
    for region_index, region in enumerate(DEMO_REGIONS):
        for position in range(per_region):
            rows.append(
                {
                    "industry": industries[cursor % count],
                    "region": region,
                    # Часть компаний в первых регионах ещё не клиент РТ.
                    "is_rt_client": not (
                        region_index < DEMO_WHITE_SPOT_REGIONS and position % 3 == 0
                    ),
                }
            )
            cursor += 1
    return pd.DataFrame(rows)


def _demo_tenders(count: int = 50, seed: int = 7) -> pd.DataFrame:
    """Детерминированный демо-набор из 50 тендеров, разложенных по 12 месяцам 2025."""
    rng = random.Random(seed)
    amounts = rng.sample(range(15_000_000, 260_000_000, 500_000), k=min(count, 490))
    rows: list[dict[str, Any]] = []
    for index in range(count):
        rows.append(
            {
                "name": DEMO_COMPANY_NAMES[index % len(DEMO_COMPANY_NAMES)],
                "title": DEMO_TENDER_TITLES[index % len(DEMO_TENDER_TITLES)],
                "region": DEMO_REGIONS[index % len(DEMO_REGIONS)],
                "amount": float(amounts[index % len(amounts)]),
                "month": index % len(MONTH_LABELS),
            }
        )
    return pd.DataFrame(rows)


def _demo_investments(count: int = 12, seed: int = 21) -> pd.DataFrame:
    """Детерминированный демо-набор инвест-проектов по стадиям."""
    rng = random.Random(seed)
    plan = (
        [STAGE_ORDER[0]] * 4
        + [STAGE_ORDER[1]] * 3
        + [STAGE_ORDER[2]] * 3
        + [STAGE_ORDER[3]] * 2
    )
    rng.shuffle(plan)
    rows: list[dict[str, Any]] = [
        {
            "stage": plan[index % len(plan)],
            "volume": float(rng.randrange(250_000_000, 1_850_000_000, 10_000_000)),
        }
        for index in range(count)
    ]
    return pd.DataFrame(rows)


@st.cache_data(ttl=30, show_spinner=False)
def _load_companies() -> tuple[pd.DataFrame, bool]:
    """Возвращает компании в канонической схеме (industry, region, is_rt_client).

    Returns:
        Кортеж «данные, признак демо-режима».
    """
    raw = _read_csv("companies.csv")
    if raw is None:
        return _demo_companies(), True

    industry = _first_column(raw, "industry", "sector", "отрасль", "category")
    region = _first_column(raw, "region", "регион", "city", "город", "territory")
    rt_flag = _first_column(raw, "is_rt_client", "rt_client", "is_client")
    status = _first_column(raw, "customer_status", "client_status", "status")

    data = pd.DataFrame(index=raw.index)
    data["industry"] = _to_text_series(raw[industry], "Прочее") if industry else "Прочее"
    data["region"] = _to_text_series(raw[region], "Не указан") if region else "Не указан"
    if rt_flag is not None:
        data["is_rt_client"] = _to_bool_series(raw[rt_flag])
    elif status is not None:
        data["is_rt_client"] = _to_bool_series(raw[status])
    else:
        data["is_rt_client"] = True
    return data, False


@st.cache_data(ttl=30, show_spinner=False)
def _load_tenders() -> tuple[pd.DataFrame, bool]:
    """Возвращает тендеры в канонической схеме (name, region, amount, month)."""
    raw = _read_csv("tenders.csv")
    if raw is None:
        return _demo_tenders(), True

    name = _first_column(raw, "name", "title", "company", "customer", "название")
    region = _first_column(raw, "region", "регион", "city", "город", "territory")
    amount = _first_column(raw, "amount", "budget_rub", "amount_rub", "budget", "сумма")
    date = _first_column(raw, "publication_date", "date", "month", "deadline", "дата")

    data = pd.DataFrame(index=raw.index)
    data["name"] = (
        _to_text_series(raw[name], "Сделка без названия") if name else "Сделка без названия"
    )
    data["region"] = _to_text_series(raw[region], "Не указан") if region else "Не указан"
    data["amount"] = pd.to_numeric(raw[amount], errors="coerce") if amount else 0.0
    data["amount"] = data["amount"].fillna(0.0).astype(float)
    data["month"] = _month_index(raw[date]) if date else _spread_months(len(data))
    return data, False


@st.cache_data(ttl=30, show_spinner=False)
def _load_investments() -> tuple[pd.DataFrame, bool]:
    """Возвращает инвест-проекты в канонической схеме (stage, volume)."""
    raw = _read_csv("investments.csv", "investmensts.csv")
    if raw is None:
        return _demo_investments(), True

    stage = _first_column(raw, "stage", "стадия", "project_stage", "status")
    volume = _first_column(raw, "volume", "amount_rub", "amount", "budget_rub", "сумма")

    data = pd.DataFrame(index=raw.index)
    data["stage"] = raw[stage].map(_normalise_stage) if stage else STAGE_ORDER[0]
    data["volume"] = pd.to_numeric(raw[volume], errors="coerce") if volume else 0.0
    data["volume"] = data["volume"].fillna(0.0).astype(float)
    return data, False


# ---------------------------------------------------------------------------
# Форматирование чисел
# ---------------------------------------------------------------------------
def _fmt_int(value: float | int) -> str:
    """Форматирует целое число с пробелами как разделителями тысяч."""
    return f"{int(round(value)):,}".replace(",", " ")


def _fmt_rub_short(value: float) -> str:
    """Форматирует сумму в ₽, подбирая единицы (млрд/млн/тыс) по величине."""
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.1f}".replace(",", " ") + " млрд ₽"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.1f}".replace(",", " ") + " млн ₽"
    if abs(value) >= 1_000:
        return f"{value / 1_000:,.1f}".replace(",", " ") + " тыс ₽"
    return _fmt_int(value) + " ₽"


def _fmt_millions(value: float) -> str:
    """Форматирует сумму в миллионах рублей (для таблицы сделок)."""
    return f"{value / 1_000_000:,.1f}".replace(",", " ") + " млн ₽"


# ---------------------------------------------------------------------------
# Графики
# ---------------------------------------------------------------------------
def _base_layout(height: int) -> dict[str, Any]:
    """Единое оформление графиков: прозрачный фон под карточку портала, без легенды."""
    return {
        "height": height,
        "margin": {"l": 10, "r": 26, "t": 18, "b": 10},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Segoe UI, Inter, Roboto, sans-serif", "size": 12, "color": RT_NAVY},
        "showlegend": False,
        "hoverlabel": {
            "bgcolor": "#FFFFFF",
            "bordercolor": "#ECE8F5",
            "font": {"color": RT_NAVY, "size": 12},
        },
    }


def _industry_figure(data: pd.DataFrame) -> go.Figure:
    """Donut «Распределение по отраслям»: hole=0.4, подписи percent+label, без легенды."""
    counts = data["industry"].value_counts()
    colors = [BRAND_PALETTE[index % len(BRAND_PALETTE)] for index in range(len(counts))]
    figure = go.Figure(
        go.Pie(
            labels=counts.index.tolist(),
            values=counts.to_numpy(),
            hole=0.4,
            sort=True,
            textinfo="percent+label",
            textposition="inside",
            insidetextorientation="radial",
            marker={"colors": colors, "line": {"color": "#FFFFFF", "width": 2}},
            hovertemplate=(
                "<b>%{label}</b><br>Компаний: %{value}<br>Доля: %{percent}<extra></extra>"
            ),
        )
    )
    figure.update_layout(**_base_layout(height=380))
    return figure


def _stage_figure(data: pd.DataFrame) -> go.Figure:
    """Горизонтальный bar «Инвест-проекты по стадиям» с цветами по стадиям."""
    counts = data["stage"].value_counts()
    stages = [stage for stage in STAGE_ORDER if stage in counts.index]
    stages += [stage for stage in counts.index if stage not in STAGE_ORDER]
    values = [int(counts[stage]) for stage in stages]
    colors = [
        STAGE_COLORS.get(stage, BRAND_PALETTE[index % len(BRAND_PALETTE)])
        for index, stage in enumerate(stages)
    ]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=stages,
            orientation="h",
            marker={"color": colors, "line": {"width": 0}},
            text=[_fmt_int(value) for value in values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>Проектов: %{x}<extra></extra>",
        )
    )
    figure.update_layout(**_base_layout(height=380))
    figure.update_xaxes(
        title_text="Количество проектов",
        showgrid=True,
        gridcolor="#ECE8F5",
        zeroline=False,
        dtick=1,
        rangemode="tozero",
    )
    figure.update_yaxes(autorange="reversed", showgrid=False, title_text=None)
    return figure


def _dynamics_figure(data: pd.DataFrame) -> go.Figure:
    """Area-график «Динамика тендеров по месяцам» (сумма сделок в ₽)."""
    monthly = (
        data.groupby("month")["amount"].sum().reindex(range(len(MONTH_LABELS)), fill_value=0.0)
    )
    figure = go.Figure(
        go.Scatter(
            x=list(MONTH_LABELS),
            y=monthly.to_numpy(),
            mode="lines+markers",
            line={"color": AREA_COLOR, "width": 3, "shape": "spline", "smoothing": 0.6},
            marker={"size": 8, "color": AREA_COLOR, "line": {"color": "#FFFFFF", "width": 2}},
            fill="tozeroy",
            fillcolor="rgba(31, 60, 136, 0.16)",
            customdata=[_fmt_int(value) + " ₽" for value in monthly.tolist()],
            hovertemplate="<b>%{x}</b><br>Сумма: %{customdata}<extra></extra>",
        )
    )
    figure.update_layout(**_base_layout(height=DASHBOARD_BLOCK_HEIGHT))
    figure.update_xaxes(title_text="Месяц", showgrid=False)
    figure.update_yaxes(
        title_text="Сумма, ₽",
        showgrid=True,
        gridcolor="#ECE8F5",
        zeroline=False,
        tickformat="~s",
    )
    return figure


def _top_deals_frame(data: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    """Топ сделок с колонками «Компания», «Регион», «Сумма»."""
    top = data.nlargest(limit, "amount")[["name", "region", "amount"]].copy()
    top = top.rename(columns={"name": "Компания", "region": "Регион", "amount": "Сумма"})
    top["Сумма"] = top["Сумма"].map(_fmt_millions)
    return top.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Отрисовка
# ---------------------------------------------------------------------------
def _block_title(icon: str, text: str) -> None:
    """Рисует заголовок блока в едином стиле дашборда.

    ``icon`` — имя монохромной SVG-иконки из :mod:`modules.icons`.
    """
    st.markdown(
        f'<div class="dash-block-title">{icon_svg(icon)}<span>{text}</span></div>',
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    """Рисует заголовок первого экрана (класс .main-header из ТЗ)."""
    st.markdown(
        f"""
        <h1 class="main-header">{icon_svg("dashboard")} Сводная панель коммерческого блока</h1>
        <p class="main-subheader">Обзор ключевых показателей и точек роста</p>
        """,
        unsafe_allow_html=True,
    )


def _render_kpis(
    companies: pd.DataFrame, tenders: pd.DataFrame, investments: pd.DataFrame
) -> None:
    """Блок из четырёх KPI-метрик коммерческого блока."""
    revenue_potential = float(tenders["amount"].sum()) + float(investments["volume"].sum())
    white_spots = int(companies.loc[~companies["is_rt_client"], "region"].nunique())

    columns = st.columns(4)
    with columns[0]:
        st.metric(
            "Компаний в базе",
            _fmt_int(len(companies)),
            delta="+12%",
            icon=":material/apartment:",
            help="data/companies.csv · len(df_companies)",
        )
    with columns[1]:
        st.metric(
            "Активных тендеров",
            _fmt_int(len(tenders)),
            delta="+5 новых",
            icon=":material/assignment:",
            help="data/tenders.csv · len(df_tenders)",
        )
    with columns[2]:
        st.metric(
            "Потенциал выручки",
            _fmt_rub_short(revenue_potential),
            delta="+8%",
            icon=":material/paid:",
            help="tenders.amount + investments.volume, авто-единицы",
        )
    with columns[3]:
        st.metric(
            "Белых пятен",
            _fmt_int(white_spots),
            delta="Требуют внимания",
            delta_color="inverse",
            delta_arrow="off",
            icon=":material/location_off:",
            help="Регионы без клиентов РТ: companies[~is_rt_client].region.nunique()",
        )


def _render_demo_note(companies_demo: bool, tenders_demo: bool, investments_demo: bool) -> None:
    """Показывает подсказку, если данные пришлось сгенерировать."""
    empty_sources = [
        name
        for name, is_demo in (
            ("data/companies.csv", companies_demo),
            ("data/tenders.csv", tenders_demo),
            ("data/investmensts.csv", investments_demo),
        )
        if is_demo
    ]
    if not empty_sources:
        return
    st.markdown(
        f'<div class="dash-caption">{icon_svg("info")}Демо-режим: '
        + " · ".join(empty_sources)
        + " — файл пуст или в нём нет нужных колонок, показан сгенерированный набор.</div>",
        unsafe_allow_html=True,
    )


def render() -> None:
    """Отрисовывает сводную панель коммерческого блока (точка входа app.py)."""
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

    companies, companies_demo = _load_companies()
    tenders, tenders_demo = _load_tenders()
    investments, investments_demo = _load_investments()

    _render_header()
    _render_kpis(companies, tenders, investments)

    st.markdown("---")
    industry_column, stage_column = st.columns(2)
    with industry_column:
        _block_title("pie_chart", "Распределение по отраслям")
        st.plotly_chart(_industry_figure(companies), width="stretch", config=PLOTLY_CONFIG)
    with stage_column:
        _block_title("construction", "Инвест-проекты по стадиям")
        st.plotly_chart(_stage_figure(investments), width="stretch", config=PLOTLY_CONFIG)

    st.markdown("---")
    dynamics_column, deals_column = st.columns(2)
    with dynamics_column:
        _block_title("trending_up", "Динамика тендеров по месяцам")
        st.plotly_chart(_dynamics_figure(tenders), width="stretch", config=PLOTLY_CONFIG)
    with deals_column:
        _block_title("emoji_events", "Топ-5 сделок")
        st.dataframe(
            _top_deals_frame(tenders),
            width="stretch",
            hide_index=True,
            height=DASHBOARD_BLOCK_HEIGHT,
        )

    _render_demo_note(companies_demo, tenders_demo, investments_demo)


# Точки входа, которые ожидает app.py (см. PAGES и _resolve_renderer).
render_dashboard = render
show_dashboard = render


if __name__ == "__main__":
    # Позволяет проверить дашборд отдельно: streamlit run modules/dashboard.py
    # При импорте из app.py (__name__ == "modules.dashboard") этот блок не выполняется,
    # поэтому единственный вызов st.set_page_config в app.py не конфликтует.
    st.set_page_config(
        page_title="Ростелеком | Сводный дашборд",
        page_icon=":material/dashboard:",
        layout="wide",
    )
    render()


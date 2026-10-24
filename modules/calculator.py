"""Калькулятор сделок.

Модуль отвечает за вычислительную логику расчёта стоимости проекта и сопутствующих метрик.  Он не занимается выводом данных в UI – это делает Streamlit‑модуль «calculator», а только возвращает чистый результат, который может использовать любой другой модуль (экспорт, отчётность и т.д.).

Функция :func:`calculate` принимает словарь с параметрами проекта и выдаёт структуру вида::

    {
        "input_parameters": {...},            # копия входных данных
        "analog_projects": [...],             # список похожих проектов из investmensts.csv
        "min_price": Decimal,                # минимальная цена (руб.)
        "optimal_price": Decimal,            # оптимальная цена (руб.)
        "max_price": Decimal,                # максимальная цена (руб.)
        "margin_percent": float,             # ожидаемая маржинальность (%)
        "region_factor": float,              # коэффициент региона
        "urgency_premium_percent": float,    # надбавка за срочность
        "unique_solutions_premium_percent": float,  # надбавка за уникальные решения
    }

Параметры проекта:
```
{
    "project_name": str,
    "project_type": str,          # например: "IT Infrastructure"
    "scale_rub": int | float,      # ориентировочный бюджет (руб.)
    "region": str,                 # регион
    "deadline": str | None,        # ISO‑дата «YYYY-MM-DD» или ``None``
    "financing_scheme": str | None,# например: "CAPEX" или "OPEX"
    "works": list[str] | None,
    "equipment": list[str] | None,
    "software": list[str] | None,
    "urgency_days": int | None,   # число дней до дедлайна
    "unique_solutions": bool | None,
}
```
Все поля помимо обязательных считаются опциональными и при отсутствии принимают значения по умолчанию.

Алгоритм расчёта:
1.  Загружаем данные из каталога ``data/`` (investmensts.csv, region.json).
2.  Находим аналогичные проекты: совпадение региона и, при наличии, схемы финансирования.
3.  Из цен аналагов берём минимальную, максимальную и среднюю цену.
4.  Корректируем цены региональным коэффициентом (investment_climate_index).
5.  Прибавляем надбавки за срочность и уникальные решения.
6.  Оцениваем маржинальность как среднее значение ожидаемого ROI аналагов.
7.  Возвращаем результат в виде словаря, пригодного для дальнейшего экспорта.

Пример использования (псевдо‑код):
```
from modules.calculator import calculate
res = calculate({"project_type": "IT Infrastructure", "scale_rub": 5000000, "region": "Rostov Oblast"})
print(res["optimal_price"])
```
"""

from __future__ import annotations

import json
import pathlib
import datetime
from decimal import Decimal, getcontext
from typing import Any, Dict, List, Optional

import pandas as pd

# Настраиваем точность Decimal – 2 знака после запятой для денег.
getcontext().prec = 10

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REGION_JSON = DATA_DIR / "region.json"
INVESTMENTS_CSV = DATA_DIR / "investmensts.csv"

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _load_json(path: pathlib.Path) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[calculator] Не найден файл {path}")
        return []


def _load_csv(path: pathlib.Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8")
    except FileNotFoundError:
        print(f"[calculator] Не найден файл {path}")
        return pd.DataFrame()


def _region_factor(region_name: str) -> float:
    """Возвращает коэффициент региона по полю investment_climate_index.
    Если регион не найден – возвращается 1.0 (без корректировки)."""
    regions = _load_json(REGION_JSON)
    for r in regions:
        if r.get("name") == region_name:
            index = r.get("investment_climate_index", 50)  # базовый индекс 50
            return 1 + (index - 50) / 200  # диапазон примерно [0.75, 1.25]
    return 1.0


def _parse_deadline(deadline: Optional[str]) -> Optional[datetime.date]:
    if deadline is None:
        return None
    try:
        return datetime.datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        print(f"[calculator] Неверный формат даты: {deadline}. Ожидается YYYY-MM-DD")
        return None

# ---------------------------------------------------------------------------
# Основная функция расчёта
# ---------------------------------------------------------------------------

def calculate(params: Dict[str, Any]) -> Dict[str, Any]:
    """Рассчитывает стоимость проекта и связанные метрики.

    Параметры:
        params – словарь с входными данными.  Обязательные ключи:
            - project_type (строка)
            - scale_rub   (int|float) – ориентировочный бюджет
            - region      (строка)
    Остальные параметры считаются опциональными.

    Возвращает словарь, описанный в заголовке модуля.
    """

    # --- Валидация обязательных полей -------------------------------------
    required = ["project_type", "scale_rub", "region"]
    for key in required:
        if key not in params:
            raise ValueError(f"Параметр '{key}' обязателен для расчёта")

    project_type: str = str(params["project_type"]).strip()
    scale_rub: Decimal = Decimal(str(params["scale_rub"]))
    region_name: str = str(params["region"]).strip()

    # --- Загрузка данных ----------------------------------------------------
    investments_df = _load_csv(INVESTMENTS_CSV)

    # --- Поиск аналогов -----------------------------------------------------
    analogs = []  # список dict
    if not investments_df.empty:
        df = investments_df.copy()
        df["region"] = df["region"].astype(str).str.strip()
        mask = df["region"].eq(region_name)
        fin_scheme = params.get("financing_scheme")
        if fin_scheme:
            mask &= df["investment_type"].str.upper() == str(fin_scheme).upper()
        analog_df = df.loc[mask]
    else:
        analog_df = pd.DataFrame(columns=["investment_id", "company_name", "amount_rub", "investment_type", "status"])

    # --- Формируем список аналогов ------------------------------------------
    for _, row in analog_df.iterrows():
        try:
            amount = Decimal(str(row["amount_rub"]))
        except Exception:
            amount = Decimal(0)
        analogs.append(
            {
                "investment_id": str(row.get("investment_id", "")),
                "company_name": str(row.get("company_name", "")),
                "amount_rub": int(amount),
                "investment_type": str(row.get("investment_type", "")),
                "status": str(row.get("status", "")),
            }
        )

    # --- Расчёт цен --------------------------------------------------------
    if analogs:
        amounts = [Decimal(a["amount_rub"]) for a in analogs]
        min_price_raw = min(amounts)
        max_price_raw = max(amounts)
        avg_price_raw = sum(amounts) / Decimal(len(amounts))
    else:
        # Нет аналогов – используем масштаб проекта как ориентир
        min_price_raw = max_price_raw = avg_price_raw = scale_rub

    # --- Корректировка регионом --------------------------------------------
    region_factor_val = _region_factor(region_name)

    def adjust(price: Decimal) -> Decimal:
        price_adj = price * Decimal(str(region_factor_val))
        # Срочность
        deadline_str = params.get("deadline") or params.get("urgency_days")
        if deadline_str is not None:
            days_until_deadline = None
            if isinstance(deadline_str, int):
                days_until_deadline = deadline_str
            else:
                d = _parse_deadline(str(deadline_str))
                if d:
                    days_until_deadline = (d - datetime.date.today()).days
            if days_until_deadline is not None and 0 <= days_until_deadline <= 30:
                urgency_premium = Decimal(0.1) * Decimal((30 - days_until_deadline)) / Decimal(30)
                price_adj *= (Decimal(1) + urgency_premium)
        # Уникальные решения
        if params.get("unique_solutions"):
            price_adj *= Decimal(1.15)
        return price_adj.quantize(Decimal("1.") )  # округляем до рубля

    min_price = adjust(min_price_raw)
    optimal_price = adjust(avg_price_raw)
    max_price = adjust(max_price_raw)

    # --- Маржинальность -----------------------------------------------------
    if analogs:
        rois = [Decimal(str(row.get("expected_roi_percent", 0))) for row in analog_df.to_dict(orient="records")]
        margin_percent = float(sum(rois) / Decimal(len(rois))) if rois else 0.0
    else:
        margin_percent = 0.0

    # --- Итоговый результат -----------------------------------------------
    result: Dict[str, Any] = {
        "input_parameters": params,
        "analog_projects": analogs,
        "min_price_rub": int(min_price),
        "optimal_price_rub": int(optimal_price),
        "max_price_rub": int(max_price),
        "margin_percent": round(margin_percent, 2),
        "region_factor": round(region_factor_val, 3),
    }

    # Добавляем сведения о надбавках для прозрачности
    urgency_premium = None
    if params.get("deadline") or params.get("urgency_days"):
        days_until_deadline = None
        if isinstance(params.get("deadline"), int):
            days_until_deadline = params["deadline"]
        else:
            d = _parse_deadline(str(params.get("deadline")))
            if d:
                days_until_deadline = (d - datetime.date.today()).days
        if days_until_deadline is not None and 0 <= days_until_deadline <= 30:
            urgency_premium = round(10 * (30 - days_until_deadline) / 30, 2)
    result["urgency_premium_percent"] = urgency_premium or 0.0
    result["unique_solutions_premium_percent"] = 15.0 if params.get("unique_solutions") else 0.0

    return result

# ---------------------------------------------------------------------------
# Если модуль запущен напрямую, демонстрируем простую работу
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    example = {
        "project_name": "Система мониторинга",
        "project_type": "IT Infrastructure",
        "scale_rub": 5000000,
        "region": "Rostov Oblast",
        "deadline": "2026-04-15",
        "financing_scheme": "CAPEX",
        "unique_solutions": True,
    }
    res = calculate(example)
    print("Результат расчёта:")
    for k, v in res.items():
        print(f"{k}: {v}")


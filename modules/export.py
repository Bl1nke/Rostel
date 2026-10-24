"""Модуль экспорта результатов калькулятора.

Предоставляет простые функции для сохранения результата в CSV, подготовки коммерческого предложения по шаблону Docx и создания структуры данных, пригодной для импорта в CRM.  Файлы создаются в рабочей директории проекта; пользователь может изменить путь в аргументах функций.

Функции:
    * :func:`export_to_csv` – сохраняет словарь результата в CSV‑файл.
    * :func:`export_commercial_proposal` – заполняет шаблон ``templates/kp_templates.docx`` и сохраняет готовый документ.
    * :func:`prepare_crm_data` – превращает результат в словарь, соответствующий полям CRM (напр., Yandex.Taxi, AmoCRM).

Весь код написан без сторонних зависимостей, кроме того, что уже присутствует в ``requirements.txt``: pandas и docxtpl.
"""

from __future__ import annotations

import csv
import datetime
import pathlib
from typing import Any, Dict

import pandas as pd
from docxtpl import DocxTemplate

# ---------------------------------------------------------------------------
# Путь к шаблону коммерческого предложения (по умолчанию)
# ---------------------------------------------------------------------------
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE_PATH = BASE_DIR / "templates" / "kp_templates.docx"

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _flatten_dict(d: Dict[str, Any], parent_key: str = "") -> Dict[str, Any]:
    """Преобразует вложенный словарь в плоский с ключами вида ``parent_child``.

    Это удобно для заполнения шаблонов docx, где обычно используются простые переменные.
    """
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}_{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, new_key))
        elif isinstance(v, list):
            # Для списков сохраняем как строку JSON‑подобно
            items[new_key] = str(v)
        else:
            items[new_key] = v
    return items

# ---------------------------------------------------------------------------
# Экспорт в CSV
# ---------------------------------------------------------------------------

def export_to_csv(result: Dict[str, Any], file_path: pathlib.Path | str) -> None:
    """Сохраняет результат расчёта в файл CSV.

    Структура файла:
        - первый столбец «Field» – имя поля;
        - второй столбец «Value» – строковое представление значения.

    Для списков создаются отдельные строки с индексом элемента.
    """
    if isinstance(file_path, str):
        file_path = pathlib.Path(file_path)
    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Field", "Value"])
        for key, val in result.items():
            if isinstance(val, list):
                # пустой список – записываем как «[]»
                if not val:
                    writer.writerow([key, "[]"])
                    continue
                for idx, item in enumerate(val, 1):
                    writer.writerow([f"{key}[{idx}]", str(item)])
            else:
                writer.writerow([key, str(val)])

# ---------------------------------------------------------------------------
# Экспорт коммерческого предложения (Docx)
# ---------------------------------------------------------------------------

def export_commercial_proposal(
    result: Dict[str, Any],
    template_path: pathlib.Path | str = TEMPLATE_PATH,
    output_path: pathlib.Path | str | None = None,
) -> pathlib.Path:
    """Генерирует коммерческое предложение на основе шаблона Docx.

    Шаблон должен содержать переменные в формате ``{{variable_name}}``.
    Функция подставляет все поля из результата (с помощью :func:`_flatten_dict`).
    Если ``output_path`` не задан, создаётся файл с именем ``proposal_{timestamp}.docx`` в той же папке, что и шаблон.

    Возвращает путь к сохранённому файлу.
    """
    if isinstance(template_path, str):
        template_path = pathlib.Path(template_path)
    if not template_path.is_file():
        raise FileNotFoundError(f"Шаблон {template_path} не найден")

    # Формируем контекст для шаблона
    ctx = _flatten_dict(result)

    doc = DocxTemplate(str(template_path))
    doc.render(ctx)

    if output_path is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = template_path.parent / f"proposal_{timestamp}.docx"
    else:
        output_path = pathlib.Path(output_path)

    doc.save(str(output_path))
    return output_path

# ---------------------------------------------------------------------------
# Подготовка данных для CRM (примерный шаблон)
# ---------------------------------------------------------------------------

def prepare_crm_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """Преобразует результат в словарь полей, пригодных для импорта в CRM.

    В проекте конкретного формата CRM не определён.  Функция возвращает простую структуру,
    которую можно дальше маппить на поля любой системы.
    """
    inp = result.get("input_parameters", {})
    crm: Dict[str, Any] = {
        "project_name": inp.get("project_name"),
        "region": inp.get("region"),
        "project_type": inp.get("project_type"),
        "estimated_min_price_rub": result.get("min_price_rub"),
        "estimated_optimal_price_rub": result.get("optimal_price_rub"),
        "estimated_max_price_rub": result.get("max_price_rub"),
        "margin_percent": result.get("margin_percent"),
    }
    return crm

# ---------------------------------------------------------------------------
# Демонстрационный запуск при прямом вызове модуля
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from calculator import calculate

    example_params = {
        "project_name": "Система мониторинга",
        "project_type": "IT Infrastructure",
        "scale_rub": 5000000,
        "region": "Rostov Oblast",
        "deadline": "2026-04-15",
        "financing_scheme": "CAPEX",
        "unique_solutions": True,
    }

    res = calculate(example_params)
    print("Экспортируем результат…")
    csv_path = pathlib.Path("calculator_result.csv")
    export_to_csv(res, csv_path)
    print(f"CSV сохранён в {csv_path}")

    docx_path = export_commercial_proposal(res)
    print(f"Коммерческое предложение сформировано: {docx_path}")

    crm_data = prepare_crm_data(res)
    print("Данные для CRM:", crm_data)
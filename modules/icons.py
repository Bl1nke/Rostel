"""Набор монохромных SVG-иконок для портала «Ростелеком Коммерческий».

Модуль заменяет эмодзи/стикеры на аккуратные векторные иконки в стиле
Material Symbols (линейные, 24×24). Иконки рисуются штрихом ``currentColor``,
поэтому наследуют цвет текста контейнера и легко красятся в фирменные цвета
Ростелекома через CSS (класс ``.rt-icon-svg``).

Пример использования::

    from modules.icons import icon_svg

    html = f'<div class="rt-notif-title">{icon_svg("notifications")} Уведомления</div>'

Для запуска модулей отдельно (``streamlit run modules/dashboard.py``) предусмотрен
фолбэк-импорт ``from icons import icon_svg``.
"""

from __future__ import annotations

#: Внутренняя разметка SVG (без внешнего тега ``<svg>``) для каждой иконки.
ICON_PATHS: dict[str, str] = {
    # Радар / сигнал — используется в логотипе и бренде портала.
    "radar": (
        '<circle cx="12" cy="12" r="1.7" fill="currentColor" stroke="none"/>'
        '<path d="M8.6 8.6a4.8 4.8 0 0 0 0 6.8"/>'
        '<path d="M15.4 8.6a4.8 4.8 0 0 1 0 6.8"/>'
        '<path d="M5.9 5.9a8.6 8.6 0 0 0 0 12.2"/>'
        '<path d="M18.1 5.9a8.6 8.6 0 0 1 0 12.2"/>'
    ),
    # Дашборд — сетка из четырёх плиток.
    "dashboard": (
        '<rect x="3" y="3" width="7.5" height="9" rx="1.6"/>'
        '<rect x="13.5" y="3" width="7.5" height="5.5" rx="1.6"/>'
        '<rect x="13.5" y="12" width="7.5" height="9" rx="1.6"/>'
        '<rect x="3" y="15.5" width="7.5" height="5.5" rx="1.6"/>'
    ),
    # Метка на карте (радар присутствия).
    "location_on": (
        '<path d="M12 21s-6.5-5.7-6.5-10.2a6.5 6.5 0 0 1 13 0C18.5 15.3 12 21 12 21z"/>'
        '<circle cx="12" cy="10.6" r="2.4"/>'
    ),
    # Портфель (инвест-навигатор).
    "business_center": (
        '<rect x="3" y="7" width="18" height="13" rx="2"/>'
        '<path d="M8.5 7V5.2A2.2 2.2 0 0 1 10.7 3h2.6a2.2 2.2 0 0 1 2.2 2.2V7"/>'
        '<path d="M3 12.5h18"/>'
    ),
    # Калькулятор (калькулятор сделок).
    "calculate": (
        '<rect x="4" y="2.5" width="16" height="19" rx="2.4"/>'
        '<rect x="7.2" y="5.6" width="9.6" height="3.8" rx="1"/>'
        '<path d="M8 13.2h.01"/><path d="M12 13.2h.01"/><path d="M16 13.2h.01"/>'
        '<path d="M8 17.2h.01"/><path d="M12 17.2h.01"/><path d="M16 17.2h.01"/>'
    ),
    # Складная карта (вкладка «Карта»).
    "map": (
        '<path d="M9 4 3.5 6.5v13L9 17l6 2.5 5.5-2.5v-13L15 6.5 9 4z"/>'
        '<path d="M9 4v13"/><path d="M15 6.5v13"/>'
    ),
    # Колокольчик (уведомления).
    "notifications": (
        '<path d="M18 8.5a6 6 0 0 0-12 0c0 6-2.5 8-2.5 8h17S18 14.5 18 8.5"/>'
        '<path d="M13.7 20.5a2 2 0 0 1-3.4 0"/>'
    ),
    # Рост (динамика тендеров, тренд).
    "trending_up": '<path d="M3 16.5 9 10.5l4 4 8-8"/><path d="M15 6.5h6v6"/>',
    # Документ (отчёт, тендеры).
    "description": (
        '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5z"/>'
        '<path d="M14 3v5h5"/><path d="M9 13h6"/><path d="M9 17h4"/>'
    ),
    # Лампа (идея, инвест-идея).
    "lightbulb": (
        '<path d="M9.5 18h5"/><path d="M10.5 21h3"/>'
        '<path d="M15.2 13.6c.2-1 .7-1.7 1.4-2.4A4.7 4.7 0 0 0 18 7.8 6 6 0 0 0 6 7.8'
        'c0 1 .2 2.2 1.4 3.4.7.7 1.2 1.4 1.4 2.4"/>'
    ),
    # Информация (демо-режим).
    "info": (
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M12 11v5"/><path d="M12 7.8h.01"/>'
    ),
    # Круговая диаграмма (распределение по отраслям).
    "pie_chart": (
        '<path d="M12 3a9 9 0 1 0 9 9h-9V3z"/>'
        '<path d="M14.5 2.6A9 9 0 0 1 21.4 9.5h-6.9V2.6z"/>'
    ),
    # Конус/стройка (инвест-проекты по стадиям).
    "construction": '<path d="M12 3 3.5 20h17L12 3z"/><path d="M8 12h8"/>',
    # Кубок (топ-5 сделок).
    "emoji_events": (
        '<path d="M7 4h10v5a5 5 0 0 1-10 0V4z"/>'
        '<path d="M7 5H4.5v1.5A3.5 3.5 0 0 0 8 10"/>'
        '<path d="M17 5h2.5v1.5A3.5 3.5 0 0 1 16 10"/>'
        '<path d="M12 14v3"/>'
        '<path d="M8.5 20h7l-.8-3h-5.4l-.8 3z"/>'
    ),
    # Гаечный ключ (модуль подключается командой).
    "build": (
        '<path d="M14.7 6.3a4 4 0 0 1-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 0 1 5.4-5.4z"/>'
    ),
}

_SVG_TEMPLATE = (
    '<svg class="rt-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true" focusable="false">{paths}</svg>'
)


def icon_svg(name: str, css_class: str = "rt-icon-svg") -> str:
    """Возвращает inline-SVG иконки ``name``.

    Иконка наследует цвет через ``currentColor`` и размер через ``font-size``
    контейнера (класс ``.rt-icon-svg`` задаёт ``1em``). Если имя неизвестно,
    возвращается пустая строка, чтобы разметка не ломалась.
    """
    paths = ICON_PATHS.get(name)
    if not paths:
        return ""
    markup = _SVG_TEMPLATE.format(paths=paths)
    if css_class != "rt-icon-svg":
        markup = markup.replace('class="rt-icon-svg"', f'class="{css_class}"', 1)
    return markup

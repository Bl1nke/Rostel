"""Главный файл приложения «Ростелеком Коммерческий» — коммерческий портал Ростелекома.

Точка входа Streamlit-приложения:
* двухфакторная аутентификация (логин/пароль + OTP-код);
* фирменное оформление в стиле брендбука Ростелекома;
* сайдбар с навигацией и уведомлениями;
* роутинг между четырьмя модулями коммерческого блока.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable

import streamlit as st

# Корень проекта должен быть в sys.path, чтобы пакет modules импортировался
# независимо от того, из какой директории запущен streamlit.
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DEMO_OTP = "1234"

st.set_page_config(
    page_title="Ростелеком | Коммерческий",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

BRAND_CSS = """
<style>
:root {
  --rt-orange: #FF4F12;
  --rt-orange-dark: #E23E05;
  --rt-orange-soft: #FFF1EA;
  --rt-blue: #4A90D9;
  --rt-blue-soft: #EAF3FD;
  --rt-purple: #7A2E8E;
  --rt-purple-soft: #F3EBF8;
  --rt-navy: #1B1B2F;
  --rt-muted: #6B6B80;
  --rt-border: #ECE8F5;
  --rt-card: #FFFFFF;
  --rt-radius: 18px;
  --rt-shadow: 0 16px 38px rgba(35, 20, 60, 0.08);
}

html, body, [class*="css"] {
  font-family: "Segoe UI", "Inter", "Roboto", "Helvetica Neue", Arial, sans-serif;
}

.stApp {
  background:
    radial-gradient(900px 520px at 8% -10%, rgba(255, 79, 18, 0.09), transparent 62%),
    radial-gradient(820px 480px at 100% 0%, rgba(74, 144, 217, 0.10), transparent 60%),
    radial-gradient(760px 520px at 55% 110%, rgba(122, 46, 142, 0.08), transparent 62%),
    #F7F8FC;
}

[data-testid="stHeader"] { background: transparent; }в 
#MainMenu, footer, [data-testid="stAppDeployButton"], .stAppDeployButton { visibility: hidden; }

.block-container {
  max-width: 1440px;
  padding-top: 1.6rem;
  padding-bottom: 2.5rem;
}

/* ---------- Сайдбар ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #FFF7F3 0%, #F2F6FD 52%, #F7F1FB 100%);
  border-right: 1px solid var(--rt-border);
}

[data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }

.rt-sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 0.9rem;
  border-radius: var(--rt-radius);
  background: linear-gradient(135deg, var(--rt-orange) 0%, #FF7A3D 48%, var(--rt-purple) 100%);
  color: #FFFFFF;
  box-shadow: 0 12px 26px rgba(255, 79, 18, 0.24);
}

.rt-brand-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 13px;
  background: rgba(255, 255, 255, 0.2);
  font-size: 1.35rem;
}

.rt-brand-title { font-size: 1.15rem; font-weight: 700; line-height: 1.15; }
.rt-brand-caption { font-size: 0.72rem; opacity: 0.85; letter-spacing: 0.04em; }

.rt-user-card {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  margin-top: 0.85rem;
  padding: 0.7rem 0.8rem;
  border: 1px solid var(--rt-border);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.85);
}

.rt-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--rt-blue-soft), var(--rt-purple-soft));
  color: var(--rt-purple);
  font-weight: 700;
  font-size: 0.85rem;
  border: 1px solid rgba(122, 46, 142, 0.15);
}

.rt-user-name { font-weight: 600; color: var(--rt-navy); font-size: 0.92rem; }
.rt-user-role { font-size: 0.74rem; color: var(--rt-muted); }

.rt-notif-title {
  margin: 0.9rem 0 0.45rem;
  font-size: 0.82rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--rt-purple);
}

.rt-notif-card {
  display: flex;
  gap: 0.55rem;
  padding: 0.6rem 0.7rem;
  margin-bottom: 0.4rem;
  border: 1px solid var(--rt-border);
  border-left: 3px solid var(--rt-orange);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  font-size: 0.8rem;
  color: var(--rt-navy);
  line-height: 1.3;
}

.rt-notif-card.blue { border-left-color: var(--rt-blue); }
.rt-notif-card.purple { border-left-color: var(--rt-purple); }
.rt-notif-time { display: block; margin-top: 0.15rem; font-size: 0.68rem; color: var(--rt-muted); }

/* ---------- Навигация ---------- */
/* Виджет радио занимает всю ширину сайдбара, как markdown-блоки
   (карточка бренда, уведомления, разделители). */
[data-testid="stSidebar"] [data-testid="stRadio"] { width: 100%; }

[data-testid="stSidebar"] [role="radiogroup"] {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  width: 100%;
  gap: 0.4rem;
}

[data-testid="stSidebar"] [role="radiogroup"] label {
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--rt-border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
  cursor: pointer;
}

/* Текст пункта растягивается по всей ширине карточки пункта. */
[data-testid="stSidebar"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] {
  width: 100%;
}

[data-testid="stSidebar"] [role="radiogroup"] label:hover {
  border-color: rgba(255, 79, 18, 0.45);
  transform: translateX(2px);
}

[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  border-color: var(--rt-orange);
  background: linear-gradient(135deg, rgba(255, 79, 18, 0.12), rgba(122, 46, 142, 0.12));
  box-shadow: 0 8px 18px rgba(122, 46, 142, 0.12);
}

[data-testid="stSidebar"] [role="radiogroup"] input { accent-color: var(--rt-orange); }

/* ---------- Кнопки ---------- */
.stButton > button,
[data-testid="stFormSubmitButton"] > button {
  min-height: 44px;
  padding: 0.55rem 1.1rem;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--rt-orange), #FF7A3D);
  color: #FFFFFF;
  font-weight: 600;
  box-shadow: 0 10px 20px rgba(255, 79, 18, 0.24);
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
}

.stButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
  transform: translateY(-1px);
  filter: brightness(1.04);
  box-shadow: 0 14px 26px rgba(255, 79, 18, 0.3);
  color: #FFFFFF;
}

.stButton > button[kind="secondary"] {
  background: #FFFFFF;
  color: var(--rt-orange-dark);
  border: 1px solid rgba(255, 79, 18, 0.35);
  box-shadow: none;
}

.stButton > button[kind="secondary"]:hover {
  background: var(--rt-orange-soft);
  color: var(--rt-orange-dark);
}

/* ---------- Поля ввода и формы ---------- */
[data-baseweb="input"],
[data-baseweb="textarea"],
[data-baseweb="select"] > div {
  border-radius: 12px !important;
}

.stTextInput input {
  background: #FFFFFF !important;
  border-radius: 12px !important;
  padding: 0.62rem 0.8rem !important;
}

.stTextInput input:focus {
  border-color: var(--rt-orange) !important;
  box-shadow: 0 0 0 3px rgba(255, 79, 18, 0.14) !important;
}

[data-testid="stForm"] {
  padding: 1.5rem;
  border: 1px solid var(--rt-border);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: var(--rt-shadow);
}
/* ---------- Метрики и карточки ---------- */
[data-testid="stMetric"] {
  padding: 1rem 1.1rem;
  border: 1px solid var(--rt-border);
  border-left: 4px solid var(--rt-orange);
  border-radius: 16px;
  background: var(--rt-card);
  box-shadow: 0 10px 24px rgba(35, 20, 60, 0.06);
}

[data-testid="stMetricLabel"] {
  color: var(--rt-muted) !important;
  font-size: 0.8rem !important;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

[data-testid="stMetricValue"] {
  color: var(--rt-navy) !important;
  font-weight: 700 !important;
}

[data-testid="stMetricDelta"] { font-weight: 600 !important; }

/* ---------- Вкладки ---------- */
.stTabs [data-baseweb="tab-list"] {
  gap: 0.35rem;
  padding: 0.35rem;
  border: 1px solid var(--rt-border);
  border-radius: 14px;
  background: #FFFFFF;
}

.stTabs [data-baseweb="tab"] {
  padding: 0.45rem 1rem;
  border-radius: 10px;
  color: var(--rt-muted);
  font-weight: 600;
}

.stTabs [data-baseweb="tab"]:hover { color: var(--rt-orange-dark); }

.stTabs [aria-selected="true"] {
  background: linear-gradient(135deg, rgba(255, 79, 18, 0.14), rgba(122, 46, 142, 0.14));
  color: var(--rt-orange-dark) !important;
}

/* ---------- Уведомления, таблицы, экспандеры ---------- */
[data-testid="stAlert"] {
  border-radius: 14px;
  border: 1px solid var(--rt-border);
}

[data-testid="stDataFrame"],
[data-testid="stTable"],
.stPlotlyChart,
.stFolium {
  overflow: hidden;
  border: 1px solid var(--rt-border);
  border-radius: 16px;
  background: #FFFFFF;
  box-shadow: 0 10px 24px rgba(35, 20, 60, 0.05);
}

[data-testid="stExpander"] {
  border: 1px solid var(--rt-border);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
}

[data-testid="stDownloadButton"] > button {
  border-radius: 12px;
  border: 1px solid rgba(122, 46, 142, 0.3);
  background: var(--rt-purple-soft);
  color: var(--rt-purple);
  font-weight: 600;
}

hr { border-color: var(--rt-border); }

/* ---------- Экран входа ---------- */
.rt-login-hero {
  margin: 3vh auto 1.6rem;
  max-width: 760px;
  text-align: center;
}

.rt-login-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 74px;
  height: 74px;
  margin-bottom: 0.9rem;
  border-radius: 24px;
  background: linear-gradient(135deg, var(--rt-orange) 0%, #FF7A3D 48%, var(--rt-purple) 100%);
  box-shadow: 0 18px 34px rgba(255, 79, 18, 0.3);
  font-size: 2.1rem;
}

.rt-eyebrow {
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--rt-orange-dark);
}

.rt-hero-title {
  margin: 0.35rem 0 0.5rem;
  font-size: 2.15rem;
  line-height: 1.15;
  color: var(--rt-navy);
}

.rt-hero-title span {
  background: linear-gradient(120deg, var(--rt-orange), var(--rt-purple));
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.rt-hero-sub { margin: 0; color: var(--rt-muted); font-size: 1rem; }

.rt-form-title {
  margin-bottom: 0.2rem;
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--rt-navy);
}

.rt-form-sub {
  margin-bottom: 0.9rem;
  font-size: 0.82rem;
  color: var(--rt-muted);
}

.rt-login-footer {
  margin-top: 1.4rem;
  text-align: center;
  font-size: 0.76rem;
  color: var(--rt-muted);
}

/* ---------- Заголовок раздела ---------- */
.rt-page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.2rem;
  padding: 1.2rem 1.4rem;
  border: 1px solid rgba(122, 46, 142, 0.12);
  border-radius: 20px;
  background: linear-gradient(120deg, rgba(255, 79, 18, 0.1), rgba(74, 144, 217, 0.14) 52%, rgba(122, 46, 142, 0.14));
}

.rt-page-header h1 {
  margin: 0.15rem 0 0.25rem;
  font-size: 1.65rem;
  line-height: 1.2;
  color: var(--rt-navy);
}

.rt-page-header p { margin: 0; color: var(--rt-muted); font-size: 0.9rem; }

.rt-header-badge {
  flex: 0 0 auto;
  padding: 0.6rem 0.8rem;
  border-radius: 16px;
  background: #FFFFFF;
  box-shadow: 0 10px 22px rgba(35, 20, 60, 0.1);
  font-size: 1.9rem;
}

.rt-footer {
  margin-top: 2.2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--rt-border);
  text-align: center;
  font-size: 0.75rem;
  color: var(--rt-muted);
}

/* ---------- Адаптивность ---------- */
@media (max-width: 1024px) {
  .block-container { padding-left: 1.2rem; padding-right: 1.2rem; }
  .rt-hero-title { font-size: 1.85rem; }
}

@media (max-width: 768px) {
  .block-container { padding-top: 1rem; }
  .rt-page-header {
    flex-direction: column;
    align-items: flex-start;
    padding: 1rem 1.1rem;
  }
  .rt-page-header h1 { font-size: 1.35rem; }
  .rt-header-badge { display: none; }
  .rt-login-hero { margin-top: 1.2rem; }
  .rt-hero-title { font-size: 1.55rem; }
  .rt-hero-sub { font-size: 0.9rem; }
  .rt-form-title { font-size: 1.05rem; }
  [data-testid="stForm"] { padding: 1.1rem; border-radius: 18px; }
  [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
  [data-testid="column"] { min-width: 100% !important; flex: 1 1 100% !important; }
  .stTabs [data-baseweb="tab"] { padding: 0.4rem 0.65rem; font-size: 0.85rem; }
}

@media (max-width: 480px) {
  .rt-login-logo { width: 60px; height: 60px; border-radius: 18px; font-size: 1.7rem; }
  .rt-hero-title { font-size: 1.35rem; }
  .rt-page-header h1 { font-size: 1.2rem; }
  .stButton > button,
  [data-testid="stFormSubmitButton"] > button,
  [data-testid="stDownloadButton"] > button { width: 100%; }
  [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
  [data-testid="stSidebar"] [role="radiogroup"] label { padding: 0.5rem 0.55rem; font-size: 0.88rem; }
  .rt-user-card { padding: 0.6rem 0.65rem; }
}
</style>
"""


# ---------------------------------------------------------------------------
# Служебные функции
# ---------------------------------------------------------------------------
def _inject_brand_styles() -> None:
    """Внедряет CSS брендбука Ростелекома в приложение."""
    st.markdown(BRAND_CSS, unsafe_allow_html=True)


def _init_session_state() -> None:
    """Инициализирует ключи состояния аутентификации."""
    defaults: dict[str, Any] = {
        "authenticated": False,
        "otp_sent": False,
        "pending_login": "",
        "user_name": "Иванов И.И.",
        "user_role": "Коммерческий блок",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_login_state() -> None:
    """Возвращает пользователя к шагу ввода логина и пароля."""
    st.session_state.authenticated = False
    st.session_state.otp_sent = False
    st.session_state.pending_login = ""

# ---------------------------------------------------------------------------
# Аутентификация: шаг 1 — логин и пароль, шаг 2 — OTP
# ---------------------------------------------------------------------------
def _render_login_screen() -> None:
    """Отрисовывает экран входа с фирменным hero-блоком."""
    st.markdown(
        """
        <div class="rt-login-hero">
          <div class="rt-login-logo">📡</div>
          <div class="rt-eyebrow">Ростелеком · Коммерческий блок</div>
          <h1 class="rt-hero-title">Портал <span>«Ростелеком коммерческий»</span></h1>
          <p class="rt-hero-sub">Единая точка входа в аналитику, тендеры и инвестиционные решения</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 1.15, 1])
    with center:
        if st.session_state.otp_sent:
            _render_otp_form()
        else:
            _render_credentials_form()

    st.markdown(
        '<div class="rt-login-footer">Доступ только для сотрудников компании. '
        'Все действия фиксируются в журнале безопасности.</div>',
        unsafe_allow_html=True,
    )


def _render_credentials_form() -> None:
    """Шаг 1: проверяет заполненность логина и пароля."""
    st.markdown(
        '<div class="rt-form-title">Вход в систему</div>'
        '<div class="rt-form-sub">Шаг 1 из 2 · корпоративная учётная запись</div>',
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        login = st.text_input("Логин", placeholder="ivanov", key="login_input")
        password = st.text_input(
            "Пароль",
            type="password",
            placeholder="••••••••",
            key="password_input",
        )
        submitted = st.form_submit_button(
            "Войти", type="primary", use_container_width=True
        )

    if submitted:
        if login.strip() and password.strip():
            st.session_state.pending_login = login.strip()
            st.session_state.otp_sent = True
            st.rerun()
        else:
            st.warning("Введите логин и пароль.")


def _render_otp_form() -> None:
    """Шаг 2: проверяет OTP-код (для демо — 1234)."""
    st.markdown(
        '<div class="rt-form-title">Двухфакторная аутентификация</div>'
        '<div class="rt-form-sub">Шаг 2 из 2 · подтвердите вход</div>',
        unsafe_allow_html=True,
    )
    st.info("📱 Код отправлен на корпоративный телефон. Для демо введите: 1234")

    with st.form("otp_form"):
        code = st.text_input(
            "Код подтверждения",
            max_chars=4,
            placeholder="••••",
            key="otp_input",
        )
        confirm = st.form_submit_button(
            "Подтвердить", type="primary", use_container_width=True
        )
        back = st.form_submit_button("← Назад", use_container_width=True)

    if back:
        st.session_state.otp_sent = False
        st.session_state.pending_login = ""
        st.rerun()

    if confirm:
        if code.strip() == DEMO_OTP:
            st.session_state.authenticated = True
            st.session_state.otp_sent = False
            st.rerun()
        else:
            st.error("Неверный код!")

# ---------------------------------------------------------------------------
# Сайдбар: бренд, пользователь, навигация и уведомления
# ---------------------------------------------------------------------------
def _render_sidebar_brand() -> None:
    """Отрисовывает логотип портала и карточку текущего пользователя."""
    st.markdown(
        """
        <div class="rt-sidebar-brand">
          <span class="rt-brand-icon">📡</span>
          <div>
            <div class="rt-brand-title">Ростелеком коммерческий</div>
            <div class="rt-brand-caption">ROSTELECOM · B2B</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="rt-user-card" title="Иванов И.И. (Коммерческий блок)">
          <span class="rt-avatar">ИИ</span>
          <div>
            <div class="rt-user-name">Иванов И.И.</div>
            <div class="rt-user-role">Коммерческий блок</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_notifications_fallback(reason: str | None = None) -> None:
    """Показывает демо-уведомления, пока модуль notifications не готов."""
    st.markdown(
        """
        <div class="rt-notif-title">🔔 Уведомления</div>
        <div class="rt-notif-card">📈 Новый тендер: «ЦОД для ЦФО»
          <span class="rt-notif-time">10 минут назад</span>
        </div>
        <div class="rt-notif-card blue">📄 Загружен отчёт по региону
          <span class="rt-notif-time">1 час назад</span>
        </div>
        <div class="rt-notif-card purple">💡 Инвест-идея: рост спроса на облака
          <span class="rt-notif-time">Сегодня</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if reason:
        st.caption(reason)


def _render_sidebar_notifications() -> None:
    """Подключает виджет уведомлений из модуля notifications."""
    try:
        from modules import notifications
    except Exception as exc:  # noqa: BLE001 - портал не должен падать из-за модуля
        _render_notifications_fallback(f"Модуль уведомлений недоступен: {exc}")
        return

    show_notifications = getattr(notifications, "show_sidebar_notifications", None)
    if not callable(show_notifications):
        _render_notifications_fallback("Модуль уведомлений ещё не подключён.")
        return

    try:
        notifications.show_sidebar_notifications()
    except Exception as exc:  # noqa: BLE001
        _render_notifications_fallback(f"Не удалось показать уведомления: {exc}")


# ---------------------------------------------------------------------------
# Роутинг между модулями команды
# ---------------------------------------------------------------------------
PAGES: dict[str, dict[str, Any]] = {
    "📊 Сводный дашборд": {
        "module": "dashboard",
        "icon": "📊",
        "title": "Сводный дашборд",
        "subtitle": "Ключевые показатели коммерческого блока в реальном времени",
        "renderers": ("render_dashboard", "show_dashboard"),
    },
    "📍 Радар присутствия": {
        "module": "radar",
        "icon": "📍",
        "title": "Радар присутствия",
        "subtitle": "География присутствия и активность по регионам",
        "renderers": ("render_radar", "show_radar"),
    },
    "💼 Инвест-навигатор": {
        "module": "navigator",
        "icon": "💼",
        "title": "Инвест-навигатор",
        "subtitle": "Инвестиционные возможности и приоритетные направления",
        "renderers": ("render_navigator", "render_invest_navigator", "show_navigator"),
    },
    "🧮 Калькулятор сделок": {
        "module": "calculator",
        "icon": "🧮",
        "title": "Калькулятор сделок",
        "subtitle": "Расчёт экономики сделки и скидочных сценариев",
        "renderers": ("render_calculator", "show_calculator"),
    },
}

_BASE_RENDERERS: tuple[str, ...] = ("render", "main", "run", "show")


#: Ключ session_state, в котором лежат времена правки файлов модулей.
#: Глобалы самого скрипта Streamlit сбрасывает на каждом rerun, поэтому храним их в сессии.
_MODULE_MTIMES_KEY = "_module_mtimes"


def _module_mtimes() -> dict[str, float]:
    """Возвращает словарь «имя модуля → время последней правки файла» из состояния сессии."""
    mtimes = st.session_state.get(_MODULE_MTIMES_KEY)
    if not isinstance(mtimes, dict):
        mtimes = {}
        st.session_state[_MODULE_MTIMES_KEY] = mtimes
    return mtimes


def _import_module(module_name: str) -> ModuleType:
    """Импортирует модуль команды и подхватывает правки файла без перезапуска сервера."""
    importlib.invalidate_caches()
    module = importlib.import_module(f"modules.{module_name}")

    module_path = getattr(module, "__file__", None)
    if not module_path:
        return module

    try:
        mtime = Path(module_path).stat().st_mtime
    except OSError:
        return module

    # Перезагружаем модуль только если файл действительно менялся: иначе в sys.modules
    # осталась бы старая (например, пустая) версия модуля и раздел выглядел бы пустым.
    mtimes = _module_mtimes()
    if mtimes.get(module_name) != mtime:
        mtimes[module_name] = mtime
        module = importlib.reload(module)
    return module


def _resolve_renderer(
    module: ModuleType, candidates: Iterable[str]
) -> Callable[[], Any] | None:
    """Находит callable-точку входа модуля среди ожидаемых имён."""
    for name in (*candidates, *_BASE_RENDERERS):
        renderer = getattr(module, name, None)
        if callable(renderer):
            return renderer
    return None


def _render_page_header(config: dict[str, Any]) -> None:
    """Отрисовывает фирменный заголовок выбранного раздела."""
    st.markdown(
        f"""
        <div class="rt-page-header">
          <div>
            <div class="rt-eyebrow">Коммерческий блок · Ростелеком</div>
            <h1>{config['icon']} {config['title']}</h1>
            <p>{config['subtitle']}</p>
          </div>
          <div class="rt-header-badge">{config['icon']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_module_placeholder(config: dict[str, Any]) -> None:
    """Показывает заглушку, пока модуль не реализовал точку входа."""
    st.info(
        f"🔧 Модуль «{config['title']}» подключается командой. "
        "Раздел уже доступен в навигации."
    )
    st.markdown("**Ожидаемая точка входа модуля**")
    renderers = ", ".join((*config["renderers"], *_BASE_RENDERERS))
    st.code(
        f"# modules/{config['module']}.py\n"
        "def render() -> None:\n"
        "    ...\n\n"
        f"# поддерживаемые имена: {renderers}",
        language="python",
    )


def _render_module_error(config: dict[str, Any], exc: Exception) -> None:
    """Показывает аккуратную ошибку вместо падения всего портала."""
    st.error(
        f"Не удалось загрузить модуль «{config['title']}». "
        f"Проверьте файл modules/{config['module']}.py."
    )
    with st.expander("Технические детали"):
        st.exception(exc)


def _render_page(page: str) -> None:
    """Загружает и отрисовывает выбранный модуль команды."""
    config = PAGES[page]
    _render_page_header(config)

    try:
        module = _import_module(config["module"])
    except Exception as exc:  # noqa: BLE001
        _render_module_error(config, exc)
        return

    renderer = _resolve_renderer(module, config["renderers"])
    if renderer is None:
        _render_module_placeholder(config)
        return

    try:
        renderer()
    except Exception as exc:  # noqa: BLE001
        _render_module_error(config, exc)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------
def main() -> None:
    """Запускает приложение: аутентификация, сайдбар, роутинг модулей."""
    _init_session_state()
    _inject_brand_styles()

    if not st.session_state.authenticated:
        _render_login_screen()
        st.stop()

    with st.sidebar:
        _render_sidebar_brand()
        st.markdown("---")
        page = st.radio(
            "Навигация",
            options=list(PAGES),
            key="nav_page",
            width="stretch",
        )
        st.markdown("---")
        _render_sidebar_notifications()
        st.markdown("---")
        st.button(
            "🚪 Выйти",
            use_container_width=True,
            on_click=_reset_login_state,
        )

    _render_page(page)

    st.markdown(
        '<div class="rt-footer">© Ростелеком · Внутренний портал «Ростелеком Коммерческий» · '
        'Коммерческий блок</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
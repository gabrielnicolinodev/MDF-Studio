"""Tema escuro (estilo CAD) aplicado via QSS."""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

BG = "#16181d"
SIDEBAR = "#101216"
CARD = "#1f2229"
CARD_BORDER = "#2b2f38"
TEXT = "#e6e8ec"
TEXT_MUTED = "#8b919d"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#5a97f8"
ACCENT_PRESSED = "#2866d1"

STYLESHEET = f"""
* {{ color: {TEXT}; font-size: 13px; }}
QMainWindow, QWidget#pageRoot, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: {BG};
}}
QScrollArea {{ border: none; }}
QWidget#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {CARD_BORDER}; }}
QLabel#brand {{ font-size: 17px; font-weight: 700; }}
QLabel#brandSub {{ color: {TEXT_MUTED}; font-size: 11px; }}
QPushButton#navButton {{
    background: transparent; border: none; border-radius: 6px;
    text-align: left; padding: 10px 14px; color: {TEXT_MUTED};
}}
QPushButton#navButton:hover {{ background: {CARD}; color: {TEXT}; }}
QPushButton#navButton:checked {{ background: {CARD}; color: {TEXT}; border-left: 3px solid {ACCENT}; }}
QPushButton#navButton:focus {{ outline: none; border: 1px solid {ACCENT}; }}
QLabel#pageTitle {{ font-size: 24px; font-weight: 700; }}
QLabel#pageSubtitle {{ color: {TEXT_MUTED}; }}
QLabel#sectionTitle {{ font-size: 15px; font-weight: 600; }}
QFrame#card {{ background: {CARD}; border: 1px solid {CARD_BORDER}; border-radius: 8px; }}
QFrame#card[interactive="true"]:hover {{ border-color: {ACCENT}; }}
QFrame#card QLabel {{ background: transparent; }}
QLabel#cardTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#cardText {{ color: {TEXT_MUTED}; }}
QLabel#badge {{
    background: #2a2f3a; color: {TEXT_MUTED}; border-radius: 9px;
    padding: 2px 8px; font-size: 11px;
}}
QLabel#badgeOk {{
    background: #12301f; color: #6ee7a0; border-radius: 9px;
    padding: 2px 8px; font-size: 11px;
}}
QLabel#statusOk {{ color: #6ee7a0; }}
QLabel#statusError {{ color: #f87171; }}
QPushButton {{
    background: {CARD}; border: 1px solid {CARD_BORDER}; border-radius: 6px;
    padding: 8px 16px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {BG}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; border-color: {CARD_BORDER}; }}
QPushButton:focus {{ border-color: {ACCENT}; }}
QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#primary:disabled {{ background: #2a3447; border-color: #2a3447; color: {TEXT_MUTED}; }}
QLineEdit, QComboBox {{
    background: {BG}; border: 1px solid {CARD_BORDER}; border-radius: 6px;
    padding: 7px 10px; min-height: 18px;
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: {TEXT_MUTED}; }}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {CARD_BORDER};
    selection-background-color: {ACCENT};
}}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {CARD_BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {CARD_BORDER};
    border-radius: 3px; background: {BG}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QSplitter::handle {{ background: {CARD_BORDER}; width: 1px; }}
QToolTip {{ background: {CARD}; border: 1px solid {CARD_BORDER}; color: {TEXT}; }}
"""


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    font = QFont(app.font())
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)

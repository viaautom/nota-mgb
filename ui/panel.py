"""Minimal panel placeholder for the plugin's validation interface."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:  # pragma: no cover - QGIS-only runtime
    from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QLabel
except ImportError:  # pragma: no cover
    QWidget = object
    QVBoxLayout = object
    QLabel = object


class MgbValidationPanel(QWidget):
    """Stage 2 panel scaffold: ready to receive evaluation data and project ranking."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_report: Optional[Dict[str, Any]] = None
        self._fallback = QLabel is object or QVBoxLayout is object

        if self._fallback:
            return

        layout = QVBoxLayout(self)
        self.title_label = QLabel("Avaliação MGB")
        self.summary_label = QLabel("Projeto ainda não avaliado.")
        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_label)

    def set_status(self, message: str) -> None:
        if self._fallback:
            return
        if hasattr(self, "summary_label"):
            self.summary_label.setText(message)

    def set_project_report(self, report: Dict[str, Any]) -> None:
        self.project_report = report
        if self._fallback:
            return
        if hasattr(self, "summary_label"):
            summary = report.get("summary", {})
            text = (
                f"Camadas: {summary.get('total_layers', 0)} | "
                f"Conformes: {summary.get('conform_layers', 0)} | "
                f"Não conformes: {summary.get('non_conform_layers', 0)}"
            )
            self.summary_label.setText(text)

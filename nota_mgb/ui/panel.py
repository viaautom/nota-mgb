"""Painel lateral do Nota MGB: abas Avaliar, Corrigir e Exportar.

Só interface: emite sinais e recebe resultados prontos do controlador
(plugin.py). Nenhuma regra do MGB mora aqui.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from qgis.PyQt.QtCore import QDate, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDockWidget,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

SELO_COLORS = {"Excelente": "#1a7f37", "Conforme": "#2f6fb0", "Não conforme": "#b42318"}
USER_ROLE = Qt.ItemDataRole.UserRole


def _wrap_label(text: str = "", style: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    if style:
        label.setStyleSheet(style)
    return label


class MgbValidationPanel(QDockWidget):
    evaluate_layer_requested = pyqtSignal()
    evaluate_project_requested = pyqtSignal()
    autofill_requested = pyqtSignal()
    save_requested = pyqtSignal(dict)
    resource_type_changed = pyqtSignal(str)
    layer_selected = pyqtSignal(str)

    def __init__(self, resource_types: Dict[str, str], parent: Optional[QWidget] = None):
        super().__init__("Nota MGB", parent)
        self.setObjectName("NotaMgbDock")
        self._form_widgets: Dict[str, Any] = {}

        root = QWidget()
        layout = QVBoxLayout(root)

        self.layer_label = _wrap_label("Nenhuma camada selecionada.", "font-weight: bold;")
        layout.addWidget(self.layer_label)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Tipo de recurso:"))
        self.type_combo = QComboBox()
        for key, label in resource_types.items():
            self.type_combo.addItem(label, key)
        self.type_combo.currentIndexChanged.connect(
            lambda _i: self.resource_type_changed.emit(self.type_combo.currentData())
        )
        type_row.addWidget(self.type_combo, 1)
        layout.addLayout(type_row)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_evaluate_tab(), "Avaliar")
        self.tabs.addTab(self._build_fix_tab(), "Corrigir")
        self.tabs.addTab(self._build_export_tab(), "Exportar")
        layout.addWidget(self.tabs, 1)
        self.setWidget(root)

    # --- construção das abas -------------------------------------------------

    def _build_evaluate_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        buttons = QHBoxLayout()
        evaluate_layer = QPushButton("Avaliar camada")
        evaluate_layer.clicked.connect(self.evaluate_layer_requested.emit)
        evaluate_project = QPushButton("Avaliar projeto")
        evaluate_project.clicked.connect(self.evaluate_project_requested.emit)
        buttons.addWidget(evaluate_layer)
        buttons.addWidget(evaluate_project)
        layout.addLayout(buttons)

        self.score_label = _wrap_label("", "font-size: 28px; font-weight: bold;")
        self.selo_label = _wrap_label("")
        self.breakdown_label = _wrap_label("")
        layout.addWidget(self.score_label)
        layout.addWidget(self.selo_label)
        layout.addWidget(self.breakdown_label)

        self.issue_list = QListWidget()
        self.issue_list.setWordWrap(True)
        self.issue_list.itemDoubleClicked.connect(lambda _item: self.tabs.setCurrentIndex(1))
        layout.addWidget(self.issue_list, 2)

        self.project_table = QTableWidget(0, 4)
        self.project_table.setHorizontalHeaderLabels(["Camada", "Nota", "Selo", "Pendências"])
        self.project_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.project_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.project_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.project_table.cellDoubleClicked.connect(self._on_project_row)
        self.project_table.setVisible(False)
        layout.addWidget(self.project_table, 2)
        return tab

    def _build_fix_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        autofill = QPushButton("Preencher automaticamente")
        autofill.setToolTip("Calcula a partir da camada: extensão, SRC, tipo, codificação, identificador, data e perfil.")
        autofill.clicked.connect(self.autofill_requested.emit)
        layout.addWidget(autofill)

        self.fix_info = _wrap_label("Avalie a camada para ver o que falta.")
        layout.addWidget(self.fix_info)

        self.form_host = QWidget()
        self.form_layout = QVBoxLayout(self.form_host)  # rótulo em cima do campo: cabe em painel estreito
        self.form_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.form_host)
        layout.addWidget(scroll, 1)

        self.save_button = QPushButton("Salvar e reavaliar")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(lambda: self.save_requested.emit(self.form_values()))
        layout.addWidget(self.save_button)
        return tab

    def _build_export_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(_wrap_label("Exportação do XML ISO 19115-3 e do relatório: próxima etapa."))
        layout.addStretch(1)
        return tab

    # --- estado ------------------------------------------------------------

    def set_layer_name(self, name: Optional[str]) -> None:
        self.layer_label.setText(f"Camada: {name}" if name else "Nenhuma camada selecionada.")

    def set_resource_type(self, key: str) -> None:
        index = self.type_combo.findData(key)
        if index >= 0 and index != self.type_combo.currentIndex():
            self.type_combo.blockSignals(True)
            self.type_combo.setCurrentIndex(index)
            self.type_combo.blockSignals(False)

    def clear_result(self) -> None:
        self.score_label.setText("")
        self.selo_label.setText("")
        self.breakdown_label.setText("")
        self.issue_list.clear()
        self._clear_form()
        self.fix_info.setText("Avalie a camada para ver o que falta.")

    def show_result(self, result: Dict[str, Any], quality_labels: Dict[str, Dict[str, Any]]) -> None:
        selo = result["selo"]
        color = SELO_COLORS.get(selo, "#444")
        self.score_label.setText(f"{result['total_score']:.0f}/100")
        n_issues = len(result["issues"])
        selo_text = selo if not n_issues else f"{selo} — faltam {n_issues} obrigatório(s)"
        self.selo_label.setText(selo_text)
        self.selo_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.breakdown_label.setText(
            f"Conformidade {result['conformity_score']:.1f}/70 · Qualidade {result['quality_score']}/30 · "
            f"{result['resource_label']}"
        )

        self.issue_list.clear()
        for issue in result["issues"]:
            prefix = "Falta" if issue["problem"] == "missing" else "Inválido"
            text = f"{prefix}: {issue['label']} — {issue['message']}  (Quadro {issue['quadro']}, linha {issue['linha']})"
            item = QListWidgetItem(text)
            item.setData(USER_ROLE, issue["id"])
            self.issue_list.addItem(item)
        for name, ok in result["quality_checks"].items():
            if not ok:
                spec = quality_labels.get(name, {})
                item = QListWidgetItem(f"Melhoria: {spec.get('description', name)} (+{spec.get('weight', 0)} pts)")
                item.setForeground(Qt.GlobalColor.darkGray)
                self.issue_list.addItem(item)
        if not self.issue_list.count():
            self.issue_list.addItem("Nada pendente.")

    def show_project(self, report: Dict[str, Any]) -> None:
        rows: List[Dict[str, Any]] = report["layers"]
        self.project_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            name = QTableWidgetItem(row["layer_name"])
            name.setData(USER_ROLE, row.get("layer_id"))
            self.project_table.setItem(r, 0, name)
            self.project_table.setItem(r, 1, QTableWidgetItem(f"{row['total_score']:.0f}"))
            self.project_table.setItem(r, 2, QTableWidgetItem(row["selo"]))
            pending = len(row["missing_required"]) + len(row["invalid_required_values"])
            self.project_table.setItem(r, 3, QTableWidgetItem(str(pending)))
        self.project_table.setVisible(True)
        summary = report["summary"]
        self.breakdown_label.setText(
            f"Projeto: {summary['total_layers']} camada(s), {summary['conform_layers']} conforme(s). "
            "Duplo clique numa linha seleciona a camada."
        )

    def _on_project_row(self, row: int, _column: int) -> None:
        item = self.project_table.item(row, 0)
        if item is not None and item.data(USER_ROLE):
            self.layer_selected.emit(item.data(USER_ROLE))

    def set_fix_message(self, text: str, details: str = "") -> None:
        self.fix_info.setText(text)
        self.fix_info.setToolTip(details)

    # --- formulário guiado ---------------------------------------------------

    def _clear_form(self) -> None:
        while self.form_layout.count() > 1:  # mantém o stretch final
            item = self.form_layout.takeAt(0)
            old = item.widget()
            if old is not None:
                old.hide()
                old.setParent(None)
                old.deleteLater()
        self._form_widgets = {}
        self.save_button.setEnabled(False)

    def build_form(
        self,
        issues: List[Dict[str, Any]],
        elements: Dict[str, Dict[str, Any]],
        domain_values: Dict[str, List[tuple]],
        current: Dict[str, Any],
    ) -> None:
        """Monta um campo para cada pendência, com lista suspensa quando há domínio."""
        self._clear_form()
        if not issues:
            self.fix_info.setText("Todos os obrigatórios estão preenchidos.")
            return
        self.fix_info.setText(f"{len(issues)} campo(s) a corrigir. Comece por \"Preencher automaticamente\".")

        for issue in issues:
            field = issue["id"]
            spec = elements[field]
            widget = self._widget_for(field, spec, domain_values, current.get(field))
            label = _wrap_label(spec["label"], "font-weight: bold;")
            label.setToolTip(spec.get("iso", ""))
            box = QWidget()
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 10)
            box_layout.setSpacing(2)
            box_layout.addWidget(label)
            box_layout.addWidget(widget)
            help_text = spec.get("help", "")
            if issue["problem"] == "invalid":
                help_text = f"{issue['message']} {help_text}"
            box_layout.addWidget(_wrap_label(help_text, "color: #666; font-size: 11px;"))
            self.form_layout.insertWidget(self.form_layout.count() - 1, box)
            self._form_widgets[field] = widget
        self.save_button.setEnabled(True)

    @staticmethod
    def _widget_for(field: str, spec: Dict[str, Any], domain_values: Dict[str, List[tuple]], value: Any) -> QWidget:
        if "domain" in spec:
            combo = QComboBox()
            combo.addItem("— escolha —", None)
            for code, label in domain_values.get(spec["domain"], []):
                combo.addItem(f"{label} ({code})", code)
            index = combo.findData(value if not isinstance(value, list) else (value[0] if value else None))
            combo.setCurrentIndex(max(index, 0))
            return combo
        if spec.get("validator") == "date":
            date = QDateEdit()
            date.setCalendarPopup(True)
            date.setDisplayFormat("dd/MM/yyyy")
            parsed = QDate.fromString(str(value or "")[:10], "yyyy-MM-dd")
            date.setDate(parsed if parsed.isValid() else QDate.currentDate())
            return date
        if spec.get("validator") == "extent" or "fixed" in spec:
            return _wrap_label("Preenchido por \"Preencher automaticamente\".", "font-style: italic;")
        if field == "resourceAbstract":
            text = QPlainTextEdit(str(value or ""))
            text.setMinimumHeight(90)
            return text
        line = QLineEdit(str(value or ""))
        if "any_of" in spec:
            line.setPlaceholderText("Denominador da escala, ex.: 50000")
        return line

    def form_values(self) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for field, widget in self._form_widgets.items():
            if isinstance(widget, QComboBox):
                value = widget.currentData()
            elif isinstance(widget, QDateEdit):
                value = widget.date().toString("yyyy-MM-dd")
            elif isinstance(widget, QPlainTextEdit):
                value = widget.toPlainText().strip()
            elif isinstance(widget, QLineEdit):
                value = widget.text().strip()
            else:
                continue
            if not value:
                continue
            if field == "spatialResolution":
                values["equivalentScale"] = value.replace(".", "").replace("1:", "")
            else:
                values[field] = value
        return values


__all__ = ["MgbValidationPanel"]

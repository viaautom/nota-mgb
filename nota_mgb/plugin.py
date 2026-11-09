"""Nota MGB: registro no QGIS e controle do painel (avaliar, corrigir, exportar).

Copyright (C) 2026 Rafael Dantas de Morais (Ibexdev)
Licença: GNU GPL v2 ou superior.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from qgis.core import (
    Qgis,
    QgsMapLayer,
    QgsMessageLog,
    QgsProject,
    QgsRasterLayer,
    QgsSettings,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox

from .core.autofill import propose_fill
from .core.domain_catalog import DomainCatalog
from .core.evaluation_engine import MetadataEvaluationEngine
from .core.iso_xml import XmlError, from_xml, importable, to_xml
from .core.layer_facts import layer_facts
from .core.metadata_store import save_metadata
from .core.project_evaluator import ProjectEvaluator
from .core.qgis_metadata_adapter import QgisMetadataAdapter
from .core.report import layer_report, project_report
from .ui.panel import MgbValidationPanel

PLUGIN_NAME = "Nota MGB"
MENU_NAME = "&Nota MGB"
PLUGIN_DIR = os.path.dirname(__file__)
DEFAULT_RESOURCE_TYPE = "cdg"
LAST_DIR_KEY = "nota_mgb/last_dir"


def log(message: str, level: Any = Qgis.MessageLevel.Info) -> None:
    QgsMessageLog.logMessage(message, PLUGIN_NAME, level)


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_") or "camada"


def _is_data_layer(layer: Optional[QgsMapLayer]) -> bool:
    return isinstance(layer, (QgsVectorLayer, QgsRasterLayer))


class MgbMetadataPlugin:
    """Classe principal, instanciada pelo QGIS via classFactory."""

    def __init__(self, iface: Any):
        self.iface = iface
        self.catalog = DomainCatalog()
        self.engine = MetadataEvaluationEngine(self.catalog)
        self.project_evaluator = ProjectEvaluator(self.engine)
        self.adapter = QgisMetadataAdapter()
        self.dock: Optional[MgbValidationPanel] = None
        self.action: Optional[QAction] = None

    # --- ciclo de vida -------------------------------------------------------

    def initGui(self) -> None:  # noqa: N802 (nome exigido pelo QGIS)
        icon = QIcon(os.path.join(PLUGIN_DIR, "icon.png"))
        self.action = QAction(icon, "Avaliar metadados (MGB 2.0)", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setStatusTip("Abre o painel Nota MGB")
        self.action.triggered.connect(self.toggle_dock)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(MENU_NAME, self.action)
        self.iface.currentLayerChanged.connect(self.on_layer_changed)

    def unload(self) -> None:
        try:
            self.iface.currentLayerChanged.disconnect(self.on_layer_changed)
        except (TypeError, RuntimeError):
            log("Sinal currentLayerChanged já estava desconectado.")
        if self.action is not None:
            self.iface.removePluginMenu(MENU_NAME, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None

    def toggle_dock(self, checked: bool = True) -> None:
        if self.dock is None:
            self.dock = MgbValidationPanel(self.engine.resource_types(), self.iface.mainWindow())
            self.dock.evaluate_layer_requested.connect(self.evaluate_layer)
            self.dock.evaluate_project_requested.connect(self.evaluate_project)
            self.dock.autofill_requested.connect(self.autofill)
            self.dock.save_requested.connect(self.save_form)
            self.dock.resource_type_changed.connect(self.on_resource_type_changed)
            self.dock.layer_selected.connect(self.select_layer)
            self.dock.export_xml_requested.connect(self.export_xml)
            self.dock.export_project_xml_requested.connect(self.export_project_xml)
            self.dock.export_report_requested.connect(self.export_report)
            self.dock.export_project_report_requested.connect(self.export_project_report)
            self.dock.import_xml_requested.connect(self.import_xml)
            self.dock.visibilityChanged.connect(self.action.setChecked)
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        self.dock.setVisible(bool(checked))
        if checked:
            self.on_layer_changed(self.iface.activeLayer())  # avalia ao abrir

    # --- camada ativa --------------------------------------------------------

    def _layer(self) -> Optional[QgsMapLayer]:
        layer = self.iface.activeLayer()
        if not _is_data_layer(layer):
            self.iface.messageBar().pushInfo(PLUGIN_NAME, "Selecione uma camada vetorial ou raster.")
            return None
        return layer

    def _resource_type(self, layer: QgsMapLayer) -> str:
        block = self.adapter.read_plugin_block(layer)
        return block.get("resourceType") or DEFAULT_RESOURCE_TYPE

    def on_layer_changed(self, layer: Optional[QgsMapLayer]) -> None:
        if self.dock is None:
            return
        self.dock.clear_result()
        if not _is_data_layer(layer):
            self.dock.set_layer_name(None)
            return
        self.dock.set_layer_name(layer.name())
        self.dock.set_resource_type(self._resource_type(layer))
        if self.dock.isVisible():
            self.evaluate_layer()

    def on_resource_type_changed(self, key: str) -> None:
        layer = self.iface.activeLayer()
        if _is_data_layer(layer):
            save_metadata(layer, {"resourceType": key})
            self.evaluate_layer()

    def select_layer(self, layer_id: str) -> None:
        layer = QgsProject.instance().mapLayer(layer_id)
        if layer is not None:
            self.iface.setActiveLayer(layer)
            self.dock.tabs.setCurrentIndex(0)

    # --- avaliar -------------------------------------------------------------

    def evaluate_layer(self) -> Optional[Dict[str, Any]]:
        layer = self._layer()
        if layer is None or self.dock is None:
            return None
        metadata = self.adapter.extract_layer_metadata(layer)
        result = self.engine.evaluate(metadata, self._resource_type(layer))
        self.dock.show_result(result, self.engine.weights)
        domain_values = {name: self.catalog.allowed_values(name) for name in self.catalog.available_domains()}
        self.dock.build_form(result["issues"], self.engine.elements, domain_values, metadata)
        return result

    def _project_layers(self) -> List[Dict[str, Any]]:
        layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if not _is_data_layer(layer):
                continue
            layers.append(
                {
                    "id": layer.id(),
                    "name": layer.name(),
                    "resource_type": self._resource_type(layer),
                    "metadata": self.adapter.extract_layer_metadata(layer),
                }
            )
        return layers

    def evaluate_project(self) -> Optional[Dict[str, Any]]:
        layers = self._project_layers()
        if not layers:
            self.iface.messageBar().pushInfo(PLUGIN_NAME, "O projeto não tem camadas vetoriais ou raster.")
            return None
        report = self.project_evaluator.evaluate_layers(layers)
        if self.dock is not None:
            self.dock.show_project(report)
        return report

    # --- corrigir ------------------------------------------------------------

    def autofill(self) -> None:
        layer = self._layer()
        if layer is None:
            return
        metadata = self.adapter.extract_layer_metadata(layer)
        changes = propose_fill(metadata, layer_facts(layer), self.engine)
        if not changes:
            self.dock.set_fix_message("Nada a calcular: o que dá para preencher sozinho já está preenchido.")
            return
        save_metadata(layer, {c["id"]: c["new"] for c in changes})
        log(f"{layer.name()}: preenchidos {', '.join(c['id'] for c in changes)}")
        self.evaluate_layer()
        details = "\n".join(f"• {c['label']}: {c['reason']}" for c in changes)
        self.dock.set_fix_message(
            f"{len(changes)} campo(s) preenchido(s) automaticamente (passe o mouse para ver quais). "
            "Complete o restante abaixo.",
            details,
        )
        self.iface.messageBar().pushSuccess(
            PLUGIN_NAME, f"{len(changes)} campo(s) preenchido(s). Salve o projeto."
        )

    def save_form(self, values: Dict[str, Any]) -> None:
        layer = self._layer()
        if layer is None:
            return
        if not values:
            self.dock.set_fix_message("Nenhum valor informado.")
            return
        save_metadata(layer, values)
        result = self.evaluate_layer()
        if result and result["is_conforme"]:
            self.iface.messageBar().pushSuccess(
                PLUGIN_NAME, f"Camada conforme: {result['total_score']:.0f}/100."
            )
            self.dock.tabs.setCurrentIndex(0)

    # --- exportar / importar ---------------------------------------------------

    def _ask_path(self, title: str, file_name: str, file_filter: str, save: bool = True) -> Optional[str]:
        settings = QgsSettings()
        start = os.path.join(settings.value(LAST_DIR_KEY, os.path.expanduser("~")), file_name)
        if save:
            path, _ = QFileDialog.getSaveFileName(self.iface.mainWindow(), title, start, file_filter)
        else:
            path, _ = QFileDialog.getOpenFileName(
                self.iface.mainWindow(), title, os.path.dirname(start), file_filter
            )
        if path:
            settings.setValue(LAST_DIR_KEY, os.path.dirname(path))
        return path or None

    def _write(self, path: str, text: str) -> bool:
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError as exc:
            self.iface.messageBar().pushCritical(PLUGIN_NAME, f"Não foi possível gravar {path}: {exc}")
            return False
        return True

    def export_xml(self) -> None:
        layer = self._layer()
        if layer is None:
            return
        metadata = self.adapter.extract_layer_metadata(layer)
        result = self.engine.evaluate(metadata, self._resource_type(layer))
        if not result["is_conforme"]:
            self.iface.messageBar().pushWarning(PLUGIN_NAME, "Corrija as pendências antes de exportar o XML.")
            return
        path = self._ask_path("Exportar XML ISO 19115-3", f"{_safe_name(layer.name())}.xml", "XML (*.xml)")
        if path and self._write(path, to_xml(metadata)):
            log(f"XML exportado: {path}")
            self.iface.messageBar().pushSuccess(PLUGIN_NAME, f"XML exportado: {path}")

    def export_project_xml(self) -> None:
        layers = self._project_layers()
        if not layers:
            self.iface.messageBar().pushInfo(PLUGIN_NAME, "O projeto não tem camadas vetoriais ou raster.")
            return
        settings = QgsSettings()
        folder = QFileDialog.getExistingDirectory(
            self.iface.mainWindow(),
            "Pasta para os XML",
            settings.value(LAST_DIR_KEY, os.path.expanduser("~")),
        )
        if not folder:
            return
        settings.setValue(LAST_DIR_KEY, folder)
        written, skipped, used = 0, [], set()
        for entry in layers:
            result = self.engine.evaluate(entry["metadata"], entry["resource_type"])
            if not result["is_conforme"]:
                skipped.append(entry["name"])
                continue
            base = _safe_name(entry["name"])
            name, n = base, 2
            while name in used:
                name, n = f"{base}_{n}", n + 1
            used.add(name)
            if self._write(os.path.join(folder, f"{name}.xml"), to_xml(entry["metadata"])):
                written += 1
        message = f"{written} XML exportado(s) em {folder}."
        if skipped:
            message += f" Não conformes (não exportadas): {', '.join(skipped)}."
        log(message)
        self.iface.messageBar().pushInfo(PLUGIN_NAME, message)

    def _save_report(self, html: str, file_name: str) -> None:
        path = self._ask_path("Salvar relatório", file_name, "HTML (*.html)")
        if path and self._write(path, html):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def export_report(self) -> None:
        layer = self._layer()
        if layer is None:
            return
        result = self.engine.evaluate(self.adapter.extract_layer_metadata(layer), self._resource_type(layer))
        self._save_report(
            layer_report(layer.name(), result, self.engine.weights),
            f"nota_mgb_{_safe_name(layer.name())}.html",
        )

    def export_project_report(self) -> None:
        report = self.evaluate_project()
        if report is not None:
            self._save_report(project_report(report), "nota_mgb_projeto.html")

    def import_xml(self) -> None:
        layer = self._layer()
        if layer is None:
            return
        path = self._ask_path("Importar metadado XML", "", "XML (*.xml)", save=False)
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = from_xml(handle.read())
        except (OSError, UnicodeDecodeError, XmlError) as exc:
            self.iface.messageBar().pushCritical(PLUGIN_NAME, f"Não foi possível ler o XML: {exc}")
            return
        schema = "ISO 19139 (MGB 2009)" if data["_schema"] == "iso19139" else "ISO 19115-3"
        values = importable(data)
        answer = QMessageBox.question(
            self.iface.mainWindow(),
            PLUGIN_NAME,
            f'Importar {len(values)} campo(s) do {schema} para a camada "{layer.name()}"?\n\n'
            "Os valores atuais desses campos serão substituídos.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        save_metadata(layer, values)
        log(f"{layer.name()}: importado {path} ({schema})")
        self.evaluate_layer()
        tip = (
            ' Use "Preencher automaticamente" para migrar ao Perfil MGB 2.0.'
            if data["_schema"] == "iso19139"
            else ""
        )
        self.iface.messageBar().pushSuccess(PLUGIN_NAME, f"Metadado importado ({schema}).{tip}")


__all__ = ["MgbMetadataPlugin"]

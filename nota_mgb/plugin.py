"""Nota MGB: registro no QGIS e controle do painel (avaliar, corrigir).

Copyright (C) 2026 Ibexdev
Licença: GNU GPL v2 ou superior.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from qgis.core import Qgis, QgsMapLayer, QgsMessageLog, QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .core.autofill import propose_fill
from .core.domain_catalog import DomainCatalog
from .core.evaluation_engine import MetadataEvaluationEngine
from .core.layer_facts import layer_facts
from .core.metadata_store import save_metadata
from .core.project_evaluator import ProjectEvaluator
from .core.qgis_metadata_adapter import QgisMetadataAdapter
from .ui.panel import MgbValidationPanel

PLUGIN_NAME = "Nota MGB"
MENU_NAME = "&Nota MGB"
PLUGIN_DIR = os.path.dirname(__file__)
DEFAULT_RESOURCE_TYPE = "cdg"


def log(message: str, level: Any = Qgis.MessageLevel.Info) -> None:
    QgsMessageLog.logMessage(message, PLUGIN_NAME, level)


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

    def evaluate_project(self) -> None:
        layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if not _is_data_layer(layer):
                continue
            layers.append({
                "id": layer.id(),
                "name": layer.name(),
                "resource_type": self._resource_type(layer),
                "metadata": self.adapter.extract_layer_metadata(layer),
            })
        if not layers:
            self.iface.messageBar().pushInfo(PLUGIN_NAME, "O projeto não tem camadas vetoriais ou raster.")
            return
        self.dock.show_project(self.project_evaluator.evaluate_layers(layers))

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
        filled = "\n".join(f"• {c['label']}: {c['reason']}" for c in changes)
        self.dock.set_fix_message(f"Preenchido automaticamente:\n{filled}\n\nConfira e complete o restante abaixo.")
        self.iface.messageBar().pushSuccess(PLUGIN_NAME, f"{len(changes)} campo(s) preenchido(s). Salve o projeto.")

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
            self.iface.messageBar().pushSuccess(PLUGIN_NAME, f"Camada conforme: {result['total_score']:.0f}/100.")
            self.dock.tabs.setCurrentIndex(0)


__all__ = ["MgbMetadataPlugin"]

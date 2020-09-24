from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsProject,
    QgsApplication)

import os

from core.task_manager import TracingCAJ


class Tracing:

    def __init__(self, iface):
        # save reference to the QGIS interface
        self.iface = iface

        self.__pipeline = None
        self.__valves = None

        # Initialize plugin directory
        self.__tm = QgsApplication.taskManager()
        self.plugin_dir = os.path.dirname(__file__)
        self.icon_folder = self.plugin_dir + os.sep + 'icons' + os.sep

    def initGui(self):
        # create action that will start plugin configuration
        self._set_info_button()
        self.action.setObjectName("TracingAction")
        self.action.setStatusTip("Start tracing from selected pipeline")
        self.action.triggered.connect(self.run)

        # add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Tracing plugins", self.action)

    def unload(self):
        # remove the plugin menu item and icon
        self.iface.removePluginMenu("&Tracing plugins", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        self.__pipeline = QgsProject.instance().mapLayersByName('pipelines_tracing')
        self.__valves = QgsProject.instance().mapLayersByName('valves_tracing')

        if len(self.__pipeline) > 0 and len(self.__valves) > 0:
            pipeline_select = self.iface.activeLayer().selectedFeatures()
            if pipeline_select:
                if len(pipeline_select) == 1:
                    tracing_caj = TracingCAJ(self.__tm, self.__pipeline, self.__valves)
                    tracing_caj.start()
                else:
                    self.iface.messageBar().pushMessage("Info",
                                                        "Select only ONE network to start", level=Qgis.Info)
                    print('Info - Select only ONE network to start')
        else:
            self.iface.messageBar().pushMessage("Info", 'Rename layers for "pipelines_tracing" and "valves_tracing" '
                                                , level=Qgis.Info)
            print('Rename layers for "pipelines_tracing" and "valves_tracing"')

    def error(self):
        self.iface.messageBar().pushMessage("Error occorred",
                                            "Error",
                                            level=Qgis.Critical)

        QgsMessageLog.logMessage('Error occurred')

    def _set_info_button(self):
        """ Set main information button (always visible) """

        icon_path = self.icon_folder + 'tracingcaj.png'
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            self.action = QAction(icon, "Start Tracing", self.iface.mainWindow())
        else:
            self.action = QAction("Start Tracing", self.iface.mainWindow())

        # add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)

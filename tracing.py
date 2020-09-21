from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from qgis.core import (
                       Qgis,
                       QgsMessageLog,
                       QgsProject,
                       QgsApplication)

import os

from core.task_manager import TracingCAJ


class TracingPlugin:

    def __init__(self, iface):
        # save reference to the QGIS interface
        self.iface = iface

        self.__networks = None
        self.__registers = None

        # Initialize plugin directory
        self.__tm = QgsApplication.taskManager()
        self.plugin_dir = os.path.dirname(__file__)
        self.icon_folder = self.plugin_dir + os.sep + 'icons' + os.sep

    def initGui(self):
        # create action that will start plugin configuration
        self.__set_info_button()
        self.action.setObjectName("TracingAction")
        self.action.setWhatsThis("Configuration for tracing plugin")
        self.action.setStatusTip("Start tracing from a recovered network")
        self.action.triggered.connect(self.run)

        # add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Tracing plugins", self.action)

    def unload(self):
        # remove the plugin menu item and icon
        self.iface.removePluginMenu("&Tracing plugins", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        self.__networks = QgsProject.instance().mapLayersByName('networks_tracing')
        self.__registers = QgsProject.instance().mapLayersByName('registers_tracing')

        if len(self.__networks) > 0 and len(self.__registers) > 0:
            network_select = self.iface.activeLayer().selectedFeatures()
            if network_select:
                if len(network_select) == 1:
                    tracing_caj = TracingCAJ(self.__tm, self.__networks, self.__registers)
                    tracing_caj.start()
                else:
                    self.iface.messageBar().pushMessage("Info",
                                                        "Selecione apenas UMA rede para iniciar o tracing", level=Qgis.Info)
                    print('Info - Selecione apenas UMA rede para iniciar o tracing')
        else:
            self.iface.messageBar().pushMessage("Error", "Renomear as redes para 'networks_tracing' e registros para "
                                                         "'registers_tracing'", level=Qgis.Warning)
            print('Renomear as redes para networks_tracing e registros para registers_tracing')

    def error(self):
        self.iface.messageBar().pushMessage("Error occorred",
                                            "Error",
                                            level=Qgis.Critical)
        QgsMessageLog.logMessage('Error occurred')

    def __set_info_button(self):
        """ Set main information button (always visible) """

        icon_path = self.icon_folder + 'tracingcaj.png'
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            self.action = QAction(icon, "Start Tracing", self.iface.mainWindow())
        else:
            self.action = QAction("Start Tracing", self.iface.mainWindow())

        # add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)

from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsProject,
    QgsApplication,
    QgsMapLayer)

import os


from global_vars import init_global_vars
from controller import ConfigController


class Tracing:

    def __init__(self, iface):
        # save reference to the QGIS interface
        self.iface = iface
        self.dlg_config = None

        self.__pipeline = None
        self.__valves = None

        # Initialize plugin directory
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

        # Initialize global variables
        init_global_vars(self.iface)

    def unload(self):
        # remove the plugin menu item and icon
        self.iface.removePluginMenu("&Tracing plugins", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        if self.dlg_config is None:
            self.dlg_config = ConfigController()

        mapLayers = QgsProject.instance().mapLayers() # Load layers dictionary from the project
        layer_list = []

        for _id in mapLayers.keys():
            if mapLayers[_id].type() == QgsMapLayer.VectorLayer:
                layer_list.append((mapLayers[_id].name(), _id))

        if len(layer_list) == 0:
            QMessageBox.information(None,
                                    QCoreApplication.translate('GroupStats', 'Information'),
                                    QCoreApplication.translate('GroupStats', 'Vector layers not found'))
            return

        self.dlg_config.iface = self.iface
        self.dlg_config.set_layers(layer_list)
        # show the dialog config
        self.dlg_config.show()


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

if __name__ == '__main__':
    Tracing().run()
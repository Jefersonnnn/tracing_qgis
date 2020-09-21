from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from qgis.core import (QgsTask,
                       QgsMessageLog,
                       Qgis,
                       QgsSpatialIndex,
                       QgsPointXY,
                       QgsProject,
                       QgsApplication)

import os

class TracingPlugin:

  def __init__(self, iface):
    # save reference to the QGIS interface
    self.iface = iface

    self.networks = None
    self.registers = None
    # Initialize plugin directory
    self.tm = QgsApplication.taskManager()
    self.plugin_dir = os.path.dirname(__file__)
    self.icon_folder = self.plugin_dir + os.sep + 'icons' + os.sep

  def initGui(self):
    # create action that will start plugin configuration
    self.set_info_button()
    self.action.setObjectName("testAction")
    self.action.setWhatsThis("Configuration for test plugin")
    self.action.setStatusTip("This is status tip")
    self.action.triggered.connect(self.run)

    # add toolbar button and menu item
    self.iface.addToolBarIcon(self.action)
    self.iface.addPluginToMenu("&Test plugins", self.action)

    # connect to signal renderComplete which is emitted when canvas
    # rendering is done
    self.iface.mapCanvas().renderComplete.connect(self.renderTest)

  def unload(self):
    # remove the plugin menu item and iconq
    self.iface.removePluginMenu("&Test plugins", self.action)
    self.iface.removeToolBarIcon(self.action)

    # disconnect form signal of the canvas
    self.iface.mapCanvas().renderComplete.disconnect(self.renderTest)

  def run(self):
    self.networks = QgsProject.instance().mapLayersByName('networks_tracing')
    self.registers = QgsProject.instance().mapLayersByName('registers_tracing')

    if len(self.networks) > 0 and len(self.registers) > 0:
      network_select = self.iface.activeLayer().selectedFeatures()
      if network_select:
          tracing_caj = TracingCAJ(self.tm, self.networks, self.registers)
          tracing_caj.start()
    else:
      print('Renomear as redes para networks_tracing e registros para registers_tracing')


  def renderTest(self, painter):
    # use painter for drawing to map canvas
    print("TestPlugin: renderTest called!")

  def error(self):
    QgsMessageLog.logMessage('Error occurred')


  def set_info_button(self):
    """ Set main information button (always visible) """

    icon_path = self.icon_folder + 'tracingcaj.png'
    if os.path.exists(icon_path):
        icon = QIcon(icon_path)
        self.action = QAction(icon, "Show info", self.iface.mainWindow())
    else:
        self.action = QAction("Show info", self.iface.mainWindow())

    # add toolbar button and menu item
    self.iface.addToolBarIcon(self.action)

class TracingQGIS(QgsTask):

    def __init__(self, networks, registers, description='TracingCAJ', user_distance=0.001):

        super().__init__(description, QgsTask.CanCancel)

        self._user_distance = user_distance

        self._networks_features = networks[0]
        self._registers_features = registers[0]

        self._list_registers = []
        self._list_visited_networks = []
        self._list_visited_network_ids = []

        self._q_list_networks = []
        self._q_list_networks_ids = []

        self._iterations = 0
        self._exception = None

        # Cria os índices espaciais
        self._idx_networks = None
        self._idx_registers = None
        if self._idx_registers is None or self._idx_networks is None:
            self.__create_spatial_index()


    def run(self):
        print('RUN')
        QgsMessageLog.logMessage(f'Started task {self.description()}',
                                 'TracingCAJ', Qgis.Info)

        # Busca por redes selecionadas (necessário ser apenas uma)
        selected_network = self._networks_features.selectedFeatures()

        if len(selected_network) != 1:
            QgsMessageLog.logMessage('Selecione apenas UMA rede', 'TracingCAJ', Qgis.Info)
            return False
        else:

            self._q_list_networks.append(selected_network[0].geometry())
            self._q_list_networks_ids.append(selected_network[0].id())

            while len(self._q_list_networks) > 0:
                self._iterations += 1

                # check isCanceled() to handle cancellation
                if self.isCanceled():
                    return False

                network = self._q_list_networks.pop(0)
                network_id = self._q_list_networks_ids.pop(0)
                if network_id not in self._list_visited_network_ids:
                    self._list_visited_networks.append(network)
                    self._list_visited_network_ids.append(network_id)
                    v1 = network.vertexAt(0)

                    v2 = network.vertexAt(len(network.get()) - 1)
                    # v2 = network.vertexAt(len(network.asMultiPolyline()[0]) - 1)
                    try:
                        self.__find_neighbors(v1)
                        self.__find_neighbors(v2)
                    except Exception as e:
                        self._exception = e
                        return False

        return True

    def finished(self, result):
        print('FINISHED')
        if result:
            self._registers_features.selectByIds(self._list_registers)
            self._networks_features.selectByIds(self._list_visited_network_ids)

            QgsMessageLog.logMessage(
                f'Task "{self.description()}" completed\n' \
                f'RandomTotal: with {self._iterations} iterations\n'
                f'Networks: {self._list_visited_network_ids} (with {self._list_registers} registers)\n',
                'TracingCAJ', Qgis.Success)
        else:
            if self._exception is None:
                QgsMessageLog.logMessage(
                    'RandomTask "{name}" not successful but without ' \
                    'exception (probably the task was manually ' \
                    'canceled by the user)'.format(
                        name=self.description()),
                    'TracingCAJ', Qgis.Warning)
            else:
                QgsMessageLog.logMessage(
                    'RandomTask "{name}" Exception: {exception}'.format(
                        name=self.description(),
                        exception=self._exception),
                    'TracingCAJ', Qgis.Critical)
                raise self._exception

    def cancel(self):
        print('CANCEL')
        QgsMessageLog.logMessage(
            f'TracingTrask {self.description()} was canceled', 'TracingCAJ',
            Qgis.Info)
        super().cancel()

    def __create_spatial_index(self):
        self._idx_networks = QgsSpatialIndex(self._networks_features.getFeatures(),
                                             flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        self._idx_registers = QgsSpatialIndex(self._registers_features.getFeatures(),
                                              flags=QgsSpatialIndex.FlagStoreFeatureGeometries)

    def __find_neighbors(self, point_vertex):

        reg_nearest = self._idx_registers.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=1,
                                                          maxDistance=self._user_distance)
        if len(reg_nearest) > 0:
            self._list_registers.append(reg_nearest[0])
        else:
            network_nearest = self._idx_networks.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=3,
                                                                 maxDistance=self._user_distance)
            # network_nearest = idx_rede_agua.intersects(QgsRectangle(QgsPointXY(pointVertex), QgsPointXY(pointVertex)))
            if len(network_nearest) > 0:
                for network_id in network_nearest:
                    network_geo = self._idx_networks.geometry(network_id)
                    if network_id not in self._list_visited_network_ids:
                        self._q_list_networks_ids.append(network_id)
                        self._q_list_networks.append(network_geo)

class TracingCAJ:
    def __init__(self, task_manager, networks, registers):
        self.networks = networks
        self.registers = registers
        self.task_manger = task_manager

        print(self.networks, self.registers, self.task_manger)

    def start(self):
        print('Instanciando TracingQGIS')
        tracing_task = TracingQGIS(self.networks, self.registers)
        print('Adicionando em Tasks')
        self.task_manger.addTask(tracing_task)

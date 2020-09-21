from qgis.core import (QgsTask,
                       QgsMessageLog,
                       Qgis,
                       QgsSpatialIndex,
                       QgsPointXY,
                       QgsProject, QgsApplication)


class TracingNetworks(QgsTask):

    def __init__(self, networks, registers, description='TracingCAJ', user_distance=0.001):
        super().__init__(description, QgsTask.CanCancel)

        self.__user_distance = user_distance

        self.__networks_features = networks[0]
        self.__registers_features = registers[0]

        self.__list_registers = []
        self.__list_visited_networks = []
        self.__list_visited_network_ids = []

        self.__q_list_networks = []
        self.__q_list_networks_ids = []

        self.__iterations = 0
        self.__exception = None

        # Cria os índices espaciais
        self.__idx_networks = None
        self.__idx_registers = None
        if self.__idx_registers is None or self.__idx_networks is None:
            self.__create_spatial_index()

    def run(self):
        QgsMessageLog.logMessage(f'Started task {self.description()}',
                                 'TracingCAJ', Qgis.Info)

        # Busca por redes selecionadas (necessário ser apenas uma)
        selected_network = self.__networks_features.selectedFeatures()

        if len(selected_network) != 1:
            QgsMessageLog.logMessage('Selecione apenas UMA rede', 'TracingCAJ', Qgis.Info)
            return False
        else:

            self.__q_list_networks.append(selected_network[0].geometry())
            self.__q_list_networks_ids.append(selected_network[0].id())

            while len(self.__q_list_networks) > 0:
                self.__iterations += 1

                # check isCanceled() to handle cancellation
                if self.isCanceled():
                    return False

                network = self.__q_list_networks.pop(0)
                network_id = self.__q_list_networks_ids.pop(0)
                if network_id not in self.__list_visited_network_ids:
                    self.__list_visited_networks.append(network)
                    self.__list_visited_network_ids.append(network_id)

                    v1 = network.vertexAt(0)
                    v2 = network.vertexAt(len(network.get()) - 1)
                    try:
                        self.__find_neighbors(v1)
                        self.__find_neighbors(v2)
                    except Exception as e:
                        self.__exception = e
                        return False

        return True

    def finished(self, result):
        if result:
            self.__registers_features.selectByIds(self.__list_registers)
            self.__networks_features.selectByIds(self.__list_visited_network_ids)

            QgsMessageLog.logMessage(f"Task {self.description()} has been executed correctly"
                                     f"Iterations: {self.__iterations}"
                                     f"Networks: {self.__list_visited_network_ids}"
                                     f"Registers: {self.__list_registers}",
                                     level=Qgis.Success)
        else:
            if self.__exception is None:
                QgsMessageLog.logMessage(f"Tracing {self.description()} not successful "
                                         f"but without exception "
                                         f"(probably the task was manually canceled by the user)",
                                         level=Qgis.Warning)
            else:
                QgsMessageLog.logMessage(f"Task {self.description()}"
                                         f"Exception: {self.__exception}", level=Qgis.Critical)
                raise self.__exception

    def cancel(self):
        QgsMessageLog.logMessage(
            f'TracingTrask {self.description()} was canceled', level=Qgis.Info)
        super().cancel()

    def __create_spatial_index(self):
        self.__idx_networks = QgsSpatialIndex(self.__networks_features.getFeatures(),
                                              flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        self.__idx_registers = QgsSpatialIndex(self.__registers_features.getFeatures(),
                                               flags=QgsSpatialIndex.FlagStoreFeatureGeometries)

    def __find_neighbors(self, point_vertex):

        reg_nearest = self.__idx_registers.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=1,
                                                           maxDistance=self.__user_distance)
        if len(reg_nearest) > 0:
            self.__list_registers.append(reg_nearest[0])
        else:
            network_nearest = self.__idx_networks.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=3,
                                                                  maxDistance=self.__user_distance)
            # network_nearest = idx_rede_agua.intersects(QgsRectangle(QgsPointXY(pointVertex), QgsPointXY(pointVertex)))
            if len(network_nearest) > 0:
                for network_id in network_nearest:
                    network_geo = self.__idx_networks.geometry(network_id)
                    if network_id not in self.__list_visited_network_ids:
                        self.__q_list_networks_ids.append(network_id)
                        self.__q_list_networks.append(network_geo)

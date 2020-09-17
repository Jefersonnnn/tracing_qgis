from qgis._core import QgsTask, QgsMessageLog, Qgis, QgsSpatialIndex, QgsPointXY, QgsProject

name_layer_registro = 'Registro de Manobra'
name_layer_rede = 'rede_de_agua'

rede_agua = QgsProject.instance().mapLayersByName(name_layer_rede)[0]
registros = QgsProject.instance().mapLayersByName(name_layer_registro)[0]

class TracingQGIS(QgsTask):

    def __init__(self, networks, registers, description='TracingCAJ', user_distance=0.001):
        super().__init__(description, QgsTask.CanCancel)
        self._user_distance = user_distance

        self._networks_features = networks
        self._registers_features = registers

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
        QgsMessageLog.logMessage(f'Started task {self.description()}',
                                 'TracingCAJ', Qgis.Info)

        # Busca por redes selecionadas (necessário ser apenas uma)
        selected_network = rede_agua.selectedFeatures()

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
        QgsMessageLog.logMessage(
            f'TracingTrask {self.description()} was canceled', 'TracingCAJ',
            Qgis.Info)
        super().cancel()

    def __create_spatial_index(self):
        self._idx_networks = QgsSpatialIndex(self._networks_features.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        self._idx_registers = QgsSpatialIndex(self._registers_features.getFeatures(), flags=QgsSpatialIndex.FlagStoreFeatureGeometries)

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

# tracing_task = TracingQGIS(rede_agua, registros)
# QgsApplication.taskManager().addTask(tracing_task)

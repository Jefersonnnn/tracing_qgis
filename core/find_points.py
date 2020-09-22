from qgis.core import QgsTask, QgsProject, QgsSpatialIndex, QgsPointXY, QgsMessageLog


class FindPoints(QgsTask):

    def __init__(self, qpipelines, description='FindHds'):
        super().__init__(description, QgsTask.CanCancel)

        self.hds_feature = QgsProject.instance().mapLayersByName('hds_tracing')[0]
        self.idx_hds = QgsSpatialIndex(self.hds_feature.getFeatures(),
                                  flags=QgsSpatialIndex.FlagStoreFeatureGeometries)

        self.__exception = None
        self.q_list_pipelines = qpipelines

        self.list_hds = []

    def find_hds_by_nearest_neighbor(point_vertex):
        hds_nearest = idx_hds.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=20,
                                              maxDistance=30)

        if len(hds_nearest) > 0:
            for hd in hds_nearest:
                list_hds.append(hd)

    def find_hds_by_geo_intersection(self, buff):
        for hds in self.hds_feature.getFeatures():
            if buff.intersects(hds.geometry()):
                hds_nearest = buff.intersection(hds.geometry())
                self.list_hds.append(hds.id())

    def find_hds_by_intersects_spatial(x1, x2):
        rect = QgsRectangle(QgsPointXY(x1.x(), x1.y()), QgsPointXY(x2.x(), x2.y()))
        p_center = rect.center()
        rect = QgsRectangle().fromCenterAndSize(p_center, rect.width(), rect.height())

        hds_nearest = idx_hds.intersects(rect)

        if len(hds_nearest) > 0:
            for hd in hds_nearest:
                list_hds.append(hd)

    def run(self):

        try:
            while len(q_list_networks) > 0:
                network = q_list_networks.pop(0)
                net_geo = network.geometry()

                buff = net_geo.buffer(15, 1)
                for i in range(0, len(net_geo.get()) - 1):
                    find_hds_by_intersects_spatial(net_geo.vertexAt(i), net_geo.vertexAt(i + 1))

                # find_hds_by_geo_intersection(buff)

                # for i in range(len(net_geo.get())):
                #    find_hds_by_nearest_neighbor(net_geo.vertexAt(i))

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
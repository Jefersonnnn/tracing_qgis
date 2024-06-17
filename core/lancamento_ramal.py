from qgis._core import QgsVectorLayer, QgsFeature, QgsGeometry
from qgis.core import (QgsTask,
                              QgsMessageLog,
                              Qgis,
                              QgsSpatialIndex,
                              QgsPointXY,
                              QgsProject, QgsApplication)


class LancamentoRamal(QgsTask):
    """
    Adiciona 'ramais' como links entre redes e hidrômetros
    """

    def __init__(self, pipelines, hidrometers, description='CreateRamalCAJ', user_distance=30):
        super().__init__(description, QgsTask.CanCancel)
        self.__user_distance = user_distance

        self.__pipelines = pipelines[0]
        self.__hidrometers = hidrometers[0]

        # Cria os índices espaciais
        self.__idx_pipelines = None
        if self.__idx_pipelines is None:
            self.__create_spatial_index()

    def run(self):
        QgsMessageLog.logMessage(f'Started task {self.description()}',
                                 'TracingCAJ', Qgis.Info)

        epsg = self.__hidrometers.crs().postgisSrid()
        uri = "LineString?crs=epsg:" + str(epsg) + "&field=id:integer""&field=distance:double(20,2)&index=yes"
        dist = QgsVectorLayer(uri, 'dist', 'memory')

        QgsProject.instance().addMapLayer(dist)
        prov = dist.dataProvider()
        points_features = [point_feature for point_feature in self.__hidrometers.getFeatures()]

        feats = []
        if len(points_features) > 0:
            for p in points_features:
                nearest_pipe = self.find_nearest_pipelines(p.geometry())
                try:
                    minDistPoint = nearest_pipe.closestSegmentWithContext(p.geometry().asPoint())[1]
                    feat = QgsFeature()
                    feat.setGeometry(QgsGeometry.fromPolylineXY([p.geometry().asPoint(), minDistPoint]))
                    feat.setAttributes([points_features.index(p), feat.geometry().length()])
                    feats.append(feat)
                except Exception as e:
                    print(p.id())

        prov.addFeatures(feats)

    def find_nearest_pipelines(self, point):
        pipelines = self.idx_pipelines.nearestNeighbor(point, 1, self.__user_distance)

        if len(pipelines) > 0:
            for pipe in pipelines:
                return self.idx_pipelines.geometry(pipe)

    def finished(self, result):
        if result:
            self.__hidrometers.selectByIds(self.__list_valves)
            self.__pipelines.selectByIds(self.__list_visited_pipelines_ids)

            QgsMessageLog.logMessage(f"Task {self.description()} has been executed correctly"
                                     f"Iterations: {self.__iterations}"
                                     f"Pipelines: {self.__list_visited_pipelines_ids}"
                                     f"Valves: {self.__list_valves}",
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
        self.__idx_pipelines = QgsSpatialIndex(self.__pipelines.getFeatures(),
                                               flags=QgsSpatialIndex.FlagStoreFeatureGeometries)

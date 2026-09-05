from qgis._core import QgsVectorLayer, QgsFeature, QgsGeometry
from qgis.core import (QgsTask,
                              QgsMessageLog,
                              Qgis,
                              QgsSpatialIndex,
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

        self._idx_pipelines = None
        self.__exception = None
        self._ramais_count = 0

    def __create_spatial_index(self):
        # Em run() para não bloquear a thread da GUI.
        self._idx_pipelines = QgsSpatialIndex(self.__pipelines.getFeatures(),
                                              flags=QgsSpatialIndex.FlagStoreFeatureGeometries)

    def run(self):
        try:
            QgsMessageLog.logMessage(f'Started task {self.description()}', 'TracingCAJ', Qgis.Info)

            self.__create_spatial_index()

            epsg = self.__hidrometers.crs().postgisSrid()
            uri = ("LineString?crs=epsg:" + str(epsg) +
                   "&field=id:integer&field=distance:double(20,2)&index=yes")
            dist = QgsVectorLayer(uri, 'dist', 'memory')
            QgsProject.instance().addMapLayer(dist)
            prov = dist.dataProvider()

            feats = []
            for i, p in enumerate(self.__hidrometers.getFeatures()):
                if self.isCanceled():
                    return False

                nearest_pipe = self.find_nearest_pipelines(p.geometry())
                if nearest_pipe is None:
                    continue

                try:
                    min_dist_point = nearest_pipe.closestSegmentWithContext(p.geometry().asPoint())[1]
                    feat = QgsFeature()
                    feat.setGeometry(QgsGeometry.fromPolylineXY([p.geometry().asPoint(), min_dist_point]))
                    feat.setAttributes([i, feat.geometry().length()])
                    feats.append(feat)
                except Exception as e:
                    QgsMessageLog.logMessage(f'Falha no hidrômetro {p.id()}: {e}', 'TracingCAJ', Qgis.Warning)

            prov.addFeatures(feats)
            dist.updateExtents()
            self._ramais_count = len(feats)
            return True
        except Exception as e:
            self.__exception = e
            return False

    def find_nearest_pipelines(self, point):
        pipelines = self._idx_pipelines.nearestNeighbor(point, 1, self.__user_distance)
        if len(pipelines) > 0:
            return self._idx_pipelines.geometry(pipelines[0])
        return None

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage(f"Task {self.description()} has been executed correctly\n"
                                     f"Ramais criados: {self._ramais_count}",
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

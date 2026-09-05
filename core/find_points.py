from collections import deque

from qgis.core import (QgsTask, QgsProject, QgsSpatialIndex, QgsPointXY,
                       QgsMessageLog, QgsVectorLayer, Qgis)


class FindPoints(QgsTask):

    #: Nenhum segmento da rede fica maior que isto ao densificar (em unidades da camada).
    MAX_SEGMENT_LEN = 10
    #: Raio de busca por hidrômetros a partir de cada vértice.
    SEARCH_RADIUS = 25

    def __init__(self, qpipelines, description='FindHds', debug=False):
        super().__init__(description, QgsTask.CanCancel)

        self.debug = debug

        if self.debug:
            self.hds_feature = QgsVectorLayer('C:/Users/jeferson.machado/Desktop/QGIS/shapes/hds_tracing.shp',
                                              "hds_tracing", "ogr")
        else:
            self.hds_feature = QgsProject.instance().mapLayersByName('hds_tracing')[0]

        self.idx_hds = None
        self.__exception = None
        self.q_list_pipelines = deque(qpipelines)
        self.list_hds = set()

    def __create_spatial_index(self):
        # Construído aqui (e não no __init__) para não bloquear a thread da GUI.
        self.idx_hds = QgsSpatialIndex(self.hds_feature.getFeatures(),
                                       flags=QgsSpatialIndex.FlagStoreFeatureGeometries)

    def find_hds_by_nearest_neighbor(self, point_vertex):
        hds_nearest = self.idx_hds.nearestNeighbor(QgsPointXY(point_vertex),
                                                   neighbors=10,
                                                   maxDistance=self.SEARCH_RADIUS)
        self.list_hds.update(hds_nearest)

    def run(self):
        try:
            self.__create_spatial_index()

            while len(self.q_list_pipelines) > 0:
                if self.isCanceled():
                    return False

                pipeline = self.q_list_pipelines.popleft()
                # densifyByDistance resolve "nenhum segmento > MAX_SEGMENT_LEN" num
                # único passe, substituindo o antigo laço de subdivisão O(n²).
                densified = pipeline.geometry().densifyByDistance(self.MAX_SEGMENT_LEN)

                for vertex in densified.vertices():
                    if self.isCanceled():
                        return False
                    self.find_hds_by_nearest_neighbor(vertex)
        except Exception as e:
            self.__exception = e
            return False

        return True

    def finished(self, result):
        if result:
            self.hds_feature.selectByIds(list(self.list_hds))

            QgsMessageLog.logMessage(f"Task {self.description()} has been executed correctly\n"
                                     f"HDS: {sorted(self.list_hds)}",
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


if __name__ == '__main__':
    path_to_pipeline_layer = "C:\\Users\\jeferson.machado\\Desktop\\QGIS\\shapes\\rede_agua_tracing.shp"

    pipelines = QgsVectorLayer(path_to_pipeline_layer, "Pipeline layer", "ogr")
    if not pipelines.isValid():
        print("Layer failed to load!")
    else:
        QgsProject.instance().addMapLayer(pipelines)

    pipes_ids = [6495]
    pipelines.selectByIds(pipes_ids)
    qlist_pipes = [x for x in pipelines.getSelectedFeatures()]

    find_p = FindPoints(qlist_pipes, debug=True)
    find_p.run()

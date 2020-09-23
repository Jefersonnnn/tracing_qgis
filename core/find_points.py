from qgis._core import QgsGeometry, QgsDistanceArea
from qgis.core import QgsTask, QgsProject, QgsSpatialIndex, QgsPointXY, QgsMessageLog, QgsRectangle, QgsVectorLayer, \
    QgsApplication, QgsPoint, Qgis, QgsWkbTypes
from qgis.utils import iface


class FindPoints(QgsTask):

    def __init__(self, qpipelines, description='FindHds', debug=False):
        super().__init__(description, QgsTask.CanCancel)

        self.debug = debug

        if self.debug:
            self.hds_feature = QgsVectorLayer('C:/Users/jeferson.machado/Desktop/QGIS/shapes/hds_tracing.shp',
                                              "hds_tracing", "ogr")
        else:
            self.hds_feature = QgsProject.instance().mapLayersByName('hds_tracing')[0]
        self.idx_hds = QgsSpatialIndex(self.hds_feature.getFeatures(),
                                       flags=QgsSpatialIndex.FlagStoreFeatureGeometries)

        self.__exception = None
        self.q_list_pipelines = qpipelines
        self.list_hds = []

    def find_hds_by_nearest_neighbor(self, points_vertex):
        hds_nearest = self.idx_hds.nearestNeighbor(point=QgsPointXY(points_vertex), neighbors=10,
                                                   maxDistance=25)

        if len(hds_nearest) > 0:
            for hd in hds_nearest:
                if hd not in self.list_hds:
                    self.list_hds.append(hd)

    def split_line(self, p1, p2, pos, pipeline):
        geo = QgsGeometry.fromPolyline([p1, p2])
        center = geo.centroid()
        pipeline.insert(pos, center.asPoint())

    def get_points(self, pipeline):
        pipe = [QgsPointXY(pipeline.vertexAt(i)) for i in range(pipeline.get().childCount())]
        distances = []
        breakForce = 0
        while True:
            if breakForce == 1000:
                break
            # check isCanceled() to handle cancellation
            if self.isCanceled():
                return False
            increment = 0
            pipeline = QgsGeometry.fromMultiPointXY(pipe)

            for i in range(len(pipe) -1):
                p1 = pipeline.vertexAt(i)
                p2 = pipeline.vertexAt(i + 1)
                d = QgsDistanceArea()
                distance = d.measureLine(QgsPointXY(p1), QgsPointXY(p2))
                distances.append(distance)
                if distance > 10:
                    self.split_line(p1, p2, i+1+increment, pipe)
                    increment += 1

            breakForce += 1
            if distances:
                if max(distances) <= 10:
                    break
            distances.clear()
        return pipeline

    def run(self):

        try:
            while len(self.q_list_pipelines) > 0:
                pipeline = self.q_list_pipelines.pop(0)
                pipeline_geo = self.get_points(pipeline.geometry())

                for i in range(0, len(pipeline_geo.get()) - 1):
                    self.find_hds_by_nearest_neighbor(pipeline_geo.vertexAt(i))

        except Exception as e:
            self.__exception = e
            return False

        return True

    def finished(self, result):
        if result:
            self.hds_feature.selectByIds(self.list_hds)

            QgsMessageLog.logMessage(f"Task {self.description()} has been executed correctly\n"
                                     f"HDS: {self.list_hds}",
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

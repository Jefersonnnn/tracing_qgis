from qgis.core import (QgsTask,
                       QgsMessageLog,
                       Qgis,
                       QgsSpatialIndex,
                       QgsPointXY,
                       QgsProject, QgsApplication)


class TracingPipelines(QgsTask):

    def __init__(self, pipelines, valves, description='TracingCAJ', user_distance=0.001):
        super().__init__(description, QgsTask.CanCancel)

        self.__user_distance = user_distance

        self.__pipelines_features = pipelines[0]
        self.__valves_features = valves[0]

        self.__list_valves = []
        self.__list_visited_pipelines = []
        self.__list_visited_pipelines_ids = []

        self.__q_list_pipelines = []
        self.__q_list_pipelines_ids = []

        self.__iterations = 0
        self.__exception = None

        # Cria os índices espaciais
        self.__idx_pipelines = None
        self.__idx_valves = None
        if self.__idx_valves is None or self.__idx_pipelines is None:
            self.__create_spatial_index()

    def run(self):
        QgsMessageLog.logMessage(f'Started task {self.description()}',
                                 'TracingCAJ', Qgis.Info)

        # Busca por redes selecionadas (necessário ser apenas uma)
        selected_pipeline = self.__pipelines_features.selectedFeatures()

        if len(selected_pipeline) != 1:
            QgsMessageLog.logMessage('Selecione apenas UMA rede', 'TracingCAJ', Qgis.Info)
            return False
        else:

            self.__q_list_pipelines.append(selected_pipeline[0].geometry())
            self.__q_list_pipelines_ids.append(selected_pipeline[0].id())

            while len(self.__q_list_pipelines) > 0:
                self.__iterations += 1

                # check isCanceled() to handle cancellation
                if self.isCanceled():
                    return False

                pipeline = self.__q_list_pipelines.pop(0)
                pipeline_id = self.__q_list_pipelines_ids.pop(0)
                if pipeline_id not in self.__list_visited_pipelines_ids:
                    self.__list_visited_pipelines.append(pipeline)
                    self.__list_visited_pipelines_ids.append(pipeline_id)

                    v1 = pipeline.vertexAt(0)
                    v2 = pipeline.vertexAt(len(pipeline.get()) - 1)
                    try:
                        self.__find_neighbors(v1)
                        self.__find_neighbors(v2)
                    except Exception as e:
                        self.__exception = e
                        return False

        return True

    def finished(self, result):
        if result:
            self.__valves_features.selectByIds(self.__list_valves)
            self.__pipelines_features.selectByIds(self.__list_visited_pipelines_ids)

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
        self.__idx_pipelines = QgsSpatialIndex(self.__pipelines_features.getFeatures(),
                                               flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        self.__idx_valves = QgsSpatialIndex(self.__valves_features.getFeatures(),
                                            flags=QgsSpatialIndex.FlagStoreFeatureGeometries)

    def __find_neighbors(self, point_vertex):

        reg_nearest = self.__idx_valves.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=1,
                                                        maxDistance=self.__user_distance)
        if len(reg_nearest) > 0:
            self.__list_valves.append(reg_nearest[0])
        else:
            pipelines_nearest = self.__idx_pipelines.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=3,
                                                                   maxDistance=self.__user_distance)
            # pipelines_nearest = idx_rede_agua.intersects(QgsRectangle(QgsPointXY(pointVertex), QgsPointXY(pointVertex)))
            if len(pipelines_nearest) > 0:
                for pipeline_id in pipelines_nearest:
                    pipeline_geometry = self.__idx_pipelines.geometry(pipeline_id)
                    if pipeline_id not in self.__list_visited_pipelines_ids:
                        self.__q_list_pipelines_ids.append(pipeline_id)
                        self.__q_list_pipelines.append(pipeline_geometry)

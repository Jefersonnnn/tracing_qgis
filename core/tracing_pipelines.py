from qgis._core import QgsVectorLayer
from qgis.core import (QgsTask,
                       QgsMessageLog,
                       Qgis,
                       QgsSpatialIndex,
                       QgsPointXY,
                       QgsProject, QgsApplication)

import global_vars


class TracingPipelines(QgsTask):

    def __init__(self, pipelines, valves, description='TracingCAJ', user_distance=0.001, onfinish=None, debug=False):
        super().__init__(description, QgsTask.CanCancel)

        self.onfinish = onfinish
        self.debug = debug
        self.__user_distance = user_distance
        self._pipelines_features = pipelines[0]
        self._valves_features = valves[0]
        self.__list_valves = []
        self.__list_valves_not_visibles = []
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

        self.iface = None
        if self.iface is None:
            self.iface = global_vars.iface

    def run(self):
        print('RUN TracingPipelines: ', self.description())
        QgsMessageLog.logMessage(f'Started task {self.description()}',
                                 'TracingCAJ', Qgis.Info)

        # Busca por redes selecionadas (necessário ser apenas uma)
        if self.debug:
            self._pipelines_features.selectByIds([13853])
            # self._pipelines_features.getFeatures(16)

        selected_pipeline = self._pipelines_features.selectedFeatures()

        if len(selected_pipeline) != 1:
            QgsMessageLog.logMessage('Selecione apenas UMA rede', 'TracingCAJ', Qgis.Info)
            return False
        else:

            self.__q_list_pipelines.append(selected_pipeline[0].geometry())
            self.__q_list_pipelines_ids.append(selected_pipeline[0].id())

            while len(self.__q_list_pipelines) > 0:
                self.__iterations += 1
                QgsMessageLog.logMessage(f'Iteration {self.__iterations}', 'TracingCAJ', Qgis.Info)

                # check isCanceled() to handle cancellation
                if self.isCanceled():
                    return False

                pipeline = self.__q_list_pipelines.pop(0)
                pipeline_id = self.__q_list_pipelines_ids.pop(0)

                if pipeline_id not in self.__list_visited_pipelines_ids:
                    self.__list_visited_pipelines.append(pipeline)
                    self.__list_visited_pipelines_ids.append(pipeline_id)

                    QgsMessageLog.logMessage(f'|-> Analisando Pipeline {pipeline_id}', 'TracingCAJ', Qgis.Info)

                    v1 = pipeline.vertexAt(0)
                    if self.debug:
                        v2 = pipeline.vertexAt(pipeline.get()[0].childCount() - 1)
                    else:
                        v2 = pipeline.vertexAt(len(pipeline.get()) - 1)

                    try:
                        QgsMessageLog.logMessage(f'|--> Analisando vertex {str(v1)}', 'TracingCAJ', Qgis.Info)
                        self.__find_neighbors(v1, pipeline_id)
                        QgsMessageLog.logMessage(f'|--> Analisando vertex {v2}', 'TracingCAJ', Qgis.Info)
                        self.__find_neighbors(v2, pipeline_id)
                    except Exception as e:
                        self.__exception = e
                        return False
        return True

    def finished(self, result):
        if result:
            # Seleciona os registro não visiveis
            print("Selecionando registro não visíveis")
            self._valves_features.selectByIds(self.__list_valves_not_visibles)
            names_valves_not_visibels = [feat['nome'] for feat in self._valves_features.selectedFeatures()]

            # Seleciona os registro visiveis
            print("Selecionando registro visíveis")
            self._valves_features.selectByIds(self.__list_valves)
            names_valves = [feat['nome'] for feat in self._valves_features.selectedFeatures()]

            self._pipelines_features.selectByIds(self.__list_visited_pipelines_ids)

            if self.onfinish:
                self.onfinish()

            QgsMessageLog.logMessage(f"Task {self.description()} has been executed correctly\n"
                                     f"Iterations: {self.__iterations}\n"
                                     f"Valves: {names_valves}\n"
                                     f"Valves not visibles: {names_valves_not_visibels}",
                                     level=Qgis.Success)
            # copy to clipboard
            self.iface.messageBar().pushMessage(
                'TracingCAJ',
                f"Task {self.description()} has been executed correctly\n"
                f"Copy to clipboard: {names_valves}",
                level=Qgis.Success,
                duration=10)
            QgsApplication.clipboard().setText(','.join(names_valves))
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
        self.__idx_pipelines = QgsSpatialIndex(self._pipelines_features.getFeatures(),
                                               flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        self.__idx_valves = QgsSpatialIndex(self._valves_features.getFeatures(),
                                            flags=QgsSpatialIndex.FlagStoreFeatureGeometries)

    def __find_neighbors(self, point_vertex, pipeline_origin_id=None):
        reg_isvisivel = None
        reg_status = None

        # Busca pelo registro mais próximo, dentro do raio maxDistance=user_distance
        reg_nearest = self.__idx_valves.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=1,
                                                        maxDistance=self.__user_distance)
        QgsMessageLog.logMessage(f'|---> Nearest: {reg_nearest}', 'TracingCAJ', Qgis.Info)
        if len(reg_nearest) > 0:
            QgsMessageLog.logMessage(f'|----> Vertex {point_vertex} is near valve {reg_nearest[0]}', 'TracingCAJ',
                                     Qgis.Info)
            # visivel = 'sim' = registro visível | visivel = 'não' = registro não visível
            reg_isvisivel = str(list(self._valves_features.getFeatures(reg_nearest))[0]['visivel'])
            # status = 0 = 'Aberto' | status = 1 = 'Fechado'
            reg_status = str(list(self._valves_features.getFeatures(reg_nearest))[0]['status'])

            QgsMessageLog.logMessage(
                f'|----> Valve {reg_nearest[0]} | visivel is {reg_isvisivel} and status is {reg_status}', 'TracingCAJ',
                Qgis.Info)

            if reg_isvisivel \
                    and reg_status \
                    and reg_isvisivel != 'NULL' \
                    and reg_isvisivel.upper() != 'NÃO' \
                    and reg_status == '0':
                self.__list_valves.append(reg_nearest[0])
            else:
                self.__list_valves_not_visibles.append(reg_nearest[0])  # Registro não visível ou NULL
                self.__find_pipelines_neighbors(point_vertex, pipeline_origin_id)
        else:
            self.__find_pipelines_neighbors(point_vertex, pipeline_origin_id)

    def __find_pipelines_neighbors(self, point_vertex, pipeline_origin_id):
        QgsMessageLog.logMessage(f'|----> Vertexis not near any valve', 'TracingCAJ', Qgis.Info)
        # Busca pelas 4 redes mais próximas no raio maxDistance=user_distance
        pipelines_nearest = self.__idx_pipelines.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=4,
                                                                 maxDistance=self.__user_distance)
        if len(pipelines_nearest) > 0:
            for pipeline_id in pipelines_nearest:
                if pipeline_origin_id:

                    origin_diameter = list(self._pipelines_features.getFeatures([pipeline_origin_id]))[0][
                        'diametro']
                    pipeline_diameter = list(self._pipelines_features.getFeatures([pipeline_id]))[0]['diametro']
                    if is_downstream(origin_diameter, pipeline_diameter):
                        continue
                        # self.__list_visited_pipelines.append(self.__idx_pipelines.geometry(pipeline_id))
                        # self.__list_visited_pipelines_ids.append(pipeline_id)

                pipeline_geometry = self.__idx_pipelines.geometry(pipeline_id)
                if pipeline_id not in self.__list_visited_pipelines_ids:
                    self.__q_list_pipelines_ids.append(pipeline_id)
                    self.__q_list_pipelines.append(pipeline_geometry)


def is_downstream(origin_diameter, destination_diameter):
    if origin_diameter > 100:
        if destination_diameter <= 75:
            return True
    return False


if __name__ == '__main__':
    path_to_pipeline_layer = "C:\\Users\\jeferson.machado\\Desktop\\QGIS\\shapes\\rede_agua_tracing.shp"
    path_to_valves_layer = "C:\\Users\\jeferson.machado\\Desktop\\QGIS\\shapes\\registro_manobra.shp"

    pipelines = QgsVectorLayer(path_to_pipeline_layer, "pipelines_tracing", "ogr")
    valves = QgsVectorLayer(path_to_valves_layer, "valves_tracing", "ogr")
    if not pipelines.isValid() or not valves.isValid():
        print("Layer failed to load!")
    else:
        QgsProject.instance().addMapLayer(pipelines)
        QgsProject.instance().addMapLayer(valves)

    pipe_features = QgsProject.instance().mapLayersByName('pipelines_tracing')
    valves_features = QgsProject.instance().mapLayersByName('valves_tracing')

    tracing = TracingPipelines(pipe_features, valves_features, debug=True)
    tracing.run()

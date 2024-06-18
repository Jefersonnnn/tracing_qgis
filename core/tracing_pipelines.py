from collections import deque

from qgis._core import QgsVectorLayer
from qgis.core import (QgsTask,
                              QgsMessageLog,
                              Qgis,
                              QgsSpatialIndex,
                              QgsPointXY,
                              QgsProject, QgsApplication)

import global_vars
import threading


class TracingPipelines(QgsTask):
    def __init__(self, pipelines, valves, description='TracingCAJ', user_distance=0.001, onfinish=None, debug=False,
                 parent=None):
        super().__init__(description, QgsTask.CanCancel)

        self.onfinish = onfinish
        self.debug = debug

        self._user_distance = user_distance
        self._pipelines_features = pipelines
        self._valves_features = valves

        self._first_pipeline_dn = None
        self._list_valves = set()
        self._list_valves_not_visible = set()
        self._list_valves_closed = set()
        self._list_visited_pipelines = set()
        self._list_visited_pipelines_ids = set()
        self._q_list_pipelines = deque()
        self._q_list_pipelines_ids = deque()

        self.__iterations = 0
        self.__exception = None

        # Callbackmsg
        self._parent = parent

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

            self._first_pipeline_dn = self._get_pipeline_dn(selected_pipeline[0].id())
            self._q_list_pipelines.append(selected_pipeline[0].geometry())
            self._q_list_pipelines_ids.append(selected_pipeline[0].id())

            while len(self._q_list_pipelines) > 0:
                self.__iterations += 1
                QgsMessageLog.logMessage(f'Iteration {self.__iterations}', 'TracingCAJ', Qgis.Info)

                # check isCanceled() to handle cancellation
                if self.isCanceled():
                    return False

                pipeline = self._q_list_pipelines.pop()
                pipeline_id = self._q_list_pipelines_ids.pop()

                if pipeline_id not in self._list_visited_pipelines_ids:
                    self._list_visited_pipelines.add(pipeline)
                    self._list_visited_pipelines_ids.add(pipeline_id)

                    QgsMessageLog.logMessage(f'|-> Analisando Pipeline {pipeline_id}', 'TracingCAJ', Qgis.Info)

                    v1 = pipeline.vertexAt(0)
                    if self.debug:
                        v2 = pipeline.vertexAt(pipeline.get()[0].childCount() - 1)
                    else:
                        v2 = pipeline.vertexAt(len(pipeline.get()) - 1)

                    try:
                        # Cria uma nova thread para cada pipeline

                        thread1 = threading.Thread(target=self.__find_neighbors, args=(v1, pipeline_id))
                        thread2 = threading.Thread(target=self.__find_neighbors, args=(v2, pipeline_id))

                        # Inicia as threads
                        thread1.start()
                        thread2.start()

                        # Aguarda as threads concluírem
                        thread1.join()
                        thread2.join()
                    except Exception as e:
                        print(e)
                        self.__exception = e
                        return False
        return True

    def finished(self, result):
        # Ativa novamente o botão

        if not self.debug:
            self._parent.set_enable_button_iniciar()

        if result:
            # Seleciona os registros não visiveis
            self._valves_features.selectByIds(list(self._list_valves_not_visible))
            names_valves_not_visible = [feat['codigo'] for feat in self._valves_features.selectedFeatures()]

            # Seleciona os registros não visiveis
            self._valves_features.selectByIds(list(self._list_valves_closed))
            names_valves_closed = [feat['codigo'] for feat in self._valves_features.selectedFeatures()]

            # Seleciona os registros visiveis
            self._valves_features.selectByIds(list(self._list_valves))
            names_valves = [feat['codigo'] for feat in self._valves_features.selectedFeatures()]

            self._pipelines_features.selectByIds(list(self._list_visited_pipelines_ids))

            if self.onfinish:
                self.onfinish()

            QgsMessageLog.logMessage(f"Task {self.description()} has been executed correctly\n"
                                     f"Iterações: {self.__iterations}\n"
                                     f"Registros: {names_valves}\n"
                                     f"Registros fechados: {names_valves_closed}\n"
                                     f"Registro não visíveis: {names_valves_not_visible}",
                                     level=Qgis.Success)
            # copy to clipboard
            self.iface.messageBar().pushMessage(
                'TracingCAJ',
                f"Task {self.description()} has been executed correctly\n"
                f"Copy to clipboard: {names_valves}",
                level=Qgis.Success,
                duration=10)

            if self._parent:
                self._parent.set_status_msg('Finalizado! registros no CTRL+V')

            if self._parent:
                self._parent.set_final_msg(f"Registros: {','.join(names_valves)}\n"
                                           f"Registro fechados: {','.join(names_valves_closed)}\n"
                                           f"Registro não visíveis: {','.join(names_valves_not_visible)}"
                                           )

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
        print(f'TracingTrask {self.description()} was canceled')
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
                                                        maxDistance=self._user_distance)
        QgsMessageLog.logMessage(f'|---> Valve Nearest: {reg_nearest}', 'TracingCAJ', Qgis.Info)
        if len(reg_nearest) > 0:
            _feature = list(self._valves_features.getFeatures(reg_nearest))[0]

            QgsMessageLog.logMessage(f'|----> Vertex {point_vertex} is near valve {reg_nearest[0]}', 'TracingCAJ',
                                     Qgis.Info)
            # visivel = 'sim' = registro visível | visivel = 'não' = registro não visível
            reg_isvisivel = str(_feature['visivel'])
            # status_operacao = 0 = 'Aberto' | status = 1 = 'Fechado'
            reg_status = str(_feature['status_operacao'])

            QgsMessageLog.logMessage(
                f'|----> Valve {reg_nearest[0]} | visivel is {reg_isvisivel} and status is {reg_status}', 'TracingCAJ',
                Qgis.Info)

            if reg_isvisivel.upper() != 'NÃO' and reg_status == '0':
                self._list_valves.add(reg_nearest[0])
            elif reg_status == '1':
                self._list_valves_closed.add(reg_nearest[0])  # Registros já fechados
            else:
                self._list_valves_not_visible.add(reg_nearest[0])  # Registro não visível ou NULL
                self.__find_pipelines_neighbors(point_vertex, pipeline_origin_id)
        else:
            self.__find_pipelines_neighbors(point_vertex, pipeline_origin_id)

    def __find_pipelines_neighbors(self, point_vertex, pipeline_origin_id):
        QgsMessageLog.logMessage(f'|----> Vertexis not near any valve', 'TracingCAJ', Qgis.Info)
        # Busca pelas 4 redes mais próximas no raio maxDistance=user_distance
        pipelines_nearest = self.__idx_pipelines.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=4,
                                                                 maxDistance=self._user_distance)
        if len(pipelines_nearest) > 0:
            for pipeline_id in pipelines_nearest:
                if pipeline_origin_id:

                    origin_diameter = self._get_pipeline_dn(pipeline_origin_id)
                    pipeline_diameter = self._get_pipeline_dn(pipeline_id)

                    if self.is_downstream(origin_diameter, pipeline_diameter):
                        continue
                        # self._list_visited_pipelines.append(self.__idx_pipelines.geometry(pipeline_id))
                        # self._list_visited_pipelines_ids.append(pipeline_id)

                pipeline_geometry = self.__idx_pipelines.geometry(pipeline_id)
                if pipeline_id not in self._list_visited_pipelines_ids:
                    self._q_list_pipelines_ids.append(pipeline_id)
                    self._q_list_pipelines.append(pipeline_geometry)

    def _get_pipeline_dn(self, pipeline_id):
        return list(self._pipelines_features.getFeatures([pipeline_id]))[0]['diametro_nominal']

    def is_downstream(self, origin_diameter, destination_diameter):
        if origin_diameter >= 100:
            if destination_diameter <= 75:
                return True
            elif origin_diameter >= destination_diameter:
                return False
        elif origin_diameter == self._first_pipeline_dn and destination_diameter <= 100:
                return False
        if origin_diameter > destination_diameter:
            return True
        return False


if __name__ == '__main__':
    path_to_pipeline_layer = "C:\\Users\\jeferson.machado\\OneDrive - CAJ\\Área de Trabalho\\QGIS\\shapes\\rede_agua_tracing.shp"
    path_to_valves_layer   = "C:\\Users\\jeferson.machado\\OneDrive - CAJ\\Área de Trabalho\\QGIS\\shapes\\registro_manobra.shp"

    pipelines = QgsVectorLayer(path_to_pipeline_layer, "pipelines_tracing", "ogr")
    valves = QgsVectorLayer(path_to_valves_layer, "valves_tracing", "ogr")
    if not pipelines.isValid() or not valves.isValid():
        print("Layer failed to load!")
    else:
        QgsProject.instance().addMapLayer(pipelines)
        QgsProject.instance().addMapLayer(valves)

    pipe_features = QgsProject.instance().mapLayersByName('pipelines_tracing')[0]
    valves_features = QgsProject.instance().mapLayersByName('valves_tracing')[0]

    tracing = TracingPipelines(pipe_features, valves_features, debug=True)
    result_finish = tracing.run()
    tracing.finished(result_finish)

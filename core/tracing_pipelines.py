from collections import deque

from qgis._core import QgsVectorLayer
from qgis.core import (QgsTask,
                              QgsMessageLog,
                              Qgis,
                              QgsFeatureRequest,
                              QgsSpatialIndex,
                              QgsPointXY,
                              QgsProject, QgsApplication)

import global_vars


class TracingPipelines(QgsTask):
    def __init__(self, pipelines, valves, description='TracingCAJ', user_distance=0.001, onfinish=None, debug=False,
                 parent=None):
        super().__init__(description, QgsTask.CanCancel)

        self.onfinish = onfinish
        self.debug = debug
        # Loga o caminho do tracing sem os efeitos do modo debug (rede fixa, etc.).
        # Ligue com `tracing_task.verbose = True` para diagnosticar um traçado.
        self.verbose = debug

        self._user_distance = user_distance
        self._pipelines_features = pipelines
        self._valves_features = valves

        self._first_pipeline_dn = None
        self._list_valves = set()
        self._list_valves_not_visible = set()
        self._list_valves_closed = set()
        self._list_visited_pipelines_ids = set()
        self._q_list_pipelines_ids = deque()
        self._queued_ids = set()

        self.__iterations = 0
        self.__exception = None

        # Callbackmsg
        self._parent = parent

        # Os índices espaciais e os caches de atributos são construídos em run(),
        # que roda na thread de background do QgsTaskManager (ver __create_spatial_index).
        self.__idx_pipelines = None
        self.__idx_valves = None
        self._dn_by_id = {}
        self._status_by_id = {}

        self.iface = global_vars.iface

    def _log(self, message, level=Qgis.Info):
        """Log condicionado (debug/verbose) para não onerar os loops quentes."""
        if self.debug or self.verbose:
            QgsMessageLog.logMessage(message, 'TracingCAJ', level)

    def run(self):
        try:
            self._log(f'Started task {self.description()}')

            self.__create_spatial_index()
            self.__build_pipeline_cache()

            # Busca por redes selecionadas (necessário ser apenas uma)
            if self.debug:
                self._pipelines_features.selectByIds([13853])

            selected_pipeline = self._pipelines_features.selectedFeatures()

            if len(selected_pipeline) != 1:
                QgsMessageLog.logMessage('Selecione apenas UMA rede', 'TracingCAJ', Qgis.Info)
                return False

            first_pipeline = selected_pipeline[0]
            self._first_pipeline_dn = self._get_pipeline_dn(first_pipeline.id())
            self._q_list_pipelines_ids.append(first_pipeline.id())
            self._queued_ids.add(first_pipeline.id())

            while len(self._q_list_pipelines_ids) > 0:
                self.__iterations += 1

                # check isCanceled() to handle cancellation
                if self.isCanceled():
                    return False

                pipeline_id = self._q_list_pipelines_ids.pop()

                if pipeline_id in self._list_visited_pipelines_ids:
                    continue
                self._list_visited_pipelines_ids.add(pipeline_id)

                self._log(f'|-> Analisando Pipeline {pipeline_id}')

                pipeline = self.__idx_pipelines.geometry(pipeline_id)

                v1 = pipeline.vertexAt(0)
                if self.debug:
                    v2 = pipeline.vertexAt(pipeline.get()[0].childCount() - 1)
                else:
                    v2 = pipeline.vertexAt(len(pipeline.get()) - 1)

                self.__find_neighbors(v1, pipeline_id)
                self.__find_neighbors(v2, pipeline_id)

            return True
        except Exception as e:
            self.__exception = e
            QgsMessageLog.logMessage(f'Exception in run(): {e}', 'TracingCAJ', Qgis.Critical)
            return False

    def finished(self, result):
        # Ativa novamente o botão
        if not self.debug and self._parent:
            self._parent.set_enable_button_iniciar()

        if result:
            all_ids = (self._list_valves
                       | self._list_valves_closed
                       | self._list_valves_not_visible)

            request = (QgsFeatureRequest()
                       .setFilterFids(list(all_ids))
                       .setSubsetOfAttributes(['codigo'], self._valves_features.fields()))
            codigo_by_id = {feat.id(): feat['codigo']
                            for feat in self._valves_features.getFeatures(request)}

            def codes(ids):
                return [str(codigo_by_id[i]) for i in ids if i in codigo_by_id]

            names_valves = codes(self._list_valves)
            names_valves_closed = codes(self._list_valves_closed)
            names_valves_not_visible = codes(self._list_valves_not_visible)

            # Realça no mapa as redes percorridas e os registros visíveis a fechar
            self._pipelines_features.selectByIds(list(self._list_visited_pipelines_ids))
            self._valves_features.selectByIds(list(self._list_valves))

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
        QgsMessageLog.logMessage(
            f'TracingTrask {self.description()} was canceled', level=Qgis.Info)
        super().cancel()

    def __create_spatial_index(self):
        self.__idx_pipelines = QgsSpatialIndex(self._pipelines_features.getFeatures(),
                                               flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
        self.__idx_valves = QgsSpatialIndex(self._valves_features.getFeatures(),
                                            flags=QgsSpatialIndex.FlagStoreFeatureGeometries)

    def __build_pipeline_cache(self):
        """Carrega diâmetro nominal e status de utilização numa única requisição (evita I/O por nó)."""
        request = QgsFeatureRequest().setSubsetOfAttributes(
            ['diametro_nominal', 'status_utilizacao'], self._pipelines_features.fields())
        for feat in self._pipelines_features.getFeatures(request):
            self._dn_by_id[feat.id()] = feat['diametro_nominal']
            self._status_by_id[feat.id()] = feat['status_utilizacao']

    def __find_neighbors(self, point_vertex, pipeline_origin_id=None):
        # Busca pelo registro mais próximo, dentro do raio maxDistance=user_distance
        reg_nearest = self.__idx_valves.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=1,
                                                        maxDistance=self._user_distance)
        self._log(f'|---> Valve Nearest: {reg_nearest}')

        if len(reg_nearest) == 0:
            self.__find_pipelines_neighbors(point_vertex, pipeline_origin_id)
            return

        valve_id = reg_nearest[0]
        _feature = self._valves_features.getFeature(valve_id)

        # visivel = 'sim' = registro visível | visivel = 'não' = registro não visível
        reg_isvisivel = str(_feature['visivel'])
        # status_operacao = 0 = 'Aberto' | status = 1 = 'Fechado'
        reg_status = str(_feature['status_operacao'])
        # status_utilizacao = 'Desativado' = registro fora de uso, não serve para manobra
        reg_utilizacao = str(_feature['status_utilizacao']).strip()

        self._log(f'|----> Valve {valve_id} | visivel={reg_isvisivel} '
                  f'status_operacao={reg_status} status_utilizacao={reg_utilizacao!r}')

        # Registro desativado não isola nada (mesmo com status_operacao=1): ignora e
        # segue o tracing pelas redes atrás de outro registro
        if reg_utilizacao.casefold() == 'desativado':
            QgsMessageLog.logMessage(
                f'Valve {valve_id} está Desativado (status_operacao={reg_status}) — '
                f'ignorada, seguindo o tracing', 'TracingCAJ', Qgis.Info)
            self.__find_pipelines_neighbors(point_vertex, pipeline_origin_id)
            return

        if reg_isvisivel.upper() != 'NÃO' and reg_status == '0':
            self._list_valves.add(valve_id)
        elif reg_status == '1':
            self._list_valves_closed.add(valve_id)  # Registros já fechados
        else:
            self._list_valves_not_visible.add(valve_id)  # Registro não visível ou NULL
            self.__find_pipelines_neighbors(point_vertex, pipeline_origin_id)

    def __find_pipelines_neighbors(self, point_vertex, pipeline_origin_id):
        self._log('|----> Vertex is not near any valve')
        # Busca pelas 4 redes mais próximas no raio maxDistance=user_distance
        pipelines_nearest = self.__idx_pipelines.nearestNeighbor(point=QgsPointXY(point_vertex), neighbors=4,
                                                                 maxDistance=self._user_distance)
        if len(pipelines_nearest) == 0:
            return

        origin_diameter = self._get_pipeline_dn(pipeline_origin_id) if pipeline_origin_id else None

        for pipeline_id in pipelines_nearest:
            if str(self._get_pipeline_status(pipeline_id)).strip().casefold() == 'desativado':
                self._log(f'|-----> Rede {pipeline_id} ignorada: Desativado')
                continue

            if origin_diameter is not None:
                pipeline_diameter = self._get_pipeline_dn(pipeline_id)
                if self.is_downstream(origin_diameter, pipeline_diameter):
                    self._log(f'|-----> Rede {pipeline_id} ignorada: is_downstream '
                              f'(origem {origin_diameter} -> destino {pipeline_diameter})')
                    continue

            if (pipeline_id not in self._list_visited_pipelines_ids
                    and pipeline_id not in self._queued_ids):
                self._log(f'|-----> Rede {pipeline_id} enfileirada')
                self._q_list_pipelines_ids.append(pipeline_id)
                self._queued_ids.add(pipeline_id)

    def _get_pipeline_dn(self, pipeline_id):
        if pipeline_id not in self._dn_by_id:
            self._dn_by_id[pipeline_id] = self._pipelines_features.getFeature(pipeline_id)['diametro_nominal']
        return self._dn_by_id[pipeline_id]

    def _get_pipeline_status(self, pipeline_id):
        if pipeline_id not in self._status_by_id:
            self._status_by_id[pipeline_id] = self._pipelines_features.getFeature(pipeline_id)['status_utilizacao']
        return self._status_by_id[pipeline_id]

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

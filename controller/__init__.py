from qgis.PyQt.QtCore import QSettings, QTimer

from qgis.core import (
    Qgis,
    QgsProject,
    QgsApplication,
    QgsMessageLog
)
from qgis.gui import QgsMapToolIdentifyFeature

from view import ConfigDialog
from core.task_manager import TracingCAJ

import global_vars


class ConfigController:

    def __init__(self):
        self._ui = ConfigDialog(controller=self)

        self._ui.layer_pipelines.currentIndexChanged.connect(self.layerSelectionPipeline)
        self._ui.layer_valves.currentIndexChanged.connect(self.layerSelectionValves)

        self._ui.btn_iniciar_tracing.clicked.connect(self.start_tracing)
        self._ui.btn_salvar_configs.clicked.connect(self.save_configs)
        self._ui.btn_selecionar_clique.toggled.connect(self.toggle_select_by_click)

        # Task Manager
        self.__tm = QgsApplication.taskManager()

        self._pipelines = None
        self._valves = None

        # Ferramenta de seleção de rede por clique no mapa (ver toggle_select_by_click)
        self._select_tool = None
        self._previous_map_tool = None

        self.iface = None
        if self.iface is None:
            self.iface = global_vars.iface

    def set_enable_button_iniciar(self):
        self._ui.btn_iniciar_tracing.setEnabled(True)

    def set_disable_button_inicial(self):
        self._ui.btn_iniciar_tracing.setEnabled(False)

    def save_configs(self):
        index_pipelines = self._ui.layer_pipelines.currentIndex()
        index_valves = self._ui.layer_valves.currentIndex()

        layerIdPipelines = None
        layerIdValves = None

        if index_pipelines != -1:
            layerIdPipelines = self._ui.layer_pipelines.itemData(index_pipelines)

        if index_valves != -1:
            layerIdValves = self._ui.layer_valves.itemData(index_valves)

        if layerIdPipelines and layerIdValves:
            Settings().save_params(layerIdPipelines, layerIdValves)
            self.set_status_msg('Configurações salvas')
            return

        self.set_status_msg('Não foi possível salvar as configurações')

    def show(self):
        # Exibe a tela de configurações
        # self._ui.exec_()
        self._ui.show()

    def start_tracing(self):
        self.set_status_msg("Iniciando...")
        try:
            if self._pipelines is not None and self._valves is not None:
                pipeline_select = self._pipelines.selectedFeatures()
                if pipeline_select:
                    if len(pipeline_select) == 1:
                        self.set_disable_button_inicial()
                        tracing_caj = TracingCAJ(
                            task_manager=self.__tm,
                            pipelines=self._pipelines,
                            valves=self._valves,
                            parent=self)
                        self.set_status_msg("Aguarde finalizar...")
                        tracing_caj.start()
                    else:
                        self.set_status_msg("Selecione apenas uma rede para iniciar...")
                        self.iface.messageBar().pushMessage("Info",
                                                            "Select only ONE network to start", level=Qgis.Info)
                else:
                    self.set_status_msg("Selecione uma rede no mapa para iniciar!")
                    self.iface.messageBar().pushMessage("Info", 'Nenhuma rede selecionada!" '
                                                        , level=Qgis.Info)
            else:
                self.set_status_msg("Referencia para as redes e registros não encontrada!")
                self.iface.messageBar().pushMessage("Info", 'Referencia para as redes e registros não encontrada!" '
                                                    , level=Qgis.Info)
        except Exception as e:
            print(e)
            self.set_enable_button_iniciar()

    def toggle_select_by_click(self, checked):
        """Ativa/desativa a ferramenta que permite selecionar a rede clicando no mapa,
        como alternativa às ferramentas de seleção nativas do QGIS."""
        canvas = self.iface.mapCanvas()

        if not checked:
            # Clique manual no botão: não estamos dentro do canvasReleaseEvent da
            # ferramenta, então é seguro trocar de ferramenta na hora.
            self._restore_previous_tool()
            return

        if self._pipelines is None:
            self._set_select_button_checked(False)
            self.set_status_msg("Selecione a camada de redes antes de usar o clique no mapa")
            return

        self._previous_map_tool = canvas.mapTool()
        self._select_tool = QgsMapToolIdentifyFeature(canvas, self._pipelines)
        self._select_tool.featureIdentified.connect(self._on_pipeline_clicked)
        self._select_tool.deactivated.connect(self._on_select_tool_deactivated)
        canvas.setMapTool(self._select_tool)
        self.set_status_msg("Clique sobre uma rede no mapa para selecioná-la...")

    def _on_pipeline_clicked(self, feature):
        self._pipelines.removeSelection()
        self._pipelines.select(feature.id())
        self.set_status_msg("Rede selecionada no mapa. Clique em Iniciar para rastrear.")
        # Este slot roda a partir de dentro do canvasReleaseEvent do próprio
        # QgsMapToolIdentifyFeature (que emite featureIdentified em plena execução do
        # evento de clique). Trocar a ferramenta do mapa agora, de forma síncrona,
        # derruba o QGIS (access violation). Adiamos para o próximo ciclo do loop de
        # eventos do Qt, quando o canvasReleaseEvent já tiver retornado.
        QTimer.singleShot(0, self._restore_previous_tool)

    def _on_select_tool_deactivated(self):
        # Também é chamado se o usuário trocar de ferramenta manualmente na barra do QGIS
        self._set_select_button_checked(False)
        self._select_tool = None
        self._previous_map_tool = None

    def _restore_previous_tool(self):
        tool = self._select_tool
        if tool is None:
            return
        canvas = self.iface.mapCanvas()
        if self._previous_map_tool is not None:
            canvas.setMapTool(self._previous_map_tool)
        else:
            canvas.unsetMapTool(tool)

    def _set_select_button_checked(self, checked):
        self._ui.btn_selecionar_clique.blockSignals(True)
        self._ui.btn_selecionar_clique.setChecked(checked)
        self._ui.btn_selecionar_clique.blockSignals(False)

    def set_layers(self, layer):
        """
            adds available layers to the selection list in the window
        :param layer:
        :return:
        """

        index_pipelines = self._ui.layer_pipelines.currentIndex()
        index_valves = self._ui.layer_valves.currentIndex()

        if index_pipelines != -1:
            layerIdPipelines = self._ui.layer_pipelines.itemData(index_pipelines)  # id of the previously selected layer

        if index_valves != -1:
            layerIdValves = self._ui.layer_valves.itemData(index_valves)

        self._ui.layer_pipelines.blockSignals(True)
        self._ui.layer_valves.blockSignals(True)

        self._ui.layer_pipelines.clear()  # fill the comboBox with a new list of layers
        self._ui.layer_valves.clear()  # fill the comboBox with a new list of layers

        layer.sort(key=lambda x: x[0].lower())
        for i in layer:
            self._ui.layer_pipelines.addItem(i[0], i[1])
            self._ui.layer_valves.addItem(i[0], i[1])

        if index_pipelines != -1:
            index2 = self._ui.layer_pipelines.findData(layerIdPipelines)  # if the previously selected layer is a list then select it
            if index2 != -1:
                self._ui.layer_pipelines.setCurrentIndex(index2)
            else:
                self.layerSelectionPipeline(0)  # if it doesn't have the first one
        else:
            self.layerSelectionPipeline(0)

        if index_valves != -1:
            index2 = self._ui.layer_valves.findData(
                layerIdValves)  # if the previously selected layer is a list then select it
            if index2 != -1:
                self._ui.layer_valves.setCurrentIndex(index2)
            else:
                self.layerSelectionValves(0)  # if it doesn't have the first one
        else:
            self.layerSelectionValves(0)

        id_pipelines, id_valves = Settings().get_params()

        if id_pipelines and id_valves:

            index_valves = self._ui.layer_valves.findData(id_valves)
            index_pipelines = self._ui.layer_pipelines.findData(id_pipelines)

            if index_valves != -1 and index_pipelines != -1:
                self._ui.layer_valves.setCurrentIndex(index_valves)
                self.layerSelectionPipeline(index_pipelines)
                self._ui.layer_pipelines.setCurrentIndex(index_pipelines)
                self.layerSelectionValves(index_valves)
                print("Configurações Carregadas!")

        self._ui.layer_pipelines.blockSignals(False)
        self._ui.layer_valves.blockSignals(False)

    def layerSelectionPipeline(self, index):  # finished
        """Runs after selecting layer from the list. Sets a new list of fields to choose from and deletes windows with already selected fields"""

        idPipelines = self._ui.layer_pipelines.itemData(index)  # Get the ID of the selected layer
        _layer_pipelines_selected = QgsProject.instance().mapLayer(idPipelines)  # .toString())

        self._pipelines = _layer_pipelines_selected

    def layerSelectionValves(self, index):  # finished
        """Runs after selecting layer from the list. Sets a new list of fields to choose from and deletes windows with already selected fields"""

        idValves = self._ui.layer_valves.itemData(index)  # Get the ID of the selected layer
        _layer_valves_selected = QgsProject.instance().mapLayer(idValves)  # .toString())

        self._valves = _layer_valves_selected

    def set_status_msg(self, msg):
        self._ui.lbl_status.setText(msg)

    def set_final_msg(self, msg):
        self._ui.txt_list_valves.clear()
        self._ui.txt_list_valves.setText(msg)


class Settings:
    """Gerenciar configurações da aplicação utilizando o QSettings"""

    sections = 'TRACING'

    def __init__(self):
        # Cria o arquivo de configurações
        self._settings = QSettings('ANALISE_EXTRAVASAMENTO', 'ANALISE_EXTRAVASAMENTO')

    def save_params(self, id_pipelines, id_valves):
        # Salvar os ids das camadas de rede e registros
        self._settings.setValue(self.sections + '/id_pipeline', id_pipelines)
        self._settings.setValue(self.sections + '/id_valves', id_valves)

    def get_params(self):
        # Retorna os ids das camadas de rede e registros
        id_pipelines = self._settings.value(self.sections + '/id_pipeline')
        id_valves = self._settings.value(self.sections + '/id_valves')

        return id_pipelines, id_valves
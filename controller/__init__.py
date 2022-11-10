import base64

from PyQt5.QtCore import QSettings, QObject

from qgis.core import (
    Qgis,
    QgsProject,
    QgsApplication
)

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

        # Flag para controle do status do botão
        self._status_button_iniciar = True

        # Task Manager
        self.__tm = QgsApplication.taskManager()

        self._pipelines = None
        self._valves = None

        self.iface = None
        if self.iface is None:
            self.iface = global_vars.iface

    def toggle_button_iniciar(self):
        if self._status_button_iniciar:
            self._ui.btn_iniciar_tracing.setEnabled(False)
            self._status_button_iniciar = False
        else:
            self._ui.btn_iniciar_tracing.setEnabled(True)
            self._status_button_iniciar = True

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

        self.set_status_msg('Não foi possível salvar as configurações')

    def show(self):
        # Exibe a tela de configurações
        # self._ui.exec_()
        self._ui.show()

    def start_tracing(self):
        self.set_status_msg("Iniciando...")
        if len(self._pipelines) > 0 and len(self._valves) > 0:
            pipeline_select = self.iface.activeLayer().selectedFeatures()
            if pipeline_select:
                if len(pipeline_select) == 1:
                    self.toggle_button_iniciar()
                    tracing_caj = TracingCAJ(self.__tm, self._pipelines, self._valves, parent=self)
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
            index2 = self._ui.layer_pipelines.findData(
                layerIdPipelines)  # if the previously selected layer is a list then select it
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
            index_valves = self._ui.layer_pipelines.findData(layerIdPipelines)
            index_pipelines = self._ui.layer_valves.findData(id_valves)

            if index_valves != -1:
                self._ui.layer_valves.setCurrentIndex(index_valves)

            if index_pipelines != -1:
                self._ui.layer_pipelines.setCurrentIndex(index_pipelines)

        self._ui.layer_pipelines.blockSignals(False)
        self._ui.layer_valves.blockSignals(False)

    def layerSelectionPipeline(self, index):  # finished
        "Runs after selecting layer from the list. Sets a new list of fields to choose from and deletes windows with already selected fields"

        idPipelines = self._ui.layer_pipelines.itemData(index)  # Get the ID of the selected layer
        _layer_pipelines_selected = QgsProject.instance().mapLayer(idPipelines)  # .toString())

        self._pipelines = _layer_pipelines_selected
        self._valves = QgsProject.instance().mapLayersByName('valves_tracing')

    def layerSelectionValves(self, index):  # finished
        "Runs after selecting layer from the list. Sets a new list of fields to choose from and deletes windows with already selected fields"

        idValves = self._ui.layer_pipelines.itemData(index)  # Get the ID of the selected layer
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

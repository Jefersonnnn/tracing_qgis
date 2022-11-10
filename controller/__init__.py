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

        # Task Manager
        self.__tm = QgsApplication.taskManager()

        self._pipelines = None
        self._valves = None

        self.iface = None
        if self.iface is None:
            self.iface = global_vars.iface

    def show(self):
        # Exibe a tela de configurações
        self._ui.exec_()

    def start_tracing(self):
        self.set_status_msg("Iniciando...")
        if len(self._pipelines) > 0 and len(self._valves) > 0:
            pipeline_select = self.iface.activeLayer().selectedFeatures()
            if pipeline_select:
                if len(pipeline_select) == 1:
                    tracing_caj = TracingCAJ(self.__tm, self._pipelines, self._valves, callback_msg=self.set_status_msg)
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


class Settings:
    """Gerenciar configurações da aplicação utilizando o QSettings"""

    sections_sansys = 'BD_SANSYS'
    sections_sde = 'BD_SDE'
    section_ftp = 'FTP'

    def __init__(self):
        # Cria o arquivo de configurações
        self._settings = QSettings('ANALISE_EXTRAVASAMENTO', 'ANALISE_EXTRAVASAMENTO')

    def save_params_db(self, driver, host, db, user, password, trust_connection=False):
        # todo: verificar se o settings são salvos para todos os usuários ou apenas para o usuário logado
        # Salva os parâmetros de conexão com o banco de dados
        self._settings.setValue(self.sections_sansys + '/driver', driver)
        self._settings.setValue(self.sections_sansys + '/host', host)
        self._settings.setValue(self.sections_sansys + '/db', db)
        self._settings.setValue(self.sections_sansys + '/user', user)
        self._settings.setValue(self.sections_sansys + '/password',
                                base64.b64encode(password.encode('utf-8')) if password else None)
        self._settings.setValue(self.sections_sansys + '/trust_connection', 'yes' if trust_connection else 'no')

    def save_params_db_sde(self, host, port, db, user, password):
        # Salva os parâmetros de conexão com o banco de dados
        self._settings.setValue(self.sections_sde + '/host_sde', host)
        self._settings.setValue(self.sections_sde + '/port_sde', port)
        self._settings.setValue(self.sections_sde + '/db_sde', db)
        self._settings.setValue(self.sections_sde + '/user_sde', user)
        self._settings.setValue(self.sections_sde + '/password_sde',
                                base64.b64encode(password.encode('utf-8')) if password else None)

    def save_params_ftp(self, host, port, user, password, root_path_ftp):
        # Salva os parâmetros de conexão com o banco de dados
        self._settings.setValue(self.section_ftp + '/host_ftp', host)
        self._settings.setValue(self.section_ftp + '/port_ftp', port)
        self._settings.setValue(self.section_ftp + '/user_ftp', user)
        self._settings.setValue(self.section_ftp + '/password_ftp',
                                base64.b64encode(password.encode('utf-8')) if password else None)
        self._settings.setValue(self.section_ftp + '/root_path_ftp', root_path_ftp)

    def get_params_ftp(self) -> (str, str, str, str, str):
        """Retorna os parâmetros de conexão com o FTP
        :return: host, port, user, password, root_path_ftp
        """
        # Retorna os parâmetros de conexão com o FTP
        host = self._settings.value(self.section_ftp + '/host_ftp', 'ftpinterno')
        port = self._settings.value(self.section_ftp + '/port_ftp', '21')
        user = self._settings.value(self.section_ftp + '/user_ftp', 'ftp.qfield')
        root_path = self._settings.value(self.section_ftp + '/root_path_ftp',
                                         'Usuários/francisco.hoffmann/Extravasamentos/')
        password = self._settings.value(self.section_ftp + '/password_ftp', '')
        password = base64.b64decode(password).decode('utf-8') if password else None
        return host, port, user, password, root_path

    def get_params_db_sde(self):
        # Retorna os parâmetros de conexão com o banco de dados
        host = self._settings.value(self.sections_sde + '/host_sde', '10.45.0.24')
        port = self._settings.value(self.sections_sde + '/port_sde', '5432')
        db = self._settings.value(self.sections_sde + '/db_sde', 'simgeo')
        user = self._settings.value(self.sections_sde + '/user_sde')
        password = self._settings.value(self.sections_sde + '/password_sde')
        password = base64.b64decode(password).decode('utf-8') if password else None
        return host, port, db, user, password

    def get_params_db(self):
        # Retorna os parâmetros de conexão com o banco de dados
        driver = self._settings.value(self.sections_sansys + '/driver')
        host = self._settings.value(self.sections_sansys + '/host', 'poseidon')
        db = self._settings.value(self.sections_sansys + '/db', 'sansys_readonly')
        user = self._settings.value(self.sections_sansys + '/user')
        password = self._settings.value(self.sections_sansys + '/password')
        password = base64.b64decode(password).decode('utf-8') if password else None
        trust_connection = 'yes' if self._settings.value(
            self.sections_sansys + '/trust_connection') == 1 or self._settings.value(
            self.sections_sansys + '/trust_connection') == 'yes' else 'no'
        return driver, host, db, user, password, trust_connection

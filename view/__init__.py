# -*- coding: utf-8 -*-
"""
/***************************************************************************
                             -------------------
        begin                : 2021-09-13
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Jeferson Machado/CAJ
        email                : jeferson.machado@aguasdejoinville.com.br
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

try:
    from qgis.PyQt import uic
    from qgis.PyQt import QtWidgets
except:
    from PyQt5 import uic, QtWidgets

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), r'ui\config_dialog.ui'))


class ConfigDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, controller, parent=None):
        """Constructor."""
        super(ConfigDialog, self).__init__(parent)

        self.setupUi(self)

        self.setWindowTitle(f"Configurações - {self.windowTitle()}")

        self.controller = controller

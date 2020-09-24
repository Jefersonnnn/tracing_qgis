import os
import sys
plugin_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.append(plugin_path)


def classFactory(iface):
    """ Load Giswater class from file giswater.
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .tracing import Tracing
    return Tracing(iface)

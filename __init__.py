# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Python tools
 A QGIS plugin which improves the embedded python editor

                              -------------------
        begin                : 2020-06-15
        git sha              : $Format:%H$
        copyright            : (C) 2020 Yoann Quenach de Quivillic
        email                : yoann.quenach@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load LayerTreeIcons class from file layertreeicons.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .pythontools import PythonTools

    return PythonTools(iface)

# -*- coding: utf-8 -*-

##########################################################################
#                                                                        #
#  Eddy: a graphical editor for the construction of Graphol ontologies.  #
#  Copyright (C) 2015 Daniele Pantaleone <danielepantaleone@me.com>      #
#                                                                        #
#  This program is free software: you can redistribute it and/or modify  #
#  it under the terms of the GNU General Public License as published by  #
#  the Free Software Foundation, either version 3 of the License, or     #
#  (at your option) any later version.                                   #
#                                                                        #
#  This program is distributed in the hope that it will be useful,       #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of        #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the          #
#  GNU General Public License for more details.                          #
#                                                                        #
#  You should have received a copy of the GNU General Public License     #
#  along with this program. If not, see <http://www.gnu.org/licenses/>.  #
#                                                                        #
#  #####################                          #####################  #
#                                                                        #
#  Graphol is developed by members of the DASI-lab group of the          #
#  Dipartimento di Ingegneria Informatica, Automatica e Gestionale       #
#  A.Ruberti at Sapienza University of Rome: http://www.dis.uniroma1.it/ #
#                                                                        #
#     - Domenico Lembo <lembo@dis.uniroma1.it>                           #
#     - Valerio Santarelli <santarelli@dis.uniroma1.it>                  #
#     - Domenico Fabio Savo <savo@dis.uniroma1.it>                       #
#     - Marco Console <console@dis.uniroma1.it>                          #
#                                                                        #
##########################################################################


from abc import ABCMeta

from PyQt5.QtCore import QRectF, QPointF, Qt
from PyQt5.QtGui import QColor, QPainterPath, QPen

from eddy.core.datatypes import DiagramMode, Identity, Restriction
from eddy.core.exceptions import ParseError
from eddy.core.items.nodes.common.base import AbstractNode
from eddy.core.items.nodes.common.label import Label
from eddy.core.regex import RE_CARDINALITY


class SquaredNode(AbstractNode):
    """
    This is the base class for all the Squared shaped nodes.
    """
    __metaclass__ = ABCMeta

    def __init__(self, width=20, height=20, brush='#fcfcfc', restriction=None, cardinality=None, **kwargs):
        """
        Initialize the node.
        :type width: int
        :type height: int
        :type brush: T <= QBrush | QColor | Color | tuple | list | bytes | unicode
        :type restriction: Restriction
        :type cardinality: dict
        """
        super().__init__(**kwargs)

        self._restriction = restriction or Restriction.Exists
        self._cardinality = cardinality if self.restriction is Restriction.Cardinality else dict(min=None, max=None)

        self.brush = brush
        self.pen = QPen(QColor(0, 0, 0), 1.0, Qt.SolidLine)
        self.polygon = self.createRect(20, 20)
        self.label = Label(self.restriction.label, centered=False, editable=False, parent=self)
        self.label.updatePos()

    ####################################################################################################################
    #                                                                                                                  #
    #   PROPERTIES                                                                                                     #
    #                                                                                                                  #
    ####################################################################################################################

    @property
    def identity(self):
        """
        Returns the identity of the current node.
        :rtype: Identity
        """
        return Identity.Concept

    @identity.setter
    def identity(self, identity):
        """
        Set the identity of the current node.
        :type identity: Identity
        """
        pass

    @property
    def cardinality(self):
        """
        Returns the cardinality of the node.
        :rtype: dict
        """
        if self._cardinality is not None:
            return self._cardinality
        return dict(min=None, max=None)

    @cardinality.setter
    def cardinality(self, cardinality):
        """
        Set the cardinality restriction of this node.
        If the restriction type of this node is not RestrictionType.cardinality the cardinality will be set to default.
        :type cardinality: dict
        """
        self._cardinality = cardinality
        if self.restriction is not Restriction.Cardinality:
            self._cardinality = dict(min=None, max=None)

    @property
    def restriction(self):
        """
        Returns the restriction type of the node.
        :rtype: Restriction
        """
        return self._restriction

    @restriction.setter
    def restriction(self, restriction):
        """
        Set the restriction of this node.
        Setting the restriction type will also reset the cardinality which would need to be set again.
        :type restriction: Restriction
        """
        self._restriction = restriction
        self._cardinality = dict(min=None, max=None)

    ####################################################################################################################
    #                                                                                                                  #
    #   INTERFACE                                                                                                      #
    #                                                                                                                  #
    ####################################################################################################################

    def copy(self, scene):
        """
        Create a copy of the current item.
        :type scene: DiagramScene
        """
        kwargs = {
            'description': self.description,
            'height': self.height(),
            'id': self.id,
            'scene': scene,
            'url': self.url,
            'width': self.width(),
        }
        node = self.__class__(**kwargs)
        node.setPos(self.pos())
        node.setLabelText(self.labelText())
        node.setLabelPos(node.mapFromScene(self.mapToScene(self.labelPos())))
        return node

    def height(self):
        """
        Returns the height of the shape.
        :rtype: int
        """
        return self.polygon.height()

    def width(self):
        """
        Returns the width of the shape.
        :rtype: int
        """
        return self.polygon.width()

    ####################################################################################################################
    #                                                                                                                  #
    #   AUXILIARY METHODS                                                                                              #
    #                                                                                                                  #
    ####################################################################################################################

    @staticmethod
    def createRect(shape_w, shape_h):
        """
        Returns the initialized rect according to the given width/height.
        :type shape_w: int
        :type shape_h: int
        :rtype: QRectF
        """
        return QRectF(-shape_w / 2, -shape_h / 2, shape_w, shape_h)

    ####################################################################################################################
    #                                                                                                                  #
    #   IMPORT / EXPORT                                                                                                #
    #                                                                                                                  #
    ####################################################################################################################

    @classmethod
    def fromGraphol(cls, scene, E):
        """
        Create a new item instance by parsing a Graphol document item entry.
        :type scene: DiagramScene
        :type E: QDomElement
        :rtype: AbstractNode
        """
        U = E.elementsByTagName('data:url').at(0).toElement()
        D = E.elementsByTagName('data:description').at(0).toElement()
        G = E.elementsByTagName('shape:geometry').at(0).toElement()
        L = E.elementsByTagName('shape:label').at(0).toElement()

        kwargs = {
            'description': D.text(),
            'height': int(G.attribute('height')),
            'id': E.attribute('id'),
            'scene': scene,
            'url': U.text(),
            'width': int(G.attribute('width')),
        }

        node = cls(**kwargs)
        node.setPos(QPointF(int(G.attribute('x')), int(G.attribute('y'))))
        node.setLabelText(L.text())
        node.setLabelPos(node.mapFromScene(QPointF(int(L.attribute('x')), int(L.attribute('y')))))
        return node

    def toGraphol(self, document):
        """
        Export the current item in Graphol format.
        :type document: QDomDocument
        :rtype: QDomElement
        """
        pos1 = self.pos()
        pos2 = self.mapToScene(self.labelPos())

        # create the root element for this node
        node = document.createElement('node')
        node.setAttribute('id', self.id)
        node.setAttribute('type', self.xmlname)

        # add node attributes
        url = document.createElement('data:url')
        url.appendChild(document.createTextNode(self.url))
        description = document.createElement('data:description')
        description.appendChild(document.createTextNode(self.description))

        # add the shape geometry
        geometry = document.createElement('shape:geometry')
        geometry.setAttribute('height', self.height())
        geometry.setAttribute('width', self.width())
        geometry.setAttribute('x', pos1.x())
        geometry.setAttribute('y', pos1.y())

        # add the shape label
        label = document.createElement('shape:label')
        label.setAttribute('height', self.label.height())
        label.setAttribute('width', self.label.width())
        label.setAttribute('x', pos2.x())
        label.setAttribute('y', pos2.y())
        label.appendChild(document.createTextNode(self.label.text()))

        node.appendChild(url)
        node.appendChild(description)
        node.appendChild(geometry)
        node.appendChild(label)

        return node

    ####################################################################################################################
    #                                                                                                                  #
    #   GEOMETRY                                                                                                       #
    #                                                                                                                  #
    ####################################################################################################################

    def boundingRect(self):
        """
        Returns the shape bounding rectangle.
        :rtype: QRectF
        """
        o = self.selectionOffset
        return self.polygon.adjusted(-o, -o, o, o)

    def painterPath(self):
        """
        Returns the current shape as QPainterPath (used for collision detection).
        :rtype: QPainterPath
        """
        path = QPainterPath()
        path.addRect(self.polygon)
        return path

    def shape(self, *args, **kwargs):
        """
        Returns the shape of this item as a QPainterPath in local coordinates.
        :rtype: QPainterPath
        """
        path = QPainterPath()
        path.addRect(self.polygon)
        return path

    ####################################################################################################################
    #                                                                                                                  #
    #   LABEL SHORTCUTS                                                                                                #
    #                                                                                                                  #
    ####################################################################################################################

    def labelPos(self):
        """
        Returns the current label position.
        :rtype: QPointF
        """
        return self.label.pos()

    def labelText(self):
        """
        Returns the label text.
        :rtype: str
        """
        return self.label.text()

    def setLabelPos(self, pos):
        """
        Set the label position.
        :type pos: QPointF
        """
        self.label.setPos(pos)

    def setLabelText(self, text):
        """
        Set the label text: will additionally parse the text value and set the restriction type accordingly.
        :raise ParseError: if an invalid text value is supplied.
        :type text: T <= bytes | unicode
        """
        value = text.strip().lower()
        if value == Restriction.Exists.label:
            self.label.setText(value)
            self.restriction = Restriction.Exists
        elif value == Restriction.Forall.label:
            self.label.setText(value)
            self.restriction = Restriction.Forall
        elif value == Restriction.Self.label:
            self.label.setText(value)
            self.restriction = Restriction.Self
        else:
            match = RE_CARDINALITY.match(value)
            if match:
                self.label.setText(value)
                self.restriction = Restriction.Cardinality
                self.cardinality = {
                    'min': None if match.group('min') == '-' else int(match.group('min')),
                    'max': None if match.group('max') == '-' else int(match.group('max')),
                }
            else:
                raise ParseError('invalid restriction supplied: {}'.format(text))

    def updateLabelPos(self, *args, **kwargs):
        """
        Update the label position.
        """
        self.label.updatePos(*args, **kwargs)

    ####################################################################################################################
    #                                                                                                                  #
    #   DRAWING                                                                                                        #
    #                                                                                                                  #
    ####################################################################################################################

    def paint(self, painter, option, widget=None):
        """
        Paint the node in the graphic view.
        :type painter: QPainter
        :type option: int
        :type widget: QWidget
        """
        scene = self.scene()

        if self.isSelected():
            painter.setPen(self.selectionPen)
            painter.drawRect(self.boundingRect())

        if scene.mode is DiagramMode.EdgeInsert and scene.mouseOverNode is self:

            edge = scene.command.edge

            brush = self.brushConnectionOk
            if not scene.validator.check(edge.source, edge, scene.mouseOverNode):
                brush = self.brushConnectionBad

            painter.setPen(Qt.NoPen)
            painter.setBrush(brush)
            painter.drawRect(self.boundingRect())

        painter.setBrush(self.brush)
        painter.setPen(self.pen)
        painter.drawRect(self.polygon)
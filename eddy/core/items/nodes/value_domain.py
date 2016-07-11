# -*- coding: utf-8 -*-

##########################################################################
#                                                                        #
#  Eddy: a graphical editor for the specification of Graphol ontologies  #
#  Copyright (C) 2015 Daniele Pantaleone <pantaleone@dis.uniroma1.it>    #
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
#  A.Ruberti at Sapienza University of Rome: http://www.dis.uniroma1.it  #
#                                                                        #
#     - Domenico Lembo <lembo@dis.uniroma1.it>                           #
#     - Valerio Santarelli <santarelli@dis.uniroma1.it>                  #
#     - Domenico Fabio Savo <savo@dis.uniroma1.it>                       #
#     - Daniele Pantaleone <pantaleone@dis.uniroma1.it>                  #
#     - Marco Console <console@dis.uniroma1.it>                          #
#                                                                        #
##########################################################################


from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QPainterPath, QIcon

from eddy.core.datatypes.graphol import Item, Identity
from eddy.core.datatypes.misc import Brush, Pen
from eddy.core.datatypes.owl import Datatype
from eddy.core.items.nodes.common.base import AbstractNode
from eddy.core.items.nodes.common.label import NodeLabel
from eddy.core.qt import Font


class ValueDomainNode(AbstractNode):
    """
    This class implements the 'Value-Domain' node.
    """
    Identities = {Identity.ValueDomain}
    Type = Item.ValueDomainNode
    MinHeight = 40
    MinWidth = 90

    def __init__(self, width=MinWidth, height=MinHeight, brush=None, **kwargs):
        """
        Initialize the ValueDomain node.
        :type width: int
        :type height: int
        :type brush: QBrush
        """
        super().__init__(**kwargs)
        self.brush = brush or Brush.White255A
        self.pen = Pen.SolidBlack1Pt
        self.polygon = self.createPolygon(self.MinWidth, self.MinHeight)
        self.background = self.createBackground(self.MinWidth + 8, self.MinHeight + 8)
        self.selection = self.createSelection(self.MinWidth + 8, self.MinHeight + 8)
        self.label = NodeLabel(template=Datatype.string.value,
                               editable=False,
                               movable=False,
                               pos=self.center,
                               parent=self)
        self.updateLayout()
        self.updateTextPos()

    #############################################
    #   PROPERTIES
    #################################

    @property
    def datatype(self):
        """
        Returns the datatype associated with this node.
        :rtype: Datatype
        """
        return Datatype.forValue(self.text())

    @property
    def identity(self):
        """
        Returns the identity of the current node.
        :rtype: Identity
        """
        return Identity.ValueDomain

    @identity.setter
    def identity(self, identity):
        """
        Set the identity of the current node.
        :type identity: Identity
        """
        pass

    #############################################
    #   INTERFACE
    #################################

    def boundingRect(self):
        """
        Returns the shape bounding rectangle.
        :rtype: QRectF
        """
        return self.selection

    def copy(self, diagram):
        """
        Create a copy of the current item.
        :type diagram: Diagram
        """
        kwargs = {'id': self.id, 'brush': self.brush, 'height': self.height(), 'width': self.width()}
        node = diagram.factory.create(self.type(), **kwargs)
        node.setPos(self.pos())
        node.setText(self.text())
        node.setTextPos(node.mapFromScene(self.mapToScene(self.textPos())))
        return node

    @staticmethod
    def createBackground(width, height):
        """
        Returns the initialized background polygon according to the given width/height.
        :type width: int
        :type height: int
        :rtype: QRectF
        """
        return QRectF(-width / 2, -height / 2, width, height)

    @staticmethod
    def createPolygon(width, height):
        """
        Returns the initialized polygon according to the given width/height.
        :type width: int
        :type height: int
        :rtype: QRectF
        """
        return QRectF(-width / 2, -height / 2, width, height)

    def height(self):
        """
        Returns the height of the shape.
        :rtype: int
        """
        return self.polygon.height()

    @classmethod
    def icon(cls, width, height, **kwargs):
        """
        Returns an icon of this item suitable for the palette.
        :type width: int
        :type height: int
        :rtype: QIcon
        """
        icon = QIcon()
        for i in (1.0, 2.0):
            # CREATE THE PIXMAP
            pixmap = QPixmap(width * i, height * i)
            pixmap.setDevicePixelRatio(i)
            pixmap.fill(Qt.transparent)
            # PAINT THE SHAPE
            polygon = cls.createPolygon(54, 34)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Pen.SolidBlack1Pt)
            painter.setBrush(Brush.White255A)
            painter.translate(width / 2, height / 2)
            painter.drawRoundedRect(polygon, 6, 6)
            # PAINT THE TEXT INSIDE THE SHAPE
            painter.setFont(Font('Arial', 10, Font.Light))
            painter.drawText(polygon, Qt.AlignCenter, 'xsd:string')
            painter.end()
            # ADD THE PIXMAP TO THE ICON
            icon.addPixmap(pixmap)
        return icon

    def paint(self, painter, option, widget=None):
        """
        Paint the node in the diagram.
        :type painter: QPainter
        :type option: QStyleOptionGraphicsItem
        :type widget: QWidget
        """
        # SET THE RECT THAT NEEDS TO BE REPAINTED
        painter.setClipRect(option.exposedRect)
        # SELECTION AREA
        painter.setPen(self.selectionPen)
        painter.setBrush(self.selectionBrush)
        painter.drawRect(self.selection)
        # SYNTAX VALIDATION
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.backgroundPen)
        painter.setBrush(self.backgroundBrush)
        painter.drawRoundedRect(self.background, 8, 8)
        # SHAPE
        painter.setBrush(self.brush)
        painter.setPen(self.pen)
        painter.drawRoundedRect(self.polygon, 8, 8)

    def painterPath(self):
        """
        Returns the current shape as QPainterPath (used for collision detection).
        :rtype: QPainterPath
        """
        path = QPainterPath()
        path.addRoundedRect(self.polygon, 8, 8)
        return path

    def setText(self, text):
        """
        Set the label text.
        :type text: str
        """
        datatype = Datatype.forValue(text) or Datatype.string
        self.label.setText(datatype.value)
        self.updateLayout()

    def setTextPos(self, pos):
        """
        Set the label position.
        :type pos: QPointF
        """
        self.label.setPos(pos)

    def shape(self):
        """
        Returns the shape of this item as a QPainterPath in local coordinates.
        :rtype: QPainterPath
        """
        path = QPainterPath()
        path.addRoundedRect(self.polygon, 8, 8)
        return path

    def text(self):
        """
        Returns the label text.
        :rtype: str
        """
        return self.label.text()

    def textPos(self):
        """
        Returns the current label position in item coordinates.
        :rtype: QPointF
        """
        return self.label.pos()

    def updateTextPos(self, *args, **kwargs):
        """
        Update the label position.
        """
        self.label.updatePos(*args, **kwargs)

    def updateLayout(self):
        """
        Update current shape rect according to the selected datatype.
        """
        width = max(self.label.width() + 16, self.MinWidth)
        self.polygon = self.createPolygon(width, self.MinHeight)
        self.background = self.createBackground(width + 8, self.MinHeight + 8)
        self.selection = self.createSelection(width + 8, self.MinHeight + 8)
        self.updateTextPos()
        self.updateEdges()

    def width(self):
        """
        Returns the width of the shape.
        :rtype: int
        """
        return self.polygon.width()
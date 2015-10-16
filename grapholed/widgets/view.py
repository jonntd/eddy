# -*- coding: utf-8 -*-

##########################################################################
#                                                                        #
#  Grapholed: a diagramming software for the Graphol language.           #
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
##########################################################################
#                                                                        #
#  Graphol is developed by members of the DASI-lab group of the          #
#  Dipartimento di Informatica e Sistemistica "A.Ruberti" at Sapienza    #
#  University of Rome: http://www.dis.uniroma1.it/~graphol/:             #
#                                                                        #
#     - Domenico Lembo <lembo@dis.uniroma1.it>                           #
#     - Marco Console <console@dis.uniroma1.it>                          #
#     - Valerio Santarelli <santarelli@dis.uniroma1.it>                  #
#     - Domenico Fabio Savo <savo@dis.uniroma1.it>                       #
#                                                                        #
##########################################################################


from functools import partial

from grapholed.functions import clamp, shaded
from grapholed.widgets import ZoomControl

from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QEvent, pyqtSlot, QPointF, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt5.QtWidgets import QGraphicsView, QWidget, QLabel, QHBoxLayout, QStyleOption, QStyle, QVBoxLayout


class MainView(QGraphicsView):
    """
    This class implements the main view displayed in the MDI area.
    """
    navUpdate = pyqtSignal()
    zoomChanged = pyqtSignal(float)

    def __init__(self, scene):
        """
        Initialize the main scene.
        :param scene: the graphics scene to render in the main view.
        """
        super().__init__(scene)
        self.viewMove = None
        self.viewMoveRate = 20
        self.viewMoveBound = 10
        self.mousePressCenterPos = None
        self.mousePressPos = None
        self.zoom = 1.00

    ############################################### SIGNAL HANDLERS ####################################################

    def handleScaleChanged(self, zoom):
        """
        Executed when the scale factor changes (triggered by the Main Slider in the Toolbar)
        :param zoom: the scale factor.
        """
        self.scaleView(zoom)

    ############################################### EVENT HANDLERS #####################################################

    def mousePressEvent(self, mouseEvent):
        """
        Executed when a mouse button is clicked on the view.
        :param mouseEvent: the mouse event instance.
        """
        self.mousePressCenterPos = self.visibleRect().center()
        self.mousePressPos = mouseEvent.pos()
        if not mouseEvent.buttons() & Qt.MidButton:
            # middle button is used to move the viewport => everything
            # else needs to be forwared to the scene and graphicsitems
            super().mousePressEvent(mouseEvent)

    def mouseMoveEvent(self, mouseEvent):
        """
        Executed when then mouse is moved on the view.
        :param mouseEvent: the mouse event instance.
        """
        if mouseEvent.buttons() & Qt.MidButton:
            # move the view accoriding to the delta between current mouse post and stored one
            self.centerOn(self.mousePressCenterPos - mouseEvent.pos() + self.mousePressPos)
        else:
            # handle the movement of graphics item before anything else
            super().mouseMoveEvent(mouseEvent)

            if mouseEvent.buttons() & Qt.LeftButton:

                self.stopViewMove()

                # see if the mouse is outside the viewport
                viewPortRect = self.viewport().rect()
                if not viewPortRect.contains(mouseEvent.pos()):

                    # check if we have an item under the mouse => we are
                    # dragging it outside the viewport rect, hence we need
                    # to move the view so that the item stays visible
                    if self.scene().itemOnTopOf(self.mapToScene(mouseEvent.pos()), edges=False):

                        delta = QPointF()
                        
                        if mouseEvent.pos().x() < viewPortRect.left():
                            delta.setX(mouseEvent.pos().x() - viewPortRect.left())
                        elif mouseEvent.pos().x() > viewPortRect.right():
                            delta.setX(mouseEvent.pos().x() - viewPortRect.right())
                            
                        if mouseEvent.pos().y() < viewPortRect.top():
                            delta.setY(mouseEvent.pos().y() - viewPortRect.top())
                        elif mouseEvent.pos().y() > viewPortRect.bottom():
                            delta.setY(mouseEvent.pos().y() - viewPortRect.bottom())

                        if delta:

                            # clamp the value so the moving operation won't be too fast
                            delta.setX(clamp(delta.x(), -self.viewMoveBound, +self.viewMoveBound))
                            delta.setY(clamp(delta.y(), -self.viewMoveBound, +self.viewMoveBound))

                            # start the view move using the predefined rate
                            self.startViewMove(delta, self.viewMoveRate)

    def mouseReleaseEvent(self, mouseEvent):
        """
        Executed when the mouse is released from the view.
        :param mouseEvent: the mouse event instance.
        """
        self.mousePressCenterPos = None
        self.mousePressPos = None
        self.stopViewMove()
        if mouseEvent.button() != Qt.MidButton:
            super().mouseReleaseEvent(mouseEvent)

    def viewportEvent(self, event):
        """
        Executed whenever the viewport changes.
        :param event: the viewport event instance.
        """
        # if the main view has been repainted, emit a
        # signal so that also the navigator can update
        if event.type() == QEvent.Paint:
            self.navUpdate.emit()
        return super().viewportEvent(event)

    def wheelEvent(self, wheelEvent):
        """
        Executed when the mouse wheel is moved on the scene.
        :param wheelEvent: the mouse wheel event.
        """
        if wheelEvent.modifiers() & Qt.ControlModifier:

            # allow zooming with the mouse wheel
            zoom = self.zoom
            zoom += +(1 / ZoomControl.Step) if wheelEvent.angleDelta().y() > 0 else -(1 / ZoomControl.Step)
            zoom = clamp(zoom, ZoomControl.MinScale, ZoomControl.MaxScale)

            if zoom != self.zoom:
                # set transformations anchors
                self.setTransformationAnchor(QGraphicsView.NoAnchor)
                self.setResizeAnchor(QGraphicsView.NoAnchor)
                # save the old position
                old = self.mapToScene(wheelEvent.pos())
                # change the zoom level
                self.scaleView(zoom)
                self.zoomChanged.emit(zoom)
                # get the new position
                new = self.mapToScene(wheelEvent.pos())
                # move the scene so the mouse is centered
                move = new - old
                self.translate(move.x(), move.y())

        else:
            # handle default behavior (view scrolling)
            super().wheelEvent(wheelEvent)

    ############################################# AUXILIARY METHODS ####################################################

    def moveBy(self, *__args):
        """
        Move the view by the given delta.
        """
        if len(__args) == 1:
            delta = __args[0]
        elif len(__args) == 2:
            delta = QPointF(__args[0], __args[1])
        else:
            raise TypeError('too many arguments; expected {0}, got {1}'.format(2, len(__args)))
        self.centerOn(self.visibleRect().center() + delta)

    def scaleView(self, zoom):
        """
        Scale the Main View according to the given zoom.
        :param zoom: the zoom factor.
        """
        transform = self.transform()
        self.resetTransform()
        self.translate(transform.dx(), transform.dy())
        self.scale(zoom, zoom)
        self.zoom = zoom

    def startViewMove(self, delta, rate):
        """
        Start the view movement.
        :param delta: the delta movement.
        :param rate: amount of milliseconds between refresh.
        """
        if self.viewMove:
            self.stopViewMove()

        # move the view: this is needed before the timer so that if we keep
        # moving the mouse fast outside the viewport rectangle we still are able
        # to move the view; if we don't do this the timer may not have kicked in
        # and thus we remain with a non-moving view with a unfocused graphicsitem
        self.moveBy(delta)

        # setup a timer for future move, so the view keeps moving
        # also if we are not moving the mouse anymore but we are
        # holding the position outside the viewport rect
        self.viewMove = QTimer()
        self.viewMove.timeout.connect(partial(self.moveBy, delta))
        self.viewMove.start(rate)

    def stopViewMove(self):
        """
        Stop the view movement by destroying the timer object causing it.
        """
        if self.viewMove:

            try:
                self.viewMove.stop()
                self.viewMove.timeout.disconnect()
            except RuntimeError:
                pass
            finally:
                self.viewMove = None

    def visibleRect(self):
        """
        Returns the visible area in scene coordinates.
        :rtype: QRectF
        """
        return self.mapToScene(self.viewport().rect()).boundingRect()


class Navigator(QWidget):
    """
    This class is used to display the current scene navigator.
    """

    ####################################################################################################################
    #                                                                                                                  #
    #   OVERVIEW                                                                                                       #
    #                                                                                                                  #
    ####################################################################################################################

    class Overview(QGraphicsView):
        """
        This class implements the view shown in the navigator.
        """
        navBrush = QColor(250, 140, 140, 100)
        navPen = QPen(QColor(250, 0, 0, 100), 1.0, Qt.SolidLine)

        def __init__(self, parent=None):
            """
            Initialize the overview.
            :param parent: the parent widget.
            """
            super().__init__(parent)
            self.mousepressed = False
            self.mainview = None

        ########################################## CUSTOM VIEW DRAWING #################################################

        def drawBackground(self, painter, rect):
            """
            Override scene drawBackground method so the grid is not rendered in the overview.
            :param painter: the active painter
            :param rect: the exposed rectangle
            """
            pass

        def drawForeground(self, painter, rect):
            """
            Draw the navigation cursor.
            :param painter: the active painter
            :param rect: the exposed rectangle
            """
            if self.mainview:
                painter.setPen(self.navPen)
                painter.setBrush(self.navBrush)
                painter.drawRect(self.mainview.visibleRect())

        ######################################### MOUSE EVENT HANDLERS #################################################

        def mousePressEvent(self, mouseEvent):
            """
            Executed when the mouse is pressed on the view.
            :param mouseEvent: the mouse event instance.
            """
            if self.mainview:
                self.mousepressed = True
                self.mainview.centerOn(self.mapToScene(mouseEvent.pos()))

        def mouseMoveEvent(self, mouseEvent):
            """
            Executed when the mouse is moved on the view.
            :param mouseEvent: the mouse event instance.
            """
            if self.mainview and self.mousepressed:
                self.mainview.centerOn(self.mapToScene(mouseEvent.pos()))

        def mouseReleaseEvent(self, mouseEvent):
            """
            Executed when the mouse is released from the view.
            :param mouseEvent: the mouse event instance.
            """
            if self.mainview:
                self.mousepressed = False

        ############################################ SIGNAL HANDLERS ###################################################

        @pyqtSlot()
        def handleNavUpdate(self):
            """
            Executed whenever the navigator view needs to be updated.
            """
            self.viewport().update()

        @pyqtSlot('QRectF')
        def handleSceneRectChanged(self, rect):
            """
            Executed whenever the rectangle of the scene rendered in the navigator changes.
            :param rect: the new rectangle.
            """
            self.fitInView(rect, Qt.KeepAspectRatio)

        ########################################### AUXILIARY METHODS ##################################################

        def setView(self, mainview):
            """
            Set the navigator over the given main view.
            :param mainview: the mainView from where to pick the scene for the navigator.
            """
            if self.mainview:

                try:
                    self.mainview.navUpdate.disconnect()
                except RuntimeError:
                    # which happens when the subwindow containing the view is closed
                    pass

            self.mainview = mainview

            if self.mainview:
                scene = self.mainview.scene()
                scene.sceneRectChanged.connect(self.handleSceneRectChanged)
                self.setScene(scene)
                self.fitInView(self.mainview.sceneRect(), Qt.KeepAspectRatio)
                self.mainview.navUpdate.connect(self.handleNavUpdate)
            else:
                # all subwindow closed => refresh so the foreground disappears
                self.viewport().update()

    ####################################################################################################################
    #                                                                                                                  #
    #   HEAD                                                                                                           #
    #                                                                                                                  #
    ####################################################################################################################

    class Head(QWidget):

        def __init__(self, body, parent=None):
            """
            Initialize the header of the widget.
            :param body: the body this header is controlling.
            :param parent: the parent widget
            """
            super().__init__(parent)
            self.body = body
            self.iconUp = QPixmap(':/icons/arrow-up')
            self.iconDown = QPixmap(':/icons/arrow-down')
            self.iconZoom = shaded(QPixmap(':/icons/zoom'), 0.7)
            self.headText = QLabel('Navigator')
            self.headImg1 = QLabel()
            self.headImg1.setPixmap(self.iconZoom)
            self.headImg2 = QLabel()

            self.headLayout = QHBoxLayout(self)
            self.headLayout.addWidget(self.headImg1, 0, Qt.AlignLeft)
            self.headLayout.addWidget(self.headText, 1, Qt.AlignLeft)
            self.headLayout.addWidget(self.headImg2, 0, Qt.AlignRight)
            self.headLayout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.headLayout.setContentsMargins(5, 4, 5, 4)

            self.setFixedSize(216, 30)
            self.setContentsMargins(0, 0, 0, 0)

        ############################################## EVENT HANDLERS ##################################################

        def enterEvent(self, event):
            """
            Executed when the mouse enter the widget area.
            :param event: the event instance.
            """
            self.setCursor(Qt.PointingHandCursor)

        def leaveEvent(self, event):
            """
            Executed when the mouse leaves the widget area.
            :param event: the event instance.
            """
            self.setCursor(Qt.ArrowCursor)

        def mousePressEvent(self, mouseEvent):
            """
            Executed when the mouse is pressed on the widget.
            :param mouseEvent: the event instance.
            """
            self.setCollapsed(self.body.isVisible())

        ############################################ AUXILIARY METHODS #################################################

        def setCollapsed(self, collapsed):
            """
            Set the collapsed status (of the attached body).
            :param collapsed: True if the body attached to the header should be collapsed, False otherwise.
            """
            self.body.setVisible(not collapsed)
            self.headImg2.setPixmap(self.iconDown if collapsed else self.iconUp)
            self.setProperty('class', 'collapsed' if collapsed else 'normal')
            # refresh the widget stylesheet
            self.style().unpolish(self)
            self.style().polish(self)
            # refresh the label stylesheet
            self.headText.style().unpolish(self.headText)
            self.headText.style().polish(self.headText)
            self.update()

        ############################################## LAYOUT UPDATE ###################################################

        def update(self, *__args):
            """
            Update the widget refreshing all the children.
            """
            self.headText.update()
            self.headImg1.update()
            super().update(*__args)

        ############################################## ITEM PAINTING ###################################################

        def paintEvent(self, paintEvent):
            """
            This is needed for the widget to pick the stylesheet.
            :param paintEvent: the paint event instance.
            """
            option = QStyleOption()
            option.initFrom(self)
            painter = QPainter(self)
            self.style().drawPrimitive(QStyle.PE_Widget, option, painter, self)

    ####################################################################################################################
    #                                                                                                                  #
    #   BODY                                                                                                           #
    #                                                                                                                  #
    ####################################################################################################################

    class Body(QWidget):

        def __init__(self, parent=None):
            """
            Initialize the body of the widget.
            :param parent: the parent widget.
            """
            super().__init__(parent)
            self.overview = Navigator.Overview()
            self.bodyLayout = QVBoxLayout(self)
            self.bodyLayout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.bodyLayout.setContentsMargins(0, 0, 0, 0)
            self.bodyLayout.addWidget(self.overview)
            self.setFixedSize(216, 216)
            self.setContentsMargins(0, 0, 0, 0)

        ############################################# ITEM PAINTING ####################################################

        def paintEvent(self, paintEvent):
            """
            This is needed for the widget to pick the stylesheet.
            :param paintEvent: the paint event instance.
            """
            option = QStyleOption()
            option.initFrom(self)
            painter = QPainter(self)
            self.style().drawPrimitive(QStyle.PE_Widget, option, painter, self)

    def __init__(self, collapsed=False):
        """
        Initialize the navigator.
        :param collapsed: whether the widget should be collapsed by default.
        """
        super().__init__()

        self.body = Navigator.Body()
        self.head = Navigator.Head(self.body)
        self.head.setCollapsed(collapsed)

        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.mainLayout.setContentsMargins(0, 0, 0, 4)
        self.mainLayout.setSpacing(0)
        self.mainLayout.addWidget(self.head)
        self.mainLayout.addWidget(self.body)

    ################################################# SHORTCUTS ########################################################

    def setView(self, mainview):
        """
        Set the navigator over the given main view.
        :param mainview: the main view from where to pick the scene for the navigator.
        """
        self.body.overview.setView(mainview)

    ################################################ LAYOUT UPDATE #####################################################

    def update(self, *__args):
        """
        Update the widget refreshing all the children.
        """
        self.head.update()
        self.body.update()
        super().update(*__args)
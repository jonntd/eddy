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


import os

from PyQt5 import QtCore
from PyQt5 import QtWidgets

from eddy.core.clipboard import Clipboard
from eddy.core.commands.edges import CommandEdgeAdd
from eddy.core.commands.nodes import CommandNodeAdd
from eddy.core.commands.nodes import CommandNodeMove
from eddy.core.commands.labels import CommandLabelMove
from eddy.core.datatypes.graphol import Item, Identity
from eddy.core.datatypes.misc import DiagramMode
from eddy.core.functions.graph import bfs
from eddy.core.functions.misc import snap, partition, first
from eddy.core.functions.path import expandPath
from eddy.core.functions.signals import connect
from eddy.core.guid import GUID
from eddy.core.items.factory import ItemFactory
from eddy.core.output import getLogger


LOGGER = getLogger(__name__)


class Diagram(QtWidgets.QGraphicsScene):
    """
    Extension of QtWidgets.QGraphicsScene which implements a single Graphol diagram.
    Additionally to built-in signals, this class emits:

    * sgnItemAdded: whenever an element is added to the Diagram.
    * sgnItemInsertionCompleted: whenever an item 'MANUAL' insertion process is completed.
    * sgnItemRemoved: whenever an element is removed from the Diagram.
    * sgnModeChanged: whenever the Diagram operational mode (or its parameter) changes.
    * sgnUpdated: whenever the Diagram has been updated in any of its parts.
    """
    GridSize = 20
    MinSize = 2000
    MaxSize = 1000000

    sgnItemAdded = QtCore.pyqtSignal('QGraphicsScene', 'QGraphicsItem')
    sgnItemInsertionCompleted = QtCore.pyqtSignal('QGraphicsItem', int)
    sgnItemRemoved = QtCore.pyqtSignal('QGraphicsScene', 'QGraphicsItem')
    sgnModeChanged = QtCore.pyqtSignal(DiagramMode)
    sgnNodeIdentification = QtCore.pyqtSignal('QGraphicsItem')
    sgnUpdated = QtCore.pyqtSignal()

    def __init__(self, path, parent):
        """
        Initialize the diagram.
        :type path: str
        :type parent: Project
        """
        super(Diagram, self).__init__(parent)

        self.factory = ItemFactory(self)
        self.guid = GUID(self)
        self.mode = DiagramMode.Idle
        self.modeParam = Item.Undefined
        self.path = expandPath(path)
        self.pasteX = Clipboard.PasteOffsetX
        self.pasteY = Clipboard.PasteOffsetY

        self.mo_Node = None
        self.mp_Data = None
        self.mp_Edge = None
        self.mp_Label = None
        self.mp_LabelPos = None
        self.mp_Node = None
        self.mp_NodePos = None
        self.mp_Pos = None

        connect(self.sgnItemAdded, self.onConnectionChanged)
        connect(self.sgnItemRemoved, self.onConnectionChanged)
        connect(self.sgnNodeIdentification, self.doNodeIdentification)

    #############################################
    #   PROPERTIES
    #################################

    @property
    def id(self):
        """
        Returns the pseudo unique id of this diagram (alias for Diagram.path).
        :rtype: str
        """
        return self.path

    @property
    def name(self):
        """
        Returns the name of the file where this diagram is stored.
        :rtype: str
        """
        return os.path.basename(os.path.normpath(self.path))

    @property
    def project(self):
        """
        Returns the project this diagram belongs to (alias for Diagram.parent()).
        :rtype: Project
        """
        return self.parent()

    @property
    def session(self):
        """
        Returns the session this diagram belongs to (alias for Diagram.project.parent()).
        :rtype: Session
        """
        return self.project.parent()

    #############################################
    #   EVENTS
    #################################

    def dragEnterEvent(self, dragEvent):
        """
        Executed when a dragged element enters the scene area.
        :type dragEvent: QGraphicsSceneDragDropEvent
        """
        super(Diagram, self).dragEnterEvent(dragEvent)
        if dragEvent.mimeData().hasFormat('text/plain'):
            dragEvent.setDropAction(QtCore.Qt.CopyAction)
            dragEvent.accept()
        else:
            dragEvent.ignore()

    def dragMoveEvent(self, dragEvent):
        """
        Executed when an element is dragged over the scene.
        :type dragEvent: QGraphicsSceneDragDropEvent
        """
        super(Diagram, self).dragMoveEvent(dragEvent)
        if dragEvent.mimeData().hasFormat('text/plain'):
            dragEvent.setDropAction(QtCore.Qt.CopyAction)
            dragEvent.accept()
        else:
            dragEvent.ignore()

    def dropEvent(self, dropEvent):
        """
        Executed when a dragged element is dropped on the diagram.
        :type dropEvent: QGraphicsSceneDragDropEvent
        """
        super(Diagram, self).dropEvent(dropEvent)
        if dropEvent.mimeData().hasFormat('text/plain'):
            snapToGrid = self.session.action('toggle_grid').isChecked()
            node = self.factory.create(Item.forValue(dropEvent.mimeData().text()))
            node.setPos(snap(dropEvent.scenePos(), Diagram.GridSize, snapToGrid))
            self.session.undostack.push(CommandNodeAdd(self, node))
            self.sgnItemInsertionCompleted.emit(node, dropEvent.modifiers())
            dropEvent.setDropAction(QtCore.Qt.CopyAction)
            dropEvent.accept()
        else:
            dropEvent.ignore()

    def mousePressEvent(self, mouseEvent):
        """
        Executed when a mouse button is clicked on the scene.
        :type mouseEvent: QGraphicsSceneMouseEvent
        """
        mouseModifiers = mouseEvent.modifiers()
        mouseButtons = mouseEvent.buttons()
        mousePos = mouseEvent.scenePos()

        if mouseButtons & QtCore.Qt.LeftButton:

            if self.mode is DiagramMode.NodeAdd:

                #############################################
                # NODE INSERTION
                #################################

                snapToGrid = self.session.action('toggle_grid').isChecked()
                node = self.factory.create(Item.forValue(self.modeParam))
                node.setPos(snap(mousePos, Diagram.GridSize, snapToGrid))
                self.session.undostack.push(CommandNodeAdd(self, node))
                self.sgnItemInsertionCompleted.emit(node, mouseEvent.modifiers())

            elif self.mode is DiagramMode.EdgeAdd:

                #############################################
                # EDGE INSERTION
                #################################

                node = self.itemOnTopOf(mousePos, edges=False)
                if node:
                    edge = self.factory.create(Item.forValue(self.modeParam), source=node)
                    edge.updateEdge(target=mousePos)
                    self.mp_Edge = edge
                    self.addItem(edge)

            else:

                # Execute super at first since this may change the diagram
                # mode: some actions are directly handle by graphics items
                # (i.e: edge breakpoint move, edge anchor move, node shape
                # resize) and we need to check whether any of them is being
                # performed before handling the even locally.
                super(Diagram, self).mousePressEvent(mouseEvent)

                if self.mode is DiagramMode.Idle:

                    if mouseModifiers & QtCore.Qt.ShiftModifier:

                        #############################################
                        # LABEL MOVE
                        #################################

                        item = self.itemOnTopOf(mousePos, nodes=False, edges=False, labels=True)
                        if item and item.isMovable():
                            self.clearSelection()
                            self.mp_Label = item
                            self.mp_LabelPos = item.pos()
                            self.mp_Pos = mousePos
                            self.setMode(DiagramMode.LabelMove)

                    else:

                        #############################################
                        # ITEM SELECTION
                        #################################

                        item = self.itemOnTopOf(mousePos, labels=True)
                        if item:

                            if item.isLabel():
                                # If we are hitting a label, check whether the label
                                # is overlapping it's parent item and such item is
                                # also intersecting the current mouse position: if so,
                                # use the parent item as placeholder for the selection.
                                parent = item.parentItem()
                                items = self.items(mousePos)
                                item =  parent if parent in items else None

                            if item:

                                if mouseModifiers & QtCore.Qt.ControlModifier:
                                    # CTRL => support item multi selection.
                                    item.setSelected(not item.isSelected())
                                else:
                                    if self.selectedItems():
                                        # Some elements have been already selected in the
                                        # diagram, during a previous mouse press event.
                                        if not item.isSelected():
                                            # There are some items selected but we clicked
                                            # on a node which is not currently selected, so
                                            # make this node the only selected one.
                                            self.clearSelection()
                                            item.setSelected(True)
                                    else:
                                        # No item (nodes or edges) is selected and we just
                                        # clicked on one so make sure to select this item and
                                        # because selectedItems() filters out item Label's,
                                        # clear out the selection on the diagram.
                                        self.clearSelection()
                                        item.setSelected(True)

                                # If we have some nodes selected we need to prepare data for a
                                # possible item move operation: we need to make sure to retrieve
                                # the node below the mouse cursor that will act as as mouse grabber
                                # to compute delta  movements for each component in the selection.
                                selected = self.selectedNodes()
                                if selected:
                                    self.mp_Node = self.itemOnTopOf(mousePos, edges=False)
                                    if self.mp_Node:
                                        self.mp_NodePos = self.mp_Node.pos()
                                        self.mp_Pos = mousePos
                                        self.mp_Data = {
                                            'nodes': {
                                                node: {
                                                    'anchors': {k: v for k, v in node.anchors.items()},
                                                    'pos': node.pos(),
                                                } for node in selected},
                                            'edges': {}
                                        }
                                        # Figure out if the nodes we are moving are sharing edges:
                                        # if that's the case, move the edge together with the nodes
                                        # (which actually means moving the edge breakpoints).
                                        for node in self.mp_Data['nodes']:
                                            for edge in node.edges:
                                                if edge not in self.mp_Data['edges']:
                                                    if edge.other(node).isSelected():
                                                        self.mp_Data['edges'][edge] = edge.breakpoints[:]

    def mouseMoveEvent(self, mouseEvent):
        """
        Executed when then mouse is moved on the scene.
        :type mouseEvent: QGraphicsSceneMouseEvent
        """
        mouseButtons = mouseEvent.buttons()
        mousePos = mouseEvent.scenePos()

        if mouseButtons & QtCore.Qt.LeftButton:

            if self.mode is DiagramMode.EdgeAdd:

                #############################################
                # EDGE INSERTION
                #################################

                if self.isEdgeAddInProgress():

                    statusBar = self.session.statusBar()
                    edge = self.mp_Edge
                    edge.updateEdge(target=mousePos)

                    previousNode = self.mo_Node
                    if previousNode:
                        previousNode.updateNode(selected=False)

                    currentNode = self.itemOnTopOf(mousePos, edges=False, skip={edge.source})
                    if currentNode:
                        self.mo_Node = currentNode
                        pvr = self.project.profile.check(edge.source, edge, currentNode)
                        currentNode.updateNode(selected=False, valid=pvr.isValid())
                        if not pvr.isValid():
                            statusBar.showMessage(pvr.message())
                        else:
                            statusBar.clearMessage()
                    else:
                        statusBar.clearMessage()
                        self.mo_Node = None
                        self.project.profile.reset()

            elif self.mode is DiagramMode.LabelMove:

                #############################################
                # LABEL MOVE
                #################################

                if self.isLabelMoveInProgress():

                    snapToGrid = self.session.action('toggle_grid').isChecked()
                    point = self.mp_LabelPos + mousePos - self.mp_Pos
                    point = snap(point, Diagram.GridSize / 4, snapToGrid)
                    delta = point - self.mp_LabelPos
                    self.mp_Label.setPos(self.mp_LabelPos + delta)

            else:

                if self.mode is DiagramMode.Idle:
                    if self.mp_Node:
                        self.setMode(DiagramMode.NodeMove)

                if self.mode is DiagramMode.NodeMove:

                    #############################################
                    # ITEM MOVEMENT
                    #################################

                    if self.isNodeMoveInProgress():

                        snapToGrid = self.session.action('toggle_grid').isChecked()
                        point = self.mp_NodePos + mousePos - self.mp_Pos
                        point = snap(point, Diagram.GridSize, snapToGrid)
                        delta = point - self.mp_NodePos
                        edges = set()

                        for edge, breakpoints in self.mp_Data['edges'].items():
                            for i in range(len(breakpoints)):
                                edge.breakpoints[i] = breakpoints[i] + delta

                        for node, data in self.mp_Data['nodes'].items():
                            edges |= set(node.edges)
                            node.setPos(data['pos'] + delta)
                            for edge, pos in data['anchors'].items():
                                node.setAnchor(edge, pos + delta)

                        for edge in edges:
                            edge.updateEdge()

        super(Diagram, self).mouseMoveEvent(mouseEvent)

    def mouseReleaseEvent(self, mouseEvent):
        """
        Executed when the mouse is released from the scene.
        :type mouseEvent: QGraphicsSceneMouseEvent
        """
        mouseModifiers = mouseEvent.modifiers()
        mouseButton = mouseEvent.button()
        mousePos = mouseEvent.scenePos()

        if mouseButton == QtCore.Qt.LeftButton:

            if self.mode is DiagramMode.EdgeAdd:

                #############################################
                # EDGE INSERTION
                #################################

                if self.isEdgeAddInProgress():

                    edge = self.mp_Edge
                    edge.source.updateNode(selected=False)
                    currentNode = self.itemOnTopOf(mousePos, edges=False, skip={edge.source})
                    insertEdge = False

                    if currentNode:
                        currentNode.updateNode(selected=False)
                        pvr = self.project.profile.check(edge.source, edge, currentNode)
                        if pvr.isValid():
                            edge.target = currentNode
                            insertEdge = True

                    # We temporarily remove the item from the diagram and we perform the
                    # insertion using the undo command that will also emit the sgnItemAdded
                    # signal hence all the widgets will be notified of the edge insertion.
                    # We do this because while creating the edge we need to display it so the
                    # user knows what he is connecting, but we don't want to truly insert
                    # it till it's necessary (when the mouse is released and the validation
                    # confirms that the generated expression is a valid graphol expression).
                    self.removeItem(edge)

                    if insertEdge:
                        self.session.undostack.push(CommandEdgeAdd(self, edge))
                        edge.updateEdge()

                    self.clearSelection()
                    self.project.profile.reset()
                    statusBar = self.session.statusBar()
                    statusBar.clearMessage()

                    self.sgnItemInsertionCompleted.emit(edge, mouseModifiers)

            elif self.mode is DiagramMode.LabelMove:

                #############################################
                # LABEL MOVE
                #################################

                if self.isLabelMoveInProgress():

                    pos = self.mp_Label.pos()
                    if self.mp_LabelPos != pos:
                        item = self.mp_Label.parentItem()
                        command = CommandLabelMove(self, item, self.mp_LabelPos, pos)
                        self.session.undostack.push(command)

                    self.setMode(DiagramMode.Idle)

            elif self.mode is DiagramMode.NodeMove:

                #############################################
                # ITEM MOVEMENT
                #################################

                if self.isNodeMoveInProgress():

                    pos = self.mp_Node.pos()
                    if self.mp_NodePos != pos:
                        data = {
                            'undo': self.mp_Data,
                            'redo': {
                                'nodes': {
                                    node: {
                                        'anchors': {k: v for k, v in node.anchors.items()},
                                        'pos': node.pos(),
                                    } for node in self.mp_Data['nodes']},
                                'edges': {x: x.breakpoints[:] for x in self.mp_Data['edges']}
                            }
                        }
                        self.session.undostack.push(CommandNodeMove(self, data))

                    self.setMode(DiagramMode.Idle)

        elif mouseButton == QtCore.Qt.RightButton:

            if self.mode is not DiagramMode.SceneDrag:

                #############################################
                # CONTEXTUAL MENU
                #################################

                item = self.itemOnTopOf(mousePos)
                if not item:
                    self.clearSelection()
                    items = []
                else:
                    items = self.selectedItems()
                    if item not in items:
                        self.clearSelection()
                        item.setSelected(True)
                        items = [item]

                self.mp_Pos = mousePos
                menu = self.session.mf.create(self, items, mousePos)
                menu.exec_(mouseEvent.screenPos())

        super(Diagram, self).mouseReleaseEvent(mouseEvent)

        self.mo_Node = None
        self.mp_Data = None
        self.mp_Edge = None
        self.mp_Label = None
        self.mp_LabelPos = None
        self.mp_Node = None
        self.mp_NodePos = None
        self.mp_Pos = None

    #############################################
    #   SLOTS
    #################################

    @QtCore.pyqtSlot('QGraphicsItem')
    def doNodeIdentification(self, node):
        """
        Perform node identification.
        :type node: AbstractNode
        """
        if Identity.Neutral in node.identities():

            predicate = lambda n1: Identity.Neutral in n1.identities()
            collection = bfs(source=node, filter_on_visit=predicate)
            generators = partition(predicate, collection)
            excluded = set()
            strong = set(generators[1])
            weak = set(generators[0])

            #############################################
            # SPECIAL CASES
            #################################

            # FILTERS
            f1 = lambda x: x.type() is Item.InputEdge
            f2 = lambda x: x.type() is Item.IndividualNode
            f3 = lambda x: x.type() is Item.MembershipEdge
            f4 = lambda x: x.identity() in {Identity.Role, Identity.Attribute, Identity.Concept} and Identity.Neutral not in x.identities()
            f5 = lambda x: x.type() in {Item.RoleNode, Item.RoleInverseNode, Item.AttributeNode}
            f6 = lambda x: x.type() is Item.IndividualNode

            # CONVERTERS
            c1 = lambda x: Identity.Concept if x.identity() is Identity.Individual else Identity.ValueDomain
            c2 = lambda x: Identity.Concept if x.identity() in {Identity.Role, Identity.Concept} else Identity.ValueDomain
            c3 = lambda x: Identity.RoleInstance if x.identity() is Identity.Role else Identity.AttributeInstance

            # AUXILIARY FUNCTIONS
            a1 = lambda x: x.identity() is Identity.Value

            for node in weak:

                if node.type() is Item.EnumerationNode:

                    # ENUMERATION:
                    #
                    #   - If it has INSTANCE as inputs => Identity is CONCEPT
                    #   - If it has VALUE as inputs => Identity is VALUE-DOMAIN
                    #
                    # After establishing the identity for this node, we discard all the
                    # nodes we used to compute such identity and also move the enumeration
                    # node from the WEAK set to the STRONG set, so it will contribute to the
                    # computation of the final identity for all the remaining WEAK nodes.

                    collection = node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2)
                    identities = set(map(c1, collection))
                    computed = Identity.Neutral

                    if identities:
                        computed = first(identities)
                        if len(identities) > 1:
                            computed = Identity.Unknown

                    node.setIdentity(computed)
                    if node.identity() is not Identity.Neutral:
                        strong.add(node)
                    for k in collection:
                        strong.discard(k)

                elif node.type() is Item.RangeRestrictionNode:

                    # RANGE RESTRICTION:
                    #
                    #   - If it has ATTRIBUTE as input => Identity is VALUE-DOMAIN
                    #   - If it has ROLE|CONCEPT as inputs => Identity is CONCEPT
                    #
                    # After establishing the identity for this node, we discard all the
                    # nodes we used to compute such identity and also moVe the range restriction
                    # node from the WEAK set to the STRONG set, so it will contribute to the
                    # computation of the final identity for all the remaining WEAK nodes.

                    collection = node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f4)
                    identities = set(map(c2, collection))
                    computed = Identity.Neutral

                    if identities:
                        computed = first(identities)
                        if len(identities) > 1:
                            computed = Identity.Unknown

                    node.setIdentity(computed)
                    if node.identity() is not Identity.Neutral:
                        strong.add(node)
                    for k in collection:
                        strong.discard(k)

                elif node.type() is Item.PropertyAssertionNode:

                    # PROPERTY ASSERTION:
                    #
                    #   - If it is targeting a ROLE using a Membership edge => Identity is ROLE INSTANCE
                    #   - If it is targeting an ATTRIBUTE using a Membership edge => Identity is ATTRIBUTE INSTANCE
                    #
                    #   OR
                    #
                    #   - If it has 2 INSTANCE as inputs => Identity is ROLE INSTANCE
                    #   - If it has 1 INSTANCE and 1 VALUE as inputs => Identity is ATTRIBUTE INSTANCE
                    #
                    # In both the cases, whether we establish or not an idendity for this node,
                    # we exclude it from both the WEAK and the STRONG sets. This is due to the fact
                    # that the PropertyAssertion node is used to perform assertions at ABox level
                    # while every other node in the graph is used at TBox level. Additionally we
                    # discard the inputs of the node from the STRONG set since they are either INSTANCE
                    # or VALUE nodes since they are not needed to compute the final identity for
                    # the remaining nodes in the WEAK set (see Enumeration node).

                    outgoing = node.outgoingNodes(filter_on_edges=f3, filter_on_nodes=f5)
                    incoming = node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f6)
                    computed = Identity.Neutral

                    # 1) USE MEMBERSHIP EDGE
                    identities = set(map(c3, outgoing))
                    if identities:
                        computed = first(identities)
                        if len(identities) > 1:
                            computed = Identity.Unknown

                    # 2) USE INPUT EDGES
                    if computed is Identity.Neutral and len(incoming) >= 2:
                        computed = Identity.RoleInstance
                        if sum(map(a1, incoming)):
                            computed = Identity.AttributeInstance

                    node.setIdentity(computed)
                    excluded.add(node)

                    for k in incoming:
                        strong.discard(k)

            #############################################
            # FINAL COMPUTATION
            #################################

            computed = Identity.Neutral
            identities = {x.identity() for x in strong}
            if identities:
                computed = first(identities)
                if len(identities) > 1:
                    computed = Identity.Unknown

            for node in weak - strong - excluded:
                node.setIdentity(computed)

    @QtCore.pyqtSlot('QGraphicsScene', 'QGraphicsItem')
    def onConnectionChanged(self, _, item):
        """
        Executed whenever a connection is created/removed.
        :type _: Diagram
        :type item: AbstractItem
        """
        if item.isEdge():
            for node in (item.source, item.target):
                self.sgnNodeIdentification.emit(node)

    #############################################
    #   INTERFACE
    #################################

    def addItem(self, item):
        """
        Add an item to the Diagram (will redraw the item to reflect its status).
        :type item: AbstractItem
        """
        super(Diagram, self).addItem(item)
        if item.isNode():
            item.updateNode()

    def edge(self, eid):
        """
        Returns the edge matching the given id or None if no edge is found.
        :type eid: str
        :rtype: AbstractEdge
        """
        return self.project.edge(self, eid)

    def edges(self):
        """
        Returns a collection with all the edges in the diagram.
        :rtype: set
        """
        return self.project.edges(self)

    def isEdgeAddInProgress(self):
        """
        Returns True if an edge insertion is currently in progress, False otherwise.
        :rtype: bool
        """
        return self.mode is DiagramMode.EdgeAdd and self.mp_Edge is not None

    def isLabelMoveInProgress(self):
        """
        Returns True if a label is currently being moved, False otherwise.
        :rtype: bool
        """
        return self.mode is DiagramMode.LabelMove and \
           self.mp_Label is not None and \
           self.mp_LabelPos is not None and \
           self.mp_Pos is not None

    def isNodeMoveInProgress(self):
        """
        Returns True if a node(s) is currently being moved, False otherwise.
        :rtype: bool
        """
        return self.mode is DiagramMode.NodeMove and \
           self.mp_Data is not None and \
           self.mp_Node is not None and \
           self.mp_NodePos is not None and \
           self.mp_Pos is not None

    def isEmpty(self):
        """
        Returns True if this diagram containts no element, False otherwise.
        :rtype: bool
        """
        return len(self.project.items(self)) == 0

    def itemOnTopOf(self, point, nodes=True, edges=True, labels=False, skip=None):
        """
        Returns the item which is on top of the given point.
        By default the method perform the search only on nodes and edges.
        :type point: QtCore.QPointF
        :type nodes: bool
        :type edges: bool
        :type labels: bool
        :type skip: iterable
        :rtype: AbstractItem
        """
        skip = skip or {}
        data = [x for x in self.items(point)
            if (nodes and x.isNode() or
                edges and x.isEdge() or
                labels and x.isLabel()) and x not in skip]
        if data:
            return max(data, key=lambda x: x.zValue())
        return None

    def nodes(self):
        """
        Returns a collection with all the nodes in the diagram.
        :rtype: set
        """
        return self.project.nodes(self)

    def node(self, nid):
        """
        Returns the node matching the given id or None if no node is found.
        :type nid: str
        :rtype: AbstractNode
        """
        return self.project.node(self, nid)

    def selectedEdges(self, filter_on_edges=lambda x: True):
        """
        Returns the edges selected in the diagram.
        :type filter_on_edges: callable
        :rtype: list
        """
        return [x for x in super(Diagram, self).selectedItems() if x.isEdge() and filter_on_edges(x)]

    def selectedItems(self, filter_on_items=lambda x: True):
        """
        Returns the items selected in the diagram.
        :type filter_on_items: callable
        :rtype: list
        """
        return [x for x in super(Diagram, self).selectedItems() if (x.isNode() or x.isEdge()) and filter_on_items(x)]

    def selectedNodes(self, filter_on_nodes=lambda x: True):
        """
        Returns the nodes selected in the diagram.
        :type filter_on_nodes: callable
        :rtype: list
        """
        return [x for x in super(Diagram, self).selectedItems() if x.isNode() and filter_on_nodes(x)]

    def setMode(self, mode, param=None):
        """
        Set the operational mode.
        :type mode: DiagramMode
        :type param: Item
        """
        if self.mode != mode or self.modeParam != param:
            LOGGER.debug('Diagram mode changed: mode=%s, param=%s', mode, param)
            self.mode = mode
            self.modeParam = param
            self.sgnModeChanged.emit(mode)

    def visibleRect(self, margin=0):
        """
        Returns a rectangle matching the area of visible items.
        :type margin: float
        :rtype: QtCore.QRectF
        """
        items = self.items()
        if items:
            x = set()
            y = set()
            for item in items:
                b = item.mapRectToScene(item.boundingRect())
                x.update({b.left(), b.right()})
                y.update({b.top(), b.bottom()})
            return QtCore.QRectF(QtCore.QPointF(min(x) - margin, min(y) - margin), QtCore.QPointF(max(x) + margin, max(y) + margin))
        return QtCore.QRectF()


class DiagramMalformedError(RuntimeError):
    """
    Raised whenever we encounter a problem while exporting a diagram.
    """
    def __init__(self, item, *args, **kwargs):
        """
        Initialize the exception.
        :type item: AbstractItem
        :type args: list
        :type kwargs: dict
        """
        super(DiagramMalformedError, self).__init__(*args, **kwargs)
        self.item = item


class DiagramNotFoundError(RuntimeError):
    """
    Raised whenever we are not able to find a diagram given its path.
    """
    pass


class DiagramNotValidError(RuntimeError):
    """
    Raised whenever a diagram appear to have an invalid structure.
    """
    pass


class DiagramParseError(RuntimeError):
    """
    Raised whenever it's not possible parse a Diagram out of a document.
    """
    pass
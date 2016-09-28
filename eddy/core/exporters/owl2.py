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


from jnius import autoclass, cast, detach

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from eddy import BUG_TRACKER
from eddy.core.datatypes.qt import Font
from eddy.core.datatypes.graphol import Item, Identity, Special, Restriction
from eddy.core.datatypes.owl import OWLSyntax, Datatype, Facet
from eddy.core.datatypes.system import File
from eddy.core.diagram import DiagramMalformedError
from eddy.core.exporters.common import AbstractProjectExporter
from eddy.core.functions.fsystem import fwrite
from eddy.core.functions.misc import first, clamp, isEmpty
from eddy.core.functions.misc import rstrip, postfix, format_exception
from eddy.core.functions.owl import OWLShortIRI, OWLAnnotationText
from eddy.core.functions.owl import OWLFunctionalDocumentFilter
from eddy.core.functions.path import expandPath, openPath
from eddy.core.functions.signals import connect
from eddy.core.output import getLogger

from eddy.ui.fields import ComboBox


LOGGER = getLogger(__name__)


class OWLProjectExporter(AbstractProjectExporter):
    """
    Extends AbstractProjectExporter with facilities to export a Graphol project into an OWL ontology.
    """
    def __init__(self, project, session=None):
        """
        Initialize the OWL Project exporter
        :type project: Project
        :type session: Session
        """
        super(OWLProjectExporter, self).__init__(project, session)

    #############################################
    #   INTERFACE
    #################################

    def export(self, path):
        """
        Perform OWL ontology generation.
        :type path: str
        """
        if not self.project.isEmpty():
            dialog = OWLProjectExporterDialog(self.project, path, self.session)
            dialog.exec_()

    @classmethod
    def filetype(cls):
        """
        Returns the type of the file that will be used for the export.
        :return: File
        """
        return File.Owl


class OWLProjectExporterDialog(QtWidgets.QDialog):
    """
    Extends QtWidgets.QDialog providing
    This class implements the form used to perform Graphol -> OWL ontology translation.
    """
    def __init__(self, project, path, session):
        """
        Initialize the form dialog.
        :type project: Project
        :type path: str
        :type session: Session
        """
        super(OWLProjectExporterDialog, self).__init__(session)

        self.path = expandPath(path)
        self.project = project
        self.worker = None
        self.workerThread = None

        #############################################
        # FORM AREA
        #################################

        self.syntaxField = ComboBox(self)
        for syntax in OWLSyntax:
            self.syntaxField.addItem(syntax.value, syntax)
        self.syntaxField.setCurrentIndex(0)
        self.syntaxField.setFixedWidth(300)
        self.syntaxField.setFont(Font('Roboto', 12))

        spacer = QtWidgets.QFrame()
        spacer.setFrameShape(QtWidgets.QFrame.HLine)
        spacer.setFrameShadow(QtWidgets.QFrame.Sunken)

        self.progressBar = QtWidgets.QProgressBar(self)
        self.progressBar.setAlignment(QtCore.Qt.AlignHCenter)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)

        self.formWidget = QtWidgets.QWidget(self)
        self.formLayout = QtWidgets.QFormLayout(self.formWidget)
        self.formLayout.addRow('Syntax', self.syntaxField)
        self.formLayout.addRow(spacer)
        self.formLayout.addRow(self.progressBar)

        #############################################
        # CONFIRMATION AREA
        #################################

        self.confirmationBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel, QtCore.Qt.Horizontal, self)
        self.confirmationBox.setContentsMargins(10, 0, 10, 10)
        self.confirmationBox.setFont(Font('Roboto', 12))

        #############################################
        # CONFIGURE LAYOUT
        #################################

        self.mainLayout = QtWidgets.QVBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.addWidget(self.formWidget)
        self.mainLayout.addWidget(self.confirmationBox, 0, QtCore.Qt.AlignRight)

        self.setWindowTitle('OWL Export')
        self.setWindowIcon(QtGui.QIcon(':/icons/128/ic_eddy'))
        self.setFixedSize(self.sizeHint())

        connect(self.confirmationBox.accepted, self.run)
        connect(self.confirmationBox.rejected, self.reject)

    #############################################
    #   INTERFACE
    #################################

    def syntax(self):
        """
        Returns the value of the OWL syntax field.
        :rtype: OWLSyntax
        """
        return self.syntaxField.currentData()

    #############################################
    #   PROPERTIES
    #################################

    @property
    def session(self):
        """
        Returns the active session (alias for OWLProjectExporterDialog.parent()).
        :rtype: Session
        """
        return self.parent()

    #############################################
    #   SLOTS
    #################################

    @QtCore.pyqtSlot(Exception)
    def onErrored(self, exception):
        """
        Executed whenever the translation errors.
        :type exception: Exception
        """
        self.workerThread.quit()

        if isinstance(exception, DiagramMalformedError):
            # LOG INTO CONSOLE
            LOGGER.warning('Malformed expression detected on {0}: {1} ... aborting!'.format(exception.item, exception))
            # SHOW A POPUP WITH THE WARNING MESSAGE
            msgbox = QtWidgets.QMessageBox(self)
            msgbox.setIconPixmap(QtGui.QIcon(':/icons/48/ic_warning_black').pixmap(48))
            msgbox.setInformativeText('Do you want to see the error in the diagram?')
            msgbox.setText('Malformed expression detected on {0}: {1}'.format(exception.item, exception))
            msgbox.setStandardButtons(QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No)
            msgbox.setWindowIcon(QtGui.QIcon(':/icons/128/ic_eddy'))
            msgbox.setWindowTitle('Malformed expression')
            msgbox.exec_()
            if msgbox.result() == QtWidgets.QMessageBox.Yes:
                self.session.doFocusItem(exception.item)
        else:
            # LOG INTO CONSOLE
            LOGGER.error('OWL 2 export could not be completed', exc_info=1)
            # SHOW A POPUP WITH THE ERROR MESSAGE
            msgbox = QtWidgets.QMessageBox(self)
            msgbox.setDetailedText(format_exception(exception))
            msgbox.setIconPixmap(QtGui.QIcon(':/icons/48/ic_error_outline_black').pixmap(48))
            msgbox.setInformativeText('Please <a href="{0}">submit a bug report</a>.'.format(BUG_TRACKER))
            msgbox.setStandardButtons(QtWidgets.QMessageBox.Close)
            msgbox.setText('Diagram translation could not be completed!')
            msgbox.setWindowIcon(QtGui.QIcon(':/icons/128/ic_eddy'))
            msgbox.setWindowTitle('Unhandled exception!')
            msgbox.exec_()

        self.reject()

    @QtCore.pyqtSlot()
    def onCompleted(self):
        """
        Executed whenever the translation completes.
        """
        self.workerThread.quit()

        msgbox = QtWidgets.QMessageBox(self)
        msgbox.setIconPixmap(QtGui.QIcon(':/icons/48/ic_done_black').pixmap(48))
        msgbox.setInformativeText('Do you want to open the OWL ontology?')
        msgbox.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msgbox.setText('Translation completed!')
        msgbox.setWindowIcon(QtGui.QIcon(':/icons/128/ic_eddy'))
        msgbox.exec_()
        if msgbox.result() == QtWidgets.QMessageBox.Yes:
            openPath(self.path)

        self.accept()

    @QtCore.pyqtSlot(int, int)
    def onProgress(self, current, total):
        """
        Update the progress bar showing the translation advancement.
        :type current: int
        :type total: int
        """
        self.progressBar.setRange(0, total)
        self.progressBar.setValue(current)

    @QtCore.pyqtSlot()
    def onStarted(self):
        """
        Executed whenever the translation starts.
        """
        self.confirmationBox.setEnabled(False)

    @QtCore.pyqtSlot()
    def run(self):
        """
        Perform the Graphol -> OWL translation in a separate thread.
        """
        LOGGER.info('Exporting project %s in OWL 2 format: %s', self.project.name, self.path)
        self.workerThread = QtCore.QThread()
        self.worker = OWLProjectExporterWorker(self.project, self.path, syntax=self.syntax())
        self.worker.moveToThread(self.workerThread)
        connect(self.worker.sgnStarted, self.onStarted)
        connect(self.worker.sgnCompleted, self.onCompleted)
        connect(self.worker.sgnErrored, self.onErrored)
        connect(self.worker.sgnProgress, self.onProgress)
        connect(self.workerThread.started, self.worker.run)
        self.workerThread.start()


class OWLProjectExporterWorker(QtCore.QObject):
    """
    Extends QtCore.QObject providing a worker thread that will perform the OWL 2 ontology generation.
    """
    sgnCompleted = QtCore.pyqtSignal()
    sgnErrored = QtCore.pyqtSignal(Exception)
    sgnFinished = QtCore.pyqtSignal()
    sgnProgress = QtCore.pyqtSignal(int, int)
    sgnStarted = QtCore.pyqtSignal()

    def __init__(self, project, path, **kwargs):
        """
        Initialize the OWL 2 Exporter worker.
        :type project: Project
        :type path: str
        """
        super(OWLProjectExporterWorker, self).__init__()

        self.path = path
        self.project = project
        self.syntax = kwargs.get('syntax', OWLSyntax.Functional)

        self._axioms = set()
        self._converted = dict()

        self.df = None
        self.man = None
        self.num = 0
        self.max = len(self.project.nodes()) * 2 + len(self.project.edges())
        self.ontology = None
        self.pm = None

        self.DefaultPrefixManager = autoclass('org.semanticweb.owlapi.util.DefaultPrefixManager')
        self.FunctionalSyntaxDocumentFormat = autoclass('org.semanticweb.owlapi.formats.FunctionalSyntaxDocumentFormat')
        self.HashSet = autoclass('java.util.HashSet')
        self.IRI = autoclass('org.semanticweb.owlapi.model.IRI')
        self.LinkedList = autoclass('java.util.LinkedList')
        self.List = autoclass('java.util.List')
        self.ManchesterSyntaxDocumentFormat = autoclass('org.semanticweb.owlapi.formats.ManchesterSyntaxDocumentFormat')
        self.OWLAnnotationValue = autoclass('org.semanticweb.owlapi.model.OWLAnnotationValue')
        self.OWLFacet = autoclass('org.semanticweb.owlapi.vocab.OWLFacet')
        self.OWL2Datatype = autoclass('org.semanticweb.owlapi.vocab.OWL2Datatype')
        self.OWLManager = autoclass('org.semanticweb.owlapi.apibinding.OWLManager')
        self.OWLOntologyDocumentTarget = autoclass('org.semanticweb.owlapi.io.OWLOntologyDocumentTarget')
        self.RDFXMLDocumentFormat = autoclass('org.semanticweb.owlapi.formats.RDFXMLDocumentFormat')
        self.PrefixManager = autoclass('org.semanticweb.owlapi.model.PrefixManager')
        self.Set = autoclass('java.util.Set')
        self.StringDocumentTarget = autoclass('org.semanticweb.owlapi.io.StringDocumentTarget')
        self.TurtleDocumentFormat = autoclass('org.semanticweb.owlapi.formats.TurtleDocumentFormat')

    #############################################
    #   INTERFACE
    #################################

    def addAxiom(self, axiom):
        """
        Add an axiom to the axiom set.
        :type axiom: OWLAxiom
        """
        self._axioms.add(axiom)

    def axioms(self):
        """
        Returns the set of axioms.
        :rtype: set
        """
        return self._axioms

    def convert(self, node):
        """
        Build and returns the OWL 2 conversion of the given node.
        :type node: AbstractNode
        :rtype: OWLObject
        """
        if node not in self._converted:
            if node.type() is Item.ConceptNode:
                self._converted[node] = self.getConcept(node)
            elif node.type() is Item.AttributeNode:
                self._converted[node] = self.getAttribute(node)
            elif node.type() is Item.RoleNode:
                self._converted[node] = self.getRole(node)
            elif node.type() is Item.ValueDomainNode:
                self._converted[node] = self.getValueDomain(node)
            elif node.type() is Item.IndividualNode:
                self._converted[node] = self.getIndividual(node)
            elif node.type() is Item.FacetNode:
                self._converted[node] = self.getFacet(node)
            elif node.type() is Item.RoleInverseNode:
                self._converted[node] = self.getRoleInverse(node)
            elif node.type() is Item.RoleChainNode:
                self._converted[node] = self.getRoleChain(node)
            elif node.type() is Item.ComplementNode:
                self._converted[node] = self.getComplement(node)
            elif node.type() is Item.EnumerationNode:
                self._converted[node] = self.getEnumeration(node)
            elif node.type() is Item.IntersectionNode:
                self._converted[node] = self.getIntersection(node)
            elif node.type() in {Item.UnionNode, Item.DisjointUnionNode}:
                self._converted[node] = self.getUnion(node)
            elif node.type() is Item.DatatypeRestrictionNode:
                self._converted[node] = self.getDatatypeRestriction(node)
            elif node.type() is Item.PropertyAssertionNode:
                self._converted[node] = self.getPropertyAssertion(node)
            elif node.type() is Item.DomainRestrictionNode:
                self._converted[node] = self.getDomainRestriction(node)
            elif node.type() is Item.RangeRestrictionNode:
                self._converted[node] = self.getRangeRestriction(node)
            else:
                raise ValueError('no conversion available for node %s' % node)
        return self._converted[node]

    def converted(self):
        """
        Returns the dictionary of converted nodes.
        :rtype: dict
        """
        return self._converted

    def step(self, num, increase=0):
        """
        Increments the progress by the given step and emits the progress signal.
        :type num: int
        :type increase: int
        """
        self.max += increase
        self.num += num
        self.num = clamp(self.num, minval=0, maxval=self.max)
        self.sgnProgress.emit(self.num, self.max)

    #############################################
    #   AUXILIARY METHODS
    #################################

    def getOWLApiDatatype(self, datatype):
        """
        Returns the OWLDatatype matching the given Datatype.
        :type datatype: Datatype
        :rtype: OWLDatatype
        """
        if datatype is Datatype.anyURI:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_ANY_URI').getIRI())
        if datatype is Datatype.base64Binary:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_BASE_64_BINARY').getIRI())
        if datatype is Datatype.boolean:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_BOOLEAN').getIRI())
        if datatype is Datatype.byte:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_BYTE').getIRI())
        if datatype is Datatype.dateTime:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_DATE_TIME').getIRI())
        if datatype is Datatype.dateTimeStamp:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_DATE_TIME_STAMP').getIRI())
        if datatype is Datatype.decimal:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_DECIMAL').getIRI())
        if datatype is Datatype.double:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_DOUBLE').getIRI())
        if datatype is Datatype.float:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_FLOAT').getIRI())
        if datatype is Datatype.hexBinary:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_HEX_BINARY').getIRI())
        if datatype is Datatype.int:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_INT').getIRI())
        if datatype is Datatype.integer:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_INTEGER').getIRI())
        if datatype is Datatype.language:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_LANGUAGE').getIRI())
        if datatype is Datatype.literal:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('RDFS_LITERAL').getIRI())
        if datatype is Datatype.long:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_LONG').getIRI())
        if datatype is Datatype.Name:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_NAME').getIRI())
        if datatype is Datatype.NCName:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_NCNAME').getIRI())
        if datatype is Datatype.negativeInteger:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_NEGATIVE_INTEGER').getIRI())
        if datatype is Datatype.NMTOKEN:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_NMTOKEN').getIRI())
        if datatype is Datatype.nonNegativeInteger:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_NON_NEGATIVE_INTEGER').getIRI())
        if datatype is Datatype.nonPositiveInteger:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_NON_POSITIVE_INTEGER').getIRI())
        if datatype is Datatype.normalizedString:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_NORMALIZED_STRING').getIRI())
        if datatype is Datatype.plainLiteral:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('RDF_PLAIN_LITERAL').getIRI())
        if datatype is Datatype.positiveInteger:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_POSITIVE_INTEGER').getIRI())
        if datatype is Datatype.rational:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('OWL_RATIONAL').getIRI())
        if datatype is Datatype.real:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('OWL_REAL').getIRI())
        if datatype is Datatype.short:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_SHORT').getIRI())
        if datatype is Datatype.string:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_STRING').getIRI())
        if datatype is Datatype.token:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_TOKEN').getIRI())
        if datatype is Datatype.unsignedByte:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_UNSIGNED_BYTE').getIRI())
        if datatype is Datatype.unsignedInt:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_UNSIGNED_INT').getIRI())
        if datatype is Datatype.unsignedLong:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_UNSIGNED_LONG').getIRI())
        if datatype is Datatype.unsignedShort:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('XSD_UNSIGNED_SHORT').getIRI())
        if datatype is Datatype.xmlLiteral:
            return self.df.getOWLDatatype(self.OWL2Datatype.valueOf('RDF_XML_LITERAL').getIRI())
        raise ValueError('invalid datatype supplied: %s' % datatype)

    def getOWLApiFacet(self, facet):
        """
        Returns the OWLFacet matching the given Facet.
        :type facet: Facet
        :rtype: OWLFacet
        """
        if facet is Facet.maxExclusive:
            return self.OWLFacet.valueOf('MAX_EXCLUSIVE')
        if facet is Facet.maxInclusive:
            return self.OWLFacet.valueOf('MAX_INCLUSIVE')
        if facet is Facet.minExclusive:
            return self.OWLFacet.valueOf('MIN_EXCLUSIVE')
        if facet is Facet.minInclusive:
            return self.OWLFacet.valueOf('MIN_INCLUSIVE')
        if facet is Facet.langRange:
            return self.OWLFacet.valueOf('LANG_RANGE')
        if facet is Facet.length:
            return self.OWLFacet.valueOf('LENGTH')
        if facet is Facet.maxLength:
            return self.OWLFacet.valueOf('MIN_LENGTH')
        if facet is Facet.minLength:
            return self.OWLFacet.valueOf('MIN_LENGTH')
        if facet is Facet.pattern:
            return self.OWLFacet.valueOf('PATTERN')
        raise ValueError('invalid facet supplied: %s' % facet)

    #############################################
    #   NODES PROCESSING
    #################################

    def getAttribute(self, node):
        """
        Build and returns a OWL 2 attribute using the given graphol node.
        :type node: AttributeNode
        :rtype: OWLDataProperty
        """
        if node.special() is Special.Top:
            return self.df.getOWLTopDataProperty()
        if node.special() is Special.Bottom:
            return self.df.getOWLBottomDataProperty()
        return self.df.getOWLDataProperty(OWLShortIRI(self.project.prefix, node.text()), self.pm)

    def getComplement(self, node):
        """
        Build and returns a OWL 2 complement using the given graphol node.
        :type node: ComplementNode
        :rtype: OWLClassExpression
        """
        if node.identity() is Identity.Unknown:
            raise DiagramMalformedError(node, 'unsupported operand(s)')
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.identity() in {Identity.Attribute, Identity.Concept, Identity.ValueDomain, Identity.Role}
        incoming = node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2)
        if not incoming:
            raise DiagramMalformedError(node, 'missing operand(s)')
        if len(incoming) > 1:
            raise DiagramMalformedError(node, 'too many operands')
        operand = first(incoming)
        if operand.identity() is Identity.Concept:
            return self.df.getOWLObjectComplementOf(self.convert(operand))
        if operand.identity() is Identity.ValueDomain:
            return self.df.getOWLDataComplementOf(self.convert(operand))
        if operand.identity() is Identity.Role:
            return self.convert(operand)
        if operand.identity() is Identity.Attribute:
            return self.convert(operand)
        raise DiagramMalformedError(node, 'unsupported operand (%s)' % operand)

    def getConcept(self, node):
        """
        Build and returns a OWL 2 concept using the given graphol node.
        :type node: ConceptNode
        :rtype: OWLClass
        """
        if node.special() is Special.Top:
            return self.df.getOWLThing()
        if node.special() is Special.Bottom:
            return self.df.getOWLNothing()
        return self.df.getOWLClass(OWLShortIRI(self.project.prefix, node.text()), self.pm)

    def getDatatypeRestriction(self, node):
        """
        Build and returns a OWL 2 datatype restriction using the given graphol node.
        :type node: DatatypeRestrictionNode
        :rtype: OWLDatatypeRestriction
        """
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.type() is Item.ValueDomainNode
        f3 = lambda x: x.type() is Item.FacetNode

        #############################################
        # BUILD DATATYPE
        #################################

        operand = first(node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2))
        if not operand:
            raise DiagramMalformedError(node, 'missing value domain node')

        de = self.convert(operand)

        #############################################
        # BUILD FACETS
        #################################

        incoming = node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f3)
        if not incoming:
            raise DiagramMalformedError(node, 'missing facet node(s)')

        collection = self.HashSet()
        for i in incoming:
            collection.add(self.convert(i))

        #############################################
        # BUILD DATATYPE RESTRICTION
        #################################

        return self.df.getOWLDatatypeRestriction(de, cast(self.Set, collection))

    def getDomainRestriction(self, node):
        """
        Build and returns a OWL 2 domain restriction using the given graphol node.
        :type node: DomainRestrictionNode
        :rtype: OWLClassExpression
        """
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.identity() in {Identity.Role, Identity.Attribute}
        f3 = lambda x: x.identity() is Identity.ValueDomain
        f4 = lambda x: x.identity() is Identity.Concept

        operand = first(node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2))
        if not operand:
            raise DiagramMalformedError(node, 'missing operand(s)')

        if operand.identity() is Identity.Attribute:

            #############################################
            # BUILD OPERAND
            #################################

            dpe = self.convert(operand)

            #############################################
            # BUILD FILLER
            #################################

            filler = first(node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f3))
            if not filler:
                dre = self.df.getTopDatatype()
            else:
                dre = self.convert(filler)

            if node.restriction() is Restriction.Exists:
                return self.df.getOWLDataSomeValuesFrom(dpe, dre)
            if node.restriction() is Restriction.Forall:
                return self.df.getOWLDataAllValuesFrom(dpe, dre)
            if node.restriction() is Restriction.Cardinality:
                cardinalities = self.HashSet()
                min_cardinality = node.cardinality('min')
                max_cardinality = node.cardinality('max')
                if min_cardinality is not None:
                    cardinalities.add(self.df.getOWLDataMinCardinality(min_cardinality, dpe, dre))
                if max_cardinality is not None:
                    cardinalities.add(self.df.getOWLDataMinCardinality(max_cardinality, dpe, dre))
                if cardinalities.isEmpty():
                    raise DiagramMalformedError(node, 'missing cardinality')
                if cardinalities.size() >= 1:
                    return self.df.getOWLDataIntersectionOf(cast(self.Set, cardinalities))
                return cardinalities.iterator().next()
            raise DiagramMalformedError(node, 'unsupported restriction (%s)' % node.restriction())

        elif operand.identity() is Identity.Role:

            #############################################
            # BUILD OPERAND
            #################################

            ope = self.convert(operand)

            #############################################
            # BUILD FILLER
            #################################

            filler = first(node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f4))
            if not filler:
                ce = self.df.getOWLThing()
            else:
                ce = self.convert(filler)

            if node.restriction() is Restriction.Self:
                return self.df.getOWLObjectHasSelf(ope)
            if node.restriction() is Restriction.Exists:
                return self.df.getOWLObjectSomeValuesFrom(ope, ce)
            if node.restriction() is Restriction.Forall:
                return self.df.getOWLObjectAllValuesFrom(ope, ce)
            if node.restriction() is Restriction.Cardinality:
                cardinalities = self.HashSet()
                min_cardinality = node.cardinality('min')
                max_cardinality = node.cardinality('max')
                if min_cardinality is not None:
                    cardinalities.add(self.df.getOWLObjectMinCardinality(min_cardinality, ope, ce))
                if max_cardinality is not None:
                    cardinalities.add(self.df.getOWLObjectMaxCardinality(max_cardinality, ope, ce))
                if cardinalities.isEmpty():
                    raise DiagramMalformedError(node, 'missing cardinality')
                if cardinalities.size() >= 1:
                    return self.df.getOWLObjectIntersectionOf(cast(self.Set, cardinalities))
                return cardinalities.iterator().next()
            raise DiagramMalformedError(node, 'unsupported restriction (%s)' % node.restriction())

    def getEnumeration(self, node):
        """
        Build and returns a OWL 2 enumeration using the given graphol node.
        :type node: EnumerationNode
        :rtype: OWLObjectOneOf
        """
        if node.identity() is Identity.Unknown:
            raise DiagramMalformedError(node, 'unsupported operand(s)')
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.type() is Item.IndividualNode
        individuals = self.HashSet()
        for i in node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2):
            individuals.add(self.convert(i))
        if individuals.isEmpty():
            raise DiagramMalformedError(node, 'missing operand(s)')
        return self.df.getOWLObjectOneOf(cast(self.Set, individuals))

    def getFacet(self, node):
        """
        Build and returns a OWL 2 facet restriction using the given graphol node.
        :type node: FacetNode
        :rtype: OWLFacetRestriction
        """
        datatype = node.datatype
        if not datatype:
            raise DiagramMalformedError(node, 'disconnected facet node')
        literal = self.df.getOWLLiteral(node.value, self.getOWLApiDatatype(datatype))
        facet = self.getOWLApiFacet(node.facet)
        return self.df.getOWLFacetRestriction(facet, literal)

    def getIndividual(self, node):
        """
        Build and returns a OWL 2 individual using the given graphol node.
        :type node: IndividualNode
        :rtype: OWLNamedIndividual
        """
        if node.identity() is Identity.Individual:
            return self.df.getOWLNamedIndividual(OWLShortIRI(self.project.prefix, node.text()), self.pm)
        elif node.identity() is Identity.Value:
            return self.df.getOWLLiteral(node.value, self.getOWLApiDatatype(node.datatype))
        raise DiagramMalformedError(node, 'unsupported identity (%s)' % node.identity())

    def getIntersection(self, node):
        """
        Build and returns a OWL 2 intersection using the given graphol node.
        :type node: IntersectionNode
        :rtype: T <= OWLObjectIntersectionOf|OWLDataIntersectionOf
        """
        if node.identity() is Identity.Unknown:
            raise DiagramMalformedError(node, 'unsupported operand(s)')
        collection = self.HashSet()
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.identity() is node.identity()
        for operand in node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2):
            collection.add(self.convert(operand))
        if collection.isEmpty():
            raise DiagramMalformedError(node, 'missing operand(s)')
        if node.identity() is Identity.Concept:
            return self.df.getOWLObjectIntersectionOf(cast(self.Set, collection))
        return self.df.getOWLDataIntersectionOf(cast(self.Set, collection))

    def getPropertyAssertion(self, node):
        """
        Build and returns a collection of individuals that can be used to build property assertions.
        :type node: PropertyAssertionNode
        :rtype: list
        """
        if node.identity() is Identity.Unknown:
            raise DiagramMalformedError(node, 'unsupported operand(s)')
        collection = []
        for operand in [node.diagram.edge(i).other(node) for i in node.inputs]:
            if operand.type() is not Item.IndividualNode:
                raise DiagramMalformedError(node, 'unsupported operand (%s)' % operand)
            collection.append(self.convert(operand))
        if len(collection) < 2:
            raise DiagramMalformedError(node, 'missing operand(s)')
        if len(collection) > 2:
            raise DiagramMalformedError(node, 'too many operands')
        return collection

    def getRangeRestriction(self, node):
        """
        Build and returns a OWL 2 range restriction using the given graphol node.
        :type node: DomainRestrictionNode
        :rtype: T <= OWLClassExpression|OWLDataProperty
        """
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.identity() in {Identity.Role, Identity.Attribute}
        f3 = lambda x: x.identity() is Identity.Concept

        # We discard Attribute's range restriction. The idea is that the
        # range restriction node whose input is an Attribute, can only serve
        # to compose the DataPropertyRange axiom and thus should never be
        # given in input to any other type of node, nor it should have
        # another input itself. If one of the above mentioned things happens
        # we'll see an AttributeError added in the application log which will
        # highlight an expression composition problem.

        operand = first(node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2))
        if not operand:
            raise DiagramMalformedError(node, 'missing operand(s)')

        if operand.identity() is Identity.Role:

            #############################################
            # BUILD OPERAND
            #################################

            ope = self.convert(operand).getInverseProperty()

            #############################################
            # BUILD FILLER
            #################################

            filler = first(node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f3))
            if not filler:
                ce = self.df.getOWLThing()
            else:
                ce = self.convert(filler)

            if node.restriction() is Restriction.Self:
                return self.df.getOWLObjectHasSelf(ope)
            if node.restriction() is Restriction.Exists:
                return self.df.getOWLObjectSomeValuesFrom(ope, ce)
            if node.restriction() is Restriction.Forall:
                return self.df.getOWLObjectAllValuesFrom(ope, ce)
            if node.restriction() is Restriction.Cardinality:
                cardinalities = self.HashSet()
                min_cardinality = node.cardinality('min')
                max_cardinality = node.cardinality('max')
                if min_cardinality is not None:
                    cardinalities.add(self.df.getOWLObjectMinCardinality(min_cardinality, ope, ce))
                if max_cardinality is not None:
                    cardinalities.add(self.df.getOWLObjectMaxCardinality(max_cardinality, ope, ce))
                if cardinalities.isEmpty():
                    raise DiagramMalformedError(node, 'missing cardinality')
                if cardinalities.size() >= 1:
                    return self.df.getOWLObjectIntersectionOf(cast(self.Set, cardinalities))
                return cardinalities.iterator().next()
            raise DiagramMalformedError(node, 'unsupported restriction (%s)' % node.restriction())

    def getRole(self, node):
        """
        Build and returns a OWL 2 role using the given graphol node.
        :type node: RoleNode
        :rtype: OWLObjectProperty
        """
        if node.special() is Special.Top:
            return self.df.getOWLTopObjectProperty()
        elif node.special() is Special.Bottom:
            return self.df.getOWLBottomObjectProperty()
        return self.df.getOWLObjectProperty(OWLShortIRI(self.project.prefix, node.text()), self.pm)

    def getRoleChain(self, node):
        """
        Constructs and returns LinkedList of chained OWLObjectExpression (OPE => Role & RoleInverse).
        :type node: RoleChainNode
        :rtype: List
        """
        if not node.inputs:
            raise DiagramMalformedError(node, 'missing operand(s)')
        collection = self.LinkedList()
        for operand in [node.diagram.edge(i).other(node) for i in node.inputs]:
            if operand.type() not in {Item.RoleNode, Item.RoleInverseNode}:
                raise DiagramMalformedError(node, 'unsupported operand (%s)' % operand)
            collection.add(self.convert(operand))
        if collection.isEmpty():
            raise DiagramMalformedError(node, 'missing operand(s)')
        return cast(self.List, collection)

    def getRoleInverse(self, node):
        """
        Build and returns a OWL 2 role inverse using the given graphol node.
        :type node: RoleInverseNode
        :rtype: OWLObjectPropertyExpression
        """
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.type() is Item.RoleNode
        operand = first(node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2))
        if not operand:
            raise DiagramMalformedError(node, 'missing operand(s)')
        return self.convert(operand).getInverseProperty()

    def getUnion(self, node):
        """
        Build and returns a OWL 2 union using the given graphol node.
        :type node: UnionNode
        :rtype: T <= OWLObjectUnionOf|OWLDataUnionOf
        """
        if node.identity() is Identity.Unknown:
            raise DiagramMalformedError(node, 'unsupported operand(s)')
        collection = self.HashSet()
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.identity() is node.identity()
        for operand in node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2):
            collection.add(self.convert(operand))
        if collection.isEmpty():
            raise DiagramMalformedError(node, 'missing operand(s)')
        if node.identity() is Identity.Concept:
            return self.df.getOWLObjectUnionOf(cast(self.Set, collection))
        return self.df.getOWLDataUnionOf(cast(self.Set, collection))

    def getValueDomain(self, node):
        """
        Build and returns a OWL 2 datatype using the given graphol node.
        :type node: ValueDomainNode
        :rtype: OWLDatatype
        """
        return self.getOWLApiDatatype(node.datatype)

    #############################################
    #   AXIOMS GENERATION
    #################################

    def createAnnotationAssertionAxiom(self, node):
        """
        Generate a OWL 2 annotation axiom.
        :type node: AbstractNode
        """
        meta = self.project.meta(node.type(), node.text())
        if meta and not isEmpty(meta['description']):
            props = self.df.getOWLAnnotationProperty(self.IRI.create("Description"))
            value = self.df.getOWLLiteral(OWLAnnotationText(meta['description']))
            value = cast(self.OWLAnnotationValue, value)
            annotation = self.df.getOWLAnnotation(props, value)
            self.addAxiom(self.df.getOWLAnnotationAssertionAxiom(self.convert(node).getIRI(), annotation))

    def createClassAssertionAxiom(self, edge):
        """
        Generate a OWL 2 ClassAssertion axiom.
        :type edge: MembershipEdge
        """
        self.addAxiom(self.df.getOWLClassAssertionAxiom(self.convert(edge.target), self.convert(edge.source)))

    def createDataPropertyAssertionAxiom(self, edge):
        """
        Generate a OWL 2 DataPropertyAssertion axiom.
        :type edge: MembershipEdge
        """
        operand1 = self.convert(edge.source)[0]
        operand2 = self.convert(edge.source)[1]
        self.addAxiom(self.df.getOWLDataPropertyAssertionAxiom(self.convert(edge.target), operand1, operand2))

    def createDataPropertyAxiom(self, node):
        """
        Generate OWL 2 Data Property specific axioms.
        :type node: AttributeNode
        """
        if node.isFunctional():
            self.addAxiom(self.df.getOWLFunctionalDataPropertyAxiom(self.convert(node)))

    def createDeclarationAxiom(self, node):
        """
        Generate a OWL 2 Declaration axiom.
        :type node: AbstractNode
        """
        self.addAxiom(self.df.getOWLDeclarationAxiom(self.convert(node)))

    def createDisjointClassesAxiom(self, node):
        """
        Generate a OWL 2 DisjointClasses axiom.
        :type node: DisjointUnionNode
        """
        collection = self.HashSet()
        for operand in node.incomingNodes(lambda x: x.type() is Item.InputEdge):
            collection.add(self.convert(operand))
        self.addAxiom(self.df.getOWLDisjointClassesAxiom(cast(self.Set, collection)))

    def createDisjointDataPropertiesAxiom(self, edge):
        """
        Generate a OWL 2 DisjointDataProperties axiom.
        :type edge: InclusionEdge
        """
        collection = self.HashSet()
        collection.add(self.convert(edge.source))
        collection.add(self.convert(edge.target))
        self.addAxiom(self.df.getOWLDisjointDataPropertiesAxiom(cast(self.Set, collection)))

    def createDisjointObjectPropertiesAxiom(self, edge):
        """
        Generate a OWL 2 DisjointObjectProperties axiom.
        :type edge: InclusionEdge
        """
        collection = self.HashSet()
        collection.add(self.convert(edge.source))
        collection.add(self.convert(edge.target))
        self.addAxiom(self.df.getOWLDisjointObjectPropertiesAxiom(cast(self.Set, collection)))

    def createEquivalentClassesAxiom(self, edge):
        """
        Generate a OWL 2 EquivalentClasses axiom.
        :type edge: InclusionEdge
        """
        collection = self.HashSet()
        collection.add(self.convert(edge.source))
        collection.add(self.convert(edge.target))
        self.addAxiom(self.df.getOWLEquivalentClassesAxiom(cast(self.Set, collection)))

    def createEquivalentDataPropertiesAxiom(self, edge):
        """
        Generate a OWL 2 EquivalentDataProperties axiom.
        :type edge: InclusionEdge
        """
        collection = self.HashSet()
        collection.add(self.convert(edge.source))
        collection.add(self.convert(edge.target))
        self.addAxiom(self.df.getOWLEquivalentDataPropertiesAxiom(cast(self.Set, collection)))

    def createEquivalentObjectPropertiesAxiom(self, edge):
        """
        Generate a OWL 2 EquivalentObjectProperties axiom.
        :type edge: InclusionEdge
        """
        collection = self.HashSet()
        collection.add(self.convert(edge.source))
        collection.add(self.convert(edge.target))
        collection = cast(self.Set, collection)
        self.addAxiom(self.df.getOWLEquivalentObjectPropertiesAxiom(collection))

    def createObjectPropertyAxiom(self, node):
        """
        Generate OWL 2 ObjectProperty specific axioms.
        :type node: RoleNode
        """
        if node.isFunctional():
            self.addAxiom(self.df.getOWLFunctionalObjectPropertyAxiom(self.convert(node)))
        if node.isInverseFunctional():
            self.addAxiom(self.df.getOWLInverseFunctionalObjectPropertyAxiom(self.convert(node)))
        if node.isAsymmetric():
            self.addAxiom(self.df.getOWLAsymmetricObjectPropertyAxiom(self.convert(node)))
        if node.isIrreflexive():
            self.addAxiom(self.df.getOWLIrreflexiveObjectPropertyAxiom(self.convert(node)))
        if node.isReflexive():
            self.addAxiom(self.df.getOWLReflexiveObjectPropertyAxiom(self.convert(node)))
        if node.isSymmetric():
            self.addAxiom(self.df.getOWLSymmetricObjectPropertyAxiom(self.convert(node)))
        if node.isTransitive():
            self.addAxiom(self.df.getOWLTransitiveObjectPropertyAxiom(self.convert(node)))

    def createObjectPropertyAssertionAxiom(self, edge):
        """
        Generate a OWL 2 ObjectPropertyAssertion axiom.
        :type edge: MembershipEdge
        """
        operand1 = self.convert(edge.source)[0]
        operand2 = self.convert(edge.source)[1]
        self.addAxiom(self.df.getOWLObjectPropertyAssertionAxiom(self.convert(edge.target), operand1, operand2))

    def createPropertyDomainAxiom(self, node):
        """
        Generate OWL 2 ObjectPropertyDomain and DataPropertyDomain axioms.
        :type node: DomainRestrictionNode
        """
        # ObjectPropertyDomain
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.identity() is Identity.Role
        role = first(node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2))
        if role:
            f3 = lambda x: x.type() in {Item.InclusionEdge, Item.EquivalenceEdge}
            f4 = lambda x: x.identity() is Identity.Concept
            for concept in node.outgoingNodes(filter_on_edges=f3, filter_on_nodes=f4):
                self.addAxiom(self.df.getOWLObjectPropertyDomainAxiom(self.convert(role), self.convert(concept)))
        # DataPropertyDomain
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.identity() is Identity.Attribute
        attribute = first(node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2))
        if attribute:
            f3 = lambda x: x.type() in {Item.InclusionEdge, Item.EquivalenceEdge}
            f4 = lambda x: x.identity() is Identity.Concept
            for concept in node.outgoingNodes(filter_on_edges=f3, filter_on_nodes=f4):
                self.addAxiom(self.df.getOWLDataPropertyDomainAxiom(self.convert(attribute), self.convert(concept)))

    def createPropertyRangeAxiom(self, node):
        """
        Generate OWL 2 ObjectPropertyRange and DataPropertyRange axioms.
        :type node: RangeRestrictionNode
        """
        # ObjectPropertyRnge
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.identity() is Identity.Role
        role = first(node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2))
        if role:
            f3 = lambda x: x.type() in {Item.InclusionEdge, Item.EquivalenceEdge}
            f4 = lambda x: x.identity() is Identity.Concept
            for concept in node.outgoingNodes(filter_on_edges=f3, filter_on_nodes=f4):
                self.addAxiom(self.df.getOWLObjectPropertyRangeAxiom(self.convert(role), self.convert(concept)))
        # DataPropertyRangeAxiom
        f1 = lambda x: x.type() is Item.InputEdge
        f2 = lambda x: x.identity() is Identity.Attribute
        attribute = first(node.incomingNodes(filter_on_edges=f1, filter_on_nodes=f2))
        if attribute:
            f3 = lambda x: x.type() in {Item.InclusionEdge, Item.EquivalenceEdge}
            f4 = lambda x: x.identity() is Identity.ValueDomain
            for concept in node.outgoingNodes(filter_on_edges=f3, filter_on_nodes=f4):
                self.addAxiom(self.df.getOWLDataPropertyRangeAxiom(self.convert(attribute), self.convert(concept)))

    def createSubclassOfAxiom(self, edge):
        """
        Generate a OWL 2 SubclassOf axiom.
        :type edge: InclusionEdge
        """
        self.addAxiom(self.df.getOWLSubClassOfAxiom(self.convert(edge.source), self.convert(edge.target)))

    def createSubDataPropertyOfAxiom(self, edge):
        """
        Generate a OWL 2 SubDataPropertyOf axiom.
        :type edge: InclusionEdge
        """
        self.addAxiom(self.df.getOWLSubDataPropertyOfAxiom(self.convert(edge.source), self.convert(edge.target)))

    def createSubObjectPropertyOfAxiom(self, edge):
        """
        Generate a OWL 2 SubObjectPropertyOf axiom.
        :type edge: InclusionEdge
        """
        self.addAxiom(self.df.getOWLSubObjectPropertyOfAxiom(self.convert(edge.source), self.convert(edge.target)))

    def createSubPropertyChainOfAxiom(self, edge):
        """
        Generate a OWL 2 SubPropertyChainOf axiom.
        :type edge: InclusionEdge
        """
        self.addAxiom(self.df.getOWLSubPropertyChainOfAxiom(self.convert(edge.source), self.convert(edge.target)))

    #############################################
    #   MAIN WORKER
    #################################

    @QtCore.pyqtSlot()
    def run(self):
        """
        Main worker.
        """
        try:

            self.sgnStarted.emit()

            #############################################
            # INITIALIZE ONTOLOGY
            #################################

            self.man = self.OWLManager.createOWLOntologyManager()
            self.df = self.man.getOWLDataFactory()
            self.ontology = self.man.createOntology(self.IRI.create(rstrip(self.project.iri, '#')))
            self.pm = self.DefaultPrefixManager()
            self.pm.setPrefix(self.project.prefix, postfix(self.project.iri, '#'))

            cast(self.PrefixManager, self.pm)

            LOGGER.debug('Initialized OWL 2 Ontology: %s', rstrip(self.project.iri, '#'))

            #############################################
            # NODES PRE-PROCESSING
            #################################

            for node in self.project.nodes():
                self.convert(node)
                self.step(+1)

            LOGGER.debug('Pre-processed %s nodes into OWL 2 expressions', len(self.converted()))

            #############################################
            # AXIOMS FROM NODES
            #################################

            for node in self.project.nodes():

                if node.type() in {Item.ConceptNode, Item.AttributeNode, Item.RoleNode, Item.ValueDomainNode}:
                    self.createDeclarationAxiom(node)
                    if node.type() is Item.AttributeNode:
                        self.createDataPropertyAxiom(node)
                    elif node.type() is Item.RoleNode:
                        self.createObjectPropertyAxiom(node)
                elif node.type() is Item.DisjointUnionNode:
                    self.createDisjointClassesAxiom(node)
                elif node.type() is Item.DomainRestrictionNode:
                    self.createPropertyDomainAxiom(node)
                elif node.type() is Item.RangeRestrictionNode:
                    self.createPropertyRangeAxiom(node)

                if node.isPredicate():
                    self.createAnnotationAssertionAxiom(node)

                self.step(+1)

            LOGGER.debug('Generated OWL 2 axioms from nodes (axioms = %s)', len(self.axioms()))

            #############################################
            # AXIOMS FROM EDGES
            #################################

            for edge in self.project.edges():

                if edge.type() is Item.InclusionEdge:

                    # CONCEPTS
                    if edge.source.identity() is Identity.Concept and edge.target.identity() is Identity.Concept:
                        self.createSubclassOfAxiom(edge)
                    # ROLES
                    elif edge.source.identity() is Identity.Role and edge.target.identity() is Identity.Role:
                        if edge.source.type() is Item.RoleChainNode:
                            self.createSubPropertyChainOfAxiom(edge)
                        elif edge.source.type() in {Item.RoleNode, Item.RoleInverseNode}:
                            if edge.target.type() is Item.ComplementNode:
                                self.createDisjointObjectPropertiesAxiom(edge)
                            elif edge.target.type() in {Item.RoleNode, Item.RoleInverseNode}:
                                self.createSubObjectPropertyOfAxiom(edge)
                    # ATTRIBUTES
                    elif edge.source.identity() is Identity.Attribute and edge.target.identity() is Identity.Attribute:
                        if edge.source.type() is Item.AttributeNode:
                            if edge.target.type() is Item.ComplementNode:
                                self.createDisjointDataPropertiesAxiom(edge)
                            elif edge.target.type() is Item.AttributeNode:
                                self.createSubDataPropertyOfAxiom(edge)
                    # VALUE DOMAIN (ONLY DATA PROPERTY RANGE)
                    elif edge.source.type() is Item.RangeRestrictionNode and edge.target.identity() is Identity.ValueDomain:
                        # This is being handled already in createPropertyRangeAxiom.
                        pass
                    else:
                        raise DiagramMalformedError(edge, 'invalid inclusion assertion')

                elif edge.type() is Item.EquivalenceEdge:

                    # CONCEPTS
                    if edge.source.identity() is Identity.Concept and edge.target.identity() is Identity.Concept:
                        self.createEquivalentClassesAxiom(edge)
                    # ROLES
                    elif edge.source.identity() is Identity.Role and edge.target.identity() is Identity.Role:
                        self.createEquivalentObjectPropertiesAxiom(edge)
                    # ATTRIBUTES
                    elif edge.source.identity() is Identity.Attribute and edge.target.identity() is Identity.Attribute:
                        self.createEquivalentDataPropertiesAxiom(edge)
                    else:
                        raise DiagramMalformedError(edge, 'invalid equivalence assertion')

                elif edge.type() is Item.MembershipEdge:

                    # CONCEPTS
                    if edge.source.identity() is Identity.Individual and edge.target.identity() is Identity.Concept:
                        self.createClassAssertionAxiom(edge)
                    # ROLES
                    elif edge.source.identity() is Identity.RoleInstance:
                        self.createObjectPropertyAssertionAxiom(edge)
                    # ATTRIBUTES
                    elif edge.source.identity() is Identity.AttributeInstance:
                        self.createDataPropertyAssertionAxiom(edge)
                    else:
                        raise DiagramMalformedError(edge, 'invalid membership assertion')

                self.step(+1)

            LOGGER.debug('Generated OWL 2 axioms from edges (axioms = %s)', len(self.axioms()))

            #############################################
            # APPLY GENERATED AXIOMS
            #################################

            LOGGER.debug('Applying OWL 2 axioms on the OWL 2 Ontology')

            for axiom in self.axioms():
                self.man.addAxiom(self.ontology, axiom)

            #############################################
            # SERIALIZE THE ONTOLOGY
            #################################

            if self.syntax is OWLSyntax.Functional:
                DocumentFormat = self.FunctionalSyntaxDocumentFormat
                DocumentFilter = OWLFunctionalDocumentFilter
            elif self.syntax is OWLSyntax.Manchester:
                DocumentFormat = self.ManchesterSyntaxDocumentFormat
                DocumentFilter = lambda x: x
            elif self.syntax is OWLSyntax.RDF:
                DocumentFormat = self.RDFXMLDocumentFormat
                DocumentFilter = lambda x: x
            elif self.syntax is OWLSyntax.Turtle:
                DocumentFormat = self.TurtleDocumentFormat
                DocumentFilter = lambda x: x
            else:
                raise TypeError('unsupported syntax (%s)' % self.syntax)

            LOGGER.debug('Serializing the OWL 2 Ontology in %s', self.syntax.value)

            # COPY PREFIXES
            ontoFormat = DocumentFormat()
            ontoFormat.copyPrefixesFrom(self.pm)
            # CREARE TARGET STREAM
            stream = self.StringDocumentTarget()
            stream = cast(self.OWLOntologyDocumentTarget, stream)
            # SAVE THE ONTOLOGY TO DISK
            self.man.setOntologyFormat(self.ontology, ontoFormat)
            self.man.saveOntology(self.ontology, stream)
            stream = cast(self.StringDocumentTarget, stream)
            string = DocumentFilter(stream.toString())
            fwrite(string, self.path)

        except Exception as e:
            self.sgnErrored.emit(e)
            LOGGER.exception(e)
        else:
            self.sgnCompleted.emit()
        finally:
            detach()
            self.sgnFinished.emit()
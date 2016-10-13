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


import csv
import io

from operator import itemgetter

from eddy.core.datatypes.collections import DistinctList
from eddy.core.datatypes.graphol import Item
from eddy.core.datatypes.system import File
from eddy.core.exporters.common import AbstractProjectExporter
from eddy.core.functions.misc import lstrip
from eddy.core.functions.fsystem import fwrite
from eddy.core.functions.owl import OWLShortIRI
from eddy.core.functions.path import openPath
from eddy.core.output import getLogger
from eddy.core.plugin import AbstractPlugin


LOGGER = getLogger(__name__)


class CsvExporterPlugin(AbstractPlugin):
    """
    Extends AbstractPlugin providing a Csv file format project exporter.
    """
    #############################################
    #   HOOKS
    #################################

    def dispose(self):
        """
        Executed whenever the plugin is going to be destroyed.
        """
        # UNINSTALL THE EXPORTER
        self.debug('Uninstalling CSV file format exporter')
        self.session.removeProjectExporter(CsvExporter)

    def start(self):
        """
        Perform initialization tasks for the plugin.
        """
        # INSTALL THE EXPORTER
        self.debug('Installing CSV file format exporter')
        self.session.addProjectExporter(CsvExporter)


class CsvExporter(AbstractProjectExporter):
    """
    This class can be used to export Graphol projects into CSV format.
    """
    KeyName = 'NAME'
    KeyType = 'TYPE'
    KeyDescription = 'DESCRIPTION'
    KeyDiagrams = 'DIAGRAMS'
    Types = [
        Item.AttributeNode,
        Item.ConceptNode,
        Item.RoleNode,
    ]

    def __init__(self, project, session=None):
        """
        Initialize the CSV exporter.
        :type project: Project
        :type session: Session
        """
        super(CsvExporter, self).__init__(project, session)

    #############################################
    #   INTERFACE
    #################################

    def export(self, path):
        """
        Perform CSV file generation.
        :type path: str
        """
        LOGGER.info('Exporting project %s in CSV format: %s', self.project.name, path)
        collection = {x: {} for x in self.Types}

        for node in self.project.predicates():
            if node.type() in collection:
                # If there is no data for this predicate node, create a new entry.
                if not node.text() in collection[node.type()]:
                    meta = self.project.meta(node.type(), node.text())
                    collection[node.type()][node.text()] = {
                        CsvExporter.KeyName: lstrip(OWLShortIRI('', node.text()), ':'),
                        CsvExporter.KeyType: node.shortName,
                        CsvExporter.KeyDescription: meta.get('description', ''),
                        CsvExporter.KeyDiagrams: DistinctList()}
                # Append the name of the diagram to the diagram list.
                collection[node.type()][node.text()][self.KeyDiagrams] += [node.diagram.name]

        # Collect data in a buffer.
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow((self.KeyName, self.KeyType, self.KeyDescription, self.KeyDiagrams))
        for i, j in sorted(((v, k) for k in collection for v in collection[k]), key=itemgetter(0)):
            writer.writerow((
                collection[j][i][self.KeyName],
                collection[j][i][self.KeyType],
                collection[j][i][self.KeyDescription],
                sorted(collection[j][i][self.KeyDiagrams]),
            ))

        # Write to disk.
        fwrite(buffer.getvalue(), path)

        # Open the document.
        openPath(path)

    @classmethod
    def filetype(cls):
        """
        Returns the type of the file that will be used for the export.
        :return: File
        """
        return File.Csv
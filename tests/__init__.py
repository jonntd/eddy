# -*- coding: utf-8 -*-

##########################################################################
#                                                                        #
#  Eddy: an editor for the Graphol ontology language.                    #
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
#  Dipartimento di Ingegneria Informatica, Automatica e Gestionale       #
#  A.Ruberti at Sapienza University of Rome: http://www.dis.uniroma1.it/ #
#                                                                        #
#     - Domenico Lembo <lembo@dis.uniroma1.it>                           #
#     - Valerio Santarelli <santarelli@dis.uniroma1.it>                  #
#     - Domenico Fabio Savo <savo@dis.uniroma1.it>                       #
#     - Marco Console <console@dis.uniroma1.it>                          #
#                                                                        #
##########################################################################


import sys
import unittest

from unittest.util import safe_repr
from PyQt5.QtTest import QTest

from eddy import Eddy


# noinspection PyTypeChecker,PyCallByClass
class EddyTestCase(unittest.TestCase):

    def setUp(self):
        """
        Initialize test case environment.
        """
        self.app = Eddy(sys.argv)
        self.mainwindow = self.app.init()
        self.mainwindow.show()
        self.mainwindow.activateWindow()
        QTest.qWaitForWindowActive(self.mainwindow)

    def tearDown(self):
        """
        Perform operation on test end.
        """
        self.app.quit()

    ############################################## CUSTOM ASSERTIONS ###################################################

    def assertDictHasKey(self, key, container, msg=None):
        """Check for a given key to be in the given dictionary."""
        if key not in container.keys():
            standardMsg = '%s not found in %s' % (safe_repr(key), safe_repr(container))
            self.fail(self._formatMessage(msg, standardMsg))

    def assertDictHasValue(self, value, container, msg=None):
        """Check for a given value to be in the given dictionary."""
        if value not in container.value():
            standardMsg = '%s not found in %s' % (safe_repr(value), safe_repr(container))
            self.fail(self._formatMessage(msg, standardMsg))

    def assertEmpty(self, container, msg=None):
        """Assert for a given container to be empty."""
        if len(container) != 0:
            standardMsg = '%s is not empty: found %s elements' % (safe_repr(container), len(container))
            self.fail(self._formatMessage(msg, standardMsg))

    def assertLen(self, count, container, msg=None):
        """Check for a given container to have the specified length."""
        if len(container) != count:
            standardMsg = 'found %s elements in %s: expecting %s' % (len(container), safe_repr(container), count)
            self.fail(self._formatMessage(msg, standardMsg))

    def assertNotEmpty(self, container, msg=None):
        """Assert for a given container to be empty."""
        if len(container) == 0:
            standardMsg = '%s unexpectedly empty: found %s elements' % (safe_repr(container), len(container))
            self.fail(self._formatMessage(msg, standardMsg))
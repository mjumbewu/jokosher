#!/usr/bin/env python

import sys, os
basedir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(basedir)

from tests import TemplateTest
import unittest

suite = unittest.TestSuite()
testList = [
	TemplateTest.TestCase,
]

for i in testList:
	suite.addTest(unittest.TestLoader().loadTestsFromTestCase(i))

unittest.TextTestRunner(verbosity=0).run(suite)


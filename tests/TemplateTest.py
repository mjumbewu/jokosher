#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL.
#	SEE THE 'COPYING' FILE FOR DETAILS
#
#	TemplateTest.py

import unittest
from Jokosher.Project import Project 

class TestCase(unittest.TestCase):
	
	def setUp(self):
		pass

	def testTemplate(self):
		try:
			Project()
		except Exception, e:
			self.fail(repr(e))

	def tearDown(self):
		pass


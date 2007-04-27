#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	ProjectTemplate.py
#	
#	This module handles the saving and loading of project templates.
#	
#
#-------------------------------------------------------------------------------

import os
import Globals
import xml.dom.minidom as xml
from Utils import LoadListFromXML, StoreListToXML
from Monitored import Monitored

#=========================================================================

class ProjectTemplate(Monitored):
	"""
	This class saves and loads templates and template information to disk.
	"""

	#_____________________________________________________________________

	def __init__(self):
		""" 
		Creates a new instance of ProjectTemplate.
		"""
		Monitored.__init__(self)

	#_____________________________________________________________________

	def SaveTemplateFile(self, name, instrlist):
		""" 
		This method will write a template file to ~/.jokosher/templates/.
		instrlist is a list containing a list of instruments e.g. [["audiofile", "Audio File", "path_to_image"], 
		["acousticguitar", "Acoustic Guitar", "path_to_image"]].
	
		Parameters:
			name -- the name of the template file.
			instrlist -- a list containing a list of instruments
		"""
		doc = xml.Document()
		head = doc.createElement("template")
		doc.appendChild(head)
		
		for items in instrlist:
			# create instrument tags for every instrument in the list
			instrtag = doc.createElement("instrument")
			head.appendChild(instrtag)
			StoreListToXML(doc, instrtag, items, "item")
		
		if not name.endswith(".template"):
			name += ".template"

		try:
			try:
				filename = open(Globals.TEMPLATES_PATH + name, "w")
				filename.write(doc.toprettyxml())
			except IOError, e:
				Globals.debug("The template %s%s does not exist" % (Globals.TEMPLATES_PATH, name))
		finally:
			filename.close()
			
		self.StateChanged("template-update")

	#_____________________________________________________________________
	
	def DeleteTemplateFile(self, name):
		"""
		This method will delete a template file.
		
		Parameters:
			name -- the name of the template file which will be deleted.
		"""
		if not name.endswith(".template"):
			name += ".template"
		
		try:
			os.remove(Globals.TEMPLATES_PATH + name)
		except OSError, e:
			Globals.debug("Cannot remove template %s%s" % (Globals.TEMPLATES_PATH, name))
			
		self.StateChanged("template-update")

	#_____________________________________________________________________
	
	def __LoadInstrumentsFromTemplateFile(self, name):
		"""
		This method will return a list containing a list of instruments which are in the given template filename.
		
		Parameters:
			name -- the name of the template.
			
		Returns:
			instrlist -- a list containing a list of instruments, e.g. [["audiofile", "Audio File", "path_to_image"]].
		"""
		if not name.endswith(".template"):
			name += ".template"
		
		if os.path.exists(Globals.TEMPLATES_PATH + name):
			filename = open(Globals.TEMPLATES_PATH + name, "r")
			doc = xml.parse(filename)
			instrlist = []
			for item in doc.getElementsByTagName("instrument"):
				instrlist.append(LoadListFromXML(item))
			return instrlist
		else:
			Globals.debug("The template %s%s does not exist" % (Globals.TEMPLATES_PATH, name))
	
	#_____________________________________________________________________
	
	def __GetTemplateList(self):
		"""
		This method will return a list of template files in the template directory (~/.jokosher/templates/")
		
		Returns:
			filenames -- a list containing the names of file in the template directory.
		"""
		templist = []
		for files in os.listdir(Globals.TEMPLATES_PATH):
			filenames = files.split(".")[0]
			templist.append(filenames)
		return templist

	#_____________________________________________________________________

	def LoadDictionaryOfInstrumentsFromTemplateFile(self):
		"""
		This method will return a dictionary containing the the template file name (key) and their
		associated instruments (value).
		e.g. {"Rock" : [["electricguitar", "Electric Guitar", "path_to_image"]]}
		"""
		instrdict = {}
		for i in self.__GetTemplateList():
			instrdict[i] = self.__LoadInstrumentsFromTemplateFile(i)
		return instrdict
	
#=========================================================================	

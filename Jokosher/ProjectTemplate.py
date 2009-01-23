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
import gobject
import Globals
import xml.dom.minidom as xml
from Utils import LoadListFromXML, StoreListToXML

#=========================================================================

class ProjectTemplate(gobject.GObject):
	"""
	This class saves and loads templates and template information to disk.
	"""

	#the extension put on the end of template files
	TEMPLATE_EXT = "template"
	
	"""
	Signals:
		"template-update" -- This template has changed.
	"""
	
	__gsignals__ = {
		"template-update" : ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () )
	}
	
	#_____________________________________________________________________

	def __init__(self):
		""" 
		Creates a new instance of ProjectTemplate.
		"""
		gobject.GObject.__init__(self)

	#_____________________________________________________________________

	def SaveTemplateFile(self, name, instrlist):
		""" 
		This method will write a template file to JOKOSHER_DATA_HOME/templates/.
		instrlist is a list containing type strings corresponding to each instrument.
		e.g. ["audiofile", "acousticguitar"].
	
		Parameters:
			name -- the name of the template file.
			instrlist -- a list containing the instrument type strings
		"""
		doc = xml.Document()
		head = doc.createElement("JokosherProjectTemplate")
		doc.appendChild(head)
		
		for typeString in instrlist:
			# create instrument tags for every instrument in the list
			instrtag = doc.createElement("Instrument")
			instrtag.setAttribute("type", typeString)
			head.appendChild(instrtag)
		
		if not name.endswith("." + self.TEMPLATE_EXT):
			name += "." + self.TEMPLATE_EXT
		namePath = os.path.join(Globals.TEMPLATES_PATH, name)
		try:
			try:
				filename = open(namePath, "w")
				filename.write(doc.toprettyxml())
			except IOError, e:
				Globals.debug("The template %s does not exist" % namePath)
		finally:
			filename.close()
			
		self.emit("template-update")

	#_____________________________________________________________________
	
	def DeleteTemplateFile(self, name):
		"""
		This method will delete a template file.
		
		Parameters:
			name -- the name of the template file which will be deleted.
		"""
		if not name.endswith("." + self.TEMPLATE_EXT):
			name += "." + self.TEMPLATE_EXT
		namePath = os.path.join(Globals.TEMPLATES_PATH, name)
		try:
			os.remove(namePath)
		except OSError, e:
			Globals.debug("Cannot remove template %s" % namePath)
			
		self.emit("template-update")

	#_____________________________________________________________________
	
	def __LoadInstrumentsFromTemplateFile(self, name):
		"""
		This method will return a list containing a list of instruments which are in the given template filename.
		
		Parameters:
			name -- the name of the template.
			
		Returns:
			instrlist -- a list containing a list of instruments, e.g. [["audiofile", "Audio File", "path_to_image"]].
		"""
		if not name.endswith("." + self.TEMPLATE_EXT):
			name += "." + self.TEMPLATE_EXT
		namePath = os.path.join(Globals.TEMPLATES_PATH, name)
		if os.path.exists(namePath):
			file = open(namePath, "r")
			doc = xml.parse(file)
			instrlist = []
			for node in doc.getElementsByTagName("Instrument"):
				typeString = str(node.getAttribute("type"))
				instrlist.append(typeString)
			return instrlist
		else:
			Globals.debug("The template %s does not exist" % namePath)
	
	#_____________________________________________________________________
	
	def __GetTemplateList(self):
		"""
		This method will return a list of template files in the template directory (JOKOSHER_DATA_HOME/templates/")
		
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
		This method will return a dictionary containing the the template file name (key) and a list
		of the associated instrument tupels.
		e.g. {"Rock" : [ ("electricguitar", "Electric Guitar", pixbufImage) ]}
		"""
		instrdict = {}
		cached = Globals.getCachedInstruments()
		for filename in self.__GetTemplateList():
			instrTuples = []
			typeStringList = self.__LoadInstrumentsFromTemplateFile(filename)
			for type in typeStringList:
				tuple_ = [x for x in cached if x[1] == type]
				if tuple_:
					name, type, pixbuf, path = tuple_[0]
					instrTuples.append( (name, type, pixbuf) )
					
			instrdict[filename] = instrTuples
		
		return instrdict
	
#=========================================================================	

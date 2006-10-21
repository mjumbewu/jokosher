#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	ExtensionManager.py
#	
#	This module defines the ExtensionManager class which is 
#	responsible for controlling extensions to Jokosher
#
#-------------------------------------------------------------------------------
import Globals
import Extension
import pkg_resources
import os.path
import imp
import gtk

#=========================================================================

class ExtensionManager:
	"""
		The ExtensionManager class handles installation and running of
		extensions. It also controls their disabling and removal.
	"""
	#_____________________________________________________________________
	
	def __init__(self, mainapp):
		self.mainapp = mainapp
		self.loadedExtensions = []
		self.API = Extension.ExtensionAPI(mainapp)
		self.LoadAllExtensions()
	#_____________________________________________________________________
	
	def register(self, extension, filename, directory):
		"""
			Called from Extension.LoadAllExtensions afer the extensions
			module has been imported (and the class instantiated in the case
			of extensions that are oggs). 
			
			extension = a reference to the extension (either a module 
				or in the case of an extension imported 
				from an egg, an instance object.
		"""
		messages = []
		passed = True
		name = None
		# check if the necessary attributes EXTENSION_NAME, EXTENSION_VERSION
		#	and EXTENSION_DESCRIPTION are present and
		#	refuse to start the extension if they are missing. 
		if hasattr(extension,"EXTENSION_NAME"):
			name = extension.EXTENSION_NAME
		else:
			Globals.debug(filename + " missing EXTENSION NAME")
			messages.append(filename + " missing EXTENSION NAME")
			passed = False
		if hasattr(extension,"EXTENSION_VERSION"):
			version = extension.EXTENSION_VERSION
		else:
			Globals.debug(filename + " missing EXTENSION_VERSION")
			messages.append(filename + " missing EXTENSION_VERSION")
			passed = False
		if hasattr(extension,"EXTENSION_DESCRIPTION"):
			description = extension.EXTENSION_DESCRIPTION
		else:
			Globals.debug(filename + " missing EXTENSION_DESCRIPTION")
			messages.append(filename + " missing EXTENSION_DESCRIPTION")
			passed = False
		# check for startup attribute
		if not hasattr(extension,"startup"):
			Globals.debug(filename + " missing startup() function")
			messages.append(filename + " missing startup() function")
			passed = False
		# check for shutdown attribute
		if not hasattr(extension,"shutdown"):
			Globals.debug(filename + " missing shutdown() function")
			messages.append(filename + " missing shutdown() function")
			passed = False
		# check extension is not already loaded
		for testExtension in self.loadedExtensions:
			if testExtension["name"] == name:
				Globals.debug(filename + " extension '" + name + "' already present")
				messages.append(filename + " extension '" + name + "' already present")
				passed = False
		
		# quit if invalid in any way
		if not passed:
			return messages
		
		# add details to loadedExtensions list
		self.loadedExtensions.append(
			{"name":name, 
			 "description":description,
			 "version":version,
			 "extension":extension,
			 "enabled":True,
			 "filename":os.path.join(directory, filename) })
			 
		
		return messages
		
	#_____________________________________________________________________
	
	def GetExtensions(self):
		"""
			Returns a generator for iterating the list of loadedExtensions
		"""
		return iter(self.loadedExtensions)

	#_____________________________________________________________________
	
	def LoadExtensionFromFile(self, filename, directory):
		"""
			Tries to load an extension fron a file
			
			filename = name of file containing extension
			directory = full path to directory containing filename
		"""
		Globals.debug("importing extension...", filename)
		extension = None
		messages = []
		if filename.endswith(".py"):
			# for a python module try and import it
			extension = None
			fn = os.path.splitext(filename)[0]
			exten_file, filnme, description = imp.find_module(fn, [directory])
			
			try:
				extension = imp.load_module(fn, exten_file, filnme, description)
				Globals.debug("...done.")
			except Exception, e:
				Globals.debug("...failed.")
				Globals.debug(e)
				if exten_file:
					exten_file.close()
				return ([filename + " failed to import"])
			if exten_file:
				exten_file.close()
		elif filename.endswith(".egg"):
			# for an egg add it to working_set and then try and
			# load it and pick out the entry points
			fullName = os.path.join(directory, filename)
			pkg_resources.working_set.add_entry(fullName)
			dist_generator = pkg_resources.find_distributions(fullName)
			for dist in dist_generator:
				try:
					extension_class = dist.load_entry_point("jokosher.extensions", "extension")
					# create an instance of the class
					extension = extension_class()
					Globals.debug("...done.")
				except Exception, e :
					Globals.debug("...failed.")
					Globals.debug(e)
					return ([filename + " failed to import"])
		else:
			# any other file extension is wrong
			Globals.debug("Invalid extension file suffix for", filename)
			messages.append("Invalid extension file suffix for", filename)
			return messages
		# try and register the extension - quit if failed
		messages = self.register(extension, filename, directory)
		if len(messages):
			return messages
		# if we're still here then start the extension
		try:
			extension.startup(self.API)
		except Exception, e :
			Globals.debug(filename + " extension failed to start")
			messages.append(filename + " extension failed to start")
			Globals.debug(e)
		
		return messages
		
	#_____________________________________________________________________
	
	def UnloadExtension(self, filename):
		"""
			This function "unloads" the extension with file name
			"filename". It just executes the shutdown() function 
			of the extension and then removes it from loadedExtensions
		"""
		index = -1
		for extension in self.GetExtensions():
			index += 1
			if extension['filename'] == filename:
				extension['extension'].shutdown()
				self.loadedExtensions.pop(index)


	#_____________________________________________________________________
			
	def LoadAllExtensions(self):
		"""
			Walk through all the EXTENSION_DIRS and import every .py and .egg file we find.
		"""
		for exten_dir in Extension.EXTENSION_DIRS:
			if not os.path.isdir(exten_dir):
				continue
			for filename in os.listdir(exten_dir):
				if filename.endswith(".egg") or filename.endswith(".py"):
					self.LoadExtensionFromFile(filename, exten_dir)
					# don't block the gui when loading many extensions
					while gtk.events_pending():
						gtk.main_iteration()
		
	#_____________________________________________________________________
		
#=========================================================================

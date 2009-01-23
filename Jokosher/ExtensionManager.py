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
import shutil

#=========================================================================

class ExtensionManager:
	"""
	The ExtensionManager class handles the installation and running of
	Extensions. It also controls their disabling and removal.
	"""
	#_____________________________________________________________________
	
	def __init__(self, mainapp):
		"""
		Creates a new Instance of ExtensionManager.
		
		Parameters:
			parent -- the parent MainApp Jokosher window.
		"""
		self.mainapp = mainapp
		self.loadedExtensions = []
		self.API = Extension.ExtensionAPI(mainapp)
		self.LoadAllExtensions()
		
	#_____________________________________________________________________
	
	def register(self, extension, filename, directory, local):
		"""
		Called from Extension.LoadAllExtensions afer the Extensions
		module has been imported (and the class instantiated in the case
		of extensions that are eggs). 
		
		Parameters:	
			extension -- a reference to the Extension. Either a module 
						or in the case of an Extension imported from an
						egg, an instance object.
			filename -- the name of the file containing the Extension.
			directory -- full path to the directory containing the file.
			local --	True = the extension is to be copied to the
								local extension directory after checking
						False = don't copy the Extension.
		
		Returns:
			True -- the Extension was successfully registered.
			False -- an error ocurred while trying to register the Extension,
					or the Extension has been disabled via the ExtensionManagerDialog.
		"""
		name = None
		preferences = False
		# check if the necessary attributes EXTENSION_NAME, EXTENSION_VERSION
		#	and EXTENSION_DESCRIPTION are present and
		#	refuse to start the extension if they are missing. 
		requiredAttributes = ("EXTENSION_NAME", "EXTENSION_VERSION",
				"EXTENSION_DESCRIPTION", "startup", "shutdown")
		missingAttrs = []
		for attr in requiredAttributes:
			if not hasattr(extension, attr):
				missingAttrs.append(attr)
		
		if missingAttrs:
			Globals.debug("\t" + filename, "missing", ", ".join(missingAttrs))
			return False
		else:
			name = extension.EXTENSION_NAME
			version = extension.EXTENSION_VERSION
			description = extension.EXTENSION_DESCRIPTION

		# check for preferences attribute
		if hasattr(extension, "preferences"):
			preferences = True

		# check extension is not already loaded
		for testExtension in self.loadedExtensions:
			if testExtension["name"] == name:
				Globals.debug(filename + " extension '" + name + "' already present")
				return False
			
		# find full file name of extension
		extensionFile = os.path.join(directory, filename)
		
		# if we are installing locally first check the file doesn't exist and
		# then try and copy it 
		if local:
			extensionFile = os.path.join(Globals.JOKOSHER_DATA_HOME, "extensions", filename)
			if os.path.exists(extensionFile):
				Globals.debug("Filename " + extensionFile + " already exists")
				return False
			else:
				try:
					shutil.copy(os.path.join(directory, filename), extensionFile)
				except Exception, e:
					Globals.debug(filename + "Failed copying file: " + str(e))
					return False
		
		# check if extension's requirements are met (only if the extension requires it)
		testResults = (True, "")
		try:
			if hasattr(extension, "check_dependencies"):
				testResults = extension.check_dependencies()
		except Exception, e:
			Globals.debug(name + " extension could not check its dependencies")
			Globals.debug(e)
			return False
		
		# if the system doesn't provide what the extension needs,
		# fail loading this plugin and set the error message
		if testResults[0] == False:
			#TODO: inform the user of the error
			Globals.debug(name + ": "+testResults[1])
			return False
		
		# check if the extension is blacklisted, if so, mark it as disabled
		enabled = True
		if name in Globals.settings.extensions['extensions_blacklist']:
			enabled = False

		# add details to loadedExtensions list
		self.loadedExtensions.append(
			{"name":name, 
			 "description":description,
			 "version":version,
			 "extension":extension,
			 "enabled":enabled,
			 "preferences":preferences,
			 "filename":extensionFile })
			 
		return True
		
	#_____________________________________________________________________
	
	def GetExtensions(self):
		"""
		Obtain a generator for iterating the list of loadedExtensions.
		
		Returns:
			a generator with the list of loadedExtensions.
		"""
		return iter(self.loadedExtensions)

	#_____________________________________________________________________
	
	def LoadExtensionFromFile(self, filename, directory, local=False):
		"""
		Tries to load an Extension fron a given file.
		
		Parameters:
			filename -- the name of the file containing the Extension.
			directory -- full path to the directory containing the file.
			local --	True = the extension is to be copied to the
								local extension directory after checking
						False = don't copy the Extension.
		
		Returns:
			True -- the Extension was successfully loaded.
			False -- an error ocurred while trying to load the Extension,
					or the Extension has been disabled via the ExtensionManagerDialog.
		"""
		Globals.debug("\timporting extension", filename)
		extension = None
		if filename.endswith(".py"):
			# for a python module try and import it
			extension = None
			fn = os.path.splitext(filename)[0]
			exten_file, filename, description = imp.find_module(fn, [directory])
			
			try:
				extension = imp.load_module(fn, exten_file, filename, description)
			except Exception, e:
				Globals.debug("\t\t...failed.")
				Globals.debug(e)
				if exten_file:
					exten_file.close()
				return False
			if exten_file:
				exten_file.close()
				
		elif filename.endswith(".egg"):
			# for an egg, add it to working_set and then try and
			# load it and pick out the entry points
			fullName = os.path.join(directory, filename)
			pkg_resources.working_set.add_entry(fullName)
			dist_generator = pkg_resources.find_distributions(fullName)
			for dist in dist_generator:
				try:
					extension_class = dist.load_entry_point("jokosher.extensions", "extension")
					# create an instance of the class
					extension = extension_class()
				except Exception, e :
					Globals.debug("\t\t...failed.")
					Globals.debug(e)
					return False
		else:
			# any other file extension is wrong
			Globals.debug("Invalid extension file suffix for", filename)
			return False
		
		# try and register the extension - quit if failed
		if not self.register(extension, filename, directory, local):
			return False
		
		# if we're still here then start the extension, if its not in the extensions_blacklist
		if extension.EXTENSION_NAME not in Globals.settings.extensions['extensions_blacklist']:
			dir
			if not self.StartExtension(self.loadedExtensions[len(self.loadedExtensions)-1]["filename"]):
				return False
		
		return True
		
	#_____________________________________________________________________

	def StopExtension(self, filename):
		"""
		Stops the given Extension.
		
		Considerations:
			This method executes the shutdown() function of the Extension.
			This is mainly for disabling Extensions	on the fly, but is also
			used for removing them.
			
		Parameters:
			filename -- the name of the file containing the Extension.
			
		Returns:
			True -- the Extension was successfully stopped.
			False -- an error ocurred while trying to stop the Extension.
		"""
		for extension in self.GetExtensions():
			if extension['filename'] == filename:
				try:
					extension['extension'].shutdown()
				except Exception, e:
					Globals.debug(filename + " extension failed to shut down")
					Globals.debug(e)
					return False
		return True

	#_____________________________________________________________________

	def StartExtension(self, filename):
		"""
		Starts the given Extension.
		
		Considerations:
			This method executes the startup() function of the Extension
			This is mainly for enabling an Extension on the fly without
			loading another instance.
			
		Parameters:
			filename -- the name of the file containing the Extension.
			
		Returns:
			True -- the Extension was successfully started.
			False -- an error ocurred while trying to start the Extension.
		"""
		for extension in self.GetExtensions():
			if extension['filename'] == filename:
				try:
					extension['extension'].startup(self.API)
				except Exception, e:
					Globals.debug(filename + " extension failed to start")
					Globals.debug(e)
					return False
		return True

	#_____________________________________________________________________
	
	def RemoveExtension(self, filename):
		"""
		Removes the given Extension.
		
		Considerations:
			This function "unloads" the Extension. It executes the shutdown()
			function of the Extension and then removes it from loadedExtensions.
			
		Parameters:
			filename -- the name of the file containing the Extension.
			
		Returns:
			True -- the Extension was successfully removed.
			False -- an error ocurred while trying to remove the Extension.
		"""
		self.StopExtension(filename)
		index = -1
		for extension in self.GetExtensions():
			index += 1
			if extension['filename'] == filename:
				try:
					os.remove(filename)
					self.loadedExtensions.pop(index)
				except Exception, e:
					Globals.debug("Failed to remove " + filename)
					Globals.debug(e)
					return False
		return True
	
	#_____________________________________________________________________
	
	def ExtensionPreferences(self, filename):
		"""
		Loads the preferences() function of an Extension.
		
		Parameters:
			filename -- the name of the file containing the Extension.
			
		Returns:
			True -- the Extension's preferences were successfully loaded.
			False -- an error ocurred while trying to load the Extension's
					preferences.
		"""
		for extension in self.GetExtensions():
			if extension['filename'] == filename:
				try:
					extension['extension'].preferences()
				except:
					Globals.debug("Someone screwed up their preferences function")
					return False
		return True
				
	#_____________________________________________________________________
			
	def LoadAllExtensions(self):
		"""
		Load all the Extensions found in EXTENSION_PATHS and import every .py
		and .egg file found.
		"""
		Globals.debug("Loading extensions:")
		for exten_dir in Globals.EXTENSION_PATHS:
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

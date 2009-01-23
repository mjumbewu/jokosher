#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	This module handles the saving and loading of mixdown profiles.
#	
#
#-------------------------------------------------------------------------------

import os
import gobject
import xml.dom.minidom as xml

import MixdownActions
import Globals
import Utils

#=========================================================================

class MixdownProfiles(gobject.GObject):
	"""
	Represents a mixdown profile, used for doing complex mixdown operations.
	"""
	
	# the extension put on the end of mixdown profiles
	MIXDOWN_EXT = "profile"
	
	"""
	Signals:
		"profile-update" -- MixdownActions have been added to a MixdownProfile.
		"error-occurred" -- An error occurred while attempting to load MixdownActions.
	"""
	
	__gsignals__ = {
		"profile-update" : ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,) ),
		"error-occurred" : ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING, gobject.TYPE_STRING) )
	}
	
	#_____________________________________________________________________

	def __init__(self, manager):
		""" 
		Creates a new instance of MixdownProfiles.
		
		Parameters:
			manager -- reference to MixdownProfileManager.
		"""
		# we need a reference to MixdownProfileManager because we need to handle
		# special cases for classes such as ExportAsFileType. 
		# ExportAsFileType requires an instance of Project to function correctly,
		# so we have to pass Project and the only way to do that is by accessing the
		# reference to Project in MixdownProfileDialog.
		
		# we also need manager for accessing extensionManager, so we can iterate over
		# loaded extensions, see the __LoadMixdownActionFromAssociatedExtension method for more details.
		self.manager = manager
		
		gobject.GObject.__init__(self)
		
	#_____________________________________________________________________
	
	def SaveProfile(self, name, actionlist=None):
		"""
		This method will write a mixdown profile to JOKOSHER_DATA_HOME/mixdownprofiles/.
		actionlist is a list containing MixdownAction instances, e.g.
		[ExportAsFileType object instance, RunAScript object instance].
	
		Parameters:
			name -- the name of the template file.
			actionlist -- a list containing MixdownAction instances.
		"""
		doc = xml.Document()
		head = doc.createElement("JokosherMixdownProfile")
		doc.appendChild(head)
		actionTag = doc.createElement("MixdownActions")
		head.appendChild(actionTag)
		
		if actionlist:
			for action in actionlist:
				actionName = doc.createElement(action.__class__.__name__)
				actionTag.appendChild(actionName)
				actionConfig = doc.createElement("Configuration")
				actionName.appendChild(actionConfig)
				Utils.StoreDictionaryToXML(doc, actionConfig, action.config)
		
		if not name.endswith("." + self.MIXDOWN_EXT):
			name += "." + self.MIXDOWN_EXT
		namePath = os.path.join(Globals.MIXDOWN_PROFILES_PATH, name)
		try:
			try:
				filename = open(namePath, "w")
				filename.write(doc.toprettyxml())
			except IOError, e:
				Globals.debug(_("The mixdown profile %s does not exist" % namePath))
		finally:
			filename.close()
			
		self.emit("profile-update", "saveProfile")
	
	#_____________________________________________________________________

	def DeleteProfile(self, name):
		"""
		This method will delete a mixdown profile.
		
		Parameters:
			name -- the name of the mixdown profile which will be deleted.
		"""
		if not name.endswith("." + self.MIXDOWN_EXT):
			name += "." + self.MIXDOWN_EXT
		namePath = os.path.join(Globals.MIXDOWN_PROFILES_PATH, name)
		try:
			os.remove(namePath)
		except OSError, e:
			Globals.debug(_("Cannot remove mixdown profile %s" % namePath))
		
		self.emit("profile-update", "deleteProfile")
	
	#_____________________________________________________________________

	def LoadMixdownActionsFromProfile(self, name):
		"""
		Called when actions from a profile need to be loaded.
		This method will return a list of MixdownAction instances associated
		with the profile name specified.
		
		Parameters:
			name-- the name of a profile to load actions from.
		
		Returns:
			actions -- a list of MixdownAction instances assocated with the profile specified.
		"""
		if not name.endswith("." + self.MIXDOWN_EXT):
			name += "." + self.MIXDOWN_EXT
		namePath = os.path.join(Globals.MIXDOWN_PROFILES_PATH, name)
		if os.path.exists(namePath):
			file = open(namePath, "r")
			doc = xml.parse(file)
			actions = []
			for node in doc.getElementsByTagName("MixdownActions"):
				for children in node.childNodes:
					if children.nodeType == 1:
						for child in children.childNodes:
							if child.nodeType == 1:
								actionObject = self.__LoadMixdownAction(children.nodeName)
								if actionObject:
									configActionObject = self.__HandleMixdownActionConfig(actionObject, child)
									actions.append(configActionObject)
			return actions
		else:
			Globals.debug(_("The mixdown profile %s does not exist" % namePath))
		
	#_____________________________________________________________________
	
	def __LoadMixdownAction(self, actionName):
		"""
		Called when a MixdownAction needs to be instantiated.
		This method will return an instance of a MixdownAction specified
		by the action name given.
		
		Parameters:
			actionName -- the name of the MixdownAction to instantiate.
		
		Returns:
			actionObject -- reference to a MixdownAction object.
		"""
		actionObject = None
		
		# load a core MixdownAction, if it fails, actionObject will still be None
		actionObject = self.__LoadMixdownActionFromCore(actionName)
		
		# if we cannot load a core action from the action name specified, then we'll
		# attempt to load it from extensions that have MixdownActions.
		if not actionObject:
			# if __LoadMixdownActionFromAssociatedExtension returns None, then
			# the extension been disabled or deleted.
			actionObject = self.__LoadMixdownActionFromAssociatedExtension(actionName)
		
		# if we have an action object then it is time to instantiate it.
		if actionObject:
			actionObject = self.__HandleSpecialCases(actionObject)
		
		return actionObject

	#_____________________________________________________________________
	
	def __LoadMixdownActionFromCore(self, actionName):
		"""
		Called when a MixdownAction from MixdownActions needs to be instantiated.
		This method returns an instantiated MixdownAction from MixdownActions.py (core)
		
		Parameters:
			actionName -- the name of the MixdownAction to instantiate.
		
		Returns:
			actionObject -- reference to a MixdownAction object.
		"""
		actionObject = None
		try:
			actionObject = getattr(MixdownActions, actionName)
		except AttributeError:
			pass
		
		return actionObject
	
	#_____________________________________________________________________

	def __LoadMixdownActionFromAssociatedExtension(self, actionName):
		"""
		Called when a MixdownAction from a Jokosher Extension needs to be instantiated.
		This method will iterate over all loaded extensions and return the MixdownAction
		object specified by the action name given.
		
		Parameters:
			actionName -- the name of the MixdownAction to instantiate.
		
		Returns:
			action -- reference to a MixdownAction object.
		"""
		count = -1
		action = None
		for extension in self.__ReturnLoadedExtensions():
			try:
				if extension["enabled"] and extension["extension"].mixdownActions:
					for item in extension["extension"].mixdownActions:
						count += 1
						if actionName == item.__name__:
							action = extension["extension"].mixdownActions[count]
							break
				else:
					self.__RaiseMixdownActionLoadingError(actionName, extension["name"])
			except AttributeError:
				pass

		return action
	
	#_____________________________________________________________________
	
	def __ReturnLoadedExtensions(self):
		"""
		Called when all loaded extension need to be returned.
		This method returns all loaded Jokosher extensions.

		Returns:
			loadedExtensions -- list of loaded Jokosher extensions.
		"""
		return self.manager.mixdownProfileDialog.mainapp.extensionManager.loadedExtensions

	#_____________________________________________________________________
	
	def __HandleMixdownActionConfig(self, actionObject, configTag):
		"""
		Called when the configuration of a MixdownAction needs to be set.
		This method handles setting the isConfigured class attribute for
		MixdownActions.
		
		Parameters:
			actionObject -- reference to a MixdownAction object.
			actionTag -- the action tag to load the config from, e.g. <ExportAsFileType> <Configuration/>
		
		Returns:
			actionObject -- the configured MixdownAction
		"""
		actionObject.config = Utils.LoadDictionaryFromXML(configTag)
		
		if actionObject.config:
			actionObject.isConfigured = True
		else:
			actionObject.isConfigured = False
		
		return actionObject
		
	#_____________________________________________________________________

	def __RaiseMixdownActionLoadingError(self, actionName, extensionName):
		"""
		Called when an error has occured while loading MixdownActions.
		This method will emit an error-occurred gobject signal, this signal
		will show a dialog, informing the user that a MixdownAction could not
		be loaded.
		
		Parameters:
			actionName -- the name of the MixdownAction which cannot be loaded.
			extensionName -- the name of the extension that the MixdownAction can't be loaded from.
		"""
		self.emit("error-occurred", actionName, extensionName)

	#_____________________________________________________________________
	
	def __HandleSpecialCases(self, actionObject):
		"""
		Called when special cases such as ExportAsFileType need to be handled.
		This method will take care of the loading of MixdownActions from MixdownActions.py,
		passing the correct arguments to the MixdownAction classes,
		e.g. ExportAsFileType requires Project to be passed to it's constructor.
		
		Parameters:
			actionObject -- reference to a MixdownAction object.
		
		Returns:
			actionObject - a MixdownAction instance.
		"""
		if actionObject == MixdownActions.ExportAsFileType:
			action = actionObject(self.manager.mixdownProfileDialog.project)
		else:
			action = actionObject()
		return action
		
	#_____________________________________________________________________

#=========================================================================

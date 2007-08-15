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
	"""
	
	__gsignals__ = {
		"profile-update" : ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,) )
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
		self.manager = manager
		
		gobject.GObject.__init__(self)
		
	#_____________________________________________________________________
	
	def SaveProfile(self, name, actionlist=None):
		""" 
		This method will write a mixdown profile to ~/.jokosher/mixdownprofiles/.
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

	def LoadProfileActions(self, name):
		"""
		Called when actions from a profile need to be loaded.
		
		Parameters:
			name-- the name of a profile to load actions from.
		
		Returns:
			actions -- a list of MixdownAction instances assocated with profile specified.
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
								actionObject = self.HandleSpecialCases(children.nodeName)
								actionObject.config = Utils.LoadDictionaryFromXML(child)
								if actionObject.config:
									actionObject.isConfigured = True
								else:
									actionObject.isConfigured = False
								actions.append(actionObject)

			return actions
		else:
			Globals.debug(_("The mixdown profile %s does not exist" % namePath))
		
	#_____________________________________________________________________
	
	def HandleSpecialCases(self, actionName):
		"""
		Called when special cases such as ExportAsFileType 
		need to be handled.
		This method will take care of the loading of MixdownActions from MixdownActions.py,
		passing the correct arguments to the MixdownAction classes,
		e.g. ExportAsFileType requires Project to be passed to it's constructor.
		
		Parameters:
			actionName -- the name of the action to be instantiated.
		
		Returns:
			action - a MixdownAction instance.
		"""
		actionObject = self.ReturnActionObjects(actionName)
		if actionObject == MixdownActions.ExportAsFileType:
			action = actionObject(self.manager.mixdownProfileDialog.project)
		else:
			action = actionObject()
		return action
		
	#_____________________________________________________________________
	
	def ReturnActionObjects(self, actionName):
		"""
		Called when MixdownAction instances need to be returned.
		Returns a MixdownAction instance.
		
		Parameters:
			actionName -- the name of the action which should be instantiated.
		"""
		# This code is still not very pretty but it does work well.
		action = None
		count = -1
		for extension in self.manager.mixdownProfileDialog.mainapp.extensionManager.loadedExtensions:
			# extension["extension"] should return extension class instances but this isn't the
			# case for extensions such as GnomeAudioProfiles and JokosherDbus which return module objects
			# we have to have a try/except block as extension["extension"].mixdownActions raises
			# an AttributeError exception if extension["extension"] is anything but a class instance.
			try:
				if extension["extension"].mixdownActions:
					for item in extension["extension"].mixdownActions:
						count += 1
						if actionName == item.__name__:
							action = extension["extension"].mixdownActions[count]
							break
			except AttributeError:
				pass
					
		# if there is no action set by the code above, then the action to be returned should be a core MixdownAction.
		if not action:
			action = getattr(MixdownActions, actionName)
		return action
	#_____________________________________________________________________

#=========================================================================

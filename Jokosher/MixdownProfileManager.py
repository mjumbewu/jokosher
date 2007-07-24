#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	This class handles the saving, modifying, and deleting of mixdown profiles.
#
#-------------------------------------------------------------------------------

import Globals
import MixdownProfiles
import os

#=========================================================================

class MixdownProfileManager:
	"""
	This class handles the saving, loading and modification associated with MixdownProfiles.
	"""
	
	#_____________________________________________________________________

	def __init__(self, parent):
		"""
		Creates a new instance of MixdownProfileManager
		
		Parameters:
			parent -- reference to MixdownProfileDialog
		"""
		self.parent = parent
		self.profiles = MixdownProfiles.MixdownProfiles(self)
		self.profiles.connect("profile-update", self.MixdownProfileUpdate)
	
	#_____________________________________________________________________
	
	def MixdownProfileUpdate(self, mixdownProfile, signalDetails):
		"""
		Called when a mixdown profile has been saved or deleted.
		Updates the profile combo model (self.parent.profileComboModel) accordingly.
		
		Parameters:
			mixdownProfile -- the MixdownProfiles instance that sent the signal
			signalDetails -- determines whether the profile was saved or deleted.
		"""
		self.parent.UpdateProfileModel(signalDetails)
		self.parent.OnCheckActionConfigured()
		
	#_____________________________________________________________________
	
	def GetMixdownProfileList(self):
		"""
		Called when the profile combo model (self.parent.profileComboModel) is populated.
		
		Returns:
			profilelist -- a list of profiles in the user's mixdown profiles directory.
		"""
		profilelist = []
		for files in os.listdir(Globals.MIXDOWN_PROFILES_PATH):
			if files.endswith(".profile"):
				filenames = files.split(".")[0]
				profilelist.append(filenames)
		return profilelist
		
	#_____________________________________________________________________

	def SaveMixdownProfile(self, profileName, actionList=None):
		"""
		Convenience method for saving a MixdownProfile to disk.
		
		Parameters:
			profileName -- The name of the profile to use in the profile filename.
			actionList -- list of MixdownActions to save.
		"""
		self.profiles.SaveProfile(profileName, actionList)
		
	#_____________________________________________________________________

	def DeleteMixdownProfile(self, profileName):
		"""
		Convenience method for deleting a MixdownProfile from disk.
		
		Parameters:
			profileName -- the name of the profile to be deleted
		"""
		self.profiles.DeleteProfile(profileName)

	#_____________________________________________________________________
	
	def ReturnAllActionsFromMixdownProfile(self, profileName):
		"""
		Convenience method for returning all actions in a MixdownProfile.
		
		Parameters:
			profileName -- the name of the MixdownProfile to load all MixdownActions from.
		"""
		actions = self.profiles.LoadProfileActions(profileName)
		return actions
		
	#_____________________________________________________________________

#=========================================================================

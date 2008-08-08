#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	This class handles restoring projects after a crash has occured.
#
#-------------------------------------------------------------------------------

import gtk.glade
import gobject
import Globals
import gettext
_ = gettext.gettext

#=========================================================================

class CrashProtectionDialog:
	"""
	Displays a dialog allowing the user to either select a previously crashed 
	project for restoration or to delete a crash file.
	"""

	#_____________________________________________________________________

	
	def __init__(self):
		self.crashedProjectTree = gtk.glade.XML(Globals.GLADE_PATH, "CrashedProjectDialog")

		self.crashedProjectDialog = self.crashedProjectTree.get_widget("CrashedProjectDialog")

		closeButton = self.crashedProjectTree.get_widget("CrashDialogCloseButton")	
		closeButton.connect("clicked", lambda dialog: self.crashedProjectDialog.destroy())

		self.populate()

	#_____________________________________________________________________


	def populate(self):
		pass

#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	Workspace.py
#	
#	A sub-class of gtk.VPaned containing the the varous views of the project
#
#-------------------------------------------------------------------------------

import gtk
import gobject
import os.path
import Globals
import RecordingView
import CompactMixView

#=========================================================================

class Workspace(gtk.VPaned):
	"""
	This class implements the workspace view.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, project, mainview):
		"""
		Creates a new instance of Workspace.
		
		Parameters:
			project -- the active Project.
			mainview -- reference to the MainApp Jokosher window.
		"""
		gtk.VPaned.__init__(self)
		self.project = project
		self.mainview = mainview
		self.small = False
		self.recordingView = RecordingView.RecordingView(project, mainview, self.small)
		self.mixView = CompactMixView.CompactMixView(project, mainview)
		self.pack1(self.recordingView, resize=True, shrink=False)
		self.pack2(self.mixView, resize=True, shrink=False)
		self.mixView.hide()
		self.show()
	#_____________________________________________________________________
	
	def ToggleCompactMix(self):
		"""
		Toggles compact mix view on/off.
		"""
		if self.mainview.compactMixButton.get_active():
			self.recordingView.ChangeSize(True)
			self.mixView.show()
			self.mainview.compactMixButton.set_tooltip_text(self.mainview.mixingViewEnabledTip)
		else:
			self.recordingView.ChangeSize(False)
			self.mixView.hide()
			self.mainview.compactMixButton.set_tooltip_text(self.mainview.mixingViewDisabledTip)
	#____________________________________________________________________	

#=========================================================================
		

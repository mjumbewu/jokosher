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
		self.add(self.recordingView)
		self.add(self.mixView)
		self.mixView.hide()
		self.show()
	#_____________________________________________________________________

	def ToggleRecording(self):
		"""
		Toggles the recording view on/off.
		"""
		if self.mainview.recordingButton.get_active():
			self.recordingView.show()
			self.mainview.contextTooltips.set_tip(
						self.mainview.recordingButton,
						self.mainview.recordingViewEnabledTip)
		else:
			#don't hide the recording view if the mix view is also hidden
			if not self.mainview.compactMixButton.get_active():
				self.mainview.recordingButton.set_active(True)
				return
			self.recordingView.hide()
			self.mainview.contextTooltips.set_tip(
						self.mainview.recordingButton,
						self.mainview.recordingViewDisabledTip)
#____________________________________________________________________	

	
	def ToggleCompactMix(self):
		"""
		Toggles compact mix view on/off.
		"""
		if self.mainview.compactMixButton.get_active():
			self.recordingView.ChangeSize(True)
			self.mixView.show()
			self.mainview.contextTooltips.set_tip(
						self.mainview.compactMixButton,
						self.mainview.mixingViewEnabledTip)
		else:
			#don't hide the mix view if the recording view is also hidden
			if not self.mainview.recordingButton.get_active():
				self.mainview.compactMixButton.set_active(True)
				return
			self.recordingView.ChangeSize(False)
			self.mixView.hide()
			self.mainview.contextTooltips.set_tip(
						self.mainview.compactMixButton,
						self.mainview.mixingViewDisabledTip)
	#____________________________________________________________________	

#=========================================================================
		

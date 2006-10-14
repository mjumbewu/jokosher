#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	AudioPreview.py
#	
#	This module is handles previewing audio files from within
#	the gtk open file dialog, when you are browsing for an audio
#	file to import.
#
#-------------------------------------------------------------------------------

import gtk
import gst

#=========================================================================

class AudioPreview(gtk.ToggleButton):
	"""
	   A simple button to be added to the load-a-clip-from-a-file open dialog,
	   which previews the selected sound.
	"""

	def __init__(self):
		gtk.ToggleButton.__init__(self, "gtk-media-play")
		self.set_use_stock(True)
		self.uri = None
		self.connect("toggled", self.OnToggle)
		self.connect("destroy", self.OnDestroy)
		# playbin is a gst element which plays a sound and works out everything
		self.previewbin = gst.element_factory_make ("playbin", "preview")
		self.bus = self.previewbin.get_bus()
		self.bus.add_signal_watch()
		# deactivate thyself if the sound finishes or there's an error
		self.bus.connect("message::eos", self.OnEOS)
		self.bus.connect("message::error", self.OnEOS)
		
	#_____________________________________________________________________

	def OnSelection(self, widget):
		self.uri = widget.get_preview_uri()
		self.set_active(False)
		
	#_____________________________________________________________________

	def OnToggle(self, widget):
		"Toggling the button plays or stops playing by setting ready state"
		if self.get_active():
			self.previewbin.set_property("uri", self.uri)
			self.previewbin.set_state(gst.STATE_PLAYING)
		else:
			self.previewbin.set_state(gst.STATE_READY)
			
	#_____________________________________________________________________
			
	def OnEOS(self, bus, message):
		self.set_active(False)
		
	#_____________________________________________________________________

	def OnDestroy(self, widget=None):
		self.previewbin.set_state(gst.STATE_NULL)
	
	#_____________________________________________________________________

#=========================================================================

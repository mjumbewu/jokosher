#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	AudioPreview.py
#	
#	This module handles previewing audio files from within
#	the gtk open file dialog, when you are browsing for an audio
#	file to import.
#
#-------------------------------------------------------------------------------

import gtk
import gst

#=========================================================================

class AudioPreview(gtk.ToggleButton):
	"""
	A button, added to the load-a-clip-from-a-file open dialog,
	which previews the selected sound.
	"""

	def __init__(self):
		"""
		Creates a new instance of AudioPreview.
		"""
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
		"""
		This method is called when a user selects a new file in the import audio file dialog. 
		The preview widget then retrieves the location of the file that has been selected
		and sets the variable self.uri to be the location of the file it retrieves.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.uri = widget.get_preview_uri()
		self.set_active(False)
		
	#_____________________________________________________________________

	def OnToggle(self, widget):
		"""
		This method is called when a user toggles the preview button between a stop
		or playing state. It will then set the button to appear pressed in when playing
		or normal when stopped.
		
		Parameters:
			widget -- reserved for GTK callbacks, dont't use it explicitly.
		"""
		if self.get_active():
			self.previewbin.set_property("uri", self.uri)
			self.previewbin.set_state(gst.STATE_PLAYING)
		else:
			self.previewbin.set_state(gst.STATE_READY)
			
	#_____________________________________________________________________
			
	def OnEOS(self, bus, message):
		"""
		Called when the preview stream ends. It deactives the AudioPreview.
		
		Parameters:
			bus -- reserved for GStreamer callbacks, dont't use it explicitly.
			message -- reserved for GStreamer callbacks, dont't use it explicitly.
		"""
		self.set_active(False)
		
	#_____________________________________________________________________

	def OnDestroy(self, widget=None):
		"""
		This method sets the preview pipeline to gst.STATE_NULL.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.previewbin.set_state(gst.STATE_NULL)
	
	#_____________________________________________________________________

#=========================================================================

import gtk
import gst

#=========================================================================

class AudioPreview(gtk.ToggleButton):

	def __init__(self):
		gtk.ToggleButton.__init__(self, "gtk-media-play")
		self.set_use_stock(True)
		self.uri = None
		self.connect("toggled", self.OnToggle)
		self.connect("destroy", self.OnDestroy)
		self.previewbin = gst.element_factory_make ("playbin", "preview");
		
		self.bus = self.previewbin.get_bus()
		self.bus.add_signal_watch()
		self.bus.connect("message::eos", self.OnEOS)
		self.bus.connect("message::error", self.OnEOS)
		
	#_____________________________________________________________________

	def OnSelection(self, widget):
		self.uri = widget.get_preview_uri()
		self.set_active(False)
		
	#_____________________________________________________________________

	def OnToggle(self, widget):
		if self.get_active():
			self.previewbin.set_property("uri", self.uri)
			self.previewbin.set_state(gst.STATE_PLAYING)
		else:
			self.previewbin.set_state(gst.STATE_READY)
			
	#_____________________________________________________________________
			
	def OnEOS(self, bus, message):
		self.set_active(False)
		
	#_____________________________________________________________________

	def OnDestroy(self, widget):
		self.previewbin.set_state(gst.STATE_NULL)
	
	#_____________________________________________________________________

#=========================================================================

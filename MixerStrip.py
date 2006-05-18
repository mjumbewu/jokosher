
import pygtk
pygtk.require("2.0")
import gtk

from VUWidget import *

#=========================================================================

class MixerStrip(gtk.Frame):
	
	__gtype_name__ = 'MixerStrip'
	
	#_____________________________________________________________________
	
	def __init__(self, project, instrument):
		gtk.Container.__init__(self)
		self.project = project
		self.instrument = instrument
		self.Updating = False
		
		self.vbox = gtk.VBox()
		self.add(self.vbox)

		self.minbutt = gtk.Button()
		img = gtk.image_new_from_stock(gtk.STOCK_GOTO_BOTTOM, gtk.ICON_SIZE_MENU)
		self.minbutt.set_image(img)
		self.minbutt.connect("clicked", self.EmitMinimise)
				
		self.tophb = gtk.HBox()
		self.tophb.pack_start(gtk.Label("foo"))
		self.tophb.pack_end(self.minbutt)

		self.vbox.pack_start(self.tophb, False)
		
		# VU Meter
		self.vu = VUWidget(instrument)
		self.vbox.pack_start(self.vu, True, True)
		
		#Control Buttons
		hb = gtk.HBox()
			
		img = gtk.image_new_from_stock(gtk.STOCK_MEDIA_RECORD, gtk.ICON_SIZE_BUTTON)
		self.recButton = gtk.ToggleButton("")
		self.recButton.set_property("image", img)
		self.recButton.connect("toggled", self.OnArm)

		self.muteButton = gtk.ToggleButton("M")
		self.muteButton.connect("toggled", self.OnMute)
		
		self.soloButton = gtk.ToggleButton("S")
		self.soloButton.connect("toggled", self.OnSolo)
		
		self.sourceButton = gtk.ToggleButton("In")
		
		hb.add(self.recButton)
		hb.add(self.muteButton)
		hb.add(self.soloButton)
		hb.add(self.sourceButton)
		self.vbox.pack_start(hb, False, False)
		
		# Label and icon
		hb = gtk.HBox()
		imgsize = gtk.icon_size_lookup(gtk.ICON_SIZE_MENU)[0]
		pixbuf = self.instrument.pixbuf.scale_simple(imgsize, imgsize, gtk.gdk.INTERP_BILINEAR)
		image = gtk.Image()
		image.set_from_pixbuf(pixbuf)
		hb.pack_start(image, False, False)
		
		self.label = gtk.Label(instrument.name)
		self.label.set_max_width_chars(6)
		hb.pack_start(self.label, True, True)
		
		self.vbox.pack_end(hb, False, False)
		self.vbox.show_all()
		self.show_all()
		
	#_____________________________________________________________________

	def OnMute(self, widget):
		if not self.Updating:
			self.instrument.ToggleMuted(False)
	
	#_____________________________________________________________________

	def OnArm(self, widget):
		if not self.Updating:
			self.instrument.ToggleArmed()
		
	#_____________________________________________________________________
	
	def OnSolo(self, widget):
		if not self.Updating:
			self.instrument.ToggleSolo(False)
		
	#_____________________________________________________________________
	
	def EmitMinimise(self, widget):
		self.emit("minimise")
	
	#_____________________________________________________________________
	
	def Update(self):
		self.Updating = True
		
		self.label.set_text(self.instrument.name)
		self.recButton.set_active(self.instrument.isArmed)
		self.muteButton.set_active(self.instrument.actuallyIsMuted)
		self.soloButton.set_active(self.instrument.isSolo)
		
		self.Updating = False
	
	#_____________________________________________________________________
	
#=========================================================================


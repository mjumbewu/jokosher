#
#       THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#       THE 'COPYING' FILE FOR DETAILS
#
#       MixerStrip.py
#       
#		Contains the VU widget, the buttons below it and levels,
#		for an Instrument in the mixing view.
#
#-------------------------------------------------------------------------------

import pygtk
pygtk.require("2.0")
import gtk
import gobject
import os
import Globals
import Utils
import ControlsBox

import gettext
_ = gettext.gettext

from VUWidget import *

#=========================================================================

class MixerStrip(gtk.Frame):
	"""
	Contains the VU widget and the buttons below it,
	for an Instrument in the mixing view.
	"""
	
	""" GTK widget name """
	__gtype_name__ = 'MixerStrip'
	
	#_____________________________________________________________________
	
	def __init__(self, project, instrument, mixview, mainview):
		"""
		Creates a new instance of MixerStrip.
		
		Parameters:
			project -- the currently active Project.
			instrument -- the instrument associated with this MixerStrip.
			mixview -- the mixing view object (CompactMixView).
			mainview -- the main Jokosher window (MainApp).
		"""
		gtk.Container.__init__(self)
		self.project = project
		self.instrument = instrument
		self.mixview = mixview
		self.mainview = mainview
		self.Updating = False
		self.statusbarMsgID = None
		
		self.vbox = gtk.VBox()
		self.add(self.vbox)

		self.minbutt = gtk.Button()
		img = gtk.image_new_from_stock(gtk.STOCK_GOTO_BOTTOM, gtk.ICON_SIZE_MENU)
		self.minbutt.set_image(img)
		self.minbutt.set_tooltip_text(_("Minimize instrument"))
		self.minbutt.connect("clicked", self.EmitMinimise)
				
		self.vbox.pack_start(self.minbutt, False)
		
		self.panvbox = gtk.VBox()
		self.panvbox.set_border_width(3)
		self.vbox.pack_start(self.panvbox, False)

		# the slider label
		balanceLabel = gtk.Label(_("Balance:"))
		self.panvbox.pack_start(balanceLabel, False)
		# add the panning slider
		self.panhbox = gtk.HBox()
		self.panhbox.set_spacing(3)
		self.leftlab = gtk.Label(_("L"))
		self.rightlab = gtk.Label(_("R"))
		self.pan = gtk.HScale()
		self.pan.set_range(-1.0, 1.0)
		self.pan.set_increments(0.1, 1.0)
		self.pan.set_draw_value(False)
		self.pan.set_tooltip_text(_("Adjust instrument balance. Right-click to center"))
		
		if self.instrument.pan:
			self.pan.set_value(self.instrument.pan)
		
		self.pan.connect("value-changed", self.OnPanChanged)
		self.pan.connect("button-press-event", self.OnPanClicked)
		self.panhbox.pack_start(self.leftlab, False)
		self.panhbox.pack_start(self.pan, True)
		self.panhbox.pack_start(self.rightlab, False)
		
		self.panvbox.pack_start(self.panhbox, False)

		#volume label
		volumeLabel = gtk.Label(_("Volume:"))
		volumeLabel.set_padding(3, 3)
		self.vbox.pack_start(volumeLabel, False)
		# VU Meter
		self.vu = VUWidget(self, self.mainview)
		self.vbox.pack_start(self.vu, True, True)
		
		#Control Buttons
		controlsBox = ControlsBox.ControlsBox(project, mainview,instrument,includeEffects=False)
		self.vbox.pack_start(controlsBox, False, False)
		
		# Label and icon
		hb = gtk.HBox()
		self.instrImage = gtk.Image()
		#initalize the image from the instrument's pixbuf
		self.OnInstrumentImage()
		hb.pack_start(self.instrImage, False, False)
		
		self.label = gtk.Label(instrument.name)
		self.label.set_max_width_chars(6)
		hb.pack_start(self.label, True, True)

		self.instrument.connect("name", self.OnInstrumentName)
		self.instrument.connect("image", self.OnInstrumentImage)
		
		self.vbox.pack_end(hb, False, False)
		self.vbox.show_all()
		self.show_all()
		
	#_____________________________________________________________________

	def EmitMinimise(self, widget):
		"""
		Minimizes the Instrument to the StatusBar.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.emit("minimise")
	
	#_____________________________________________________________________
	
	def OnInstrumentName(self, instrument=None):
		"""
		Callback for when the instrument's name changes.
		
		Parameters:
			instrument -- the instrument instance that send the signal.
		"""
		self.label.set_text(self.instrument.name)
		
	#_____________________________________________________________________
	
	def OnInstrumentImage(self, instrument=None):
		"""
		Callback for when the instrument's image changes.
		
		Parameters:
			instrument -- the instrument instance that send the signal.
		"""
		imgsize = gtk.icon_size_lookup(gtk.ICON_SIZE_MENU)[0]
		pixbuf = self.instrument.pixbuf.scale_simple(imgsize, imgsize, gtk.gdk.INTERP_BILINEAR)
		self.instrImage.set_from_pixbuf(pixbuf)
		
	#_____________________________________________________________________

	def Destroy(self):
		"""
		Called when the MixerStrip is destroyed. It also emits the
		destroy signal to the VUMixer widget.
		"""
		self.instrument.disconnect_by_func(self.OnInstrumentImage)
		self.instrument.disconnect_by_func(self.OnInstrumentName)
		self.vu.Destroy()
		self.destroy()
	
	#_____________________________________________________________________

	def GetLevel(self):
		"""
		Obtain the instrument level.
		
		Returns:
			the level of the instrument.
		"""
		return self.instrument.level
		
	#_____________________________________________________________________

	def GetVolume(self):
		"""
		Obtain the instrument volume.
		
		Returns:
			the volume of the instrument.
		"""
		return self.instrument.volume
		
	#_____________________________________________________________________

	def SetVolume(self, vol):
		"""
		Sets the instrument's volume.
		
		Parameters:
			vol -- volume value to set this Instrument's volume to.
		"""
		self.instrument.SetVolume(vol)
		
	#_____________________________________________________________________
	
	def CommitVolume(self):
		self.instrument.CommitVolume()
	
	#_____________________________________________________________________
	
	def OnPanChanged(self, slider):
		"""
		Changes the Instrument's audiopanorama value to the
		one indicated by the slider control.
		It also updates the statusbar when dragging the slider.
		
		Parameters:
			slider -- panning slider control.
		"""
		value = round(slider.get_value(), 2)
		
		# clear any existing status bar messages
		if self.statusbarMsgID is not None:
			self.mainview.ClearStatusBar(self.statusbarMsgID)
		
		# set the statusbar message depending on the current pan value
		if value < 0:
			self.statusbarMsgID = self.mainview.SetStatusBar(_("Current balance is <b>%d%%</b> left") % (-value * 100))
		elif value == 0:
			self.statusbarMsgID = self.mainview.SetStatusBar(_("Current balance is <b>centered</b>"))
		else:
			self.statusbarMsgID = self.mainview.SetStatusBar(_("Current balance is <b>%d%%</b> right") % (value * 100))
		
		#to remove the status bar message in a few seconds
		self.OnTimedStatusBarClear()
		
		self.instrument.pan = value
		self.instrument.panElement.set_property("panorama", value)
		
	#_____________________________________________________________________
	
	def OnPanClicked(self, slider, mouse):
		"""
		Centers the panning slider bar when right clicked.
		
		Parameters:
			slider -- panning slider control.
			mouse -- mouse event that fired this callback.
		"""
		if mouse.button == 3:
			slider.set_value(0.0)
			return True
			
	#_____________________________________________________________________
	
	def OnTimedStatusBarClear(self):
		"""
		Waits for a few seconds and then clears the status bar message.
		"""
		# clear any existing status bar messages
		if self.statusbarMsgID is not None:
			gobject.timeout_add(2000, self.mainview.ClearStatusBar, self.statusbarMsgID)
			self.statusbarMsgID = None
	
	#_____________________________________________________________________
#=========================================================================

#create signal to be emitted by MixerStrip
gobject.signal_new("minimise", MixerStrip, gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())

#=========================================================================

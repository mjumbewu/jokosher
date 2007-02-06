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
		self.mintip = gtk.Tooltips()
		self.mintip.set_tip(self.minbutt, _("Minimize instrument"), None)
		self.minbutt.connect("clicked", self.EmitMinimise)
				
		self.vbox.pack_start(self.minbutt, False)
		
		# the slider label
		balanceLabel = gtk.Label(_("Balance:"))
		self.vbox.pack_start(balanceLabel, False)
		# add the panning slider
		self.panbox = gtk.HBox()
		self.leftlab = gtk.Label(_("L"))
		self.rightlab = gtk.Label(_("R"))
		self.pan = gtk.HScale()
		self.pan.set_range(-1.0, 1.0)
		self.pan.set_increments(0.1, 1.0)
		self.pan.set_draw_value(False)
		self.pantip = gtk.Tooltips()
		self.pantip.set_tip(self.pan, _("Adjust instrument balance. Right-click to center"), None)
		
		if self.instrument.pan:
			self.pan.set_value(self.instrument.pan)
		
		self.pan.connect("value-changed", self.OnPanChanged)
		self.pan.connect("button-press-event", self.OnPanClicked)
		self.panbox.pack_start(self.leftlab, False)
		self.panbox.pack_start(self.pan, True)
		self.panbox.pack_start(self.rightlab, False)
		
		self.vbox.pack_start(self.panbox, False)

		#volume label
		volumeLabel = gtk.Label(_("Volume:"))
		self.vbox.pack_start(volumeLabel, False)
		# VU Meter
		self.vu = VUWidget(self, self.mainview)
		self.vbox.pack_start(self.vu, True, True)
		
		#Control Buttons
		hb = gtk.HBox()
		
		# define the tooltip messages and images for buttons that change states
		self.recTipDisabled = _("Enable this instrument for recording")
		self.recTipEnabled = _("Disable this instrument for recording")
		self.muteTipDisabled = _("Mute - silence this instrument")
		self.muteTipEnabled = _("Unmute - hear this instrument")
		self.soloTipDisabled = _("Activate Solo - silence all other instruments")
		self.soloTipEnabled = _("Deactivate Solo - hear all the instruments")
		
		self.recImgDisabled = gtk.gdk.pixbuf_new_from_file(os.path.join(Globals.IMAGE_PATH, "icon_arm.png"))
		self.recImgEnabled = gtk.gdk.pixbuf_new_from_file(os.path.join(Globals.IMAGE_PATH, "icon_disarm.png"))
		self.soloImgDisabled = gtk.gdk.pixbuf_new_from_file(os.path.join(Globals.IMAGE_PATH, "icon_solo.png"))
		self.soloImgEnabled = gtk.gdk.pixbuf_new_from_file(os.path.join(Globals.IMAGE_PATH, "icon_group.png"))
		self.muteImgDisabled = Utils.GetIconThatMayBeMissing("stock_volume", gtk.ICON_SIZE_BUTTON, False)
		self.muteImgEnabled = Utils.GetIconThatMayBeMissing("stock_volume-mute", gtk.ICON_SIZE_BUTTON, False)
		
		# create the actual buttons and set their initial properties
		self.recButton = gtk.ToggleButton("")
		self.recButton.connect("toggled", self.OnArm)
		self.recTip = gtk.Tooltips()
		self.recTip.set_tip(self.recButton, self.recTipDisabled, None)

		self.muteButton = gtk.ToggleButton("")
		self.muteButton.connect("toggled", self.OnMute)
		self.muteTip = gtk.Tooltips()
		self.muteTip.set_tip(self.muteButton, self.muteTipDisabled, None)
		
		self.soloButton = gtk.ToggleButton("")
		self.soloTip = gtk.Tooltips()
		self.soloTip.set_tip(self.soloButton, self.soloTipDisabled, None)
		self.soloButton.connect("toggled", self.OnSolo)
		
		# add the buttons to the hbox
		hb.add(self.recButton)
		hb.add(self.muteButton)
		hb.add(self.soloButton)
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
		
		self.Update()
		
	#_____________________________________________________________________

	def OnMute(self, widget):
		"""
		Toggles muting the instrument on/off.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.Updating:
			self.instrument.ToggleMuted(False)
	
	#_____________________________________________________________________

	def OnArm(self, widget):
		"""
		Toggles arming the instrument on/off.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.Updating:
			self.instrument.ToggleArmed()
		
	#_____________________________________________________________________
	
	def OnSolo(self, widget):
		"""
		Toggles soloing the instrument on/off.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.Updating:
			self.instrument.ToggleSolo(False)
		
	#_____________________________________________________________________
	
	def EmitMinimise(self, widget):
		"""
		Minimizes the Instrument to the StatusBar.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.emit("minimise")
	
	#_____________________________________________________________________
	
	def Update(self):
		"""
		Updates the MixerStrip interface elements according to the actual
		instrument state (i.e. muted/not muted).
		"""
		self.Updating = True
		
		self.mintip.enable()
		self.label.set_text(self.instrument.name)
		
		# update the mute button image and tooltip
		image = gtk.Image()
		if self.instrument.actuallyIsMuted:
			image.set_from_pixbuf(self.muteImgEnabled)
			self.muteButton.set_image(image)
			self.muteTip.set_tip(self.muteButton, self.muteTipEnabled, None)
		else:
			image.set_from_pixbuf(self.muteImgDisabled)
			self.muteButton.set_image(image)
			self.muteTip.set_tip(self.muteButton, self.muteTipDisabled, None)
		
		# update the arm button image and tooltip	
		image = gtk.Image()
		if self.instrument.isArmed:
			image.set_from_pixbuf(self.recImgEnabled)
			self.recButton.set_image(image)
			self.recTip.set_tip(self.recButton, self.recTipEnabled, None)
		else:
			image.set_from_pixbuf(self.recImgDisabled)
			self.recButton.set_image(image)
			self.recTip.set_tip(self.recButton, self.recTipDisabled, None)
			
		# update the solo button image and tooltip
		image = gtk.Image()
		if self.instrument.isSolo:
			image.set_from_pixbuf(self.soloImgEnabled)
			self.soloButton.set_image(image)
			self.soloTip.set_tip(self.soloButton, self.soloTipEnabled, None)
		else:
			image.set_from_pixbuf(self.soloImgDisabled)
			self.soloButton.set_image(image)
			self.soloTip.set_tip(self.soloButton, self.soloTipDisabled, None)
		
		self.Updating = False
	
	#_____________________________________________________________________
	
	def Destroy(self):
		"""
		Called when the MixerStrip is destroyed. It also emits the
		destroy signal to the VUMixer widget.
		"""
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

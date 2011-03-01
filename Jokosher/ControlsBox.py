#
#       THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#       THE 'COPYING' FILE FOR DETAILS
#
#       ControlsBox.py
#       
#	Contains instrument buttons common to the InstrumentViewer and MixerStrip classes.
#
#-------------------------------------------------------------------------------

import pygtk
pygtk.require("2.0")
import gtk
import os.path
import Globals
import Utils
import InstrumentEffectsDialog
import platform
import gettext
_ = gettext.gettext

#=========================================================================

class ControlsBox(gtk.HBox):

	def __init__(self, project, mainview, instrument, includeEffects=True):
		gtk.Container.__init__(self)
		"""
		Creates a new instance of ControlsBox.

		Parameters:
			mainview -- The Main Jokosher window 
			instrument -- The instrument that the ControlsBox control.
			includeEffects -- Whether the Effects button is included or not.
			This may be extended to include all the buttons.
		"""

		self.project = project
		self.mainview = mainview
		self.instrument = instrument

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
		self.muteImgDisabled = Utils.GetIconThatMayBeMissing("stock_volume", self.recImgEnabled.get_width(), False) # Use size of other control button images if fetching stock image
		self.muteImgEnabled = Utils.GetIconThatMayBeMissing("stock_volume-mute", self.recImgEnabled.get_width(), False)
		
		self.recButton = gtk.ToggleButton()
		self.recButton.set_tooltip_text(self.recTipEnabled)
		self.recButton.connect("toggled", self.OnArm)
		
		self.muteButton = gtk.ToggleButton()
		self.muteButton.connect("toggled", self.OnMute)
		self.muteButton.set_tooltip_text(self.muteTipDisabled)
		
		self.soloButton = gtk.ToggleButton()
		self.soloButton.set_tooltip_text(self.soloTipDisabled)
		self.soloButton.connect("toggled", self.OnSolo)
		
		self.add(self.recButton)
		self.add(self.muteButton)
		self.add(self.soloButton)

		if includeEffects:
			self.propsButton = gtk.Button()
			procimg = gtk.Image()
			procimg.set_from_file(os.path.join(Globals.IMAGE_PATH, "icon_effectsapply.png"))
			self.propsButton.set_image(procimg)
			self.effectsDialog = None		#the instrument effects dialog (to make sure more than one is never opened)

			self.propsButton.connect("clicked", self.OnEffectsButtonClicked)
			self.propsButton.set_tooltip_text(_("Instrument Effects"))
			self.add(self.propsButton)
		
		self.instrument.connect("solo", self.OnInstrumentSolo)
		self.instrument.connect("arm", self.OnInstrumentArm)
		self.instrument.connect("mute", self.OnInstrumentMute)
		
		#initialize the images on the buttons
		for i in (self.OnInstrumentArm, self.OnInstrumentMute, self.OnInstrumentSolo):
			i(self.instrument)

	#_____________________________________________________________________

	def OnMute(self, widget):
		"""
		Toggles muting the instrument on/off.
		It will also update the pressed in/out look of the button.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.Updating:
			self.instrument.ToggleMuted(wasSolo=False)
	
	#_____________________________________________________________________

	def OnArm(self, widget):
		"""
		Toggles arming the instrument on/off.
		It will also update the pressed in/out look of the button.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.Updating:
			self.instrument.ToggleArmed()
		
	#_____________________________________________________________________
	
	def OnSolo(self, widget):
		"""
		Toggles soloing the instrument on/off.
		It will also update the pressed in/out look of the button.
		"""
		if not self.Updating:
			self.instrument.ToggleSolo(False)
	#_____________________________________________________________________

	def OnInstrumentSolo(self, instrument=None):
		"""
		Callback for when the instrument's solo status changes.
		
		Parameters:
			instrument -- the instrument instance that send the signal.
		"""
		self.Updating = True
		self.soloButton.set_active(self.instrument.isSolo)
		self.Updating = False
		
		# update the solo button image and tooltip
		image = gtk.Image()
		if self.instrument.isSolo:
			image.set_from_pixbuf(self.soloImgEnabled)
			self.soloButton.set_image(image)
			self.soloButton.set_tooltip_text(self.soloTipEnabled)
		else:
			image.set_from_pixbuf(self.soloImgDisabled)
			self.soloButton.set_image(image)
			self.soloButton.set_tooltip_text(self.soloTipDisabled)

	#_____________________________________________________________________
	
	def OnInstrumentArm(self, instrument=None):
		"""
		Callback for when the instrument's armed status changes.
		
		Parameters:
			instrument -- the instrument instance that send the signal.
		"""
		self.Updating = True
		self.recButton.set_active(self.instrument.isArmed)
		self.Updating = False
		
		# update the arm button image and tooltip	
		image = gtk.Image()
		if self.instrument.isArmed:
			image.set_from_pixbuf(self.recImgEnabled)
			self.recButton.set_image(image)
			self.recButton.set_tooltip_text(self.recTipEnabled)
		else:
			image.set_from_pixbuf(self.recImgDisabled)
			self.recButton.set_image(image)
			self.recButton.set_tooltip_text(self.recTipDisabled)
	
	#_____________________________________________________________________
	
	def OnInstrumentMute(self, instrument=None):
		"""
		Callback for when the instrument's muted status changes.
		
		Parameters:
			instrument -- the instrument instance that send the signal.
		"""
		self.Updating = True
		self.muteButton.set_active(self.instrument.actuallyIsMuted)
		self.Updating = False
		
		# update the mute button image and tooltip
		image = gtk.Image()
		if self.instrument.actuallyIsMuted:
			image.set_from_pixbuf(self.muteImgEnabled)
			self.muteButton.set_image(image)
			self.muteButton.set_tooltip_text(self.muteTipEnabled)
		else:
			image.set_from_pixbuf(self.muteImgDisabled)
			self.muteButton.set_image(image)
			self.muteButton.set_tooltip_text(self.muteTipDisabled)
	
	#______________________________________________________________________

	def OnEffectsButtonClicked(self, widget):
		"""
		Creates and shows the instrument effects dialog if LADSPA is installed.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- reserved for GTK callbacks, don't use it explicitly.
		"""
		Globals.debug("props button pressed")
		

		if Globals.LADSPA_NAME_MAP:

			if not self.effectsDialog:
				self.effectsDialog = InstrumentEffectsDialog.InstrumentEffectsDialog(
						self.instrument,
						self.OnEffectsDialogDestroyed,
						self.mainview.icon)
			else:
				self.effectsDialog.BringWindowToFront()

		else:
			message = gtk.MessageDialog(parent=None, flags=0, type=gtk.MESSAGE_INFO,buttons=gtk.BUTTONS_OK, message_format=_("You do not have any LADSPA effects plugins installed"))
			if platform.system() == "Windows":
				message.format_secondary_text(_("Jokosher does not currently support any LADSPA plugins on Windows"))
			else:
				message.format_secondary_text(_("Jokosher requires one or more packages of LADSPA effects to be able to use this feature, please install the relevant package(s) for your distribution."))

			message.show_all()
			response = message.run()

			if response == gtk.RESPONSE_OK:
				message.destroy()
 

	#______________________________________________________________________
	
	def OnEffectsDialogDestroyed(self, window):
		"""
		Called when the InstrumentEffectsDialog is destroyed.
		
		Parameters:
			window -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.effectsDialog = None
		
	#______________________________________________________________________
#=========================================================================

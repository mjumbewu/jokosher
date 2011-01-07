#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	TimeLineBar.py
#	
#	This module is the gtk.Frame which sits above the instruments and
#	holds the TImeLine as well as the click track button and the bpm label.
#
#-------------------------------------------------------------------------------

import gtk
import gobject
import gettext
import os
import TimeLine
import Globals
import ui.EventLaneHSeparator as EventLaneHSeparator

# for the time signature combo
from math import log

_=gettext.gettext

class TimeLineBar(gtk.HBox):
	"""
	This class contains the TimeLine widget as well as the click track button and the bpm label in a gtk.Frame widget.
	"""
	#_____________________________________________________________________
	
	def __init__(self, project, mainview):
		"""
		Creates a new instance of TimeLineBar
		
		Parameters:
			project -- reference to Project (Project.py).
			mainview -- reference to MainApp (JokosherApp.py).
		"""
		gtk.HBox.__init__(self)
		
		self.project = project
		self.mainview = mainview
		self.timeline = TimeLine.TimeLine(self.project, mainview)
		self.Updating = False
		
		# add click / bpm / signature box
		self.clickbutton = gtk.VolumeButton()
		self.clickbutton.set_value(0)
		self.clickbutton.set_relief(gtk.RELIEF_NORMAL)
		self.clickbutton.set_property("size", gtk.ICON_SIZE_BUTTON)
		
		self.clickbutton_metronome_image = gtk.Image()
		self.clickbutton_metronome_image.set_from_file(os.path.join(Globals.IMAGE_PATH, "icon_click.png"))
		# use get_child() not get_image here because GtkScaleButton
		# uses gtk_container_add() in its internal implementation
		self.clickbutton_volume_image = self.clickbutton.get_child()
		self.clickbutton.set_image(self.clickbutton_metronome_image)
		
		image_size_group = gtk.SizeGroup(gtk.SIZE_GROUP_BOTH)
		image_size_group.add_widget(self.clickbutton_metronome_image)
		image_size_group.add_widget(self.clickbutton_volume_image)
		
		self.clickbutton.set_tooltip_text(_("Adjust volume of click track"))
					
		self.bpmeventbox = gtk.EventBox()
		self.bpmframe = gtk.Frame()
		self.bpmeventbox.set_tooltip_text(_("Beats per minute"))
		self.bpmframe.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
		
		self.bpmlabel = gtk.Label()
		self.bpmlabel.set_use_markup(True)
		self.bpmlabel.set_markup("<b>%s</b>" % (self.project.bpm))
		self.bpmlabel.set_padding(5, 5)
		self.bpmeventbox.add(self.bpmlabel)
		self.bpmframe.add(self.bpmeventbox)
		
		self.bpmedit = gtk.SpinButton()
		self.bpmedit.set_range(1, 400)
		self.bpmedit.set_increments(1, 5)
		self.bpmedit.set_value(self.project.bpm)
		self.bpmedit.connect("activate", self.OnAcceptEditBPM)
		self.bpmedit.connect("key_press_event", self.OnEditBPMKey)
		self.bpmedit.connect_after("button-release-event", self.OnEditBPMClick)

		self.sigeventbox = gtk.EventBox()
		self.sigeventbox.set_tooltip_text(_("Time signature"))
		self.sigframe = gtk.Frame()
		self.sigframe.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
		
		self.siglabel = gtk.Label()
		self.siglabel.set_use_markup(True)
		self.siglabel.set_markup("<b>%d/%d</b>" % (self.project.meter_nom, self.project.meter_denom))
		self.siglabel.set_padding(5, 5)
		self.sigeventbox.add(self.siglabel)
		self.sigframe.add(self.sigeventbox)
		self.sigeditPacked = False

		# set events
		self.clickbutton.connect("value-changed", self.OnClickTrackVolume)
		self.clickbutton.connect("enter_notify_event", self.OnClickButtonEnter)
		self.clickbutton.connect("leave_notify_event", self.OnClickButtonEnter)
		
		self.bpmeventbox.set_events(gtk.gdk.BUTTON_PRESS_MASK)
		self.bpmeventbox.connect("button_release_event", self.OnEditBPM)
		self.bpmeventbox.connect("enter_notify_event", self.OnMouseMoveBPM)
		self.bpmeventbox.connect("leave_notify_event", self.OnMouseMoveBPM)
		
		self.sigeventbox.set_events(gtk.gdk.BUTTON_PRESS_MASK)
		self.sigeventbox.connect("button_press_event", self.OnEditSig)
		self.sigeventbox.connect("enter_notify_event", self.OnMouseMoveTimeSig)
		self.sigeventbox.connect("leave_notify_event", self.OnMouseMoveTimeSig)
		
		self.project.connect("bpm", self.OnProjectBPMChange)
		self.project.connect("time-signature", self.OnProjectSigChange)
		self.project.connect("click-track", self.OnProjectClickTrackChange)

		self.sigDialog = None
		
		# ###########################################################
		
		self.headerhbox = gtk.HBox()
		self.headerhbox.set_border_width(2)
		self.headerhbox.set_spacing(5)
		self.headerhbox.pack_start(self.clickbutton, True, True)
		self.headerhbox.pack_start(self.bpmframe, True, True)
		self.headerhbox.pack_start(self.sigframe, True, True)
		
		self.headerVBox = gtk.VBox()
		self.headerVBox.pack_start(self.headerhbox, True, True)
		self.headerVBox.pack_start(gtk.HSeparator(), False, False)
		
		self.timelineVBox = gtk.VBox()
		self.timelineVBox.pack_start(self.timeline, True, True)
		separator = EventLaneHSeparator.EventLaneHSeparator(self.project, self.project.transport)
		self.timelineVBox.pack_start(separator, False, False)
		
		self.pack_start(self.headerVBox, False, False)
		self.pack_start(self.timelineVBox)	

	#_____________________________________________________________________
	
	def GetHeaderWidget(self):
		"""
			Returns the widget which is required to be aligned with the instrument headers.
		"""
		return self.headerVBox
	
	#_____________________________________________________________________
	
	def OnProjectBPMChange(self, project):
		"""
		Callback for when the BPM of the project changes. This method 
		will update the contents of the beats per minute box.
		
		Parameters:
			project -- The project that send the signal.
		"""
		#Do this outside the if statement so that it gets updated if someone else changes the bpm
		self.bpmlabel.set_use_markup(True)
		self.bpmlabel.set_markup("<b>%d</b>" % (self.project.bpm))
		
	#_____________________________________________________________________
	
	def OnProjectSigChange(self, project):
		"""
		Callback for when the BPM of the project changes. This method 
		will update the contents of the time signature label.
		
		Parameters:
			project -- The project that send the signal.
		"""
		self.siglabel.set_use_markup(True)
		self.siglabel.set_markup("<b>%d/%d</b>" % (self.project.meter_nom, self.project.meter_denom))
		
	#_____________________________________________________________________
	
	def OnProjectClickTrackChange(self, project, value):
		"""
		Callback for when the click track of the project it turned on
		or shut off. This method will update the button and tooltip state.
		
		Parameters:
			project -- The project that send the signal.
			value -- The new value of the click track volume.
		"""
		self.Updating = True
		self.clickbutton.set_value(value)
		self.Updating = False
		
	#_____________________________________________________________________
	
	def OnEditBPM(self, widget, event):
		"""
		Called when the user clicks the beats per minute box.
		This method will show a spin button widget with a value inside which the user can change.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if event.type == gtk.gdk.BUTTON_RELEASE:
			startWidth = self.headerhbox.size_request()[0]
			
			if self.bpmeventbox.parent:
				self.bpmframe.remove(self.bpmeventbox)
				self.bpmframe.add(self.bpmedit)
				self.bpmedit.show()
				
				self.bpmedit.grab_add()
				self.bpmedit.grab_focus()

	#_____________________________________________________________________
	
	def OnAcceptEditBPM(self, widget=None, cancel=False):
		"""
		Called when the user finishes editing the beats per minute box.
		This method then updates the beats per minute value to the value the user 
		enters.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.bpmedit.grab_remove()
		
		if self.bpmedit.parent:
			self.bpmframe.remove(self.bpmedit)
			self.bpmframe.add(self.bpmeventbox)
			self.bpmframe.show_all()
			
			if not cancel:
				newbpm = self.bpmedit.get_value_as_int()
				self.project.SetBPM(float(newbpm))
		
	#_____________________________________________________________________
	
	def OnEditBPMClick(self, widget, event):
		"""
		Handles the button presses while doing a grab on the bpm edit spinbutton.
		If we get a mouse event, it means the user has clicked outside the spinbutton.
		So then we save what the user edited and go back to a label.
		"""
		if event.type == gtk.gdk.BUTTON_RELEASE:
			self.OnAcceptEditBPM()
			return True

	#_____________________________________________________________________

	def OnEditBPMKey(self, widget, event):
		"""
		Handles the key presses while editing the instrument name label.
		Used to make the escape key save the name and then return to normal mode.
		
		Parameters:
			widget -- GTK callback.
			event -- GTK callback.
		"""
		key = gtk.gdk.keyval_name(event.keyval)
		
		if key == "Escape":
			self.OnAcceptEditBPM(cancel=True)
			return True

	#_____________________________________________________________________

	def OnEditSig(self, widget, event):
		"""
		Called when the user clicks the time signature box.
		This method will show a dialog for changing the time signature.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		""" 
		if event.type == gtk.gdk.BUTTON_PRESS:
			if not self.sigDialog:
				self.gtk_builder = Globals.LoadGtkBuilderFilename("TimeSignatureDialog.ui")
		
				signals = {
					"on_spinBeats_value_changed" : self.OnNomValueChange,
					"on_comboValue_changed" : self.OnDenomValueChange,
					"on_buttonClose_clicked" : self.OnSigDialogClose
				}
				self.gtk_builder.connect_signals(signals)

				# references to GUI widgets
				self.sigDialog = self.gtk_builder.get_object("TimeSignatureDialog")
				self.spinBeats = self.gtk_builder.get_object("spinBeats")
				self.comboValue = self.gtk_builder.get_object("comboValue")
				
				# set some properties for the widgets
				self.sigDialog.set_icon(self.mainview.icon)
				self.spinBeats.set_value(self.project.meter_nom)
				self.comboValue.set_active(int(log(self.project.meter_denom, 2)))
			else:
				self.sigDialog.present()
			
	#_____________________________________________________________________
	
	def OnNomValueChange(self, spinButton):
		"""
		Updates the Project's beats per measure value.
		
		Parameters:
			combobox -- beats per measure combobox.
		"""
		self.project.SetMeter(int(spinButton.get_value()),
							  self.project.meter_denom)
		
	#_____________________________________________________________________
		
	def OnDenomValueChange(self, combobox):
		"""
		Updates the Project's beat value.
		
		Parameters:
			spinButton -- beat value spin button.
		"""
		self.project.SetMeter(self.project.meter_nom,
							  int(combobox.get_active_text()))
	
	#_____________________________________________________________________
	
	def OnSigDialogClose(self, button):
		"""
		Closes the time signature settings dialog.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.sigDialog.destroy()
		self.sigDialog = None

	#_____________________________________________________________________
	
	def OnMouseMoveBPM(self, widget, event):
		"""
		Called when the mouse pointer enters or leaves the beats per minute box.
		This method changes the type of cursor if the mouse pointer is hovered over the beats per minute box.
				
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not widget.window: 
			return
		
		if (event.type == gtk.gdk.ENTER_NOTIFY):
			widget.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
		else:
			widget.window.set_cursor(None)
			
	#_____________________________________________________________________
	
	def OnMouseMoveTimeSig(self, widget, event):
		"""
		Called when the mouse pointer enters or leaves the beats per minute box.
		This method changes the type of cursor if the mouse pointer is hovered over the beats per minute box.
				
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not widget.window: 
			return
		
		if (event.type == gtk.gdk.ENTER_NOTIFY):
			self.sigeventbox.set_state(gtk.STATE_PRELIGHT)
		else:
			self.sigeventbox.set_state(gtk.STATE_NORMAL)
			
	#_____________________________________________________________________

	def OnClickTrackVolume(self, widget, value):
		"""
		Called when the click button is clicked. This method will call the project
		to set the volume of the click track.
		""" 
		if not self.Updating:
			self.project.SetClickTrackVolume(value)
			
	#_____________________________________________________________________
	
	def OnClickButtonEnter(self, widget, event):
		if event.type == gtk.gdk.ENTER_NOTIFY:
			self.clickbutton.set_image(self.clickbutton_volume_image)
		elif event.type == gtk.gdk.LEAVE_NOTIFY:
			self.clickbutton.set_image(self.clickbutton_metronome_image)
		
	#_____________________________________________________________________
	
#=========================================================================

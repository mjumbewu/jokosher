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
import TimeLine
import gettext
import os
import Globals
import gobject

# for the time signature combo
from math import log

_=gettext.gettext

class TimeLineBar(gtk.Frame):
	"""
	This class contains the TimeLine widget as well as the click track button and the bpm label in a gtk.Frame widget.
	"""
	#_____________________________________________________________________
	
	def __init__(self, project, projectview, mainview):
		"""
		Creates a new instance of TimeLineBar
		
		Parameters:
			project -- reference to Project (Project.py).
			projectview -- reference to RecordingView (RecordingView.py).
			mainview -- reference to MainApp (JokosherApp.py).
		"""
		gtk.Frame.__init__(self)
		
		self.project = project
		self.projectview = projectview
		self.mainview = mainview
		self.timeline = TimeLine.TimeLine(self.project, self, mainview)
		self.Updating = False
		
		self.bgColor = "#73d216"
		self.bgActiveColor = "#81eb17"
		self.fontColor = "#0b410b"
		
		# add click / bpm / signature box
		self.clickbutton = gtk.ToggleButton()
		self.clicktip = gtk.Tooltips()
		clickimg = gtk.Image()
		clickimg.set_from_file(os.path.join(Globals.IMAGE_PATH, "icon_click.png"))
		self.clickbutton.set_image(clickimg)

		self.clicktip.set_tip(self.clickbutton, _("Turn click track on"), None)
		self.clickbutton.connect("toggled", self.OnClick)
					
		self.bpmeventbox = gtk.EventBox()
		self.bpmeventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.bgColor))
		self.bpmframe = gtk.Frame()
		self.bpmeventtip = gtk.Tooltips()
		self.bpmeventtip.set_tip(self.bpmeventbox, _("Beats per minute"), None)
		self.bpmframe.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
		self.bpmframe.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.bgColor))
		
		self.bpmlabel = gtk.Label()
		self.bpmlabel.set_use_markup(True)
		self.bpmlabel.set_markup("<span foreground='%s'><b>%s</b></span>" % (self.fontColor, self.project.bpm))
		self.bpmlabel.set_padding(5, 5)
		self.bpmeventbox.add(self.bpmlabel)
		self.bpmframe.add(self.bpmeventbox)
		self.bpmeditPacked = False

		self.sigeventbox = gtk.EventBox()
		self.sigeventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.bgColor))
		self.sigeventtip = gtk.Tooltips()
		self.sigeventtip.set_tip(self.sigeventbox, _("Time signature"), None)
		self.sigframe = gtk.Frame()
		self.sigframe.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
		self.sigframe.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.bgColor))

		self.siglabel = gtk.Label()
		self.siglabel.set_use_markup(True)
		self.siglabel.set_markup("<span foreground='%s'><b>%d/%d</b></span>" % (self.fontColor, self.project.meter_nom, self.project.meter_denom))
		self.siglabel.set_padding(5, 5)
		self.sigeventbox.add(self.siglabel)
		self.sigframe.add(self.sigeventbox)
		self.sigeditPacked = False

		# set events
		self.bpmeventbox.set_events(gtk.gdk.BUTTON_PRESS_MASK)
		self.bpmeventbox.connect("button_press_event", self.OnEditBPM)
		self.bpmeventbox.connect("enter_notify_event", self.OnMouseMoveBPM)
		self.bpmeventbox.connect("leave_notify_event", self.OnMouseMoveBPM)
		
		self.sigeventbox.set_events(gtk.gdk.BUTTON_PRESS_MASK)
		self.sigeventbox.connect("button_press_event", self.OnEditSig)
		self.sigeventbox.connect("enter_notify_event", self.OnMouseMoveTimeSig)
		self.sigeventbox.connect("leave_notify_event", self.OnMouseMoveTimeSig)

		self.sigDialog = None
		
		# ###########################################################
		
		self.headerhbox = gtk.HBox()
		self.headerhbox.set_border_width(2)
		self.headerhbox.set_spacing(5)
		self.headerhbox.pack_start(self.clickbutton, True, True)
		self.headerhbox.pack_start(self.bpmframe, True, True)
		self.headerhbox.pack_start(self.sigframe, True, True)
		
		self.hbox = gtk.HBox()
		self.alignment = gtk.Alignment(0, 0, 1.0, 1.0)
		self.alignment.add(self.headerhbox)
		self.hbox.pack_start(self.alignment, False, False)
		self.add(self.hbox)
		self.headerhbox.connect("check-resize", self.projectview.Update)
		self.connect("size-allocate", self.OnAllocate)
		self.hbox.pack_start(self.timeline)	

	#_____________________________________________________________________

	def OnAllocate(self, widget, allocation):
		"""
		From:
		http://www.moeraki.com/pygtkreference/pygtk2reference/class-gtkwidget.html#signal-gtkwidget--size-allocate
		The "size-allocate" signal is emitted when widget is given a new space allocation.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly. 
			allocation -- the position and size to be allocated to the widget.
		"""
		self.allocation = allocation

	#_____________________________________________________________________
	
	def Update(self):
		""" 
		Updates the contents TimeLineBar, updating the values in the beats per
		minute box and time signature box, as well as updating the click button
		sensitivity and instrument header width.
		"""
		if not self.Updating:
			instrumentviews=[]
			if self.mainview.recording:
				instrumentviews+=self.mainview.recording.views
			if self.mainview.compactmix:
				instrumentviews+=self.mainview.compactmix.projectview.views

			self.Updating = True
			maxwidth=self.headerhbox.size_request()[0]
	
			for ident, iv in instrumentviews:  #self.mainview.recording.views:
				if iv.instrument in iv.mainview.project.instruments:
					if iv.headerBox.size_request()[0] > maxwidth:
						maxwidth = iv.headerBox.size_request()[0]

			for ident, iv in instrumentviews:  #self.mainview.recording.views:
				if iv.headerAlign.size_request()[0] != (maxwidth+2):
					iv.ResizeHeader(maxwidth+2)
			
			Globals.INSTRUMENT_HEADER_WIDTH = maxwidth + 2
			
			self.alignment.set_padding(0, 0, 0, maxwidth - self.headerhbox.size_request()[0])

			self.clickbutton.set_active(self.project.clickEnabled)
			self.OnAcceptEditBPM()
			self.UpdateSigLabel()
			self.timeline.queue_draw()
			
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
		if event.type == gtk.gdk.BUTTON_PRESS:
			startWidth = self.headerhbox.size_request()[0]
			self.bpmframe.remove(self.bpmeventbox)
						
			self.bpmedit = gtk.SpinButton()
			self.bpmedit.set_range(1, 400)
			self.bpmedit.set_increments(1, 5)
			self.bpmedit.set_value(self.project.bpm)
			self.bpmedit.connect("activate", self.OnAcceptEditBPM)

			self.bpmframe.add(self.bpmedit)
			self.bpmedit.show()
			self.bpmedit.grab_focus()
			self.bpmeditPacked = True
			#adjust padding so that the timeline event lanes still line up
			newWidth = self.headerhbox.size_request()[0]
			padding = self.alignment.get_padding()
			self.alignment.set_padding(0, 0, 0, padding[3] - (newWidth -startWidth))

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
				self.sigDialogTree = gtk.glade.XML(Globals.GLADE_PATH, "TimeSignatureDialog")
		
				signals = {
					"on_spinBeats_value_changed" : self.OnNomValueChange,
					"on_comboValue_changed" : self.OnDenomValueChange,
					"on_buttonClose_clicked" : self.OnSigDialogClose
				}
				
				self.sigDialogTree.signal_autoconnect(signals)

				# references to GUI widgets
				self.sigDialog = self.sigDialogTree.get_widget("TimeSignatureDialog")
				self.spinBeats = self.sigDialogTree.get_widget("spinBeats")
				self.comboValue = self.sigDialogTree.get_widget("comboValue")
				
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
		self.projectview.UpdateSize()
	
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
	
	def UpdateSigLabel(self):
		"""
		Updates the time signature label in the main Jokosher window.
		"""
		self.siglabel.set_use_markup(True)
		self.siglabel.set_markup("<span foreground='%s'><b>%d/%d</b></span>" % (self.fontColor, self.project.meter_nom, self.project.meter_denom))
		self.projectview.UpdateSize()
		
	#_____________________________________________________________________
	
	def OnAcceptEditBPM(self, widget=None):
		"""
		Called when the user finishes editing the beats per minute box.
		This method then updates the beats per minute value to the value the user 
		enters and then writes that change to disk if the user saves the project. 
		If anything but OnEditBPM calls this method, it will update the contents of the beats per minute box.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.bpmeditPacked:
			self.bpmframe.remove(self.bpmedit)
			#FIXME: find a better way to do project.PrepareClick() it doesn't take a really long time with large bpm
			newbpm = self.bpmedit.get_value_as_int()
			
			self.project.SetBPM(float(newbpm))
			self.project.PrepareClick()
			
			self.bpmframe.add(self.bpmeventbox)
			self.bpmedit.destroy()
			self.bpmframe.show_all()
			self.bpmeditPacked = False
		
		#Do this outside the if statement so that it gets updated if someone else changes the bpm
		self.bpmlabel.set_use_markup(True)
		self.bpmlabel.set_markup("<span foreground='%s'><b>%d</b></span>" % (self.fontColor, self.project.bpm))
		self.bpmeventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.bgColor))
			
		self.projectview.UpdateSize()
		
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
			self.bpmeventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.bgActiveColor))
		else:
			widget.window.set_cursor(None)
			self.bpmeventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.bgColor))
			
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
			self.sigeventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.bgActiveColor))
		else:
			self.sigeventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(self.bgColor))
			
	#_____________________________________________________________________

	def OnClick(self, widget):
		"""
		Called when the click button is clicked.
		This method will also set the clicked button to appear pressed in if clicked.
		If the click button is clicked while in a 'pressed in' state. It will appear as it did originally.
		""" 
		if widget.get_active() == True:
			self.project.EnableClick()
			self.clicktip.set_tip(self.clickbutton, _("Turn click track off"), None)
		if widget.get_active() == False:
			self.project.DisableClick()
			self.clicktip.set_tip(self.clickbutton, _("Turn click track on"), None)
			
	#_____________________________________________________________________
		
#=========================================================================

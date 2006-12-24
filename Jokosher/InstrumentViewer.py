#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	InstrumentViewer.py
#	
#	Encapsulate the customised track viewing and editing control
#
#-------------------------------------------------------------------------------

import gtk
import pango
from Project import *
from EventLaneViewer import *
import Globals
import InstrumentEffectsDialog
import AddInstrumentDialog
import gettext
_ = gettext.gettext

#=========================================================================	

class InstrumentViewer(gtk.EventBox):
	""" 
		Class to encapsulate the customised track viewing and editing control.
	"""

	EDGE_DISTANCE = 5				# Size of event edge handle
	EDGE_HOT_ZONE = 10				# Size of 'hot zone' used to trigger drawing of edge handle
	BAR_WIDTH = 15
	MAX_PEAK = 30
	LABEL_WIDTH_CHARS = 12
	UNSELECTED_COLOUR = None
	SELECTED_COLOUR = None
	
	INSTR_DRAG_TYPE = 83			# Number only to be used inside Jokosher
	DRAG_TARGETS = [ ( "jokosher_instr_move", 	# A custom name for the instruments
					   gtk.TARGET_SAME_APP,		# Only move inside Jo
					   INSTR_DRAG_TYPE )]		# Use the custom number
	
	#_____________________________________________________________________
	
	def __init__(self, project, instrument, projectview, mainview, small = False):
		gtk.EventBox.__init__(self)
		"""
		Creates a new instance of InstrumentViewer.
		
		Parameters:
			project - the current active Project
			instrument - the Instrument that the event lane belongs
			instrumentviewer - the InstrumentViewer holding the event lane
			projectview - the RecordingView instance that this belongs to
			mainview - reference to the mainwindow in JokosherApp
			small - set to True if we want small edit views (i.e. for mix view)
		"""
		self.instrument = instrument
		self.project = project
		self.small = small
		self.projectview = projectview
		self.mainview = mainview
		self.instrument.AddListener(self)
		self.effectsDialog = None		#the instrument effects dialog (to make sure more than one is never opened)
		
		self.Updating = False
		
		#get the default colour for the current theme
		self.UNSELECTED_COLOR = self.get_style().bg[0]
		
		
		self.mainBox = gtk.HBox()
		self.add(self.mainBox)
		
		self.headerBox = gtk.VBox()
		self.headerEventBox = gtk.EventBox()
		self.headerEventBox.add(self.headerBox)
		self.headerAlign = gtk.Alignment(0, 0, 1.0, 1.0)
		self.headerAlign.add(self.headerEventBox)
		self.eventLane = EventLaneViewer(project, instrument, self, mainview, self.small)
		
		self.mainBox.pack_start(self.headerAlign, False, False)
		self.mainBox.pack_end(self.eventLane, True, True)

		# create track header bits
		self.labelbox = gtk.HBox()
		self.labelbox.set_spacing(6)
		self.labeleventbox = gtk.EventBox()
		self.instrlabel = gtk.Label(self.instrument.name)
		self.instrlabel.set_ellipsize(pango.ELLIPSIZE_END)
		self.instrlabel.set_width_chars(self.LABEL_WIDTH_CHARS)
		self.editlabel = gtk.Entry()
		self.editlabel.set_text(self.instrument.name)
		self.editlabelPacked = False

		# add the label to the event box
		self.labeleventbox.add(self.instrlabel)

		# set events
		self.labeleventbox.set_events(gtk.gdk.BUTTON_PRESS_MASK | 
						gtk.gdk.ENTER_NOTIFY |
						gtk.gdk.LEAVE_NOTIFY )
		self.labeleventbox.connect("button_press_event", self.OnEditLabel)
		self.labeleventbox.connect("enter_notify_event", self.OnMouseMove)
		self.labeleventbox.connect("leave_notify_event", self.OnMouseMove)
		self.connect("button_press_event", self.OnSelect)
		
		#load missing image icon if instrument has no icon
		if not self.instrument.pixbuf:
			self.instrument.pixbuf = self.render_icon(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_DIALOG)
		
		self.image = gtk.Image()
		if not (self.small):
			self.image.set_from_pixbuf(self.instrument.pixbuf)
		else:
			pb = self.instrument.pixbuf.scale_simple(20, 20, gtk.gdk.INTERP_BILINEAR)
			self.image.set_from_pixbuf(pb)
		
		self.labelbox.pack_start(self.image, False)
		self.labelbox.pack_end(self.labeleventbox)
		self.headerBox.pack_start(self.labelbox)
		self.controlsBox = gtk.HBox()
		self.headerBox.pack_start(self.controlsBox, False)
		
		if not (self.small):
			recimg = gtk.image_new_from_stock(gtk.STOCK_MEDIA_RECORD, gtk.ICON_SIZE_BUTTON)
			self.recTip = gtk.Tooltips()
			self.recButton = gtk.ToggleButton("")
			self.recButton.set_property("image", recimg)
			self.recTip.set_tip(self.recButton, _("Enable this instrument for recording"), None)
			self.recButton.connect("toggled", self.OnArm)
			
			self.muteButton = gtk.ToggleButton("")
			self.muteButton.connect("toggled", self.OnMute)
			self.muteTip = gtk.Tooltips()
			self.muteTip.set_tip(self.muteButton, _("Mute - silence this instrument"), None)
			
			soloimg = gtk.Image()
			soloimg.set_from_file(os.path.join(Globals.IMAGE_PATH, "icon_solo.png"))
			self.soloButton = gtk.ToggleButton("")
			self.soloButton.set_image(soloimg)
			self.soloTip = gtk.Tooltips()
			self.soloTip.set_tip(self.soloButton, _("Solo - silence all other instruments"), None)
			#self.recButton.set_property("image", soloimg)
			self.soloButton.connect("toggled", self.OnSolo)
			
			self.propsButton = gtk.Button()
			procimg = gtk.Image()
			procimg.set_from_file(os.path.join(Globals.IMAGE_PATH, "icon_effectsapply.png"))
			self.propsButton.set_image(procimg)

			self.propsButton.connect("button_press_event", self.OnInstrumentEffects)
			self.propsTip = gtk.Tooltips()
			self.propsTip.set_tip(self.propsButton, _("Instrument Effects"), None)
			
			self.controlsBox.add(self.recButton)
			self.controlsBox.add(self.muteButton)
			self.controlsBox.add(self.soloButton)
			self.controlsBox.add(self.propsButton)
		else:
			self.separator = gtk.HSeparator()
			self.headerBox.pack_end(self.separator, False, True)
		self.instrument.isSelected = False
		
		# Begin Drag and Drop code
		self.headerEventBox.drag_dest_set(gtk.DEST_DEFAULT_MOTION,
										  self.DRAG_TARGETS, 
										  gtk.gdk.ACTION_MOVE)
		self.headerEventBox.connect('drag_motion', self.OnDragMotion)
		self.headerEventBox.drag_source_set(gtk.gdk.BUTTON1_MASK, 
										    self.DRAG_TARGETS, 
										    gtk.gdk.ACTION_MOVE)
		# Connect to drag_begin to add a custom icon
		self.headerEventBox.connect('drag_begin', self.OnDragBegin)
		self.headerEventBox.connect('drag_drop', self.OnDragDrop)

	#_____________________________________________________________________

	def OnMute(self, widget):
		"""
		Called when the mute button is clicked.
		This method will also set the mute button to appear pressed in if clicked.
		If the mute button is clicked while in a 'pressed in' state. It will appear as it did originally.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.Updating:
			self.instrument.ToggleMuted(wasSolo=False)
	
	#_____________________________________________________________________

	def OnArm(self, widget):
		"""
		Called when the record button is clicked.
		This method will also set the record button to appear pressed in if clicked.
		If the record button is clicked while in a 'pressed in' state. It will appear as it did originally.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.Updating:
			self.instrument.ToggleArmed()
		
	#_____________________________________________________________________
	
	def OnSolo(self, widget):
		"""
		Called when the solo button is clicked.
		This method will also set the solo button to appear pressed in if clicked.
		If the solo button is clicked while in a 'pressed in' state. It will appear as it did originally.
		"""
		if not self.Updating:
			self.instrument.ToggleSolo(False)
		
	#_____________________________________________________________________

	def OnSelect(self, widget, event):
		"""
		Called when a button has been pressed anywhere within InstrumentViewer.
		This method sets the instrument to a selected state
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if 'GDK_CONTROL_MASK' in event.state.value_names:
			self.instrument.SetSelected(True)
		else:
			self.project.ClearEventSelections()
			self.project.SelectInstrument(self.instrument)
		
		return True

	#_____________________________________________________________________

	def OnEditLabel(self, widget, event):
		"""
		Called when a button has been pressed within the instrument name label.
		This method shows a text entry that allows the user to change the name of an instrument
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.instrument.isSelected:
			self.OnSelect(widget, event)
			# Don't edit label unless the user clicks while we are already selected
			return True
			
		# replace label with gtk.Entry in order to edit it
		if event.type == gtk.gdk.BUTTON_PRESS:
			#save width of label because when its hidden, width == 0
			width = self.labeleventbox.size_request()[0]
			self.labeleventbox.hide_all()
			
			self.editlabel = gtk.Entry()
			self.editlabel.set_text(self.instrument.name)
			#set the entry to the same width as the label so that the header doesnt resize
			self.editlabel.set_size_request(width, -1)
			self.editlabel.connect("activate", self.OnAcceptEditLabel)
			self.editlabel.show()
			
			self.labelbox.pack_end(self.editlabel)
			self.editlabel.grab_focus()
			self.editlabelPacked = True
			self.mainview.instrNameEntry = self.editlabel
			return True
	
	#_____________________________________________________________________

	def OnAcceptEditLabel(self, widget=None):
		"""
		Called after the instrument label has been edited.
		This method updates the instrument label with the label the user entered.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		# change instrument name then replace edit label with normak label
		if self.editlabelPacked:	
			name = self.editlabel.get_text()
			if name != "":
				self.instrlabel.set_text(name)
			self.labelbox.remove(self.editlabel)
			self.editlabelPacked = False
			self.mainview.instrNameEntry = None
			if self.editlabel:
				self.editlabel.destroy()
			self.labeleventbox.show_all()
			
			if name != "" and name != self.instrument.name:
				#this must be done last because it triggers update
				self.instrument.SetName(name)
		
	#_____________________________________________________________________
	
	def Destroy(self):
		"""
		Called when the InstrumentViewer is closed
		This method destroys the InstrumentViewer.
		"""
		self.instrument.RemoveListener(self)
		self.eventLane.Destroy()
		self.destroy()
	
	#_____________________________________________________________________
	
	def Update(self):
		"""
		Called when requested by projectview.Update() to update
		the display.
		This method updates the display in response to a change in state in any object
		is it listening to.
		This method then calls EventLaneViewer.Update()
		to update its EventLaneViewer.
		"""
		self.Updating = True

		if not self.small:
			self.recButton.set_active(self.instrument.isArmed)
			self.recTip.enable()
			self.muteButton.set_active(self.instrument.actuallyIsMuted)
			self.soloButton.set_active(self.instrument.isSolo)
			self.soloTip.enable()
		
			if self.instrument.actuallyIsMuted:
				self.muteButton.set_image(gtk.image_new_from_icon_name("stock_volume-mute", gtk.ICON_SIZE_BUTTON))
				self.muteTip.set_tip(self.muteButton, _("Muted"), None)
			else:
				self.muteButton.set_image(gtk.image_new_from_icon_name("stock_volume", gtk.ICON_SIZE_BUTTON))
				self.muteTip.set_tip(self.muteButton, _("Unmuted"), None)
		
		if self.instrument.isSelected:
			#For some reason, putting self.style.base[3] in __init__ makes it return the wrong colour.
			self.SELECTED_COLOUR = self.get_style().base[3]
			
			self.modify_bg(gtk.STATE_NORMAL, self.SELECTED_COLOUR)
			self.headerEventBox.modify_bg(gtk.STATE_NORMAL, self.SELECTED_COLOUR)
			self.labeleventbox.modify_bg(gtk.STATE_NORMAL, self.SELECTED_COLOUR)
			self.eventLane.modify_bg(gtk.STATE_NORMAL, self.SELECTED_COLOUR)
			
		else:
			self.modify_bg(gtk.STATE_NORMAL, self.UNSELECTED_COLOUR)
			self.headerEventBox.modify_bg(gtk.STATE_NORMAL, self.UNSELECTED_COLOUR)
			self.labeleventbox.modify_bg(gtk.STATE_NORMAL, self.UNSELECTED_COLOUR)
			self.eventLane.modify_bg(gtk.STATE_NORMAL, self.UNSELECTED_COLOUR)

		self.instrlabel.set_text(self.instrument.name)
		if self.editlabelPacked:
			self.OnAcceptEditLabel()
		self.eventLane.Update()
		self.Updating = False

	#______________________________________________________________________

	def OnMouseMove(self, widget, event):
		"""
		Called when the mouse cursor enters or leaves the instrument name label area.
		This method changes the cursor to show text is edittable 
		when hovered over the instrument label area.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.window: return
		if (event.type == gtk.gdk.ENTER_NOTIFY):
			self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
		else:
			self.window.set_cursor(None)
			
	#______________________________________________________________________

	def ResizeHeader(self, width):
		"""
		Called when a request is made to resize the instrument area.
		This method updates the padding space of the header box in order to line
		up correctly with the timeline display. 
		NOTE: Not called here but from TimeLineBar.py
		
		Parameters:
			width -- the width of the instrument header box
		"""
		padding = width - self.headerBox.size_request()[0]
		self.headerAlign.set_padding(0, 0, 0, padding)


	#______________________________________________________________________

	def OnInstrumentEffects(self, widget, mouse):
		"""
		Creates and shows the instrument effects dialog
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- reserved for GTK callbacks, don't use it explicitly.
		"""
		Globals.debug("props button pressed")
		if not self.effectsDialog:
			self.effectsDialog = InstrumentEffectsDialog.InstrumentEffectsDialog(self.instrument, self.OnInstrumentEffectsDestroyed)
		else:
			self.effectsDialog.BringWindowToFront()

	#______________________________________________________________________
	
	def OnInstrumentEffectsDestroyed(self, window):
		"""
		Called when a request is made to destroy the InstrumentEffectsDialog.
		This method destroys the InstrumentEffectsDialog.
		
		Parameters:
			window -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.effectsDialog = None
		
	#______________________________________________________________________
	
	def OnDragMotion(self, widget, context, x, y, time):
		"""
		Called each time the user moves his/her mouse while dragging.
		'if' clause checks if mouse is on an instrument that isn't the
		source instrument. 
		If so, this method then swaps that instrument and the
		source instrument in the GUI. Swapping of the Instrument objects
		in self.project.instruments happens in OnDragDrop().
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			context -- a cairo context widget.
			x -- reserved for GTK callbacks, don't use it explicitly.
			y -- reserved for GTK callbacks, don't use it explicitly.
			time -- reserved for GTK callbacks, don't use it explicitly.
		"""
		source = context.get_source_widget() 	# Will return an EventBox (self.headerEventBox)
		if widget != source:					# Dont swap with self
			box = self.GetInstrumentViewVBox()
			iv_array = box.get_children()				# InstrumentView array
			index_iv = iv_array.index(self)
			
			source_iv = [iv for iv in iv_array if iv.headerEventBox == source][0]
			index_source_iv = iv_array.index(source_iv)
			
			box.reorder_child(source_iv, index_iv)		# Immediate visual feedback
		# Without these lines the icon would fly back to the start of the drag when dropping
		context.drag_status(gtk.gdk.ACTION_MOVE, time)
		return True

	#______________________________________________________________________
	
	def OnDragBegin(self, widget, context):
		"""
		Called when the drag and drop procedure begins.
		This method will display the instrument icon when dragging.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			context -- a cairo context widget.
		"""
		widget.drag_source_set_icon_pixbuf(self.instrument.pixbuf)
		return True
	
	#______________________________________________________________________
	
	def OnDragDrop(self, widget, context, x, y, time):
		"""
		Called when the user releases MOUSE1.
		This method calls MoveInstrument, which moves the dragged
		instrument to the end position in the
		self.project.instruments array.
		MoveInstrument is undo-able.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			context -- a cairo context widget.
			x -- reserved for GTK callbacks, don't use it explicitly.
			y -- reserved for GTK callbacks, don't use it explicitly.
		"""
		id = self.instrument.id
		box = self.GetInstrumentViewVBox()
		position = box.get_children().index(self)
		
		if self.project.instruments.index(self.instrument) == position:
			#there is no change in position
			return
		
		self.project.MoveInstrument(id, position)
		context.finish(True, False, time)
	
	#______________________________________________________________________

	def GetInstrumentViewVBox(self):
		"""
		Returns:
			self.projectview.instrumentbox -- returns the instrumentBox if the current view is a RecordingView.
			self.projectview.time -- returns the timebox if the current view is a CompactMixView.
		"""
		if hasattr(self.projectview, "instrumentBox"):
			return self.projectview.instrumentBox
		else:
			return self.projectview.timebox
	
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None, *extra):
		"""
		Called when a change of state is signalled by any of the
		objects this view is 'listening' to.
		
		Parameters:
			obj -- object changing state. *CHECK*
			change -- the change which has occured.
			extra -- extra parameters passed by the caller.
		"""
		if change == "image":
			self.image.clear()
			self.image.set_from_pixbuf(self.instrument.pixbuf)
	
	#______________________________________________________________________

	def OnChangeInstrumentType(self, widget, event):
		"""
		Called when a button has been pressed in the instrument header icon.
		This method displays the change instrument dialog, allowing the user to change a selected instrument.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.instrument.isSelected:
			self.OnSelect(widget, event)
			# Don't edit type unless the user clicks while we are already selected
			return True
		
		AddInstrumentDialog.AddInstrumentDialog(self.project, self.mainview, self.instrument)
		    
	#______________________________________________________________________


	#=========================================================================	

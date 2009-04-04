#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	InstrumentViewer.py
#	
#	Encapsulate the customised track viewing and editing control.
#
#-------------------------------------------------------------------------------

import gtk
import pango
from EventLaneViewer import *
import Globals
import AddInstrumentDialog
import ControlsBox
import Utils
import gettext
_ = gettext.gettext

#=========================================================================	

class InstrumentViewer(gtk.EventBox):
	""" 
	Encapsulates the customized track viewing and editing control.
	"""
	
	""" Size of the instrument name label """
	LABEL_WIDTH_CHARS = 12
	
	""" Widget color when unselected """
	UNSELECTED_COLOUR = None
	
	""" Widget color when selected """
	SELECTED_COLOUR = None
	
	""" Number only to be used inside Jokosher """
	INSTR_DRAG_TYPE = 83
	
	""" Custom numbers for use while dragging audio in Jokosher """
	DRAG_TARGETS = [ ( "jokosher_instr_move", 	# A custom name for the instruments
					   gtk.TARGET_SAME_APP,		# Only move inside Jo
					   INSTR_DRAG_TYPE )]		# Use the custom number
	
	"""
	   The events we wish to receive after we grab the mouse (and it is no longer above this widget)
	   If events other than mouse event are put in here, it may cause the program to crash.
	"""
	_POINTER_GRAB_EVENTS = (
			gtk.gdk.BUTTON_RELEASE_MASK |
			gtk.gdk.BUTTON_PRESS_MASK)
	
	#_____________________________________________________________________
	
	def __init__(self, project, instrument, projectview, mainview, small = False):
		gtk.EventBox.__init__(self)
		"""
		Creates a new instance of InstrumentViewer.
		
		Parameters:
			project -- the currently active Project.
			instrument -- the instrument that the event lane belongs.
			instrumentviewer - the InstrumentViewer holding the event lane.
			projectview - the RecordingView instance that this belongs to.
			mainview - the MainApp Jokosher window.
			small - set to True if we want small edit views (i.e. for mixing view).
		"""
		self.instrument = instrument
		self.project = project
		self.small = small
		self.projectview = projectview
		self.mainview = mainview
		
		self.Updating = False
		
		#get the default colour for the current theme
		self.UNSELECTED_COLOR = self.rc_get_style().bg[gtk.STATE_NORMAL]
		#use base instead of bg colours so that we get the lighter colour that is used for list items in TreeView.
		self.SELECTED_COLOUR = self.rc_get_style().base[gtk.STATE_SELECTED]
		
		self.mainBox = gtk.HBox()
		self.add(self.mainBox)
		
		self.headerBox = gtk.VBox()
		self.headerEventBox = gtk.EventBox()
		self.headerEventBox.add(self.headerBox)
		self.eventLane = EventLaneViewer(project, instrument, self, mainview, self.small)
		
		self.mainBox.pack_start(self.headerEventBox, False, False)
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
		self.editlabel.connect("activate", self.OnAcceptEditLabel)
		self.editlabel.connect("key_press_event", self.OnEditLabelKey)
		self.editlabel.connect_after("button-press-event", self.OnEditLabelClick)
		self.editlabel.connect_after("button-release-event", self.OnEditLabelClick)
		self.editlabel_is_mouse_down = False
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
		self.controlsBox = ControlsBox.ControlsBox(project,mainview,instrument,includeEffects=True)
		self.headerBox.pack_start(self.controlsBox, False)
		
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
		self.headerEventBox.connect('drag_end', self.OnDragEnd)
		
		self.instrument.connect("name", self.OnInstrumentName)
		self.instrument.connect("image", self.OnInstrumentImage)
		self.instrument.connect("selected", self.OnInstrumentSelected)

		#set the appropriate colour if the instrument it already selected.
		self.OnInstrumentSelected()
		self.show_all()
		self.labelbox.show()
		if self.small:
			self.controlsBox.hide()

	#_____________________________________________________________________
	
	def GetHeaderWidget(self):
		"""
			Returns the widget which is required to be aligned with the instrument headers.
		"""
		return self.headerBox
	
	#_____________________________________________________________________

	def OnSelect(self, widget, event):
		"""
		Called when a button has been pressed anywhere within InstrumentViewer.
		This method sets the instrument to a selected state.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		
		Returns:
			True -- continue GTK signal propagation. *CHECK*
		"""
		
		if self.instrument.project.GetIsRecording():
			return
		
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
		This method shows a text entry that allows the user to change the name
		of the correspondent Instrument
		
		Parameters:
			widget -- GTK callback.
			event -- GTK callback.
			
		Returns:
			True -- continue GTK signal propagation.
		"""
		if not self.instrument.isSelected:
			# Don't edit label unless the user clicks while we are already selected
			# return false so that the event is handled by the parent widget.
			return False
			
		# replace label with gtk.Entry in order to edit it
		if event.type == gtk.gdk.BUTTON_PRESS:
			#save width of label because when its hidden, width == 0
			width = self.labeleventbox.size_request()[0]
			
			self.editlabel.set_text(self.instrument.name)
			#set the entry to the same width as the label so that the header doesnt resize
			self.editlabel.set_size_request(width, -1)
			self.editlabel.show()
			
			self.labelbox.remove(self.labeleventbox)
			self.labelbox.pack_end(self.editlabel)
			
			self.editlabel.grab_add()
			self.editlabel.grab_focus()
			
			self.editlabelPacked = True
			self.editlabel_is_mouse_down = False
			self.mainview.instrNameEntry = self.editlabel
			
			return True
	
	#_____________________________________________________________________
	
	def OnEditLabelClick(self, widget, event):
		"""
		Handles the button presses while doing a grab on the editing label.
		We need to keep track of both BUTTON_PRESS and BUTTON_RELEASE because:
			1) if the mouse click is on the gtk.Entry, release will be forwarded, press will not.
			2) if the mouse is outside the gtk.Entry, both press and release will be forwarded.
		Therefore if we get both press and release together, we accept the changed and remove the edit dialog.
		"""
		if event.type == gtk.gdk.BUTTON_PRESS:
			self.editlabel_is_mouse_down = True
			return True
		elif event.type == gtk.gdk.BUTTON_RELEASE and self.editlabel_is_mouse_down:
			self.OnAcceptEditLabel()
			return True

	#_____________________________________________________________________

	def OnEditLabelKey(self, widget, event):
		"""
		Handles the key presses while editing the instrument name label.
		Used to make the escape key save the name and then return to normal mode.
		
		Parameters:
			widget -- GTK callback.
			event -- GTK callback.
		"""
		key = gtk.gdk.keyval_name(event.keyval)
		
		if key == "Escape":
			self.editlabel.set_text("")
			self.OnAcceptEditLabel()
			return True

	#_____________________________________________________________________

	def OnAcceptEditLabel(self, widget=None):
		"""
		Called after the instrument label has been edited.
		This method updates the instrument label with the label the user entered.
		
		Parameters:
			widget -- GTK callback.
		"""
		self.editlabel.grab_remove()
		# change instrument name then replace edit label with normal label
		if self.editlabelPacked:
			name = self.editlabel.get_text()
			if name != "":
				self.instrlabel.set_text(name)
			self.labelbox.remove(self.editlabel)
			self.editlabelPacked = False
			self.mainview.instrNameEntry = None
			self.labelbox.pack_end(self.labeleventbox)
			
			if name != "" and name != self.instrument.name:
				#this must be done last because it triggers update
				self.instrument.SetName(name)
		
	#_____________________________________________________________________
	
	def Destroy(self):
		"""
		Called when the InstrumentViewer is closed
		This method also destroys the corresponding EventLaneViewer.
		"""
		self.instrument.disconnect_by_func(self.OnInstrumentImage)
		self.eventLane.Destroy()
		self.destroy()
	
	#_____________________________________________________________________
	
	def OnInstrumentSelected(self, instrument=None):
		"""
		Callback for when the instrument's selected status changes.
		
		Parameters:
			instrument -- the instrument instance that send the signal.
		"""
		if self.instrument.isSelected:
			self.modify_bg(gtk.STATE_NORMAL, self.SELECTED_COLOUR)
			self.headerEventBox.modify_bg(gtk.STATE_NORMAL, self.SELECTED_COLOUR)
			self.labeleventbox.modify_bg(gtk.STATE_NORMAL, self.SELECTED_COLOUR)
			self.eventLane.modify_bg(gtk.STATE_NORMAL, self.SELECTED_COLOUR)
			
		else:
			self.modify_bg(gtk.STATE_NORMAL, self.UNSELECTED_COLOUR)
			self.headerEventBox.modify_bg(gtk.STATE_NORMAL, self.UNSELECTED_COLOUR)
			self.labeleventbox.modify_bg(gtk.STATE_NORMAL, self.UNSELECTED_COLOUR)
			self.eventLane.modify_bg(gtk.STATE_NORMAL, self.UNSELECTED_COLOUR)
	
	#______________________________________________________________________

	def OnInstrumentName(self, instrument=None):
		"""
		Callback for when the instrument's name changes.
		
		Parameters:
			instrument -- the instrument instance that send the signal.
		"""
		self.instrlabel.set_text(self.instrument.name)
	
	#_____________________________________________________________________
	
	def OnMouseMove(self, widget, event):
		"""
		Called when the mouse cursor enters or leaves the instrument name label area.
		This method changes the cursor to show text is editable 
		when hovered over the instrument label area.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.window or self.instrument.project.GetIsRecording():
			return
		if (event.type == gtk.gdk.ENTER_NOTIFY):
			self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
		else:
			self.window.set_cursor(None)
			
	#______________________________________________________________________

	def OnDragMotion(self, widget, context, x, y, time):
		"""
		Called each time the user moves the mouse while dragging.
		If the mouse is on an instrument that isn't the source
		instrument, it swaps that instrument and the source instrument
		in the GUI. Swapping of the Instrument objects in self.project.instruments
		happens in OnDragDrop().
		
		Parameters:
			widget -- InstrumentViewer the mouse is hovering over.
			context -- cairo widget context. Used to extract the source instrument.
			x -- reserved for GTK callbacks, don't use it explicitly.
			y -- reserved for GTK callbacks, don't use it explicitly.
			time -- reserved for GTK callbacks, don't use it explicitly.
		
		Returns:
			True -- continue GTK signal propagation. *CHECK*
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
		Called when the user releases MOUSE1, finishing a drag and drop
		procedure. This callback will only be called if the drag is dropped
		on a widget that can handle the drop event. Otherwise only the
		"drag_end" signal will be emitted, This is why the MoveInstrument()
		function is called in OnDragEnd().
			
		Parameters:
			widget -- InstrumentViewer being dragged.
			context -- reserved for GTK callbacks, don't use it explicitly.
			x -- reserved for GTK callbacks, don't use it explicitly.
			y -- reserved for GTK callbacks, don't use it explicitly.
			time -- reserved for GTK callbacks, don't use it explicitly.
		"""
		box = self.GetInstrumentViewVBox()
		position = box.get_children().index(self)
		
		if self.project.instruments.index(self.instrument) == position:
			#there is no change in position
			context.finish(False, False, time)
		else:
			context.finish(True, False, time)
	
	#______________________________________________________________________
	
	def OnDragEnd(self, widget, context):
		"""
		Called when the user releases MOUSE1, finishing a drag and drop
		procedure. This callback will only be called if the drag is dropped
		on a widget that can handle the drop event. Otherwise only the
		"drag_end" signal will be emitted, This is why the MoveInstrument()
		function is called in OnDragEnd().
		Calls MoveInstrument, which moves the dragged instrument to
		the end position in the self.project.instruments array.
		
		Considerations:
			the MoveInstrument action is undo-able.
			
		Parameters:
			widget -- InstrumentViewer being dragged.
			context -- reserved for GTK callbacks, don't use it explicitly.
			x -- reserved for GTK callbacks, don't use it explicitly.
			y -- reserved for GTK callbacks, don't use it explicitly.
			time -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		box = self.GetInstrumentViewVBox()
		position = box.get_children().index(self)
		
		if self.project.instruments.index(self.instrument) != position:
			#there was a change in position
			id = self.instrument.id
			self.project.MoveInstrument(id, position)
		
	#______________________________________________________________________

	def GetInstrumentViewVBox(self):
		"""
		Obtain the current Instrument view box.
		
		Returns:
			the instrumentBox if the current view is a RecordingView.
			the timebox if the current view is a CompactMixView.
		"""
		if hasattr(self.projectview, "instrumentBox"):
			return self.projectview.instrumentBox
		else:
			return self.projectview.timebox
	
	#_____________________________________________________________________
	
	def OnInstrumentImage(self, instrument):
		"""
		Callback for when the instrument's image changes.
		
		Parameters:
			instrument -- the instrument instance that send the signal.
		"""
		self.image.clear()
		self.image.set_from_pixbuf(self.instrument.pixbuf)
		
	#______________________________________________________________________

	def OnChangeInstrumentType(self, widget, event):
		"""
		Called when a button has been pressed in the instrument header icon.
		This method displays the AddInstrumentDialog, allowing the user
		to change the selected instrument.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
			
		Returns:
			True -- if there's no instrument selected, select one and then
					continue GTK signal propagation. *CHECK*
		"""
		if not self.instrument.isSelected:
			self.OnSelect(widget, event)
			# Don't edit type unless the user clicks while we are already selected
			return True
		
		AddInstrumentDialog.AddInstrumentDialog(self.project, self.mainview, self.instrument)
		    
	#______________________________________________________________________

	def ChangeSize(self, small):
		"""
		Changes the size of the instrument viewer
		
		Parameters:
			small -- True if the instrument viewer is to be small.
		"""
		self.small = small
		self.eventLane.ChangeSize(small)
		if self.small:
			pb = self.instrument.pixbuf.scale_simple(20, 20, gtk.gdk.INTERP_BILINEAR)
			self.image.set_from_pixbuf(pb)
			self.controlsBox.hide()
			self.separator.show()
		else:
			self.image.set_from_pixbuf(self.instrument.pixbuf)
			self.controlsBox.show()
			self.separator.hide()

	#____________________________________________________________________	
#=========================================================================	

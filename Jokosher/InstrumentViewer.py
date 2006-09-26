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
import Waveform
import Globals
import InstrumentEffectsDialog
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
			project - the current active project
			instrument - the instrument that the event lane belongs
			instrumentviewer - the instrumentviewer holding the event lane
			projectview - the RecordingView instance that this belongs to
			mainview - the main Jokosher window
			small - set to True if we want small edit views (i.e. for mix view)
		"""
		self.instrument = instrument
		self.project = project
		self.small = small
		self.projectview = projectview
		self.mainview = mainview
		
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
		self.labeleventbox = gtk.EventBox()
		self.instrlabel = gtk.Label(self.instrument.name)	
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
		
		image = gtk.Image()
		if not (self.small):
			image.set_from_pixbuf(self.instrument.pixbuf)
		else:
			pb = self.instrument.pixbuf.scale_simple(20, 20, gtk.gdk.INTERP_BILINEAR)
			image.set_from_pixbuf(pb)
		
		self.labelbox.pack_start(image, False)
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
			soloimg.set_from_file(os.path.join(Globals.IMAGE_PATH, "solo.png"))
			self.soloButton = gtk.ToggleButton("")
			self.soloButton.set_image(soloimg)
			self.soloTip = gtk.Tooltips()
			self.soloTip.set_tip(self.soloButton, _("Solo - silence all other instruments"), None)
			#self.recButton.set_property("image", soloimg)
			self.soloButton.connect("toggled", self.OnSolo)
			
			self.propsButton = gtk.Button("In")
			self.propsButton.connect("button_press_event", self.OnProcessingMenu)
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
			Callback for "toggle" signal on Mute button
		"""
		if not self.Updating:
			self.instrument.ToggleMuted(wasSolo=False)
	
	#_____________________________________________________________________

	def OnArm(self, widget):
		"""
			Callback for "toggle" signal on Record button
		"""
		if not self.Updating:
			self.instrument.ToggleArmed()
		
	#_____________________________________________________________________
	
	def OnSolo(self, widget):
		"""
			Callback for "toggle" signal on Solo button
		"""
		if not self.Updating:
			self.instrument.ToggleSolo(False)
		
	#_____________________________________________________________________

	def OnSelect(self, widget, event):
		"""
			Callback for "button_press_event" anywhere within InstrumentViewer
			Sets instrument to selected state
		"""
		if 'GDK_CONTROL_MASK' not in event.state.value_names:
			self.project.ClearEventSelections()
			self.project.ClearInstrumentSelections()
		self.instrument.SetSelected(True)
		return True

	#_____________________________________________________________________

	def OnEditLabel(self, widget, event):
		"""
			Callback for "button_press_event" in the instrument name label
		"""
		if not self.instrument.isSelected:
			self.OnSelect(widget, event)
			# Don't edit label unless the user clicks while we are already selected
			return True
			
		# replace label with gtk.Entry in order to edit it
		if event.type == gtk.gdk.BUTTON_PRESS:
			self.labeleventbox.hide_all()
			
			self.editlabel = gtk.Entry()
			self.editlabel.set_text(self.instrument.name)
			self.editlabel.set_width_chars(len(self.instrument.name))
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
			Called when the instrument label has been edited
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
	
	def Update(self):
		"""
			Called when requested by projectview.Update() to update
			the display in response to a change in state in any object
			it is listening to. In turn calls EventLaneViewer.Update()
			for its EventLaneViewer.
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
			Callback for "enter_notify_event" and "leave_notify_event"
			for the instrument name label. Changes cursor to show the 
			text is edittable
		"""
		if not self.window: return
		if (event.type == gtk.gdk.ENTER_NOTIFY):
			self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
		else:
			self.window.set_cursor(None)

	def ResizeHeader(self, width):
		"""
			Changes the padding space of the header box in order to line
			up correctly with the timeline display. 
			NOTE: Not called here but from TimeLineBar.py
		"""
		padding = width - self.headerBox.size_request()[0]
		self.headerAlign.set_padding(0, 0, 0, padding)


	#______________________________________________________________________

	def OnInstrumentEffects(self, widget):
		""" Creates and shows the instrument effects dialog"""
		Globals.debug("props button pressed")
		newdlg = InstrumentEffectsDialog.InstrumentEffectsDialog(self.instrument)
		#if destroyCallback:
		#	newdlg.dlg.connect("destroy", destroyCallback)


	#______________________________________________________________________

	def OnProcessingMenu(self, widget, mouse):
		"""
			Callback for "button_press_event" on the properties button.
			Pops up a menu (currently only Instrument Effects).
		"""
		m = gtk.Menu() 
		items = [(_("Instrument Effects..."), self.OnInstrumentEffects)] 
		for i, cb in items:
			a = gtk.MenuItem(label=i)
			a.show() 
			m.append(a)
			if cb:
				a.connect("activate", cb)

		m.popup(None, None, None, mouse.button, mouse.time)
	
	#______________________________________________________________________
	
	def OnDragMotion(self, widget, context, x, y, time):
		'''
			Called each time the user moves his/her mouse while dragging.
			'if' clause checks if mouse is on an instrument that isn't the
			source instrument. If so, it swaps that instrument and the
			source instrument in the GUI. Swapping of the Instrument objects
			in self.project.instruments happens in OnDragDrop().
		'''
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
		'''
			Called at the start of the drag and drop.
			Displays the instrument icon when dragging.
		'''
		widget.drag_source_set_icon_pixbuf(self.instrument.pixbuf)
		return True
	
	#______________________________________________________________________
	
	def OnDragDrop(self, widget, context, x, y, time):
		'''
			Called when the user releases MOUSE1.
			Calls MoveInstrument, which moves the dragged
			instrument to the end position in the
			self.project.instruments array.
			MoveInstrument is undo-able.
		'''
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
		'''
			Returns the instrumentBox if the current view is a RecordingView.
			Returns the timebox if the current view is a CompactMixView.
		'''
		if hasattr(self.projectview, "instrumentBox"):
			return self.projectview.instrumentBox
		else:
			return self.projectview.timebox
	
	#=========================================================================	

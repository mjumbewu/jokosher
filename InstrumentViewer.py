
import gtk
import pango
from Project import *
from EventLaneViewer import *
import Waveform

#=========================================================================	

class InstrumentViewer(gtk.EventBox):
	""" Class to encapsulate the customised track viewing and editing control. """

	EDGE_DISTANCE = 5				# Size of event edge handle
	EDGE_HOT_ZONE = 10				# Size of 'hot zone' used to trigger drawing of edge handle
	BAR_WIDTH = 15
	MAX_PEAK = 30
	UNSELECTED_COLOUR = None
	SELECTED_COLOUR = None
	
	#_____________________________________________________________________
	
	def __init__(self, project, instrument, projectview, mainview, small = False):
		gtk.EventBox.__init__(self)
		
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
		self.headerAlign = gtk.Alignment(0, 0, 1.0, 1.0)
		self.headerAlign.add(self.headerBox)
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
		
		self.labelbox.set_size_request(0, -1)
		
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
			self.recButton = gtk.ToggleButton("")
			self.recButton.set_property("image", recimg)
			self.recButton.connect("toggled", self.OnArm)
			
			self.muteButton = gtk.ToggleButton("")
			self.muteButton.connect("toggled", self.OnMute)
			
			soloimg = gtk.Image()
			soloimg.set_from_file(os.path.join(Globals.JOKOSHER_PATH, "images", "solo.png"))
			self.soloButton = gtk.ToggleButton("")
			self.soloButton.set_image(soloimg)
			#self.recButton.set_property("image", soloimg)
			self.soloButton.connect("toggled", self.OnSolo)
			
			self.sourceButton = gtk.ToggleButton("In")
			
			self.controlsBox.add(self.recButton)
			self.controlsBox.add(self.muteButton)
			self.controlsBox.add(self.soloButton)
			self.controlsBox.add(self.sourceButton)
		else:
			self.separator = gtk.HSeparator()
			self.headerBox.pack_end(self.separator, False, True)
		self.instrument.isSelected = False

	#_____________________________________________________________________

	def OnMute(self, widget):
		if not self.Updating:
			self.instrument.ToggleMuted(wasSolo=False)
	
	#_____________________________________________________________________

	def OnArm(self, widget):
		if not self.Updating:
			self.instrument.ToggleArmed()
		
	#_____________________________________________________________________
	
	def OnSolo(self, widget):
		if not self.Updating:
			self.instrument.ToggleSolo(False)
		
	#_____________________________________________________________________

	def OnSelect(self, widget, event):
		if 'GDK_CONTROL_MASK' not in event.state.value_names:
			self.project.ClearEventSelections()
			self.project.ClearInstrumentSelections()
		self.instrument.SetSelected(True)
		return True

	#_____________________________________________________________________

	def OnEditLabel(self, widget, event):
		self.OnSelect(widget, event)
		if event.type == gtk.gdk.BUTTON_PRESS:
			self.labeleventbox.hide_all()
			
			self.editlabel = gtk.Entry()
			self.editlabel.set_text(self.instrument.name)
			self.editlabel.connect("activate", self.OnAcceptEditLabel)
			self.editlabel.show()
			
			self.labelbox.pack_end(self.editlabel)
			self.editlabel.grab_focus()
			self.editlabelPacked = True
			self.mainview.instrNameEntry = self.editlabel
			return True
	
	#_____________________________________________________________________

	def OnAcceptEditLabel(self, widget=None):
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
		self.Updating = True

		if not self.small:
			self.recButton.set_active(self.instrument.isArmed)
			self.muteButton.set_active(self.instrument.actuallyIsMuted)
			self.soloButton.set_active(self.instrument.isSolo)
		
			if self.instrument.actuallyIsMuted:
				self.muteButton.set_image(gtk.image_new_from_icon_name("stock_volume-mute", gtk.ICON_SIZE_BUTTON))
			else:
				self.muteButton.set_image(gtk.image_new_from_icon_name("stock_volume", gtk.ICON_SIZE_BUTTON))
		
		if self.instrument.isSelected:
			#For some reason, putting self.style.base[3] in __init__ makes it return the wrong colour.
			self.SELECTED_COLOUR = self.get_style().base[3]
			
			self.modify_bg(gtk.STATE_NORMAL, self.SELECTED_COLOUR)
			self.labeleventbox.modify_bg(gtk.STATE_NORMAL, self.SELECTED_COLOUR)
			self.eventLane.modify_bg(gtk.STATE_NORMAL, self.SELECTED_COLOUR)
			
		else:
			self.modify_bg(gtk.STATE_NORMAL, self.UNSELECTED_COLOUR)
			self.labeleventbox.modify_bg(gtk.STATE_NORMAL, self.UNSELECTED_COLOUR)
			self.eventLane.modify_bg(gtk.STATE_NORMAL, self.UNSELECTED_COLOUR)
		
		self.instrlabel.set_text(self.instrument.name)
		if self.editlabelPacked:
			self.OnAcceptEditLabel()
		self.eventLane.Update()
		self.Updating = False

	#______________________________________________________________________

	def OnMouseMove(self, widget, event):
		if not self.window: return
		if (event.type == gtk.gdk.ENTER_NOTIFY):
			self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
		else:
			self.window.set_cursor(None)

	def ResizeHeader(self, width):
		padding = width - self.headerBox.size_request()[0]
		self.headerAlign.set_padding(0, 0, 0, padding)

#=========================================================================	


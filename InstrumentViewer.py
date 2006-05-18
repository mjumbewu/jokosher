
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
	SELECTED_COLOUR = gtk.gdk.Color(int(65535*0.9), int(65535*0.9), 65535)
	
	#_____________________________________________________________________
	
	def __init__(self, project, instrument, small = False):
		gtk.EventBox.__init__(self)
		
		self.instrument = instrument
		self.project = project
		self.small = small
		
		self.Updating = False
		
		#get the default colour for the current theme
		self.UNSELECTED_COLOR = self.get_style().bg[0]
		
		self.mainBox = gtk.HBox()
		self.add(self.mainBox)
		
		self.headerBox = gtk.VBox()
		self.eventLane = EventLaneViewer(project, instrument, self.small)
																	
		self.mainBox.pack_start(self.headerBox, False, False)
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
		self.headerBox.pack_start(self.labelbox, False, False)
		self.controlsBox = gtk.HBox()
		self.headerBox.add(self.controlsBox)
		
		if not (self.small):
			img = gtk.image_new_from_stock(gtk.STOCK_MEDIA_RECORD, gtk.ICON_SIZE_BUTTON)
			self.recButton = gtk.ToggleButton("")
			self.recButton.set_property("image", img)
			self.recButton.connect("toggled", self.OnArm)

			self.muteButton = gtk.ToggleButton("Mute")
			self.muteButton.connect("toggled", self.OnMute)
			
			self.soloButton = gtk.ToggleButton("Solo")
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

	def OnSelect(self, widget, event=None):
		self.instrument.SetSelected()
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
	
	#_____________________________________________________________________

	def OnAcceptEditLabel(self, widget=None):
		if self.editlabelPacked:	
			name = self.editlabel.get_text()
			self.instrlabel.set_text(name)
			self.labelbox.remove(self.editlabel)
			self.editlabelPacked = False
			if self.editlabel:
				self.editlabel.destroy()
			self.labeleventbox.show_all()
			
			#this must be done last because it triggers update
			self.instrument.SetName(name)
		
	#_____________________________________________________________________
	
	def Update(self):
		self.Updating = True
		if not self.small:
			self.recButton.set_active(self.instrument.isArmed)
			self.muteButton.set_active(self.instrument.actuallyIsMuted)
			self.soloButton.set_active(self.instrument.isSolo)
		
		if self.instrument.isSelected:
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

#=========================================================================	


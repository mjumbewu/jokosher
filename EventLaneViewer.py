
import gtk, Instrument
from EventViewer import *

#=========================================================================

class EventLaneViewer(gtk.EventBox):

	#_____________________________________________________________________

	def __init__(self, project, instrument, small = False):
		gtk.EventBox.__init__(self)

		self.small = small
		self.vbox = gtk.VBox()
		self.fixed = gtk.Fixed()

		self.separator = gtk.HSeparator()
		self.vbox.pack_start(self.fixed, True, True)
		self.vbox.pack_end(self.separator, False, True)

		self.vbox.show_all()
		self.add(self.vbox)
		self.show_all()
			
		self.project = project
		self.instrument = instrument
		self.project.transport.AddListener(self)
		self.project.AddListener(self)
		self.instrument.AddListener(self)
		
		# This defines where the blue cursor indicator should be drawn (in pixels)
		self.highlightCursor = None
		
		# True if the popup menu is visible
		self.popupIsActive = False
		
		# True if the cursor is inside a child event object
		self.childActive = False
		
		self.set_events(	gtk.gdk.POINTER_MOTION_MASK |
							gtk.gdk.BUTTON_RELEASE_MASK |
							gtk.gdk.BUTTON_PRESS_MASK )
		
		self.connect("button-press-event", self.OnMouseDown)
		self.connect("motion_notify_event", self.OnMouseMove)
		self.connect("leave_notify_event", self.OnMouseLeave)
		self.fixed.connect("expose-event", self.OnDraw)
		
		self.Update()
		
	#_____________________________________________________________________
		
	def OnDraw(self, widget, event):

		d = widget.window
		gc = d.new_gc()
		
		transport = self.project.transport
		
		# Draw lane edges
		col = gc.get_colormap().alloc_color("#666666")
		gc.set_foreground(col)
		d.draw_line(gc, 0, self.allocation.height-1, self.allocation.width-1, self.allocation.height-1)
		
		# Draw play cursor position
		col = gc.get_colormap().alloc_color("#FF0000")
		gc.set_foreground(col)
		
		pos = transport.position - self.project.viewStart
		x = int(pos * self.project.viewScale)
		d.draw_line(gc, x, 0, x, self.allocation.height)
		
		# Draw edit position
		if self.highlightCursor and not self.childActive:
			col = gc.get_colormap().alloc_color("#0000FF")
			gc.set_foreground(col)
			d.draw_line(gc, int(self.highlightCursor), 0, int(self.highlightCursor), self.allocation.height)
		
	#_____________________________________________________________________
		
	def Update(self, child=None):
		
		if child:
			x = int((child.event.start - self.project.viewStart) * self.project.viewScale)
			self.fixed.move( child, x, 0 )
		else:
			# Get a list of the active EventViewer widgets
			widgets = []
			self.fixed.foreach(lambda x: widgets.append(x))
			widgets = [x for x in widgets if type(x) == EventViewer]
			
			# Move them to the correct positions
			for w in widgets:
				x = int((w.event.start - self.project.viewStart) * self.project.viewScale)
				self.fixed.move(w, x, 0)
				
			# Check if any events have been deleted
			for w in widgets:
				if w.event not in self.instrument.events:
					self.fixed.remove(w)
					self.childActive = False

			# Check if any events have been added
			widget_events = [w.event for w in widgets]
			for ev in self.instrument.events:
				if ev not in widget_events:
					x = int((ev.start - self.project.viewStart) * self.project.viewScale)
					child = EventViewer(self, self.project, ev, self.allocation.height, self.small)
					self.fixed.put(	child, x, 0)
				
			self.fixed.show_all()
		self.queue_draw()
			
	#_____________________________________________________________________

	def OnMouseDown(self, widget, mouse):
		
		if self.childActive:
			return
		
		# Create context menu on RMB 
		if mouse.button == 3: 
			m = gtk.Menu() 
			items = [	("Create Event From File", self.CreateEventFromFile),
					 ] 

			for i, cb in items: 
				if i == "---":
					a = gtk.SeparatorMenuItem()
				else:
					a = gtk.MenuItem(label=i) 
				a.show() 
				m.append(a) 
				if cb:
					a.connect("activate", cb) 
			self.highlightCursor = mouse.x
			self.popupIsActive = True

			m.popup(None, None, None, mouse.button, mouse.time)
			m.connect("selection-done",self.OnMenuDone)
			
	#_____________________________________________________________________
	
	def OnMenuDone(self, widget):
		self.popupIsActive = False
		self.highlightCursor = None
	
	#_____________________________________________________________________

	def OnMouseMove(self, widget, mouse):
		# TODO - we need to add code here to snap to beat/bar etc.
		self.highlightCursor = mouse.x
		self.queue_draw()
		
	#_____________________________________________________________________
		
	def OnMouseLeave(self, widget, mouse):
		if not self.popupIsActive:
			self.highlightCursor = None
		self.queue_draw()

	#_____________________________________________________________________
	
	def CreateEventFromFile(self, evt):
		dlg = gtk.FileChooserDialog("Import file...", action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=(("Select", 1)))
		dlg.connect("response", self.OnDialogResponse)
		dlg.connect("file-activated", self.OnDialogResponse)
		dlg.run()
	
	#_____________________________________________________________________
	
	def OnDialogResponse(self, dlg, evt=None):
		if evt == None or evt == 1:
			dlg.hide()
			self.instrument.addEventFromFile(0, dlg.get_filename())
		dlg.destroy()
		self.Update()
		
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None):
		if type(obj) == type(self.project) or type(obj) == Instrument.Instrument:
			self.Update()
		else:
			x1 = int((self.project.transport.PrevPosition - self.project.viewStart) * self.project.viewScale)
			x2 = int((self.project.transport.position - self.project.viewStart) * self.project.viewScale)
			self.queue_draw_area(min(x1,x2), 0, 1 + abs(x2 - x1), self.allocation.height)
		
	#_____________________________________________________________________
	
#=========================================================================

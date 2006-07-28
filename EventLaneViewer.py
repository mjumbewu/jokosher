
import gtk, Instrument
from EventViewer import *
from AudioPreview import AudioPreview
import Monitored
import os.path

#=========================================================================

class EventLaneViewer(gtk.EventBox):

	#_____________________________________________________________________

	def __init__(self, project, instrument, instrumentviewer, mainview, small = False):
		gtk.EventBox.__init__(self)

		self.small = small
		self.instrumentviewer = instrumentviewer
		self.mainview = mainview
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
		
		#The position where the last mouse click was
		self.mouseDownPos = [0,0]
		
		# True if the cursor is inside a child event object
		self.childActive = False
		
		self.set_events(	gtk.gdk.POINTER_MOTION_MASK |
							gtk.gdk.BUTTON_RELEASE_MASK |
							gtk.gdk.BUTTON_PRESS_MASK )
		
		self.connect("button-press-event", self.OnMouseDown)
		self.connect("motion_notify_event", self.OnMouseMove)
		self.connect("leave_notify_event", self.OnMouseLeave)
		self.fixed.connect("expose-event", self.OnDraw)
		
		self.messageID = None
		
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
		
		x = int(round((transport.position - self.project.viewStart) * self.project.viewScale))
		d.draw_line(gc, x, 0, x, self.allocation.height)
		
		# Draw edit position
		if self.highlightCursor and not self.childActive:
			col = gc.get_colormap().alloc_color("#0000FF")
			gc.set_foreground(col)
			d.draw_line(gc, int(self.highlightCursor), 0, int(self.highlightCursor), self.allocation.height)
		
	#_____________________________________________________________________
		
	def Update(self, child=None):

		if child and child in self.fixed.get_children():
			x = int(round((child.event.start - self.project.viewStart) * self.project.viewScale))
			self.fixed.move( child, x, 0 )
		else:			
			# Move them to the correct positions
			for w in self.fixed.get_children():
				#Check that it is EventViewer (could be a button drawer)
				if type(w) == EventViewer:
					if w.event not in self.instrument.events:
						# Check if any events have been deleted
						self.fixed.remove(w)
						self.childActive = False
					else:
						x = int(round((w.event.start - self.project.viewStart) * self.project.viewScale))
						self.fixed.move(w, x, 0)

			# Check if any events have been added
			widget_events = [w.event for w in self.fixed.get_children()]
			for ev in self.instrument.events:
				if ev not in widget_events:
					x = int(round((ev.start - self.project.viewStart) * self.project.viewScale))
					child = EventViewer(self, self.project, ev, self.allocation.height, self, self.mainview, self.small)
					self.fixed.put(	child, x, 0)
			self.fixed.show_all()
		self.queue_draw()
			
	#_____________________________________________________________________

	def OnMouseDown(self, widget, mouse):
		
		if self.childActive:
			return
		
		self.mouseDownPos = [mouse.x, mouse.y]
		
		# Create context menu on RMB 
		if mouse.button == 3: 
			m = gtk.Menu() 
			items = [	("Import Audio File...", self.CreateEventFromFile, True),
					("---", None, None),
					("Paste", self.OnPaste, self.project.clipboardList),
					("Delete", self.OnDelete, True)
					 ] 

			for i, cb, sensitive in items: 
				if i == "---":
					a = gtk.SeparatorMenuItem()
				else:
					a = gtk.MenuItem(label=i)
					
				a.set_sensitive(bool(sensitive))
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
		# display status bar message if has not already been displayed
		if not self.messageID: 
			self.messageID = self.mainview.SetStatusBar("<b>Right-click</b> for more options.")
		# TODO - we need to add code here to snap to beat/bar etc.
		self.highlightCursor = mouse.x
		self.queue_draw()
		
	#_____________________________________________________________________
		
	def OnMouseLeave(self, widget, mouse):
		if self.messageID:   #clesr status bar if not already clear
			self.mainview.ClearStatusBar(self.messageID)
			self.messageID = None
		if not self.popupIsActive:
			self.highlightCursor = None
		self.queue_draw()

	#_____________________________________________________________________
	
	def CreateEventFromFile(self, evt):
		buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK)

		copyfile=gtk.CheckButton("Copy file to project")
		copyfile.show()

		dlg = gtk.FileChooserDialog("Import file...", action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=buttons)
		dlg.set_current_folder(self.mainview.defaultlocation)
		dlg.set_extra_widget(copyfile)
		
		audiopreview = AudioPreview()
		dlg.set_preview_widget(audiopreview)
		dlg.connect("selection-changed", audiopreview.OnSelection)
		
		response = dlg.run()

		if response == gtk.RESPONSE_OK:
			dlg.hide()
			start = (self.mouseDownPos[0]/self.project.viewScale) + self.project.viewStart
			self.instrument.addEventFromFile(start, dlg.get_filename(),copyfile.get_active())
			self.mainview.defaultlocation=os.path.dirname(dlg.get_filename())
		dlg.destroy()

	#_____________________________________________________________________
	
	def OnPaste(self, widget):
		if not self.project.clipboardList:
			return
		
		for event in self.project.clipboardList:
			start = (self.mouseDownPos[0]/self.project.viewScale) + self.project.viewStart
			self.instrument.addEventFromEvent(start, event)
		
	#_____________________________________________________________________
	
	def OnDelete(self, event):
		self.project.DeleteInstrument(self.instrument.id)
		self.mainview.UpdateDisplay()
	
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None):
		if obj is self.project or obj is self.instrument:
			self.Update()
		else:
			x1 = round((self.project.transport.PrevPosition - self.project.viewStart) * self.project.viewScale)
			x2 = round((self.project.transport.position - self.project.viewStart) * self.project.viewScale)
			self.queue_draw_area(int(x1)-1, 0, 3, self.allocation.height)
			self.queue_draw_area(int(x2)-1, 0, 3, self.allocation.height)
		
	#_____________________________________________________________________
	

#=========================================================================

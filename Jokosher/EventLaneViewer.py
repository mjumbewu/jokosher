#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	EventLaneViewer.py
#	
#	This is a gui class that acts as the container for all the 
#	EventViewers belonging to a single instrument. Graphically,
#	this class makes up the timeline portion of the instrument,
#	on which the events can be placed and moved.
#
#-------------------------------------------------------------------------------

import gtk
from EventViewer import *
import os.path
import gettext
import urllib # To decode URI's
import Globals # To get projectfolder
_ = gettext.gettext

#=========================================================================

class EventLaneViewer(gtk.EventBox):
	"""
	This class is a container for all the individual EventViewers
	for a single Instrument.
	"""
	
	""" Number only to be used inside Jokosher """
	URI_DRAG_TYPE = 84
	
	""" Custom numbers for use while dragging text in Jokosher """
	DRAG_TARGETS = [ ( "text/uri-list", 	# Accept uri-lists
						0,					# From everywhere
						URI_DRAG_TYPE ),		# Use the custom number
						("text/plain", 0, URI_DRAG_TYPE) # so drags from Firefox work
						]
	
	#_____________________________________________________________________

	def __init__(self, project, instrument, instrumentviewer, mainview, small = False):
		"""
		Creates a new instance of EventLaneViewer.
		
		Parameters:
			project -- the currently active Project.
			instrument -- the Instrument that the Event lane belongs to.
			instrumentviewer -- the InstrumentViewer holding the Event lane.
			mainview -- the MainApp Jokosher window.
			small -- set to True if we want small edit views (i.e. for mixing view).
		"""
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
		self.project.transport.connect("position", self.OnTransportPosition)
		self.project.connect("view-start", self.OnProjectViewChange)
		self.project.connect("zoom", self.OnProjectViewChange)
		self.instrument.connect("event", self.OnInstrumentSignal)
		self.instrument.connect("recording-done", self.OnInstrumentSignal)
		self.instrument.connect("selected", self.OnInstrumentSignal)
		
		# This defines where the blue cursor indicator should be drawn (in pixels)
		self.highlightCursor = None
		
		# True if the popup menu is visible
		self.popupIsActive = False
		
		#The position where the last mouse click was
		self.mouseDownPos = [0,0]
		
		self.set_events(	gtk.gdk.POINTER_MOTION_MASK |
							gtk.gdk.BUTTON_RELEASE_MASK |
							gtk.gdk.BUTTON_PRESS_MASK )
		
		self.connect("button-press-event", self.OnMouseDown)
		self.connect("motion_notify_event", self.OnMouseMove)
		self.connect("leave_notify_event", self.OnMouseLeave)
		self.fixed.drag_dest_set(	gtk.DEST_DEFAULT_DROP,
									self.DRAG_TARGETS, 
									gtk.gdk.ACTION_COPY)
		self.fixed.connect("drag_data_received", self.OnDragDataReceived)
		self.fixed.connect("drag_motion", self.OnDragMotion)
		self.fixed.connect("drag_leave", self.OnDragLeave)
		self.fixed.connect("expose-event", self.OnDraw)
		
		self.messageID = None
		self.Update()
		
	#_____________________________________________________________________
		
	def OnDraw(self, widget, event):
		"""
		Called everytime the window is drawn.
		Handles the drawing of the lane edges and vertical line cursors.
		
		Parameters:
			widget -- GTK widget to be repainted.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""

		wnd = widget.window
		gc = wnd.new_gc()
		
		transport = self.project.transport
		
		# Draw lane edges
		col = gc.get_colormap().alloc_color("#666666")
		gc.set_foreground(col)
		wnd.draw_line(gc, 0, self.allocation.height-1, self.allocation.width-1, self.allocation.height-1)
		
		# Draw play cursor position
		col = gc.get_colormap().alloc_color("#FF0000")
		gc.set_foreground(col)
		
		x = int(round((transport.position - self.project.viewStart) * self.project.viewScale))
		wnd.draw_line(gc, x, 0, x, self.allocation.height)
		
		# Draw edit position
		if self.highlightCursor:
			col = gc.get_colormap().alloc_color("#0000FF")
			gc.set_foreground(col)
			wnd.draw_line(gc, int(self.highlightCursor), 0, int(self.highlightCursor), self.allocation.height)
		
	#_____________________________________________________________________
		
	def Update(self, child=None):
		"""
		Updates the complete view when requested by a signal from project or instrument or __init__.
		
		Parameters:
			child -- a particular child widget to be updated. If provided, only this 
					one will be updated, and all other children will be left alone.
		"""
		if child and child in self.fixed.get_children():
			x = int(round((child.event.start - self.project.viewStart) * self.project.viewScale))
			self.fixed.move( child, x, 0 )
			child.UpdateDrawerPosition()
		else:			
			# Move them to the correct positions
			for widget in self.fixed.get_children():
				#Check that it is EventViewer (could be a button drawer)
				if type(widget) == EventViewer:
					if widget.event not in self.instrument.events:
						# Check if any events have been deleted
						self.fixed.remove(widget)
						# remove the event's drawer if it's showing
						if widget.drawer.parent == self.fixed:
							self.fixed.remove(widget.drawer)
						#destroy the object
						widget.Destroy()
					else:
						x = int(round((widget.event.start - self.project.viewStart) * self.project.viewScale))
						self.fixed.move(widget, x, 0)
						widget.UpdateDrawerPosition()

			# Check if any events have been added
			widget_events = [widget.event for widget in self.fixed.get_children()]
			for ev in self.instrument.events:
				if ev not in widget_events:
					x = int(round((ev.start - self.project.viewStart) * self.project.viewScale))
					child = EventViewer(self, self.project, ev, self.allocation.height, self.mainview, self.small)
					self.fixed.put(child, x, 0)
			self.fixed.show_all()
		self.queue_draw()
			
	#_____________________________________________________________________
	
	def Destroy(self):
		"""
		Called when the EventLaneViewer gets destroyed.
		It also destroys any child widget and disconnects itself from any
		gobject signals.
		"""
		self.project.transport.disconnect_by_func(self.OnTransportPosition)
		self.project.disconnect_by_func(self.OnProjectViewChange)
		self.instrument.disconnect_by_func(self.OnInstrumentSignal)
		
		for widget in self.fixed.get_children():
			#Check that it is EventViewer (could be a button drawer)
			if type(widget) == EventViewer:
				widget.Destroy()
		
		self.destroy()
	
	#_____________________________________________________________________

	def OnMouseDown(self, widget, mouse):
		"""
		Called when the user pressed a mouse button.
		If it's a right-click, creates a context menu on the fly for importing,
		pasting and deleting Events.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- GTK mouse event that fired this method call.
		"""
		if self.project.GetIsRecording():
			return True

		self.mouseDownPos = [mouse.x, mouse.y]
		
		if mouse.type == gtk.gdk._2BUTTON_PRESS:
			self.CreateEventFromFile()
			
		if self.popupIsActive:
			self.OnMenuDone()
		# Create context menu on RMB 
		elif mouse.button == 3:
			menu = gtk.Menu()
		
			audioimg = None
			if self.mainview.audioFilePixbuf:
				audioimg = gtk.Image()
				audioimg.set_from_pixbuf(self.mainview.audioFilePixbuf)
			
			items = [	(_("_Add Audio File..."), self.CreateEventFromFile, True, audioimg),
					("---", None, None, None),
					(_("_Paste"), self.OnPaste, self.project.clipboardList, gtk.image_new_from_stock(gtk.STOCK_PASTE, gtk.ICON_SIZE_MENU)),
					(_("_Delete"), self.OnDelete, True, gtk.image_new_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_MENU))
					]

			for label, callback, sensitive, image in items:
				if label == "---":
					menuItem = gtk.SeparatorMenuItem()
				elif image:
					menuItem = gtk.ImageMenuItem(label, True)
					menuItem.set_image(image)
				else:
					menuItem = gtk.MenuItem(label=label)
					
				menuItem.set_sensitive(bool(sensitive))
				menuItem.show()
				menu.append(menuItem)
				if callback:
					menuItem.connect("activate", callback)
			self.highlightCursor = mouse.x
			self.popupIsActive = True

			menu.popup(None, None, None, mouse.button, mouse.time)
			menu.connect("selection-done", self.OnMenuDone)
		
		if 'GDK_CONTROL_MASK' in mouse.state.value_names:
			self.instrument.SetSelected(True)
		else:
			self.project.ClearEventSelections()
			self.project.SelectInstrument(self.instrument)
			
		return True
			
	#_____________________________________________________________________
	
	def OnMenuDone(self, widget=None):
		"""
		Hides the right-click context menu after the user has selected one
		of its options or clicked elsewhere.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.popupIsActive = False
		self.highlightCursor = None
	
	#_____________________________________________________________________

	def OnMouseMove(self, widget, mouse):
		"""
		Display a message in the StatusBar when the mouse hovers over the
		EventLaneViewer.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- GTK mouse event that fired this method call.
		"""
		if self.project.GetIsRecording():
			return True
		
		# display status bar message if has not already been displayed
		if not self.messageID: 
			self.messageID = self.mainview.SetStatusBar(_("<b>Right-click</b> for more options."))
		# TODO - we need to add code here to snap to beat/bar etc.
		self.highlightCursor = mouse.x
		self.queue_draw()
		
	#_____________________________________________________________________
		
	def OnMouseLeave(self, widget, mouse):
		"""
		Clears the StatusBar message when the mouse moves out of the
		EventLaneViewer area.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- GTK mouse event that fired this method call.
		"""
		if self.messageID:   #clear status bar if not already clear
			self.mainview.ClearStatusBar(self.messageID)
			self.messageID = None
		if not self.popupIsActive:
			self.highlightCursor = None
		self.queue_draw()

	#_____________________________________________________________________
	
	def CreateEventFromFile(self, event=None):
		"""
		Called when "Import Audio File..." is selected from the right-click context menu.
		Opens up a file chooser dialog to import an Event.
		
		Parameters:
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		filenames, copyfile = self.mainview.ShowImportFileChooser()
		#filename will be None is the user cancelled the dialog
		if filenames:
			start = 0
			if event:
				#if we we're called from a mouse click, use the mouse position as the start
				start = (self.mouseDownPos[0]/self.project.viewScale) + self.project.viewStart
			
			self.instrument.AddEventsFromList(start, filenames)

	#_____________________________________________________________________
	
	def OnPaste(self, widget):
		"""
		Called when "Paste" is selected from the context menu.
		Adds the selected Event to the clipboard.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.project.clipboardList:
			return
		
		for event in self.project.clipboardList:
			start = (self.mouseDownPos[0]/self.project.viewScale) + self.project.viewStart
			self.instrument.addEventFromEvent(start, event)
		
	#_____________________________________________________________________
	
	def OnDelete(self, event=None):
		"""
		Called when "Delete" is selected from context menu.
		Deletes the selected Instrument from the Project.
		
		Considerations:
			This delete is called when right-clicking an EMPTY section
			of the EventLaneViewer. For right-clicking over a selected
			Event see OnDelete in EventViewer.
			
		Parameters:
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.project.DeleteInstrument(self.instrument.id)
	
	#_____________________________________________________________________
	
	def OnProjectViewChange(self, project):
		"""
		Callback function for when the project view changes,
		and the "view-start" or the "zoom" signal is send, and we
		need to update.
		
		Parameters:
			project -- The project instance that send the signal.
		"""
		self.Update()
		
	#_____________________________________________________________________
	
	def OnInstrumentSignal(self, instrument, extra=None):
		"""
		Callback for any change signal from instrument.
		
		Parameters:
			instrument -- the instrument instance that send the signal.
			extra -- extra optional parameters passed by the caller.
		"""
		self.Update()
		
	#_____________________________________________________________________
	
	def OnTransportPosition(self, transportManager, extraString):
		"""
		Callback for signal when the transport position changes.
		Here we just redraw the playhead.
		
		Parameters:
			transportManager -- the TransportManager instance that send the signal.
			extraString -- a string specifying the extra action details. i.e. "stop-action"
					means that the position changed because the user hit stop.
		"""
		x1 = round((self.project.transport.PrevPosition - self.project.viewStart) * self.project.viewScale)
		x2 = round((self.project.transport.position - self.project.viewStart) * self.project.viewScale)
		self.queue_draw_area(int(x1)-1, 0, 3, self.allocation.height)
		self.queue_draw_area(int(x2)-1, 0, 3, self.allocation.height)
	
	#_____________________________________________________________________
	
	def OnDragDataReceived(self, widget, context, x, y, selection, targetType, time):
		"""
		Called when the user releases MOUSE1, finishing a drag and drop
		procedure.
		Adds an Event for each "file://"-uri in the uri-list to the Instrument, 
		one after the other. The files will be copied to the Project's audio directory.
			
		Parameters:
			widget -- InstrumentViewer being dragged.
			context -- reserved for GTK callbacks, don't use it explicitly.
			x -- point in the X axis the dragged object was dropped.
			y -- point in the Y axis the dragged object was dropped..
			selection -- selected object area that was dragged.
			targetType -- mimetype of the dragged object.
			time -- reserved for GTK callbacks, don't use it explicitly.
			
		Returns:
			True -- continue GTK signal propagation. *CHECK*
		"""
		start = (x/self.project.viewScale) + self.project.viewStart
		# Splitlines to separate the uri's, unquote to decode the uri-encoding ('%20' -> ' ')
		uris = [urllib.unquote(uri) for uri in selection.data.splitlines()]
		self.instrument.AddEventsFromList(start, uris, True)
		
		context.finish(True, False, time)
		return True
	
	#_____________________________________________________________________
	
	def OnDragMotion(self, widget, context, x, y, time):
		"""
		Called each time the user moves the mouse while dragging.
		Draws a cursor on the EventLane while dragging something over it.
		
		Parameters:
			widget -- InstrumentViewer the mouse is hovering over.
			context -- cairo widget context.
			x -- reserved for GTK callbacks, don't use it explicitly.
			y -- reserved for GTK callbacks, don't use it explicitly.
			time -- reserved for GTK callbacks, don't use it explicitly.
		
		Returns:
			True -- continue GTK signal propagation. *CHECK*
		"""
		context.drag_status(gtk.gdk.ACTION_COPY, time)
		self.highlightCursor = x
		self.queue_draw()
		return True
	
	#_____________________________________________________________________
	
	def OnDragLeave(self, widget, drag_context, timestamp):
		"""
		Called when the user moves the cursor ouf of the EventLaneViewer
		while performing a drag and drop procedure.
		Hides the highlight cursor.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			drag_context -- reserved for GTK callbacks, don't use it explicitly.
			timestamp -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.highlightCursor = None
		self.queue_draw()
		
	#_____________________________________________________________________
	
	def ChangeSize(self, small):
		"""
		Changes the size of the event lane.
		
		Parameters:
			small - True if the event lane is to be small.
		"""
		self.small = small
		for eventViewer in self.fixed.get_children():
			eventViewer.ChangeSize(small)
			
	#____________________________________________________________________	

#=========================================================================

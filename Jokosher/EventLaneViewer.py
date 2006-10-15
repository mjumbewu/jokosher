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
from AudioPreview import AudioPreview
import os.path
import gettext
import urlparse # To split up URI's
import urllib # To decode URI's
import Globals # To get projectfolder
_ = gettext.gettext

#=========================================================================

class EventLaneViewer(gtk.EventBox):
	"""
		This class is a container for all the individual EventViewers
		for a single instrument.
	"""
	
	URI_DRAG_TYPE = 84			# Number only to be used inside Jokosher
	DRAG_TARGETS = [ ( "text/uri-list", 	# Accept uri-lists
					   0,					# From everywhere
					   URI_DRAG_TYPE ),		# Use the custom number
					   ('text/plain', 0, URI_DRAG_TYPE) # so drags from Firefox work
					   ]
	
	#_____________________________________________________________________

	def __init__(self, project, instrument, instrumentviewer, mainview, small = False):
		"""
			project - the current active project
			instrument - the instrument that the event lane belongs
			instrumentviewer - the instrumentviewer holding the event lane
			mainview - the main Jokosher window
			small - set to True if we want small edit views (i.e. for mix view)
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
			Callback for 'expose-event'
			The drawing areas cannot be drawn on until this point
		"""

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
		"""
			Updates the complete view when requested by OnStateChanged or __init__
		"""
		if child and child in self.fixed.get_children():
			x = int(round((child.event.start - self.project.viewStart) * self.project.viewScale))
			self.fixed.move( child, x, 0 )
			child.UpdateDrawerPosition()
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
						w.UpdateDrawerPosition()

			# Check if any events have been added
			widget_events = [w.event for w in self.fixed.get_children()]
			for ev in self.instrument.events:
				if ev not in widget_events:
					x = int(round((ev.start - self.project.viewStart) * self.project.viewScale))
					child = EventViewer(self, self.project, ev, self.allocation.height, self, self.mainview, self.small)
					self.fixed.put(child, x, 0)
			self.fixed.show_all()
		self.queue_draw()
			
	#_____________________________________________________________________

	def OnMouseDown(self, widget, mouse):
		"""
			Callback for 'button-press-event' signal 
		"""
		
		if self.childActive:
			return
		
		self.mouseDownPos = [mouse.x, mouse.y]
		
		# Create context menu on RMB 
		if mouse.button == 3: 
			m = gtk.Menu() 
			items = [	(_("Import Audio File..."), self.CreateEventFromFile, True),
					("---", None, None),
					(_("Paste"), self.OnPaste, self.project.clipboardList),
					(_("Delete"), self.OnDelete, True)
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
		"""
			Callback for 'selection-done' signal - context menu selected
		"""
		self.popupIsActive = False
		self.highlightCursor = None
	
	#_____________________________________________________________________

	def OnMouseMove(self, widget, mouse):
		"""
			Callback for 'motion_notify_event' - mouse moved/entered eventlaneviewer
		"""
		# display status bar message if has not already been displayed
		if not self.messageID: 
			self.messageID = self.mainview.SetStatusBar(_("<b>Right-click</b> for more options."))
		# TODO - we need to add code here to snap to beat/bar etc.
		self.highlightCursor = mouse.x
		self.queue_draw()
		
	#_____________________________________________________________________
		
	def OnMouseLeave(self, widget, mouse):
		"""
			Callback for 'leave_notify_event' - mouse left eventlaneviewer
		"""
		if self.messageID:   #clear status bar if not already clear
			self.mainview.ClearStatusBar(self.messageID)
			self.messageID = None
		if not self.popupIsActive:
			self.highlightCursor = None
		self.queue_draw()

	#_____________________________________________________________________
	
	def CreateEventFromFile(self, evt):
		"""
			Called on selecting "Import Audio File..." from context menu.
			Opens up a file chooser dialog.
		"""
		buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK)

		copyfile = gtk.CheckButton(_("Copy file to project"))
		# Make it copy files to audio dir by default
		copyfile.set_active(True)
		copyfile.show()

		dlg = gtk.FileChooserDialog(_("Import file..."), action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=buttons)
		dlg.set_current_folder(Globals.settings.general["projectfolder"])
		dlg.set_extra_widget(copyfile)
		
		
		vbox = gtk.VBox()
		audiopreview = AudioPreview()
		vbox.pack_start(audiopreview, True, False)
		vbox.show_all()
		
		dlg.set_preview_widget(vbox)
		dlg.set_use_preview_label(False)
		dlg.connect("selection-changed", audiopreview.OnSelection)
		
		response = dlg.run()

		if response == gtk.RESPONSE_OK:
			#stop the preview audio from playing without destorying the dialog
			audiopreview.OnDestroy()
			dlg.hide()
			start = (self.mouseDownPos[0]/self.project.viewScale) + self.project.viewStart
			self.instrument.addEventFromFile(start, dlg.get_filename(),copyfile.get_active())
			Globals.settings.general["projectfolder"] = os.path.dirname(dlg.get_filename())
			Globals.settings.write()
			dlg.destroy()
		else:
			dlg.destroy()

	#_____________________________________________________________________
	
	def OnPaste(self, widget):
		"""
			Called when selecting "Paste" from context menu 
			 - adds an event from the clipboard
		"""
		if not self.project.clipboardList:
			return
		
		for event in self.project.clipboardList:
			start = (self.mouseDownPos[0]/self.project.viewScale) + self.project.viewStart
			self.instrument.addEventFromEvent(start, event)
		
	#_____________________________________________________________________
	
	def OnDelete(self, event):
		"""
			Called when selecting Delete from context menu
			 - deletes instrument from project
			NOTE: This is delete when right-clicking an EMPTY section
			      of the event lane. For right-clicking over a selected 
						event see OnDelete in EventViewer
		"""
		self.project.DeleteInstrument(self.instrument.id)
		self.mainview.UpdateDisplay()
	
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None):
		"""
			Called on a change of state in any of the objacts we are interested in.
			If there's a project or instrument change then redraw everything,
			otherwise just redraw the play head.
		"""
		if obj is self.project or obj is self.instrument:
			self.Update()
		else:
			x1 = round((self.project.transport.PrevPosition - self.project.viewStart) * self.project.viewScale)
			x2 = round((self.project.transport.position - self.project.viewStart) * self.project.viewScale)
			self.queue_draw_area(int(x1)-1, 0, 3, self.allocation.height)
			self.queue_draw_area(int(x2)-1, 0, 3, self.allocation.height)
		
	#_____________________________________________________________________
	
	def OnDragDataReceived(self, widget, context, x, y, selection, targetType, time):
		'''
			Called when the drop succeeds. Adds an event for each "file://"-uri
			in the uri-list to the instrument, one after the other. The files
			will be copied to the project audio directory.
		'''
		start = (x/self.project.viewScale) + self.project.viewStart
		# Splitlines to separate the uri's, unquote to decode the uri-encoding ('%20' -> ' ')
		uris = [urllib.unquote(uri) for uri in selection.data.splitlines()]
		for uri in uris:
			# Parse the uri, and continue only if it is pointing to a local file
			(scheme, domain, file, params, query, fragment) = urlparse.urlparse(uri, "file")
			if scheme == "file":
				event = self.instrument.addEventFromFile(start, file, True) # True: copy
				event.MoveButDoNotOverlap(event.start)
				start = event.start # Should improve performance with very large file-lists
			elif scheme == 'http':
				# download and import. This should probably be done in the background.
				event = self.instrument.addEventFromURL(start, uri)
				event.MoveButDoNotOverlap(event.start)
				start = event.start
		context.finish(True, False, time)
		return True
	
	#_____________________________________________________________________
	
	def OnDragMotion(self, widget, context, x, y, time):
		'''
			Draws a cursor on the EventLane while dragging something over it.
		'''
		context.drag_status(gtk.gdk.ACTION_COPY, time)
		self.highlightCursor = x
		self.queue_draw()
		return True
	
	#_____________________________________________________________________
	
	def OnDragLeave(self, widget, drag_context, timestamp):
		'''
			Removes the cursor when dragging out of the EventLane.
		'''
		self.highlightCursor = None
		self.queue_draw()
	
#=========================================================================

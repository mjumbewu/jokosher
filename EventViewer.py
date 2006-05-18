#!/usr/bin/python

import sys
import gtk
import math
import cairo
import Project

#=========================================================================

class EventViewer(gtk.DrawingArea):
	""" The EventViewer class handles displaying a single event as part
		of an EventLaneViewer object.
	"""

	__gtype_name__ = 'EventViewer'
	
	#_____________________________________________________________________

	def __init__(self, lane, project, event, height, small = False):

		self.small = small
		gtk.DrawingArea.__init__(self)
		
		self.set_events(	gtk.gdk.POINTER_MOTION_MASK |
							gtk.gdk.BUTTON_RELEASE_MASK |
							gtk.gdk.BUTTON_PRESS_MASK |
							gtk.gdk.LEAVE_NOTIFY_MASK )
							
		self.connect("expose_event",self.OnDraw)
		self.connect("motion_notify_event", self.OnMouseMove)
		self.connect("leave_notify_event", self.OnMouseLeave)
		self.connect("button_press_event", self.OnMouseDown)
		self.connect("button_release_event", self.OnMouseUp)
		self.connect("configure_event", self.OnSizeChanged)
		
		self.height = height			# Height of this object in pixels
		self.event = event				# The event this widget is representing
		self.project = project			# A reference to the open project
		self.isDragging = False			# True if this event is currently being dragged
		self.lane = lane				# The parent lane for this object
		self.last_num_levels = 0		# Used to track if we need to resize the GUI object
		self.isLoading = False			# Used to track if we need to update the GUI after loading a waveform
		self.currentScale = 0			# Tracks if the project viewScale has changed
		
		# source is an offscreen canvas to hold our waveform image
		self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.allocation.width, self.allocation.height)
		self.DrawWaveform()

		# Monitor the things this object cares about
		self.project.AddListener(self)
		self.event.AddListener(self)

		# This defines where the blue cursor indicator should be drawn (in pixels)
		self.highlightCursor = None
		
	#_____________________________________________________________________

	def OnDraw(self, widget, event):
		""" This function blits the waveform data onto the screen, and
			then draws the play cursor over it.
		"""

		# Get a cairo surface for this drawing op
		context = widget.window.cairo_create()

		# Give it our waveform image as a source
		context.set_source_surface(self.source, 0, 0)	
		
		# set a clip region for the expose event
		context.rectangle(event.area.x, event.area.y,
							  event.area.width, event.area.height)
		context.clip()

		# Blit our waveform across
		context.paint()

		# Overlay an extra rect if we're selected
		if self.event.isSelected:
			context.rectangle(event.area.x, event.area.y,
							  event.area.width, event.area.height)
			context.set_source_rgba(0, 0, 1.0, 0.2)
			context.fill()
		
		#Draw play position
		x = int((self.project.transport.position - self.event.start) * self.project.viewScale)
		context.set_line_width(1)
		context.set_antialias(cairo.ANTIALIAS_NONE)
		context.move_to(x+1, 0)
		context.line_to(x+1, self.allocation.height)
		context.set_source_rgb(1.0, 0, 0)
		context.stroke()
		
		# Draw the highlight cursor if it's over us
		if self.highlightCursor:
			context.move_to(self.highlightCursor, 0)
			context.line_to(self.highlightCursor, self.allocation.height)
			context.set_source_rgb(0, 0, 1.0)
			context.stroke()

		return False
		
	#_____________________________________________________________________

	def DrawWaveform(self):
		""" This function uses Cairo to draw the waveform level information
			onto a canvas in memory.
		"""
		rect = self.get_allocation()

		context = cairo.Context(self.source)
		context.set_line_width(2)
		context.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
		
		if self.event.isLoading:
			# Draw a white background
			context.rectangle(0, 0, rect.width, rect.height)
			context.set_source_rgb(1, 1, 1)
			context.fill()
			# and a border
			context.set_line_width(2)
			context.rectangle(0, 0, rect.width, rect.height)
			context.set_source_rgb(0, 0, 0)
			context.stroke()
			# Write "Loading..."
			context.move_to(5, 12)
			if self.event.duration == 0:
				displayLength = "0%"
			else:
				displayLength = "%d%%" % int(100 * self.event.loadingLength /
			  														 self.event.duration)
			context.show_text("Loading (%s)..." % displayLength)
			context.stroke()
			# And exit here
			return
		
		if len(self.event.levels) == 0:
			raise "Trying to draw an event with no level data!"
		
		scale = (self.event.duration * self.project.viewScale) / float(len(self.event.levels))
		context.scale(scale, 1.0)

		# Draw white background
		context.rectangle(0, 0, len(self.event.levels), rect.height)
		context.set_source_rgb(1, 1, 1)
		context.fill()

		# Draw volume curve
		x_pos = 0
		context.move_to(0,rect.height)

		for peak in self.event.levels:
			scaled_peak = peak * rect.height
			context.line_to(x_pos, rect.height - int(scaled_peak))
			x_pos += 1

		context.line_to(x_pos, rect.height)
		context.set_source_rgb(0, 1, 0.0)
		context.fill_preserve()
		context.set_source_rgb(0, 0.0, 0)
		context.set_line_width(0.6)
		context.stroke()
		
		# Reset the drawing scale
		context.identity_matrix()
		context.scale(1.0, 1.0)
		
		# Draw black border
		if (self.event.isSelected):
			context.set_line_width(4)
		else:
			context.set_line_width(2)
		context.rectangle(0, 0, rect.width, rect.height)
		context.set_source_rgb(0, 0, 0)
		context.stroke()
		context.set_line_width(2)
		
		# Draw Event name
		context.move_to(5, 12)
		context.show_text(self.event.name)
		

	#_____________________________________________________________________

	def OnMouseMove(self,widget,mouse):
	
		if not self.window:
			return
			
		if self.isDragging:
			ptr = gtk.gdk.display_get_default().get_pointer()
			x = ptr[1]
			y = ptr[2]
			dx = float(x - self.mouseAnchor[0]) / self.project.viewScale
			time = self.event.start + dx
			time = max(0, time)
			self.event.start = time
			self.mouseAnchor = [x, y]
			self.lane.Update(self)
			self.highlightCursor = None
		else:
			self.highlightCursor = mouse.x
		
		self.lane.childActive = True
		self.queue_draw()

	#_____________________________________________________________________
	
	def OnMouseDown(self, widget, mouse):
	
		# Check if control is being pressed
		if 'GDK_CONTROL_MASK' in mouse.state.value_names:
			control = True
		else:
			control = False

		if mouse.button == 3:
			m = gtk.Menu()
			items = [	("Split", self.OnSplit, True),
						("Join", self.OnJoin, self.event.instrument.MultipleEventsSelected()),
						("---", None, None),
						("Delete", self.OnDelete, self.event.isSelected)
					 ] 

			for i, cb, sense in items: 
				if i == "---":
					a = gtk.SeparatorMenuItem()
				else:
					a = gtk.MenuItem(i)
					if sense:
						a.set_sensitive(True)
					else:
						a.set_sensitive(False)
				a.show() 
				m.append(a) 
				if cb:
					a.connect("activate", cb) 
			self.highlightCursor = mouse.x
			self.popupIsActive = True

			m.popup(None, None, None, mouse.button, mouse.time)
			m.connect("selection-done",self.OnMenuDone)
			
			self.mouseAnchor = [mouse.x, mouse.y]
			
		else:
			self.isDragging = True
			if not (control):
				self.project.ClearEventSelections()
				self.project.ClearInstrumentSelections()
			self.event.SetSelected(True)
			self.eventStart = self.event.start
			ptr = gtk.gdk.display_get_default().get_pointer()
			self.mouseAnchor = [ptr[1], ptr[2]]
		return True
			
	#_____________________________________________________________________
	
	def OnMenuDone(self, widget):
		self.popupIsActive = False
		self.highlightCursor = None
		
	#_____________________________________________________________________
		
	def OnMouseUp(self, widget, mouse):
		
		if mouse.button != 3:		
			self.isDragging = False
			if (self.eventStart != self.event.start):
				self.event.Move(self.eventStart, self.event.start)
				return False #need to pass this button release up to RecordingView
	#_____________________________________________________________________
		
	def OnMouseLeave(self, widget, event):
		self.highlightCursor = None
		self.lane.childActive = False
		self.queue_draw()
		
	#_____________________________________________________________________
			
	def OnSplit(self, evt):
		x = self.mouseAnchor[0]
		x /= float(self.project.viewScale)
		self.event.Split(x)
		self.lane.Update()
		
	#_____________________________________________________________________

	def OnJoin(self, evt):
		self.event.instrument.JoinEvents()
		self.lane.Update()

	#_____________________________________________________________________

	def OnDelete(self, evt):
		# delete event
		self.lane.childActive = False
		self.event.Delete()
		self.lane.Update()

	#_____________________________________________________________________
	
	def do_size_request(self, requisition):
		""" We need to override this function otherwise we get
			given a 1x1 display size!
		"""
		if self.event.duration > 0:
			requisition.width = self.event.duration * self.project.viewScale
		else:
			requisition.width = 10 * self.project.viewScale
			
		if not (self.small):
			requisition.height = 77
		else:
			rect = self.get_allocation()
			print "Working out height",rect.height
			if rect.height < 30:
				requisition.height = 30
			else:
				requisition.height = rect.height

	#_____________________________________________________________________
	
	def OnStateChanged(self, obj):
				
		if self.isLoading != self.event.isLoading:
			self.DrawWaveform()
			self.isLoading = self.event.isLoading
				
		if len(self.event.levels) != self.last_num_levels:
			self.queue_resize()
			self.DrawWaveform()
			self.last_num_levels = len(self.event.levels)
			
		if type(obj) == Project.Project:
			if self.currentScale != self.project.viewScale:
				self.queue_resize()
				self.DrawWaveform()
				self.last_num_levels = len(self.event.levels)
				self.currentScale = self.project.viewScale

		self.queue_draw()

	#_____________________________________________________________________

	def OnSizeChanged(self, obj, evt):
		if self.allocation.width != self.source.get_width() or self.allocation.height != self.source.get_height():
			self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.allocation.width, self.allocation.height)
			self.DrawWaveform()

	#_____________________________________________________________________

#=========================================================================

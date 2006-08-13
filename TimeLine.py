
import gtk
import pango
import gobject
import gst

#=========================================================================

class TimeLine(gtk.DrawingArea):

	""" This class handles drawing the time line display.
	"""

	__gtype_name__ = 'TimeLine'
	
	N_LINES = 5 # Number of 'short' lines + 1

	#_____________________________________________________________________

	def __init__(self, project, timelinebar, mainview):
		""" project - reference to the active project
		"""
		
		gtk.DrawingArea.__init__(self)
	
		self.project = project
		self.timelinebar = timelinebar
		self.mainview = mainview
		self.project.transport.AddListener(self)
		self.project.AddListener(self)
		self.height = 44
		self.buttonDown = False
		self.dragging = False
	
		self.set_events(gtk.gdk.POINTER_MOTION_MASK |
								gtk.gdk.BUTTON_PRESS_MASK |
								gtk.gdk.BUTTON_RELEASE_MASK)
		self.connect("expose-event", self.OnDraw)
		self.connect("button_release_event", self.onMouseUp)
		self.connect("button_press_event", self.onMouseDown)
		self.connect("motion_notify_event", self.onMouseMove)
		self.connect("size_allocate", self.OnAllocate)
		self.savedLine = None
	#_____________________________________________________________________

	def OnAllocate(self, widget, allocation):
		self.allocation = allocation
		#Redraw timeline
		self.DrawLine(widget)
		
	#_____________________________________________________________________
		
	def OnDraw(self, widget, event):
		""" Fires off the drawing operation. """
		
		if self.savedLine == None:
			self.DrawLine(widget)
		if self.project.transport.RedrawTimeLine:
			self.project.transport.RedrawTimeLine = False
			self.DrawLine(widget)
		if self.project.RedrawTimeLine:
			self.project.RedrawTimeLine = False
			self.DrawLine(widget)
		d = widget.window

		gc = d.new_gc()
		
		# redraw area from saved image
		d.draw_image(gc, self.savedLine, event.area.x,
		event.area.y, event.area.x, event.area.y,
		event.area.width, event.area.height)

		# Draw play cursor position
		col = gc.get_colormap().alloc_color("#FF0000")
		gc.set_foreground(col)
		 
		x = int(round((self.project.transport.position - self.project.viewStart) * self.project.viewScale))
		d.draw_line(gc, x, 0, x, self.get_allocation().height)	
	
	#_____________________________________________________________________
		
	def DrawLine(self, widget):
		""" Draws the timeline and saves it to memory
		    - Must be called initially and to redraw the timeline
				  after moving the project start
		"""
		d = widget.window

		gc = d.new_gc()
		
		y = 0
		
		col = gc.get_colormap().alloc_color("#FFFFFF")
		gc.set_foreground(col)
		gc.set_fill(gtk.gdk.SOLID)
		
		d.draw_rectangle(	gc, True, 
							0, 
							0, 
							self.get_allocation().width, 
							self.get_allocation().height)
							
		col = gc.get_colormap().alloc_color("#555555")
		gc.set_foreground(col)
							
		d.draw_rectangle(	gc, False, 
							0, 
							0, 
							self.get_allocation().width, 
							self.get_allocation().height)
		
		transport = self.project.transport
		x = 0
		if transport.mode == transport.MODE_BARS_BEATS:
		
			# Calculate our scroll offset
			pos = (self.project.viewStart / 60.) * transport.bpm
			beat = int(pos)
			offset = pos - beat
			
			if offset > 0.:
				x -= offset * ((self.project.viewScale * 60.) / transport.bpm)
				x += (self.project.viewScale * 60.) / transport.bpm
				beat += 1
		
			while x < self.get_allocation().width:
				# Draw the beat/bar divisions
				ix = int(x)
				if beat % transport.meter_nom:
					d.draw_line(gc, ix, int(self.get_allocation().height/1.2), ix, self.get_allocation().height)
				else:
					d.draw_line(gc, ix, int(self.get_allocation().height/2), ix, self.get_allocation().height)
					
					# Draw the bar number
					l = pango.Layout(self.create_pango_context())
					l.set_text(str((beat / transport.meter_nom)+1))
					d.draw_layout(gc, ix, 5, l)
					
				beat += 1
				
				x += (60. / transport.bpm ) * self.project.viewScale
		else:
			# Working in milliseconds here. Using seconds gives modulus problems because they're floats
			viewScale = self.project.viewScale / 1000.
			viewStart = int(self.project.viewStart * 1000)
			factor, displayMilliseconds = self.get_factor(viewScale)
			
			# Calculate our scroll offset
			# sec : viewStart, truncated to 1000ms; the second that has past just before the beginning of our surface
			msec = viewStart - (viewStart % 1000)
			# sec : move to the last 'line' that wasn't drawn
			if (msec % factor) != 0:
				msec -= (msec % factor)
			# offset: the amount of milliseconds since the last second before the timeline
			offset = viewStart - msec

			if offset > 0: # x = 0. atm, it should stay that way if offset == 0.
				# offset : milliseconds
				# viewScale : pixels / milliseconds
				# offset * viewScale : offset in pixels
				x -= offset * viewScale # return to the last 'active' second
				x += viewScale * factor # positions the cursor at the first second to be drawn
				msec += factor # cursor is at the first line to be drawn now
				
			# Draw ticks up to the end of our display
			while x < self.get_allocation().width:
				ix = int(x)
				if msec % (self.N_LINES * factor):
					d.draw_line(gc, ix, int(self.get_allocation().height/1.2), ix, self.get_allocation().height)
				else:
					d.draw_line(gc, ix, int(self.get_allocation().height/2), ix, self.get_allocation().height)
					
					# Draw the bar number
					l = pango.Layout(self.create_pango_context())
					if displayMilliseconds:
						#Should use transportmanager for this...
						l.set_text("%d:%02d:%03d"%((msec/1000) / 60, (msec/1000) % 60, msec%1000) )
					else:
						l.set_text("%d:%02d"%((msec/1000) / 60, (msec/1000) % 60))
					d.draw_layout(gc, ix, 5, l)
				
				msec += factor
				x += viewScale * factor
		self.savedLine = d.get_image(0, 0, self.get_allocation().width, self.get_allocation().height)
	
	#_____________________________________________________________________
		
	def do_size_request(self, requisition):
		requisition.width = self.get_allocation().width
		requisition.height = self.height
		
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None):
		""" 
		Called when there is a change fo state in transport
		manager.Could be one of
		 *  Mode changed from bars/beats to minutes or vice versa
		    (requires a complete redraw of timeline - flag set)
		 *  Change in playing position -only needs partial redraw
		 *  Project change e.g. acroll or zoom change
		    (requires a complete redraw of timeline - flag set)
		"""
		if self.project.transport.RedrawTimeLine or self.project.RedrawTimeLine:
			self.queue_draw()
			return
		x1 = round((self.project.transport.PrevPosition - self.project.viewStart) * self.project.viewScale)
		x2 = round((self.project.transport.position - self.project.viewStart) * self.project.viewScale)
		
		self.queue_draw_area(int(x1)-1, 0, 3, self.get_allocation().height)
		self.queue_draw_area(int(x2)-1, 0, 3, self.get_allocation().height)
		
	#_____________________________________________________________________
		
	def onMouseDown(self, widget, event):
		self.buttonDown = True
		self.dragging = False
		self.moveHead(event.x)
		return True

	#_____________________________________________________________________

	def onMouseMove(self, widget, event):
		if not self.buttonDown:
			return
		self.dragging = True
		
		self.moveHead(event.x)
		
	#_____________________________________________________________________
		
	def onMouseUp(self, widget, event):
		self.dragging = False
		self.buttonDown = False
		
	#_____________________________________________________________________
		
	def moveHead(self, xpos):
		pos = self.project.viewStart + xpos/ self.project.viewScale
		self.project.transport.SeekTo(pos)
		
	#_____________________________________________________________________
	
	def get_factor(self, viewScale):
		'''
			To be used for drawing the MODE_HOURS_MINS_SECS timeline
			
			Returns:
				- an integer factor to be multiplied with the viewScale to zoom the timeline in/out
				- a boolean indicating if milliseconds should be displayed
			The default factor is 1000, meaning that the distance between the short lines of the timeline
			symbolizes 1000 milliseconds. The code will increase of decrease this factor to keep the
			timeline readable. The factors can be set with the ZOOM_LEVELS array. This array
			contains zoom levels that support precision from 20 ms to 1 minute. More extreme zoom
			levels could be added, but would never be reached because the viewScale is limited.
		'''
		SHORT_TEXT_WIDTH = 28 # for '0:00' notation
		LONG_TEXT_WIDTH = 56 # for '0:00:000' notation
		TEXT_WIDTH = SHORT_TEXT_WIDTH
		WHITESPACE = 50
		factor = 1000 # Default factor is 1 second for 1 line
		ZOOM_LEVELS = [20, 100, 200, 1000, 4000, 12000, 60000]
		if (TEXT_WIDTH + WHITESPACE) > (self.N_LINES * factor * viewScale):
			factor = ZOOM_LEVELS[ZOOM_LEVELS.index(factor) + 1]
			while (TEXT_WIDTH + WHITESPACE) > (self.N_LINES * factor * viewScale) and factor != ZOOM_LEVELS[-1]:
				factor = ZOOM_LEVELS[ZOOM_LEVELS.index(factor) + 1]
		else:
			while (TEXT_WIDTH + WHITESPACE) < (factor * viewScale) and factor != ZOOM_LEVELS[0]:
				factor = ZOOM_LEVELS[ZOOM_LEVELS.index(factor) - 1]
				if factor == 200:
					TEXT_WIDTH = LONG_TEXT_WIDTH
		return factor, (factor < 200) # 0.2 * 5 = 1.0 second, if the interval is smaller, milliseconds are needed
	
#=========================================================================

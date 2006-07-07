
import gtk
import pango
import gobject
import gst

#=========================================================================

class TimeLine(gtk.DrawingArea):

	""" This class handles drawing the time line display.
	"""

	__gtype_name__ = 'TimeLine'

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
			# Calculate our scroll offset
			sec = int(self.project.viewStart)
			offset = self.project.viewStart - sec

			if offset > 0.:
				x -= offset * self.project.viewScale
				x += self.project.viewScale
				sec += 1
				
			# Draw ticks up to the end of our display
			while x < self.get_allocation().width:
				ix = int(x)
				if sec % 5:
					d.draw_line(gc, ix, int(self.get_allocation().height/1.2), ix, self.get_allocation().height)
				else:
					d.draw_line(gc, ix, int(self.get_allocation().height/2), ix, self.get_allocation().height)
					
					# Draw the bar number
					l = pango.Layout(self.create_pango_context())
					l.set_text("%d:%02d"%(sec / 60, sec % 60))
					d.draw_layout(gc, ix, 5, l)
					
				sec += 1
				x += self.project.viewScale
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
#=========================================================================

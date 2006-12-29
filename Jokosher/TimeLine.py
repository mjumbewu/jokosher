#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	TimeLine.py
#	
#	This class handles the drawing of the timeline display.
#
#-------------------------------------------------------------------------------

import gtk
import pango

#=========================================================================

class TimeLine(gtk.DrawingArea):
	"""
	This class handles drawing the time line display. The time line is part of the
	TimeLineBar. TimeLine displays the time in minutes/seconds (MODE_HOURS_MINS_SECS)
	or bars and beats (MODE_BARS_BEATS). These modes are set in project.transport.
		
	To improve performance, the line isn't being constructed on each call of OnDraw. It
	is saved into self.savedLine as a gtk.gdk.Image. A new savedLine is constructed when
		- there is no savedLine
		- or project.transport.RedrawTimeLine is True
		- or project.RedrawTimeLine is True
		
	When the time line is constructed in MODE_HOURS_MINS_SECS, it dynamically adjusts
	its scale to the project.viewScale. MODE_BARS_BEATS does not support this (yet).
	"""

	""" GTK widget name """
	__gtype_name__ = 'TimeLine'
	
	""" Number of 'short' lines + 1 (Used for the MODE_HOURS_MINS_SECS timeline)
	Like this:	|				|		   	|
				|  |1 |2 |3 |4 	|  |  |  |  | etc
	"""
	_NUM_LINES = 5

	#_____________________________________________________________________

	def __init__(self, project, timelinebar, mainview):
		"""
		Creates a new instance of TimeLine
		
		Parameters:
			project - reference to Project (Project.py)
			timelinebar - reference of TimeLineBar (TimeLineBar.py)
			mainview - reference to JokosherApp (JokosherApp.py) - Not used atm.
		"""
		gtk.DrawingArea.__init__(self)
	
		self.project = project
		self.timelinebar = timelinebar
		self.mainview = mainview
		
		# Listen for changes in the project and the TransportManager
		self.project.transport.AddListener(self)
		self.project.AddListener(self)
		
		self.height = 44
		self.buttonDown = False
		self.dragging = False
		self.savedLine = None
	
		self.set_events(gtk.gdk.POINTER_MOTION_MASK |
								gtk.gdk.BUTTON_PRESS_MASK |
								gtk.gdk.BUTTON_RELEASE_MASK)
		self.connect("expose-event", self.OnDraw)
		self.connect("button_release_event", self.onMouseUp)
		self.connect("button_press_event", self.onMouseDown)
		self.connect("motion_notify_event", self.onMouseMove)
		self.connect("size_allocate", self.OnAllocate)
	#_____________________________________________________________________

	def OnAllocate(self, widget, allocation):
		"""
		From:
		http://www.moeraki.com/pygtkreference/pygtk2reference/class-gtkwidget.html#signal-gtkwidget--size-allocate
		The "size-allocate" signal is emitted when widget is given a new space allocation.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			allocation -- the position and size to be allocated to the widget.
		"""
		self.allocation = allocation
		# Reconstruce timeline because allocation changed
		self.DrawLine(widget)
		# Redraw the reconstructed timeline
		self.queue_draw()
		
	#_____________________________________________________________________
		
	def OnDraw(self, widget, event):
		"""
		Fires off the drawing operation.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
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
		
		# redraw area from saved gtk.gdk.Image
		d.draw_image(gc, self.savedLine,
					 event.area.x, event.area.y,
					 event.area.x, event.area.y,
					 event.area.width, event.area.height)

		# Draw play cursor position
		# Set the color:
		col = gc.get_colormap().alloc_color("#FF0000")
		gc.set_foreground(col)
		# And draw:
		x = int(round((self.project.transport.position - self.project.viewStart) * self.project.viewScale))
		d.draw_line(gc, x, 0, x, self.get_allocation().height)	
	
	#_____________________________________________________________________
		
	def DrawLine(self, widget):
		""" 
		Draws the timeline and saves it to memory
		Must be called initially and to redraw the timeline
		after moving the project start.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		d = widget.window

		gc = d.new_gc()
		
		y = 0
		
		# Draw the white background
		col = gc.get_colormap().alloc_color("#FFFFFF")
		gc.set_foreground(col)
		gc.set_fill(gtk.gdk.SOLID)
		
		d.draw_rectangle(	gc, True, # True = filled
							0, 
							0, 
							self.get_allocation().width, 
							self.get_allocation().height)
		
		# Draw a gray frame around the background
		col = gc.get_colormap().alloc_color("#555555")
		gc.set_foreground(col)
							
		d.draw_rectangle(	gc, False, # False = not filled
							0, 
							0, 
							self.get_allocation().width, 
							self.get_allocation().height)
		
		x = 0
		transport = self.project.transport
		if transport.mode == transport.MODE_BARS_BEATS:
			# Calculate our scroll offset
			# viewStart is in seconds. Seconds/60 = minutes. Minutes * Beat/Minute = beats (not an integer here)
			pos = (self.project.viewStart / 60.) * self.project.bpm
			# floor to an integer. beat = the last beat before viewStart
			beat = int(pos)
			# offset = part of a beat that has past since the last beat (offset < 1)
			offset = pos - beat
			
			if offset > 0.:
				# beats * ( pixels/minute ) / ( beats/minute ) = pixels
				# Set x to the position in pixels of the last beat 
				x -= offset * ((self.project.viewScale * 60.) / self.project.bpm)
				# (pixels/minute) / ( beats/minute) * 1 beat = pixels
				# Add the length of one beat, in pixels
				x += (self.project.viewScale * 60.) / self.project.bpm
				# x is now at the pixel-position of the first beat after the viewStart
				beat += 1
		
			while x < self.get_allocation().width:
				# Draw the beat/bar divisions
				ix = int(x)
				if beat % self.project.meter_nom:
					d.draw_line(gc, ix, int(self.get_allocation().height/1.2), ix, self.get_allocation().height)
				else:
					d.draw_line(gc, ix, int(self.get_allocation().height/2), ix, self.get_allocation().height)
					
					# Draw the bar number
					l = pango.Layout(self.create_pango_context())
					l.set_text(str((beat / self.project.meter_nom)+1))
					d.draw_layout(gc, ix, 5, l)
					
				beat += 1
				
				x += (60. / self.project.bpm ) * self.project.viewScale
		else:
			# Working in milliseconds here. Using seconds gives modulus problems because they're floats
			viewScale = self.project.viewScale / 1000.
			viewStart = int(self.project.viewStart * 1000)
			factor, displayMilliseconds = self.GetZoomFactor(viewScale)
			
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
				if msec % (self._NUM_LINES * factor):
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
		"""
		From:
		http://www.moeraki.com/pygtkreference/pygtk2reference/class-gtkwidget.html#signal-gtkwidget--size-request
		The "size-request" signal is emitted when a new size is
		requested for widget using the set_size_request() method.
		
		Parameters:
			requisition -- the widget's requested size as a gtk.Requisition.
		"""
		requisition.width = self.get_allocation().width
		requisition.height = self.height
		
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None, *extra):
		""" 
		Called when there is a change of state in transport	manager or project. 
		Could be one of
			*  Mode changed from bars/beats to minutes or vice versa
			(requires a complete redraw of timeline - flag set)
			*  Change in playing position -only needs partial redraw
			*  Project change e.g. a scroll or zoom change
			(requires a complete redraw of timeline - flag set)
				
		Parameters:
			obj -- an object to inform when this method is called.
			change -- the change which has occured.
			extra -- the extra parameters to be passed.
		"""
		#if the timeline is not currently on screen then quit
		if not self.window:
			return
		if self.project.transport.RedrawTimeLine or self.project.RedrawTimeLine:
			self.queue_draw()
			return
		# The next section is the autoscroll during playback
		# so ignore if where not in playback
		if self.project.GetIsPlaying() and not self.project.GetIsExporting():
			#if playhead is now beyond the rightmost position then  force scroll & quit
			rightPos = self.project.viewStart + self.timelinebar.projectview.scrollRange.page_size
			if self.project.transport.position > rightPos:
				while self.project.transport.position > rightPos:
					self.project.SetViewStart(rightPos)
					self.timelinebar.projectview.scrollRange.value = rightPos
					rightPos += self.timelinebar.projectview.scrollRange.page_size
				return
			#if playhead is beyond leftmost position the force scroll and quit
			if self.project.transport.position < self.project.viewStart:
				pos = self.project.viewStart
				while self.project.transport.position < pos:
					pos = max(0, pos - self.timelinebar.projectview.scrollRange.page_size)
					self.timelinebar.projectview.scrollRange.value = pos
				self.project.SetViewStart(pos)
				return
		x1 = round((self.project.transport.PrevPosition - self.project.viewStart) * self.project.viewScale)
		x2 = round((self.project.transport.position - self.project.viewStart) * self.project.viewScale)
		
		self.queue_draw_area(int(x1)-1, 0, 3, self.get_allocation().height)
		self.queue_draw_area(int(x2)-1, 0, 3, self.get_allocation().height)
		
	#_____________________________________________________________________
		
	def onMouseDown(self, widget, event):
		"""
		Called when a mouse button is clicked.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.buttonDown = True
		self.dragging = False
		self.moveHead(event.x)
		return True

	#_____________________________________________________________________

	def onMouseMove(self, widget, event):
		"""
		Called when the mouse pointer has moved.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly. 
		"""			
		if not self.buttonDown:
			return
		self.dragging = True
		
		# prevent playhead being dragged to the window edge - TODO make scrolling actually work!!
		pos = event.x /self.project.viewScale
		if (pos > 0.99 * self.timelinebar.projectview.scrollRange.page_size) or (pos < 0.01 * self.timelinebar.projectview.scrollRange.page_size):
			self.buttonDown = False
			return
		self.moveHead(event.x)
		
	#_____________________________________________________________________
		
	def onMouseUp(self, widget, event):
		"""
		Called when a mouse button is released.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.dragging = False
		self.buttonDown = False
		
	#_____________________________________________________________________
		
	def moveHead(self, xpos):
		"""
		Changes the project position to the time matching xpos.
		
		Parameters:
			xpos -- the time of the new project position.
		"""
		pos = self.project.viewStart + xpos/ self.project.viewScale
		self.project.transport.SeekTo(pos)
		
	#_____________________________________________________________________
	
	def GetZoomFactor(self, viewScale):
		"""
		To be used for drawing the MODE_HOURS_MINS_SECS timeline.
		
		Parameters:
			viewScale -- the view scale in pixels per second.
		
		Returns:
			- an integer factor to be multiplied with the viewScale to zoom the timeline in/out
			- a boolean indicating if milliseconds should be displayed
			The default factor is 1000, meaning that the distance between the short lines of the timeline
			symbolizes 1000 milliseconds. The code will increase of decrease this factor to keep the
			timeline readable. The factors can be set with the zoomLevels array. This array
			contains zoom levels that support precision from 20 ms to 1 minute. More extreme zoom
			levels could be added, but will never be reached because the viewScale is limited.
		"""
		shortTextWidth = 28 # for '0:00' notation
		longTextWidth = 56 # for '0:00:000' notation
		textWidth = shortTextWidth
		whiteSpace = 50
		factor = 1000 # Default factor is 1 second for 1 line
		zoomLevels = [20, 100, 200, 1000, 4000, 12000, 60000]
		if (textWidth + whiteSpace) > (self._NUM_LINES * factor * viewScale):
			factor = zoomLevels[zoomLevels.index(factor) + 1]
			while (textWidth + whiteSpace) > (self._NUM_LINES * factor * viewScale) and factor != zoomLevels[-1]:
				factor = zoomLevels[zoomLevels.index(factor) + 1]
		else:
			while (textWidth + whiteSpace) < (factor * viewScale) and factor != zoomLevels[0]:
				factor = zoomLevels[zoomLevels.index(factor) - 1]
				if factor == 200:
					textWidth = longTextWidth
		return factor, (factor < 200) # 0.2 * 5 = 1.0 second, if the interval is smaller, milliseconds are needed
	
#=========================================================================

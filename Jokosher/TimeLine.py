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
import cairo
import gobject

import gettext
_ = gettext.gettext

#=========================================================================

class TimeLine(gtk.DrawingArea):
	"""
	This class handles drawing the time line display. The time line is part of the
	TimeLineBar. TimeLine displays the time in minutes/seconds (MODE_HOURS_MINS_SECS)
	or bars and beats (MODE_BARS_BEATS). These modes are set in project.transport.
	
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
	
	"""
	Various color configurations:
	   ORGBA = Offset, Red, Green, Blue, Alpha
	   RGBA = Red, Green, Blue, Alpha
	   RGB = Red, Green, Blue
	"""
	_BORDER_RGB = (85./255, 85./255, 85./255)
	_BACKGROUND_RGB = (1, 1, 1)
	_TEXT_RGB = (0, 0, 0)
	_BEAT_BAR_RGB = (0, 0, 0)
	_PLAY_CURSOR_RGB = (1, 0, 0)
	
	"""
	   The events we wish to receive after we grab the mouse (and it is no longer above this widget)
	   If events other than mouse event are put in here, it may cause the program to crash.
	"""
	_POINTER_GRAB_EVENTS = (
			gtk.gdk.POINTER_MOTION_MASK |
			gtk.gdk.BUTTON_RELEASE_MASK |
			gtk.gdk.BUTTON_PRESS_MASK)
	
	"""Number of milliseconds between each scrollbar update while autoscrolling"""
	_AUTOSCROLL_UPDATE_INTERVAL = 100
	
	"""
		Speed is relative to distance between mouse and closest edge of the timeline.
		i.e. The further away you pull your mouse, the faster it scrolls.
		The speed, multiplied by the mouse's distance, is the amount we scroll each update.
	"""
	_AUTOSCROLL_SPEED = 0.2
	
	#_____________________________________________________________________

	def __init__(self, project, mainview):
		"""
		Creates a new instance of TimeLine
		
		Parameters:
			project - reference to Project (Project.py)
			mainview - reference to JokosherApp (JokosherApp.py) - Not used atm.
		"""
		gtk.DrawingArea.__init__(self)
	
		self.project = project
		self.mainview = mainview
		
		# Listen for changes in the project and the TransportManager
		self.project.transport.connect("transport-mode", self.OnTransportMode)
		self.project.transport.connect("position", self.OnTransportPosition)
		self.project.connect("bpm", self.OnProjectTimelineChange)
		self.project.connect("time-signature", self.OnProjectTimelineChange)
		self.project.connect("view-start", self.OnProjectTimelineChange)
		self.project.connect("zoom", self.OnProjectTimelineChange)
		
		self.height = 44
		self.buttonDown = False
		self.current_autoscroll_diff = 0

		# source is an offscreen canvas to hold our waveform image
		self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, 0, 0)
		
		#rectangle of cached draw area
		self.cachedDrawArea = gtk.gdk.Rectangle(0, 0, 0, 0)

		# Accessibility helpers
		self.SetAccessibleName()
		self.set_property("can-focus", True)
	
		self.set_events(self._POINTER_GRAB_EVENTS)
		self.set_flags(gtk.CAN_FOCUS)
		
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
			widget -- reserved for GTK callbacks.
			allocation -- the gtk.gdk.Rectangle allocated to the widget.
		"""
		self.allocation = allocation
		
		# Reconstruct the timeline because the size allocation changed
		self.DrawLine()
		
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
		area = event.area
		cache = self.cachedDrawArea
		
		#check if the expose area is within the already cached rectangle
		if area.x < cache.x or (area.x + area.width > cache.x + cache.width):
			self.DrawLine()
		
		# Get a cairo surface for this drawing op
		context = widget.window.cairo_create()

		# Give it our timeline image as a source
		context.set_source_surface(self.source, 0, 0)
		# TODO: see what's the problem with using the cached (x,y) values
		#context.set_source_surface(self.source, self.cachedDrawArea.x, self.cachedDrawArea.y)

		# Blit our timeline
		context.paint()
		
		# Draw play cursor position (add 1 so it lines up correctly)
		x = self.project.transport.GetPixelPosition()
		context.set_line_width(1)
		context.move_to(x+0.5, 0)
		context.line_to(x+0.5, self.allocation.height)
		context.set_antialias(cairo.ANTIALIAS_NONE)
		context.set_source_rgb(*self._PLAY_CURSOR_RGB)
		context.stroke()
	
	#_____________________________________________________________________
		
	def DrawLine(self):
		""" 
		Uses Cairo to draw the timeline onto a canvas in memory.
		Must be called initially and to redraw the timeline
		after moving the project start.
		
		Parameters:
			allocation -- the gtk.gdk.Rectangle allocated to the widget.
		"""
		allocArea = self.get_allocation()
		
		#rect = gtk.gdk.Rectangle(allocArea.x - allocArea.width, allocArea.y,
		#				allocArea.width*3, allocArea.height)
		
		# TODO: temporary rect initialization
		rect = allocArea
		
		#Check if our area to cache is outside the allocated area
		#if rect.x < 0:
		#	rect.x = 0
		#if rect.x + rect.width > allocArea.width:
		#	rect.width = allocArea.width - rect.x
		
		self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, rect.width, rect.height)
		
		context = cairo.Context(self.source)
		context.set_line_width(2)
		context.set_antialias(cairo.ANTIALIAS_NONE)

		# Draw white background
		context.rectangle(0, 0, rect.width, rect.height)
		context.set_source_rgb(*self._BACKGROUND_RGB)
		context.fill()
		
		# Draw the widget border
		context.set_line_width(0.2)
		context.rectangle(0, 0, rect.width, rect.height)
		context.set_source_rgb(*self._BORDER_RGB)
		context.stroke()
		
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
				
				# (pixels/minute) / (beats/minute) * 1 beat = pixels
				# Add the length of one beat, in pixels
				x += (self.project.viewScale * 60.) / self.project.bpm
				
				# x is now at the pixel-position of the first beat after the viewStart
				beat += 1

			spacing = (60. / self.project.bpm) * self.project.viewScale

			if self.project.meter_denom == 8 and (self.project.meter_nom % 3) == 0 and self.project.meter_nom != 3:
				# Compound time signature, so beats are really 1 dotted note (3 1/8 notes)
				beats_per_bar = self.project.meter_nom / 3
				spacing *= 3
			else:
				# Simple meter
				beats_per_bar = self.project.meter_nom
		
			while x < self.get_allocation().width:
				# Draw the beat/bar divisions
				ix = int(x)

				if beat % beats_per_bar:
					lineHeight = int(self.get_allocation().height/1.2)
				else:
					lineHeight = int(self.get_allocation().height/2)
					
					# Draw the bar number
					context.set_source_rgb(*self._TEXT_RGB)
					number = (beat / beats_per_bar)+1
					
					# TODO: small hack to fix a problem with the numbers not being
					#       properly centered
					if(number == 1):
						context.move_to(ix, 15)
					else:
						context.move_to(ix-3, 15)
						
					context.show_text(str(number))
				
				# Draw the bar itself	
				context.move_to(ix, lineHeight)
				context.line_to(ix, self.get_allocation().height)
				context.set_source_rgb(*self._BEAT_BAR_RGB)
				context.stroke()
					
				beat += 1

				x += spacing
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
					lineHeight = int(self.get_allocation().height/1.2)
				else:
					lineHeight = int(self.get_allocation().height/2)
					
					# Draw the bar number
					if displayMilliseconds:
						#Should use transportmanager for this...
						number = "%d:%02d:%03d"%((msec/1000) / 60, (msec/1000) % 60, msec%1000)
					else:
						number = "%d:%02d"%((msec/1000) / 60, (msec/1000) % 60)
						
					context.set_source_rgb(*self._TEXT_RGB)
					context.move_to(ix, 15)
					context.show_text(number)
				
				# Draw the bar itself
				context.move_to(ix, lineHeight)
				context.line_to(ix, self.get_allocation().height)
				context.set_source_rgb(*self._BEAT_BAR_RGB)
				context.stroke()
				
				msec += factor
				x += viewScale * factor
		
		#set area to record where the cached surface goes
		self.cachedDrawArea = rect
	
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
	
	def OnProjectTimelineChange(self, project):
		"""
		Callback for signal when time signature, zoom level,
		bpm or view start of the project change. All of these things
		effect the way that the timeline is drawn.
		
		Parameters:
			project -- the project instance that send the signal.
		"""
		self.queue_draw()
		
	#_____________________________________________________________________
	
	def OnTransportMode(self, transportManager, mode):
		"""
		Callback for signal when the transport mode changes.
		
		Parameters:
			transportManager -- the TransportManager instance that send the signal.
			mode -- the mode type that the transport changed to.
		"""
		self.queue_draw()
	
	#_____________________________________________________________________
	
	def OnTransportPosition(self, transportManager, extraString):
		"""
		Callback for signal when the transport position changes.
		
		Parameters:
			transportManager -- the TransportManager instance that send the signal.
			extraString -- a string specifying the extra action details. i.e. "stop-action"
					means that the position changed because the user hit stop.
		"""
	
		#if the timeline is not currently on screen then quit
		if not self.window:
			return
		
		width_in_secs = self.allocation.width / self.project.viewScale
		# The left and right sides of the viewable area
		rightPos = self.project.viewStart + width_in_secs
		leftPos = self.project.viewStart
		currentPos = self.project.transport.GetPosition()
		
		# Check if the playhead was recently viewable (don't force it in view if it wasn't previously in view)
		# Don't autoscroll if "stop-action" is send in extra because that means the 
		# user just hit stop and did not purposely change the position.
		if "stop-action" != extraString:
			if leftPos < self.project.transport.GetPreviousPosition() < rightPos:
				if currentPos > rightPos:
					# now the playhead has moved off to the right, so force the scroll in that direction
					self.project.SetViewStart(rightPos)
			
				elif currentPos < leftPos:
					#if playhead is beyond leftmost position then force scroll and quit
					leftPos = max(0, leftPos - width_in_secs)
					self.project.SetViewStart(leftPos)
	
		prev_pos = self.project.transport.GetPreviousPixelPosition()
		new_pos = self.project.transport.GetPixelPosition()
	
		self.queue_draw_area(prev_pos - 1, 0, 3, self.get_allocation().height)
		self.queue_draw_area(new_pos - 1, 0, 3, self.get_allocation().height)
	
	#_____________________________________________________________________
	
	def onMouseDown(self, widget, event):
		"""
		Called when a mouse button is clicked.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
			
		Returns:
			True -- to continue the GTK signal propagation.
		"""
		
		response = gtk.gdk.pointer_grab(self.window, False, self._POINTER_GRAB_EVENTS, None, None, event.time)
		self.buttonDown = (response == gtk.gdk.GRAB_SUCCESS)
		self.current_autoscroll_diff = 0
		self.moveHead(event.x)
		self.grab_focus()
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
		
		old_diff = self.current_autoscroll_diff
		
		alloc = self.get_allocation()
		xpos = event.x
		if 0 < xpos < alloc.width:
			self.current_autoscroll_diff = 0
			self.moveHead(xpos)
		else:
			if xpos > alloc.width:
				self.current_autoscroll_diff = (xpos - alloc.width) * self._AUTOSCROLL_SPEED
			else:
				self.current_autoscroll_diff = xpos * self._AUTOSCROLL_SPEED
			
			if old_diff == 0:
				gobject.timeout_add(self._AUTOSCROLL_UPDATE_INTERVAL, self.onUpdateAutoscroll)
		
	#_____________________________________________________________________
	
	def onUpdateAutoscroll(self):
		if self.current_autoscroll_diff:
			if self.current_autoscroll_diff > 0:
				start_xpos = self.current_autoscroll_diff;
				playhead_xpos = start_xpos + self.allocation.width - 1
			else:
				start_xpos = self.current_autoscroll_diff
				playhead_xpos = start_xpos
				
			start = self.project.viewStart + (start_xpos / self.project.viewScale)
			playhead = self.project.viewStart + (playhead_xpos / self.project.viewScale)
			
			self.project.SetViewStart(start)
			self.project.transport.SeekTo(playhead)

			return True
		else:
			return False
		
	#_____________________________________________________________________
		
	def onMouseUp(self, widget, event):
		"""
		Called when a mouse button is released.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.buttonDown:
			self.buttonDown = False
			self.current_autoscroll_diff = 0
			gtk.gdk.pointer_ungrab(event.time)
		
		return True
		
	#_____________________________________________________________________
		
	def moveHead(self, xpos):
		"""
		Changes the project position to the time matching xpos.
		
		Parameters:
			xpos -- the time of the new project position.
		"""
		pos = self.project.viewStart + (xpos / self.project.viewScale)
		pos = max(0., pos)
		self.project.transport.SeekTo(pos)
		self.SetAccessibleName()
		
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
	
	#_____________________________________________________________________
	
	def SetAccessibleName(self):
		"""
		Set a name property in ATK to help users with screenreaders.
		"""
		if self.project.transport.mode == self.project.transport.MODE_BARS_BEATS:
			tuple_ = self.project.transport.GetPositionAsBarsAndBeats()
			position_text = _("Timeline, %(bars)d bars, %(beats)d beats and %(ticks)d ticks in") % \
					{"bars":tuple_[0], "beats":tuple_[1], "ticks":tuple_[2]}
		else:
			tuple_ = self.project.transport.GetPositionAsHoursMinutesSeconds()
			position_text = _("Timeline, %(hours)d hours, %(mins)d minutes, %(secs)d seconds and %(millis)d milliseconds in") % \
					{"hours":tuple_[0], "mins":tuple_[1], "secs":tuple_[2], "millis":tuple_[3]}

		self.get_accessible().set_name(position_text)

	#_____________________________________________________________________
	
#=========================================================================

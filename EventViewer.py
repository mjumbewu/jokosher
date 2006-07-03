
import sys
import gtk
import math
import cairo
import Project
import Monitored
import Utils

#=========================================================================

class EventViewer(gtk.DrawingArea):
	""" The EventViewer class handles displaying a single event as part
		of an EventLaneViewer object.
	"""

	__gtype_name__ = 'EventViewer'
	
	#the maximum width of the stroke above the fill
	#stroke width will shrink when zooming out
	_MAX_LINE_WIDTH = 2
	
	#the width and height of the volume curve handles
	_PIXX_FADEMARKER_WIDTH = 30
	_PIXY_FADEMARKER_HEIGHT = 11
	
	"""various colour configurations
	   ORGBA = Offset, Red, Green, Blue, Alpha
	   RGBA = Red, Green, Blue, Alpha
	   RGB = Red, Green, Blue
	"""
	_OPAQUE_GRADIENT_STOP_ORGBA = (0.2, 138./255, 226./255, 52./255, 1)
	_TRANSPARENT_GRADIENT_STOP_ORGBA = (1, 138./255, 226./255, 52./255, 0.5)
	_BORDER_RGB = (79./255, 154./255, 6./255)
	_BACKGROUND_RGB = (1, 1, 1)
	_TEXT_RGB = (0, 0, 0)
	_SELECTED_RGBA = (0, 0, 1, 0.2)
	_SELECTION_RGBA = (0, 0, 1, 0.5)
	_FADEMARKERS_RGBA = (1, 0, 0, 0.8)
	_PLAY_POSITION_RGB = (1, 0, 0)
	_HIGHLIGHT_POSITION_RGB = (0, 0, 1)
	_FADELINE_RGB = (1, 0.7, 0.7)
	
	#_____________________________________________________________________

	def __init__(self, lane, project, event, height, eventlaneviewer, mainview,  small = False):

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
		
		self.height = height			# Height of this object in pixels
		self.event = event				# The event this widget is representing
		self.project = project			# A reference to the open project
		self.isDragging = False			# True if this event is currently being dragged
		# Selections--marking part of the waveform. Don't confuse this with
		# self.event.isSelected, which means the whole waveform is selected.
		self.isSelecting = False		# True if a selection is currently being set
		self.Selection = [0,0]			# Selection begin and end points
		self.isDraggingFade = False		# True if the user is dragging a fade marker
		self.lane = lane				# The parent lane for this object
		self.last_num_levels = 0		# Used to track if we need to resize the GUI object
		self.isLoading = False			# Used to track if we need to update the GUI after loading a waveform
		self.currentScale = 0			# Tracks if the project viewScale has changed
		self.redrawWaveform = False		# Force redraw the cached waveform on next expose event
		self.eventDuration = 0
		
		# source is an offscreen canvas to hold our waveform image
		self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, 0, 0)
		#rectangle of cached draw area
		self.cachedDrawArea = gtk.gdk.Rectangle(0, 0, 0, 0)

		# Monitor the things this object cares about
		self.project.AddListener(self)
		self.event.AddListener(self)

		# This defines where the blue cursor indicator should be drawn (in pixels)
		self.highlightCursor = None
		
		self.fadeMarkersContext = None
		
		# drawer: this will probably be its own object in time
		self.drawer = gtk.HBox()
		trimButton = gtk.Button("T")
		self.drawer.add(trimButton)
		effectButton = gtk.Button("E")
		self.drawer.add(effectButton)
		trimButton.connect("clicked", self.TrimToSelection)
		self.drawer.show()
		
		self.mainview = mainview
		self.eventlaneviewer = eventlaneviewer
		self.messageID = None
		self.volmessageID = None
		self.selmessageID = None
	#_____________________________________________________________________

	def OnDraw(self, widget, event):
		""" This function blits the waveform data onto the screen, and
			then draws the play cursor over it.
		"""
		c = self.cachedDrawArea
		e = event.area
		
		#check if the expose area is within the already cached rectangle
		if e.x < c.x or (e.x + e.width > c.x + c.width) or self.redrawWaveform:
			self.DrawWaveform(event.area)
		
		# Get a cairo surface for this drawing op
		context = widget.window.cairo_create()

		# Give it our waveform image as a source
		context.set_source_surface(self.source, self.cachedDrawArea.x, self.cachedDrawArea.y)	

		# Blit our waveform across
		context.paint()

		# Overlay an extra rect if we're selected
		if self.event.isSelected:
			context.rectangle(event.area.x, event.area.y,
							  event.area.width, event.area.height)
			context.set_source_rgba(*self._SELECTED_RGBA)
			context.fill()
		
		
		#Draw play position
		x = int(round((self.project.transport.position - self.event.start) * self.project.viewScale))
		context.set_line_width(1)
		context.set_antialias(cairo.ANTIALIAS_NONE)
		context.move_to(x+1, 0)
		context.line_to(x+1, self.allocation.height)
		context.set_source_rgb(*self._PLAY_POSITION_RGB)
		context.stroke()
		
		# Draw the highlight cursor if it's over us and we're not dragging a fadeMarker
		if self.highlightCursor and not self.isDraggingFade:
			context.move_to(self.highlightCursor, 0)
			context.line_to(self.highlightCursor, self.allocation.height)
			context.set_source_rgb(*self._HIGHLIGHT_POSITION_RGB)
			context.set_dash([3,1],1)
			context.stroke()
			pixbuf = widget.render_icon(gtk.STOCK_CUT, gtk.ICON_SIZE_SMALL_TOOLBAR)
			widget.window.draw_pixbuf(None, pixbuf, 0, 0, int(self.highlightCursor), 0)
			

		# Overlay an extra rect if there is a selection
		self.fadeMarkersContext = None
		if self.Selection != [0,0]:
			x1,x2 = self.Selection[:]
			if x2 < x1:
				x2,x1 = x1,x2
			context.rectangle(event.area.x + x1, event.area.y,
							  event.area.x + x2 - x1, event.area.height)
			context.set_source_rgba(*self._SELECTION_RGBA)
			context.fill()
			
			#subtract fade marker height so that it is not drawn partially offscreen
			padded_height = self.allocation.height - self._PIXY_FADEMARKER_HEIGHT
			
			# and overlay the fademarkers
			context.set_source_rgba(*self._FADEMARKERS_RGBA)
			
			pixxFM_left = event.area.x + x1 + 1 - self._PIXX_FADEMARKER_WIDTH
			pixyFM_left = int(padded_height * (100-self.fadePoints[0]) / 100.0)
			context.rectangle(pixxFM_left, pixyFM_left,
			                  self._PIXX_FADEMARKER_WIDTH , self._PIXY_FADEMARKER_HEIGHT)
			
			pixxFM_right = event.area.x + x2
			pixyFM_right = int(padded_height * (100-self.fadePoints[1]) / 100.0)
			context.rectangle(pixxFM_right, pixyFM_right,
			                  self._PIXX_FADEMARKER_WIDTH, self._PIXY_FADEMARKER_HEIGHT)
			
			context.fill()
			
			context.set_source_rgba(1,1,1,1)
			context.move_to(pixxFM_left + 1, pixyFM_left + self._PIXY_FADEMARKER_HEIGHT - 1)
			context.show_text("%s%%" % int(self.fadePoints[0]))
			context.move_to(pixxFM_right + 1, pixyFM_right + self._PIXY_FADEMARKER_HEIGHT - 1)
			context.show_text("%s%%"% int(self.fadePoints[1]))
			context.stroke()
			
			# redo the rectangles so they're the path and we can in_fill() check later
			context.rectangle(pixxFM_left, pixyFM_left,
			                  self._PIXX_FADEMARKER_WIDTH, self._PIXY_FADEMARKER_HEIGHT)
			context.rectangle(pixxFM_right, pixyFM_right,
			                  self._PIXX_FADEMARKER_WIDTH, self._PIXY_FADEMARKER_HEIGHT)
			self.fadeMarkersContext = context

		return False
		
	#_____________________________________________________________________

	def DrawWaveform(self, exposeArea):
		""" This function uses Cairo to draw the waveform level information
			onto a canvas in memory.
		"""
		allocArea = self.get_allocation()
		
		rect = gtk.gdk.Rectangle(exposeArea.x - exposeArea.width, exposeArea.y,
						exposeArea.width*3, exposeArea.height)
		#Check if our area to cache is outside the allocated area
		if rect.x < 0:
			rect.x = 0
		if rect.x + rect.width > allocArea.width:
			rect.width = allocArea.width - rect.x
			
		self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, rect.width, rect.height)

		context = cairo.Context(self.source)
		context.set_line_width(2)
		context.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
		
		if self.event.isLoading:
			# Draw a white background
			context.rectangle(0, 0, rect.width, rect.height)
			context.set_source_rgb(*self._BACKGROUND_RGB)
			context.fill()
			# and a border
			context.set_line_width(2)
			context.rectangle(0, 0, rect.width, rect.height)
			context.set_source_rgb(*self._TEXT_RGB)
			context.stroke()
			# Write "Loading..."
			context.move_to(5, 12)
			if self.event.duration == 0:
				displayLength = 0
			else:
				displayLength = int(100 * self.event.loadingLength / self.event.duration)
			context.show_text("Loading (%d%%)..." % displayLength)
			context.stroke()
			# And exit here
			return
		
		if len(self.event.levels) == 0:
			raise "Trying to draw an event with no level data!"
		
		scale = (self.event.duration * self.project.viewScale) / float(len(self.event.levels))

		# Draw white background
		context.rectangle(0, 0, rect.width, rect.height)
		context.set_source_rgb(*self._BACKGROUND_RGB)
		context.fill()

		# draw the fade line
		context.set_source_rgb(*self._FADELINE_RGB)
		context.move_to(0,0) # FIXME: scale the Y!
		pixy = 0
		for sec,vol in self.event.audioFadePoints:
			pixx = self.pixxFromSec(sec)
			pixy = self.pixyFromVol(vol)
			context.line_to(pixx,pixy)
		pixxEnd = self.pixxFromSec(self.event.duration)
		context.line_to(pixxEnd,pixy)
		
		context.stroke()

		# Draw volume curve
		x_pos = int(rect.x/scale)
		x = 0
		context.move_to(0,rect.height)
				
		# calculate the fade curve
		fadecurve = self.getFadeCurve(self.event.duration, 
		            self.event.audioFadePoints, 
		            len(self.event.levels))
		# apply the fade curve to the volume curve to get new volumes
		levelsToUse = [x[0]*x[1] for x in zip(self.event.levels,fadecurve)]
		
		for peak in levelsToUse[x_pos:]:
			x = (x_pos*scale) - rect.x
			peakOnScreen = int(peak * rect.height)
			context.line_to(x, rect.height - peakOnScreen)
			
			if x > rect.width:
				break
			x_pos += 1
		
		context.line_to(x, rect.height)
		
		#levels gradient fill
		gradient = cairo.LinearGradient(0.0, 0.0, 0, rect.height)
		gradient.add_color_stop_rgba(*self._OPAQUE_GRADIENT_STOP_ORGBA)
		gradient.add_color_stop_rgba(*self._TRANSPARENT_GRADIENT_STOP_ORGBA)
		context.set_source(gradient)
		context.fill_preserve()
		
		#levels path (on top of the fill)
		context.set_source_rgb(*self._BORDER_RGB)
		context.set_line_join(cairo.LINE_JOIN_ROUND)
		if scale < self._MAX_LINE_WIDTH:
			context.set_line_width(scale)
		else:
			context.set_line_width(self._MAX_LINE_WIDTH)
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
		context.set_source_rgb(*self._BORDER_RGB)
		context.stroke()
		context.set_line_width(2)
		
		#check if we are at the beginning
		if rect.x == 0:
			#Draw event name
			context.set_source_rgb(*self._TEXT_RGB)
			context.move_to(5, 12)
			context.show_text(self.event.name)
		
		#set area to record where the cached surface goes
		self.cachedDrawArea = rect
		self.redrawWaveform = False

	#_____________________________________________________________________

	def OnMouseMove(self,widget,mouse):
	
		if not self.window:
			return
		# display status bar message if has not already been displayed
		if not self.messageID: 
			self.messageID = self.mainview.SetStatusBar("To <b>Split, Double-Click</b> the wave - To <b>Select, Shift-Click</b> and drag the mouse")
		
		if self.isDraggingFade:
			#subtract half the fademarker height so it doesnt go half off the screen
			cur_pos = (mouse.y - (self._PIXY_FADEMARKER_HEIGHT / 2))
			height = self.allocation.height - self._PIXY_FADEMARKER_HEIGHT
			percent = cur_pos / float(height)
			percent = max(0, percent)
			percent = min(1, percent)
			
			self.fadePoints[self.fadeBeingDragged] = 100 - int(percent * 100)
			self.queue_draw()
			
			if not self.volmessageID:
				self.volmessageID = self.mainview.SetStatusBar("<b>NOTE</b>: The volume sliders in this pre-release version of Jokosher do not affect the audio.")
			
			return True

		if self.fadeMarkersContext and self.fadeMarkersContext.in_fill(mouse.x, mouse.y):
			# quit this function now, so the highlightCursor doesn't move
			# while you're over a fadeMarker
			return True
			
		if self.isDragging:
			ptr = gtk.gdk.display_get_default().get_pointer()
			x = ptr[1]
			y = ptr[2]
			dx = float(x - self.mouseAnchor[0]) / self.project.viewScale
			time = self.event.start + dx
			time = max(0, time)
			
			if self.event.MayPlace(time):
				self.event.start = time
				self.lane.Update(self)
				self.mouseAnchor = [x, y]
			else:
				temp = self.event.start
				self.event.MoveButDoNotOverlap(time)
				self.lane.Update(self)
				
				#MoveButDoNotOverlap() moves the event out of sync with the mouse
				#and the mouseAnchor must be updated manually.
				delta = (self.event.start - temp) * self.project.viewScale
				self.mouseAnchor[0] += int(delta)
				
				
			self.highlightCursor = None
		elif self.isSelecting:
			self.Selection[1] = max(0,min(self.allocation.width,mouse.x))
		else:
			self.highlightCursor = mouse.x
		
		self.lane.childActive = True
		self.queue_draw()
		return True

	#_____________________________________________________________________
	
	def OnMouseDown(self, widget, mouse):
		""" Possible clicks to capture:
		   {L|R}MB: deselect all events, remove any existing selection in this event,
		      select this event, begin moving the event
		   LMB+shift: remove any existing selection in this event, begin 
		      selecting part of this event
		   {L|R}MB+ctrl: select this event without deselecting other events
		   RMB: context menu
		   LMB double-click: split here
		   LMB over a fadeMarker: drag that marker
		"""
		
		# {L|R}MB: deselect all events, select this event, begin moving the event
		# {L|R}MB+ctrl: select this event without deselecting other events
		if 'GDK_CONTROL_MASK' not in mouse.state.value_names:
			self.project.ClearEventSelections()
			self.project.ClearInstrumentSelections()
		self.event.SetSelected(True)
		
		# RMB: context menu
		if mouse.button == 3:
			self.ContextMenu(mouse)
		elif mouse.button == 1:
			if 'GDK_SHIFT_MASK' in mouse.state.value_names:
				# LMB+shift: remove any existing selection in this event, begin 
				#   selecting part of this event
				self.isSelecting = True
				self.Selection[0] = mouse.x
				self.fadePoints = [100,100]
				if not self.selmessageID: 
					self.selmessageID = self.mainview.SetStatusBar("<b>Click</b> the buttons below the selection to do something to that portion of audio.")
			else:
				if self.fadeMarkersContext and self.fadeMarkersContext.in_fill(mouse.x, mouse.y):
					# LMB over a fadeMarker: drag that marker
					self.isDraggingFade = True
					if mouse.x > self.Selection[1]:
						self.fadeBeingDragged = 1
						return True
					else:
						self.fadeBeingDragged = 0
						return True
				if mouse.type == gtk.gdk._2BUTTON_PRESS:
					# LMB double-click: split here
					self.mouseAnchor[0] = mouse.x
					self.OnSplit(None)
					return True
				
				# remove any existing selection in this event
				self.Selection = [0,0]
				if self.drawer.parent == self.lane.fixed:
					self.lane.fixed.remove(self.drawer)
					if self.volmessageID:   #clesr status bar if not already clear
						self.mainview.ClearStatusBar(self.volmessageID)
						self.volmessageID = None
					if self.selmessageID:   #clesr status bar if not already clear
						self.mainview.ClearStatusBar(self.selmessageID)
						self.selmessageID = None	
				self.isDragging = True
				
				self.eventStart = self.event.start
				ptr = gtk.gdk.display_get_default().get_pointer()
				self.mouseAnchor = [ptr[1], ptr[2]]
	
		return True

	#_____________________________________________________________________
		
	def ContextMenu(self,mouse):
		m = gtk.Menu()
		items = [	("Split", self.OnSplit, True),
					("---", None, None),
					("Cut", self.OnCut, True),
					("Copy", self.OnCopy, True),
					("Delete", self.OnDelete, True)
				] 

		for i, cb, sensitive in items: 
			if i == "---":
				a = gtk.SeparatorMenuItem()
			else:
				a = gtk.MenuItem(i)
			
			a.set_sensitive(bool(sensitive))
			a.show() 
			m.append(a) 
			if cb:
				a.connect("activate", cb) 
		self.highlightCursor = mouse.x
		self.popupIsActive = True

		m.popup(None, None, None, mouse.button, mouse.time)
		m.connect("selection-done",self.OnMenuDone)
		
		self.mouseAnchor = [mouse.x, mouse.y]
			
	#_____________________________________________________________________
	
	def OnMenuDone(self, widget):
		self.popupIsActive = False
		self.highlightCursor = None
		
	#_____________________________________________________________________
		
	def OnMouseUp(self, widget, mouse):
		
		if mouse.button == 1:
			if self.isDragging:		
				self.isDragging = False
				if (self.eventStart != self.event.start):
					self.event.Move(self.eventStart, self.event.start)
					return False #need to pass this button release up to RecordingView
			elif self.isDraggingFade:
				self.isDraggingFade = False
				# set the audioFadePoints appropriately
				self.setAudioFadePointsFromCurrentSelection()
			elif self.isSelecting:
				self.isSelecting = False
				selection_direction = "ltor"
				if self.Selection[0] > self.Selection[1]:
					self.Selection = [self.Selection[1], self.Selection[0]]
					selection_direction = "rtol"
				eventx = int((self.event.start - self.project.viewStart) *
				              self.project.viewScale)
				if selection_direction == "ltor":
					width = self.drawer.allocation.width
					if width == 1: width = 40 # fudge it because it has no width initially
					x = int(self.Selection[1] - width)
					if self.drawer.parent == self.lane.fixed:
						self.lane.fixed.remove(self.drawer)
					self.lane.fixed.put(self.drawer,eventx + x,75)
				else:
					if self.drawer.parent == self.lane.fixed:
						self.lane.fixed.remove(self.drawer)
					self.lane.fixed.put(self.drawer,eventx + int(self.Selection[0]),75)
				self.lane.Update()
				
				
	#_____________________________________________________________________
		
	def OnMouseLeave(self, widget, event):
		if self.messageID:   #clesr status bar if not already clear
			self.mainview.ClearStatusBar(self.messageID)
			self.messageID = None
		self.highlightCursor = None
		self.lane.childActive = False
		self.queue_draw()
		
	#_____________________________________________________________________
			
	def OnSplit(self, evt):
		x = self.mouseAnchor[0]
		if x==0.0:
			return
		x /= float(self.project.viewScale)
		self.event.Split(x)
		self.lane.Update()
		
	#_____________________________________________________________________
	
	def OnCut(self, gtkevent):
		self.project.clipboardList = [self.event]
		self.OnDelete()
	
	#_____________________________________________________________________
	
	def OnCopy(self, gtkevent):
		self.project.clipboardList = [self.event]
	
	#_____________________________________________________________________

	def OnDelete(self, evt=None):
		# delete event
		self.lane.childActive = False
		self.event.Delete()
		self.lane.Update()
	
	#_____________________________________________________________________
		
	def TrimToSelection(self, evt):
		# Cut this event down so only the selected bit remains. This event
		# is L-S-R, where S is the selected bit; we're removing L and R.

		leftOfSel = self.Selection[0] / float(self.project.viewScale)
		rightOfSel = self.Selection[1] / float(self.project.viewScale)
		
		# Hide the drawer
		self.lane.fixed.remove(self.drawer)

		self.event.Trim(leftOfSel, rightOfSel)
		self.Selection = [0,0]

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
	
	def OnStateChanged(self, obj, change=None):
		if self.isLoading != self.event.isLoading:
			self.redrawWaveform = True
			self.isLoading = self.event.isLoading
		
		if self.event.duration != self.eventDuration:
			#the position may have changed once the correct duration was determined
			self.lane.Update(self)
			self.eventDuration = self.event.duration
				
		if len(self.event.levels) != self.last_num_levels:
			self.redrawWaveform = True
			self.queue_resize()
			self.last_num_levels = len(self.event.levels)
			
		if type(obj) == Project.Project:
			if self.currentScale != self.project.viewScale:
				self.redrawWaveform = True
				self.queue_resize()
				self.last_num_levels = len(self.event.levels)
				self.currentScale = self.project.viewScale

		self.queue_draw()

	#_____________________________________________________________________
	
	def getFadeCurve(self, duration, fades, totalLevels):
		"""The fade curve is a list of multipliers; the list is the
		   length of the levels list, and to make the actual levels list,
		   you take the ordinary levels list and multiply each level by
		   its corresponding entry in the fadecurve.
		   Pass the duration of the sample, the list of audio fade points, 
		   and the number of levels
		"""
		
		# no fades registered
		if not fades:
			return [1.0] * totalLevels
		
		oneSecondInLevels = int(totalLevels / duration)
		# get the first volume value; the whole clip must start at that
		fadecurve = []
		currentfade = (0.0,fades[0][1])
		myfades = fades + [(duration,fades[-1][1])]
		for thisfade in myfades:
			levelsInThisSection = int((thisfade[0] - currentfade[0]) * oneSecondInLevels)
			if thisfade[1] == currentfade[1]:
				# not actually a fade, just two points at the same volume
				fadecurve += [currentfade[1]] * levelsInThisSection
			else:
				step = (thisfade[1] - currentfade[1]) / levelsInThisSection
				adder = list(Utils.floatRange(currentfade[1], thisfade[1], step))
				fadecurve += adder
			currentfade = thisfade
		return fadecurve
		
	#_____________________________________________________________________

	def pixxFromSec(self, sec):
		"""Converts seconds to an X pixel position in the waveform"""
		return round(float(sec) / self.event.duration * self.allocation.width)
	
	#_____________________________________________________________________
	
	def secFromPixx(self,pixx):
		"""Converts an X pixel position in the waveform into seconds"""
		return (float(pixx) / self.allocation.width) * self.event.duration
	
	#_____________________________________________________________________
	
	def pixyFromVol(self, vol):
		"""Converts volume (0.0-1.0) to a Y pixel position in the waveform"""
		return round((1.0 - vol) * self.allocation.height)
	
	#_____________________________________________________________________
	
	def volFromPixy(self,pixy):
		"""Converts a Y pixel position in the waveform into a volume (0.0-1.0)"""
		return 1.0 - (float(pixy) / self.allocation.height)

	#_____________________________________________________________________
	
	def setAudioFadePointsFromCurrentSelection(self):
		secLeft = self.secFromPixx(self.Selection[0])
		secRight = self.secFromPixx(self.Selection[1])
		
		# fadePoints values are a percentage
		pixyLeft = ((100-self.fadePoints[0]) / 100.0) * self.allocation.height
		pixyRight = ((100-self.fadePoints[1]) / 100.0) * self.allocation.height
		
		volLeft = self.volFromPixy(pixyLeft)
		volRight = self.volFromPixy(pixyRight)
		
		self.event.addAudioFadePoints((secLeft,volLeft), (secRight,volRight))
		self.redrawWaveform = True
		
	#_____________________________________________________________________
	
#=========================================================================

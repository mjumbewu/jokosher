#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	EventViewer.py
#	
#	This module is the gui class that represents an event.
#	It handles the drawing of the waveform, audio fades, and
#	anything else that happens when you click a rectangular 
#	event on the gui.
#
#-------------------------------------------------------------------------------

import gtk
import cairo
import Project
import Utils
import os
import gettext
_ = gettext.gettext
import Globals

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
	_FADELINE_RGB = (1, 0.6, 0.6)
	
	#_____________________________________________________________________

	def __init__(self, lane, project, event, height, eventlaneviewer, mainview,  small = False):

		self.small = small
		
		self.selectiontip = gtk.Tooltips()
		
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
		self.isDraggingFade = False		# True if the user is dragging a fade marker
		self.lane = lane				# The parent lane for this object
		self.currentScale = 0			# Tracks if the project viewScale has changed
		self.redrawWaveform = False		# Force redraw the cached waveform on next expose event
		self.drawerAlignToLeft = True		#boolean; if the drawer should be at the left of current selection
									#otherwise it will be put on the right
		self.fadeMarkers = [100,100]		#the values of the right and left fade markers on the selection
		
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
		trimButton = gtk.Button()
		trimimg = gtk.Image()
		trimimg.set_from_file(os.path.join(Globals.IMAGE_PATH, "icon_trim.png"))
		trimButton.set_image(trimimg)
		self.selectiontip.set_tip(trimButton,_("Trim"),None)

		self.drawer.add(trimButton)
		trimButton.connect("clicked", self.TrimToSelection)
		
		delFPButton = gtk.Button("Delete Fade Points")
		self.drawer.add(delFPButton)
		delFPButton.connect("clicked", self.DeleteSelectedFadePoints)
		self.selectiontip.set_tip(delFPButton,_("Delete Fade Points"),None)
		
		snapFPButton = gtk.Button("Snap To Fade Points")
		self.drawer.add(snapFPButton)
		snapFPButton.connect("clicked", self.SnapSelectionToFadePoints)
		self.selectiontip.set_tip(snapFPButton,_("Snap To Fade Points"),None)
		
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
		if self.event.selection != [0,0]:
			x1,x2 = self.GetSelectionAsPixels()
			if x2 < x1:
				x2,x1 = x1,x2
			context.rectangle(x1, 0, x2 - x1, event.area.height)
			context.set_source_rgba(*self._SELECTION_RGBA)
			context.fill()
			
			#subtract fade marker height so that it is not drawn partially offscreen
			padded_height = self.allocation.height - self._PIXY_FADEMARKER_HEIGHT
			
			# and overlay the fademarkers
			context.set_source_rgba(*self._FADEMARKERS_RGBA)
			
			pixxFM_left = x1 + 1
			#if there is enough room on the left of the selection,
			#place the fademarker outside the selection bounds.
			if x1 + 1 >= self._PIXX_FADEMARKER_WIDTH:
				pixxFM_left -= self._PIXX_FADEMARKER_WIDTH
			pixyFM_left = int(padded_height * (100-self.fadeMarkers[0]) / 100.0)
			context.rectangle(pixxFM_left, pixyFM_left,
			                  self._PIXX_FADEMARKER_WIDTH , self._PIXY_FADEMARKER_HEIGHT)
			
			pixxFM_right = x2
			#if there is enough room on the right of the selection,
			#place the fademarker outside the selection bounds.
			if x2 + self._PIXX_FADEMARKER_WIDTH > event.area.width:
				pixxFM_right -= self._PIXX_FADEMARKER_WIDTH
			pixyFM_right = int(padded_height * (100-self.fadeMarkers[1]) / 100.0)
			context.rectangle(pixxFM_right, pixyFM_right,
			                  self._PIXX_FADEMARKER_WIDTH, self._PIXY_FADEMARKER_HEIGHT)
			
			context.fill()
			
			context.set_source_rgba(1,1,1,1)
			context.move_to(pixxFM_left + 1, pixyFM_left + self._PIXY_FADEMARKER_HEIGHT - 1)
			context.show_text("%s%%" % int(self.fadeMarkers[0]))
			context.move_to(pixxFM_right + 1, pixyFM_right + self._PIXY_FADEMARKER_HEIGHT - 1)
			context.show_text("%s%%"% int(self.fadeMarkers[1]))
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
			context.show_text(_("Loading (%d%%)...") % displayLength)
			context.stroke()
			# And exit here
			return
		
		if len(self.event.levels) == 0:
			Globals.debug("Trying to draw an event with no level data!")
			return
		
		scale = (self.event.duration * self.project.viewScale) / float(len(self.event.levels))

		# Draw white background
		context.rectangle(0, 0, rect.width, rect.height)
		context.set_source_rgb(*self._BACKGROUND_RGB)
		context.fill()
		
		# Draw volume curve
		x_pos = int(rect.x/scale)
		x = 0
		context.move_to(0,rect.height)
				
		# get levels list
		fadedLevels = self.event.GetFadeLevels()
		
		for peak in fadedLevels[x_pos:]:
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
		
		if self.event.audioFadePoints:
			pixelPoints = []
			# draw the fade line
			context.set_source_rgb(*self._FADELINE_RGB)
			
			firstPoint = self.event.audioFadePoints[0]
			pixx = self.PixXFromSec(firstPoint[0]) - rect.x
			pixy = self.PixYFromVol(firstPoint[1])
			context.move_to(pixx, pixy)
			for sec, vol in self.event.audioFadePoints[1:]:
				pixx = self.PixXFromSec(sec) - rect.x
				pixy = self.PixYFromVol(vol)
				pixelPoints.append((pixx, pixy))
				context.line_to(pixx,pixy)		
			context.stroke()
			
			#draw the fade points
			for pixx, pixy in pixelPoints:
				context.arc(pixx, pixy, 3.5, 0, 7)
				context.fill()
		
		
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
			self.messageID = self.mainview.SetStatusBar(_("To <b>Split, Double-Click</b> the wave - To <b>Select, Shift-Click</b> and drag the mouse"))
		
		if self.isDraggingFade:
			#subtract half the fademarker height so it doesnt go half off the screen
			cur_pos = (mouse.y - (self._PIXY_FADEMARKER_HEIGHT / 2))
			height = self.allocation.height - self._PIXY_FADEMARKER_HEIGHT
			percent = cur_pos / float(height)
			#set percent between 0 and 1
			percent = min(1, max(0, percent))
			
			self.fadeMarkers[self.fadeBeingDragged] = 100 - int(percent * 100)
			self.queue_draw()
			
			if not self.volmessageID:
				self.volmessageID = self.mainview.SetStatusBar(_("<b>NOTE</b>: The volume sliders in this pre-release version of Jokosher do not affect the audio."))
			
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
			x2 = max(0,min(self.allocation.width,mouse.x))
			self.event.selection[1] = self.SecFromPixX(x2)
			self.UpdateFadeMarkers()
			
			selection_direction = "ltor"
			selection = self.event.selection
			if selection[0] > selection[1]:
				selection_direction = "rtol"
				self.fadeMarkers.reverse()
			
			if self.drawer.parent != self.lane.fixed:
				#the drawer is not in the lane, we must add it
				self.lane.fixed.put(self.drawer,1,75)
				#update the lane so the drawer is shown
				self.lane.Update()
			
			#set the drawer align position
			self.drawerAlignToLeft = (selection_direction == "rtol")
			#move the drawer to its proper position
			self.UpdateDrawerPosition(selection_direction == "rtol")
			
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
			self.project.SelectInstrument(None)
		self.event.SetSelected(True)
		
		# RMB: context menu
		if mouse.button == 3:
			self.ContextMenu(mouse)
		elif mouse.button == 1:
			if 'GDK_SHIFT_MASK' in mouse.state.value_names:
				# LMB+shift: remove any existing selection in this event, begin 
				#   selecting part of this event
				self.isSelecting = True
				self.event.selection[0] = self.SecFromPixX(mouse.x)
				self.fadeMarkers = [100,100]
				if not self.selmessageID: 
					self.selmessageID = self.mainview.SetStatusBar(_("<b>Click</b> the buttons below the selection to do something to that portion of audio."))
			else:
				if self.fadeMarkersContext and self.fadeMarkersContext.in_fill(mouse.x, mouse.y):
					# LMB over a fadeMarker: drag that marker
					self.isDraggingFade = True
					if mouse.x > self.PixXFromSec(self.event.selection[1]) - self._PIXX_FADEMARKER_WIDTH - 1:
						self.fadeBeingDragged = 1
						return True
					else:
						self.fadeBeingDragged = 0
						return True
				if mouse.type == gtk.gdk._2BUTTON_PRESS:
					# LMB double-click: split here
					self.mouseAnchor[0] = mouse.x
					if self.event.isLoading == False:
						self.OnSplit(None)
					return True
				
				# remove any existing selection in this event
				self.event.selection = [0,0]
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
		items = [	(_("Split"), self.OnSplit, True),
					("---", None, None),
					(_("Cut"), self.OnCut, True),
					(_("Copy"), self.OnCopy, True),
					(_("Delete"), self.OnDelete, False)
				] 

		for i, cb, sometimes in items: 
			if i == "---":
				a = gtk.SeparatorMenuItem()
			else:
				a = gtk.MenuItem(i)
			
			if self.event.isLoading and sometimes:
				a.set_sensitive(False)
			else:
				a.set_sensitive(True)
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
				self.SetAudioFadePointsFromCurrentSelection()
			elif self.isSelecting:
				self.isSelecting = False
				selection_direction = "ltor"
				selection = self.event.selection
				if selection[0] > selection[1]:
					self.event.selection = [selection[1], selection[0]]
					selection_direction = "rtol"
					
				
				if self.drawer.parent != self.lane.fixed:
					#the drawer is not in the lane, we must add it
					self.lane.fixed.put(self.drawer,1,75)
					
				#set the drawer align position
				self.drawerAlignToLeft = (selection_direction == "rtol")
				#move the drawer to its proper position
				self.UpdateDrawerPosition()
				#update the lane so the drawer is shown
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
		
		if self.event.isLoading == True:
			return
		
		# Hide the drawer
		self.lane.fixed.remove(self.drawer)

		self.event.Trim(self.event.selection[0], self.event.selection[1])
		self.event.selection = [0,0]

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
			
			if rect.height < 30:
				requisition.height = 30
			else:
				requisition.height = rect.height

	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None):
		if change == self.event.WAVEFORM:
			self.redrawWaveform = True
			self.UpdateFadeMarkers()
		
		elif change == self.event.MOVE:
			self.lane.Update(self)
		
		elif change == self.event.LENGTH:
			self.redrawWaveform = True
			self.queue_resize()
		
		elif change == self.event.CORRUPT and self.small==False:
			message=_("%s\n\nFile is corrupt, not an audio file, or the associated plugin is not installed"%self.event.filelabel)

			dlg = gtk.MessageDialog(None,
				gtk.DIALOG_MODAL,
				gtk.MESSAGE_ERROR,
				gtk.BUTTONS_CLOSE,
				message)
			dlg.connect('response', lambda dlg, response: dlg.destroy())
			dlg.show()
			self.OnDelete()
	
		elif type(obj) == Project.Project and self.currentScale != self.project.viewScale:
			self.redrawWaveform = True
			self.queue_resize()
			self.last_num_levels = len(self.event.levels)
			self.currentScale = self.project.viewScale
		
		self.queue_draw()

	#_____________________________________________________________________

	def PixXFromSec(self, sec):
		"""Converts seconds to an X pixel position in the waveform"""
		return round(float(sec + self.event.start) * self.project.viewScale)
	
	#_____________________________________________________________________
	
	def SecFromPixX(self,pixx):
		"""Converts an X pixel position in the waveform into seconds"""
		return float(pixx) / self.project.viewScale - self.event.start
	
	#_____________________________________________________________________
	
	def PixYFromVol(self, vol):
		"""Converts volume (0.0-1.0) to a Y pixel position in the waveform"""
		return round((1.0 - vol) * self.allocation.height)
	
	#_____________________________________________________________________
	
	def VolFromPixY(self,pixy):
		"""Converts a Y pixel position in the waveform into a volume (0.0-1.0)"""
		return 1.0 - (float(pixy) / self.allocation.height)

	#_____________________________________________________________________
	
	def SetAudioFadePointsFromCurrentSelection(self):				
		volLeft = self.fadeMarkers[0] / 100.0
		volRight = self.fadeMarkers[1] / 100.0
		
		selection = self.event.selection
		self.event.AddAudioFadePoints(selection[0], selection[1], volLeft, volRight)
	
	#_____________________________________________________________________
	
	def GetSelectionAsPixels(self):
		"""
		   Returns the event selection as a list of two points
		   measured in pixels instead of seconds like event.selection.
		"""
		x1 = self.PixXFromSec(self.event.selection[0])
		x2 = self.PixXFromSec(self.event.selection[1])
		return [x1, x2]
	
	#_____________________________________________________________________
	
	def UpdateDrawerPosition(self, reverseSelectionPoints=False):
		if self.drawer.parent != self.lane.fixed:
			#drawer is not in lane
			return
		
		if reverseSelectionPoints:
			selection = [self.event.selection[1], self.event.selection[0]]
		else:
			selection = self.event.selection[:]

		x0 = self.project.viewScale * self.event.selection[0]	
		x1 = (self.project.viewScale * self.event.selection[1]) - x0

		if x0 < self.drawer.size_request()[0] and x1< self.drawer.size_request()[0]:
			self.drawerAlignToLeft = True

		eventx = int((self.event.start - self.project.viewStart) * self.project.viewScale)
		if self.drawerAlignToLeft:
			x = int(self.PixXFromSec(selection[0]))
		else:
			width = self.drawer.allocation.width
			if width == 1:
				width = 40 # fudge it because it has no width initially
			x = int(self.PixXFromSec(selection[1]) - width)
		
		self.lane.fixed.move(self.drawer,eventx + x,75)
		#don't update the lane because it calls us and that might cause infinite loop

	#_____________________________________________________________________
	
	def DeleteSelectedFadePoints(self, event):
		if self.event.isLoading == True:
			return
		self.event.DeleteSelectedFadePoints()
		
	#_____________________________________________________________________
	
	def SnapSelectionToFadePoints(self, event):
		if len(self.event.audioFadePoints) < 2:
			#not enough levels
			return
			
		points = [x[0] for x in self.event.audioFadePoints]
		left, right = self.event.selection
		
		leftOfLeft = max([x for x in points if x < left])
		rightOfLeft = min([x for x in points if x >= left])
		
		leftOfRight = max([x for x in points if x < right])
		rightOfRight = min([x for x in points if x >= right])
		
		if abs(leftOfLeft - left) < abs(rightOfLeft - left):
			leftChooses = leftOfLeft
		else:
			leftChooses = rightOfLeft

		if abs(leftOfRight - right) > abs(rightOfRight - right):
			rightChooses = rightOfRight
		else:
			rightChooses = leftOfRight

		if leftChooses == rightChooses:
			#the both selected the same point
			if abs(leftChooses - left) > abs(rightChooses - right):
				#if right is closer to the point
				leftChooses = leftOfLeft
			else:
				rightChooses = rightOfRight
		
		self.event.selection = [leftChooses, rightChooses]
		self.UpdateFadeMarkers()
		self.queue_draw()
		
	#_____________________________________________________________________
	
	def UpdateFadeMarkers(self):
		self.fadeMarkers = [self.event.GetFadeLevelAtPoint(x) * 100 for x in self.event.selection]
	
	#_____________________________________________________________________

#=========================================================================

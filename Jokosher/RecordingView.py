#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	RecordingView.py
#	
#	A sub-class of gtk.Frame containing the visual layout of instrument
#	tracks, timeline, and horizontal scrollbars.
#
#-------------------------------------------------------------------------------

import gtk
import InstrumentViewer
import TimeLineBar
import Globals
from gettext import gettext as _
import urllib

#=========================================================================

class RecordingView(gtk.Frame):
	"""
	This class encapsulates a visual layout of a project comprising
	instrument tracks, timeline, and horizontal scrollbars.
	Despite its name, it also appears under the mixing view contained
	in a CompactMixView object, where it represents the same
	information with shorter instrument tracks.
	"""
	
	""" GTK widget name """
	__gtype_name__ = 'RecordingView'
	
	""" Width, in pixel, for the instrument headers """
	INSTRUMENT_HEADER_WIDTH = 150
	""" How far in you are allowed to zoom. """
	ZOOM_MAX_SCALE = 100.0
	""" How for out you are allowed to zoom. 
	This is just a default value and will change 
	depending on the project length."""
	ZOOM_MIN_SCALE = 5.0
	
	""" Number only to be used inside Jokosher """
	URI_DRAG_TYPE = 86
	
	""" Custom numbers for use while dragging text in Jokosher """
	DRAG_TARGETS = [ ( "text/uri-list", 	# Accept uri-lists
						0,					# From everywhere
						URI_DRAG_TYPE ),		# Use the custom number
						("text/plain", 0, URI_DRAG_TYPE) # so drags from Firefox work
						]

	#_____________________________________________________________________

	def __init__(self, project, mainview, mixView=None, small=False):
		"""
		Creates a new instance of RecordingView.
		
		Parameters:
			project -- the currently active Project.
			mainview -- the main Jokosher window (MainApp).
			mixView -- the CompactMixView object that holds this instance of
						RecordingView, if the mixing view is the currently 
						active one.
						If the recording view is the active one, then this
						should be set to None.
			small -- set to True if we want small edit views (i.e. for the mixing view).
		"""
		gtk.Frame.__init__(self)

		self.project = project
		self.mainview = mainview
		self.mixView = mixView
		self.small = small
		self.timelinebar = TimeLineBar.TimeLineBar(self.project, self, mainview)
		
		## create darker workspace box
		self.eventBox = gtk.EventBox()
		self.eventBox.connect("button-press-event", self.OnEmptySpaceDoubleClicked)
		
		self.vbox = gtk.VBox()
		self.add(self.vbox)
		self.vbox.pack_start(self.timelinebar, False, False)
		self.instrumentWindow = gtk.ScrolledWindow()
		self.instrumentBox = gtk.VBox()
		
		## pack the instrument box inside the eventbox as you cant modify the color of a gtk.Box
		self.eventBox.add(self.instrumentBox)
		self.instrumentWindow.add_with_viewport(self.eventBox)
		self.instrumentWindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		self.vbox.pack_start(self.instrumentWindow, True, True)
		self.instrumentWindow.child.set_shadow_type(gtk.SHADOW_NONE)
		self.views = []	
		
		self.hb = gtk.HBox()
		self.hb.set_spacing(6)
		self.vbox.pack_end(self.hb, False, False)
		self.al = gtk.Alignment(0, 0, 1, 1)
		self.scrollRange = gtk.Adjustment()
		sb = gtk.HScrollbar(self.scrollRange)
		self.al.add(sb)
		self.al.set_padding(0, 0, 0, 0)
		self.hb.pack_start(self.al)
		
		self.lastzoom = 0
		
		#recording view contains zoom buttons
		if not self.mixView:
			self.zoomSlider = gtk.HScale()
			self.zoomSlider.set_size_request(70, -1)
			
			self.zoomSlider.set_range(self.ZOOM_MIN_SCALE, self.ZOOM_MAX_SCALE)
			self.zoomSlider.set_increments(0.2, 0.2)
			self.zoomSlider.set_draw_value(False)
			self.zoomSlider.set_value(self.project.viewScale)
			self.zoomtip = gtk.Tooltips()
			self.zoomtip.set_tip(self.zoomSlider, _("Zoom the timeline"),None)
			
			self.zoomSlider.connect("value-changed", self.OnZoom)
			
			inbutton = gtk.Button()
			inimg = gtk.image_new_from_stock(gtk.STOCK_ZOOM_IN, gtk.ICON_SIZE_BUTTON)
			inbutton.set_image(inimg)
			inbutton.set_relief(gtk.RELIEF_NONE)
			inbutton.connect("clicked", self.OnZoomIn)
			
			outbutton = gtk.Button()
			outimg = gtk.image_new_from_stock(gtk.STOCK_ZOOM_OUT, gtk.ICON_SIZE_BUTTON)
			outbutton.set_image(outimg)
			outbutton.set_relief(gtk.RELIEF_NONE)
			outbutton.connect("clicked", self.OnZoomOut)

			self.hb.pack_start( outbutton, False, False)
			self.hb.pack_start( self.zoomSlider, False, False)
			self.hb.pack_start( inbutton, False, False)
		
		self.extraScrollTime = 25
		self.centreViewOnPosition = False
		self.scrollRange.lower = 0
		self.scrollRange.upper = 100
		self.scrollRange.value = 0
		self.scrollRange.step_increment = 1
		
		sb.connect("value-changed", self.OnScroll)
		self.connect("expose-event", self.OnExpose)
		self.connect("button_release_event", self.OnExpose)
		self.connect("button_press_event", self.OnMouseDown)
		self.connect("size-allocate", self.OnAllocate)
		
		self.vbox.drag_dest_set(	gtk.DEST_DEFAULT_DROP,
									self.DRAG_TARGETS, 
									gtk.gdk.ACTION_COPY)
		self.vbox.connect("drag_data_received", self.OnDragDataReceived)
		self.vbox.connect("drag_motion", self.OnDragMotion)
		
		self.Update()
	#_____________________________________________________________________

	def OnExpose(self, widget, event):
		"""
		Sets scrollbar properties (i.e. size, scroll increments, etc),
		once space for the object has been allocated.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		st = self.rc_get_style().bg[gtk.STATE_NORMAL]
		
		## Set the new color components
		st.red -= 3000
		st.green -= 3000
		st.blue -= 3000
		
		cmap = self.get_colormap()
		
		## allocate new colors
		col = cmap.alloc_color(st.red, st.green, st.blue)
		stcp = self.get_style().copy()
		stcp.bg[gtk.STATE_NORMAL] = col
		
		## use the new colormap
		self.eventBox.set_style(stcp)
		
		# calculate scrollable width - allow 4 pixels for borders
		self.scrollRange.page_size = (self.allocation.width - Globals.INSTRUMENT_HEADER_WIDTH - 4) / self.project.viewScale
		self.scrollRange.page_increment = self.scrollRange.page_size
		# add EXTRA_SCROLL_TIME extra seconds
		length = self.project.GetProjectLength() + self.extraScrollTime
		self.scrollRange.upper = length
		
		if self.centreViewOnPosition:  
			self.centreViewOnPosition = False  
			#set the view to be centred over the playhead  
			start = self.project.transport.GetPosition() - (self.scrollRange.page_size / 2)
			self.SetViewPosition(start)
		# Need to adjust project view start if we are zooming out
		# and the end of the project is now before the end of the page.
		# Project end will be at right edge unless the start is also on 
		# screen, in which case the start will be at the left.
		elif self.project.viewStart + self.scrollRange.page_size > length:
			self.SetViewPosition(length - self.scrollRange.page_size)
		
		if not self.mixView:
			#check the min zoom value (based on project length)
			pixelSize = self.allocation.width - Globals.INSTRUMENT_HEADER_WIDTH - 4	# four pixels to account for borders
			minScale = pixelSize / length
			self.zoomSlider.set_range(minScale, self.ZOOM_MAX_SCALE)
			if self.zoomSlider.get_value() < minScale:
				self.zoomSlider.set_value(minScale)
		
	#_____________________________________________________________________

	def OnAllocate(self, widget, allocation):
		"""
		Callback for "size-allocate" signal.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			allocation -- new allocation value to be set.
		"""
		self.allocation = allocation
		
	#_____________________________________________________________________
	

	def Update(self):
		"""
		Updates the GUI to reflect changes on the instruments, timeline and
		scrollbars.
		Called either directly from OnStateChanged(), or via the owning
		CompactMixView.update()(depending on which view we are in) when
		there is a change of state in an instrument being listened to.
		
		Considerations:
			InstrumentViews MUST have the order that the instruments have in
			Project.instruments, to keep the drag and drop of InstrumentViews
			consistent.
		"""
		children = self.instrumentBox.get_children()
		orderCounter = 0
		for instr in self.project.instruments:
			#Find the InstrumentView that matches instr:
			iv = None
			for ident, instrV in self.views:
				if instrV.instrument is instr:
					iv = instrV
					break
			#If there is no InstrumentView for instr, create one:
			if not iv:
				iv = InstrumentViewer.InstrumentViewer(self.project, instr, self, self.mainview, self.small)
				# if this is mix view then add parent (CompactMixView) as listener
				# otherwise add self
				if self.mixView:
					instr.AddListener(self.mixView)
				else:
					instr.AddListener(self)
				#Add it to the views
				self.views.append((instr.id, iv))
				iv.headerAlign.connect("size-allocate", self.UpdateSize)
			
			if iv not in children:
				#Add the InstrumentView to the VBox
				self.instrumentBox.pack_start(iv, False, False)
			else:
				#If the InstrumentView has already been added, just move it
				self.instrumentBox.reorder_child(iv, orderCounter)
				
			#Make sure the InstrumentView is visible:
			iv.show()
			
			orderCounter += 1
		
		removeList = []
		#self.views is up to date now
		for ident, iv in self.views:
			#check if instrument has been deleted
			if not iv.instrument in self.project.instruments:
				if iv in children:
					self.instrumentBox.remove(iv)
				iv.Destroy()
				removeList.append((ident, iv))
			else:
				iv.Update() #Update non-deleted instruments
		
		#remove all the unused ones so the garbage collector can clean then up
		for tuple_ in removeList:
			self.views.remove(tuple_)
		del removeList
		
		if len(self.views) > 0:
			self.UpdateSize(None, self.views[0][1].headerAlign.get_allocation())
		else:
			self.UpdateSize(None, None)
		self.show_all()
	
	#_____________________________________________________________________
		
	def UpdateSize(self, widget=None, size=None):
		"""
		Called during update() to re-align the timeline and scrollbars
		with the start of the event lane since the instrument width may
		have been altered.
		"""
		#find the width of the instrument headers (they should all be the same size)
		if size:
			tempWidth = size.width
		else:
			tempWidth = self.INSTRUMENT_HEADER_WIDTH
		
		#set it to the globals class
		Globals.INSTRUMENT_HEADER_WIDTH = tempWidth
		
		#align timeline and scrollbar
		self.timelinebar.Update()
		self.al.set_padding(0, 0, tempWidth, 0)
	
	#_____________________________________________________________________
	
	def OnScroll(self, widget):
		"""
		Callback for "value-changed" signal from scrollbar.
		Updates the Project playhead position.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		pos = widget.get_value()
		self.project.SetViewStart(pos)

	#_____________________________________________________________________

	def OnZoom(self, widget):
		"""
		Updates the viewing scale for the Project when the user
		zooms in or out.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		# The left and right sides of the viewable area
		rightPos = self.project.viewStart + self.scrollRange.page_size
		leftPos = self.project.viewStart
		currentPos = self.project.transport.GetPosition()
		# Check if the playhead is currently viewable (don't force it in view if it isn't already in view)
		if leftPos < currentPos < rightPos:
			self.centreViewOnPosition = True
		
		#now do the zoom
		self.project.SetViewScale(widget.get_value())

	#_____________________________________________________________________
	
	def OnZoomOut(self, widget):
		"""
		Calls OnZoom when the user zooms out.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		tmp = self.project.viewScale * 4. / 5.
		#setting the value will trigger the gtk event and call OnZoom for us.
		self.zoomSlider.set_value(tmp)
		
	#_____________________________________________________________________
		
	def OnZoom100(self, widget):
		"""
		This method is not currently used (it was used when the zoom buttons existed).
		It's left here for future use.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.project.SetViewScale(25.0)
		
	#_____________________________________________________________________
		
	def OnZoomIn(self, widget):
		"""
		Calls OnZoom when the user zooms in.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		tmp = self.project.viewScale * 1.25
		#setting the value will trigger the gtk event and call OnZoom for us.
		self.zoomSlider.set_value(tmp)
		
	#_____________________________________________________________________

	def SetViewPosition(self, position):
		"""
		Moves the view so that the given position is the leftmost side
		of the viewable area for scrolling, etc.
		
		Parameters:
			position -- the new position to set.
		"""
		length = self.project.GetProjectLength() + self.extraScrollTime 
		#check if its over the project length
		start = min(length - self.scrollRange.page_size, position)
		#check if its under zero (do this after checking the project length, because if the project length is 0 it will go under)
		start = max(0, start)
		self.scrollRange.value = start
		self.project.SetViewStart(start)
	
	#_____________________________________________________________________
	
	def OnMouseDown(self, widget, mouse):
		"""
		Callback for "button_press_event" (not catered for, by any
		button presses or other mouse handlers).
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- reserved for GTK callbacks, don't use it explicitly.
		"""
		# If we're here then we're out of bounds of anything else
		# So we should clear any selected events
		self.project.ClearEventSelections()
		self.project.SelectInstrument(None)
		self.Update()
		
	#_____________________________________________________________________
	
	def OnEmptySpaceDoubleClicked(self, widget, mouse):
		"""
		Callback for "button_press_event" (not catered for, by any
		button presses or other mouse handlers).
		Shows the add instrument dialog when the empty space is double clicked.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if mouse.type == gtk.gdk._2BUTTON_PRESS:
			self.mainview.OnShowAddInstrumentDialog()
			
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None, *extra):
		"""
		Called when a change of state is signalled by any of the
		objects this view is 'listening' to.
		
		Parameters:
			obj -- object changing state. *CHECK*
			change -- the change which has occured.
			extra -- extra parameters passed by the caller.
		"""
		#don't update on volume change because it happens very often
		if change != "volume":
			self.Update()
		
	#_____________________________________________________________________
	
	def OnDragDataReceived(self, widget, context, x, y, selection, targetType, time):
		"""
		Called when the user releases MOUSE1, finishing a drag and drop
		procedure.
		Adds an instrument and event for each "file://"-uri in the uri-list to the Instrument, 
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
		# Splitlines to separate the uri's, unquote to decode the uri-encoding ('%20' -> ' ')
		uris = [urllib.unquote(uri) for uri in selection.data.splitlines()]
		self.project.AddInstrumentAndEvents(uris, True) # True: copy
		
		context.finish(True, False, time)
		self.Update()
		return True
	
	#_____________________________________________________________________
	
	def OnDragMotion(self, widget, context, x, y, time):
		"""
		Called each time the user moves the mouse onto this widget while dragging.
		
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
		return True
	
	#_____________________________________________________________________
#=========================================================================

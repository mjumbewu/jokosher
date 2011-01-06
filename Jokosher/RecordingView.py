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
import ui.MessageArea as MessageArea
from gettext import gettext as _
import urllib

#=========================================================================

class RecordingView(gtk.Frame):
	"""
	This class encapsulates a visual layout of a project comprising
	instrument tracks, timeline, and horizontal scrollbars.
	"""
	
	""" GTK widget name """
	__gtype_name__ = 'RecordingView'
	
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
	
	"""The number of seconds shown after the end of the last event"""
	EXTRA_SCROLL_TIME = 25

	#_____________________________________________________________________

	def __init__(self, project, mainview, small=False):
		"""
		Creates a new instance of RecordingView.
		
		Parameters:
			project -- the currently active Project.
			mainview -- the main Jokosher window (MainApp).
			small -- set to True if we want small edit views (i.e. for the mixing view).
		"""
		gtk.Frame.__init__(self)

		self.project = project
		self.mainview = mainview
		self.small = small
		self.timelinebar = TimeLineBar.TimeLineBar(self.project, mainview)
		
		self.errorMessageArea = None
		self.restoreMessageArea = None
		self.unsetNameMessageArea = None
		
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
		
		self.header_size_group = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
		self.header_size_group.add_widget(self.timelinebar.GetHeaderWidget())
		
		self.hb = gtk.HBox()
		self.hb.set_spacing(6)
		self.hb.set_border_width(6)
		self.vbox.pack_end(self.hb, False, False)
		self.vbox.pack_end(gtk.HSeparator(), False, False)
		
		self.zoom_hb = gtk.HBox()
		self.zoom_hb.set_spacing(6)
		self.zoom_hb.set_border_width(0)
		self.header_size_group.add_widget(self.zoom_hb)
		
		self.scrollRange = gtk.Adjustment()
		self.scrollBar = gtk.HScrollbar(self.scrollRange)
		
		self.hb.pack_start(self.zoom_hb, False, False)
		self.hb.pack_start(self.scrollBar, True, True)
		
		self.lastzoom = 0
		
		self.zoomSlider = gtk.HScale()
		self.zoomSlider.set_size_request(70, -1)
		
		self.zoomSlider.set_range(self.ZOOM_MIN_SCALE, self.ZOOM_MAX_SCALE)
		self.zoomSlider.set_increments(0.2, 0.2)
		self.zoomSlider.set_draw_value(False)
		self.zoomSlider.set_value(self.project.viewScale)
		self.zoomSlider.set_tooltip_text(_("Zoom the timeline - Right-Click to reset to the default level"))
		
		self.zoomSlider.connect("value-changed", self.OnZoom)
		self.zoomSlider.connect("button-press-event", self.OnZoomReset)
		
		self.inbutton = gtk.Button()
		inimg = gtk.image_new_from_stock(gtk.STOCK_ZOOM_IN, gtk.ICON_SIZE_BUTTON)
		self.inbutton.set_image(inimg)
		self.inbutton.set_relief(gtk.RELIEF_NONE)
		self.inbutton.set_tooltip_text(_("Zoom in timeline"))
		self.inbutton.connect("clicked", self.OnZoomIn)
		
		self.outbutton = gtk.Button()
		outimg = gtk.image_new_from_stock(gtk.STOCK_ZOOM_OUT, gtk.ICON_SIZE_BUTTON)
		self.outbutton.set_image(outimg)
		self.outbutton.set_relief(gtk.RELIEF_NONE)
		self.outbutton.set_tooltip_text(_("Zoom out timeline"))
		self.outbutton.connect("clicked", self.OnZoomOut)

		self.zoom_hb.pack_start( self.outbutton, False, False)
		self.zoom_hb.pack_start( self.zoomSlider, False, False)
		self.zoom_hb.pack_start( self.inbutton, False, False)
		
		self.centreViewOnPosition = False
		self.scrollRange.lower = 0
		self.scrollRange.upper = 100
		self.scrollRange.value = 0
		self.scrollRange.step_increment = 1
		
		self.scrollBar.connect("value-changed", self.OnScroll)
		self.connect("expose-event", self.OnExpose)
		self.connect("button_release_event", self.OnExpose)
		self.connect("button_press_event", self.OnMouseDown)
		
		#connect to the project signals
		self.project.connect("gst-bus-error", self.OnProjectGstError)
		self.project.connect("incremental-save", self.OnProjectIncSave)
		self.project.connect("instrument::added", self.OnInstrumentAdded)
		self.project.connect("instrument::reordered", self.OnInstrumentReordered)
		self.project.connect("instrument::removed", self.OnInstrumentRemoved)
		self.project.connect("view-start", self.OnViewStartChanged)
		
		self.vbox.drag_dest_set(	gtk.DEST_DEFAULT_DROP,
									self.DRAG_TARGETS, 
									gtk.gdk.ACTION_COPY)
		self.vbox.connect("drag_data_received", self.OnDragDataReceived)
		self.vbox.connect("drag_motion", self.OnDragMotion)
		
		#add the instruments that were loaded from the project file already
		for instr in self.project.instruments:
			self.OnInstrumentAdded(project, instr)
			
		self.show_all()
		self.show_all()
		if self.small:
			self.inbutton.hide()
			self.outbutton.hide()
			self.zoomSlider.hide()
		
		if self.project.CanDoIncrementalRestore():
			message = _("Would you like to restore the current project?")
			details = _("A crash was detected and changes to your project were not saved.\nIf you would like, you can attempt to recover these lost changes.")
			
			msg_area = MessageArea.MessageArea()
			msg_area.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
			msg_area.add_stock_button_with_text(_("_Restore Project"), gtk.STOCK_APPLY, gtk.RESPONSE_OK)
			msg_area.set_text_and_icon(gtk.STOCK_DIALOG_QUESTION, message, details)
			
			msg_area.connect("response", self.OnRestoreMessageAreaResponse, msg_area)
			msg_area.connect("close", self.OnRestoreMessageAreaClose, msg_area)
			
			self.vbox.pack_end(msg_area, False, False)
			msg_area.show()
			self.restoreMessageArea = msg_area
		elif self.project.name_is_unset:
			self.ShowUnsetProjectNameMessage()
		
	#_____________________________________________________________________
	
	def OnExpose(self, widget=None, event=None):
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
		
		# calculate scrollable width (scroll bar should always be same width as viewable area)
		self.scrollRange.page_size = (self.scrollBar.allocation.width) / self.project.viewScale
		self.scrollRange.page_increment = self.scrollRange.page_size
		# add EXTRA_SCROLL_TIME extra seconds
		length = self.project.GetProjectLength() + self.EXTRA_SCROLL_TIME
		self.scrollRange.upper = length
		
		if self.centreViewOnPosition:  
			self.centreViewOnPosition = False  
			#set the view to be centred over the playhead  
			start = self.project.transport.GetPosition() - (self.scrollRange.page_size / 2)
			self.project.SetViewStart(start)
		# Need to adjust project view start if we are zooming out
		# and the end of the project is now before the end of the page.
		# Project end will be at right edge unless the start is also on 
		# screen, in which case the start will be at the left.
		elif self.project.viewStart + self.scrollRange.page_size > length:
			self.project.SetViewStart(length - self.scrollRange.page_size)
		
		#check the min zoom value (based on project length)
		# (scroll bar should always be same width as viewable area)
		pixelSize = self.scrollBar.allocation.width 
		minScale = pixelSize / length
		self.zoomSlider.set_range(minScale, self.ZOOM_MAX_SCALE)
		if self.zoomSlider.get_value() < minScale:
			self.zoomSlider.set_value(minScale)
		
	#_____________________________________________________________________
	
	def OnInstrumentAdded(self, project, instrument):
		"""
		Callback for when an instrument is added to the project.
		
		Parameters:
			project -- The project that the instrument was added to.
			instrument -- The instrument that was added.
		"""
		instrViewer = InstrumentViewer.InstrumentViewer(project, instrument, self, self.mainview, self.small)
		
		#Add it to the views
		self.views.append((instrument.id, instrViewer))
		self.header_size_group.add_widget(instrViewer.GetHeaderWidget())
		
		self.instrumentBox.pack_start(instrViewer, False, False)
		instrViewer.show()
	
	#_____________________________________________________________________
	
	def OnInstrumentRemoved(self, project, instrument):
		"""
		Callback for when an instrument is removed from the project.
		
		Parameters:
			project -- The project that the instrument was removed from.
			instrument -- The instrument that was removed.
		"""
		for ID, instrViewer in self.views:
			if ID == instrument.id:
				if instrViewer.parent:
					self.instrumentBox.remove(instrViewer)
				instrViewer.Destroy()
				self.views.remove((ID, instrViewer))
				break
	
	#_____________________________________________________________________
	
	def OnInstrumentReordered(self, project, instrument):
		"""
		Callback for when an instrument's position in the project has changed.
		
		Parameters:
			project -- The project that the instrument was changed on.
			instrument -- The instrument that was reordered.
		"""
		for ID, instrViewer in self.views:
			if ID == instrument.id:
				if instrViewer.parent:
					pos = self.project.instruments.index(instrument)
					self.instrumentBox.reorder_child(instrViewer, pos)
					instrViewer.show_all()
				break
		
	
	#_____________________________________________________________________
	
	def OnProjectGstError(self, project, error, debug):
		"""
		Callback for when the project sends a gstreamer error message
		from the pipeline.
		
		Parameters:
			project -- The project instance that send the signal.
			error -- The type of error that occurred as a string.
			debug -- A string with more debug information about the error.
		"""
		if not error:
			error = _("A Gstreamer error has occurred")
		
		if not self.errorMessageArea:
			msg_area = self.CreateDefaultErrorPane(error, debug)
			self.vbox.pack_end(msg_area, False, False)
			msg_area.show()
			self.errorMessageArea = msg_area
	
	#_____________________________________________________________________
	
	def CreateDefaultErrorPane(self, error, details):
		message = _("A GStreamer error has occurred.")
		info = _("If this problem persists consider reporting a bug using the link in the help menu.")
		
		details = "\n".join((error, info))
		
		msg_area = MessageArea.MessageArea()
		msg_area.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
		msg_area.set_text_and_icon(gtk.STOCK_DIALOG_ERROR, message, details)
		
		msg_area.connect("response", self.OnMessageAreaReponse, msg_area)
		msg_area.connect("close", self.OnMessageAreaClose, msg_area)
		
		return msg_area
		
	#_____________________________________________________________________
	
	def OnMessageAreaClose(self, widget, message_area):
		if self.errorMessageArea:
			self.vbox.remove(self.errorMessageArea)
			self.errorMessageArea = None
	
	#_____________________________________________________________________
	
	def OnMessageAreaReponse(self, widget, response_id, message_area):
		if response_id == gtk.RESPONSE_CLOSE:
			self.OnMessageAreaClose(widget, message_area)
	
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
		#setting the value will trigger the "value-changed" signal and call OnZoom for us.
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
		#setting the value will trigger the "value-changed" signal and call OnZoom for us.
		self.zoomSlider.set_value(tmp)

	#_____________________________________________________________________
		
	def OnZoomReset(self, widget, mouse):
		"""
		Calls OnZoom when the user resets the zoom to the default by right-clicking.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if mouse.button == 3:
			tmp = (self.ZOOM_MAX_SCALE - self.ZOOM_MIN_SCALE) / 2
			#setting the value will trigger the "value-changed" signal and call OnZoom for us.
			self.zoomSlider.set_value(tmp)
			return True
		
	#_____________________________________________________________________
	
	def OnViewStartChanged(self, project):
		"""
		Callback for when the project notifies that the
		viewable start position has changed.
		
		Parameters:
			project -- The project instance that send the signal.
		"""
		self.scrollRange.value = project.viewStart
	
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
		if mouse.type == gtk.gdk._2BUTTON_PRESS or mouse.type == gtk.gdk._3BUTTON_PRESS:
			return True
		self.project.ClearEventSelections()
		self.project.SelectInstrument(None)
		
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
	
	def ChangeSize(self, small):
		"""
		Alters the size of the instrument lanes and removes the zoom buttons.
		
		Parameters:
			small -- True if changing to small. Otherwise False.
		"""
		#if the requested size has not changed then quit
		if small == self.small:
			return
		self.small = small
		children = self.instrumentBox.get_children()
		for instrView in children:
			instrView.ChangeSize(small)
		if self.small:
			self.inbutton.hide()
			self.outbutton.hide()
			self.zoomSlider.hide()
		else:
			self.inbutton.show()
			self.outbutton.show()
			self.zoomSlider.show()
			
	#____________________________________________________________________	
	
	def OnRestoreMessageAreaClose(self, widget=None, msg_area=None):
		if self.restoreMessageArea:
			self.vbox.remove(self.restoreMessageArea)
			self.restoreMessageArea = None
			
			if self.unsetNameMessageArea is None:
				self.ShowUnsetProjectNameMessage()
	
	#____________________________________________________________________
	
	def OnRestoreMessageAreaResponse(self, widget, response_id, msg_area):
		if response_id == gtk.RESPONSE_OK:
			self.project.DoIncrementalRestore()
		
		self.OnRestoreMessageAreaClose()
	
	#____________________________________________________________________
	
	def OnProjectIncSave(self, project):
		if self.restoreMessageArea:
			self.OnRestoreMessageAreaClose()
		elif self.unsetNameMessageArea:
			self.OnUnsetNameMessageAreaClose()
	
	#____________________________________________________________________
	
	def ShowUnsetProjectNameMessage(self):
		if not self.project.name_is_unset:
			return
	
		message = _("This project has no name. Would you like to give it one?")
		details = _("The Properties dialog in the File menu lets you change the name of author of the project.")
		
		msg_area = MessageArea.MessageArea()
		msg_area.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
		msg_area.add_stock_button_with_text(_("_Open Properties"), gtk.STOCK_APPLY, gtk.RESPONSE_OK)
		msg_area.set_text_and_icon(gtk.STOCK_DIALOG_QUESTION, message, details)
		
		msg_area.connect("response", self.OnUnsetNameMessageAreaResponse, msg_area)
		msg_area.connect("close", self.OnUnsetNameMessageAreaClose, msg_area)
		
		self.vbox.pack_end(msg_area, False, False)
		msg_area.show()
		self.unsetNameMessageArea = msg_area
		
	#_____________________________________________________________________
	
	def OnUnsetNameMessageAreaClose(self, widget=None, msg_area=None):
		if self.unsetNameMessageArea:
			self.vbox.remove(self.unsetNameMessageArea)
			self.unsetNameMessageArea = None
	
	#____________________________________________________________________
	
	def OnUnsetNameMessageAreaResponse(self, widget, response_id, msg_area):
		if response_id == gtk.RESPONSE_OK:
			self.mainview.OnProjectProperties()
		
		self.OnUnsetNameMessageAreaClose()
	
	#____________________________________________________________________
#=========================================================================

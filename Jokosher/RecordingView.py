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

#=========================================================================

class RecordingView(gtk.Frame):
	"""
		This class encapsulates a visual layout of a project comprising
		instrument tracks, timeline, and horizontal scrollbars.
		Despite it's name it also appears under the mixing view contained
		in a CompactMixView object, where it represents the same 
		information with shorter instrument tracks.
	"""

	__gtype_name__ = 'RecordingView'
	INSTRUMENT_HEADER_WIDTH = 150
	EXTRA_SCROLL_TIME = 10

	#_____________________________________________________________________

	def __init__(self, project, mainview, mixView=None, small=False):
		"""
			project - the current active project
			mainview - the main Jokosher window
			mixView - the CompactMixView object that holds this if we are in
			          mixing view. If we are in recording view then None
			small - set to True if we want small edit views (i.e. for mix view)
		"""
		gtk.Frame.__init__(self)

		self.project = project
		self.mainview = mainview
		self.mixView = mixView
		self.small = small
		self.timelinebar = TimeLineBar.TimeLineBar(self.project, self, mainview)

		self.vbox = gtk.VBox()
		self.add(self.vbox)
		self.vbox.pack_start(self.timelinebar, False, False)
		self.instrumentWindow = gtk.ScrolledWindow()
		self.instrumentBox = gtk.VBox()
		self.instrumentWindow.add_with_viewport(self.instrumentBox)
		self.instrumentWindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		self.vbox.pack_start(self.instrumentWindow, True, True)
		self.instrumentWindow.child.set_shadow_type(gtk.SHADOW_NONE)
		self.views = []	
		
		self.hb = gtk.HBox()
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
			zoom = gtk.HScale()
			zoom.set_size_request(70, -1)
			zoom.set_range(-5.0, 5.0)
			zoom.set_increments(1, 1)
			zoom.set_draw_value(False)
			zoom.set_value(0)
			
			zoom.connect("value-changed", self.OnZoom)

			inimg = gtk.image_new_from_stock(gtk.STOCK_ZOOM_IN, gtk.ICON_SIZE_BUTTON)
			outimg = gtk.image_new_from_stock(gtk.STOCK_ZOOM_OUT, gtk.ICON_SIZE_BUTTON)

			self.hb.pack_start( outimg, False, False)
			self.hb.pack_start( zoom, False, False)
			self.hb.pack_start( inimg, False, False)
		
		self.scrollRange.lower = 0
		self.scrollRange.upper = 100
		self.scrollRange.value = 0
		self.scrollRange.step_increment = 1
		
		sb.connect("value-changed", self.OnScroll)
		self.connect("expose-event", self.OnExpose)
		self.connect("button_release_event", self.OnExpose)
		self.connect("button_press_event", self.OnMouseDown)
		self.connect("size-allocate", self.OnAllocate)
		
		self.Update()
	#_____________________________________________________________________

	def OnExpose(self, widget, event):
		"""
			Sets scrollbar properties once space has been allocated 
		"""
		
		# calculate scrollable width - allow 4 pixels for borders
		self.scrollRange.page_size = (self.allocation.width - Globals.INSTRUMENT_HEADER_WIDTH - 4) / self.project.viewScale
		self.scrollRange.page_increment = self.scrollRange.page_size
		# add EXTRA_SCROLL_TIME extra seconds
		length = self.project.GetProjectLength() + self.EXTRA_SCROLL_TIME
		self.scrollRange.upper = length
		# Need to adjust project view start if we are zooming out
		# and the end of the project is now before the end of the page.
		# Project end will be at right edge unless the start is also on 
		# screen, in which case the start will be at the left.
		if self.project.viewStart + self.scrollRange.page_size > length:
			start = max(0, length - self.scrollRange.page_size)
			self.scrollRange.value = start
			if start != self.project.viewStart:
				self.project.SetViewStart(start)
			
		
	#_____________________________________________________________________

	def OnAllocate(self, widget, allocation):
		"""
			Callback for "size-allocate" signal
		"""
		self.allocation = allocation
		
	#_____________________________________________________________________
	

	def Update(self):
		"""
			Called either directly from OnStateChanged() or via the owning
			CompactMixView.update() (depending on which view we are in) when
			there is a change of state of an instrument being listened to.
		"""
		# Note: InstrumentViews MUST have the order that the instruments have in
		#       Project.instruments to keep the drag and drop of InstrumentViews
		#       consistent!
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
			
		#self.views is up to date now
		for ident, iv in self.views:
			#check if instrument has been deleted
			if not iv.instrument in self.project.instruments and iv in children:
				self.instrumentBox.remove(iv)
			else:
				iv.Update() #Update non-deleted instruments
		
		
		if len(self.views) > 0:
			self.UpdateSize(None, self.views[0][1].headerAlign.get_allocation())
		else:
			self.UpdateSize(None, None)
		self.show_all()
	
	#_____________________________________________________________________
		
	def UpdateSize(self, widget=None, size=None):
		"""
			Called during update() to re-align the timeline and scrollbars
			with the start of the event lane (instrument width may have altered)
		"""
		#find the width of the instrument headers (they should all be the same size)
		if size:
			tempWidth = size.width
		else:
			tempWidth = self.INSTRUMENT_HEADER_WIDTH
		
		#set it to the globals class
		Globals.INSTRUMENT_HEADER_WIDTH = tempWidth
		
		#align timeline and scrollbar
		self.timelinebar.Update(tempWidth)
		self.al.set_padding(0, 0, tempWidth, 0)
	
	#_____________________________________________________________________
	
	def OnScroll(self, widget):
		"""
			Callback for "value-changed" signal from scrillbar
		"""
		pos = widget.get_value()
		self.project.SetViewStart(pos)

	#_____________________________________________________________________

	def OnZoom(self, widget):
		"""
			Callback for the zoom slider being moved.
		"""
		
		print self.lastzoom
		
		if self.lastzoom < widget.get_value():
			self.lastzoom = widget.get_value()
			self.OnZoomIn()
			
		if self.lastzoom > widget.get_value():
			self.lastzoom = widget.get_value()
			self.OnZoomOut()


	#_____________________________________________________________________

		
	def OnZoomOut(self):
		"""
			Zooms the view.
		"""
		tmp = self.project.viewScale * 2. / 3
		if tmp > 0.5:
			self.project.viewScale = tmp
		self.project.SetViewScale(self.project.viewScale)
		
	#_____________________________________________________________________
		
	def OnZoom100(self, widget):
		"""
			This method is not currently used (it was used when we had zoom buttons) but is
			left here in case we use it in future.
		"""
		self.project.SetViewScale(25.0)
		
	#_____________________________________________________________________
		
	def OnZoomIn(self):
		"""
			Zooms the view.
		"""
		tmp = self.project.viewScale * 1.5
		# beyond 4000 is likely to make the levels disappear
		# increase or remove the limit if event level density is increased.
		if tmp < 4000:
			self.project.viewScale = tmp
		self.project.SetViewScale(self.project.viewScale)
				
	#_____________________________________________________________________

	def OnMouseDown(self, widget, mouse):
		"""
			Callback for "button_press_event" (not catered for by any
			button presses or other mouse handlers)
		"""
		# If we're here then we're out of bounds of anything else
		# So we should clear any selected events
		self.project.ClearEventSelections()
		self.project.SelectInstrument(None)
		self.Update()
		
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None):
		"""
			Called on a change of state in any objects that this object
			is listening to.
		"""
		#HACK because we don't have an instance of instrument we can easily access.
		#in case there are no instruments, we update (hence the "not")
		if not self.project.instruments or change != self.project.instruments[0].VOLUME:
			self.Update()
		
	#_____________________________________________________________________	
#=========================================================================

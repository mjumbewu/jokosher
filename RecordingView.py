
import gtk
import InstrumentViewer
import TimeLineBar
import gobject
import Globals
import Monitored

#=========================================================================

class RecordingView(gtk.Frame):

	__gtype_name__ = 'RecordingView'
	FPS = 30
	INSTRUMENT_HEADER_WIDTH = 150

	#_____________________________________________________________________

	def __init__(self, project):
		gtk.Frame.__init__(self)

		self.project = project
		self.timelinebar = TimeLineBar.TimeLineBar(self.project, self.Update)

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
		zoom_out = gtk.ToolButton(gtk.STOCK_ZOOM_OUT)
		zoom = gtk.ToolButton(gtk.STOCK_ZOOM_100)
		zoom_in = gtk.ToolButton(gtk.STOCK_ZOOM_IN)
		self.hb.pack_start( zoom_out, False, False)
		self.hb.pack_start( zoom, False, False)
		self.hb.pack_start( zoom_in, False, False)
		
		self.scrollRange.lower = 0
		self.scrollRange.upper = 100
		self.scrollRange.value = 0
		self.scrollRange.step_increment = 1
		
		zoom_out.connect("clicked", self.OnZoomOut)
		zoom.connect("clicked", self.OnZoom100)
		zoom_in.connect("clicked", self.OnZoomIn)
		sb.connect("value-changed", self.OnScroll)
		self.connect("expose-event", self.OnExpose)
		self.connect("button_release_event", self.OnExpose)
		self.connect("button_press_event", self.OnMouseDown)
		
		self.Update()
	#_____________________________________________________________________

	def OnExpose(self, widget, event):
		self.scrollRange.page_size = (self.allocation.width - 180) / self.project.viewScale
		self.scrollRange.page_increment = self.scrollRange.page_size
		self.scrollRange.upper = self.project.GetProjectLength()
	#_____________________________________________________________________
	
	def Update(self):
		children = self.instrumentBox.get_children()
		for instr in self.project.instruments:
			iv = None
			for ident, instrV in self.views:
				if instrV.instrument is instr:
					iv = instrV
					break
			if not iv:
				iv = InstrumentViewer.InstrumentViewer(self.project, instr)
				instr.AddListener(self)
				self.views.append((instr.id, iv))
				iv.headerBox.connect("size-allocate", self.UpdateSize)
			
			if not iv in children:
				self.instrumentBox.pack_start(iv, False, False)
			
			iv.show()
		
		for ident, iv in self.views:
			#check if instrument has been deleted
			if not iv.instrument in self.project.instruments and iv in children:
				self.instrumentBox.remove(iv)
			else:
				iv.Update()
		
		if len(self.views) > 0:
			self.UpdateSize(None, self.views[0][1].headerBox.get_allocation())
		else:
			self.UpdateSize(None, None)
		self.show_all()
	
	#_____________________________________________________________________
		
	def UpdateSize(self, widget, size):
		#find the width of the instrument headers (they should all be the same size)
		if size:
			tempWidth = size.width
		else:
			tempWidth = self.INSTRUMENT_HEADER_WIDTH
		
		#set it to the globals class so compactmix can use the same width
		Globals.INSTRUMENT_HEADER_WIDTH = tempWidth
		
		self.timelinebar.Update(tempWidth)
		self.al.set_padding(0, 0, tempWidth, 0)
	
	#_____________________________________________________________________
	
	def OnScroll(self, widget):
		pos = widget.get_value()
		self.project.SetViewStart(pos)

	#_____________________________________________________________________
		
	def OnZoomOut(self, widget):
		tmp = self.project.viewScale * 2. / 3
		if tmp > 0.5:
			self.project.viewScale = tmp
		self.project.SetViewScale(self.project.viewScale)
		
	#_____________________________________________________________________
		
	def OnZoom100(self, widget):
		self.project.SetViewScale(25.0)
		
	#_____________________________________________________________________
		
	def OnZoomIn(self, widget):
		tmp = self.project.viewScale * 1.5
		# Warning: change this value with caution increases
		# beyond 4000 are likely to cause crashes!
		if tmp < 4000:
			self.project.viewScale = tmp
		self.project.SetViewScale(self.project.viewScale)
				
	#_____________________________________________________________________

	def OnMouseDown(self, widget, mouse):
		# If we're here then we're out of bounds of anything else
		# So we should clear any selected events
		self.project.ClearEventSelections()
		self.project.ClearInstrumentSelections()
		self.Update()
		
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None):
		if change != Monitored.LEVEL:
			self.Update()
		
	#_____________________________________________________________________	
#=========================================================================

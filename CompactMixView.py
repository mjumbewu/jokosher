
import gtk
from MixerStrip import *
import InstrumentViewer
import gobject
import TimeLineBar
import Globals
import Monitored
from MasterMixerStrip import *

#create signal to be emitted by MixerStrip
gobject.signal_new("minimise", MixerStrip, gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())

#=========================================================================

class CompactMixView(gtk.Frame):
	""" This class implements the mix view
	"""
	
	FPS = 10 # number of times a second the VUWidgets need updating
	
	#_____________________________________________________________________
	
	def __init__(self, project, mainview):
		gtk.Container.__init__(self)
		self.project = project
		self.mainview = mainview
		self.vbox = None
		self.channels = []
		self.lanes = []
		self.hbox = None
		self.timebox = None
		self.instrbar = None
		self.Updating = False
		
		self.vbox = gtk.VBox()
		self.add(self.vbox)
		
		self.timelinebar = TimeLineBar.TimeLineBar(self.project, self, mainview)
		self.vbox.pack_start(self.timelinebar, False, False)
		
		self.vpaned = gtk.VPaned()
		self.vbox.pack_start(self.vpaned, True, True)
		
		self.timebox = gtk.VBox()
		scrolledwindow = gtk.ScrolledWindow()
		scrolledwindow.add_with_viewport(self.timebox)
		self.vpaned.add(scrolledwindow)
		
		self.hbox = gtk.HBox()
		self.vpaned.add(self.hbox)
		
		#self.masterfaderhbox = gtk.HBox()
		self.mastermixer = MasterMixerStrip(self.project, self, self.mainview)
		
		#self.vpaned.add(self.masterfaderhbox)
		self.show_all()
		self.UpdateTimeout = False

		self.connect("button_press_event", self.OnMouseDown)
		self.connect("size_allocate", self.OnAllocate)
		
		self.Update()
		
	#_____________________________________________________________________

	def OnAllocate(self, widget, allocation):
		self.allocation = allocation
	
	#_____________________________________________________________________

	def Update(self):
		if self.Updating:
			return
		self.Updating = True
		
		self.timelinebar.Update(Globals.INSTRUMENT_HEADER_WIDTH)
		
		for i in self.timebox.get_children():
			self.timebox.remove(i)
		for i in self.hbox.get_children():
			self.hbox.remove(i)
		
		for instr in self.project.instruments:
			if instr.isVisible:
				lanebox = None
				for i in self.lanes:
					if i.instrument is instr:
						lanebox = i
						lanebox.Update()
						break
					
				if not lanebox:
					lanebox = InstrumentViewer.InstrumentViewer(self.project, instr, self, self.mainview, True)
					instr.AddListener(self)
					self.lanes.append(lanebox)
				
				self.timebox.pack_start(lanebox)
				lanebox.headerBox.set_size_request(Globals.INSTRUMENT_HEADER_WIDTH, -1)
				
				strip = None
				for i in self.channels:
					if i.instrument is instr:
						strip = i
						strip.Update()
						break
				
				if not strip:
					strip = MixerStrip(self.project, instr, self, self.mainview)
					strip.connect("minimise", self.OnMinimiseTrack, instr)
					self.channels.append(strip)
					
				self.hbox.pack_start(strip, False, False)
		
		#Pack the master vuwidget
		self.hbox.pack_end(self.mastermixer, False, False)
			
		#create the minimise instruments bar
		if self.instrbar:
			self.vbox.remove(self.instrbar)
		self.instrbar = gtk.Toolbar()
		self.instrbar.set_show_arrow(True)
		self.instrbar.set_style(gtk.TOOLBAR_BOTH_HORIZ)
		self.vbox.pack_end(self.instrbar, False, True)
		
		toollab = gtk.ToolItem()
		lab = gtk.Label()
		lab.set_markup("<b>Instruments Not Shown:</b>")
		toollab.add(lab)
		toollab.set_is_important(True)
		self.instrbar.insert(toollab, 0)

		for instr in self.project.instruments:
			if not instr.isVisible:
				toolbutt = gtk.ToolButton()
				
				imgsize = gtk.icon_size_lookup(gtk.ICON_SIZE_MENU)[0]
				pixbuf = instr.pixbuf.scale_simple(imgsize, imgsize, gtk.gdk.INTERP_BILINEAR)
				image = gtk.Image()
				image.set_from_pixbuf(pixbuf)
				
				toolbutt.set_label(instr.name)
				toolbutt.set_icon_widget(image)
				toolbutt.set_is_important(True)
				toolbutt.connect("clicked", self.OnMaximiseTrack, instr)
				
				self.instrbar.insert(toolbutt, -1)
		
		self.show_all()
		self.Updating = False
		#for when being called from gobject thread
		return False
	#_____________________________________________________________________

	def OnMinimiseTrack(self, widget, instr):
		instr.SetVisible(False)
		
	#_____________________________________________________________________

	def OnMaximiseTrack(self, widget, instr):
		instr.SetVisible(True)
		
	#_____________________________________________________________________

	def OnMouseDown(self, widget, event):
		self.project.ClearEventSelections()
		self.project.ClearInstrumentSelections()
	
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None):
		self.Update()
	#_____________________________________________________________________
	
	def OnUpdateTimeout(self):
		""" Called at intervals (self.FPS) to update the VU meters
		"""
		if self.mainview.isPlaying:
			self.mastermixer.vu.queue_draw()
			
			# redraw VU widgets for each instrument
			for mix in self.channels:
				mix.vu.queue_draw()
			
			return True
		else:
			# kill timeout when play has stopped
			self.UpdateTimeout = False
			return False
	#_____________________________________________________________________
		
	def StartUpdateTimeout(self):
		""" Initiates the OnUpdateTimeout - called from MainApp.play()
		when the play button is pressed
		"""
		if not self.UpdateTimeout:
			gobject.timeout_add(int(1000 / self.FPS), self.OnUpdateTimeout, priority = gobject.PRIORITY_LOW)
			self.UpdateTimeout = True
	#_____________________________________________________________________
	
#=========================================================================
		

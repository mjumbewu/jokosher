import gtk
import gobject
import Globals
import RecordingView
from MixerStrip import *
from MasterMixerStrip import *
import gettext
_ = gettext.gettext

#create signal to be emitted by MixerStrip
gobject.signal_new("minimise", MixerStrip, gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ())

#=========================================================================

class CompactMixView(gtk.Frame):
	""" This class implements the mix view
	"""
	
	FPS = 10 # number of times a second the VUWidgets need updating
	
	#_____________________________________________________________________
	
	def __init__(self, project, mainview):
		gtk.Frame.__init__(self)
		self.project = project
		self.mainview = mainview
		self.channels = []
		self.lanes = []
		self.Updating = False
		self.instrbar = None
		
		self.vbox = gtk.VBox()
		self.add(self.vbox)
		self.vpaned = gtk.VPaned()
		self.vbox.pack_start(self.vpaned, True, True)
		self.projectview = RecordingView.RecordingView(project, mainview, self, True)
		self.vpaned.add(self.projectview)
		self.hbox = gtk.HBox()
		self.vpaned.add(self.hbox)
		
		self.mastermixer = MasterMixerStrip(self.project, self, self.mainview)
		
		self.show_all()
		self.UpdateTimeout = False
		self.Update()
	#_____________________________________________________________________

	def Update(self):
		if self.Updating:
			return
		
		self.Updating = True
		self.projectview.Update()
		for i in self.hbox.get_children():
			self.hbox.remove(i)
		
		for instr in self.project.instruments:
			if instr.isVisible:
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
			
		#create the minimise instruments bar
		if self.instrbar:
			self.vbox.remove(self.instrbar)
		self.instrbar = gtk.Toolbar()
		self.instrbar.set_show_arrow(True)
		self.instrbar.set_style(gtk.TOOLBAR_BOTH_HORIZ)
		self.vbox.pack_end(self.instrbar, False, True)
		
		toollab = gtk.ToolItem()
		lab = gtk.Label()
		lab.set_markup(_("<b>Instruments Not Shown:</b>"))
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
	
#=========================================================================
		
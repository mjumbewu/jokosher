#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	CompactMixView.py
#	
#	A sub-class of gtk.Frame containing the mixing view of the project
#
#-------------------------------------------------------------------------------

import gtk
import gobject
import RecordingView
from MixerStrip import *
from MasterMixerStrip import *
import gettext
_ = gettext.gettext

#=========================================================================

class CompactMixView(gtk.Frame):
	"""
	This class implements the mixing workspace view.
	"""
	
	""" Number of times a second the VUWidgets need updating. """
	FPS = 10
	
	#_____________________________________________________________________
	
	def __init__(self, project, mainview):
		"""
		Creates a new instance of CompactMixView.
		
		Parameters:
			project -- the active Project.
			mainview -- reference to the MainApp Jokosher window.
		"""
		gtk.Frame.__init__(self)
		self.project = project
		self.mainview = mainview
		self.small = True
		self.mix = False
		self.mixerStripList = []
		self.minimisedButtonList = []
		self.lanes = []
		self.Updating = False
		self.CreateInstrumentBar()
		
		self.vbox = gtk.VBox()
		self.add(self.vbox)
		self.hbox = gtk.HBox()
		self.vbox.pack_start(self.hbox, True, True)
		
		self.mastermixer = MasterMixerStrip(self.project, self, self.mainview)
		self.hbox.pack_end(self.mastermixer, False, False)
		
		self.scrollWindow = gtk.ScrolledWindow()
		self.mixerBox = gtk.HBox()
		
		self.scrollWindow.add_with_viewport(self.mixerBox)
		# remove the shadow on the viewport
		self.scrollWindow.child.set_shadow_type(gtk.SHADOW_NONE)
		self.scrollWindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_NEVER)
		self.hbox.pack_start(self.scrollWindow, True, True)
		

		self.project.connect("instrument::added", self.OnInstrumentAdded)
		self.project.connect("instrument::reordered", self.OnInstrumentReordered)
		self.project.connect("instrument::removed", self.OnInstrumentRemoved)
		
		#initialize the instrument widgets
		for instr in self.project.instruments:
			self.OnInstrumentAdded(self.project, instr)
		self.show_all()
		self.UpdateTimeout = False
		
	#_____________________________________________________________________

	def CreateInstrumentBar(self):
		self.instrumentBar = gtk.Toolbar()
		self.instrumentBar.set_show_arrow(True)
		self.instrumentBar.set_style(gtk.TOOLBAR_BOTH_HORIZ)
		toollab = gtk.ToolItem()
		lab = gtk.Label()
		lab.set_markup(_("<b>Instruments Not Shown:</b>"))
		toollab.add(lab)
		toollab.set_is_important(True)
		self.instrumentBar.insert(toollab, 0)
	
	#_____________________________________________________________________

	def OnMinimiseTrack(self, widget, instr):
		"""
		Minimizes a mixer strip (instrument).
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			instr -- the Instrument to be hidden.
		"""
		instr.SetVisible(False)
		
	#_____________________________________________________________________

	def OnMaximiseTrack(self, widget, instr):
		"""
		Maximizes a mixer strip (instrument).
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			instr -- the Instrument to be shown.
		"""
		instr.SetVisible(True)
	
	#_____________________________________________________________________
	
	def OnInstrumentVisible(self, instrument):
		"""
		Callback for when the visible status of an instrument changes.
		
		Parameters:
			instrument -- the instrument instance that send the signal.
		"""
		
		visib = instrument.isVisible
		for strip in self.mixerStripList:
			if not strip.instrument is instrument:
				continue
			
			if visib and not strip.parent:
				self.mixerBox.pack_start(strip, False, False)
				strip.show_all()
			elif not visib and strip.parent:
				self.mixerBox.remove(strip)
			
			break
		
		for instr, toolButton in self.minimisedButtonList:
			if not instr is instrument:
				continue
				
			if not visib and not toolButton.parent:
				self.instrumentBar.insert(toolButton, -1)
				toolButton.show_all()
			elif visib and toolButton.parent:
				self.instrumentBar.remove(toolButton)
			
			break
		
		# Only show the instrument bar if there is something minimized
		minimisedInstrs = [x for x in self.project.instruments if not x.isVisible]
		if minimisedInstrs and not self.instrumentBar.parent:
			self.vbox.pack_end(self.instrumentBar, False, True)
			self.instrumentBar.show_all()
		elif not minimisedInstrs and self.instrumentBar.parent:
			self.vbox.remove(self.instrumentBar)
		
	#_____________________________________________________________________
	
	def OnInstrumentAdded(self, project, instrument):
		"""
		Callback for when an instrument is added to the project.
		
		Parameters:
			project -- The project that the instrument was added to.
			instrument -- The instrument that was added.
		"""
		
		strip = MixerStrip(self.project, instrument, self, self.mainview)
		strip.connect("minimise", self.OnMinimiseTrack, instrument)
		self.mixerStripList.append(strip)
		
		#create the toolbar button that will be shown when the instrument is minimised
		imgsize = gtk.icon_size_lookup(gtk.ICON_SIZE_MENU)[0]
		pixbuf = instrument.pixbuf.scale_simple(imgsize, imgsize, gtk.gdk.INTERP_BILINEAR)
		image = gtk.Image()
		image.set_from_pixbuf(pixbuf)
		toolButton = gtk.ToolButton()
		toolButton.set_label(instrument.name)
		toolButton.set_icon_widget(image)
		toolButton.set_is_important(True)
		toolButton.connect("clicked", self.OnMaximiseTrack, instrument)
		
		self.minimisedButtonList.append( (instrument, toolButton) )
		
		instrument.connect("visible", self.OnInstrumentVisible)
		#check if the instrument is currently visible and show the widgets
		self.OnInstrumentVisible(instrument)
	
	#_____________________________________________________________________
	
	def OnInstrumentRemoved(self, project, instrument):
		"""
		Callback for when an instrument is removed from the project.
		
		Parameters:
			project -- The project that the instrument was removed from.
			instrument -- The instrument that was removed.
		"""
		
		for strip in self.mixerStripList:
			if strip.instrument is instrument:
				if strip.parent:
					self.mixerBox.remove(strip)
				strip.Destroy()
				self.mixerStripList.remove(strip)
				break
				
		for instr, toolButton in self.minimisedButtonList:
			if instr is instrument:
				if toolButton.parent:
					self.instrumentBar.remove(toolButton)
				self.minimisedButtonList.remove( (instr, toolButton) )
				break
	
	#_____________________________________________________________________
	
	def OnInstrumentReordered(self, project, instrument):
		"""
		Callback for when an instrument's position in the project has changed.
		
		Parameters:
			project -- The project that the instrument was changed on.
			instrument -- The instrument that was reordered.
		"""
		if not instrument.isVisible:
			return
		
		visibleInstrs = [x for x in self.project.instruments if x.isVisible]
		for strip in self.mixerStripList:
			if strip.instrument is instrument:
				if strip.parent:
					pos = visibleInstrs.index(instrument)
					self.mixerBox.reorder_child(strip, pos + 1)
				break
		
	#_____________________________________________________________________
	
	def OnUpdateTimeout(self):
		"""
		Called at intervals (self.FPS) to update the VU meters.
		
		Returns:
			True -- keeps the timeout going during playback.
			False -- stops the timeout when playback stops.
		"""
		if self.mainview.isPlaying:
			self.mastermixer.vu.queue_draw()
			
			# redraw VU widgets for each instrument
			for mix in self.mixerStripList:
				mix.vu.queue_draw()
			
			return True
		else:
			# kill timeout when playback has stopped
			self.UpdateTimeout = False
			return False
	
	#_____________________________________________________________________
	
	def StartUpdateTimeout(self):
		""" 
		Initiates the OnUpdateTimeout - called from MainApp.play()
		when the play button is pressed.
		"""
		if not self.UpdateTimeout:
			gobject.timeout_add(int(1000 / self.FPS), self.OnUpdateTimeout, priority = gobject.PRIORITY_LOW)
			self.UpdateTimeout = True
	
#=========================================================================
		

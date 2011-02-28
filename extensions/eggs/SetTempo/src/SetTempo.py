#	SetTempo.py
#	-----------
#	This extension allows you to set the tempo for imported audio
#	by playing it back and tapping the space bar in time with the beat.
import Jokosher.Extension
import gtk
import pkg_resources
import time
	
#=========================================================================

class SetTempo:
	"""
	The class implements the SetTempo extension. It consists of
	a dialog popped up by selecting the "Set Tempo" option
	which is installed into the extensions menu by 
	the startup method.
	
	The SetTempo extension allows you to determine the tempo for the
	current project by tapping out the beat on the spacebar during
	playback. It has it's own play and stop buttons to avoid 
	switching back and forth with the main Jokosher window.
	"""
	EXTENSION_NAME = "Set Tempo"
	EXTENSION_DESCRIPTION = "Sets the tempo for the current project by tapping in time with the music"
	EXTENSION_VERSION = "0.11"
	
	# The number of past intervals it will store to perform a "rolling" average.
	ROLLING_SAMPLE_SIZE = 4
	
	#_____________________________________________________________________
	
	def startup(self, api):
		"""
		Called by the extension manager during Jokosher startup
		or when the extension is added via ExtensionManagerDialog.
		
		Parameters:
			api -- a reference to the Extension API
		"""
		self.API = api
		self.menu_item = self.API.add_menu_item("Set Tempo", self.OnMenuItemClick)

	#_____________________________________________________________________
	
	def shutdown(self):
		"""
		Called by the extension manager when the extension is
		disabled or deleted.
		"""
		self.menu_item.destroy()

	#_____________________________________________________________________
	
	def OnMenuItemClick(self, arg):
		"""
		GTK callback when the menu item added in startup()
		is selected.
		
		Parameters:
			arg -- set by GTK
		"""
		xmlString = pkg_resources.resource_string(__name__, "SetTempo.ui")
		gtkBuilder = gtk.Builder()
		gtkBuilder.add_from_string(xmlString)
		
		self.window = gtkBuilder.get_object("SetTempoDialog")
		self.API.set_window_icon(self.window)
		self.tempoLabel = gtkBuilder.get_object("tempoLabel")
		signals = {
			"OnClearClicked" : self.OnClear,
			"OnStopClicked" : self.OnStop,
			"OnPlayClicked" : self.OnPlay,
			"OnTapClicked" : self.OnTap,
			"OnSetClicked" : self.OnSet,
			"OnCancelClicked" : self.OnCancel
		}
		gtkBuilder.connect_signals(signals)
		
		self.window.set_transient_for(self.API.mainapp.window)
		self.WriteLabel(0)
		self.tappingTime = False
		self.prevTime = 0
		self.intervalList = []
		self.bpm = 0

	#_____________________________________________________________________
	
	def OnClear(self, widget):
		"""
		GTK callback when the "Clear" button is clicked
		
		Parameters:
			widget -- set by GTK
		"""
		self.tappingTime = False
		self.WriteLabel(0)
		self.bpm = 0
		
	#_____________________________________________________________________
	
	def OnStop(self, widget):
		"""
		GTK callback when the "Stop" button is clicked
			
		Parameters:
			widget -- set by GTK
		"""
		self.API.stop()
		
	#_____________________________________________________________________
	
	def OnPlay(self, widget):
		"""
		GTK callback when the "Play" button is clicked
			
		Parameters:
			widget -- set by GTK
		"""
		self.API.play()
		
	#_____________________________________________________________________
	
	def OnTap(self, widget):
		"""
		GTK callback when the "Tap" button is clicked
		Note that none of the other buttons grab the focus
		when clicked so the spacebar can easily be used to 
		press this button. (Tapping the spacebar bar being
		easier than clicking the mouse).
			
		Parameters:
			widget -- set by GTK
		"""
		timeNow = time.time()
		if self.tappingTime:
			self.intervalList.append(timeNow - self.prevTime)
			while len(self.intervalList) > self.ROLLING_SAMPLE_SIZE:
				self.intervalList.pop(0)
			sum = reduce(lambda x,y:x+y, self.intervalList)
			self.bpm = int(60 * float(len(self.intervalList)) / sum)
			self.WriteLabel(self.bpm)
		else:
			self.tappingTime = True

		self.prevTime = timeNow
		
	#_____________________________________________________________________
	
	def OnSet(self, widget):
		"""
		GTK callback when the "Set" button is clicked
			
		Parameters:
			widget -- set by GTK
		"""
		if self.bpm > 0:
			self.API.set_bpm(self.bpm)
			self.window.destroy()
		
	#_____________________________________________________________________
	
	def OnCancel(self, widget):
		"""
		GTK callback when the "Cancel" button is clicked
			
		Parameters:
			widget -- set by GTK
		"""
		self.window.destroy()
		
	#_____________________________________________________________________
	
	def WriteLabel(self, value):
		"""
		Formats and writes the bpm value
		"""
		if value:
			self.tempoLabel.set_markup("<span font_desc='Sans Bold 32'>%d BPM</span>" % value)
		else:
			self.tempoLabel.set_markup("<span font_desc='Sans Bold 32'>No BPM</span>")

	#_____________________________________________________________________
	
#=========================================================================


import pygtk
pygtk.require("2.0")
import gtk

from VUWidget import *

#=========================================================================

class MasterMixerStrip(gtk.Frame):
	
	__gtype_name__ = 'MasterMixerStrip'
	
	#_____________________________________________________________________
	
	def __init__(self, project):
		gtk.Container.__init__(self)
		self.project = project
		self.Updating = False
		
		self.vbox = gtk.VBox()
		self.add(self.vbox)

		self.label = gtk.Label("Master Volume")
				
		self.vbox.pack_start(self.label, False)
		
		# VU Meter
		self.vu = VUWidget(self)
		self.vbox.pack_start(self.vu, True, True)
				
		self.vbox.show_all()
		self.show_all()
		
	#_____________________________________________________________________
	
	def EmitMinimise(self, widget):
		self.emit("minimise")
	
	#_____________________________________________________________________

	def GetLevel(self):
		return self.project.masterlevel

	#_____________________________________________________________________

	def GetVolume(self):
		return self.project.mastervolume
		
	#_____________________________________________________________________

	def SetVolume(self, vol):
		self.project.SetVolume(vol)
		
	#_____________________________________________________________________
	
#=========================================================================

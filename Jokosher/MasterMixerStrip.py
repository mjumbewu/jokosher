#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	Contains a master VU widget and levels for all Instruments.
#
#-------------------------------------------------------------------------------
import pygtk
pygtk.require("2.0")
import gtk

from VUWidget import *
import gettext
_ = gettext.gettext

#=========================================================================

class MasterMixerStrip(gtk.Frame):
	"""
	Contains a master VU widget and levels for all Instruments.
	"""
	
	""" GTK widget name """
	__gtype_name__ = 'MasterMixerStrip'
	
	#_____________________________________________________________________
	
	def __init__(self, project, mixview, mainview):
		"""
		Contains a new instance of MasterMixerStrip.
		
		Parameters:
			project -- the currently active Project.
			mixview -- the mixing view object (CompactMixView).
			mainview -- the main Jokosher window (MainApp).
		"""
		gtk.Container.__init__(self)
		self.project = project
		self.mixview = mixview
		self.mainview = mainview
		self.Updating = False
		
		self.vbox = gtk.VBox()
		self.add(self.vbox)

		self.label = gtk.Label(_("Master Volume:"))
		self.label.set_padding(3, 3)

		self.vbox.pack_start(self.label, False)
		
		# VU Meter
		self.vu = VUWidget(self, self.mainview)
		self.vbox.pack_start(self.vu, True, True)
				
		self.vbox.show_all()
		self.show_all()
		
	#_____________________________________________________________________
	
	def EmitMinimise(self, widget):
		"""
		Passes the EmitMinimise call coming from an Instrument MixerStrip to GTK.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.emit("minimise")
	
	#_____________________________________________________________________

	def GetLevel(self):
		"""
		Obtain the master level.
		
		Returns:
			the master level value.
		"""
		return self.project.level

	#_____________________________________________________________________

	def GetVolume(self):
		"""
		Obtain the master volume.
		
		Returns:
			the master volume level.
		"""
		return self.project.volume
		
	#_____________________________________________________________________

	def SetVolume(self, vol):
		"""
		Sets the master volume.
		
		Parameters:
			vol -- volume value to set the master volume to.
		"""
		self.project.SetVolume(vol)
		
	#_____________________________________________________________________
	
	def CommitVolume(self):
		#there is no incremental save for project volume
		#as opposed to instrument volume. So do nothing for now.
		pass
	
	#_____________________________________________________________________
	
#=========================================================================

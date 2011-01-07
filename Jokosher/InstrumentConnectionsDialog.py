#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	This class handles all of the processing associated with the
#	Instrument Connections dialog.
#
#-------------------------------------------------------------------------------

import gtk
import gobject
import pygst
pygst.require("0.10")
import gst
import Globals
import AudioBackend
import PreferencesDialog
import gettext
_ = gettext.gettext

#=========================================================================

class InstrumentConnectionsDialog:
	"""
	Handles all of the processing associated with the Instrument Connections dialog.
	"""
	
	#_____________________________________________________________________

	def __init__(self, project, parent):
		"""
		Creates a new instance of InstrumentConnectionsDialog.
		
		Parameters:
			project -- the currently active Project.
			parent -- reference to the MainApp Jokosher window.
		"""
		if project:
			self.project = project
		else:
			return
		
		self.gtk_builder = Globals.LoadGtkBuilderFilename("InstrumentConnectionsDialog.ui")

		self.signals = {
			"on_close_clicked" : self.OnClose,
			"on_change_sound_system" : self.OnChangeSoundSystem,
		}
		
		self.gtk_builder.connect_signals(self.signals)

		self.window = self.gtk_builder.get_object("InstrumentConnectionsDialog")
		self.vbox = self.gtk_builder.get_object("vbox")
		
		if len(self.project.instruments) > 0:
			self.Populate()
		else:
			self.gtk_builder.get_object("explainLabel").set_text(_("There are no instruments to connect"))

		self.parent = parent
		self.window.set_icon(self.parent.icon)
		## centre the InstrumentConnectionsDialog on the main jokosher window
		self.window.set_transient_for(self.parent.window)
		self.window.show_all()

	#_____________________________________________________________________

	def OnClose(self, button):
		"""
		Called when the dialog gets closed.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.window.destroy()
	
	#_____________________________________________________________________
	
	def OnChangeSoundSystem(self, button):
		prefsdlg = PreferencesDialog.PreferencesDialog(self.project, self.parent, self.parent.icon)
		self.window.hide()
		# TODO: don't create a new instance of this window each time
		prefsdlg.dlg.connect("destroy", self.parent.OnInstrumentConnectionsDialog)
		prefsdlg.dlg.show_all()
	
	#_____________________________________________________________________

	def Populate(self):
		"""
		Creates all the widgets for intruments and devices that compose the
		InstrumentConnectionsDialog and then adds them to the dialog.
		"""
		
		self.devices_list = []
		liststore = gtk.ListStore(gobject.TYPE_STRING)
	
		#Find out how many channels a device offers
		for device, deviceName in AudioBackend.ListCaptureDevices():
			#Don't want the default device twice (once as 'default' and once as its actual hw ref)
			# Default will always be the first one, and have no name.
			if not self.devices_list and not deviceName:
				if device == "default":
					display = _("Default")
				else:
					display = _("Default (%s)") % device
				self.devices_list.append((device, display, -1))
				liststore.append((display,))
			else:			
				num_channels = AudioBackend.GetChannelsOffered(device)
				for input in xrange(num_channels):
					if num_channels > 1:
						s = _("%(device)s (%(id)s), input %(input)d")
						display = s % {"device":deviceName, "id":device, "input":input}
					else:
						display = _("%(device)s (%(id)s)") % {"device":deviceName, "id":device}
					self.devices_list.append((device, deviceName, input))
					liststore.append((display,))
		
		if self.devices_list:
			for instr in self.project.instruments:
				instrument = instr
				row = gtk.HBox()
				row.set_spacing(10)
				image = gtk.Image()
				image.set_from_pixbuf(instrument.pixbuf)
				label = gtk.Label(instrument.name)
				
				combobox = gtk.ComboBox(liststore)
				cell = gtk.CellRendererText()
				combobox.pack_start(cell, True)
				combobox.add_attribute(cell, 'text', 0)
				
				if instr.input is None:
					# None means default; default is first in combobox
					combobox.set_active(0)
				else:
					currentItem = 0
					for device, deviceName, input in self.devices_list:
						if instr.input == device and input == instr.inTrack:
							combobox.set_active(currentItem)
						currentItem += 1
				
				combobox.connect("changed", self.OnSelected, instr)
				row.pack_start(combobox, True, True)
				row.pack_start(image, False, False)
				row.pack_start(label, False, False)
				
				self.vbox.add(row)
		else:
			audiosrc = Globals.settings.recording["audiosrc"]
			sound_system = None
			for name, element in Globals.CAPTURE_BACKENDS:
				if element == audiosrc:
					sound_system = name
			
			if sound_system:
				msg = _("The %(sound-system-name)s sound system does not support device selection.")
				msg %= {"sound-system-name" : sound_system}
			else:
				msg = _('The "%(custom-pipeline)s" sound system does not support device selection.')
				msg %= {"custom-pipeline" : audiosrc}
			self.gtk_builder.get_object("explainLabel").set_text(msg)
			self.vbox.hide()
	
	#_____________________________________________________________________
			
	def OnSelected(self, widget, instr):
		"""
		Sets the instrument's input device.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			instr -- Instrument to change the input device to.
		"""
		device, deviceName, inTrack = self.devices_list[widget.get_active()]
		instr.SetInput(device, inTrack)
			
	#_____________________________________________________________________
	
#=========================================================================

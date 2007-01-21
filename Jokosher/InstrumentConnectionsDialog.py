#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	This class handles all of the processing associated with the
#	Instrument Connections dialog.
#
#-------------------------------------------------------------------------------

import gtk.glade
import gobject
import pygst
pygst.require("0.10")
import gst
import Globals
import AlsaDevices
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
		
		self.res = gtk.glade.XML(Globals.GLADE_PATH, "InstrumentConnectionsDialog")

		self.signals = {
			"on_close_clicked" : self.OnClose,
		}
		
		self.res.signal_autoconnect(self.signals)

		self.window = self.res.get_widget("InstrumentConnectionsDialog")
		self.vbox = self.res.get_widget("vbox")
		
		if len(self.project.instruments) > 0:
			self.Populate()
		else:
			self.res.get_widget("explainLabel").set_text(_("There are no instruments to connect"))

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

	def Populate(self):
		"""
		Creates all the widgets for intruments and devices that compose the
		InstrumentConnectionsDialog and then adds them to the dialog.
		"""
		self.inputs = {}
	
		#Find out how many channels a device offers
		for device, deviceName in AlsaDevices.GetAlsaList("capture").items():

			#Don't want the default device twice (once as 'default' and once as its actual hw ref)
			if device == "default":
				continue

			self.inputs[device] = (deviceName, AlsaDevices.GetChannelsOffered(device))
		
		for instr in self.project.instruments:		
			instrument = instr
			row = gtk.HBox()
			row.set_spacing(10)
			image = gtk.Image()
			image.set_from_pixbuf(instrument.pixbuf)
			label = gtk.Label(instrument.name)
			
			liststore = gtk.ListStore(gobject.TYPE_STRING)
			combobox = gtk.ComboBox(liststore)
			cell = gtk.CellRendererText()
			combobox.pack_start(cell, True)
			combobox.add_attribute(cell, 'text', 0)

			self.AlsaID = []
			
			# put in a none option just in case
			combobox.append_text(_("Default"))
			if instr.input == "default" and instr.inTrack == 0:
				combobox.set_active(0)
			self.AlsaID.append(("default", 0))
			
			currentItem = 1
			for device, (deviceName, numInputs) in self.inputs.items():
				for input in range(0, numInputs):
					combobox.append_text(_("%s input %d") % (deviceName, input))
					if instr.input == device and input == instr.inTrack:
						combobox.set_active(currentItem)
					self.AlsaID.append((device, input))
					currentItem += 1
			
			combobox.connect("changed", self.OnSelected, instr)
			row.pack_start(combobox, False, False)
			row.pack_start(image, False, False)
			row.pack_start(label, False, False)
			
			self.vbox.add(row)
	
	#_____________________________________________________________________
			
	def OnSelected(self, widget, instr):
		"""
		Sets the instrument's input device.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			instr -- Instrument to change the input device to.
		"""
		device, inTrack = self.AlsaID[widget.get_active()]
		if device != instr.input or inTrack != instr.inTrack:
			instr.input = device
			instr.inTrack = inTrack
			self.project.unsavedChanges = True
			
	#_____________________________________________________________________
	
#=========================================================================

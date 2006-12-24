#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
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
	""" This class handles all of the processing associated with the
		Instrument Connections dialog.
	"""	
	#_____________________________________________________________________

	def __init__(self, project, parent):
				
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
		self.window.destroy()
	
	#_____________________________________________________________________

	def Populate(self):
		self.inputs = {}
	
		#Find out how many channels a device offers
		for deviceName, device in AlsaDevices.GetAlsaList("capture").items():

			#Don't want the default device twice (once as 'default' and once as its actual hw ref)
			if device == "default":
				continue

			self.inputs[deviceName] = (device, AlsaDevices.GetChannelsOffered(device))
		
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

			currentItem = 0
			for deviceName, (device, numInputs) in self.inputs.items():
				for input in range(0, numInputs):
					combobox.append_text("%s input %d"%(deviceName, input))
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
		'''Set the instrument's input'''
		device, inTrack = self.AlsaID[widget.get_active()]
		if device != instr.input or inTrack != instr.inTrack:
			instr.input = device
			instr.inTrack = inTrack
			self.project.unsavedChanges = True
			
	#_____________________________________________________________________
	
#=========================================================================

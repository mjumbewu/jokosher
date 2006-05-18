
import gtk
import gtk.glade
import gobject
import pygst
pygst.require("0.10")
import gst
import os
import sys
import Globals
import Project
import AlsaDevices

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
		
		self.res = gtk.glade.XML ("Jokosher.glade", "InstrumentConnectionsDialog")

		self.signals = {
			"on_close_clicked" : self.OnClose,
		}
		
		self.res.signal_autoconnect(self.signals)

		self.window = self.res.get_widget("InstrumentConnectionsDialog")
		self.vbox = self.res.get_widget("vbox")
		
		if len(self.project.instruments) > 0:
			self.Populate()
		else:
			self.res.get_widget("explainLabel").set_text("There are no instruments to connect")

		self.parent = parent
		self.window.set_icon(self.parent.icon)
		self.window.show_all()

	#_____________________________________________________________________

	def OnClose(self, button):
		self.window.destroy()

	def Populate(self):
		mixers = {}
	
		for device in AlsaDevices.GetAlsaList("capture").values():

			mixer = gst.element_factory_make('alsamixer')
			mixer.set_property("device", device)
			mixer.set_state(gst.STATE_READY)

			if not mixer.implements_interface(gst.interfaces.Mixer):
				print 'Cannot get mixer tracks from the device. Check permissions on the mixer device.'
			else:
				mixers[device] = mixer.list_tracks()
			
			mixer.set_state(gst.STATE_NULL)
		
		for instr in self.project.instruments:			
			instrument = instr
			row = gtk.HBox()
			row.set_spacing(10)
			image = gtk.Image()
			image.set_from_pixbuf(instrument.pixbuf)
			label = gtk.Label(instrument.name)
			
			# we will need to pre-select the current input in the combo box
			# but its not coded yet
			
			liststore = gtk.ListStore(gobject.TYPE_STRING)
			combobox = gtk.ComboBox(liststore)
			cell = gtk.CellRendererText()
			combobox.pack_start(cell, True)
			combobox.add_attribute(cell, 'text', 0)

			self.AlsaID = []

			for device in mixers:
				mixertracks = mixers[device]
				for t in mixertracks:
					if t.flags & gst.interfaces.MIXER_TRACK_INPUT:
						combobox.append_text(t.label)
						self.AlsaID.append(device)
			
			combobox.connect("changed", self.OnSelected, instr)
			row.pack_start(combobox, False, False)
			row.pack_start(image, False, False)
			row.pack_start(label, False, False)
			
			self.vbox.add(row)
			
	def OnSelected(self, widget, instr):
		'''Set the instrument's input'''
		print widget.get_active_text()
		print instr.name
		device = self.AlsaID[widget.get_active()]
		print device
		instr.input = "alsasrc device=" + device

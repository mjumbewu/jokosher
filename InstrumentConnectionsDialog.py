
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
		
		self.res = gtk.glade.XML(parent.GLADE_PATH, "InstrumentConnectionsDialog")

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
		self.mixers = {}
	
		for device in AlsaDevices.GetAlsaList("capture").values():

			#Don't want the default device twice (once as 'default' and once as its actual hw ref)
			if device == "default":
				continue

			mixer = gst.element_factory_make('alsamixer')
			mixer.set_property("device", device)
			mixer.set_state(gst.STATE_READY)

			if not mixer.implements_interface(gst.interfaces.Mixer):
				print 'Cannot get mixer tracks from the device. Check permissions on the mixer device.'
			else:
				self.mixers[device] = mixer.list_tracks()
			
			mixer.set_state(gst.STATE_NULL)
		
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
			for device in self.mixers:
				mixertracks = self.mixers[device]
				for t in mixertracks:
					if t.flags & gst.interfaces.MIXER_TRACK_INPUT:
						combobox.append_text(t.label)
						if instr.inTrack and instr.input == device and t.label == instr.inTrack:
							combobox.set_active(currentItem)
						self.AlsaID.append(device)
						currentItem += 1
			
			combobox.connect("changed", self.OnSelected, instr)
			row.pack_start(combobox, False, False)
			row.pack_start(image, False, False)
			row.pack_start(label, False, False)
			
			self.vbox.add(row)
			
	def OnSelected(self, widget, instr):
		'''Set the instrument's input'''
		device = self.AlsaID[widget.get_active()]
		mixertracks = self.mixers[device]
		for track in mixertracks:
			if track.label == widget.get_active_text():
				inTrack = track.label
		print inTrack
		if device != instr.input or inTrack != instr.inTrack:
			instr.input = device
			instr.inTrack = inTrack
			self.project.unsavedChanges = True

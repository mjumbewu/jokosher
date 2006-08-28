#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	AddInstrumentDialog.py
#	
#	This module handles the dialog for adding instruments to a project. Don't
#	you just love instruments. We do. In fact, I suspect Laszlo has printed a
#	picture of the dialog box out and sleeps next to it.
#
#-------------------------------------------------------------------------------

import gtk
import gtk.glade
import os
import Globals

#=========================================================================

class AddInstrumentDialog:
	""" This class handles all of the processing associated with the
		Add Instrument dialog.
	"""	
	#_____________________________________________________________________

	def __init__(self, project, parent):
		self.parent = parent
		self.project = project
		
		self.res = gtk.glade.XML(Globals.GLADE_PATH, "AddInstrumentDialog")

		self.signals = {
			"on_OK_clicked" : self.OnOK,
			"on_Cancel_clicked" : self.OnCancel,
			"on_instrument_search_changed" : self.OnSearchChange,
		}
		
		self.res.signal_autoconnect(self.signals)
		
		self.dlg = self.res.get_widget("AddInstrumentDialog")
		self.tree = self.res.get_widget("Instruments")
		self.search_entry = self.res.get_widget("instrument_search")
		
		self.okbutton = self.res.get_widget("okButton")
		self.okbutton.set_sensitive(False)

		self.tree.connect("item-activated", self.OnSelected)
		self.tree.connect("selection-changed", self.OnSelectionChanged)

		self.model = gtk.ListStore(str, str, gtk.gdk.Pixbuf)
			
		for i in Globals.getCachedInstruments():
			self.model.append(i)
		
		self.tree.set_model(self.model)
			
		self.tree.set_text_column(0)
		self.tree.set_pixbuf_column(2)
		self.tree.set_orientation(gtk.ORIENTATION_VERTICAL)
		self.tree.set_selection_mode(gtk.SELECTION_MULTIPLE)
		self.tree.set_item_width(90)
		self.tree.set_size_request(72, -1)
		self.dlg.resize(350, 300)
		
		self.dlg.set_icon(self.parent.icon)
		self.dlg.set_transient_for(self.parent.window)
		
	#_____________________________________________________________________
	
	def OnSelected(self, iconview, path):
		"""An instrument is selected"""
		
		self.OnOK()

	#_____________________________________________________________________
			
	def OnOK(self, button=None):
		"""OK pushed on the dialog"""
		
		sel = self.tree.get_selected_items()
		for i in sel:
			currentItem = self.model[i[0]]
			self.project.AddInstrument(currentItem[0], currentItem[1], currentItem[2])
	
		self.parent.UpdateDisplay()
		self.parent.undo.set_sensitive(True)
		self.dlg.destroy()
		
	#_____________________________________________________________________
	
	def OnCancel(self, button):
		"""Cancel button is pressed"""
		
		self.dlg.destroy()
		
	#_____________________________________________________________________

	def OnSelectionChanged(self, button):
		"""If a new instrument icon is chosen, this method is called"""
		sel = self.tree.get_selected_items()

		if len(sel) <= 0:
			self.okbutton.set_sensitive(False)
		else:
			self.okbutton.set_sensitive(True)
			
	#_____________________________________________________________________
	
	def OnSearchChange(self, widget):
		"""A new letter is added to the search box, so update the search"""
		
		search_text = self.search_entry.get_text()
		self.model = gtk.ListStore(str, str, gtk.gdk.Pixbuf)
		
		for i in Globals.getCachedInstruments():
			if search_text.lower() in i[0].lower():
				self.model.append(i)
		
		self.tree.set_model(self.model)
		
	#_____________________________________________________________________

#=========================================================================

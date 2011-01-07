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
import Globals
import textwrap
import gettext
_ = gettext.gettext


#=========================================================================

class AddInstrumentDialog:
	"""
	This class handles all of the processing associated with the Add Instrument dialog.
	"""
	#_____________________________________________________________________

	def __init__(self, project, parent, instr=None):
		"""
		Creates a new instance of AddInstrumentDialog.
		
		Parameters:
			project -- the Project to add instruments to.
			parent -- parent window of the AddInstrumentDialog (JokosherApp).
			instr -- if present, indicates the Instrument whose type wants to be changed.
		"""
		self.parent = parent
		self.project = project
		self.instr = instr

		self.gtk_builder = Globals.LoadGtkBuilderFilename("AddInstrumentDialog.ui")

		self.signals = {
			"on_OK_clicked" : self.OnOK,
			"on_Cancel_clicked" : self.OnCancel,
			"on_instrument_search_changed" : self.OnSearchChange,
			"on_AddInstrument_configure_event" : self.OnResize,
			"on_AddInstrument_destroy" : self.OnDestroy,
		}
		
		self.gtk_builder.connect_signals(self.signals)
		
		self.dlg = self.gtk_builder.get_object("AddInstrumentDialog")
		self.tree = self.gtk_builder.get_object("Instruments")
		self.search_entry = self.gtk_builder.get_object("instrument_search")
		self.search_entry.set_activates_default(True)
		self.okbutton = self.gtk_builder.get_object("okButton")
		self.okbutton.set_sensitive(False)
		self.okbutton.set_flags(gtk.CAN_DEFAULT)
		self.okbutton.grab_default()
		
		if self.instr: 
			self.dlg.set_title(_("Change Instrument Type"))
			self.gtk_builder.get_object("instructions").set_text(
					  _("Choose the new instrument type for %s") % self.instr.name)
			self.okbutton.set_label("gtk-ok")

		

		self.tree.connect("item-activated", self.OnSelected)
		self.tree.connect("selection-changed", self.OnSelectionChanged)

		self.model = gtk.ListStore(str, str, gtk.gdk.Pixbuf)
			
		for instr in Globals.getCachedInstruments():
			lineList = [x.center(12) for x in textwrap.wrap(instr[0], 11)]
			newList = "\n".join(lineList)
			self.model.append((newList, instr[1], instr[2]))
		
		self.tree.set_model(self.model)
			
		self.tree.set_text_column(0)
		self.tree.set_pixbuf_column(2)
		self.tree.set_orientation(gtk.ORIENTATION_VERTICAL)
		if self.instr:
			self.tree.set_selection_mode(gtk.SELECTION_SINGLE)
		else:
			self.tree.set_selection_mode(gtk.SELECTION_MULTIPLE)
			
		self.tree.set_item_width(90)
		self.tree.set_size_request(72, -1)
				
		self.width = int(Globals.settings.general["addinstrumentwindowwidth"])
		self.height = int(Globals.settings.general["addinstrumentwindowheight"])
		self.dlg.resize(self.width, self.height)

		self.dlg.set_icon(self.parent.icon)
		self.dlg.set_transient_for(self.parent.window)
		self.dlg.show()
	#_____________________________________________________________________
	
	def OnSelected(self, iconview, path):
		"""
		Calls the OnOK method when an instrument has been selected.
		
		Parameters:
			iconview -- reserved for GTK callbacks, don't use it explicitly.
			path -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.OnOK()

	#_____________________________________________________________________
			
	def OnOK(self, button=None):
		"""
		This method is called when the ok button in the dialog has been clicked.
		It will then add the selected instrument into the main jokosher window (JokosherApp).  
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicity.
		"""
		selectedItems = self.tree.get_selected_items()
		if not self.instr:
			instrList = []
			for i in selectedItems:
				item = self.model[i[0]]
				#find the actual instrument using index 1 (the instrument type)
				#because the name has been wrapped in self.model and can't be used
				name, type, pixbuf, path = [x for x in Globals.getCachedInstruments() if x[1] == item[1]][0]
				instrList.append( (name, type) )
			
			self.project.AddInstruments(instrList)
		else:
			item = self.model[selectedItems[0][0]]
			instrItem = [x for x in Globals.getCachedInstruments() if x[1] == item[1]][0]
			self.instr.ChangeType(instrItem[1], instrItem[0])


		self.dlg.destroy()
		
	#_____________________________________________________________________
	
	def OnCancel(self, button):
		"""
		Called when the cancel button in the dialog has been clicked.
		
		Parameters:
			button -- reserved for GTK callbacks, dont't use it explicity.
		"""

		self.dlg.destroy()
		
	#_____________________________________________________________________

	def OnSelectionChanged(self, button):
		"""
		Called when a new instrument icon is chosen.
		The ok button in the dialog will appear inactive if there are no instruments selected.
		
		Parameters:
			button -- reserved for GTK callbacks, dont't use it explicity.
		"""
		sel = self.tree.get_selected_items()

		if len(sel) <= 0:
			self.okbutton.set_sensitive(False)
		else:
			self.okbutton.set_sensitive(True)
			
	#_____________________________________________________________________
	
	def OnSearchChange(self, widget):
		"""
		This method will be called when a new letter has been added to the search box.
		It will then update the search results accordingly.
		
		Parameters:
			widget -- reserved for GTK callbacks, dont't use it explicity.
		"""
		search_text = self.search_entry.get_text()
		self.model = gtk.ListStore(str, str, gtk.gdk.Pixbuf)
		
		for instr in Globals.getCachedInstruments():
			if search_text.lower() in instr[0].lower():
				self.model.append((instr[0], instr[1], instr[2]))
		
		self.tree.set_model(self.model)
		
	#_____________________________________________________________________


	def OnResize(self, widget, event):
		"""
		This method is called when the add instrument dialog is resized

		Parameters:
			widget -- GTK callback parameter.
			event -- GTK callback parameter.
			
		Returns:
			False -- continue GTK signal propagation.
		"""		

		(self.width, self.height) = widget.get_size()

		return False

	#_____________________________________________________________________

	def OnDestroy(self, widget=None, event=None):
		"""
		Called when the add instrument dialog is destroyed

		Parameters: 
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		Globals.settings.general["addinstrumentwindowwidth"] = self.width
		Globals.settings.general["addinstrumentwindowheight"] = self.height
		Globals.settings.write()
		
	#_____________________________________________________________________	



#=========================================================================

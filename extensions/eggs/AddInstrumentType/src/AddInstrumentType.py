#	AddInstrumentType.py
#	--------------------
#	This extension is for adding your own instrument types. This is more 
#	of a practical test extension than a good, complete module. For example, 
#	you can't delete instrument types from this extension. I also think
#	that this functionality should eventually be integrated into the 
#	AddInstrumentsDialog, but for now we can work with this.

import Jokosher.Extension
import gtk
import gtk.glade
import os
import pkg_resources

class AddInstrumentType:
	EXTENSION_NAME = "Add Instrument Type"
	EXTENSION_DESCRIPTION = "Adds an instrument type to jokosher"
	EXTENSION_VERSION = "0.0.1"
	
	def OnOk(self, arg):
		name = self.instrument_name.get_text()
		type = self.instrument_name.get_text().lower().replace(" ", "")
		error = self.API.create_new_instrument_type(name, type, self.filechooser.get_filename())
		if error == 1:
			message = "That name is already in use. Please choose another one."
		elif error == 2:
			message = "Unable to load image file. Please choose a different one."
		elif error == 3:
			message = "Write error; unable to save instrument."
		else:
			self.window.destroy()
			return
		
		dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, 
							gtk.BUTTONS_CLOSE, message)
		dlg.run()
		dlg.destroy()	
		
	def OnCancel(self, arg):
		self.window.destroy()
	
	def OnMenuItemClick(self, arg):
		xmlString = pkg_resources.resource_string(__name__,"AddInstrumentType.glade")
		wTree = gtk.glade.xml_new_from_buffer(xmlString, len(xmlString),"NewInstrumentTypeDialog")
		
		signals = {
			"on_OK_clicked" : self.OnOk,
			"on_Cancel_clicked" : self.OnCancel
		}
		wTree.signal_autoconnect(signals)
	
		self.window = wTree.get_widget("NewInstrumentTypeDialog")
		self.filechooser = wTree.get_widget("filechooserbutton1")
		self.instrument_name = wTree.get_widget("entry1")
	
		filter = gtk.FileFilter()
		filter.add_pixbuf_formats()
		filter.set_name("Images")
		
		self.filechooser.add_filter(filter)
	
		self.window.show_all()
	
	def startup(self, api):
		self.API = api
		self.menu_item = self.API.add_menu_item("Add Instrument Type", self.OnMenuItemClick)

	def shutdown(self):
		self.menu_item.destroy()

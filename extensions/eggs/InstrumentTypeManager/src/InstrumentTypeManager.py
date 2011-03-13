#	AddInstrumentType.py
#	--------------------
#	This extension is for adding your own instrument types. This is more 
#	of a practical test extension than a good, complete module. For example, 
#	you can't delete instrument types from this extension. I also think
#	that this functionality should eventually be integrated into the 
#	AddInstrumentsDialog, but for now we can work with this.

import Jokosher.Extension
import gtk
import os
import pkg_resources

class InstrumentTypeManager:
	EXTENSION_NAME = "Instrument Type Manager"
	EXTENSION_DESCRIPTION = "Adds or deletes an instrument type from jokosher"
	EXTENSION_VERSION = "0.11"
	
	def OnOk(self, arg):
		self.OnApply()
		self.window.destroy()
				
	def OnInstrumentChanged(self, widget = None):
		self.selection = self.instrument_name.get_active_iter()
		if self.selection:
			self.imagePath = self.model.get_value(self.selection, 2)
			self.image.set_from_file(self.imagePath)
			self.icon.set_image(self.image)
			self.filechooser.set_filename(self.imagePath)
	
	def OnIconClicked(self, widget = None):
		response = self.filechooser.run()
		if response == gtk.RESPONSE_OK:
			self.imagePath = self.filechooser.get_filename()
			self.image.set_from_file(self.imagePath)
			self.icon.set_image(self.image)
		self.filechooser.hide()
				
	def OnApply(self, widget = None):
		name = self.instrument_name.child.get_text()
		if self.changes_flag == "new":
			type = self.instrument_name.child.get_text().lower().replace(" ", "")
			
			# add to the model
			self.model.append([name, type, self.imagePath])
			
			# add instrument
			error = self.API.create_new_instrument_type(name, type, self.imagePath)
			if error == 1:
				message = "That name is already in use. Please choose another one."
			elif error == 2:
				message = "Unable to load image file. Please choose a different one."
			elif error == 3:
				message = "Write error; unable to save instrument."
			else:
				return
		
			dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, 
								gtk.BUTTONS_CLOSE, message)
			dlg.run()
			dlg.destroy()

			self.instrument_name.child.set_property("editable", False)
			self.icon_button.set_property("sensitive", False)

			self.changes_flag = None
	
	def OnAdd(self, widget = None):
		self.instrument_name.child.set_text("New Instrument")
		self.image.clear()
		self.instrument_name.child.set_property("editable", True)
		self.icon_button.set_property("sensitive", True)
		self.changes_flag = "new"
		
	
	def OnRemove(self, widget = None):
		confirm_message = "Do you really want to remove this instrument?"
		confirm_dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, 
								gtk.BUTTONS_YES_NO, confirm_message)
		response = confirm_dlg.run()
		if response == gtk.RESPONSE_YES:
			type = self.model.get_value(self.selection, 1)
			error = self.API.delete_instrument_type(type)
			if error:
				confirm_dlg.destroy()
				if error == 1:
					error_message = "This is a default instrument. You cannot delete default instruments."
				elif error == 2:
					error_message = "Instrument files could not be deleted"	
				elif error == 3:
					error_message = "Instrument could not be removed from cache"
				
				error_dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, 
									gtk.BUTTONS_CLOSE, error_message)
				error_dlg.run()
				error_dlg.destroy()
				return
				
			self.model.remove(self.selection)
			self.instrument_name.set_active(0)
			confirm_dlg.destroy()
		else:
			confirm_dlg.destroy()
		
	def OnMenuItemClick(self, arg):
		xmlString = pkg_resources.resource_string(__name__,"InstrumentTypeManager.ui")
		self.gtkBuilder = gtk.Builder()
		self.gtkBuilder.add_from_string(xmlString)
		
		signals = {
			"on_OK_clicked" : self.OnOk,
			"on_Apply_clicked" : self.OnApply,
			"on_Add_clicked": self.OnAdd,
			"on_Remove_clicked": self.OnRemove,
			"on_Instrument_changed": self.OnInstrumentChanged,
			"on_Icon_clicked": self.OnIconClicked,
		}
		self.gtkBuilder.connect_signals(signals)
	
		self.window = self.gtkBuilder.get_object("NewInstrumentTypeDialog")
		self.API.set_window_icon(self.window)
		self.icon = self.gtkBuilder.get_object("button3")
		self.instrument_name = self.gtkBuilder.get_object("comboboxentry1")
		self.icon_button = self.gtkBuilder.get_object("button3")

		self.instrument_name.child.set_property("editable", False)
	
		self.filechooser = gtk.FileChooserDialog((_('Choose an Icon')), None, 
				gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		self.filechooser.set_default_response(gtk.RESPONSE_OK)
		
		fileFilter = gtk.FileFilter()
		fileFilter.add_pixbuf_formats()
		fileFilter.set_name("Images")
		
		self.filechooser.add_filter(fileFilter)
		
		self.changes_flag = None
	
		self.image = gtk.Image()
		
		self.imagePath = None
		
		self.window.show_all()
		
		self.model = gtk.ListStore(str, str, str)
		for instrument in self.API.list_available_instrument_types():
			self.model.append([instrument[0], instrument[1], instrument[3]])
		self.instrument_name.set_model(self.model)
		self.instrument_name.set_text_column(0)
		self.selection = self.model.get_iter_first()
		self.instrument_name.set_active(0)
		
					
	def startup(self, api):
		self.API = api
		self.menu_item = self.API.add_menu_item("Instrument Type Manager", self.OnMenuItemClick)
		
	def shutdown(self):
		self.menu_item.destroy()

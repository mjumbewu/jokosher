#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	This module shows the Extensions Manager dialog which is used to add, remove
#	and configure Jokosher's Extensions.
#
#-------------------------------------------------------------------------------

import gtk, pango
import Globals, Extension
import gettext
import os
_ = gettext.gettext

class ExtensionManagerDialog:
	"""
	This module shows the Extensions Manager dialog which is used to add, remove
	and configure Jokosher's Extensions.
	"""
	def __init__(self, parent):
		"""
		Creates a new instance of ExtensionManagerDialog.
		
		Parameters:
			parent -- the parent MainApp Jokosher window.
		"""
		self.parent = parent
		
		self.gtk_builder = Globals.LoadGtkBuilderFilename("ExtensionManagerDialog.ui")
		
		signals = {
			"on_Close_clicked" : self.OnClose,
			"on_Add_clicked" : self.OnAdd,
			"on_Remove_clicked": self.OnRemove,
			"on_Treeview_selected": self.OnSelect,
			"on_Preferences_clicked": self.OnPreferences
		}
		self.gtk_builder.connect_signals(signals)
		
		self.dlg = self.gtk_builder.get_object("ExtensionManagerDialog")
		self.tree = self.gtk_builder.get_object("treeviewExtensions")
		self.eb = self.gtk_builder.get_object("descriptionEventBox")
		self.description = self.gtk_builder.get_object("ExtensionDescription")
		self.prefs_button = self.gtk_builder.get_object("buttonPreferences")
		
		self.AddColumn("Enabled", 0, 'toggle')
		self.AddColumn("Name", 1, 'text', 30)
		self.AddColumn("Version", 3, 'text', 7)

		self.model = gtk.ListStore(bool, str, str, str, str, bool)
		self.tree.set_model(self.model)

		for extension in self.parent.extensionManager.GetExtensions():
			self.model.append((extension["enabled"], extension["name"], extension["description"], extension["version"], extension["filename"], extension["preferences"]))


		self.dlg.set_transient_for(self.parent.window)
		self.dlg.show()
	
	#_____________________________________________________________________

	def OnClose(self, button):
		"""
		Destroys the dialog when the close button is pressed.
		It also saves the Extensions's settings.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.dlg.destroy()
		Globals.settings.write()
	#_____________________________________________________________________

	def AddColumn(self, title, modelId, cell_renderer='text', cell_width=20):
		"""
		Adds a display column to the ExtensionManager dialog.
		
		Parameters:
			title -- title of the column.
			modelId -- index of the column within the TreeView model.
			cell_renderer -- type of render to use:
							'text' = renders text into the TreeView.
							'toggle' = renders toggle buttons into the TreeView.
			cell_width -- width in pixels of the column.
		"""
		if cell_renderer == 'toggle':
			renderer = gtk.CellRendererToggle()
			renderer.set_property('activatable', True)
			column = gtk.TreeViewColumn(title, renderer, active=modelId)
			renderer.connect('toggled', self.ToggleEnabled)
		
		else:
			renderer = gtk.CellRendererText()
			renderer.set_property('ellipsize', pango.ELLIPSIZE_END)
			renderer.set_property('ellipsize-set', True)
			renderer.set_property('width-chars', cell_width)
			column = gtk.TreeViewColumn(title, renderer, text=modelId)
			column.set_property('resizable', True)

		self.tree.append_column(column)
	
	#_____________________________________________________________________

	def ToggleEnabled(self, cell, path):
		"""
		Enables/disables an Extension.
		
		Parameters:
			cell -- reserved for GTK callbacks, don't use it explicitly.
			path -- path to the Extension.
		"""
		self.model[path][0] = not self.model[path][0]
		
		iter = self.model.get_iter(path)
		name = self.model.get_value(iter, 1)
		filename = self.model.get_value(iter, 4)
		
		if self.model[path][0]:
			if name in Globals.settings.extensions['extensions_blacklist']:
				Globals.settings.extensions['extensions_blacklist'] = Globals.settings.extensions['extensions_blacklist'].replace(name, "")
				Globals.debug("extension-blacklist:", Globals.settings.extensions['extensions_blacklist'])
				for extension in self.parent.extensionManager.GetExtensions():
					if filename == extension['filename']:
						extension['enabled'] = True

				self.parent.extensionManager.StartExtension(filename)
		else:
			if name not in Globals.settings.extensions['extensions_blacklist']:
				Globals.settings.extensions['extensions_blacklist'] += name+" "
				self.parent.extensionManager.StopExtension(filename)
				
				for extension in self.parent.extensionManager.GetExtensions():
					if filename == extension['filename']:
						extension['enabled'] = False
	#_____________________________________________________________________

	def OnSelect(self, tree):
		"""
		When an Extension is selected, enables/disables the preferences button
		according to the reported Extension capabilities and updates the
		description label.
		
		Parameters:
			tree -- GTKTreeView holding the Extensions's representation.
		"""
		descr_text = ""
		selection = self.tree.get_selection().get_selected()[1]
		if selection:
			preferences = self.model.get_value(selection, 5)
			if preferences:
				self.prefs_button.set_sensitive(True)
			else:
				self.prefs_button.set_sensitive(False)
		
			descr_text = self.model.get_value(selection, 2)
		self.description.set_text(descr_text)
	#_____________________________________________________________________
	
	def OnAdd(self, button):
		"""
		Displays a dialog which allows the user to add an external Extension.
		If an error occurs, an error dialog is displayed.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		chooser = gtk.FileChooserDialog((_('Choose a Jokosher Extension file')), None, 
				gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		chooser.set_default_response(gtk.RESPONSE_OK)
		chooser.set_transient_for(self.dlg)

		filter = gtk.FileFilter()
		filter.set_name(_("Jokosher Extension Files (*.py *.egg)"))
		filter.add_pattern("*.py")
		filter.add_pattern("*.egg")

		chooser.add_filter(filter)

		response = chooser.run()
			
		if response == gtk.RESPONSE_OK:
			install_dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, 
					gtk.BUTTONS_YES_NO, "Install extension to local jokosher extension directory?")
			install_response = install_dlg.run()
			
			if install_response == gtk.RESPONSE_YES:
				filename = chooser.get_filename()
				#TODO: redo the enable/disable stuff here
				
				if not self.parent.extensionManager.LoadExtensionFromFile(os.path.basename(filename), os.path.dirname(filename), local=True):
					dlg = gtk.MessageDialog(self.dlg,
						gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
						gtk.MESSAGE_ERROR,
						gtk.BUTTONS_CLOSE,
						_("There was a problem loading the extension"))
					dlg.run()
					dlg.destroy()
				self.UpdateModel()
				chooser.destroy()
			
			else:
				install_dlg.destroy()
			install_dlg.destroy()	
								
		chooser.destroy()
	
	#_____________________________________________________________________

	def OnRemove(self, button):
		"""
		Removes an Extension from the Extensions list.
		If an error occurs, an error dialog is displayed.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		selection = self.tree.get_selection()
		row_selected = selection.get_selected()[1]
		filename = self.model.get_value(row_selected, 4)
		
		if row_selected:
			if Extension.EXTENSION_DIR_USER in filename:
				dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, 
						gtk.BUTTONS_YES_NO, "Remove the selected extension?")
				response = dlg.run()
				if response == gtk.RESPONSE_YES:
					dlg.destroy()
					if not self.parent.extensionManager.RemoveExtension(filename): #don't forget to change to RemoveExtenion() in ExtensionManager
						dlg2 = gtk.MessageDialog(self.dlg,
							gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
							gtk.MESSAGE_ERROR,
							gtk.BUTTONS_CLOSE,
							_("There was a problem removing the extension"))
						dlg2.run()
						dlg2.destroy()
						
					self.UpdateModel()
				
				dlg.destroy()

			else:
				dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
						gtk.BUTTONS_OK, "This extension was installed by your system. You cannot remove it.")
				dlg.run()
				dlg.destroy()
		else:
			dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR,
					gtk.BUTTONS_OK, "No extension selected!")
			dlg.run()
			dlg.destroy()

	#_____________________________________________________________________

	def OnPreferences(self, button):
		"""
		Displays the Extension's preferences dialog.
		If an error occurs, an error dialog is displayed.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		selection = self.tree.get_selection().get_selected()[1]
		filename = self.model.get_value(selection, 4)

		if not self.parent.extensionManager.ExtensionPreferences(filename):
			dlg = gtk.MessageDialog(self.dlg,
							gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
							gtk.MESSAGE_ERROR,
							gtk.BUTTONS_CLOSE,
							_("An error occurred when trying to launch the preferences for the extension"))
			dlg.run()
			dlg.destroy()

	#_____________________________________________________________________

	def UpdateModel(self):
		"""
		Updates the ExtensionManagerDialog Extension list, to reflect changes
		in the currently available Extensions.
		"""
		selection = self.tree.get_selection()
		row_selected = selection.get_selected()[1]
		
		num_extensions = len(self.parent.extensionManager.loadedExtensions)
		num_model = len(self.model)
		
		if num_model < num_extensions:
			extension = self.parent.extensionManager.loadedExtensions[num_extensions-1]
			self.model.append((extension["enabled"], extension["name"], extension["description"], extension["version"], extension["filename"], extension["preferences"]))
		
		elif num_model > num_extensions:
			self.model.remove(row_selected)

	#_____________________________________________________________________

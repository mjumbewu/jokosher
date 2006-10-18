import gtk.glade
import Globals
import os,shutil
import gettext
_ = gettext.gettext

class ExtensionManagerDialog:
	def __init__(self, parent):
		self.parent = parent
		
		self.wTree = gtk.glade.XML(Globals.GLADE_PATH, "ExtensionManagerDialog")
		
		signals = {
			"on_Close_clicked" : self.OnClose,
			"on_Add_clicked" : self.OnAdd,
			#"on_Remove_clicked": self.OnRemove
		}
		self.wTree.signal_autoconnect(signals)
		
		self.dlg = self.wTree.get_widget("ExtensionManagerDialog")
		self.tree = self.wTree.get_widget("treeview1")
		self.restart_label = self.wTree.get_widget("label1")
		
		self.AddColumn("Enabled", 0, 'toggle')
		self.AddColumn("Name", 1)
		self.AddColumn("Description", 2)
		self.AddColumn("Version", 3)

		self.model = gtk.ListStore(bool, str, str, str)
		self.tree.set_model(self.model)

		for extension in parent.extensionManager.GetExtensions():
			self.model.append((extension["enabled"], extension["name"], extension["description"], extension["version"]))

		self.dlg.set_transient_for(self.parent.window)
		self.dlg.show()
	
	def OnClose(self, button):
		self.dlg.destroy()

	def AddColumn(self, title, modelId, cell_renderer='text'):
		if cell_renderer == 'toggle':
			renderer = gtk.CellRendererToggle()
			renderer.set_property('activatable', True)
			column = gtk.TreeViewColumn(title, renderer, active=modelId)
			renderer.connect('toggled', self.ToggleEnabled)
		else:
			column = gtk.TreeViewColumn(title, gtk.CellRendererText(), text=modelId)
		self.tree.append_column(column)
	
	def ToggleEnabled(self, cell, path):
		self.model[path][0] = not self.model[path][0]
		self.restart_label.set_property('visible', self.restart_label.get_property('visible'))
	
	def OnAdd(self, button):
		chooser = gtk.FileChooserDialog((_('Choose a Jokosher Extension file')), None, gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		chooser.set_default_response(gtk.RESPONSE_OK)
		chooser.set_transient_for(self.dlg)

		filter = gtk.FileFilter()
		filter.set_name(_("Jokosher Extension Files (*.py *.egg)"))
		filter.add_pattern("*.py")
		filter.add_pattern("*.egg")

		chooser.add_filter(filter)

		while True:
			response = chooser.run()
			
			if response == gtk.RESPONSE_OK:
				install_dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, 
							gtk.BUTTONS_YES_NO, "Install extension to local jokosher extension directory?")
				install_response = install_dlg.run()
				
				if install_response == gtk.RESPONSE_YES:
					filename = chooser.get_filename()
					shutil.copy(filename, os.path.expanduser("~/.jokosher/extensions/")+os.path.basename(filename))
					chooser.destroy()
				else:
					install_dlg.destroy()
				install_dlg.destroy()	
								
			elif response == gtk.RESPONSE_CANCEL or response == gtk.RESPONSE_DELETE_EVENT:
				break

		chooser.destroy()

	
	#def OnRemove(self, button):
		#indented for interpreter		

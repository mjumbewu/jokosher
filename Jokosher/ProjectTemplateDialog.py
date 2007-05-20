#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	ProjectTemplateDialog.py
#	
#	This module is used to present a dialog which allows the user to create, modify and
#	remove project templates.
#
#-------------------------------------------------------------------------------

import gtk
import gtk.glade
import Globals
import ProjectTemplate
import gettext
_ = gettext.gettext

#=========================================================================

class ProjectTemplateDialog:
	"""
	This class allows the user to modify, save and delete project templates.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, newprojectdlg, template):
		""" 
		Creates a new instance of ProjectTemplateDialog.
		
		Parameters:
			newprojectdlg -- reference to NewProjectDialog.
			template -- reference to ProjectTemplate.
		"""
		self.newprojectdlg = newprojectdlg
		self.template = template

		self.wTree = gtk.glade.XML(Globals.GLADE_PATH, "ProjectTemplateDialog")
		

		signals = {
			"on_save_button_clicked" : self.OnSaveButtonClicked,
			"on_delete_button_clicked" : self.OnDeleteButtonClicked,
			"on_add_button_clicked" : self.OnAddButtonClicked,
			"on_remove_button_clicked": self.OnRemoveButtonClicked,
			"on_close_button_clicked" : self.OnCloseButtonClicked,
		}
		self.wTree.signal_autoconnect(signals)
		
		self.window = self.wTree.get_widget("ProjectTemplateDialog")
		self.window.set_transient_for(self.newprojectdlg.dlg)
		self.window.set_icon(self.newprojectdlg.dlg.get_icon())
		
		self.tempcombo = self.wTree.get_widget("template_comboentry")
		self.tempcombo.child.set_activates_default(True)
		
		self.instrtree = self.wTree.get_widget("instrument_treeview")
		self.addinstrbtn = self.wTree.get_widget("add_button")
		self.removetempinstr = self.wTree.get_widget("remove_button")
		self.temptree = self.wTree.get_widget("template_treeview")
		
		self.savebtn = self.wTree.get_widget("save_button")
		self.savebtn.set_flags(gtk.CAN_DEFAULT)
		self.savebtn.grab_default()
		self.deletebtn = self.wTree.get_widget("delete_button")
		
		self.temptreemodel = gtk.ListStore(gtk.gdk.Pixbuf, str, str)
		self.instrtreemodel = gtk.ListStore(gtk.gdk.Pixbuf, str, str)
		
		# the template combo entry uses the same model as the template combo in new project dialog
		self.tempcombo.set_model(self.newprojectdlg.templatemodel)
		self.instrtree.set_model(self.instrtreemodel)		
		self.temptree.set_model(self.temptreemodel)
		
		self.tempcombo.clear()
		textrend = gtk.CellRendererText()
		self.tempcombo.pack_start(textrend)
		self.tempcombo.add_attribute(textrend, "text", 0)
		
		self.instrtree.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
		self.instrtree.append_column(gtk.TreeViewColumn(_("Type"), gtk.CellRendererPixbuf(), pixbuf=0))
		self.instrtree.append_column(gtk.TreeViewColumn(_("Instrument Name"), gtk.CellRendererText(), text=2))
		
		self.temptree.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
		self.temptree.append_column(gtk.TreeViewColumn(_("Type"), gtk.CellRendererPixbuf(), pixbuf=0))
		self.temptree.append_column(gtk.TreeViewColumn(_("Instrument Name"), gtk.CellRendererText(), text=2))
		
		self.tempcombo.connect("changed", self.OnTemplateEntryChanged)

		self.PopulateJokosherInstrumentsModel()
		self.tempcombo.set_active(self.newprojectdlg.templatecombo.get_active())
		self.template.connect("template-update", self.OnTemplateUpdate)
		self.window.show_all()
		
	#_____________________________________________________________________		
		
	def OnTemplateEntryChanged(self, widget):
		"""
		Called when the template combo entry contents change.
			
		Parameters:
			widget -- reserved for GTK callbacks. Don't use explicitly.
		"""
		if self.tempcombo.child.get_text():
			self.savebtn.set_sensitive(True)
			self.deletebtn.set_sensitive(True)
			self.Update()
		else:
			self.savebtn.set_sensitive(False)
			self.deletebtn.set_sensitive(False)
			
	#_____________________________________________________________________
	
	def Update(self):
		"""
		Called when the template combo entry contents change.
		Loads instruments from a template file and appends them to the template instruments model.
		"""
		for key, value in self.template.LoadDictionaryOfInstrumentsFromTemplateFile().iteritems():
			if key == self.tempcombo.child.get_text():
				self.temptreemodel.clear()
				for name, type, pixbuf in value:
					pixbuf = pixbuf.scale_simple(22, 22, gtk.gdk.INTERP_BILINEAR)
					self.temptreemodel.append( (pixbuf, type, name) )
				break
	
	#_____________________________________________________________________
	
	def OnAddButtonClicked(self, widget):
		"""
		Called when the add button is clicked.
		Adds selected instruments to the template instruments model.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use explicitly.
		"""
		selection = self.instrtree.get_selection()
		if selection:
			model, selected = selection.get_selected_rows()
			iters = [model.get_iter(path) for path in selected]
			for iter in iters:
				self.temptreemodel.append( (model[iter][0], model[iter][1], model[iter][2]) )
		else:
			return

	#_____________________________________________________________________
	
	def OnRemoveButtonClicked(self, widget):
		"""
		Called when the remove button is clicked.
		Removes any selected instruments from the template instruments model.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use explicitly.
		"""
		selection = self.temptree.get_selection()
		if selection:
			model, selected = selection.get_selected_rows()
			iters = [model.get_iter(path) for path in selected]
			for iter in iters:
				model.remove(iter)
		else:
			return

	#_____________________________________________________________________
	
	def OnSaveButtonClicked(self, widget):
		"""
		Called when the save button is clicked.
		Saves added template instruments to a template file.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use explicitly.
		"""
		instruments = []
		for row in self.temptreemodel:
			instruments.append(row[1])
		self.template.SaveTemplateFile(self.tempcombo.child.get_text(), instruments)
		
	#_____________________________________________________________________
			
	def OnDeleteButtonClicked(self, widget):
		"""
		Called when the delete button is clicked.
		Removes the selected template file from disk.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use explicitly.
		"""
		self.template.DeleteTemplateFile(self.tempcombo.child.get_text())

	#_____________________________________________________________________
		
	def OnCloseButtonClicked(self, widget):
		"""
		Called when the close button is clicked.
		Destroys the project templates window.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use explicitly.
		"""
		self.window.destroy()
		
	#_____________________________________________________________________
	
	def OnTemplateUpdate(self, projectTemplate):
		"""
		Callback for when the ProjectTemplate instance for this dialog
		sends a signal to update.
		
		Parameters:
			projectTemplate -- The ProjectTemplate instance that send the signal.
		"""
		self.UpdateTemplateModel()
	
	#_____________________________________________________________________
	
	def PopulateJokosherInstrumentsModel(self):
		"""
		Called when the jokosher instruments model needs to be populated.
		"""
		instrlist = [(x[0], x[1], x[2]) for x in Globals.getCachedInstruments()]
		for name, type, pixbuf in instrlist:
			pixbuf = pixbuf.scale_simple(22, 22, gtk.gdk.INTERP_BILINEAR)
			self.instrtreemodel.append( (pixbuf, type, name) )	
		
	#_____________________________________________________________________
	
	def UpdateTemplateModel(self):
		"""
		Called when the template model needs updating.
		"""
		self.newprojectdlg.templatemodel.clear()
		for item in self.template.LoadDictionaryOfInstrumentsFromTemplateFile().keys():
			self.newprojectdlg.templatemodel.append((item,))
			self.newprojectdlg.templatecombo.show_all()
			self.newprojectdlg.templatecombo.set_active(0)
		
	#_____________________________________________________________________
		
#=========================================================================

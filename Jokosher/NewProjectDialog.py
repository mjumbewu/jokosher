#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	NewDialog.py
#	
#	This module shows the New Project which is used to create a new Jokosher
#	project.
#
#-------------------------------------------------------------------------------

import gtk.glade
import os
import ProjectManager
import PlatformUtils
import Globals
import gettext
_ = gettext.gettext
import ProjectTemplate
import ProjectTemplateDialog

class NewProjectDialog:
	"""
	This module shows the New Project which is used to create a new Jokosher project.
	"""
	#_____________________________________________________________________	
	
	def __init__(self, parent):
		"""
		Creates a new instance of NewProjectDialog.
		
		The dialog is used to create a new Project based on the user's input.
		
		Parameters:
			parent -- reference to the MainApp Jokosher window.
		"""
		self.parent = parent
		
		self.res = gtk.glade.XML(Globals.GLADE_PATH, "NewProjectDialog")

		self.signals = {
			"on_OK_clicked" : self.OnOK,
			"on_Cancel_clicked" : self.OnCancel,
			"on_editbutton_clicked" : self.OnEdit,
			"on_Template_toggled" : self.TemplateCheckboxToggled
		}
		
		self.res.signal_autoconnect(self.signals)
		
		self.dlg = self.res.get_widget("NewProjectDialog")

		self.sideimage = self.res.get_widget("sideimage")
		self.sideimage.set_from_file(os.path.join(Globals.IMAGE_PATH, "newproject.png"))
		
		self.name = self.res.get_widget("name")
		self.name.set_activates_default(True)
		self.folder = self.res.get_widget("folder")
		self.author = self.res.get_widget("author")
		self.author.set_activates_default(True)
		
		self.template = ProjectTemplate.ProjectTemplate()
		self.template_checkbox = self.res.get_widget("template_checkbox")
		self.templatehbox = self.res.get_widget("template_hbox")
		self.templatehbox.set_sensitive(False)
		self.templatecombo = self.res.get_widget("template_combo")
		self.templatecombo.clear()
		
		self.templatemodel = gtk.ListStore(str)
		for files in self.template.LoadDictionaryOfInstrumentsFromTemplateFile().iterkeys():
			self.templatemodel.append((files,))
		self.templatecombo.set_model(self.templatemodel)
		
		text = gtk.CellRendererText()
		self.templatecombo.pack_start(text)
		self.templatecombo.add_attribute(text, "text", 0)
		
		self.templatecombo.set_active(0)

		# Default author to name of currently logged in user
		self.author.set_text(PlatformUtils.getFullName())
		
		self.okbutton = self.res.get_widget("okButton")
		self.okbutton.set_flags(gtk.CAN_DEFAULT)
		self.okbutton.grab_default()
		
		# Set the default folder of 'folder' (a FileChooserButton)
		if os.path.exists(Globals.settings.general["projectfolder"]):
			self.folder.set_current_folder(Globals.settings.general["projectfolder"])
		else:
			self.folder.set_current_folder(os.path.expanduser("~"))

		self.dlg.resize(350, 300)
		self.dlg.set_icon(self.parent.icon)
		self.dlg.set_transient_for(self.parent.window)

	#_____________________________________________________________________
	
	def TemplateCheckboxToggled(self, widget):
		"""
		Called when the template checkbox is activated.
		The template hbox becomes inactive if the template checkbox is activated.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly. 
		"""
		self.templatehbox.set_sensitive(self.template_checkbox.get_active())
		
	#_____________________________________________________________________	
		
	def OnOK(self, button):
		"""
		Tries to create and set a new Project with the user input name, author
		and location.
		If the process fails, a message is issued to the user stating the error.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		name = self.name.get_text()
		if not name:
			name = _("New Project")
			
		author = self.author.get_text()
		if not author:
			author = _("Unknown Author")
			
		# CreateNewProject expects a URI	
		folder = PlatformUtils.pathname2url(self.folder.get_current_folder())
		
		# Save the selected folder as the default folder
		Globals.settings.general["projectfolder"] = folder
		Globals.settings.write()
		if not folder:
			folder = "~"

		try:
			project = ProjectManager.CreateNewProject(folder, name, author)
		except ProjectManager.CreateProjectError, e:
			if e.errno == 1:
				message = _("Could not initialize project.")
			elif e.errno == 2:
				message = _("A file or folder with this name already exists. Please choose a different project name and try again.")
			elif e.errno == 3:
				message = _("The file or folder location is write-protected.")
			elif e.errno == 4:
				message = _("Invalid name or author.")
			elif e.errno == 5:
				message = _("The URI scheme given is either invalid or not supported")
			elif e.errno == 6:
				message = "%s %s" % (_("Unable to load required Gstreamer plugin:"), e.message)
			
			# show the error dialog with the relavent error message	
			dlg = gtk.MessageDialog(self.dlg,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_ERROR,
				gtk.BUTTONS_OK,
				_("Unable to create project.\n\n%s") % message)
			dlg.run()
			dlg.destroy()
		else:
			self.AddTemplateToProject(project)
			self.parent.SetProject(project)
			self.dlg.destroy()
		
	#_____________________________________________________________________	
	
	def OnCancel(self, button):
		"""
		Destroys the dialog when the cancel button is pressed.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.dlg.destroy()

	#_____________________________________________________________________
	
	def OnEdit(self, button):
		"""
		Displays the ProjectTemplate dialog, allowing the user to create, delete and modify project
		templates.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		ProjectTemplateDialog.ProjectTemplateDialog(self, self.template)
		
	#_____________________________________________________________________
	
	def ReturnProjectInstrumentTuples(self, name):
		"""
		Ths method will return a tuple containing the name, type and pixbuf of the instruments in a given template file.
		
		Parameters:
			name -- the name of the template to use.
		
		Returns:
			instruments -- a list of instruments containing tuples required for project.AddInstruments()
		"""
		return self.template.LoadDictionaryOfInstrumentsFromTemplateFile()[name]
		
	#_____________________________________________________________________
	
	def AddTemplateToProject(self, project):
		"""
		Adds template instruments to the user's project.
		"""
		if self.template_checkbox.get_active():
			active = self.templatecombo.get_model()[self.templatecombo.get_active()][0]
			tuples = self.ReturnProjectInstrumentTuples(active)
			instrList = []
			for name, type, pixbuf in tuples:
				instrList.append( (name, type))
			project.AddInstruments(instrList)
	
	#_____________________________________________________________________
	
#=========================================================================

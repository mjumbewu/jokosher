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

import gtk
import gtk.glade
import gobject
import os
from ConfigParser import SafeConfigParser
import Project
import AddInstrumentDialog
import pwd
import Globals
import gettext
_ = gettext.gettext

class NewProjectDialog:
	
	#_____________________________________________________________________	
	
	def __init__(self, parent):

		self.parent = parent
		
		self.res = gtk.glade.XML(Globals.GLADE_PATH, "NewProjectDialog")

		self.signals = {
			"on_OK_clicked" : self.OnOK,
			"on_Cancel_clicked" : self.OnCancel,
		}
		
		self.res.signal_autoconnect(self.signals)
		
		self.dlg = self.res.get_widget("NewProjectDialog")

		self.sideimage = self.res.get_widget("sideimage")
		self.sideimage.set_from_file(os.path.join(Globals.IMAGE_PATH, "newproject.png"))
		
		self.name = self.res.get_widget("name")
		self.folder = self.res.get_widget("folder")
		self.author = self.res.get_widget("author")
		
		# Default author to name of currently logged in user
		try:
			# Try to get the full name if it exists
			fullname = pwd.getpwuid(os.getuid())[4].split(",")[0]
			if fullname == "":
				fullname = pwd.getpwuid(os.getuid())[0]
			self.author.set_text(fullname)
		except:
			# If we can't get the fullname, then just use the login
			self.author.set_text(pwd.getpwuid(os.getuid())[0])
		
		self.okbutton = self.res.get_widget("okButton")

		self.dlg.resize(350, 300)
		self.dlg.set_icon(self.parent.icon)
		self.dlg.set_transient_for(self.parent.window)
	
	#_____________________________________________________________________	
		
	def OnOK(self, button):
		"""OK button has been pressed."""
		name = self.name.get_text()
		if not name:
			name = _("New Project")
			
		author = self.author.get_text()
		if not author:
			author = _("Unknown Author")
			
		folder = self.folder.get_current_folder()
		if not folder:
			folder = "~"
		
		try:
			project=Project.CreateNew(folder,name, author)
		except Project.CreateProjectError, e:
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
			
			# show the error dialog with the relavent error message	
			dlg = gtk.MessageDialog(self.dlg,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_ERROR,
				gtk.BUTTONS_OK,
				_("Unable to create project.\n\n%s") % message)
			dlg.run()
			dlg.destroy()
		else:
			self.parent.SetProject(project)
			self.dlg.destroy()
		
	#_____________________________________________________________________	
	
	def OnCancel(self, button):
		"""Cancel button is pressed."""
		self.dlg.destroy()

	#_____________________________________________________________________	

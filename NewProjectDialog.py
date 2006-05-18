
import gtk
import gtk.glade
import gobject
import os
import re
from ConfigParser import SafeConfigParser
import Project
import AddInstrumentDialog
import pwd

class NewProjectDialog:
	
	#_____________________________________________________________________	
	
	def __init__(self, parent):

		self.parent = parent
		
		self.res = gtk.glade.XML ("Jokosher.glade", "NewProjectDialog")

		self.signals = {
			"on_OK_clicked" : self.OnOK,
			"on_Cancel_clicked" : self.OnCancel,
		}
		
		self.res.signal_autoconnect(self.signals)
		
		self.dlg = self.res.get_widget("NewProjectDialog")

		self.sideimage = self.res.get_widget("sideimage")
		self.sideimage.set_from_file("images/newproject.png")
		
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
		name = self.name.get_text()
		delimname = re.sub(' ', '_', name)
		filename = (delimname + ".jok")
		projectdir = os.path.join(self.folder.get_current_folder(), delimname)
		
		if os.path.exists(projectdir):
			dlg = gtk.MessageDialog(self.dlg,
					gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
					gtk.MESSAGE_QUESTION,
					gtk.BUTTONS_YES_NO,
					"A folder with that name already exists.\n" +
					"Are you sure you want to overwrite it?")
			response = dlg.run()
			if response == gtk.RESPONSE_NO:
				dlg.destroy()
				return
			elif response == gtk.RESPONSE_YES:
				dlg.destroy()
		else:
			os.mkdir(projectdir)
			
		audio_dir = os.path.join(projectdir, "audio")
		if not os.path.exists(audio_dir):
			os.mkdir(audio_dir)

		project = Project.Project()
		project.name = name
		project.author = self.author.get_text()
		project.startTransportThread()
	
		# remember that projectfile contains the path
		project.projectfile = os.path.join(projectdir, filename)
		project.saveProjectFile(project.projectfile)
		
		self.parent.SetProject(project)
			
		self.dlg.destroy()
		
	#_____________________________________________________________________	
				
	def OnCancel(self, button):
		self.dlg.destroy()

	#_____________________________________________________________________	

#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	WelcomeDialog.py
#	
#	This class displays the welcome dialog when the application starts.
#
#-------------------------------------------------------------------------------

import gtk.glade
import os
import Globals
import PreferencesDialog

#=========================================================================

class WelcomeDialog:
	"""
	This class handles all of the processing associated with the
	Welcome Dialog (which comes up on start).
	"""	
	#_____________________________________________________________________

	def __init__(self, mainwindow):
		"""
		Creates a new instance of MainApp.
		
		Parameters:
			mainwindow -- instance of JokosherApp. Used for parent/child relationship.
		"""

		# this points to JokosherApp		
		self.mainwindow = mainwindow
				
		self.res = gtk.glade.XML(Globals.GLADE_PATH, "WelcomeDialog")

		self.signals = {
			"on_newproject_clicked" : self.OnNewProject,
			"on_openproject_clicked" : self.OnOpenProject,
			"on_preferences_clicked" : self.OnPreferences,
			"on_openrecentprojectbutton_clicked" : self.OnOpenRecentProjectButton,
			"on_quit_clicked" : self.OnQuit,
			"on_startupcb_toggled" : self.OnStartupToggled,
		}
		
		self.res.signal_autoconnect(self.signals)

		self.window = self.res.get_widget("WelcomeDialog")
		self.window.set_icon(self.mainwindow.icon)
		self.window.set_transient_for(self.mainwindow.window)
		
		self.tree = self.res.get_widget("recentprojectslist")
		self.headerimage = self.res.get_widget("headerimage")
		self.headerimage.set_from_file(os.path.join(Globals.IMAGE_PATH, "welcomeheader.png"))

		self.openrecentbutton = self.res.get_widget("openrecentprojectbutton")
		self.openrecentbutton.set_sensitive(False)

		# set up recent projects treeview with a ListStore model. We also
		# use CellRenderPixbuf as we are using icons for each entry
		self.model = gtk.ListStore(str, str, str)
		self.PopulateRecentProjects()
		self.tree.set_model(self.model)
		self.tvcolumn = gtk.TreeViewColumn('Recent Projects')
		self.cellpb = gtk.CellRendererPixbuf()
		self.cell = gtk.CellRendererText()
		
		self.tvcolumn.pack_start(self.cellpb, False)
		self.tvcolumn.pack_start(self.cell, True)
		
		self.tvcolumn.set_attributes(self.cellpb, stock_id=0)
		self.tvcolumn.set_attributes(self.cell, text=1)
		
		self.tree.append_column(self.tvcolumn)

		self.tree.connect("row-activated", self.OnRecentProjectSelected)
		self.tree.connect("cursor-changed", self.OnEnableRecentProjectButton)
		
		self.window.show_all()

	#_____________________________________________________________________
	
	def OnNewProject(self, widget):
		"""
		Starts a new project.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		# hide the welcome dialog and call OnNewProject() from JokosherApp
		self.window.hide()
		self.mainwindow.OnNewProject(self, self.OnDialogClose)
	
	#_____________________________________________________________________
			
	def OnOpenProject(self, button=None):
		"""
		Opens an existing project.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""

		# hide the welcome dialog and call OnOpenProject() from JokosherApp		
		self.window.hide()
		self.mainwindow.OnOpenProject(self, self.OnDialogClose)
		
	#_____________________________________________________________________
	
	def OnPreferences(self, button):
		"""
		Shows the preferences window.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""

		# hide the welcome dislog and call OnPreferences() from JokosherApp		
		self.window.hide()
		self.mainwindow.OnPreferences(self, self.OnDialogClose)
		
	#_____________________________________________________________________

	def OnDialogClose(self, dialog=None):
		"""
		The dialog was closed.
		
		Parameters:
			dialog -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		if self.mainwindow.project:
			self.window.destroy()
		else:
			self.window.show_all()
		
	#_____________________________________________________________________

	def OnQuit(self, button):
		"""
		Quits Jokosher.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		gtk.main_quit()

	#_____________________________________________________________________

	def PopulateRecentProjects(self):
		"""
		Populate the Recent Projects menu with items from global settings.
		"""
		self.model.clear()
		for path, name in self.mainwindow.recentprojectitems:	
			self.model.append([gtk.STOCK_NEW, name, path])
	
	#_____________________________________________________________________

	def OnRecentProjectSelected(self, treeview, path, view_column):
		"""
		This method is called when one of the entries in the recent projects
		list is selected.
		
		Parameters:
			treeview -- reserved for GTK callbacks, don't use it explicitly.
			path -- path to the project file.
			view_column -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		item = self.model[path]
		response = self.mainwindow.OnRecentProjectsItem(self, item[2], item[1])
		if response:
			#it opened without error, so close our window
			self.window.destroy()
		
	#_____________________________________________________________________

	def OnEnableRecentProjectButton(self, treeview):
		"""
		When a recent project is selected, enable the button to load it.
		
		Parameters:
			treeview -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		self.openrecentbutton.set_sensitive(True)
		
	#_____________________________________________________________________

	def OnOpenRecentProjectButton(self, widget):
		"""
		Loads the selected recent project.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		item = self.model[self.tree.get_cursor()[0]]
		self.mainwindow.OnRecentProjectsItem(self, item[2], item[1])
		self.window.destroy()
	
	#_____________________________________________________________________

	def OnStartupToggled(self, widget):
		"""
		When the startup toggle box is toggled, this method is run to update
		the setting in Globals.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		if widget.get_active():
			Globals.settings.general["startupaction"] = PreferencesDialog.STARTUP_NOTHING
		else:	
			Globals.settings.general["startupaction"] = PreferencesDialog.STARTUP_WELCOME_DIALOG
		
		Globals.settings.write()
	
	#_____________________________________________________________________
#=========================================================================

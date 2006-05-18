
import gtk
import gtk.glade
import gobject
import os
import sys
from ConfigParser import SafeConfigParser
import Globals
import Project
import PreferencesDialog
import xml.dom.minidom as xml

#=========================================================================

class WelcomeDialog:
	""" This class handles all of the processing associated with the
		Welcome Dialog (which comes up on start).
	"""	
	#_____________________________________________________________________

	def __init__(self, mainwindow):
				
		self.mainwindow = mainwindow
				
		self.res = gtk.glade.XML ("Jokosher.glade", "WelcomeDialog")

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
		self.headerimage.set_from_file("images/welcomeheader.png")

		self.openrecentbutton = self.res.get_widget("openrecentprojectbutton")
		self.openrecentbutton.set_sensitive(False)

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
		self.window.destroy()
		self.mainwindow.OnNewProject(self)
	
	#_____________________________________________________________________
			
	def OnOpenProject(self, button=None):
		self.window.destroy()
		self.mainwindow.OnOpenProject(self)
		
	#_____________________________________________________________________
	
	def OnPreferences(self, button):
		self.window.hide()
		pref = PreferencesDialog.PreferencesDialog(None, None, self.mainwindow.icon)
		pref.dlg.connect("destroy", self.OnPreferencesDialogClose)
		pref.dlg.set_transient_for(self.mainwindow.window)
		
	#_____________________________________________________________________
 
	def OnPreferencesDialogClose(self, dialog=None):
		self.window.show_all()
		
	#_____________________________________________________________________

	def OnQuit(self, button):
		gtk.main_quit()

	#_____________________________________________________________________

	def PopulateRecentProjects(self):
		'''Populate the Recent Projects menu with items from global settings'''		
		for path, name in self.mainwindow.recentprojectitems:	
			self.model.append([gtk.STOCK_NEW, name, path])
	
	#_____________________________________________________________________

	def OnRecentProjectSelected(self, treeview, path, view_column):
		item = self.model[path]
		self.mainwindow.OnRecentProjectsItem(self, item[2], item[1])
		self.window.destroy()
		
	#_____________________________________________________________________

	def OnEnableRecentProjectButton(self, treeview):
		self.openrecentbutton.set_sensitive(True)
		
	#_____________________________________________________________________

	def OnOpenRecentProjectButton(self, widget):
		item = self.model[self.tree.get_cursor()[0]]
		self.mainwindow.OnRecentProjectsItem(self, item[2], item[1])
		self.window.destroy()
	
	#_____________________________________________________________________

	def OnStartupToggled(self, widget):
		if widget.get_active():
			Globals.settings.general["startupaction"] = PreferencesDialog.STARTUP_NOTHING
		else:	
			Globals.settings.general["startupaction"] = PreferencesDialog.STARTUP_WELCOME_DIALOG
		
		Globals.settings.write()

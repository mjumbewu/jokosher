#!/usr/bin/python

import pygtk
pygtk.require("2.0")
import gtk
import gtk.glade
import sys, os
import gobject
import pygst
pygst.require("0.10")
import gst
try:
	gst.element_factory_make("gnlcomposition")
except:
	print "Gstreamer plugin gnonlin is not installed."
	print "See http://jokosher.org/trac/wiki/GettingJokosher for more details."
	sys.exit()

import xml.dom.minidom as xml

import AddInstrumentDialog
import TimeView
import CompactMixView
import PreferencesDialog
import RecordingView
import NewProjectDialog
import Project
import ConfigParser
import Globals
import WelcomeDialog
import InstrumentConnectionsDialog

gobject.threads_init()

#=========================================================================

class MainApp:
	
	# Class Constants
	MODE_RECORDING = 1
	MODE_COMPACT_MIX = 2

	#_____________________________________________________________________

	def __init__(self):

		self.wTree = gtk.glade.XML ("Jokosher.glade", "MainWindow")
		
		#Connect event handlers
		signals = {
			"on_MainWindow_destroy" : self.OnDestroy,
			"on_AddInstrument_clicked" : self.OnShowAddInstrumentDialog,
			"on_About_activate" : self.About,
			"on_Record_toggled" : self.Record,
			"on_Play_toggled" : self.Play,
			"on_Stop_clicked" : self.Stop,
			"on_Recording_toggled" : self.OnRecordingView,
			"on_CompactMix_toggled" : self.OnCompactMixView,
			"on_export_activate" : self.OnExport,
			"on_preferences_activate" : self.OnPreferences,
			"on_open_activate" : self.OnOpenProject,
			"on_save_activate" : self.OnSaveProject,
			"on_new_activate" : self.OnNewProject,
			"on_close_activate" : self.OnCloseProject,
			"on_show_as_bars_beats_ticks_toggled" : self.OnShowBarsBeats,
			"on_show_as_hours_minutes_seconds_toggled" : self.OnShowHoursMins,
			"on_undo_activate" : self.OnUndo,
			"on_redo_activate" : self.OnRedo,
			"on_MouseDown" : self.OnMouseDown,
			"on_instrumentconnections_activate" : self.OnInstrumentConnectonsDialog,
			"on_projectmenu_activate" : self.OnProjectMenu
		}
		self.wTree.signal_autoconnect(signals)
		
		# grab some references to bits of the GUI
		self.window = self.wTree.get_widget("MainWindow")
		self.play = self.wTree.get_widget("Play")
		self.stop = self.wTree.get_widget("Stop")
		self.record = self.wTree.get_widget("Record")
		self.save = self.wTree.get_widget("save")
		self.save_as = self.wTree.get_widget("save_as")
		self.close = self.wTree.get_widget("close")
		self.reverse = self.wTree.get_widget("Rewind")
		self.forward = self.wTree.get_widget("Forward")
		self.addInstrumentButton = self.wTree.get_widget("AddInstrument")
		self.forward = self.wTree.get_widget("Forward")
		self.editmenu = self.wTree.get_widget("editmenu")
		self.undo = self.wTree.get_widget("undo")
		self.redo = self.wTree.get_widget("redo")
		self.cut = self.wTree.get_widget("cut")
		self.copy = self.wTree.get_widget("copy")
		self.paste = self.wTree.get_widget("paste")
		self.delete = self.wTree.get_widget("delete")
		self.projectmenu = self.wTree.get_widget("projectmenu")
		self.export = self.wTree.get_widget("export")
		self.recentprojects = self.wTree.get_widget("recentprojects")
		self.menubar = self.wTree.get_widget("menubar")
		
		self.recentprojectitems = []

		self.recentprojectsmenu = gtk.Menu()
		self.recentprojects.set_submenu(self.recentprojectsmenu)

		self.project = None
		self.recording = None
		self.headerhbox = None
		self.timeview = None
		self.tvtoolitem = None #wrapper for putting timeview in toolbar
		self.recording = None
		self.compactmix = None
		self.main_vbox = self.wTree.get_widget("main_vbox")
		
		# Initialise some useful vars
		self.mode = None
		self.settingButtons = True
		self.wTree.get_widget("Recording").set_active(True)
		self.settingButtons = False
		
		self.isRecording = False
		self.isPlaying = False
		
		# set sensitivity
		self.SetGUIProjectLoaded()

		# Connect up the forward and reverse handlers. We can't use the autoconnect as we need child items
		
		innerbtn = self.reverse.get_children()[0]
		innerbtn.connect("pressed", self.OnRewindPressed)
		innerbtn.connect("released", self.OnRewindReleased)
		
		innerbtn = self.forward.get_children()[0]
		innerbtn.connect("pressed", self.OnForwardPressed)
		innerbtn.connect("released", self.OnForwardReleased)
		
		# populate the Recent Projects menu
		self.OpenRecentProjects()
		self.PopulateRecentProjects()
		
		#set window icon
		self.window.set_icon_from_file("logo.png")
		#make icon available to others
		self.icon = self.window.get_icon()
		
		# Show the main window
		self.window.show_all()
		
		# Make sure we can import for the instruments folder
		sys.path.append("Instruments")
		
		self.window.add_events(gtk.gdk.KEY_PRESS_MASK)
		self.window.connect_after("key-press-event", self.OnKeyPress)
		self.window.connect("button_press_event", self.OnMouseDown)

		# check if we should display the startup dialog
		
		if Globals.settings.general["startupaction"] == PreferencesDialog.STARTUP_LAST_PROJECT:
			self.OpenLastProject()
		elif Globals.settings.general["startupaction"] == PreferencesDialog.STARTUP_NOTHING:
			pass
		else: #default option if no preference is set
			WelcomeDialog.WelcomeDialog(self)
		
	#_____________________________________________________________________

	def clean(self):
		self.project.clean()
		
	#_____________________________________________________________________	
		
	def OnChangeView(self, view, mode):
		if not self.settingButtons:
			self.settingButtons = True
			self.wTree.get_widget("Recording").set_active(mode == self.MODE_RECORDING)
			self.wTree.get_widget("CompactMix").set_active(mode == self.MODE_COMPACT_MIX)
			self.settingButtons = False
			
			if view:
				children = self.main_vbox.get_children()
				if self.recording in children:
					self.main_vbox.remove(self.recording)
				elif self.compactmix in children:
					self.main_vbox.remove(self.compactmix)
				
				self.main_vbox.pack_end(view, True, True)
				self.window.show_all()
				self.mode = mode
				self.UpdateCurrentDisplay()

	#_____________________________________________________________________
	
	def OnRecordingView(self, window=None):
		if hasattr(self, "recording"):
			self.OnChangeView(self.recording, self.MODE_RECORDING)	
	#_____________________________________________________________________
	
	def OnCompactMixView(self, window=None):
		if hasattr(self, "compactmix"):
			self.OnChangeView(self.compactmix, self.MODE_COMPACT_MIX)
	#_____________________________________________________________________
	
	def OnDestroy(self, widget=None, event=None):
		if self.CloseProject() == 0:
			gtk.main_quit()
		else:
			return True #stop signal propogation
		
	#_____________________________________________________________________
	
	def OnShowAddInstrumentDialog(self, widget):
		""" Creates and shows the 'Add Instrument' dialog box """
		dlg = AddInstrumentDialog.AddInstrumentDialog(self.project, self)
	
	#_____________________________________________________________________
	
	def About(self, widget = None):
		'''Display about dialog'''
		aboutTree = gtk.glade.XML ("Jokosher.glade", "AboutDialog")
		dlg = aboutTree.get_widget("AboutDialog")
		dlg.set_transient_for(self.window)
		dlg.set_icon(self.icon)
		
	#_____________________________________________________________________

	def Record(self, widget = None):
		'''Toggle recording'''
		
		if self.settingButtons:
			return
		
		canRecord = False
		for i in self.project.instruments:
			if i.isArmed:
				canRecord = True
				
		if not canRecord:
			dlg = gtk.MessageDialog(self.window,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_INFO,
				gtk.BUTTONS_CLOSE,
				"No instruments are armed for recording. You need to arm an instrument before you can begin recording.")
			dlg.connect('response', lambda dlg, response: dlg.destroy())
			dlg.run()
			self.settingButtons = True
			widget.set_active(False)
			self.settingButtons = False
		else:		
			self.isRecording = not self.isRecording
			self.stop.set_sensitive(self.isRecording)
			self.play.set_sensitive(not self.isRecording)
			if self.isRecording:
				self.project.record()
			else:
				self.project.stop()

	#_____________________________________________________________________
	
	def Play(self, widget = None):
		'''Toggle playing'''
		self.isPlaying = not self.isPlaying
		self.stop.set_sensitive(self.isPlaying)
		self.record.set_sensitive(not self.isPlaying)
		self.compactmix.StartUpdateTimeout()
		if self.isPlaying:
			self.project.play()
		else:
			self.project.stop()

	#_____________________________________________________________________

	#The stop button is really just an alias for toggling play/record to off
	def Stop(self, widget = None):
		'''Stop recording/playing (whichever is happening)'''
		if self.isRecording: 
			self.record.set_active(False)
		if self.isPlaying: 
			self.play.set_active(False)

	#_____________________________________________________________________

	def OnRewindPressed(self, widget = None):
		self.project.transport.Reverse(True)
		
	#_____________________________________________________________________
		
	def OnRewindReleased(self, widget = None):
		self.project.transport.Reverse(False)
		
	#_____________________________________________________________________
		
	def OnForwardPressed(self, widget = None):
		self.project.transport.Forward(True)
		
	#_____________________________________________________________________
		
	def OnForwardReleased(self, widget = None):
		self.project.transport.Forward(False)
	
	#_____________________________________________________________________
	
	def InstrumentSelected(self, widget = None, event = None):
		'''If an instrument has been selected, enable the record button'''
		for instr in self.project.instruments:
			if instr.isSelected:
				self.record.set_sensitive(True)

	#_____________________________________________________________________
	
	def OnExport(self, widget = None):
		'''Display a save dialog allowing the user to export as ogg or mp3'''
		buttons = (gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK)
		chooser = gtk.FileChooserDialog("Export Project", self.window, gtk.FILE_CHOOSER_ACTION_SAVE, buttons)
		
		oggfilter = gtk.FileFilter()
		oggfilter.set_name("Ogg Vorbis (*.ogg)")
		oggfilter.add_pattern("*.ogg")
		
		mp3filter = gtk.FileFilter()
		mp3filter.set_name("MP3 (*.mp3)")
		mp3filter.add_pattern("*.mp3")
		
		chooser.add_filter(mp3filter)
		chooser.add_filter(oggfilter)
		
		response = chooser.run()
		if response == gtk.RESPONSE_OK:
			filename = chooser.get_filename()
			chooser.destroy()
		
			export = gtk.glade.XML ("Jokosher.glade", "ProgressDialog")
			export.signal_connect("on_cancel_clicked", self.OnExportCancel)
			
			self.exportdlg = export.get_widget("ProgressDialog")
			self.exportdlg.set_icon(self.icon)
			self.exportdlg.set_transient_for(self.window)
			
			label = export.get_widget("progressLabel")
			label.set_text("Exporting project to file: %s" %filename)
			
			self.exportprogress = export.get_widget("progressBar")
			
			gobject.timeout_add(100, self.UpdateExportDialog)
			self.project.export(filename)
		else:
			chooser.destroy()
		
	#_____________________________________________________________________
	
	def UpdateExportDialog(self):
		tuple = self.project.get_export_progress()
		if tuple[0] == -1:
			self.exportprogress.set_fraction(0.0)
			self.exportprogress.set_text("Preparing to export project")
		elif tuple[0] == tuple[1] == 100:
			self.exportdlg.destroy()
			return False
		else:
			self.exportprogress.set_fraction(tuple[0]/tuple[1])
			self.exportprogress.set_text("%d of %d seconds exported" % (tuple[0], tuple[1]))
			
		return True
	
	#_____________________________________________________________________
	
	def OnExportCancel(self, widget=None):
		self.exportdlg.destroy()
		self.project.export_eos()
	
	#_____________________________________________________________________
	
	def OnPreferences(self, widget, destroyCallback=None):
		if (self.project):
			prefsdlg = PreferencesDialog.PreferencesDialog(self.project, self.UpdateDisplay, self.icon)
		else:
			prefsdlg = PreferencesDialog.PreferencesDialog(self.project, None, self.icon)
			
		if destroyCallback:
			prefsdlg.dlg.connect("destroy", destroyCallback)
	
	#_____________________________________________________________________
	
	def OnShowBarsBeats(self, widget):
		if self.project and self.project.transport:
			self.project.transport.SetMode(self.project.transport.MODE_BARS_BEATS)
		
	#_____________________________________________________________________
	
	def OnShowHoursMins(self, widget):
		if self.project and self.project.transport:
			self.project.transport.SetMode(self.project.transport.MODE_HOURS_MINS_SECS)
		
	#_____________________________________________________________________
	
	def UpdateCurrentDisplay(self):
		if self.mode == self.MODE_RECORDING:
			self.recording.Update()
		elif self.mode == self.MODE_COMPACT_MIX:
			self.compactmix.Update()
	
	#_____________________________________________________________________
	
	def UpdateDisplay(self):
		if self.mode == self.MODE_RECORDING:
			self.recording.Update()
			gobject.idle_add(self.compactmix.Update)
		elif self.mode == self.MODE_COMPACT_MIX:
			self.compactmix.Update()
			gobject.idle_add(self.recording.Update)
		
	#_____________________________________________________________________

	def OnOpenProject(self, widget, destroyCallback=None):
		
		chooser = gtk.FileChooserDialog(('Choose a Jokosher project file'), None, gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		chooser.set_default_response(gtk.RESPONSE_OK)
		chooser.set_transient_for(self.window)
		allfilter = gtk.FileFilter()
		allfilter.set_name("All Files")
		allfilter.add_pattern("*")
		
		jokfilter = gtk.FileFilter()
		jokfilter.set_name("Jokosher Project File (*.jokosher)")
		jokfilter.add_pattern("*.jokosher")
		
		chooser.add_filter(jokfilter)
		chooser.add_filter(allfilter)
		
		if destroyCallback:
			chooser.connect("destroy", destroyCallback)
		
		while True:
			response = chooser.run()
			
			if response == gtk.RESPONSE_OK:
				
				filename = chooser.get_filename()
				
				try:
					self.SetProject(Project.LoadFromFile(filename))
				except Project.OpenProjectError:
					dlg = gtk.MessageDialog(chooser,
						gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
						gtk.MESSAGE_ERROR,
						gtk.BUTTONS_OK,
						"The project file could not be opened.\n")
					dlg.set_icon(self.icon)
					dlg.run()
					dlg.destroy()
				else:
					break
				
			elif response == gtk.RESPONSE_CANCEL or response == gtk.RESPONSE_DELETE_EVENT:
				break
		
		chooser.destroy()
		
	#_____________________________________________________________________
		
	def OnSaveProject(self, widget=None):		
		if self.project:
			self.project.ClearInstrumentSelections()
			self.project.ClearEventSelections()
			self.project.saveProjectFile()
			
	#_____________________________________________________________________

	def OnNewProject(self, widget, destroyCallback=None):
		""" Creates and shows the 'New Project' dialog box """
		newdlg = NewProjectDialog.NewProjectDialog(self)
		if destroyCallback:
			newdlg.dlg.connect("destroy", destroyCallback)
		
	#_____________________________________________________________________
		
	def OnCloseProject(self, widget):
		""" Closes a project """
		if self.CloseProject() == 0:
			self.SetGUIProjectLoaded()
	#_____________________________________________________________________
	
	def CloseProject(self):
		#return values: 0 == okay, 1 == cancel and return to program
		if not self.project:
			return 0
		
		print "Shutting down",
		self.Stop()
		if self.project.CheckUnsavedChanges():
			message = "<span size='large' weight='bold'>Save changes to project \"%s\" before closing?</span>\n\nYour changes will be lost if you don't save them." % self.project.name
			
			dlg = gtk.MessageDialog(self.window,
				gtk.DIALOG_MODAL |
				gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_WARNING,
				gtk.BUTTONS_NONE)
			dlg.set_markup(message)
			
			dlg.add_button("Close _Without Saving", gtk.RESPONSE_NO)
			dlg.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
			defaultAction = dlg.add_button(gtk.STOCK_SAVE, gtk.RESPONSE_YES)
			#make save the default action when enter is pressed
			dlg.set_default(defaultAction)
			
			dlg.set_transient_for(self.window)
			
			response = dlg.run()
			dlg.destroy()
			if response == gtk.RESPONSE_YES:
				self.OnSaveProject()
			elif response == gtk.RESPONSE_NO:
				pass
			elif response == gtk.RESPONSE_CANCEL or response == gtk.RESPONSE_DELETE_EVENT:
				return 1
				
		self.project.closeProject()
		print "Done"
		
		self.project = None
		self.mode = None
		return 0
		
	#_____________________________________________________________________
	
	def OnUndo(self, widget):
		self.project.Undo()
		self.UpdateDisplay()
		
	#_____________________________________________________________________
	
	def OnRedo(self, widget):
		self.project.Redo()
		self.UpdateDisplay()

	#_____________________________________________________________________
	
	def OnStateChanged(self, obj=None, change=None):
		#for when undo and redo history change
		undo = len(self.project.undoStack) or len(self.project.savedUndoStack)
		self.undo.set_sensitive(undo)
		redo = len(self.project.redoStack) or len(self.project.savedRedoStack)
		self.redo.set_sensitive(redo)
		
		if self.project.CheckUnsavedChanges():
			self.window.set_title('*%s - Jokosher' % self.project.name)
		else:
			self.window.set_title('%s - Jokosher' % self.project.name)
		
	#_____________________________________________________________________

	def InsertRecentProject(self, path, name):
		for item in self.recentprojectitems:
			if path == item[0]:
				self.recentprojectitems.remove(item)
				break
		
		self.recentprojectitems.insert(0, (path, name))
		self.SaveRecentProjects()
		self.PopulateRecentProjects()

	#_____________________________________________________________________

	def PopulateRecentProjects(self):
		'''Populate the Recent Projects menu with items from self.recentprojectitems'''
		
		menuitems = self.recentprojectsmenu.get_children()

		for c in menuitems:
			self.recentprojectsmenu.remove(c)
		
		for item in self.recentprojectitems:
			self.mitem = gtk.MenuItem(item[1])
			self.recentprojectsmenu.append(self.mitem)
			self.mitem.connect("activate", self.OnRecentProjectsItem, item[0], item[1])
				
			self.mitem.show()

		self.recentprojectsmenu.show()
	#_____________________________________________________________________
	
	def OpenRecentProjects(self):
		'''Populate the self.recentprojectpaths with items from global settings'''
		self.recentprojectitems = []
		if Globals.settings.general.has_key("recentprojects"):
			filestring = Globals.settings.general["recentprojects"]
			filestring = filestring.split(",")
			recentprojectitems = []
			for i in filestring:
				if len(i.split("|")) == 2:
					recentprojectitems.append(i.split("|"))	
					
			for path, name in recentprojectitems:
				#TODO - see ticket 80; should it check if the project is valid?
				if not os.path.exists(path):
					print "Error: Couldn't open recent project", path
				else:
					self.recentprojectitems.append((path, name))
		
		self.SaveRecentProjects()

	#_____________________________________________________________________
	
	def OnRecentProjectsItem(self, widget, path, name):
		try:
			self.SetProject(Project.LoadFromFile(path))
		except Project.OpenProjectError:
			dlg = gtk.MessageDialog(self.window,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_ERROR,
				gtk.BUTTONS_OK,
				"The project file could not be opened.\n")
			dlg.run()
			dlg.destroy()
			return
	
	#_____________________________________________________________________

	def SaveRecentProjects(self):
		string = ""

		# Cut list to 8 items
		self.recentprojectitems = self.recentprojectitems[:8]
		
		for path, name in self.recentprojectitems:
			string = string + str(path) + "|" + str(name) + ","
			
		string = string[:-1]
		Globals.settings.general['recentprojects'] = string
		Globals.settings.write()
		
	#______________________________________________________________________
	
	def OnDelKey(self):
		# Delete any select instruments
		for instr in self.project.instruments:
			if (instr.isSelected):
				# Select all the instruments events to delete
				for ev in instr.events:
					ev.isSelected = True
				#set not selected so when we undo we don't get two selected instruments
				instr.isSelected = False
				self.project.DeleteInstrument(instr.id)

		# Delete any selected events
		for instr in self.project.instruments:
			for ev in instr.events:
				if ev.isSelected:
					ev.Delete()

		self.undo.set_sensitive(True)
		self.UpdateDisplay()
	
	#______________________________________________________________________

	def OnMouseDown(self, widget, mouse):
		if self.project:
			self.project.ClearEventSelections()
			self.project.ClearInstrumentSelections()
		self.UpdateCurrentDisplay()
		
	#______________________________________________________________________
	
	def SetGUIProjectLoaded(self):
		children = self.main_vbox.get_children()
		if self.recording in children:
			self.main_vbox.remove(self.recording)
		elif self.compactmix in children:
			self.main_vbox.remove(self.compactmix)
		
		if self.headerhbox in children:
			self.main_vbox.remove(self.headerhbox)
		if self.tvtoolitem in self.wTree.get_widget("MainToolbar").get_children():
			self.wTree.get_widget("MainToolbar").remove(self.tvtoolitem)
		
		RecordingToggle = self.wTree.get_widget("Recording")
		CompactToggle = self.wTree.get_widget("CompactMix")
		
		ctrls = (self.save, self.save_as, self.close, self.addInstrumentButton,
			self.reverse, self.forward, self.play, self.stop, self.record,
			self.projectmenu, self.export, self.cut, self.copy, self.paste,
			self.undo, self.redo, self.delete,
			RecordingToggle, CompactToggle, 
			self.wTree.get_widget("WorkspacesLabel"))
		
		if self.project:
			# make various buttons and menu items enabled now we have a project option
			for c in ctrls:
				c.set_sensitive(True)
			
			#set undo/redo if there is saved undo history
			self.OnStateChanged()
				
			# Create our custom widgets
			self.timeview = TimeView.TimeView(self.project)
			self.compactmix = CompactMixView.CompactMixView(self.project)
			self.recording = RecordingView.RecordingView(self.project)
			
			# Add them to the main window
			self.main_vbox.pack_end(self.recording, True, True)
			
			self.tvtoolitem = gtk.ToolItem()
			self.tvtoolitem.add(self.timeview)
			self.wTree.get_widget("MainToolbar").insert(self.tvtoolitem, -1)
			
			self.compactmix.Update()
			self.OnRecordingView()
			
		else:
			for c in ctrls:
				c.set_sensitive(False)
			
			#untoggle all toggle buttons when the project is unloaded
			self.settingButtons = True
			for t in (RecordingToggle, CompactToggle):
				t.set_active(False)
			self.settingButtons = False
				
			# Set window title with no project name
			self.window.set_title('Jokosher')
			
			# Destroy our custom widgets
			if self.recording:
				self.recording.destroy()
				self.recording = None
			if self.compactmix:
				self.compactmix.destroy()
				self.compactmix = None
			if self.tvtoolitem:
				self.tvtoolitem.destroy()
				self.tvtoolitem = None
	
	#_____________________________________________________________________
	
	def OnKeyPress(self, widget, event):
		
		keysdict = {
			65471:self.OnRecordingView, # F2 - Recording View
			65472:self.OnCompactMixView, # F3 - Compact Mix View
			65535:self.OnDelKey, # delete key - remove selected item
			65288:self.OnDelKey, # backspace key
		}

		if event.keyval in keysdict:
			keysdict[event.keyval]()

	#_____________________________________________________________________
	
	def OnInstrumentConnectonsDialog(self, widget):
		dlg = InstrumentConnectionsDialog.InstrumentConnectionsDialog(self.project, self)
		
	#_____________________________________________________________________
	
	def OnProjectMenu(self, widget):
		#HACK: when project menu opens, put the time format to the right
		#one so that we don't have to monitor transportmanager
		if self.settingButtons:
			return
		self.settingButtons = True
		a = self.wTree.get_widget("show_as_bars_beats_ticks")
		b = self.wTree.get_widget("show_as_hours_minutes_seconds")
		transport = self.project.transport
		
		a.set_active(transport.mode == transport.MODE_BARS_BEATS)
		b.set_active(transport.mode == transport.MODE_HOURS_MINS_SECS)
		
		self.settingButtons = False
	
	#_____________________________________________________________________
	
	def OpenLastProject(self):
		if len(self.recentprojectitems) > 0:
			path = self.recentprojectitems[0][0]
			name = self.recentprojectitems[0][1]
			try:
				self.SetProject(Project.LoadFromFile(path))
			except Project.OpenProjectError:
				dlg = gtk.MessageDialog(self.window,
					gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
					gtk.MESSAGE_ERROR,
					gtk.BUTTONS_OK,
					"The previous project file could not be opened.\n")
				dlg.run()
				dlg.destroy()
				#launch welcome dialog instead
				WelcomeDialog.WelcomeDialog(self)
				return
	
	#_____________________________________________________________________
	
	def SetProject(self, project):
		if self.project:
			if self.CloseProject() != 0:
				return
			
		self.project = project
		self.project.AddListener(self)
		self.InsertRecentProject(project.projectfile, project.name)
		
		Project.GlobalProjectObject = project

		# make various buttons and menu items enabled now we have a project
		self.SetGUIProjectLoaded()
		
	#_____________________________________________________________________

#=========================================================================
		
print "Starting up"

def main():
	app=MainApp()
	gtk.threads_init()
	gtk.main()

if __name__ == "__main__":
	main()


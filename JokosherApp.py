#!/usr/bin/python

import pygtk
pygtk.require("2.0")
import gtk
import gtk.glade
import sys, os
import os.path
import gobject
import pygst
pygst.require("0.10")
import gst
import optparse


import locale
import gettext
_ = gettext.gettext

import AddInstrumentDialog
import TimeView
import CompactMixView
import PreferencesDialog
import RecordingView
import NewProjectDialog
import Project
import Globals
import WelcomeDialog
import InstrumentConnectionsDialog
import StatusBar
import AlsaDevices
from EffectPresets import *
import Extension

gobject.threads_init()

#=========================================================================

class MainApp:
	
	
	# Class Constants
	MODE_RECORDING = 1
	MODE_COMPACT_MIX = 2

	#_____________________________________________________________________

	def __init__(self):

		#Find the absolute path in case we were imported from another directory
		Globals.SetAbsPaths()

		try:
			locale.setlocale(locale.LC_ALL, '')
			gettext.bindtextdomain(Globals.LOCALE_APP, Globals.LOCALE_DIR)
			gettext.bind_textdomain_codeset(Globals.LOCALE_APP, "UTF-8");
			gettext.textdomain(Globals.LOCALE_APP)
			gtk.glade.bindtextdomain(Globals.LOCALE_APP, Globals.LOCALE_DIR)
			gtk.glade.textdomain(Globals.LOCALE_APP)
		except locale.Error:
			print "Locale unsupported, defaulting to english for all Jokosher specific text"
		
		self.wTree = gtk.glade.XML(Globals.GLADE_PATH, "MainWindow")
		
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
			"on_save_as_activate" : self.OnSaveAsProject,
			"on_new_activate" : self.OnNewProject,
			"on_close_activate" : self.OnCloseProject,
			"on_show_as_bars_beats_ticks_toggled" : self.OnShowBarsBeats,
			"on_show_as_hours_minutes_seconds_toggled" : self.OnShowHoursMins,
			"on_undo_activate" : self.OnUndo,
			"on_redo_activate" : self.OnRedo,
			"on_cut_activate" : self.OnCut,
			"on_copy_activate" : self.OnCopy,
			"on_paste_activate" : self.OnPaste,
			"on_delete_activate" : self.OnDelete,
			"on_MouseDown" : self.OnMouseDown,
			"on_instrumentconnections_activate" : self.OnInstrumentConnectonsDialog,
			"on_editmenu_activate" : self.OnEditMenu,
			"on_projectmenu_activate" : self.OnProjectMenu,
			"on_prereleasenotes_activate" : self.OnPreReleaseNotes,
			"on_contributing_activate" : self.OnContributingDialog

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
		self.lastopenedproject = None

		self.recentprojectsmenu = gtk.Menu()
		self.recentprojects.set_submenu(self.recentprojectsmenu)
		
		self.project = None
		self.recording = None
		self.headerhbox = None
		self.timeview = None
		self.tvtoolitem = None #wrapper for putting timeview in toolbar
		self.recording = None
		self.compactmix = None
		self.instrNameEntry = None #the gtk.Entry when editing an instrument name
		self.main_vbox = self.wTree.get_widget("main_vbox")
		
		self.statusbar = StatusBar.StatusBar()
		self.main_vbox.pack_end(self.statusbar, False)
		
		# Initialise some useful vars
		self.mode = None
		self.settingButtons = True
		self.wTree.get_widget("Recording").set_active(True)
		self.settingButtons = False
		self.defaultlocation = os.path.realpath(".")
		self.isRecording = False
		self.isPlaying = False

		# parse command line
		openproject = None
		parser = optparse.OptionParser("usage: %prog [project]")
		(options, args) = parser.parse_args()
		if len(args) > 0:
			openproject = args[0]

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
		self.window.set_icon_from_file(os.path.join(Globals.IMAGE_PATH, "jokosher-icon.png"))
		#make icon available to others
		self.icon = self.window.get_icon()
		
		# Show the main window
		self.window.show_all()
		
		# Make sure we can import for the instruments folder
		sys.path.append("Instruments")
		
		self.window.add_events(gtk.gdk.KEY_PRESS_MASK)
		self.window.connect_after("key-press-event", self.OnKeyPress)
		self.window.connect("button_press_event", self.OnMouseDown)

		self.CheckGstreamerVersions()


		if openproject:
			self.OpenProjectFromPath(openproject)
		elif Globals.settings.general["startupaction"] == PreferencesDialog.STARTUP_LAST_PROJECT:
			if self.lastopenedproject:
				self.OpenProjectFromPath(self.lastopenedproject[0])
		elif Globals.settings.general["startupaction"] == PreferencesDialog.STARTUP_NOTHING:
			return

		#if everything else bombs out resort to the welcome dialog
		if self.project == None:
			WelcomeDialog.WelcomeDialog(self)

		# set up presets registry - this should probably be removed here	
		EffectPresets().FillEffectsPresetsRegistry()
		
		# Load extensions -- this should probably go somewhere more appropriate
		Extension.API.mainapp = self
		Extension.LoadAllExtensions()
	#_____________________________________________________________________	

	def OnChangeView(self, view, mode):
		if not self.settingButtons:
			self.settingButtons = True
			self.wTree.get_widget("Recording").set_active(mode == self.MODE_RECORDING)
			self.wTree.get_widget("CompactMix").set_active(mode == self.MODE_COMPACT_MIX)
			self.settingButtons = False
			
			if view:
				# need to force a redraw of timeline when changing
				# views (may have been zoom or scroll while hidden)
				self.project.RedrawTimeLine = True
				children = self.main_vbox.get_children()
				if self.recording in children:
					self.main_vbox.remove(self.recording)
					# synchronise scrollbars
					self.compactmix.projectview.scrollRange.value = self.recording.scrollRange.value
				elif self.compactmix in children:
					self.main_vbox.remove(self.compactmix)
					# synchronise scrollbars
					self.recording.scrollRange.value = self.compactmix.projectview.scrollRange.value
				
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
		AddInstrumentDialog.AddInstrumentDialog(self.project, self)
	
	#_____________________________________________________________________
	
	def About(self, widget = None):
		'''Display about dialog'''
		aboutTree = gtk.glade.XML(Globals.GLADE_PATH, "AboutDialog")
		dlg = aboutTree.get_widget("AboutDialog")
		dlg.set_transient_for(self.window)
		dlg.set_icon(self.icon)
		
	#_____________________________________________________________________

	def Record(self, widget = None):
		'''Toggle recording'''
		if self.settingButtons or not widget.get_active():
			return
		
		canRecord = False
		for i in self.project.instruments:
			if i.isArmed:
				canRecord = True

		#Check to see if any instruments are trying to use the same input channel
		usedChannels = {}
		for instr in self.project.instruments:
			if instr.isArmed:
				if usedChannels.has_key(instr.input):
					if usedChannels[instr.input].has_key(instr.inTrack):
						string = _("The instruments '%s' and '%s' both have the same input selected (%s). Please either disarm one, or connect it to a different input through 'Project -> Instrument Connections'")
						message = string % (usedChannels[instr.input][instr.inTrack], instr.name, instr.inTrack)
						dlg = gtk.MessageDialog(self.window,
							gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
							gtk.MESSAGE_INFO,
							gtk.BUTTONS_CLOSE,
							message)
						dlg.connect('response', lambda dlg, response: dlg.destroy())
						dlg.run()
						self.settingButtons = True
						widget.set_active(False)
						self.settingButtons = False
						return
					else:
						usedChannels[instr.input][instr.inTrack] = instr.name
				else:
					usedChannels[instr.input] = {instr.inTrack : instr.name}
				
		if not canRecord:
			dlg = gtk.MessageDialog(self.window,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_INFO,
				gtk.BUTTONS_CLOSE,
				_("No instruments are armed for recording. You need to arm an instrument before you can begin recording."))
			dlg.connect('response', lambda dlg, response: dlg.destroy())
			dlg.run()
			self.settingButtons = True
			widget.set_active(False)
			self.settingButtons = False
		else:		
			#Deselect all input channels (the required ones will be reselected by each instrument)
			devices = AlsaDevices.GetAlsaList("capture").values()
			for device in devices: 
				mixer = gst.element_factory_make('alsamixer')
				mixer.set_property("device", device)
				mixer.set_state(gst.STATE_READY)

				for track in mixer.list_tracks():
					if track.flags & gst.interfaces.MIXER_TRACK_INPUT:
						mixer.set_record(track, False)
					#Most cards incapable of multiple simultanious input have a channel called 'Capture' which must be enabled along with the actual input channel
					if track.label == 'Capture':
						mixer.set_record(track, True)

				mixer.set_state(gst.STATE_NULL)

			self.isRecording = not self.isRecording
			self.stop.set_sensitive(self.isRecording)
			self.play.set_sensitive(not self.isRecording)
			if self.isRecording:
				try:
					self.project.record()
				except Project.AudioInputsError, e:
					if e.errno==0:
						message=_("No channels capable of recording have been found, please attach a device and try again.")
					else:
						message=_("Your sound card isn't capable of recording from multiple sources at the same time. Please disarm all but one instrument.")

					dlg = gtk.MessageDialog(self.window,
						gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
						gtk.MESSAGE_INFO,
						gtk.BUTTONS_CLOSE,
						message)
					dlg.connect('response', lambda dlg, response: dlg.destroy())
					dlg.run()
					self.project.terminate()
					self.isRecording = not self.isRecording
					self.stop.set_sensitive(self.isRecording)
					self.play.set_sensitive(not self.isRecording)
					self.record.set_active(self.isRecording)
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
		chooser = gtk.FileChooserDialog(_("Mixdown Project"), self.window, gtk.FILE_CHOOSER_ACTION_SAVE, buttons)
		chooser.set_current_folder(self.defaultlocation)

		saveLabel = gtk.Label(_("Save as file type:"))		
		typeCombo = gtk.combo_box_new_text()
		#tuples containing the display test, and the extension (without ".")
		types = [("Ogg Vorbis (.ogg)","ogg"), ("MP3 (.mp3)","mp3"), 
					("Flac (.flac)","flac"), ("WAV (.wav)","wav")]
		for i in types:
			typeCombo.append_text(i[0])
		#Default file type is ogg
		typeCombo.set_active(0)
		
		extraHBox = gtk.HBox()
		extraHBox.pack_start(saveLabel, False)
		extraHBox.pack_end(typeCombo, False)
		extraHBox.show_all()
		chooser.set_extra_widget(extraHBox)
		
		response = chooser.run()
		if response == gtk.RESPONSE_OK:
			filename = chooser.get_filename()
			self.defaultlocation = os.path.dirname(filename)
			#If they haven't already appended the extension for the 
			#chosen file type, add it to the end of the file.
			filetype = types[typeCombo.get_active()][1]
			if not filename.lower().endswith(filetype):
				filename = filename + "." + filetype
				
			chooser.destroy()
		
			export = gtk.glade.XML (Globals.GLADE_PATH, "ProgressDialog")
			export.signal_connect("on_cancel_clicked", self.OnExportCancel)
			
			self.exportdlg = export.get_widget("ProgressDialog")
			self.exportdlg.set_icon(self.icon)
			self.exportdlg.set_transient_for(self.window)
			
			label = export.get_widget("progressLabel")
			label.set_text(_("Mixing project to file: %s") %filename)
			
			self.exportprogress = export.get_widget("progressBar")
			
			gobject.timeout_add(100, self.UpdateExportDialog)
			self.project.export(filename)
		else:
			chooser.destroy()
		
	#_____________________________________________________________________
	
	def UpdateExportDialog(self):
		tuple = self.project.get_export_progress()
		if tuple[0] == -1 or tuple[1] == 0:
			self.exportprogress.set_fraction(0.0)
			self.exportprogress.set_text(_("Preparing to mixdown project"))
		elif tuple[0] == tuple[1] == 100:
			self.exportdlg.destroy()
			return False
		else:
			self.exportprogress.set_fraction(tuple[0]/tuple[1])
			self.exportprogress.set_text(_("%d of %d seconds completed") % (tuple[0], tuple[1]))
			
		return True
	
	#_____________________________________________________________________
	
	def OnExportCancel(self, widget=None):
		self.exportdlg.destroy()
		self.project.export_eos()
	
	#_____________________________________________________________________
	
	def OnPreferences(self, widget, destroyCallback=None):
		prefsdlg = PreferencesDialog.PreferencesDialog(self.project, self, self.icon)
			
		if destroyCallback:
			prefsdlg.dlg.connect("destroy", destroyCallback)
	
	#_____________________________________________________________________
	
	def OnShowBarsBeats(self, widget):
		if self.settingButtons:
			return
		if widget.get_active() and self.project and self.project.transport:
			self.project.SetTransportMode(self.project.transport.MODE_BARS_BEATS)
		
	#_____________________________________________________________________
	
	def OnShowHoursMins(self, widget):
		if self.settingButtons:
			return
		if widget.get_active() and self.project and self.project.transport:
			self.project.SetTransportMode(self.project.transport.MODE_HOURS_MINS_SECS)
		
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
		
		chooser = gtk.FileChooserDialog((_('Choose a Jokosher project file')), None, gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		chooser.set_current_folder(self.defaultlocation)

		chooser.set_default_response(gtk.RESPONSE_OK)
		chooser.set_transient_for(self.window)
		allfilter = gtk.FileFilter()
		allfilter.set_name(_("All Files"))
		allfilter.add_pattern("*")
		
		jokfilter = gtk.FileFilter()
		jokfilter.set_name(_("Jokosher Project File (*.jokosher)"))
		jokfilter.add_pattern("*.jokosher")
		
		chooser.add_filter(jokfilter)
		chooser.add_filter(allfilter)
		
		if destroyCallback:
			chooser.connect("destroy", destroyCallback)
		
		while True:
			response = chooser.run()
			
			if response == gtk.RESPONSE_OK:
				
				filename = chooser.get_filename()
				self.defaultlocation = os.path.dirname(filename)
				if self.OpenProjectFromPath(filename,chooser):
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
	
	def OnSaveAsProject(self, widget=None):
		buttons = (gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK)
		chooser = gtk.FileChooserDialog(_("Choose a location to save the project"), self.window, gtk.FILE_CHOOSER_ACTION_SAVE, buttons)
		chooser.set_current_folder(self.defaultlocation)

		response = chooser.run()
		if response == gtk.RESPONSE_OK:
			filename = chooser.get_filename()
			self.defaultlocation = os.path.dirname(filename)
			self.project.ClearInstrumentSelections()
			self.project.ClearEventSelections()
			self.project.saveProjectFile(filename)
		chooser.destroy()
		
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
		
		self.Stop()
		if self.project.CheckUnsavedChanges():
			message = _("<span size='large' weight='bold'>Save changes to project \"%s\" before closing?</span>\n\nYour changes will be lost if you don't save them.") % self.project.name
			
			dlg = gtk.MessageDialog(self.window,
				gtk.DIALOG_MODAL |
				gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_WARNING,
				gtk.BUTTONS_NONE)
			dlg.set_markup(message)
			
			dlg.add_button(_("Close _Without Saving"), gtk.RESPONSE_NO)
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
			self.window.set_title(_('*%s - Jokosher') % self.project.name)
		else:
			self.window.set_title(_('%s - Jokosher') % self.project.name)
		
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
			
			#the first project is our last opened project
			if recentprojectitems and os.path.exists(recentprojectitems[0][0]):
				self.lastopenedproject = recentprojectitems[0]
			
		self.SaveRecentProjects()

	#_____________________________________________________________________
	
	def OnRecentProjectsItem(self, widget, path, name):
		self.OpenProjectFromPath(path)

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
	
	def OnCut(self, widget=None, cut=True):
		if self.instrNameEntry:
			#if an instrument name is currently being edited
			if cut:
				self.instrNameEntry.cut_clipboard()
			else:
				self.instrNameEntry.copy_clipboard()
			return
	
		#Wipe the clipboard clean
		self.project.clipboardList = []
		for instr in self.project.instruments:
			for event in instr.events:
				if event.isSelected:
					#Add to the clipboard
					self.project.clipboardList.append(event)
					if cut:
						#if we are cutting (as opposed to copying)
						event.Delete()

		self.UpdateDisplay()
	
	#______________________________________________________________________
	
	def OnCopy(self, widget=None):
		self.OnCut(widget, False)
	
	#______________________________________________________________________
	
	def OnPaste(self, widget=None):
		if self.instrNameEntry:
			#if an instrument name is currently being edited
			self.instrNameEntry.paste_clipboard()
			return
	
		for instr in self.project.instruments:
			if instr.isSelected:
				for event in self.project.clipboardList:
					instr.addEventFromEvent(0, event)
				break
		
		self.UpdateDisplay()
	
	#______________________________________________________________________
	
	def OnDelete(self, widget=None):
		# Delete any select instruments
		for instr in self.project.instruments:
			if (instr.isSelected):
				#set not selected so when we undo we don't get two selected instruments
				instr.isSelected = False
				self.project.DeleteInstrument(instr.id)
			else:
				# Delete any selected events
				for ev in instr.events:
					if ev.isSelected:
						ev.Delete()
	
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
			self.compactmix = CompactMixView.CompactMixView(self.project, self)
			self.recording = RecordingView.RecordingView(self.project, self)
			
			# Add them to the main window
			self.main_vbox.pack_start(self.recording, True, True)
			
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
			self.window.set_title(_('Jokosher'))
			
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
		
		if 'GDK_CONTROL_MASK' in event.state.value_names:
			keysdict = {
				120:self.OnCut, # Ctrl-X
				99: self.OnCopy, # Ctrl-C
				118:self.OnPaste, # Ctrl-V
			}
		else:
			keysdict = {
				65471:self.OnRecordingView, # F2 - Recording View
				65472:self.OnCompactMixView, # F3 - Compact Mix View
				65535:self.OnDelete, # delete key - remove selected item
				65288:self.OnDelete, # backspace key
			}	
		
		if event.keyval in keysdict:
			keysdict[event.keyval]()
		
	#_____________________________________________________________________
	
	def OnInstrumentConnectonsDialog(self, widget):
		InstrumentConnectionsDialog.InstrumentConnectionsDialog(self.project, self)
		
	#_____________________________________________________________________
	
	def OnEditMenu(self, widget):
		#HACK: when the edit menu opens, check if any events or
		#instruments are selected and set the cut, copy, paste and delete accordingly
		instrSelected = False
		eventSelected = False
		for instr in self.project.instruments:
			if instr.isSelected:
				instrSelected = True
				break
			else:
				for ev in instr.events:
					if ev.isSelected:
						eventSelected = True
		
		self.cut.set_sensitive(instrSelected or eventSelected)
		self.copy.set_sensitive(instrSelected or eventSelected)
		self.paste.set_sensitive(instrSelected and bool(self.project.clipboardList))
		self.delete.set_sensitive(instrSelected or eventSelected)
	
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

	def OpenProjectFromPath(self,path, parent=None):
		try:
			self.SetProject(Project.LoadFromFile(path))
			return True
		except Project.OpenProjectError, e:
			self.ShowOpenProjectErrorDialog(e,parent)
			return False

	#_____________________________________________________________________
	
	
	def SetProject(self, project):
		try:
			project.ValidateProject()
		except Project.InvalidProjectError, e:
			message=""
			if e.files:
				message+=_("The project references non-existant files:\n")
				for f in e.files:
					message += f + "\n"
			if e.images:
				message+=_("\nThe project references non-existant images:\n")
				for f in e.images:
					message += f + "\n"

			dlg = gtk.MessageDialog(self.window,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_ERROR,
				gtk.BUTTONS_OK,
				_("%s\n Invalid or corrupt project file, will not open.")%message)
			dlg.run()
			dlg.destroy()
			return

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
	
	def CheckGstreamerVersions(self):
		#Check for CVS versions of Gstreamer and gnonlin
		message = ""
		v = gst.version()
		if (v[1] < 10) or (v[2] < 9):
			message += _("You must have Gstreamer version 0.10.9 or higher.\n")
		gnl = gst.registry_get_default().find_plugin("gnonlin")
		if gnl:
			ignored, gnlMajor, gnlMinor = gnl.get_version().split(".", 2)
			#Compare gnlMajor and gnlMinor as a float so later versions of gnonlin will work
			gnlMajor = float(gnlMajor)
			gnlMinor = float(gnlMinor)
			if gnlMajor < 10 or gnlMinor < 4.2:
				message += _("You must have Gstreamer plugin gnonlin version 0.10.4.2 or later.\n")
		elif not gnl:
			message += _("Gstreamer plugin gnonlin is not installed.") + \
			_("\nSee http://jokosher.org/trac/wiki/GettingJokosher for more details.\n")

		if not gst.registry_get_default().find_plugin("level"):
			message += _("You must have the Gstreamer plugin packs gst-plugins-base and gst-plugins-good installed.\n")
		if message:
			dlg = gtk.MessageDialog(self.window,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_WARNING,
				gtk.BUTTONS_CLOSE)
			dlg.set_markup(_("<big>Some functionality will not work correctly or at all.</big>\n\n%s") % message)
			dlg.run()
			dlg.destroy()
	
	#_____________________________________________________________________

	def SetStatusBar(self, message):
		return self.statusbar.Push(message)
	
	#_____________________________________________________________________

	def ClearStatusBar(self, messageID):
		self.statusbar.Remove(messageID)
	
	#_____________________________________________________________________

	def OnPreReleaseNotes(self, widget):
		dlg = gtk.MessageDialog(self.window,
			gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
			gtk.MESSAGE_WARNING,
			gtk.BUTTONS_CLOSE)
		dlg.set_markup(_("<big>Notes about this release</big>\n\nThis version of Jokosher (0.1) is a pre-release version, and is infact, our very first release. As such, you may encounter some bugs and functionality that is not present."))
		dlg.run()
		dlg.destroy()

	#_____________________________________________________________________

	def OnContributingDialog(self, widget):
		
		self.contribTree = gtk.glade.XML(Globals.GLADE_PATH, "ContributingDialog")

		self.topimage = self.contribTree.get_widget("topimage")
		self.topimage.set_from_file(os.path.join(Globals.IMAGE_PATH, "jokosher-logo.png"))
		
		# grab some references to bits of the GUI
		self.contribdialog = self.wTree.get_widget("ContributingDialog")
		#self.contribdialog.show_all()
		
	#_____________________________________________________________________
	
	def ShowOpenProjectErrorDialog(self, error, parent=None):
		if not parent:
			parent = self.window

		if error.errno==1:
			message = _("The URI scheme '%s' is either invalid or not supported."%error.info)
		elif error.errno==2:
			message = _("Unable to unzip the project file %s"%error.info)
		elif error.errno==3:		
			message = _("The project file was created with version \"%s\" of Jokosher.\n") % error.info + \
					  _("Projects from version \"%s\" are incompatible with this release.\n") % error.info
		elif error.errno==4:
			message = _("The project:\n%s\n\ndoes not exist.\n") % error.info
		else:
			message = _("The project file could not be opened.\n")

			
		dlg = gtk.MessageDialog(parent,
			gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
			gtk.MESSAGE_ERROR,
			gtk.BUTTONS_OK,
			message)
		dlg.set_icon(self.icon)
		dlg.run()
		dlg.destroy()
	
	#_____________________________________________________________________


#=========================================================================

def main():
	MainApp()
	gtk.threads_init()
	gtk.main()



if __name__ == "__main__":
	main()


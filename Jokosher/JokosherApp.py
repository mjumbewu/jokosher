#!/usr/bin/python
#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	Jokosher's main class. It creates the majority of the main window GUI
#	and gets everything up and running.
#
#-------------------------------------------------------------------------------

import pygtk
pygtk.require("2.0")
import gobject, gtk
import sys
import os.path
import pygst
pygst.require("0.10")
import gst
from subprocess import Popen, PIPE

import gettext
_ = gettext.gettext

import AddInstrumentDialog, TimeView, Workspace
import PreferencesDialog, ExtensionManagerDialog, RecordingView
import ProjectManager, Globals
import InstrumentConnectionsDialog
import EffectPresets, Extension, ExtensionManager
import Utils, AudioPreview
import PlatformUtils
import ui.StatusBar as StatusBar
import ProjectListDatabase

#=========================================================================

class MainApp:
	"""
	Jokosher's main class. It creates the majority of the main window GUI and 
	gets everything up and running.
	"""
	
	# Class Constants
	""" Constant value used to indicate Jokosher's recording mode  """
	MODE_RECORDING = 1
	
	""" Constant value used to indicate Jokosher's mixing mode  """
	MODE_COMPACT_MIX = 2

	#_____________________________________________________________________

	def __init__(self, openproject=None, loadExtensions=True, startuptype=None):
		"""
		Creates a new instance of MainApp.
		
		Parameters:
			openproject -- filename of the project to open at startup.
			loadExtensions -- whether the extensions should be loaded.
			startuptype -- determines the startup state of Jokosher:
							0 = Open the project referred by the openproject parameter.
							1 = Do not open the previous project.
		"""
		# create tooltip messages for buttons
		self.recTipEnabled = _("Stop recording")
		self.recTipDisabled = _("Arm an instrument, then click here to begin recording")
		self.recStopTipEnabled = _("Stop recording")
		self.recStopTipDisabled = _("Stop playback")
		self.mixingViewEnabledTip = _("Hide the audio level mixers")
		self.mixingViewDisabledTip = _("Show the audio level mixers")
		
		self.gtk_builder = Globals.LoadGtkBuilderFilename("MainWindow.ui")
		
		#Connect event handlers
		signals = {
			"on_MainWindow_destroy" : self.OnDestroy,
			"on_MainWindow_configure_event" : self.OnResize,
			"on_AddInstrument_clicked" : self.OnShowAddInstrumentDialog,
			"on_About_activate" : self.About,
			"on_Record_toggled" : self.Record, 
			"on_Play_clicked" : self.Play,
			"on_Stop_clicked" : self.Stop,
			"on_CompactMix_toggled" : self.OnCompactMixView,
			"on_export_activate" : self.OnExport,
			"on_preferences_activate" : self.OnPreferences,
			"on_open_activate" : self.OnOpenProject,
			"on_import_activate" : self.OnImportProject,
			"on_save_activate" : self.OnSaveProject,
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
			"on_instrumentconnections_activate" : self.OnInstrumentConnectionsDialog,
			"on_filemenu_activate" : self.OnFileMenu,
			"on_editmenu_activate" : self.OnEditMenu,
			"on_help_contents_activate" : self.OnHelpContentsMenu,
			"on_forums_activate" : self.OnForumsMenu,
			"on_contributing_activate" : self.OnContributingDialog,
			"on_ExtensionManager_activate" : self.OnExtensionManagerDialog,
			"on_instrumentmenu_activate" : self.OnInstrumentMenu,
			"on_instrMenu_add_audio" : self.OnAddAudio,
			"on_change_instr_type_activate" : self.OnChangeInstrument,
			"on_remove_instr_activate" : self.OnRemoveInstrument,
			"on_report_bug_activate" : self.OnReportBug,
			"on_project_add_audio" : self.OnAddAudioFile,
			"on_system_information_activate" : self.OnSystemInformation,
			"on_properties_activate" : self.OnProjectProperties,
			"on_openrecentbutton_clicked" : self.OnOpenRecentProjectButton,
		}
		self.gtk_builder.connect_signals(signals)
		
		# grab some references to bits of the GUI
		self.window = self.gtk_builder.get_object("MainWindow")
		self.play = self.gtk_builder.get_object("Play")
		self.stop = self.gtk_builder.get_object("Stop")
		self.record = self.gtk_builder.get_object("Record")
		self.save = self.gtk_builder.get_object("save")
		self.close = self.gtk_builder.get_object("close")
		self.reverse = self.gtk_builder.get_object("Rewind")
		self.forward = self.gtk_builder.get_object("Forward")
		self.addInstrumentButton = self.gtk_builder.get_object("AddInstrument")
		self.compactMixButton = self.gtk_builder.get_object("CompactMix")
		self.editmenu = self.gtk_builder.get_object("editmenu")
		self.filemenu = self.gtk_builder.get_object("filemenu")
		self.undo = self.gtk_builder.get_object("undo")
		self.redo = self.gtk_builder.get_object("redo")
		self.cut = self.gtk_builder.get_object("cut")
		self.copy = self.gtk_builder.get_object("copy")
		self.paste = self.gtk_builder.get_object("paste")
		self.delete = self.gtk_builder.get_object("delete")
		self.instrumentMenu = self.gtk_builder.get_object("instrumentmenu")
		self.export = self.gtk_builder.get_object("export")
		self.recentprojects = self.gtk_builder.get_object("recentprojects")
		self.recentprojectsmenu = self.gtk_builder.get_object("recentprojects_menu")
		self.menubar = self.gtk_builder.get_object("menubar")
		self.toolbar = self.gtk_builder.get_object("MainToolbar")
		self.addAudioMenuItem = self.gtk_builder.get_object("add_audio_file_instrument_menu")
		self.changeInstrMenuItem = self.gtk_builder.get_object("change_instrument_type")
		self.removeInstrMenuItem = self.gtk_builder.get_object("remove_selected_instrument")
		self.addAudioFileButton = self.gtk_builder.get_object("addAudioFileButton")
		self.addAudioFileMenuItem = self.gtk_builder.get_object("add_audio_file_project_menu")
		self.addInstrumentFileMenuItem = self.gtk_builder.get_object("add_instrument1")
		self.recordingInputsFileMenuItem = self.gtk_builder.get_object("instrument_connections1")
		self.timeFormatFileMenuItem = self.gtk_builder.get_object("time_format1")
		self.properties_menu_item = self.gtk_builder.get_object("project_properties")
		self.welcome_pane = self.gtk_builder.get_object("WelcomePane")
		self.recent_projects_tree = self.gtk_builder.get_object("recent_projects_tree")
		self.recent_projects_button = self.gtk_builder.get_object("recent_projects_button")
		
		self.project_database_list = ProjectListDatabase.ProjectItemList()
		
		self.project = None
		self.headerhbox = None
		self.timeview = None
		self.tvtoolitem = None #wrapper for putting timeview in toolbar
		self.workspace = None
		self.instrNameEntry = None #the gtk.Entry when editing an instrument name
		self.main_vbox = self.gtk_builder.get_object("main_vbox")
		
		self.statusbar = StatusBar.StatusBar()
		self.main_vbox.pack_end(self.statusbar, False)
		
		# Initialise some useful vars
		self.mode = None
		self.settingButtons = True
		self.compactMixButton.set_active(False)
		self.settingButtons = False
		self.isRecording = False
		self.isPlaying = False
		self.isPaused = False

		# Intialise context sensitive tooltips for workspace buttons
		self.compactMixButton.set_tooltip_text(self.mixingViewDisabledTip)
		
		# set the window size to the last saved value
		x = int(Globals.settings.general["windowwidth"])
		y = int(Globals.settings.general["windowheight"])
		self.window.resize(x, y)
		
		# Connect up the forward and reverse handlers. We can't use the autoconnect as we need child items
		innerbtn = self.reverse.get_children()[0]
		innerbtn.connect("pressed", self.OnRewindPressed)
		innerbtn.connect("released", self.OnRewindReleased)
		
		innerbtn = self.forward.get_children()[0]
		innerbtn.connect("pressed", self.OnForwardPressed)
		innerbtn.connect("released", self.OnForwardReleased)
		
		jokosher_logo_path = os.path.join(Globals.IMAGE_PATH, "jokosher-logo.png")
		self.jokosher_logo_pixbuf = gtk.gdk.pixbuf_new_from_file(jokosher_logo_path)
		
		miximg = gtk.Image()
		miximg.set_from_file(os.path.join(Globals.IMAGE_PATH, "icon_mix.png"))	
		self.compactMixButton.set_icon_widget(miximg)
		miximg.show()
		
		#get the audiofile image from Globals
		self.audioFilePixbuf = Globals.getCachedInstrumentPixbuf("audiofile")
		
		audioimg = gtk.Image()
		size = gtk.icon_size_lookup(gtk.ICON_SIZE_MENU)
		pixbuf = self.audioFilePixbuf.scale_simple(size[0], size[1], gtk.gdk.INTERP_BILINEAR)
		audioimg.set_from_pixbuf(pixbuf)
		# set the add audio menu item icon
		self.addAudioMenuItem.set_image(audioimg)
		
		size = gtk.icon_size_lookup(self.toolbar.get_icon_size())
		pixbuf = self.audioFilePixbuf.scale_simple(size[0], size[1], gtk.gdk.INTERP_BILINEAR)
		audioimg = gtk.Image()
		audioimg.set_from_pixbuf(pixbuf)	
		self.addAudioFileButton.set_icon_widget(audioimg)
		audioimg.show()
		
		self.recent_projects_tree_model = gtk.ListStore(str, object, str)
		self.recent_projects_tree.set_model(self.recent_projects_tree_model)
		# populate the Recent Projects menu
		self.OpenRecentProjects()
		self.PopulateRecentProjects()
		
		# set up recent projects treeview with a ListStore model. We also
		# use CellRenderPixbuf as we are using icons for each entry
		tvcolumn = gtk.TreeViewColumn()
		cellpb = gtk.CellRendererPixbuf()
		cell = gtk.CellRendererText()
		
		tvcolumn.pack_start(cellpb, False)
		tvcolumn.pack_start(cell, True)
		
		tvcolumn.set_attributes(cellpb, stock_id=0)
		tvcolumn.set_attributes(cell, text=2)
		
		self.recent_projects_tree.append_column(tvcolumn)
		self.recent_projects_tree.connect("row-activated", self.OnRecentProjectSelected)
		
		# set sensitivity
		self.SetGUIProjectLoaded()
		
		# set window icon
		icon_theme = gtk.icon_theme_get_default()
		try:
			pixbuf = icon_theme.load_icon("jokosher", 48, 0)
			self.window.set_icon(pixbuf)
		except gobject.GError, exc:
			self.window.set_icon_from_file(os.path.join(Globals.IMAGE_PATH, "jokosher.png"))
		# make icon available to others
		self.window.realize()
		self.icon = self.window.get_icon()
		
		
		self.window.add_events(gtk.gdk.KEY_PRESS_MASK)
		self.window.connect_after("key-press-event", self.OnKeyPress)
		self.window.connect("button_press_event", self.OnMouseDown)

		self.CheckGstreamerVersions()

		# set up presets registry - this should probably be removed here	
		EffectPresets.EffectPresets()
		Globals.PopulateEncoders()
		Globals.PopulateAudioBackends()
		
		if loadExtensions:
			# Load extensions -- this should probably go somewhere more appropriate
			self.extensionManager = ExtensionManager.ExtensionManager(self)

		## Setup is complete so start up the GUI and perhaps load a project
		## any new setup code needs to go above here
		
		# Show the main window
		self.window.show_all()
		if len(self.recent_projects_tree_model) > 0:
			self.recent_projects_tree.set_cursor( (0,) ) # the highlight the first item
			self.recent_projects_button.grab_focus()

		# command line options override preferences so check for them first,
		# then use choice from preferences
		if startuptype == 1: # no-project cmdline switch
			return
		elif openproject: # a project name on the cmdline
			self.OpenProjectFromPath(openproject)
		elif Globals.settings.general["startupaction"] == PreferencesDialog.STARTUP_LAST_PROJECT:
			if self.lastopenedproject:
				self.OpenProjectFromPath(self.lastopenedproject[0])
		elif Globals.settings.general["startupaction"] == PreferencesDialog.STARTUP_NOTHING:
			return

		self.welcome_background = None
		# Uncomment this next line to draw a nice background on the welcome pane
		#self.welcome_background = gtk.gdk.pixbuf_new_from_file("my-alpha-background.png")
		if self.welcome_background:
			self.welcome_pane.connect_after("expose-event", self.OnWelcomePaneExpose)

	#_____________________________________________________________________
	
	def OnWelcomePaneExpose (self, widget, event):
		"""
		Draw a pretty picture to the background of the welcome pane.
		
		Parameters:
			widget -- GTK callback parameter.
			event -- GTK callback parameter.
		"""
		if not self.welcome_background:
			return False
		
		flags = widget.flags()
		if flags & gtk.VISIBLE and flags & gtk.MAPPED:
			if not flags & gtk.NO_WINDOW and not flags & gtk.APP_PAINTABLE:
				widget.window.draw_pixbuf(widget.style.white_gc, self.welcome_background, 0, 0, 0, 0);
				
	#_____________________________________________________________________
	
	def OnCompactMixView(self, button=None):
		"""
		Updates the main window after switching to the compact view mixing mode.
		
		Parameters:
			button -- Button object calling this method.
		"""
		if self.workspace:
			self.workspace.ToggleCompactMix()

	#_____________________________________________________________________


	def OnF3Pressed(self):
		"""
		Toggle to compact mix view button when F3 is pressed.
		"""

		self.compactMixButton.set_active(not self.compactMixButton.get_active())

	#_____________________________________________________________________
	
	def OnResize(self, widget, event):
		"""
		Called when the main window gets resized.
		
		Parameters:
			widget -- GTK callback parameter.
			event -- GTK callback parameter.
			
		Returns:
			False -- continue GTK signal propagation.
		"""
		(self.width, self.height) = widget.get_size()
		
		return False
	
	#_____________________________________________________________________
	
	def OnDestroy(self, widget=None, event=None):
		"""
		Called when the main window is destroyed.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		
		Returns:
			True -- the current project can't be properly closed.
					This stops signal propagation.
		"""
		# save the current window size
		Globals.settings.general["windowwidth"] = self.width
		Globals.settings.general["windowheight"] = self.height
		Globals.settings.write()
		
		if self.CloseProject() == 0:
			gtk.main_quit()
		else:
			return True #stop signal propogation
		
	#_____________________________________________________________________
	
	def OnShowAddInstrumentDialog(self, widget=None):
		"""
		Creates and shows the "Add Instrument" dialog box.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		AddInstrumentDialog.AddInstrumentDialog(self.project, self)
	
	#_____________________________________________________________________

	def OnChangeInstrument(self, widget=None):
		"""
		Changes the type of the selected Instrument.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.	
		"""
		# Change the type of a select instrument
		for instr in self.project.instruments:
			if (instr.isSelected):
				AddInstrumentDialog.AddInstrumentDialog(self.project, self, instr)
				return
	
	#_____________________________________________________________________
	
	def About(self, widget=None):
		"""
		Creates and shows the "About" dialog box.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		gtk.about_dialog_set_url_hook(self.AboutLinkActivate)
		gtk_builder = Globals.LoadGtkBuilderFilename("AboutDialog.ui")
		dlg = gtk_builder.get_object("AboutDialog")
		dlg.set_transient_for(self.window)
		dlg.set_icon(self.icon)
		dlg.set_logo(self.jokosher_logo_pixbuf)
		dlg.run()
		dlg.destroy()
		
	#_____________________________________________________________________

	def AboutLinkActivate(self, widget, link):
		"""
		Opens the Jokosher website in the user's default web browser.

		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		Utils.OpenExternalURL(url=link, message=_("<big>Couldn't launch the jokosher website automatically.</big>\n\nPlease visit %s to access it."), parent=self.window)
		
	#_____________________________________________________________________
	
	def OnReportBug(self, widget):
		"""
		Opens the report bug launchpad website in the user's default web browser.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		Utils.OpenExternalURL(url="https://bugs.launchpad.net/jokosher/+filebug/", message=_("<big>Couldn't launch the launchpad website automatically.</big>\n\nPlease visit %s to access it."), parent=self.window)
		
	#_____________________________________________________________________

	def Record(self, widget=None):
		"""
		Toggles recording. If there's an error, a warning/error message is 
		issued to the user.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		# toggling the record button invokes this function so we use the settingButtons var to 
		# indicate that we're just changing the GUI state and dont need to do anything code-wise
		if self.settingButtons:
			return
		
		if self.isRecording:
			self.project.Stop()
			return
		
		canRecord = False
		for i in self.project.instruments:
			if i.isArmed:
				canRecord = True

		#Check to see if any instruments are trying to use the same input channel
		usedChannels = []
		armed_instrs = [x for x in self.project.instruments if x.isArmed]
		for instrA in armed_instrs:
			for instrB in armed_instrs:
				if instrA is not instrB and instrA.input == instrB.input and instrA.inTrack == instrB.inTrack:
					string = _("The instruments '%(name1)s' and '%(name2)s' both have the same input selected. Please either disarm one, or connect it to a different input through 'Project -> Recording Inputs'")
					message = string % {"name1" : instrA.name, "name2" : instrB.name}
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

		if not canRecord:
			Globals.debug("can not record")
			if self.project.instruments:
				errmsg = "No instruments are armed for recording. You need to arm an instrument before you can begin recording."
			else:
				errmsg = "No instruments have been added. You must add an instrument before recording"
			dlg = gtk.MessageDialog(self.window,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_INFO,
				gtk.BUTTONS_CLOSE,
				_(errmsg))
			dlg.connect('response', lambda dlg, response: dlg.destroy())
			dlg.run()
			self.settingButtons = True
			widget.set_active(False)
			self.settingButtons = False
		else:
			Globals.debug("can record")
			self.project.Record()

	#_____________________________________________________________________
	
	def TogglePlayIcon(self):
		"""
		Changes the play button icon/tooltip from play to pause and viceversa.
		"""
		if not self.isPlaying:
			self.play.set_stock_id(gtk.STOCK_MEDIA_PLAY)
		else:
			self.play.set_stock_id(gtk.STOCK_MEDIA_PAUSE)
		
		# TODO: change the tooltips in 1.0
		#self.contextTooltips.set_tip(play, tooltip)
		
	#_____________________________________________________________________
	
	def Play(self, widget=None):
		"""
		Toggles playback.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""

		if self.settingButtons == True:
			return 

		self.TogglePlayIcon()
		if not self.isPlaying:
			self.project.Play()
		else:
			self.project.Pause()

	#_____________________________________________________________________

	#The stop button is really just an alias for toggling play/record to off
	def Stop(self, widget=None):
		"""
		Stops the current record/playback (whichever is happening) operation.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""

		self.project.Stop()

	#_____________________________________________________________________

	def OnRewindPressed(self, widget=None):
		"""
		Starts moving backward within the project's timeline.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.project.transport.Reverse(True)
		
	#_____________________________________________________________________
		
	def OnRewindReleased(self, widget=None):
		"""
		Stops the current rewind operation.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.project.transport.Reverse(False)
		
	#_____________________________________________________________________
		
	def OnForwardPressed(self, widget=None):
		"""
		Starts moving forward within the project's timeline.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.project.transport.Forward(True)
		
	#_____________________________________________________________________
		
	def OnForwardReleased(self, widget=None):
		"""
		Stops the current forward operation.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.project.transport.Forward(False)
	
	#_____________________________________________________________________
	
	def OnExport(self, widget=None):
		"""
		Creates and shows a save file dialog which allows the user to export
		the project as ogg or mp3.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		buttons = (gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK)
		chooser = gtk.FileChooserDialog(_("Export Project"), self.window, gtk.FILE_CHOOSER_ACTION_SAVE, buttons)
		if os.path.exists(Globals.settings.general["projectfolder"]):
			chooser.set_current_folder(Globals.settings.general["projectfolder"])
		else:
			chooser.set_current_folder(os.path.expanduser("~"))
		chooser.set_do_overwrite_confirmation(True)
		chooser.set_default_response(gtk.RESPONSE_OK)
		chooser.set_current_name(self.project.name)

		sampleRateHBox = gtk.HBox()
		sampleRateLabel = gtk.Label(_("Sample rate:"))
		sampleRateCombo = gtk.combo_box_new_text()
		sampleRateHBox.pack_start(sampleRateLabel, False, False, 10)
		sampleRateHBox.pack_start(sampleRateCombo, False, False, 10)
		bitRateLabel = gtk.Label(_("Bit rate:"))
		bitRateCombo = gtk.combo_box_new_text()
		bitRateHBox = gtk.HBox()
		bitRateHBox.pack_start(bitRateLabel, False, False, 10)
		bitRateHBox.pack_start(bitRateCombo, False, False, 10)
		saveLabel = gtk.Label(_("Save as file type:"))		
		typeCombo = gtk.combo_box_new_text()
		typeCombo.connect("changed", self.OnExportFormatChanged, sampleRateHBox, bitRateHBox)
		
		for frmt in Globals.EXPORT_FORMATS:
			typeCombo.append_text("%s (.%s)" % (frmt["description"], frmt["extension"]))
		#Make the first item the default
		typeCombo.set_active(0)

		for index, samplerate in enumerate(Globals.SAMPLE_RATES):
			sampleRateCombo.append_text("%d Hz" % samplerate)
			if samplerate == Globals.DEFAULT_SAMPLE_RATE:
				sampleRateCombo.set_active(index)
		
		for index, bitrate in enumerate(Globals.BIT_RATES):
			bitRateCombo.append_text("%d kbps" % bitrate)
			if bitrate == Globals.DEFAULT_BIT_RATE:
				bitRateCombo.set_active(index)

		extraHBox = gtk.HBox()
		extraHBox.pack_start(sampleRateHBox, False)
		extraHBox.pack_start(bitRateHBox, False)
		extraHBox.pack_end(typeCombo, False, False, 10)
		extraHBox.pack_end(saveLabel, False, False, 10)
		extraHBox.show_all()
		chooser.set_extra_widget(extraHBox)
		
		response = chooser.run()
		if response == gtk.RESPONSE_OK:
			exportFilename = chooser.get_filename()
			Globals.settings.general["projectfolder"] = os.path.dirname(exportFilename)
			Globals.settings.write()
			#If they haven't already appended the extension for the 
			#chosen file type, add it to the end of the file.
			filetypeDict = Globals.EXPORT_FORMATS[typeCombo.get_active()]
			if not exportFilename.lower().endswith("." + filetypeDict["extension"]):
				exportFilename += "." + filetypeDict["extension"]
		
			if sampleRateHBox.get_property("visible"):
				samplerate = Globals.SAMPLE_RATES[sampleRateCombo.get_active()]
			else:
				samplerate = None
			if bitRateHBox.get_property("visible"):
				bitrate = Globals.BIT_RATES[bitRateCombo.get_active()]
				if filetypeDict["extension"] == "ogg":
					# vorbisenc takes bit rate in bps instead of kbps
					bitrate *= 1024
			else:
				bitrate = None

			chooser.destroy()
			self.project.Export(exportFilename, filetypeDict["pipeline"], samplerate, bitrate)
		else:
			chooser.destroy()
		
	#_____________________________________________________________________

	def OnExportFormatChanged(self, typeCombo, sampleRateHBox, bitRateHBox):
		"""
		Updates the export file chooser dialog's setting options to make sure
		that they're appropriate for the selected format.
		"""

		format_def = Globals.EXPORT_FORMATS[typeCombo.get_active()]
		if format_def["setSampleRate"]:
			sampleRateHBox.show()
		else:
			sampleRateHBox.hide()

		if format_def["setBitRate"]:
			bitRateHBox.show()
		else:
			bitRateHBox.hide()

	#_____________________________________________________________________
	
	def UpdateExportDialog(self):
		"""
		Updates the progress bar corresponding to the current export operation.
		"""
		progress = self.project.GetExportProgress()
		if progress[0] == -1 or progress[1] == 0:
			self.exportprogress.set_fraction(0.0)
			self.exportprogress.set_text(_("Preparing to mixdown project"))
		elif progress[0] == progress[1] == 100:
			self.exportdlg.destroy()
			return False
		else:
			self.exportprogress.set_fraction(progress[0]/progress[1])
			self.exportprogress.set_text(_("%(progress)d%% of %(total)d seconds completed") % {"progress":(progress[0]/progress[1]*100), "total":progress[1] } )
			
		return True
	
	#_____________________________________________________________________
	
	def OnExportCancel(self, widget=None):
		"""
		Cancels a running export operation and destroys the export progress dialog.
		
		Parameters:
			widget: reserved for GTK callbacks, don't use it explicitly.
		"""
		self.exportdlg.destroy()
		self.project.TerminateExport()
	
	#_____________________________________________________________________
	
	def OnPreferences(self, widget, destroyCallback=None):
		"""
		Creates and shows the "Jokosher Preferences" dialog.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			destroyCallback -- function that'll get called when the preferences 
								dialog gets destroyed.
		"""
		prefsdlg = PreferencesDialog.PreferencesDialog(self.project, self, self.icon)
			
		if destroyCallback:
			prefsdlg.dlg.connect("destroy", destroyCallback)
	
	#_____________________________________________________________________
	
	def OnShowBarsBeats(self, widget):
		"""
		Sets and updates the current timeline view to Bars, Beats and Ticks.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.settingButtons:
			return
		if widget.get_active() and self.project and self.project.transport:
			self.project.SetTransportMode(self.project.transport.MODE_BARS_BEATS)
		
	#_____________________________________________________________________
	
	def OnShowHoursMins(self, widget):
		"""
		Sets and updates the current timeline view to Hours, Minutes and Seconds.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.settingButtons:
			return
		if widget.get_active() and self.project and self.project.transport:
			self.project.SetTransportMode(self.project.transport.MODE_HOURS_MINS_SECS)
		
	#_____________________________________________________________________
	
	def OnOpenProject(self, widget):
		self.OnCloseProject()
	
	#_____________________________________________________________________

	def OnImportProject(self, widget, destroyCallback=None):
		"""
		Creates and shows a open file dialog which allows the user to open
		an existing Jokosher project.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			destroyCallback -- function that'll get called when the open file
								dialog gets destroyed.
		"""
		chooser = gtk.FileChooserDialog(
		        title=_('Choose a Jokosher project file'),
		        parent=self.window,
		        action=gtk.FILE_CHOOSER_ACTION_OPEN,
		        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		
		if os.path.exists(Globals.settings.general["projectfolder"]):
			chooser.set_current_folder(Globals.settings.general["projectfolder"])
		else:
			chooser.set_current_folder(os.path.expanduser("~"))

		chooser.set_default_response(gtk.RESPONSE_OK)
		allfilter = gtk.FileFilter()
		allfilter.set_name(_("All Files"))
		allfilter.add_pattern("*")
		
		jokfilter = gtk.FileFilter()
		jokfilter.set_name(_("Jokosher Project Files (*.jokosher)"))
		jokfilter.add_pattern("*.jokosher")
		
		chooser.add_filter(jokfilter)
		chooser.add_filter(allfilter)
		
		if destroyCallback:
			chooser.connect("destroy", destroyCallback)
		
		response = chooser.run()
		
		if response == gtk.RESPONSE_OK:
			
			filename = chooser.get_filename()
			Globals.settings.general["projectfolder"] = os.path.dirname(filename)
			Globals.settings.write()

			uri = chooser.get_uri()
			chooser.destroy()

			try:
				new_project_file = ProjectManager.ImportProject(uri)
			except ProjectManager.OpenProjectError, e:
				self.ShowOpenProjectErrorDialog(e, self.window)
			
			if new_project_file:
				self.OpenProjectFromPath(new_project_file, chooser)
			else:
				dlg = gtk.MessageDialog(
				        parent=self.window,
				        flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				        type=gtk.MESSAGE_ERROR,
				        buttons=gtk.BUTTONS_OK,
				        message_format=_("An error occurred and the project could not be imported."))
				dlg.run()
				dlg.destroy()
		else:
			chooser.destroy()
		
	#_____________________________________________________________________
		
	def OnSaveProject(self, widget=None):
		"""
		Saves the current project file.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""	
		if self.project:
			self.project.SelectInstrument(None)
			self.project.ClearEventSelections()
			self.project.SaveProjectFile()
			
	#_____________________________________________________________________
	
	def OnNewProject(self, widget):
		"""
		Tries to create a new Project inside the Jokosher data directory.
		If the process fails, a message is issued to the user stating the error.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		name = _("New Project")
		author = _("Unknown Author")
			
		try:
			project = ProjectManager.CreateNewProject(name, author)
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
			
			# show the error dialog with the relevant error message	
			dlg = gtk.MessageDialog(self.dlg,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_ERROR,
				gtk.BUTTONS_OK,
				_("Unable to create project.\n\n%s") % message)
			dlg.run()
			dlg.destroy()
		else:
			self.SetProject(project)
		
	#_____________________________________________________________________
		
	def OnCloseProject(self, widget=None):
		"""
		Closes the current project by calling CloseProject(). 
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.CloseProject() == 0:
			self.SetGUIProjectLoaded()
	#_____________________________________________________________________
	
	def CloseProject(self):
		"""
		Closes the current project. If there's changes pending, it'll ask the user for confirmation.
		
		Returns:
			the status of the close operation:
			0 = there was no project open or it was closed succesfully.
			1 = cancel the operation and return to the normal program flow.
		"""
		if not self.project:
			return 0
		
		self.Stop()
		
		"""
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
			"""
		
		if self.project.CheckUnsavedChanges():
			self.OnSaveProject()
			self.project.CloseProject()
		elif self.project.newly_created_project:
			self.project.CloseProject()
			ProjectManager.DeleteProjectLocation(self.project)

		self.project = None
		self.mode = None
		return 0
		
	#_____________________________________________________________________
	
	def OnUndo(self, widget):
		"""
		Undoes the last change made to the project and updates the displays.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.project.Undo()
		
	#_____________________________________________________________________
	
	def OnRedo(self, widget):
		"""
		Redoes the last undo operation and updates the displays.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.project.Redo()

	#_____________________________________________________________________
	
	def OnProjectAudioState(self, project):
		"""
		Callback for when the project starts playing or recording, or when it is
		paused or stopped.
		
		Parameters:
			project -- The project instance that send the signal.
		"""
		self.isPlaying = (self.project.audioState == self.project.AUDIO_PLAYING)
		self.isPaused = (self.project.audioState == self.project.AUDIO_PAUSED)
		self.isRecording = (self.project.audioState == self.project.AUDIO_RECORDING)
		self.stop.set_sensitive(True)	#stop should always be clickable
		self.record.set_sensitive(not self.isPlaying)
		
		controls = (self.play, self.reverse, self.forward, self.editmenu, self.instrumentMenu, 
				self.workspace.recordingView.timelinebar.headerhbox, 
				self.addInstrumentButton, self.addAudioFileButton)
		for widget in controls:
			widget.set_sensitive(not self.isRecording)
		
		self.settingButtons = True
		self.record.set_active(self.isRecording)
		self.TogglePlayIcon()
		self.settingButtons = False
		
		# update the tooltips depending on the current recording state
		if self.isRecording:
			self.record.set_tooltip_text(self.recTipEnabled)
			self.stop.set_tooltip_text(self.recStopTipEnabled)
		else:
			self.record.set_tooltip_text(self.recTipDisabled)
			self.stop.set_tooltip_text(self.recStopTipDisabled)
		
		self.workspace.mixView.StartUpdateTimeout()
	
	#_____________________________________________________________________
	
	def OnProjectExportStart(self, project):
		"""
		Callback for when the project starts exporting audio to a file.
		
		Parameters:
			project -- The project instance that send the signal.
		"""
		gtk_builder = Globals.LoadGtkBuilderFilename("ProgressDialog.ui")
		gtk_builder.connect_signals({"on_cancel_clicked": self.OnExportCancel})
		
		self.exportdlg = gtk_builder.get_object("ProgressDialog")
		self.exportdlg.set_icon(self.icon)
		self.exportdlg.set_transient_for(self.window)
		
		label = gtk_builder.get_object("progressLabel")
		label.set_text(_("Mixing project to file: %s") % self.project.exportFilename)
		
		self.exportprogress = gtk_builder.get_object("progressBar")
		
		gobject.timeout_add(100, self.UpdateExportDialog)
		
	#_____________________________________________________________________
	
	
	def OnProjectExportStop(self, project):
		"""
		Callback for when the project has finished exporting audio to a file.
		
		Parameters:
			project -- The project instance that send the signal.
		"""
		if self.exportdlg:
			self.exportdlg.destroy()
	
	#_____________________________________________________________________
	
	def OnProjectNameChanged(self, project, new_name):
		"""
		Callback for when the project's name changes.
		"""
		
		self.project_database_list.UpdateName(self.project.projectfile, new_name)
		self.SaveRecentProjects()
		self.PopulateRecentProjects()
	
	#_____________________________________________________________________
	
	def OnProjectUndo(self, project=None):
		"""
		Callback for when the project's undo or redo stacks change.
		
		Parameters:
			project -- The project instance that send the signal.
		"""
		self.undo.set_sensitive(self.project.CanPerformUndo())
		self.redo.set_sensitive(self.project.CanPerformRedo())
	
		if self.project.CheckUnsavedChanges():
			self.window.set_title(_('*%s - Jokosher') % self.project.name)
		else:
			self.window.set_title(_('%s - Jokosher') % self.project.name)
		
	#_____________________________________________________________________
	
	def OnTransportMode(self, transportManager=None, mode=None):
		"""
		Callback for signal when the transport mode changes.
		
		Parameters:
			transportManager -- the TransportManager instance that send the signal.
			mode -- the mode type that the transport changed to.
		"""
		if self.settingButtons:
			return
		self.settingButtons = True
		modeBars = self.gtk_builder.get_object("show_as_bars_beats_ticks")
		modeHours = self.gtk_builder.get_object("show_as_hours_minutes_seconds")
		transport = self.project.transport
		
		modeBars.set_active(transport.mode == transport.MODE_BARS_BEATS)
		modeHours.set_active(transport.mode == transport.MODE_HOURS_MINS_SECS)
		
		self.settingButtons = False
		
	#_____________________________________________________________________

	def UpdateProjectLastUsedTime(self, path, name):
		"""
		Inserts a new project with its corresponding path to the recent project list.
		
		Parameters:
			path -- path to the project file.
			name -- name of the project being added.
		"""
		
		if self.project_database_list.Contains(path):
			self.project_database_list.UpdateLastUsedTime(path)
		else:
			self.project_database_list.AddProjectItem(path, name)
		
		self.SaveRecentProjects()
		self.PopulateRecentProjects()

	#_____________________________________________________________________
	
	def PopulateRecentProjects(self):
		"""
		Populates the Recent Projects menu with items from self.project_database_list.
		"""	
		
		MAX_PROJECTS_SHOWN = 4
		
		menuitems = self.recentprojectsmenu.get_children()
		for c in menuitems:
			self.recentprojectsmenu.remove(c)
		
		if self.project_database_list:
			ordered_project_items = self.project_database_list.GetOrderedItems()
			for item in ordered_project_items[:MAX_PROJECTS_SHOWN]:
				mitem = gtk.MenuItem(item.name)
				self.recentprojectsmenu.append(mitem)
				mitem.connect("activate", self.OnRecentProjectsItem, item)
			
			mitem = gtk.SeparatorMenuItem()
			self.recentprojectsmenu.append(mitem)
			
			if len(ordered_project_items) > MAX_PROJECTS_SHOWN:
				menu_text = _("Show all %d projects") % len(ordered_project_items)
			else:
				menu_text = _("Show all projects")
			
			mitem = gtk.MenuItem(menu_text)
			mitem.set_tooltip_text(_("Close the current project, and show all available projects"))
			self.recentprojectsmenu.append(mitem)
			# To show all projects we close the project, which shows the welcome screen
			mitem.connect("activate", self.OnCloseProject)

			self.recentprojects.set_sensitive(True)
			self.recentprojectsmenu.show_all()
			
			#Update the welcome screen
			self.recent_projects_tree_model.clear()
			for item in ordered_project_items:	
				self.recent_projects_tree_model.append([gtk.STOCK_NEW, item, item.name])
			
		else:
			#there are no items, so just make it insensitive
			self.recentprojects.set_sensitive(False)
			
			self.recent_projects_tree_model.clear()
		
	#_____________________________________________________________________
	
	def OpenRecentProjects(self):
		"""
		Load the self.project_database_list with items from global settings.
		"""
		
		if Globals.settings.recentprojects['paths'] == "":
			if Globals.settings.general['recentprojects'] != "":
				# this is a first run; import the old recent projects
				imports = ProjectListDatabase.GetOldRecentProjects()
				for path, name in imports:
					self.project_database_list.AddProjectItem(path, name)
				
				ProjectListDatabase.StoreProjectItems(self.project_database_list)
				Globals.settings.general['recentprojects'] = ""
				Globals.settings.write()
		else:
			self.project_database_list = ProjectListDatabase.LoadProjectItems()
			
		self.project_database_list.PurgeNonExistantPaths()
		
	#_____________________________________________________________________
	
	def OnRecentProjectsItem(self, widget, project_item):
		"""
		Opens the project selected from the "Recent Projects" drop-down menu.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			path -- path to the project file.
			name -- name of the project being opened.
		"""
		return self.OpenProjectFromPath(project_item.path)

	#_____________________________________________________________________
	
	def OnRecentProjectSelected(self, treeview, path, view_column):
		"""
		This method is called when one of the entries in the recent projects
		list is selected.
		
		Parameters:
			treeview -- reserved for GTK callbacks, don't use it explicitly.
			path -- reserved for GTK callbacks, don't use it explicitly.
			view_column -- reserved for GTK callbacks, don't use it explicitly.
		"""
		item = self.recent_projects_tree_model[path][1]
		response = self.OnRecentProjectsItem(treeview, item)
		
	#_____________________________________________________________________
	
	def OnOpenRecentProjectButton(self, widget):
		"""
		Loads the selected recent project.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		path = self.recent_projects_tree.get_cursor()[0]
		if path:
			item = self.recent_projects_tree_model[path][1]
			self.OnRecentProjectsItem(self, item)
	
	#_____________________________________________________________________

	def SaveRecentProjects(self):
		"""
		Saves the list of the previously used projects to the Jokosher config file.
		"""
		
		ProjectListDatabase.StoreProjectItems(self.project_database_list)
		
	#______________________________________________________________________
	
	def OnCut(self, widget=None, cut=True):
		"""
		Cuts the portion of selected audio and puts it in the clipboard.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			cut --  determines whether the operation should perform a cut or copy operation:
					True = perform a cut operation.
					False = perform a copy operation.
		"""
		if self.isPlaying or self.isPaused:
			return
		
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
	
	#______________________________________________________________________
	
	def OnCopy(self, widget=None):
		"""
		Copies the portion of selected audio to the clipboard.	
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.OnCut(widget, False)
	
	#______________________________________________________________________
	
	def OnPaste(self, widget=None):
		"""
		Pastes the portion of audio in the clipboard to the selected instrument,
		at the selected position in time.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.isPlaying or self.isPaused:
			return
		
		if self.instrNameEntry:
			#if an instrument name is currently being edited
			self.instrNameEntry.paste_clipboard()
			return
	
		for instr in self.project.instruments:
			if instr.isSelected:
				for event in self.project.clipboardList:
					instr.addEventFromEvent(0, event)
				break
	
	#______________________________________________________________________
	
	def OnDelete(self, widget=None):
		"""
		Deletes the currently selected instruments or events.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.project.GetIsRecording() or self.isPlaying or self.isPaused:
			return
		
		# list to store instruments to delete, so we don't modify the list while we are iterating
		instrOrEventList = []
		eventList = []
		# Delete any select instruments
		for instr in self.project.instruments:
			if (instr.isSelected):
				#set not selected so when we undo we don't get two selected instruments
				instr.isSelected = False
				instrOrEventList.append(instr)
			else:
				# Delete any selected events
				for ev in instr.events:
					if ev.isSelected:
						instrOrEventList.append(ev)

		if instrOrEventList:
			self.project.DeleteInstrumentsOrEvents(instrOrEventList)
	
	#______________________________________________________________________

	def OnMouseDown(self, widget, mouse):
		"""
		If there's a project open, clears event and instrument selections.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.project:
			self.project.ClearEventSelections()
			self.project.SelectInstrument(None)
		
	#______________________________________________________________________
	
	def SetGUIProjectLoaded(self):
		"""
		Refreshes the main window and it's components when a project is opened or closed.
		For example, buttons are enabled/disabled whether there's a project currently open or not. 
		"""
		children = self.main_vbox.get_children()
		if self.workspace in children:
			self.main_vbox.remove(self.workspace)
		if self.welcome_pane in children:
			self.main_vbox.remove(self.welcome_pane)
		
		if self.headerhbox in children:
			self.main_vbox.remove(self.headerhbox)
		if self.tvtoolitem in self.toolbar.get_children():
			self.toolbar.remove(self.tvtoolitem)
		
		ctrls = (self.save, self.close, self.addInstrumentButton, self.addAudioFileButton,
			self.reverse, self.forward, self.play, self.stop, self.record,
			self.instrumentMenu, self.export, self.cut, self.copy, self.paste,
			self.undo, self.redo, self.delete, self.compactMixButton, self.properties_menu_item,
			self.addAudioFileMenuItem, self.addInstrumentFileMenuItem, self.recordingInputsFileMenuItem,
			self.timeFormatFileMenuItem)
		
		if self.project:
			# make various buttons and menu items enabled now we have a project option
			for c in ctrls:
				c.set_sensitive(True)
			
			
			#set undo/redo if there is saved undo history
			self.OnProjectUndo()
				
			# Create our custom widgets
			self.timeview = TimeView.TimeView(self.project)
			self.workspace = Workspace.Workspace(self.project, self)

			# Set the scroll position
			self.workspace.recordingView.OnExpose() # Calculate the scroll range
			self.workspace.recordingView.scrollBar.set_value(self.project.viewStart)
			
			# Add them to the main window
			self.main_vbox.pack_start(self.workspace, True, True)
			
			self.tvtoolitem = gtk.ToolItem()
			self.tvtoolitem.add(self.timeview)
			self.toolbar.insert(self.tvtoolitem, -1)
			self.tvtoolitem.show_all()
			
			#reset toggle buttons
			self.settingButtons = True
			self.compactMixButton.set_active(False)
			self.settingButtons = False
			
		else:
			#reset toggle buttons when the project is unloaded
			self.settingButtons = True
			self.compactMixButton.set_active(False)
			self.settingButtons = False

			for c in ctrls:
				c.set_sensitive(False)
			
			
			# Set window title with no project name
			self.window.set_title(_('Jokosher'))
			
			# Destroy our custom widgets
			if self.workspace:
				self.workspace.destroy()
				self.workspace = None
			if self.tvtoolitem:
				self.tvtoolitem.destroy()
				self.tvtoolitem = None
				
			self.main_vbox.pack_start(self.welcome_pane, True, True)
			if len(self.recent_projects_tree_model) > 0:
				self.recent_projects_tree.set_cursor( (0,) ) # the highlight the first item
				self.recent_projects_button.grab_focus()

	#_____________________________________________________________________
	
	def OnKeyPress(self, widget, event):
		"""
		Handles the hotkeys, calling whichever function they are assigned to.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		key = gtk.gdk.keyval_name(event.keyval)
		
		if 'GDK_CONTROL_MASK' in event.state.value_names:
			keysdict = {
				"x"	: self.OnCut, # Ctrl-X
				"c"	: self.OnCopy, # Ctrl-C
				"v"	: self.OnPaste, # Ctrl-V
			}
		else:
			keysdict = {
				"F1"			: self.OnHelpContentsMenu, # F1 - Help Contents
				"F3"			: self.OnF3Pressed, # F3 - Compact Mix View
				"Delete"		: self.OnDelete, # delete key - remove selected item
				"BackSpace" 	: self.OnDelete, # backspace key
				"space"		: self.Play,
				"p"			: self.Play,
				"r"			: self.Record
			}	
		
		if key in keysdict:
			keysdict[key]()
			#very important; return True if we successfully handled the key press
			#so that someone else doesn't handle it afterwards as well.
			return True
		else:
			return False
		
	#_____________________________________________________________________
	
	def OnInstrumentConnectionsDialog(self, widget):
		"""
		Creates and shows the "Instrument Connections Dialog".
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		InstrumentConnectionsDialog.InstrumentConnectionsDialog(self.project, self)
		
	#_____________________________________________________________________
	
	def OnFileMenu(self, widget):
		"""
		When the file menu opens, check if there are any events and set the mixdown project menu item's
		sensitivity accordingly and also the 'mixdown as' sensitivity.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.isRecording:
			self.export.set_sensitive(False)
			self.addInstrumentFileMenuItem.set_sensitive(False)
			self.addAudioFileMenuItem.set_sensitive(False)
			self.recordingInputsFileMenuItem.set_sensitive(False)
			return
		
		eventList = False
		if self.project:
			self.addInstrumentFileMenuItem.set_sensitive(True)
			self.addAudioFileMenuItem.set_sensitive(True)
			self.recordingInputsFileMenuItem.set_sensitive(True)
			for instr in self.project.instruments:
				if instr.events:
					eventList = True
					break
		self.export.set_sensitive(eventList)
			
	#_____________________________________________________________________
	
	def OnEditMenu(self, widget):
		"""
		HACK: When the edit menu opens, checks if any events or instruments are selected 
		and sets the cut, copy, paste and delete menu items sensitivity accordingly.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		instrSelected = False
		eventSelected = False
		if self.project:
			for instr in self.project.instruments:
				if instrSelected and eventSelected:
					break
				if instr.isSelected:
					instrSelected = True
				else:
					for ev in instr.events:
						if ev.isSelected:
							eventSelected = True
		
		self.cut.set_sensitive(eventSelected)
		self.copy.set_sensitive(eventSelected)
		self.paste.set_sensitive(instrSelected and bool(self.project.clipboardList))
		self.delete.set_sensitive(instrSelected or eventSelected)
	
	#_____________________________________________________________________
	
	def OnInstrumentMenu(self, widget):
		"""
		HACK: When the instrument menu opens, set sensitivity depending on
		whether there's a selected instrument or not.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		instrCount = 0
		if self.project:
			for instr in self.project.instruments:
				if instr.isSelected:
					instrCount += 1
		
		self.addAudioMenuItem.set_sensitive(instrCount == 1)
		self.changeInstrMenuItem.set_sensitive(instrCount == 1)
		self.removeInstrMenuItem.set_sensitive(instrCount > 0)
	
	#_____________________________________________________________________

	def OpenProjectFromPath(self, path, parent=None):
		"""
		Opens the project file referred by the path parameter.
		
		Parameters:
			path -- path to the project to be opened.
			parent -- parent window of the error message dialog.
		
		Returns:
			the status of the loading operation:
			True = the project could be successfully opened and 
			  		set as the current project.
			False = loading the project failed. A dialog will be
					displayed to user detailing the error.
		"""
		try:
			uri = PlatformUtils.pathname2url(path)
			self.SetProject(ProjectManager.LoadProjectFile(uri))
			return True
		except ProjectManager.OpenProjectError, e:
			self.ShowOpenProjectErrorDialog(e, parent)
			return False

	#_____________________________________________________________________
	
	def SetProject(self, project):
		"""
		Tries to establish the Project parameter as the current project.
		If there are errors, an error message is issued to the user.
		
		Parameters:
			project -- the Project object to set as the main project.
		"""
		try:
			ProjectManager.ValidateProject(project)
		except ProjectManager.InvalidProjectError, e:
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
		
		self.project.connect("audio-state::play", self.OnProjectAudioState)
		self.project.connect("audio-state::pause", self.OnProjectAudioState)
		self.project.connect("audio-state::record", self.OnProjectAudioState)
		self.project.connect("audio-state::stop", self.OnProjectAudioState)
		self.project.connect("audio-state::export-start", self.OnProjectExportStart)
		self.project.connect("audio-state::export-stop", self.OnProjectExportStop)
		self.project.connect("name", self.OnProjectNameChanged)
		self.project.connect("undo", self.OnProjectUndo)
		
		self.project.transport.connect("transport-mode", self.OnTransportMode)
		self.OnTransportMode()
		self.UpdateProjectLastUsedTime(project.projectfile, project.name)
		self.project.PrepareClick()

		# make various buttons and menu items enabled now we have a project
		self.SetGUIProjectLoaded()
		
	#_____________________________________________________________________
	
	def CheckGstreamerVersions(self):
		"""
		Check for CVS versions of Gstreamer and gnonlin. If requirements are not met,
		a warning message is issued to the user.
		"""
		#Check for CVS versions of Gstreamer and gnonlin
		message = ""
		gstVersion = gst.version()
		if ((gstVersion[1] <= 10 and gstVersion[2] < 9) or gstVersion[1] < 10):
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
			_("\nSee http://doc.jokosher.org/Installation for more details.\n")

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
		"""
		Appends the message parameter to the status bar text.
		
		Parameters:
			message -- string to append to the status bar text.
		"""
		return self.statusbar.Push(message)
	
	#_____________________________________________________________________

	def ClearStatusBar(self, messageID):
		"""
		Clears the status bar text in the position pointed by messageID.
		
		Parameters:
			messageID -- the message identifier of the text to be cleared.
		"""
		self.statusbar.Remove(messageID)
	
	#_____________________________________________________________________

	def OnHelpContentsMenu(self, widget=None):
		"""
		Calls the appropiate help tool with the user manual in the correct
		locale.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if gtk.pygtk_version[0] == 2 and gtk.pygtk_version[1] < 14:
			helpfile = "http://doc.jokosher.org"
		elif Globals.USE_LOCAL_HELP:
			helpfile = "ghelp:" + Globals.HELP_PATH
		else:
			helpfile = "ghelp:jokosher"
	
		Utils.OpenExternalURL(url=helpfile, message=_("<big>Couldn't launch the Jokosher documentation site.</big>\n\nPlease visit %s to access it."), parent=self.window)

	#_____________________________________________________________________

	def OnForumsMenu(self, widget):
		"""
		Opens the Jokosher forum in the user's default web browser.

		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		Utils.OpenExternalURL(url="http://www.jokosher.org/forums", message=_("<big>Couldn't launch the forums website automatically.</big>\n\nPlease visit %s to access them."), parent=self.window)
		
	#_____________________________________________________________________

	def OnContributingDialog(self, widget):
		"""
		Creates and shows the "Contributing to Jokosher" dialog.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		gtk_builder = Globals.LoadGtkBuilderFilename("ContributingDialog.ui")
		
		# grab references to the ContributingDialog window and vbox
		self.contribdialog = gtk_builder.get_object("ContributingDialog")
		self.contribvbox = gtk_builder.get_object("vbox14")
		self.contribdialog.set_icon(self.icon)

		# centre the ContributingDialog window on MainWindow
		self.contribdialog.set_transient_for(self.window)

		# set the contributing image
		self.topimage = gtk_builder.get_object("topimage")
		self.topimage.set_from_pixbuf(self.jokosher_logo_pixbuf)

		# create the bottom vbox containing the contributing website link
		vbox = gtk.VBox()			
		label = gtk.Label()
		label.set_markup(_("<b>To find out more, visit:</b>"))
		vbox.pack_start(label, False, False)
		
		if gtk.pygtk_version >= (2, 10, 0) and gtk.gtk_version >= (2, 10, 0):
			contriblnkbtn = gtk.LinkButton("http://www.jokosher.org/contribute", label="http://www.jokosher.org/contribute")
			contriblnkbtn.connect("clicked", self.OnContributingLinkButtonClicked)
			vbox.pack_start(contriblnkbtn, False, False)
		else:
			vbox.pack_start(gtk.Label("http://www.jokosher.org/contribute"), False, False)
		
		self.contribvbox.pack_start(vbox, False, False)
		self.contribdialog.show_all()

	#_____________________________________________________________________

	def OnContributingLinkButtonClicked(self, widget):
		"""
		Opens the Jokosher contributing website in the user's default web browser.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		Utils.OpenExternalURL(url="http://www.jokosher.org/contribute", 
			message=_("<big>Couldn't launch the contributing website automatically.</big>\n\nPlease visit %s to access it."), parent=self.window)
	
	#_____________________________________________________________________
	
	def GetDistroVersion(self):
		"""
		Obtain a string with the distribution name and version.
		
		Returns:
			A string with the distribution name and version.
		"""
		versionStr = ""
		try:
			#distro name
			output = Popen(args=["lsb_release", "-i"], stdout=PIPE).stdout.read()
			versionStr += output[output.find("\t")+1:len(output)-1]
			
			#distro version
			output = Popen(args=["lsb_release", "-r"], stdout=PIPE).stdout.read()
			versionStr += " " + output[output.find("\t")+1:len(output)-1]
		except OSError:
			versionStr = None
	
		return versionStr
	
	#_____________________________________________________________________
	
	def OnSystemInformation(self, widget):
		"""
		Displays a small window with the system information.
		
		Parameters:
			widget -- Gtk callback parameter.
		"""
		gtk_builder = Globals.LoadGtkBuilderFilename("SystemInformationDialog.ui")
		
		# grab references to the SystemInformationDialog window and vbox
		self.sysInfoDialog = gtk_builder.get_object("SystemInformationDialog")
		self.gstVersionStr = gtk_builder.get_object("labelGStreamerVersion")
		self.gnonlinVersionStr = gtk_builder.get_object("labelGnonlinVersion")
		self.distroVersionStr = gtk_builder.get_object("labelDistributionVersion")
		sysInfoCloseButton = gtk_builder.get_object("closeButton")
	
		#connect the close button
		sysInfoCloseButton.connect("clicked", lambda dialog: self.sysInfoDialog.destroy())
	
		#set the version strings to the appropriate value
		gstVersion = "%s.%s.%s.%s" % gst.version()
		self.gstVersionStr.set_text(gstVersion)
		
		gnlVersion = gst.registry_get_default().find_plugin("gnonlin")
		if gnlVersion:
			ignored, gnlMajor, gnlMinor = gnlVersion.get_version().split(".", 2)		
			message = "%s.%s" % (gnlMajor, gnlMinor)
		elif not gnlVersion:
			message += _("Gnonlin is missing!")
		self.gnonlinVersionStr.set_text(message)
		
		distroVersion = self.GetDistroVersion()
		if distroVersion is not None:
			self.distroVersionStr.set_text(distroVersion)
		else:
			self.distroVersionStr.set_text(_("Unknown"))
	
	#_____________________________________________________________________

	def ShowOpenProjectErrorDialog(self, error, parent=None):
		"""
		Creates and shows a dialog to inform the user about an error that has ocurred.
		
		Parameters:
			error -- string with the error(s) description.
			parent -- parent window of the error message dialog.
		"""
		if not parent:
			parent = self.window

		if error.errno == 1:
			message = _("The URI scheme '%s' is either invalid or not supported.") % error.info
		elif error.errno == 2:
			message = _("Unable to unzip the project file %s") % error.info
		elif error.errno == 3:		
			message = _("The project file was created with version \"%s\" of Jokosher.\n") % error.info + \
					  _("Projects from version \"%s\" are incompatible with this release.\n") % error.info
		elif error.errno == 4:
			message = _("The project:\n%s\n\ndoes not exist.\n") % error.info
		elif error.errno == 5:
			first = _("The project file could not be opened.\n")
			second = _("It is recommended that you report this to the Jokosher developers or get help at http://www.jokosher.org/forums/")
			message = "%s\n%s\n\n%s" % (first, second, error.info)
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

	def OnExtensionManagerDialog(self, widget):
		"""
		Creates and shows the "Extension Manager" dialog.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		ExtensionManagerDialog.ExtensionManagerDialog(self)
	
	#_____________________________________________________________________

	def OnAddAudio(self, widget):
		"""
		Adds an audio file to the selected Instrument.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		instrID = None
		for instr in self.project.instruments:
			if instr.isSelected:
				instrID = instr.id
				break
		
		if instrID != None:
			for id, instrViewer in self.workspace.recordingView.views:
				if instrID == id:
					instrViewer.eventLane.CreateEventFromFile()
		
	#_____________________________________________________________________

	def OnRemoveInstrument(self, widget):
		"""
		Removes all selected Instruments from the Project.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		# list to store instruments to delete, so we don't modify the list while we are iterating
		instrList = []
		for instr in self.project.instruments:
			if instr.isSelected:
				#set not selected so when we undo we don't get two selected instruments
				instr.isSelected = False
				instrList.append(instr)
		
		if instrList:
			self.project.DeleteInstrumentsOrEvents(instrList)
	
	#_____________________________________________________________________
	
	def ShowImportFileChooser(self):
		"""
		Creates a file chooser dialog and gets the filename to be imported,
		as well as if the file should be copied to the project folder or not.
		
		Returns:
			A 2-tuple containing the a list of file paths to be imported and a boolean
			that will be true if the user requested the file to be copied to the project folder.
			Both entries in the tuple will be None is the dialog was cancelled.
		"""
		buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK)

		copyfile = gtk.CheckButton(_("Copy file to project"))
		# Make it copy files to audio dir by default
		copyfile.set_active(True)
		copyfile.show()

		dlg = gtk.FileChooserDialog(_("Add Audio File..."), action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=buttons)
		dlg.set_default_response(gtk.RESPONSE_OK)
		dlg.set_icon(self.icon)
		if os.path.exists(Globals.settings.general["projectfolder"]):
			dlg.set_current_folder(Globals.settings.general["projectfolder"])
		else:
			dlg.set_current_folder(os.path.expanduser("~"))
		dlg.set_extra_widget(copyfile)
		dlg.set_select_multiple(True)
		
		vbox = gtk.VBox()
		audiopreview = AudioPreview.AudioPreview()
		vbox.pack_start(audiopreview, True, False)
		vbox.show_all()
		
		dlg.set_preview_widget(vbox)
		dlg.set_use_preview_label(False)
		dlg.connect("selection-changed", audiopreview.OnSelection)
		
		response = dlg.run()
		if response == gtk.RESPONSE_OK:
			#stop the preview audio from playing without destroying the dialog
			audiopreview.OnDestroy()
			dlg.hide()
			Globals.settings.general["projectfolder"] = os.path.dirname(dlg.get_filename())
			Globals.settings.write()
			filenames = dlg.get_filenames()
			copyfileBool = copyfile.get_active()
			dlg.destroy()
			
			return (filenames, copyfileBool)
		
		dlg.destroy()
		return (None, None)

	#_____________________________________________________________________

	def OnAddAudioFile(self, widget=None):
		"""
		Called when the "Add Audio File Instrument" in the project menu is clicked.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		filenames, copyfile = self.ShowImportFileChooser()
		#check if None in case the user click cancel on the dialog.
		if filenames:
			self.project.AddInstrumentAndEvents(filenames, copyfile)
		
	#_____________________________________________________________________

	def OnProjectProperties(self, widget=None):
		"""
		Called when the "Properties..." in the project menu is clicked.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.project:
			return
		
		gtk_builder = Globals.LoadGtkBuilderFilename("ProjectPropertiesDialog.ui")
		dlg = gtk_builder.get_object("ProjectPropertiesDialog")
		nameEntry = gtk_builder.get_object("nameEntry")
		authorEntry = gtk_builder.get_object("authorEntry")
		notesTextView = gtk_builder.get_object("notesTextView")
		
		nameEntry.set_text(self.project.name)
		authorEntry.set_text(self.project.author)
		buffer = gtk.TextBuffer()
		buffer.set_text(self.project.notes)
		notesTextView.set_buffer(buffer)
		
		dlg.connect("response", self.OnProjectPropertiesClose, nameEntry, authorEntry, notesTextView)
		dlg.show_all()
		
	#_____________________________________________________________________
		
	def OnProjectPropertiesClose(self, dialog, response, nameEntry, authorEntry, notesTextView):
		"""
		Called when the "Project Properties" windows is closed.
		
		Parameters:
			dialog -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		if self.project and response == gtk.RESPONSE_CLOSE:
			name = nameEntry.get_text()
			author = authorEntry.get_text()
			buffer = notesTextView.get_buffer()
			notes = buffer.get_text(*buffer.get_bounds())
			
			self.project.SetName(name)
			self.project.SetAuthor(author)
			self.project.SetNotes(notes)
				
		dialog.destroy()

	#_____________________________________________________________________
#=========================================================================

def main():
	"""
	Main entry point for Jokosher.
	"""	
	MainApp()
	gobject.threads_init()
	gtk.main()

if __name__ == "__main__":
	main()

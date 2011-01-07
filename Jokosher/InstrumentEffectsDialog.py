#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	InstrumentEffectsDialog.py
#	
#	This module us used to present the dialog for adding and managing instrument
#	effects. Note that this module deals with the main effects dialog *and* the
#	effect settings dialog, which we're both handed to Mr. Bacon in a spec by the
#	Gods of Metal. They came to him in a dream to warn against a bleak future where
#	massively distorted music could not be made using linux.
#
#-------------------------------------------------------------------------------

import gtk
import gobject
import cairo
import pygst
pygst.require("0.10")
import gst
import os
import Globals
import EffectPresets

import gettext
_ = gettext.gettext

#=========================================================================

class InstrumentEffectsDialog:
	"""
	This class displays and implements the Instrument effects dialog
	box, which can be used to add, remove, and edit effects for an
	Instrument.
	"""
	
	#_____________________________________________________________________	
	
	def __init__(self, instrument, destroyCallback, windowIcon):
		"""
		This constructor enables a lot of variables, reads in the gtk
		builder file for the main dialog, and populates the effects and
		presets controls.
		
		Parameters:
			instrument -- Instrument whose effects are being modified.
			destroyCallback -- GTK callback. Called when this dialog gets destroyed.
			windowIcon -- icon to use on the window's upper corner.
		"""
		# a reference to the instrument object
		self.instrument = instrument
		self.windowIcon = windowIcon
		
		self.gtk_builder = Globals.LoadGtkBuilderFilename("InstrumentEffectsDialog.ui")

		self.Updating = False
		self.effectWidgets = []
		
		self.signals = {
			"on_comboPresets_changed" : self.OnEffectChainPresetChanged,
			"on_buttonPresetSave_clicked" : self.OnEffectChainPresetSave,
			"on_buttonPresetDelete_clicked" : self.OnEffectChainPresetDelete,
			
			"on_comboCategories_changed" : self.OnCategoryChanged,
			"on_listEffects_row_activated" : self.OnEffectActivated,
			"on_listActiveEffects_row_activated" : self.OnActiveEffectActivated,
			"on_buttonEffectAdd_clicked" : self.OnEffectAdd,
			"on_buttonEffectUp_clicked" : self.OnEffectUp,
			"on_buttonEffectDown_clicked" : self.OnEffectDown,
			"on_buttonEffectDelete_clicked" : self.OnEffectDeleted,
			"on_buttonEffectSettings_clicked" : self.OnEffectSettings,
			
			"on_buttonPlay_clicked" : self.OnPlay,
			"on_buttonClose_clicked" : self.OnClose,
			"on_InstrumentEffects_configure_event" : self.OnResize,
			"on_InstrumentEffects_destroy" : self.OnDestroy
		}
		
		# auto connect the signals to the methods
		self.gtk_builder.connect_signals(self.signals)

		# grab references to some gtk builder widgets
		self.window = self.gtk_builder.get_object("InstrumentEffectsDialog")
		self.mainvbox = self.gtk_builder.get_object("InstrumentEffectsDialogVBox")
		
		self.imageInstrument = self.gtk_builder.get_object("imageInstrument")
		self.comboPresets = self.gtk_builder.get_object("comboPresets")
		self.buttonPresetSave = self.gtk_builder.get_object("buttonPresetSave")
		self.buttonPresetDelete = self.gtk_builder.get_object("buttonPresetDelete")
		
		self.comboCategories = self.gtk_builder.get_object("comboCategories")
		self.listEffects = self.gtk_builder.get_object("listEffects")
		self.buttonEffectAdd = self.gtk_builder.get_object("buttonEffectAdd")
		self.labelActiveEffects = self.gtk_builder.get_object("labelActiveEffects")
		self.listActiveEffects = self.gtk_builder.get_object("listActiveEffects")
		self.buttonEffectUp = self.gtk_builder.get_object("buttonEffectUp")
		self.buttonEffectDown = self.gtk_builder.get_object("buttonEffectDown")
		self.buttonEffectDelete = self.gtk_builder.get_object("buttonEffectDelete")
		self.buttonEffectSettings = self.gtk_builder.get_object("buttonEffectSettings")

		self.buttonPlay = self.gtk_builder.get_object("buttonPlay")
		self.buttonClose = self.gtk_builder.get_object("buttonClose")

		# connect the right-click signal for both treeviews
		self.listEffects.connect("button-press-event", self.OnEffectsTreeViewClick)
		self.listActiveEffects.connect("button-press-event", self.OnActiveEffectsTreeViewClick)

		# connect the destroy signal and set the window icon
		self.window.connect("destroy", destroyCallback)
		self.window.set_icon(self.windowIcon)
		
		# set single selection for the list views
		self.listEffects.get_selection().set_mode(gtk.SELECTION_SINGLE)
		self.listActiveEffects.get_selection().set_mode(gtk.SELECTION_SINGLE)

		# create and pack the header image
		self.headerCairoImage = CairoDialogHeaderImage(_("Instrument Effects"))
		self.headerCairoImage.set_size_request(self.window.allocation.width, 60)
		self.mainvbox.pack_start(self.headerCairoImage, False, False)
		self.headerCairoImage.show()
		
		# set the instrument name and image from self.instrument
		self.imageInstrument.set_from_pixbuf(self.instrument.pixbuf.scale_simple(32, 32, gtk.gdk.INTERP_BILINEAR))
		self.labelActiveEffects.set_label(self.labelActiveEffects.get_label()+self.instrument.name)
		
		# create the appropriate models
		self.modelCategories = gtk.ListStore(gtk.gdk.Pixbuf, str) #image, category
		self.modelPresets = gtk.ListStore(str) #name
		self.modelEffects = gtk.ListStore(gtk.gdk.Pixbuf, str, str, str, bool) #image, shortname, longname, category, listed
		self.modelActiveEffects = gtk.ListStore(gtk.gdk.Pixbuf, str, str, int) #image, shortname, longname, uniqueID

		# create a model filter for the effects model, and set it's visible column
		self.filterEffects = self.modelEffects.filter_new()
		self.filterEffects.set_visible_column(4)

		# set the models for each widget accordingly
		self.comboCategories.set_model(self.modelCategories)
		self.comboPresets.set_model(self.modelPresets)
		self.listEffects.set_model(self.filterEffects)
		self.listActiveEffects.set_model(self.modelActiveEffects)
		
		# create the columns with their respective renderers and add them	
		self.listEffects.append_column(gtk.TreeViewColumn(_("Name"), gtk.CellRendererText(), text=2))
		self.listActiveEffects.append_column(gtk.TreeViewColumn(_("Type"), gtk.CellRendererPixbuf(), pixbuf=0))
		self.listActiveEffects.append_column(gtk.TreeViewColumn(_("Name"), gtk.CellRendererText(), text=2))
		
		# effects combo
		pixRenderer = gtk.CellRendererPixbuf()
		pixRenderer.set_property("xpad", 6)
		pixRenderer.set_property("ypad", 3)
		textRenderer = gtk.CellRendererText()
		self.comboCategories.clear()					# all combos by default have one textRenderer. Remove it
														# before adding the pixRenderer.
		self.comboCategories.pack_start(pixRenderer, expand=False)
		self.comboCategories.pack_start(textRenderer)
		self.comboCategories.add_attribute(pixRenderer, "pixbuf", 0)
		self.comboCategories.add_attribute(textRenderer, "text", 1)
		
		# presets combo
		self.comboPresets.clear()
		textRenderer = gtk.CellRendererText()
		self.comboPresets.pack_start(textRenderer)
		self.comboPresets.add_attribute(textRenderer, "text", 0)
		
		# create a copy of the categories list to avoid errors in the for's
		categories = Globals.LADPSA_CATEGORIES_LIST
		
		#the temporary list to sort them
		tempEffectList = []
		# load all available effects into modelEffects
		for effect in Globals.LADSPA_NAME_MAP:
			newEffect = [None, None, None, None, None]

			try:
				imageFile = categories[Globals.LADSPA_CATEGORIES_DICT[effect[0]]][1]	# image path
				category = categories[Globals.LADSPA_CATEGORIES_DICT[effect[0]]][0]
			except KeyError:	# unclassified
				imageFile = categories[1][1]
				category = categories[1][0]
				
			newEffect[0] = gtk.gdk.pixbuf_new_from_file(os.path.join(Globals.IMAGE_PATH, imageFile)) # image
			newEffect[1] = effect[0]	# short name
			newEffect[2] = effect[1]	# long name
			newEffect[3] = category
			newEffect[4] = False		# listed in the left effects pane
			
			tempEffectList.append(newEffect)
		
		tempEffectList.sort(key=lambda x: x[2].lower()) #sort alphabetically by long name
		for newEffect in tempEffectList:
			self.modelEffects.append(newEffect)
		
		# create a list with available presets and populate the model
		self.presets = EffectPresets.EffectPresets()
		self._LoadInstrumentPresets()
				
		# append the categories and their image to the categories combo box
		for index, category in enumerate(categories):
			# skip the Broken category
			if index == 0:
				continue
				
			for effect in self.modelEffects:
				#If there is at least one effect in this category; always include unclassified
				if effect[3] == category[0] or index == 1:	
					imageFile = category[1]
					icon = gtk.gdk.pixbuf_new_from_file(os.path.join(Globals.IMAGE_PATH, imageFile))
					self.modelCategories.append([icon, category[0]])
					break
		
		#set the first one active
		self.comboCategories.set_active(0)
		
		# this says if the project is playing, so we know to toggle the
		# play button in the dialog	
		self.isPlaying = self.instrument.project.GetIsPlaying()

		if self.isPlaying:
			self.buttonPlay.set_use_stock(True)
			self.buttonPlay.set_label(gtk.STOCK_MEDIA_STOP)

		# listen to the Project, Instrument and Preset changes
		self.instrument.project.connect("audio-state::play", self.OnProjectPlay)
		self.instrument.project.connect("audio-state::record", self.OnProjectRecord)
		self.instrument.project.connect("audio-state::stop", self.OnProjectStop)
		self.instrument.connect("effect", self.OnInstrumentEffect)
		self.presets.connect("single-preset", self.OnSinglePreset)
		self.presets.connect("chain-preset", self.OnChainPreset)

		self.updatinggui = True
		if self.instrument.currentchainpreset is not None:
			self.comboPresets.set_active(self.instrument.currentchainpreset)
		self.updatinggui = False

		self.width = int(Globals.settings.general["instrumenteffectwindowwidth"])
		self.height = int(Globals.settings.general["instrumenteffectwindowheight"])
		self.window.resize(self.width, self.height)

			
		self.Update()
			
	#_____________________________________________________________________
	
	def _LoadInstrumentPresets(self):
		"""
		Loads the presets for this Instrument type if there are any available.
		It then adds them to the chain presets combo box model.
		"""
		self.availpresets = []
		self.modelPresets.clear()
		
		self.presets.FillEffectsPresetsRegistry()
		
		try:
			instrPresets = self.presets.effectpresetregistry["instruments"][self.instrument.instrType] 
			for pres in instrPresets:
				if instrPresets[pres]["dependencies"].issubset(Globals.LADSPA_FACTORY_REGISTRY):
					self.availpresets.append(pres)
					self.modelPresets.append([pres])
		except KeyError:
			# no presets for this Instrument
			pass
		
	#_____________________________________________________________________
	
	def Update(self):
		"""
		Refreshes the effects inside the modelActiveEffects when they are
		added, removed or shuffled.
		"""
		if self.Updating:
			return
		self.Updating = True
		
		# create a copy of the categories list to avoid errors in the for
		categories = Globals.LADPSA_CATEGORIES_LIST
		
		# clear the active effects list
		self.modelActiveEffects.clear()
		
		# append all the active effects to the modelActiveEffects
		for effect in self.instrument.effects:
			shortName =  effect.get_factory().get_name()
			longName = effect.get_factory().get_longname()	
			activeEffect = [None, None, None, None]
			
			try:
				imageFile = categories[Globals.LADSPA_CATEGORIES_DICT[shortName]][1]	# image path
			except KeyError:
				imageFile = categories[1][1]	# unclassified
				
			activeEffect[0] = gtk.gdk.pixbuf_new_from_file(os.path.join(Globals.IMAGE_PATH, imageFile))
			activeEffect[1] = shortName
			activeEffect[2] = longName
			activeEffect[3] = len(self.modelActiveEffects)
			
			self.modelActiveEffects.append(activeEffect)
		
		self.Updating = False
		
	#_____________________________________________________________________	
		
	def OnClose(self, button):
		"""
		If the OK button is pressed on the dialog box, the window is destroyed.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.instrument.project.disconnect_by_func(self.OnProjectPlay)
		self.instrument.project.disconnect_by_func(self.OnProjectRecord)
		self.instrument.project.disconnect_by_func(self.OnProjectStop)
		self.instrument.disconnect_by_func(self.OnInstrumentEffect)
		self.window.destroy()
		
	#_____________________________________________________________________	

	def OnPlay(self, button):
		"""
		Pressing the Play/Stop button on the dialog box allows the user
		to play back the project to test if the effect settings are
		right for them. When user press the Play button, it switches to
		a stop button, and vice versa.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.isPlaying == False:
			# things to do if the project is not already playing, and hence
			# needs to start playing
			self.instrument.project.Play()
			self.isPlaying = True
		else:
			self.instrument.project.Stop()
			self.isPlaying = False

	#_____________________________________________________________________
	
	def OnSinglePreset(self, effectPresets):
		"""
		Callback function for when the a the list of single effects is modified.
		"""
		self._LoadEffectPresets()
	
	#_____________________________________________________________________
	
	def OnChainPreset(self, effectPresets):
		"""
		Callback function for when the a the list of chain effects is modified.
		"""
		self._LoadInstrumentPresets()
	
	#_____________________________________________________________________
	
	def OnProjectRecord(self, project):
		"""
		Callback for when the project starts recording.
		
		Parameters:
			project -- The project instance that send the signal.
		"""
		self.window.set_sensitive(False)
	
	#_____________________________________________________________________
	
	def OnProjectPlay(self, project):
		"""
		Callback for when the project starts playing.
		
		Parameters:
			project -- The project instance that send the signal.
		"""
		# things to do if the project is not already playing, and hence
		# needs to start playing
		self.buttonPlay.set_use_stock(True)
		self.buttonPlay.set_label(gtk.STOCK_MEDIA_STOP)
		
		# set this to True to show we are now playing
		self.isPlaying = True
	
	#_____________________________________________________________________
	
	def OnProjectStop(self, project):
		"""
		Callback for when the project stops playing or recording.
		
		Parameters:
			project -- The project instance that send the signal.
		"""
		self.window.set_sensitive(True)
		# things to do when the stop button is pressed to stop playback
		self.buttonPlay.set_use_stock(True)
		self.buttonPlay.set_label(gtk.STOCK_MEDIA_PLAY)
		
		# set this to False to show we are no longer playing
		self.isPlaying = False
	
	#_____________________________________________________________________
	
	def OnInstrumentEffect(self, instrument):
		"""
		Callback for when the effects on the instrument change.
		
		Parameters:
			instrument -- the instrument instance that send the signal.
		"""
		self.Update()
	
	#_____________________________________________________________________
	
	def OnCategoryChanged(self, combo):
		"""
		Updates the list of available effects depending on the category chosen.
		
		Parameters:
			combo -- reserved for GTK callbacks, don't use it explicitly.
		"""
		# display all the correspondent effects in the effects list
		for effect in self.modelEffects:
			if effect[3] == self.modelCategories[combo.get_active()][1]:	#match the category
				effect[4] = True	#display the effect
			else:
				effect[4] = False	#hide the effect
	
	#_____________________________________________________________________
	
	def OnActiveEffectsTreeViewClick(self, widget, mouse):
		"""
		Called when the user presses a mouse button over the ListActiveEffects TreeView.
		If it's a right-click, creates a context menu on the fly for
		manipulating effects.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- GTK mouse event that fired this method call.
		"""
		selection = self.listActiveEffects.get_selection().get_selected()
		
		# return if there is no active selection
		if not selection[1]:
			return
		
		# Create context menu on a right-click
		if mouse.button == 3:
			menu = gtk.Menu()
			items = [
					(_("_Move up..."), self.OnEffectUp, True, gtk.image_new_from_stock(gtk.STOCK_GO_UP, gtk.ICON_SIZE_MENU)),
					(_("M_ove down..."), self.OnEffectDown, True, gtk.image_new_from_stock(gtk.STOCK_GO_DOWN, gtk.ICON_SIZE_MENU)),
					("---", None, False, None),
					(_("_Delete"), self.OnEffectDeleted, True, gtk.image_new_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_MENU)),
					(_("_Settings"), self.OnEffectSettings, True, gtk.image_new_from_stock(gtk.STOCK_PROPERTIES, gtk.ICON_SIZE_MENU))
					]
			
			for label, callback, sensitivity, image in items:
				if label == "---":
					menuItem = gtk.SeparatorMenuItem()
				elif image:
					menuItem = gtk.ImageMenuItem(label, True)
					menuItem.set_image(image)
				else:
					menuItem = gtk.MenuItem(label=label)
				
				menuItem.set_sensitive(sensitivity)
				menuItem.show()
				menu.append(menuItem)
				if callback:
					menuItem.connect("activate", callback)
			
			menu.popup(None, None, None, mouse.button, mouse.time)
	#_____________________________________________________________________
	
	def OnEffectsTreeViewClick(self, widget, mouse):
		"""
		Called when the user presses a mouse button over the ListEffects TreeView.
		If it's a right-click, creates a context menu on the fly for
		manipulating effects.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- GTK mouse event that fired this method call.
		"""
		selection = self.listEffects.get_selection().get_selected()
		
		# return if there is no active selection
		if not selection[1]:
			return
		
		# Create context menu on a right-click
		if mouse.button == 3:
			menu = gtk.Menu()
			
			menuItem = gtk.ImageMenuItem(_("_Activate effect"), True)
			menuItem.set_image(gtk.image_new_from_stock(gtk.STOCK_GO_FORWARD, gtk.ICON_SIZE_MENU))
			menuItem.show()
			menu.append(menuItem)
			menuItem.connect("activate", self.OnEffectAdd)
		
			menu.popup(None, None, None, mouse.button, mouse.time)
			
	#_____________________________________________________________________
	
	def OnEffectActivated(self, treeview, path, view_column):
		"""
		Adds the double clicked effect from the left effects pane to the Instrument.
		
		Parameters:
			treeview -- treeview that fired this event.
			path -- path to the activated row. Format: (index,)
			view_column -- the column in the activated row.
		"""
		self.OnEffectAdd()
		
	#_____________________________________________________________________
	
	def OnActiveEffectActivated(self, treeview, path, view_column):
		"""
		Displays the settings for the double clicked effect from the active effects
		pane.
		
		Parameters:
			treeview -- treeview that fired this event.
			path -- path to the activated row. Format: (index,)
			view_column -- the column in the activated row.
		"""
		self.OnEffectSettings()
	
	#_____________________________________________________________________
	
	def OnEffectAdd(self, widget=None):
		"""
		Adds the currently selected effect to the Instrument.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		selection = self.listEffects.get_selection().get_selected()
		
		# return if there is no active selection
		if not selection[1]:
			return

		self.instrument.AddEffect(self.filterEffects[selection[1]][1])
		
	#_____________________________________________________________________

	def OnEffectUp(self, button):
		"""
		Moves the selected effect one position up on the list.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		selection = self.listActiveEffects.get_selection().get_selected()
		
		# return if there is no active selection or it's the first element
		if not selection[1] or self.modelActiveEffects[selection[1]].path == (0,):
			return
		
		# grab references to the effect position in the table and the
		# effect element itself, to then move it
		effectPos = self.modelActiveEffects[selection[1]].path[0]
		effect = self.instrument.effects[effectPos]
		
		newPosition = self.modelActiveEffects[selection[1]].path[0]-1
		self.instrument.ChangeEffectOrder(effect, newPosition)
		
		# reselect the effect moved in this operation
		self.listActiveEffects.set_cursor(newPosition)
	
	#_____________________________________________________________________
	
	def OnEffectDown(self, button):
		"""
		Moves the selected effect one position down on the list.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		selection = self.listActiveEffects.get_selection().get_selected()
		
		# return if there is no active selection or it's the last element
		if not selection[1] or self.modelActiveEffects[selection[1]].next == None:
			return
		
		# grab references to the effect position in the table and the
		# effect element itself, to then move it
		effectPos = self.modelActiveEffects[selection[1]].path[0]
		effect = self.instrument.effects[effectPos]
		
		newPosition = self.modelActiveEffects[selection[1]].path[0]+1
		self.instrument.ChangeEffectOrder(effect, newPosition)
		
		# reselect the effect moved in this operation
		self.listActiveEffects.set_cursor(newPosition)
		
	#_____________________________________________________________________
	
	def OnEffectDeleted(self, widget):
		"""
		Removes the currently selected effect from the Instrument.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		selection = self.listActiveEffects.get_selection().get_selected()
		
		# return if there is no active selection
		if not selection[1]:
			return
		
		# grab references to the effect position in the table and the
		# effect element itself, to then delete it
		effectPos = self.modelActiveEffects[selection[1]].path[0]
		effect = self.instrument.effects[effectPos]
		
		self.instrument.RemoveEffect(effect)
		
		# select another existing active effect for usability,
		# so users can repeteadly click on delete to delete all effects
		if len(self.modelActiveEffects) > 0:
			self.listActiveEffects.set_cursor(0)
		
	#_____________________________________________________________________
	
	def OnEffectSettings(self, button=None):
		"""
		Show a dialog filled with settings sliders for a specific effect
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		# TODO: Make this modal or as part of the effects window
		selection = self.listActiveEffects.get_selection().get_selected()
		
		# return if there is no active selection
		if not selection[1]:
			return
		
		# grab references to the effect position in the table and the
		# effect element itself
		self.effectpos = self.modelActiveEffects[selection[1]].path[0]
		self.effectelement = self.instrument.effects[self.effectpos]
		
		# this variable is used to slash the values for the different sliders
		self.sliderdict = {}
		
		# Threshold value to determine if a property is buggy
		self.propertyThreshold = 1000000
		
		# Min/Max value assigned to buggy properties
		self.fixValue = 15.0
		
		# set the index of the current edited effect - used to reference the
		# effect elsewhere
		self.settings_gtk_builder = Globals.LoadGtkBuilderFilename("EffectSettingsDialog.ui")

		settsignals = {
			"on_presetsCombo_changed" : self.OnSingleEffectPresetChanged,
			"on_savePresetButton_clicked" : self.OnSingleEffectPresetSave,
			"on_deletePresetButton_clicked" : self.OnSingleEffectPresetDelete,
			"on_closeButton_clicked" : self.OnSingleEffectSettingsClose
		}

		self.settings_gtk_builder.connect_signals(settsignals)

		# create references to gtk builder widgets
		self.settingswindow = self.settings_gtk_builder.get_object("EffectSettingsDialog")
		self.settingsvbox = self.settings_gtk_builder.get_object("EffectSettingsVBox")
		self.effectLabel = self.settings_gtk_builder.get_object("effectLabel")
		self.effectImage = self.settings_gtk_builder.get_object("effectImage")
		self.settingstable = self.settings_gtk_builder.get_object("settingsTable")
		self.presetscombo = self.settings_gtk_builder.get_object("presetsCombo")
		
		self.settingsHeaderCairoImage = CairoDialogHeaderImage(_("Effect Settings"))
		self.settingsHeaderCairoImage.set_size_request(450, 60)
		self.settingsvbox.pack_start(self.settingsHeaderCairoImage, expand=False, fill=True)
		self.settingsHeaderCairoImage.show()
		
		# set the window icon and parent (for correct modal mode)
		self.settingswindow.set_icon(self.windowIcon)
		self.settingswindow.set_transient_for(self.window)
		
		# grab a list of properties from the effect
		proplist = gobject.list_properties(self.instrument.effects[self.effectpos])
		
		# set the effect name and icon
		self.effectLabel.set_label("<b>%s</b>" % self.modelActiveEffects[selection[1]][2])
		self.effectImage.set_from_pixbuf(self.modelActiveEffects[selection[1]][0])
		
		# resize the settingstable to accomodate the number of settings sliders required
		self.settingstable.resize(len(proplist), 2)
		
		count = 0
		
		# iterate through the properties list, determine its value type 
		# and show it where needed
		for property in proplist:
			# non readable params
			if not(property.flags & gobject.PARAM_READABLE):
				# create and attach a property name label to the settings table
				label = gtk.Label(property.name)
				label.set_alignment(1, 0.5)
				self.settingstable.attach(label, 0, 1, count, count+1, xoptions=gtk.FILL)

				rlabel = gtk.Label(_("-parameter not readable-"))
				self.settingstable.attach(rlabel, 1, 2, count, count+1)

			# just display non-writable param values
			elif not(property.flags & gobject.PARAM_WRITABLE):
				# create and attach a property name label to the settings table
				label = gtk.Label(property.name)
				label.set_alignment(1, 0.5)
				self.settingstable.attach(label, 0, 1, count, count+1, xoptions=gtk.FILL)
								
				wvalue = self.effectelement.get_property(property.name)
				
				if wvalue != None:
					wlabel = gtk.Label(wvalue)
					self.settingstable.attach(wlabel, 1, 2, count, count+1, xoptions=gtk.FILL)

			elif hasattr(property, "minimum") and hasattr(property, "maximum"):
				# create and attach a property name label to the settings table
				label = gtk.Label(property.name)
				label.set_alignment(1, 0.5)
				self.settingstable.attach(label, 0, 1, count, count+1, xoptions=gtk.FILL)

				# assume that it's numeric so we can use an HScale
				value = self.effectelement.get_property(property.name)
				
				# use these values for the slider range
				minValue = property.minimum
				maxValue = property.maximum
				
				# fix the ridiculously big min/max range values if needed
				if property.minimum < -self.propertyThreshold:
					minValue = -self.fixValue
					
				if property.maximum > self.propertyThreshold:
					maxValue = self.fixValue
				
				adj = gtk.Adjustment(value, minValue, maxValue)
				adj.connect("value_changed", self.SetSingleEffectSetting, property.name, property)
				self.sliderdict[property.name] = hscale = gtk.HScale(adj)
				hscale.set_value_pos(gtk.POS_RIGHT)
				
				# add step increment for mouse-wheel scrolling - proportional
				# to range in view. Must be at least the smallest interval
				# possible (determined by get_digits()) or scroll doesn't happen
				adj.step_increment = (maxValue - minValue) / 100.0
				adj.step_increment = max(adj.step_increment, 1.0 / (10 ** hscale.get_digits()))
				
				# check for ints and change digits
				if not((property.value_type == gobject.TYPE_FLOAT) or
					   (property.value_type == gobject.TYPE_DOUBLE)):
					hscale.set_digits(0)

				# add the slider to the settings table (with tooltips)
				self.sliderdict[property.name].set_tooltip_text(property.blurb)
				self.settingstable.attach(self.sliderdict[property.name], 1, 2, count, count+1, gtk.FILL|gtk.EXPAND)
			
			count += 1

		# set up presets
		self.elementfactory = self.effectelement.get_factory().get_name()
		
		self.model = gtk.ListStore(str)
		self.presetscombo.set_model(self.model)
		self._LoadEffectPresets()
		
		# show the settings window	
		self.settingstable.show()
		self.settingswindow.show_all()

	#_____________________________________________________________________
	
	def _LoadEffectPresets(self):
		"""
		Loads the presets for the selected effect if there are any available.
		It then adds them to the effects presets combo box.
		
		The following checks are performed during this operation:
			a) the preset is on the system (in LADSPA_FACTORY_REGISTRY).
			b) the preset is for this plugin.
		"""
		self.availEffectPresets = []
		self.model.clear()
		
		self.presets.FillEffectsPresetsRegistry()
		
		try:
			effectPresets = self.presets.effectpresetregistry["effects"][self.elementfactory]
			if self.elementfactory in Globals.LADSPA_FACTORY_REGISTRY:
				for pres in effectPresets:
					deps = effectPresets[pres]["dependencies"]
					if len(deps) == 1 and self.elementfactory in deps:
						self.availEffectPresets.append(pres)
						self.model.append([pres])
						#self.presetscombo.append_text(pres)
		except KeyError:
			# no presets for this effect
			pass
	
	#_____________________________________________________________________
		
	def OnSingleEffectSettingsClose(self, button):
		"""
		Close the effect settings window.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.settingswindow.destroy()

	#_____________________________________________________________________	
	
	def SetSingleEffectSetting(self, slider, name, property):
		"""
		Set the value of a gstreamer property from an effects slider.
		
		Parameters:
			slider -- slider control which indicates the value to assign to property.
			name -- name of the property being set.
			property -- property being set.
		"""
		# grab the slider setting
		if not((property.value_type == gobject.TYPE_FLOAT) or
			   (property.value_type == gobject.TYPE_DOUBLE)):
			value = int(slider.get_value())
		else:
			value = slider.get_value()
		
		# set the gstreamer property
		self.instrument.effects[self.effectpos].set_property(name, value)
		
	#_____________________________________________________________________	

	def OnSingleEffectPresetSave(self, widget):
		"""
		Grab the effect properties and send it to the presets code
		to be saved.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
		"""
		# grab the label from the combo
		label = self.presetscombo.get_active_text()
		
		if label == "":
			return
		
		effectdict = {}
		
		effect = self.instrument.effects[self.effectpos]
		effectelement = effect.get_factory().get_name()
		
		proplist = gobject.list_properties(effect)
		
		# for each property in proplist, add it to the effectdict dictionary
		for property in proplist:
			effectdict[property.name] = effect.get_property(property.name)

		# save the preset	
		self.presets.SaveSingleEffect(label, effectdict, effectelement, "LADSPA")
		
	#_____________________________________________________________________
	
	def OnSingleEffectPresetDelete(self, button):
		"""
		Removes the selected effect preset.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		presetName = self.presetscombo.get_active_text()
		
		if presetName == "":
			return
		
		effect = self.instrument.effects[self.effectpos]
		effectName = effect.get_factory().get_name()
		
		self.presets.DeleteSingleEffect(presetName, effectName)
	
	#_____________________________________________________________________
	
	def OnEffectChainPresetSave(self, button):
		"""
		Grabs the effects chain and sends it to the presets code to be saved.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		# grab the label from the combo
		label = self.comboPresets.get_active_text()
		
		if label == "":
			return
		
		self.effectlist = []
				
		for effect in self.instrument.effects:
			effectdict = {}
			effectsettings = {}

			proplist = gobject.list_properties(effect)
		
			for property in proplist:
				effectsettings[property.name] = effect.get_property(property.name)

			effectdict["effectelement"] = effect.get_factory().get_name()
			effectdict["effecttype"] = "LADSPA"
			effectdict["settings"] = effectsettings
			
			self.effectlist.append(effectdict)
		
		self.presets.SaveEffectChain(label, self.effectlist, self.instrument.instrType)

	#_____________________________________________________________________
	
	def OnEffectChainPresetDelete(self, button):
		"""
		Removes the selected effects chain preset.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		presetName = self.comboPresets.get_active_text()
		
		if presetName == "":
			return
		
		self.presets.DeleteEffectChain(presetName, self.instrument.instrType)
	
	#_____________________________________________________________________
	
	def OnSingleEffectPresetChanged(self, combo):
		"""
		Loads a preset when it's selected from the single effect preset combo.
		
		Parameters:
			combo -- reserved for GTK callbacks, don't use it explicitly.
		"""
		presetname = name = combo.get_active_text()
		
		if presetname not in self.availEffectPresets:
			return
		
		settings = self.presets.LoadSingleEffect(presetname, 
												 self.effectelement.get_factory().get_name())
		if not settings:
			return

		for item in settings:
			#self.sliderdict[str(item)]
			try:
				self.effectelement.set_property(item, settings[item])
				self.sliderdict[str(item)].set_value(settings[item])
			except:
				pass
		
		self.settingstable.show()
		self.settingswindow.show_all()

	#_____________________________________________________________________	
	
	def OnEffectChainPresetChanged(self, combo):
		"""
		Loads a preset when it's selected from the chain preset combo.
		
		Parameters:
			combo -- reserved for GTK callbacks, don't use it explicitly.
		"""
		# If we're still setting up the gui then we dont want to *do* anything when 
		# we set the combobox so check the flag and quit if necessary
		if self.updatinggui == True:
			return
		
		presetname = name = combo.get_active_text()
		if presetname not in self.availpresets:
			return

		self.instrument.currentchainpreset = combo.get_active()
		settings = self.presets.LoadEffectChain(presetname, self.instrument.instrType)
		
		self.instrument.effects = []
		
		for item in settings:
			effect = settings[item]
			prefs = effect['preferences']
			setts = effect['settings']

			effect = self.instrument.AddEffect(prefs['effectelement'])

			for sett in setts:
				try:
					setts[sett]
					effect.set_property(sett, setts[sett])

				except:
					Globals.debug("problem loading preset property %s= %s"%(sett,setts[sett]))
					pass

		self.Update()
		
	#_____________________________________________________________________	
	
	def BringWindowToFront(self):
		"""
		Puts the InstrumentsEffectDialog on top of other windows.
		"""
		self.window.present()
		
	#_____________________________________________________________________



	def OnResize(self, widget, event):
		"""
		This method is called when the Instrument Effect dialog is resized

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
		Called when the instrument effects dialog is destroyed

		Parameters: 
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
		"""
		
		Globals.settings.general["instrumenteffectwindowwidth"] = self.width
		Globals.settings.general["instrumenteffectwindowheight"] = self.height
		Globals.settings.write()
	#_____________________________________________________________________	

#=========================================================================

class CairoDialogHeaderImage(gtk.DrawingArea):
	"""
	Renders a banner for the top of the effects dialog using Cairo.
	"""
	
	_LEFT_GRADIENT_STOP_RGBA = (0, 0.99, 0.87, 0.38, 1)
	_RIGHT_GRADIENT_STOP_RGBA = (1, 0.93, 0.55, 0.16, 1)
	_TEXT_RGBA = (0.93, 0.55, 0.16, 1)
	_FONT_SIZE = 40
	_LEFT_LOGO_INDENT = 7
	_LEFT_TEXT_INDENT = 56
	
	#_____________________________________________________________________
	
	def __init__(self, headerText):
		"""
		Creates a new instance of CairoDialogHeaderImage.
		
		Parameters:
			headerText -- text to be displayed at the header.
		"""
		gtk.DrawingArea.__init__(self)
		self.headerText = headerText
		
		self.connect("configure_event", self.OnSizeChanged)
		self.connect("expose-event", self.OnDraw)
		
		self.logo = cairo.ImageSurface.create_from_png(os.path.join(Globals.IMAGE_PATH, "jokosher.png"))
		self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.allocation.width, self.allocation.height)
		self.GenerateCachedImage()
		
	#_____________________________________________________________________
		
	def OnSizeChanged(self, obj, evt):
		"""
		Called when the widget's size changes.
		
		Parameters:
			obj -- reserved for Cairo callbacks, don't use it explicitly. *CHECK*
			evt -- reserved for Cairo callbacks, don't use it explicitly. *CHECK*
		"""
		if self.allocation.width != self.source.get_width() or self.allocation.height != self.source.get_height():
			self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.allocation.width, self.allocation.height)
			self.GenerateCachedImage()

	#_____________________________________________________________________

	def GenerateCachedImage(self):
		"""
		Renders the image so that we don't have to re-render it every
		time there is an expose event from a mouse move or something.
		"""
		
		rect = self.get_allocation()

		ctx = cairo.Context(self.source)
		ctx.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
		
		# Create our gradient
		pat = cairo.LinearGradient(0.0, 0.0, rect.width, 0)
		pat.add_color_stop_rgba(*self._RIGHT_GRADIENT_STOP_RGBA)
		pat.add_color_stop_rgba(*self._LEFT_GRADIENT_STOP_RGBA)

		# Fill the widget
		ctx.rectangle(0, 0, rect.width, rect.height)
		ctx.set_source(pat)
		ctx.fill()
		
		#Paint the Jokosher logo on top (x=7, y=8 centres the logo)
		logoPos = (rect.height - self.logo.get_height()) / 2
		ctx.set_source_surface(self.logo, self._LEFT_LOGO_INDENT, int(logoPos))
		ctx.paint()
		
		ctx.set_source_rgba(*self._TEXT_RGBA)
		textPos = rect.height - ((rect.height - self._FONT_SIZE) / 2) - 5
		ctx.move_to(self._LEFT_TEXT_INDENT, int(textPos))
		ctx.set_font_size(self._FONT_SIZE)
		ctx.show_text(self.headerText)
		ctx.stroke()
	
	#_____________________________________________________________________

	def OnDraw(self, widget, event):
		"""
		Handles the GTK expose event.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
			
		Returns:
			False -- indicates the GTK signal to:
					1) continue propagating the regular signal.
					2) stop calling the callback on a timeout_add.
		"""
		
		ctx = widget.window.cairo_create()
		#Don't repaint the whole area unless necessary
		ctx.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
		ctx.clip()
		# Paint the cached image across the widget
		ctx.set_source_surface(self.source, 0, 0)	
		ctx.paint()

		return False
		
	#_____________________________________________________________________


#=========================================================================

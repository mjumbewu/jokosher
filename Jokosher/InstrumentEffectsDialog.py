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

import gtk.glade
import gobject
import cairo
import pygst
pygst.require("0.10")
import gst
import os
import Globals
import EffectPresets
from EffectWidget import EffectWidget

import gettext
_ = gettext.gettext

#=========================================================================

class InstrumentEffectsDialog:
	"""
		This class displays and implements the instrument effects dialog
		box, which can be used to add, remove, and edit effects for an
		instrument.
	"""
	
	#_____________________________________________________________________	
	
	def __init__(self, instrument, destroyCallback):
		"""
			This constructor enables a bunch of variables, reads in the glade
			file for the main dialog, and populates the effects and presets
			combo boxes
		"""
		
		# a reference to the instrument object
		self.instrument = instrument
		
		self.res = gtk.glade.XML(Globals.GLADE_PATH, "InstrumentEffectsDialog")

		self.Updating = False
		self.effectWidgets = []
		
		self.signals = {
			"on_okbutton_clicked" : self.OnOK,
			"on_cancelbutton_clicked" : self.OnCancel,
			"on_transportbutton_clicked" : self.OnTransport,
			"on_effectscombo_changed" : self.OnSelectEffect,
			"on_addbutton_clicked" : self.OnAddEffect,
			"on_chainpresetsave_clicked" : self.OnSaveEffectChainPreset,
			"on_chainpresetcombo_changed" : self.OnChainPresetChanged
		}
		
		# auto connect the signals to the methods
		self.res.signal_autoconnect(self.signals)

		# grab some references to Glade items
		self.window = self.res.get_widget("InstrumentEffectsDialog")
		self.mainvbox = self.res.get_widget("InstrumentEffectsDialogVBox")
		self.effectscombo = self.res.get_widget("effectscombo")
		self.effectsbox = self.res.get_widget("effectsbox")
		self.addeffect = self.res.get_widget("addbutton")
		self.instrumentimage = self.res.get_widget("instrumentimage")
		self.chainpresetcombo = self.res.get_widget("chainpresetcombo")
		self.chainsave = self.res.get_widget("chainpresetsave")
		self.transportbutton = self.res.get_widget("transportbutton")

		self.window.connect("destroy", destroyCallback)
		self.addeffect.set_sensitive(False)

		self.headerCairoImage = CairoDialogHeaderImage(_("Instrument Effects"))
		self.headerCairoImage.set_size_request(750, 60)
		self.mainvbox.pack_start(self.headerCairoImage, False, False)
		self.headerCairoImage.show()
		
		# pick the gtk.Entry out of the effectscombo and
		# add a gtk.EntryCompletion to it
		self.effectsEntry = self.effectscombo.child
		self.effectsEntryCompletion = gtk.EntryCompletion()
		self.effectsEntryCompletion.set_match_func(self.matchEffect)
		self.effectsEntry.set_completion(self.effectsEntryCompletion)
		self.effectsEntryCompletion.set_text_column(0)
		self.effectsEntryCompletion.connect("match-selected", self.OnEntrySelected)
		
		
		# set the instrumentimage to the self.instrument icon
		self.instrumentimage.set_from_pixbuf(self.instrument.pixbuf)
		
		# set the model for the effects combo to a ListStore
		self.model = gtk.ListStore(str)
		self.effectscombo.set_model(self.model)

		for item in Globals.LADSPA_NAME_MAP:
			Globals.debug(item[1])
			longname = item[1]
			shortname = longname[:45]
			
			if len(longname) > 45:
				shortname = shortname + "..."
			
			self.effectscombo.append_text(shortname)

		# make the EntryCompletion use the same list for its model
		self.effectsEntryCompletion.set_model(self.model)
		self.presets = EffectPresets.EffectPresets()

		# set up presets
						
		self.model = gtk.ListStore(str)
		self.chainpresetcombo.set_model(self.model)

		# appends presets for this instrument
		# if it is on the system (in LADSPA_FACTORY_REGISTRY). It then adds the
		# presets to the chain presets combo box.
		self.availpresets = []
		for key, value in self.presets.effectpresetregistry.iteritems():
			if value['instrument'] == self.instrument.instrType and \
					value['dependencies'].issubset(Globals.LADSPA_FACTORY_REGISTRY):
				self.availpresets.append(key)
		
		for pres in self.availpresets:
			self.chainpresetcombo.append_text(pres)
			
		# this says if the project is playing, so we know to toggle the
		# transport button in the dialog	

		self.isPlaying = self.instrument.project.IsPlaying

		if self.isPlaying:
			self.transportbutton.set_use_stock(True)
			self.transportbutton.set_label(gtk.STOCK_MEDIA_STOP)


		self.instrument.project.AddListener(self)
		self.instrument.AddListener(self)

		if self.instrument.currentchainpreset is not None:
			self.chainpresetcombo.set_active(self.instrument.currentchainpreset)
			
		self.Update()
			
	#_____________________________________________________________________	
	
	def Update(self):
		if self.Updating:
			return
		self.Updating = True
		
		for i in self.effectsbox.get_children():
			self.effectsbox.remove(i)
		
		for effect in self.instrument.effects:
			effwidget = None
			for i in self.effectWidgets:
				if i.effect is effect:
					effwidget = i
					break
			
			if not effwidget:
				effectname =  effect.get_factory().get_longname()
				effwidget = EffectWidget(effect, effectname)
				effwidget.connect("remove", self.OnRemoveEffect, effect)
				effwidget.connect("clicked", self.OnEffectSetting, effect)
				self.effectWidgets.append(effwidget)
			
			self.effectsbox.pack_start(effwidget, True)
		
		self.effectsbox.show_all()
		
		self.Updating = False
		
	#_____________________________________________________________________	
		
	def OnOK(self, button):
		"""
			If the OK button is pressed on the dialog box, the window is
			destroyed.
		"""

		self.instrument.project.RemoveListener(self)
		self.instrument.RemoveListener(self)
		self.window.destroy()
		
	#_____________________________________________________________________	
	
	def OnCancel(self, button):
		"""
			If the Cancel button is pressed, the dialog is destroyed.
		"""
		self.instrument.project.RemoveListener(self)
		self.instrument.RemoveListener(self)	
		self.window.destroy()

	#_____________________________________________________________________	

	def OnTransport(self, button):
		"""
			Pressing the Play/Stop button on the dialog box allows the user
			to play back the project to test if the effect settings are
			right for them. When user press the Play button, it switches to
			a stop button, and vice versa.
		"""
		if self.isPlaying == False:
			# things to do if the project is not already playing, and hence
			# needs to start playing
			self.instrument.project.play()
			self.isPlaying = True
		else:
			self.instrument.project.stop()
			self.isPlaying = False

	#_____________________________________________________________________

	def OnStateChanged(self,obj,change=None, *extra):
		
		if obj is self.instrument and change == "effects":
			self.Update()
		
		# check self.isPlaying to see if the project is playing already
		elif change == "play":
			# things to do if the project is not already playing, and hence
			# needs to start playing
			self.transportbutton.set_use_stock(True)
			self.transportbutton.set_label(gtk.STOCK_MEDIA_STOP)
			
			# set this to True to show we are now playing
			self.isPlaying = True

		elif change =="stop":
			# things to do when the stop button is pressed to stop playback
			self.transportbutton.set_use_stock(True)
			self.transportbutton.set_label(gtk.STOCK_MEDIA_PLAY)
			
			# set this to False to show we are no longer playing
			self.isPlaying = False
					

	#_____________________________________________________________________	

	def OnSelectEffect(self, combo):
		"""
			Callback for when an effect is selected from the effects list.
		"""
		self.addeffect.set_sensitive(True)
		
	#_____________________________________________________________________	

	def OnAddEffect(self, widget):
		"""
			Get the name of the currently selected effect
			and add it to the instrument.
		"""
		effectindex = self.effectscombo.get_active()	
		# quit if there is no active selection
		if effectindex == -1:
			return
		
		# check the actively selected name  matches the 
		# value in the gtk.Entry if it doesn't then a search was
		# probably abandoned without selecting so ignore this
		if Globals.LADSPA_NAME_MAP[effectindex][1] != self.effectsEntry.get_text():
			return
		
		name = Globals.LADSPA_NAME_MAP[effectindex][0]
		self.instrument.AddEffect(name)
		
	#_____________________________________________________________________
	
	def OnRemoveEffect(self, widget, effect):
		"""
			Remove an effect from the instrument.
		"""
		self.instrument.RemoveEffect(effect)
		
	#_____________________________________________________________________
		
	def OnEffectSetting(self, button, effect):
		"""
			Show a dialog filled with settings sliders for a specific effect
		"""
		
		# TODO: Make this modal or as part of the effects window"""

		# grab references the effect position in the table and the
		# effect element itself
		self.effectpos = self.effectsbox.child_get_property(button, "position")
		self.effectelement = self.instrument.effects[self.effectpos]
		
		# this variable is used to slash the values for the different sliders
		self.sliderdict = {}
		
		# set the index of the current edited effect - used to reference the
		# effect elsewhere
						
		self.settWin = gtk.glade.XML(Globals.GLADE_PATH, "EffectSettingsDialog")

		settsignals = {
			"on_cancelbutton_clicked" : self.OnEffectSettingCancel,
			"on_okbutton_clicked" : self.OnEffectSettingOK,
			"on_savepresetbutton_clicked" : self.OnSaveSingleEffectPreset,
			"on_presetcombo_changed" : self.OnEffectPresetChanged
		}

		self.settWin.signal_autoconnect(settsignals)

		# create references to glade items
		self.settingswindow = self.settWin.get_widget("EffectSettingsDialog")
		self.settingsvbox = self.settWin.get_widget("EffectSettingsVBox")
		#self.effectlabel = self.settWin.get_widget("effectlabel")
		#self.effectlabel.set_text(self.currentplugin)
		self.settingstable = self.settWin.get_widget("settingstable")
		self.presetcombo = self.settWin.get_widget("presetcombo")
		
		self.settingsHeaderCairoImage = CairoDialogHeaderImage(_("Effect Settings"))
		self.settingsHeaderCairoImage.set_size_request(450, 60)
		self.settingsvbox.pack_start(self.settingsHeaderCairoImage, False, False)
		self.settingsHeaderCairoImage.show()
		
		# grab a list of properties from the effect
		proplist = gobject.list_properties(self.instrument.effects[self.effectpos])
		
		# resize the settingstable to accomodate the number of effects
		# sliders required
		self.settingstable.resize(len(proplist), 2)
		
		count = 0
		
		# iterate through the properties list and determine the value type
		# of the property and show it where needed
		for property in proplist:		            
			# non readable params
			if not(property.flags & gobject.PARAM_READABLE):
				label = gtk.Label(property.name)
				label.set_alignment(1,0.5)
				self.settingstable.attach(label, 0, 1, count, count+1, gtk.SHRINK)

				rlabel = gtk.Label("-parameter not readable-")
				self.settingstable.attach(rlabel, 1, 2, count, count+1)

			# just display non-writable param values
			elif not(property.flags & gobject.PARAM_WRITABLE):
				label = gtk.Label(property.name)
				label.set_alignment(1,0.5)
				self.settingstable.attach(label, 0, 1, count, count+1)

				wvalue = self.effectelement.get_property(property.name)
				if wvalue:
					wlabel = gtk.Label(wvalue)
					self.settingstable.attach(wlabel, 1, 2, count, count+1, gtk.SHRINK)

			# TODO: tooltips using property.blurb

			elif hasattr(property, "minimum") and hasattr(property, "maximum"):
				label = gtk.Label(property.name)
				label.set_alignment(1,0.5)
				self.settingstable.attach(label, 0, 1, count, count+1, gtk.SHRINK)

				#guess that it's numeric - we can use an HScale
				value = self.effectelement.get_property(property.name)
				adj = gtk.Adjustment(value, property.minimum, property.maximum)

				adj.connect("value_changed", self.SetEffectSetting, property.name, property)
				self.sliderdict[property.name] = hscale = gtk.HScale(adj)
				hscale.set_value_pos(gtk.POS_RIGHT)
				# add step increment for mouse-wheel scrolling - proportional
				# to range in view. Must be at least the smallest interval
				# possible (determined by get_digits()) or scroll doesn't happen
				adj.step_increment = (property.maximum - property.minimum) / 100
				adj.step_increment = max(adj.step_increment, 1.0 / (10 ** hscale.get_digits()))
				
				#check for ints and change digits
				if not((property.value_type == gobject.TYPE_FLOAT) or
					   (property.value_type == gobject.TYPE_DOUBLE)):
					hscale.set_digits(0)
	
				self.settingstable.attach(self.sliderdict[property.name], 1, 2, count, count+1, gtk.FILL|gtk.EXPAND)
			
			count += 1

		# set up presets
		
		elementfactory = self.effectelement.get_factory().get_name()
		
		self.model = gtk.ListStore(str)
		self.presetcombo.set_model(self.model)

		# append preset for this effects plugin
		# if (a) it is on the system (in LADSPA_FACTORY_REGISTRY) and (b) if the preset is
		# only for that plugin. The list is shown in the presets combo box for this effect
		self.availpresets = []
		if elementfactory in Globals.LADSPA_FACTORY_REGISTRY:
			for key, value in self.presets.effectpresetregistry.iteritems():
				deps = value['dependencies']
				if len(deps) == 1 and elementfactory in deps:
					self.availpresets.append(key)
				

		for pres in self.availpresets:
			self.presetcombo.append_text(pres)
		
		self.settingstable.show()
		self.settingswindow.show_all()

	#_____________________________________________________________________	
		
	def OnEffectSettingOK(self, button):
		"""
			Close the effect settings window.
		"""
		
		self.settingswindow.destroy()

	#_____________________________________________________________________	
		
	def OnEffectSettingCancel(self, button):
		"""
			Close the effect settings window
		"""
		
		self.settingswindow.destroy()
		
	#_____________________________________________________________________	
		
	def SetEffectSetting(self, slider, name, property):
		"""
			Set the value of a gstreamer property from an effects slider.
		"""
		
		# grab the slider setting
		if not((property.value_type == gobject.TYPE_FLOAT) or
			   (property.value_type == gobject.TYPE_DOUBLE)):
			value = int(slider.get_value())
		else:
			value = slider.get_value()
		
		# now set the gstreamer property
		self.instrument.effects[self.effectpos].set_property(name, value)
		
	#_____________________________________________________________________	

	def OnSaveSingleEffectPreset(self, widget):
		"""
			Grab the effect properties and send it to the presets code
			to be saved.
		"""

		# grab the label from the combo
		label = self.presetcombo.get_active_text()
		
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
	
	def OnSaveEffectChainPreset(self, widget):
		"""
			Grab the chain send it to the presets code to be saved.
		"""

		label = self.chainpresetcombo.get_active_text()
		
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
	
	def OnSettingEntryChanged(self, widget):
		pass

	#_____________________________________________________________________	
	
	def OnEffectPresetChanged(self, combo):
		"""
			A preset is selected from the single effect preset
			combo. Load it.
		"""
		presetname = name = combo.get_active_text()
		if presetname not in self.availpresets:
			return

		settings = self.presets.LoadSingleEffectSettings(self.effectelement, presetname)
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
	
	def OnChainPresetChanged(self, combo):
		"""
			A preset is selected from the chain preset combo. Load it.
		"""
					
		presetname = name = combo.get_active_text()
		if presetname not in self.availpresets:
			return

		self.instrument.currentchainpreset = combo.get_active()
		settings = self.presets.LoadInstrumentEffectChain(presetname)
		
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
		self.window.present()
		
	#_____________________________________________________________________

	def matchEffect(self, completion, entrystr, iter):
		"""
		   Callback for matching on effect entry box
		   if the effect contains the current string
		   then returns True
		"""
		modelString = completion.get_model()[iter][0]
		return entrystr.lower() in modelString.lower()
		
	#_____________________________________________________________________

	def OnEntrySelected(self, completion, model, modelIter):
		"""
		   Callback for selection made in the entry completion for effects combo
		"""
		# read the effect description and scan the effectscombo
		# until it's found and set it active as this is what the add
		# button uses
		value = model.get_value(modelIter, 0)
		effectsModel = self.effectscombo.get_model()
		effectsIter = effectsModel.get_iter_first()
		while effectsModel.get_value(effectsIter, 0) != value:
			effectsIter = effectsModel.iter_next(effectsIter)
		self.effectscombo.set_active_iter(effectsIter)
	#_____________________________________________________________________
#=========================================================================

class CairoDialogHeaderImage(gtk.DrawingArea):
	"""
	   Renders a nice banner for the top of the effects
	   dialog using Cairo.
	"""
	
	_LEFT_GRADIENT_STOP_RGBA = (0, 0.99, 0.87, 0.38, 1)
	_RIGHT_GRADIENT_STOP_RGBA = (1, 0.93, 0.55, 0.16, 1)
	_TEXT_RGBA = (0.93, 0.55, 0.16, 1)
	_FONT_SIZE = 40
	_LEFT_LOGO_INDENT = 7
	_LEFT_TEXT_INDENT = 56
	
	#_____________________________________________________________________
	
	def __init__(self, headerText):
		gtk.DrawingArea.__init__(self)
		self.headerText = headerText
		
		self.connect("configure_event", self.OnSizeChanged)
		self.connect("expose-event", self.OnDraw)
		
		self.logo = cairo.ImageSurface.create_from_png(os.path.join(Globals.IMAGE_PATH, "jokosher-icon.png"))
		self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.allocation.width, self.allocation.height)
		self.GenerateCachedImage()
		
	#_____________________________________________________________________
		
	def OnSizeChanged(self, obj, evt):
		"""
		   Called when the widget's size changes
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

#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	InstrumentEffectsDialog.py
#	
#	This module us used to present the dialog for adding and managing instrument
#	effects. Note that this module deals with the main effects dialog *and* the
#	effect settings dialog.
#
#-------------------------------------------------------------------------------

import gtk
import gtk.glade
import gobject
import pygst
pygst.require("0.10")
import gst
import os
from ConfigParser import SafeConfigParser
import Project
import Globals
import EffectPresets
from EffectWidget import EffectWidget

class InstrumentEffectsDialog:
	
	#_____________________________________________________________________	
	
	def __init__(self, instrument):
		"""This constructor enables a bunch of variables, reads in the glade
		file for the main dialog, and populates the effects and presets
		combo boxes"""
		
		self.instrument = instrument
		self.res = gtk.glade.XML(Globals.GLADE_PATH, "InstrumentEffectsDialog")

		# this refers to the current effects Plugin
		self.currentplugin = None
		
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
		self.effectscombo = self.res.get_widget("effectscombo")
		self.effectsbox = self.res.get_widget("effectsbox")
		self.addeffect = self.res.get_widget("addbutton")
		self.instrumentimage = self.res.get_widget("instrumentimage")
		self.chainpresetcombo = self.res.get_widget("chainpresetcombo")
		self.chainsave = self.res.get_widget("chainpresetsave")
		self.transportbutton = self.res.get_widget("transportbutton")

		# here we grab the headerimage reference and then set the image
		self.headerimage = self.res.get_widget("headerimage")
		self.headerimage.set_from_file(os.path.join(Globals.IMAGE_PATH, "effectsheader.png"))
		
		# set the instrumentimage to the self.instrument icon
		self.instrumentimage.set_from_pixbuf(self.instrument.pixbuf)
		
		# set the model for the effects combo to a ListStore
		self.model = gtk.ListStore(str)
		self.effectscombo.set_model(self.model)

		for item in Globals.LADSPA_NAME_MAP:
			print item[1]
			longname = item[1]
			shortname = longname[:30]
			
			if len(longname) > 30:
				shortname = shortname + "..."
			
			self.effectscombo.append_text(shortname)

		if not self.instrument.effects == []:
			self.PopulateEffects()

		self.presets = EffectPresets.EffectPresets()

		# set up presets
						
		self.model = gtk.ListStore(str)
		self.chainpresetcombo.set_model(self.model)

		# mighty list comprehension that returns presets for this instrument
		# if it is on the system (in LADSPA_FACTORY_REGISTRY). It then adds the
		# presets to the chain presets combo box.

		availpresets = [x[0] for x in self.presets.effectpresetregistry.items() if x[1].get('instrument')== self.instrument.instrType and x[1]['dependencies'].issubset(Globals.LADSPA_FACTORY_REGISTRY)]
		
		for pres in availpresets:
			self.chainpresetcombo.append_text(pres)
			
		# this says if the project is playing, so we know to toggle the
		# transport button in the dialog	
		self.isPlaying = False	
			
	#_____________________________________________________________________	
		
	def OnOK(self, button):
			self.window.destroy()
		
	#_____________________________________________________________________	
				
	def OnCancel(self, button):
		self.window.destroy()

	#_____________________________________________________________________	

	def OnTransport(self, button):
		if self.isPlaying == False:
			self.instrument.project.play()
			self.transportbutton.set_use_stock(True)
			self.transportbutton.set_label(gtk.STOCK_MEDIA_STOP)
			self.chainsave.set_sensitive(False)
			self.addeffect.set_sensitive(False)
			self.chainpresetcombo.set_sensitive(False)
			self.effectscombo.set_sensitive(False)
			self.isPlaying = True
		else:
			self.instrument.project.stop()
			self.transportbutton.set_use_stock(True)
			self.transportbutton.set_label(gtk.STOCK_MEDIA_PLAY)
			self.chainsave.set_sensitive(True)
			self.addeffect.set_sensitive(True)
			self.chainpresetcombo.set_sensitive(True)
			self.effectscombo.set_sensitive(True)
			self.isPlaying = False
					

	#_____________________________________________________________________	

	def OnSelectEffect(self, combo):
		"""Callback for when an effect is selected from the effects list. This
		method looks up the name from the combo box in LADSPA_NAME_MAP and
		returns the factory name (e.g. ladspa-foo-effect). This is then set to
		self.currentplugin."""
		
		self.effectindex = combo.get_active()
		
		self.currentplugin = Globals.LADSPA_NAME_MAP[self.effectindex][0]
		
		#for e in Globals.LADSPA_NAME_MAP:
			#if Globals.LADSPA_NAME_MAP[e] == name:
				#self.currentplugin = e

	#_____________________________________________________________________	

	def OnAddEffect(self, combo):
		"""The effect element is created and added to the
		self.instrument.effects list"""
				
		# if self.instrument.effects is empty, this is the first effect being
		# added, and we need to unlink the converter and volume elements as
		# they had no effectsbin between them
		if self.instrument.effects == []:
			self.instrument.converterElement.unlink(self.instrument.volumeElement)

		self.instrument.effects.append(gst.element_factory_make(self.currentplugin, self.currentplugin))
		#self.instrument.effects.append(self.effect)

		effectname = Globals.LADSPA_NAME_MAP[self.effectindex][1]
		effectnum = len(self.instrument.effects) - 1
		print "ADDED INSTRUMENT NUMBER:"
		print effectnum
		effwidg = EffectWidget(self, effectname, effectnum)
		self.effectsbox.pack_start(effwidg, True)
		
		self.effectsbox.show_all()

	#_____________________________________________________________________	
		
	def OnEffectSetting(self, button):
		"""Show a dialog filled with settings sliders for a specific effect"""
		
		"""TODO: Make this modal or as part of the effects window"""

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
		self.effectlabel = self.settWin.get_widget("effectlabel")
		self.effectlabel.set_text(self.currentplugin)
		self.settingstable = self.settWin.get_widget("settingstable")
		self.presetcombo = self.settWin.get_widget("presetcombo")

		# set the dialog image
		self.headerimage = self.settWin.get_widget("headerimage")
		self.headerimage.set_from_file(os.path.join(Globals.IMAGE_PATH, "effectsettingsheader.png"))
		
		# grab a list of properties from the effect
		proplist = gobject.list_properties(self.instrument.effects[self.effectpos])
		
		# resize the settingstable to accomodate the number of effects
		# sliders required
		self.settingstable.resize(len(proplist), 2)
		
		count = 0
		
		# iterate through the properties list and determine the value type
		# of the property and show it where needed
		for property in proplist:		            
			#non readable params
			if not(property.flags & gobject.PARAM_READABLE):
				label = gtk.Label(property.name)
				label.set_alignment(1,0.5)
				self.settingstable.attach(label, 0, 1, count, count+1)

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
					self.settingstable.attach(wlabel, 1, 2, count, count+1)

			#TODO: tooltips using property.blurb

			elif hasattr(property, "minimum") and hasattr(property, "maximum"):
				label = gtk.Label(property.name)
				label.set_alignment(1,0.5)
				self.settingstable.attach(label, 0, 1, count, count+1)

				#guess that it's numeric - we can use an HScale
				value = self.effectelement.get_property(property.name)
				adj = gtk.Adjustment(value, property.minimum, property.maximum)

				adj.connect("value_changed", self.SetEffectSetting, property.name, property)
				self.sliderdict[property.name] = hscale = gtk.HScale(adj)
				hscale.set_value_pos(gtk.POS_RIGHT)
                
				#check for ints and change digits
				if not((property.value_type == gobject.TYPE_FLOAT) or
					   (property.value_type == gobject.TYPE_DOUBLE)):
					hscale.set_digits(0)
	
				self.settingstable.attach(self.sliderdict[property.name], 1, 2, count, count+1)
                
			count += 1

		# set up presets
		
		elementfactory = self.effectelement.get_factory().get_name()
		
		self.model = gtk.ListStore(str)
		self.presetcombo.set_model(self.model)

		# mighty list comprehension that returns presets for this effects plugin
		# if (a) it is on the system (in LADSPA_FACTORY_REGISTRY) and (b) if the preset is
		# only for that plugin. Witness the m/\d skillz. The values returned
		# are shown in the presets combo box for this effect
		availpresets = [x for x in self.presets.effectpresetregistry if self.presets.effectpresetregistry[x]['dependencies']==set([elementfactory]) and elementfactory in Globals.LADSPA_FACTORY_REGISTRY]

		for pres in availpresets:
			self.presetcombo.append_text(pres)
		
		self.settingstable.show()
		self.settingswindow.show_all()

	#_____________________________________________________________________	
		
	def OnEffectSettingOK(self, button):
		"""Close the window"""
		self.settingswindow.destroy()

	#_____________________________________________________________________	
		
	def OnEffectSettingCancel(self, button):
		"""Close the window"""
		self.settingswindow.destroy()
		
	#_____________________________________________________________________	
		
	def PopulateEffects(self):
		"""Fill the effectsbox table with the effects, iterated from the
		effects list"""
		
		# remove all effects from the effectsbox table
		map(self.effectsbox.remove, self.effectsbox.get_children())
		
		# for each effect in self.instrument.effects, add a button to the
		# table and connect a callback
		for effect in self.instrument.effects:
			self.currentplugin =  effect.get_factory().get_name()
			effectname =  effect.get_factory().get_longname()
			effectnum = len(self.instrument.effects) - 1
				
			effwidg = EffectWidget(self, effectname, effectnum)
			self.effectsbox.pack_start(effwidg, True)
			
			self.effectsbox.pack_start(effwidg)
		
			self.effectsbox.show_all()
				
	#_____________________________________________________________________	
		
	def SetEffectSetting(self, slider, name, property):
		"""Set the value of a gstreamer property from an effects slider"""
		
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
		"""Grab the effect properties and send it to the presets code to be saved"""

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
		"""Grab the chain send it to the presets code to be saved"""

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
		"""A preset is selected from the single effect preset combo. Load it."""
		presetname = name = combo.get_active_text()
		settings = self.presets.LoadSingleEffectSettings(self.effectelement, presetname)

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
		"""A preset is selected from the chain preset combo. Load it."""
		presetname = name = combo.get_active_text()
		settings = self.presets.LoadInstrumentEffectChain(presetname)
		
		self.instrument.effects = []
		
		for item in settings:
			effect = gst.element_factory_make(item, item)
			
			for sett in settings[item]:
				try:
					settings[item][sett]
					effect.set_property(sett, settings[item][sett])
				except:
					pass
		
			self.instrument.effects.append(effect)
		self.PopulateEffects()

	#_____________________________________________________________________	
	
	def OnRemoveEffect(self, widget, effectnum):

		try:
			self.instrument.effectsbin.remove(self.instrument.effects[effectnum])
		except:
			pass
		
		self.instrument.effects.pop(effectnum)
		
		self.PopulateEffects()
		
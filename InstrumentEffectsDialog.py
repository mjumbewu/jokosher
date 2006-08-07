
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

class InstrumentEffectsDialog:
	
	#_____________________________________________________________________	
	
	def __init__(self, instrument):
		
		self.instrument = instrument
		self.res = gtk.glade.XML(Globals.GLADE_PATH, "InstrumentEffectsDialog")

		# this refers to the current effects Plugin
		self.currentplugin = None
		
		self.signals = {
			"on_okbutton_clicked" : self.OnOK,
			"on_cancelbutton_clicked" : self.OnCancel,
			"on_previewbutton_clicked" : self.OnPreview,
			"on_effectscombo_changed" : self.OnSelectEffect,
			"on_addbutton_clicked" : self.OnAddEffect,
			"on_chainpresetsave_clicked" : self.OnSaveEffectChainPreset
		}
		
		self.res.signal_autoconnect(self.signals)

		self.window = self.res.get_widget("InstrumentEffectsDialog")
		self.effectscombo = self.res.get_widget("effectscombo")
		self.effectsbox = self.res.get_widget("effectsbox")
		self.addeffect = self.res.get_widget("addbutton")
		self.instrumentimage = self.res.get_widget("instrumentimage")
		self.chainpresetcombo = self.res.get_widget("chainpresetcombo")
		
		self.instrumentimage.set_from_pixbuf(self.instrument.pixbuf)
		
		thelist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
		self.effects = []
		for f in thelist:
			if "Filter/Effect/Audio/LADSPA" in f.get_klass():
				self.effects.append(f)

		self.model = gtk.ListStore(str)
		self.effectscombo.set_model(self.model)

		for item in self.effects:
			longname = item.get_longname()
			shortname = longname[:30]
			
			if len(longname) > 30:
				shortname = shortname + "..."
			
			self.effectscombo.append_text(shortname)

		if not self.effects == []:
			self.PopulateEffects()

		self.presets = EffectPresets.EffectPresets()
		
		#self.window.resize(350, 300)
		#self.window.set_icon(self.parent.icon)
		#self.window.set_transient_for(self.parent.window)
	
	#_____________________________________________________________________	
		
	def OnOK(self, button):
			self.window.destroy()
		
	#_____________________________________________________________________	
				
	def OnCancel(self, button):
		self.window.destroy()

	#_____________________________________________________________________	

	def OnPreview(self, button):
		self.window.destroy()

	#_____________________________________________________________________	

	def OnSelectEffect(self, combo):
		name = combo.get_active_text()

		for e in self.effects:
			if e.get_longname() == name:
				self.currentplugin = e.get_name()

	#_____________________________________________________________________	

	def OnAddEffect(self, combo):
		self.instrument.effects.append(gst.element_factory_make(self.currentplugin, self.currentplugin))
		#self.instrument.effects.append(self.effect)
		
		button = gtk.Button(self.currentplugin)
		button.connect("clicked", self.OnEffectSetting)
		self.effectsbox.pack_start(button)
		
		self.effectsbox.show_all()

	#_____________________________________________________________________	
		
	def OnEffectSetting(self, button):
		"""Show specific effects settings"""
		
		"""TODO: Make this modal or as part of the effects window"""

		self.effectpos = self.effectsbox.child_get_property(button, "position")
		
		# set the index of the current edited effect - used to reference the
		# effect elsewhere
						
		self.settWin = gtk.glade.XML(Globals.GLADE_PATH, "EffectSettingsDialog")

		settsignals = {
			"on_cancelbutton_clicked" : self.OnEffectSettingCancel,
			"on_okbutton_clicked" : self.OnEffectSettingOK,
			"on_savepresetbutton_clicked" : self.OnSaveSingleEffectPreset,
		}

		self.settWin.signal_autoconnect(settsignals)

		self.settingswindow = self.settWin.get_widget("EffectSettingsDialog")
		self.effectlabel = self.settWin.get_widget("effectlabel")
		self.settingstable = self.settWin.get_widget("settingstable")
		self.presetcombo = self.settWin.get_widget("presetcombo")
		
		proplist = gobject.list_properties(self.instrument.effects[self.effectpos])

		self.settingstable.resize(len(proplist), 2)
		
		count = 0

		element = self.instrument.effects[self.effectpos]

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

				wvalue = element.get_property(property.name)
				if wvalue:
					wlabel = gtk.Label(wvalue)
					self.settingstable.attach(wlabel, 1, 2, count, count+1)

			#TODO: tooltips using property.blurb

			elif hasattr(property, "minimum") and hasattr(property, "maximum"):
				label = gtk.Label(property.name)
				label.set_alignment(1,0.5)
				self.settingstable.attach(label, 0, 1, count, count+1)

				#guess that it's numeric - we can use an HScale
				value = element.get_property(property.name)
				adj = gtk.Adjustment(value, property.minimum, property.maximum)

				adj.connect("value_changed", self.SetEffectSetting, property.name, property)
				hscale = gtk.HScale(adj)
				hscale.set_value_pos(gtk.POS_RIGHT)
                
				#check for ints and change digits
				if not((property.value_type == gobject.TYPE_FLOAT) or
					   (property.value_type == gobject.TYPE_DOUBLE)):
					hscale.set_digits(0)
	
				self.settingstable.attach(hscale, 1, 2, count, count+1)
                
			count += 1

		#self.effectlabel.set_text("hello")
		self.settingstable.show()
		self.settingswindow.show_all()

	#_____________________________________________________________________	
		
	def OnEffectSettingOK(self, button):
			self.settingswindow.destroy()

	#_____________________________________________________________________	
		
	def OnEffectSettingCancel(self, button):
			self.settingswindow.destroy()
		
	#_____________________________________________________________________	
		
	def PopulateEffects(self):
			print "Populating effects"
			
			for effect in self.instrument.effects:
				self.currentplugin =  effect.get_factory().get_name()
				print effect.get_factory().get_name()
				
				button = gtk.Button(self.currentplugin)
				button.connect("clicked", self.OnEffectSetting)
				self.effectsbox.pack_start(button)
		
				self.effectsbox.show_all()
				
	#_____________________________________________________________________	
		
	def SetEffectSetting(self, slider, name, property):
		"""set the value of an effects slider to its property"""
		
		if not((property.value_type == gobject.TYPE_FLOAT) or
			   (property.value_type == gobject.TYPE_DOUBLE)):
			value = int(slider.get_value())
		else:
			value = slider.get_value()
		
		self.instrument.effects[self.effectpos].set_property(name, value)
		
	#_____________________________________________________________________	


	def OnSaveSingleEffectPreset(self, widget):
		"""Grab the effect properties and send it to the presets code to be saved"""

		label = self.presetcombo.get_active_text()
		
		effectdict = {}
		
		effect = self.instrument.effects[self.effectpos]
		effectelement = effect.get_factory().get_name()
		
		proplist = gobject.list_properties(effect)
		
		for property in proplist:
			effectdict[property.name] = effect.get_property(property.name)

		self.presets.SaveSingleEffect(label, effectdict, effectelement, "LADSPA")
		
	#_____________________________________________________________________	
	
	def OnSaveEffectChainPreset(self, widget):
		"""Grab the effect properties and send it to the presets code to be saved"""

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
		

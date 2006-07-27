
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

class InstrumentEffectsDialog:
	
	#_____________________________________________________________________	
	
	def __init__(self, instrument):
		
		self.instrument = instrument
		self.res = gtk.glade.XML(Globals.GLADE_PATH, "InstrumentEffectsDialog")

		# this refers to the current effects Plugin
		self.currentplugin = None
		self.currentedit = None
		
		self.signals = {
			"on_okbutton_clicked" : self.OnOK,
			"on_cancelbutton_clicked" : self.OnCancel,
			"on_previewbutton_clicked" : self.OnPreview,
			"on_effectscombo_changed" : self.OnSelectEffect,
			"on_addbutton_clicked" : self.OnAddEffect

		}
		
		self.res.signal_autoconnect(self.signals)

		self.window = self.res.get_widget("InstrumentEffectsDialog")
		self.effectscombo = self.res.get_widget("effectscombo")
		self.effectsbox = self.res.get_widget("effectsbox")
		self.addeffect = self.res.get_widget("addbutton")
		self.instrumentimage = self.res.get_widget("instrumentimage")
		
		self.instrumentimage.set_from_file(self.instrument.pixbufPath)
		
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
		print self.currentplugin
		self.instrument.effects.append(gst.element_factory_make(self.currentplugin, "effect"))
		#self.instrument.effects.append(self.effect)
		
		button = gtk.Button(self.currentplugin)
		button.connect("clicked", self.OnEffectSetting)
		self.effectsbox.pack_start(button)
		
		print self.instrument.effects
		self.effectsbox.show_all()

	#_____________________________________________________________________	
		
	def OnEffectSetting(self, button):
		print "Showing plugin settings"

		buttonpos = self.effectsbox.child_get_property(button, "position")
		self.currentedit = buttonpos
		
		self.settWin = gtk.glade.XML(Globals.GLADE_PATH, "EffectSettingsDialog")

		settsignals = {
			"on_cancelbutton_clicked" : self.OnEffectSettingCancel,
			"on_okbutton_clicked" : self.OnEffectSettingOK,

		}

		self.settWin.signal_autoconnect(settsignals)

		self.settingswindow = self.settWin.get_widget("EffectSettingsDialog")
		self.effectlabel = self.settWin.get_widget("effectlabel")
		self.settingstable = self.settWin.get_widget("settingstable")

		proplist = gobject.list_properties(self.instrument.effects[buttonpos])
		
		rows = 0
		
		for property in proplist:
			scale = gtk.HScale()
			lab = gtk.Label(property.name)
			print property.name + " " + property.value_type.name
			print "\tvalue: " + str(self.instrument.effects[buttonpos].get_property(property.name))
			if hasattr(property, "minimum") == True:
				print "GET:"
				#print self.instrument.effects[self.currentedit].get_property(property.name)
				scale.connect("value-changed", self.SetEffectSetting, property.name)
				scale.set_range(property.minimum, property.maximum)
				scale.set_value(self.instrument.effects[self.currentedit].get_property(property.name))

			self.settingstable.resize(rows, 2)
			self.settingstable.attach(lab, 0, 1, rows-1, rows)
			self.settingstable.attach(scale, 1, 2, rows-1, rows)
			lab.show()
			scale.show()
			rows = rows + 1

		self.effectlabel.set_text("hello")

		self.settingswindow.show()

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
		
	def SetEffectSetting(self, slider, name):
		#print slider
		print name
		print "NEW"
		print slider.get_value()
		self.instrument.effects[self.currentedit].set_property(name, slider.get_value())
		

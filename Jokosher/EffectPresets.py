#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	EffectPresets.py
#	
#	This module implements support for effects presets. These presets are used
#	to store settings for single effects and multiple effects strung together
#	(called a 'chain').
#
#	The way this works is that we have a LADSPA_FACTORY_REGISTRY filled with
#	the system's LADSPA effects, LADSPA_NAME_MAP which amps LADSPA element
#	factory names (Such as ladspa-delay-5s) to the effect name (such as
#	Simple Delay) and self.effectpresetsregistry which contains a generated
#	dictionary of effects. This dictionary is search with list comprehensions
#	to get the relavent presets out.
#
#-------------------------------------------------------------------------------

import pygst
pygst.require("0.10")
import gst
import xml.dom.minidom as xml
import os
import Globals
from Utils import *
import glob
import string

#=========================================================================

class EffectPresets:
	"""
	This class implements support for effects presets. These presets are used
	to store settings for single effects and multiple effects strung together
	(called a 'chain').
	"""
	#_____________________________________________________________________	
	
	def __init__(self):
		"""
		Creates a new instance of EffectsPresets. If needed, it populates the
		LADSPA and effect presets registries.
		"""
		Globals.EFFECT_PRESETS_VERSION = "0.2"
		
		# this is the main dictionary of presets
		self.effectpresetregistry = {}
		
		# fill the different data structures with information if necessary. The LADSPA
		# structures are part of Globals.py

		if Globals.LADSPA_NAME_MAP==[] or Globals.LADSPA_FACTORY_REGISTRY == None:
			self.FillLADSPARegistry()

		self.FillEffectsPresetsRegistry()
	
	#_____________________________________________________________________

	def SaveSingleEffect(self, label, effectdict, effectelement, effecttype):
		"""
		This method will write a single effect preset to a preset file.
		
		Parameters:
			label --the name of the effect.
			effectdict -- the effect dictionary.
			effectelement -- the effect that the user selected.
			effecttype -- the type of the effect the user selected.
		"""
		self.effectelement = effectelement
		self.effecttype = effecttype
	
		if not Globals.EFFECT_PRESETS_PATH:
			raise "No save path specified!"
		
		doc = xml.Document()
		head = doc.createElement("JokosherPreset")
		doc.appendChild(head)
		
		head.setAttribute("version", Globals.EFFECT_PRESETS_VERSION)

		effectblock = doc.createElement("Effect")
		#effectblock.setAttribute("element", effectelement)
		#effectblock.setAttribute("effectype", effecttype)
		head.appendChild(effectblock)
		
		paramsblock = doc.createElement("Parameters")
		effectblock.appendChild(paramsblock)
		
		paramslist = ["effectelement", "effecttype"]
		
		StoreParametersToXML(self, doc, paramsblock, paramslist)
		
		settingsblock = doc.createElement("Settings")
		effectblock.appendChild(settingsblock)
		
		StoreDictionaryToXML(doc, settingsblock, effectdict)
		
		file = open(Globals.EFFECT_PRESETS_PATH + "/" + label + ".jpreset", "w")
		file.write(doc.toprettyxml())
		file.close()
		
	#_____________________________________________________________________

	def SaveEffectChain(self, label, effectlist, instrumenttype):
		"""
		Write an effect chain to a preset file.
		
		Parameters:
			label -- the name of the effect.
			effectlist -- the list of effects.
			instrumenttype -- the type of instrument currently being used.
		"""		
		self.effectelement = None
		self.effecttype = None
		
		if not Globals.EFFECT_PRESETS_PATH:
			raise "No save path specified!"
		
		doc = xml.Document()
		head = doc.createElement("JokosherPreset")
		doc.appendChild(head)
		
		head.setAttribute("version", Globals.EFFECT_PRESETS_VERSION)

		# effect chain preset files have an extra <Chain> block which mainly
		# serves to indicate which type of instrument the effect is for
		chainblock = doc.createElement("Chain")
		head.appendChild(chainblock)
			
		chaindict = {}
		chaindict["instrument"] = instrumenttype

		StoreDictionaryToXML(doc, chainblock, chaindict)

		# the structure of each <Effect> tag is not different from the single
		# effect presets, there is just an <Effect> block for each effect in
		# the chain
		for effect in effectlist:
			self.effectelement = effect["effectelement"]
			self.effecttype = effect["effecttype"]
		
			Globals.debug(self.effectelement)

			effectblock = doc.createElement("Effect")
			head.appendChild(effectblock)
						
			paramsblock = doc.createElement("Parameters")
			effectblock.appendChild(paramsblock)
			
			paramslist = ["effectelement", "effecttype"]
			
			StoreParametersToXML(self, doc, paramsblock, paramslist)
			
			settingsblock = doc.createElement("Settings")
			effectblock.appendChild(settingsblock)
			
			StoreDictionaryToXML(doc, settingsblock, effect["settings"])
		
		presetfile = open(Globals.EFFECT_PRESETS_PATH + "/" + label + ".jpreset", "w")
		presetfile.write(doc.toprettyxml())
		presetfile.close()
		
	#_____________________________________________________________________
	
	def LoadSingleEffectSettings(self, effectelement, presetname):
		"""
		Load effect settings from a preset file for a single effect.
		
		Parameters:
			effectelement -- the effect element to be loaded.
			presetname -- the name of the preset to be loaded.
			
		Returns:
			a settings dictionary with the loaded settings for the effect.
		"""
		presetfile = Globals.EFFECT_PRESETS_PATH + "/" + presetname + ".jpreset"
		Globals.debug(presetfile)

		if not os.path.exists(presetfile):
			Globals.debug("preset file does not exist")
			return False
		else:	
			xmlfile = open(presetfile, "r")
			doc = xml.parse(presetfile)

		settingstags = doc.getElementsByTagName('Effect')[0].getElementsByTagName('Settings')[0]
		settdict = LoadDictionaryFromXML(settingstags)
		
		return settdict
	#_____________________________________________________________________
	
	def LoadSingleEffectList(self):
		"""
		TODO -- This method is not yet implemented.
		"""
		pass
		
	#_____________________________________________________________________
	
	def LoadInstrumentEffectList(self):
		"""
		TODO -- This method is not yet implemented.
		"""
		pass
		
	#_____________________________________________________________________
	
	def LoadInstrumentEffectChain(self, presetname):
		"""
		Load settings from the preset file for an effects chain.
		
		Parameters:
			presetname -- name of the preset to be loaded.
			
		Returns:
			a settings dictionary with the loaded settings for the effects.
		"""
		presetfile = Globals.EFFECT_PRESETS_PATH + "/" + presetname + ".jpreset"
			
		if not os.path.exists(presetfile):
			Globals.debug("preset file does not exist")
		else:	
			xmlfile = open(presetfile, "r")
			doc = xml.parse(presetfile)

		settdict = {}
		
		for effect in doc.getElementsByTagName('Effect'):
			preftags = effect.getElementsByTagName('Parameters')[0]
			prefs = LoadDictionaryFromXML(preftags)

			settingstags = effect.getElementsByTagName('Settings')[0]
			setts = LoadDictionaryFromXML(settingstags)
			elementname = setts["name"]
			settdict[str(elementname)] = {'preferences': prefs, 'settings': setts}

		return settdict
		
	#_____________________________________________________________________
	
	def FillEffectsPresetsRegistry(self):
		"""
		Load all presets into the main presets registry.
		"""
		Globals.debug("\tReading in presets...")
		presetsfiles = glob.glob(Globals.EFFECT_PRESETS_PATH + "/*.jpreset")
		
		for file_ in presetsfiles:
			preset = {}
			depslist = []
			presetname = None
			
			if not os.path.exists(file_):
				Globals.debug("preset file does not exist")
			else:	
				xmlfile = open(file_, "r")
				doc = xml.parse(file_)

			ischain = None
			
			try:	
				instrument = doc.getElementsByTagName('Chain')[0].getElementsByTagName('instrument')[0].getAttribute('value')
				ischain = 1
			except:
				instrument = None
			
			
			for effect in doc.getElementsByTagName("Effect"):
				paramtags = effect.getElementsByTagName("Parameters")[0]

				for node in paramtags.childNodes:
					if node.nodeType == xml.Node.ELEMENT_NODE:
						if node.getAttribute("type") == "int":
							pass
						elif node.getAttribute("type") == "float":
							pass
						else:
							if node.tagName == "effectelement":
								depslist.append(str(node.getAttribute("value")))
			
			presetname = file_.replace(str(Globals.EFFECT_PRESETS_PATH + "/"), "")
			presetfile = presetname
			presetname = presetname.replace(".jpreset", "")
			
			preset["dependencies"] = set(depslist)
			preset["file"] = str(presetfile)
			
			if ischain == 1:
				preset["instrument"] = str(instrument)
			
			self.effectpresetregistry[presetname] = preset
		
		Globals.debug("\t...done.")
		
	#_____________________________________________________________________
	
	def FillLADSPARegistry(self):
		"""
		Fill Globals.LADSPA_FACTORY_REGISTRY with effects on the system. This
		is to ensure that only presets with effects on the current system are listed.
		"""
		Globals.debug("Filling LADSPA Registry")
		
		##make sure all the structures are empty before we append to them
		Globals.LADSPA_NAME_MAP=[]
		Globals.LADSPA_FACTORY_REGISTRY = None
		effects = []

		gstFeatures = gst.registry_get_default().get_feature_list(gst.ElementFactory)
		
		for feature in gstFeatures:
			if "Filter/Effect/Audio/LADSPA" in feature.get_klass():
				# from the list of LADSPA effects we check which ones only
				# have a single sink and a single src so we know they work
				if feature.get_num_pad_templates() == 2:
					sinkpads = 0
					srcpads = 0
					pads = feature.get_static_pad_templates()
				
					for pad in pads:
						if pad.direction == gst.PAD_SINK:
							sinkpads += 1

						if pad.direction == gst.PAD_SRC:
							srcpads += 1
					
					if srcpads == 1 and sinkpads == 1:
						effects.append(feature.get_name())
						Globals.LADSPA_NAME_MAP.append((feature.get_name(), feature.get_longname()))

		Globals.debug("\t", len(effects), "LADSPA effects loaded")
		Globals.LADSPA_FACTORY_REGISTRY = set(effects)
		
	#_____________________________________________________________________
	
#=========================================================================

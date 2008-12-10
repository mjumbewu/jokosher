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
import gobject
import xml.dom.minidom as xml
import os
import Globals
from Utils import *
import glob
import string

#=========================================================================

class EffectPresets(gobject.GObject):
	"""
	This class implements support for effects presets. These presets are used
	to store settings for single effects and multiple effects strung together
	(called a 'chain').

	Signals:
		"single-preset" -- The waveform date for this event has changed.
		"chain-preset" -- The starting position of this event has changed.

	"""
	__gsignals__ = {
		"single-preset" 	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"chain-preset" 	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () )
	}
	
	#_____________________________________________________________________	
	
	def __init__(self):
		"""
		Creates a new instance of EffectsPresets. If needed, it populates the
		LADSPA and effect presets registries.
		"""
		gobject.GObject.__init__(self)
		
		# Version of the preset files xml format
		Globals.EFFECT_PRESETS_VERSION = "0.2"
		
		"""
		This is the main dictionary of presets. It has the following structure when filled:
		
		 	effectpresetregistry[presetType][elementName][presetname][property]
		 	
		where:
			presetType = "instruments" or "effects"
			elementName = unique ladspa or instrument name (i.e. ladspa-eq or guitar)
			presetName = name of the preset (i.e. Chorus + Delay)
			property = an specific preset property (i.e. dependencies or file)
			
			*Note: all these 4 fields are dictionaries
		
		Diagram:
		
		effectpresetregistry
			|
			+--instruments
			|  |
			|  +--guitar
			|  |  |
			|  |  +--Chorus + Delay
			|  |  |  |
			|  |  |  +--instrument: guitar
			|  |  |  +--dependencies: ["effect1", "effect2"]
			|  |  |  +--file: guitar - Chorus + Delay.jpreset
			|  |  |
			|  |  +--Heavy Metal
			|  |     |
			|  |     +-- (...)
			|  |
			|  +--audiofile
			|     |
			|     +--Delay chamber
			|     |  |
			|     |  +-- (...)
			|     |
			|     +--Hum removal
			|        |
			|        +-- (...)
			|
			+--effects
			   |
			   +--ladspa-eq
			   |  |
			   |  +--Rock
			   |  |  |
			   |  |  +--dependencies: ["effect1", "effect2"]
			   |  |  +--file: ladspa-eq - Rock.jpreset
			   |  |
			   |  +--Jazz
			   |  |  |
			   |  |  +-- (...)
			   |  |
			   |  +--Pop
			   |     |
			   |     +-- (...)
			   |
			   +--ladspa-chorus
			      |
			      +--Full depth
			      |  |
			      |  +-- (...)
			      |
			      +--Bubbly dream
			         |
			         +-- (...)
		"""
		self.effectpresetregistry = {}
		
		# string used to separate the preset type from its name when generating
		# a preset filename
		self.separator = " - "
		
		# fill the different data structures with information if necessary. The LADSPA
		# structures are part of Globals.py

		if not Globals.LADSPA_NAME_MAP or not Globals.LADSPA_FACTORY_REGISTRY:
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
			raise Exception("No preset save path specified!")
		
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
		
		filename = self._PresetFilename(effectelement, label)
		file = open(Globals.EFFECT_PRESETS_PATH + filename, "w")
		file.write(doc.toprettyxml())
		file.close()
		
		self.emit("single-preset")
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
			raise Exception("No effect chain preset save path specified!")
		
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
		
		filename = self._PresetFilename(instrumenttype, label)
		presetfile = open(os.path.realpath(Globals.EFFECT_PRESETS_PATH + filename), "w")
		presetfile.write(doc.toprettyxml())
		presetfile.close()
		
		self.emit("chain-preset")
		
	#_____________________________________________________________________
	
	def LoadSingleEffect(self, presetName, effectelement):
		"""
		Load effect settings from a preset file for a single effect.
		
		Parameters:
			presetName -- the name of the preset to be loaded.
			effectelement -- the effect element to be loaded.
			
		Returns:
			a settings dictionary with the loaded settings for the effect or
			False if the preset file doesn't exist.
		"""
		filename = self._PresetFilename(effectelement, presetName)
		presetfile = Globals.EFFECT_PRESETS_PATH + filename
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
	
	#____________________________________________________________________
	
	def LoadEffectChain(self, presetName, instrType):
		"""
		Load settings from the preset file for an Instrument's effects chain.
		
		Parameters:
			presetName -- name of the preset to be loaded.
			
		Returns:
			a settings dictionary with the loaded settings for the effects.
		"""
		filename = self._PresetFilename(instrType, presetName)
		presetfile = Globals.EFFECT_PRESETS_PATH + filename
		
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
	
	def LoadSingleEffectList(self):
		"""
		TODO -- This method is not yet implemented.
		"""
		pass
		
	#_____________________________________________________________________
	
	def LoadEffectChainList(self):
		"""
		TODO -- This method is not yet implemented.
		"""
		pass
		
	#_____________________________________________________________________
	
	def DeleteSingleEffect(self, presetName, effectName):
		"""
		Removes a single effect preset.
		
		Parameters:
			presetName -- name of the preset to be removed.
			effectName -- ladspa unique name of the effect the preset 
							belongs to.
		"""
		self._DeletePresetFile(self._PresetFilename(effectName, presetName))
		self.emit("single-preset")
	
	#_____________________________________________________________________
	
	def DeleteEffectChain(self, presetName, instrType):
		"""
		Removes an effect chain preset.
		
		Parameters:
			presetName -- name of the preset to be removed.
			instrType -- type of the Instrument the preset belongs to.
		"""
		self._DeletePresetFile(self._PresetFilename(instrType, presetName))
		self.emit("chain-preset")
	
	#_____________________________________________________________________
	
	def _DeletePresetFile(self, filename):
		"""
		Removes a preset file.
		
		Parameters:
			filename -- name of the preset file to remove.
		"""
		presetFile = os.path.expanduser(Globals.EFFECT_PRESETS_PATH + filename)
		
		if os.path.isfile(presetFile):
			os.remove(presetFile)
	
	#_____________________________________________________________________
	
	def _PresetFilename(self, prefix, name):
		"""
		Creates the correct preset filename according to the parameters.
		
		Examples:	
			PresetFilename("Guitar", "Soloist") will output:
				"/Guitar %separator% Soloist.jpreset"
				
			PresetFilename("ladspa-delay", "5ms deep delay") will output:
				"/ladspa-delay %separator% 5ms deep delay.jpreset"
			
			where %separator% is the separator string defined inside __init__
			
		Parameters:
			prefix -- unique ladspa shortname or instrType.
			name -- name of the preset.
			
		Returns:
			a properly formatted preset filename string.
		"""
		return ("/%s%s%s.jpreset") % (prefix, self.separator, name)
	
	#_____________________________________________________________________
	
	def FillEffectsPresetsRegistry(self):
		"""
		Load all chain/effect presets into the main presets registry.
		"""
		Globals.debug("\tReading in presets...")
		presetsfiles = glob.glob(Globals.EFFECT_PRESETS_PATH + "/*.jpreset")
		
		self.effectpresetregistry = {}
		self.effectpresetregistry["instruments"] = {}
		self.effectpresetregistry["effects"] = {}
		
		for file_ in presetsfiles:
			preset = {}
			depslist = []
			presetname = None
			effectName = None
			
			if not os.path.exists(file_):
				Globals.debug("preset file does not exist")
			else:	
				xmlfile = open(file_, "r")
				doc = xml.parse(file_)

			# True if the loaded preset corresponds to an effect chain, False otherwise
			isChain = None
			
			try:	
				instrument = doc.getElementsByTagName('Chain')[0].getElementsByTagName('instrument')[0].getAttribute('value')
				isChain = True
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
								effectName = str(node.getAttribute("value"))
			
			presetname = file_.replace(str(Globals.EFFECT_PRESETS_PATH + "/"), "")
			presetfile = presetname
			
			# extract the preset name from the prefix
			presetname = presetname.split(self.separator, 1)
			if len(presetname) == 1:
				# the filename doesn't have a prefix. Could be an old or non-compliant file
				# TODO: should upgrade the filename or it won't load
				presetname = presetname[0]
			else:
				presetname = presetname[1]
			
			presetname = presetname.replace(".jpreset", "")	
			preset["dependencies"] = set(depslist)
			preset["file"] = str(presetfile)
			
			if isChain:
				preset["instrument"] = str(instrument)
				presetType = "instruments"
				elementName = instrument
			else:
				presetType = "effects"
				elementName = effectName
				
			# create the elementName dir if it doesn't exist
			try:
				self.effectpresetregistry[presetType][elementName]
			except KeyError:
				self.effectpresetregistry[presetType][elementName] = {}
			
			self.effectpresetregistry[presetType][elementName][presetname] = preset
			
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

		ladspaFactoryList = gst.registry_get_default().get_feature_list_by_plugin("ladspa")
		
		for factory in ladspaFactoryList:
			if isinstance(factory, gst.ElementFactory):
				# from the list of LADSPA effects we check which ones only
				# have a single sink and a single src so we know they work
				if factory.get_num_pad_templates() == 2:
					pads = factory.get_static_pad_templates()
					sinkpads = len( [pad for pad in pads if pad.direction == gst.PAD_SINK] )
					srcpads = len( [pad for pad in pads if pad.direction == gst.PAD_SRC] )
					
					if srcpads == 1 and sinkpads == 1:
						effects.append(factory.get_name())
						Globals.LADSPA_NAME_MAP.append((factory.get_name(), factory.get_longname()))

		Globals.debug("\t", len(effects), "LADSPA effects loaded")
		Globals.LADSPA_FACTORY_REGISTRY = set(effects)
		
	#_____________________________________________________________________
	
#=========================================================================

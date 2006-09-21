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

import gtk
import gtk.glade
import gobject
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

	#_____________________________________________________________________    
	
	def __init__(self):
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
		"""Write a single effect preset to a preset file"""
	
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
		
		StoreDictionaryToXML(self, doc, settingsblock, effectdict)
		
		f = open(Globals.EFFECT_PRESETS_PATH + "/" + label + ".jpreset", "w")
		f.write(doc.toprettyxml())
		f.close()
		
	#_____________________________________________________________________    

	def SaveEffectChain(self, label, effectlist, instrumenttype):
		"""Write an effect chain to a preset file"""        
		
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

		StoreDictionaryToXML(self, doc, chainblock, chaindict)

		# the structure of each <Effect> tag is not different from the single
		# effect presets, there is just an <Effect> block for each effect in
		# the chain
		for eff in effectlist:
			self.effectelement = eff["effectelement"]
			self.effecttype = eff["effecttype"]
		
			print self.effectelement

			effectblock = doc.createElement("Effect")
			head.appendChild(effectblock)
						
			paramsblock = doc.createElement("Parameters")
			effectblock.appendChild(paramsblock)
			
			paramslist = ["effectelement", "effecttype"]
			
			StoreParametersToXML(self, doc, paramsblock, paramslist)
			
			settingsblock = doc.createElement("Settings")
			effectblock.appendChild(settingsblock)
			
			StoreDictionaryToXML(self, doc, settingsblock, eff["settings"])
		
		f = open(Globals.EFFECT_PRESETS_PATH + "/" + label + ".jpreset", "w")
		f.write(doc.toprettyxml())
		f.close()
		
	#_____________________________________________________________________
	
	def LoadSingleEffectSettings(self, effectelement, presetname):
		"""Load effect settings from a preset file for a single effect"""

		presetfile = Globals.EFFECT_PRESETS_PATH + "/" + presetname + ".jpreset"
		print presetfile
			
		if not os.path.exists(presetfile):
			print "preset file does not exist"
		else:	
			xmlfile = open(presetfile, "r")
			doc = xml.parse(presetfile)

		settingstags = doc.getElementsByTagName('Effect')[0].getElementsByTagName('Settings')[0]
		settdict = LoadDictionaryFromXML(settingstags)
		
		return settdict
	#_____________________________________________________________________    
	
	def LoadSingleEffectList(self):
		pass
		
	#_____________________________________________________________________    
	
	def LoadInstrumentEffectList(self):
		pass
		
	#_____________________________________________________________________    
	
	def LoadInstrumentEffectChain(self, presetname):
		"""Load settings from the preset file for an effects chain"""
		
		presetfile = Globals.EFFECT_PRESETS_PATH + "/" + presetname + ".jpreset"
			
		if not os.path.exists(presetfile):
			print "preset file does not exist"
		else:	
			xmlfile = open(presetfile, "r")
			doc = xml.parse(presetfile)

		settdict = {}
		
		for eff in doc.getElementsByTagName('Effect'):
			settingstags = eff.getElementsByTagName('Settings')[0]
			setts = LoadDictionaryFromXML(settingstags)
			elementname = setts["name"]
			settdict[str(elementname)] = setts
		
		return settdict
		
	#_____________________________________________________________________
	
	def FillEffectsPresetsRegistry(self):
		"""Read in all presets into the main presets registry"""
		
		print "Reading in presets..."
		presetsfiles = glob.glob(Globals.EFFECT_PRESETS_PATH + "/*.jpreset")
		
		for f in presetsfiles:
			preset = {}
			depslist = []
			presetname = None
			
			if not os.path.exists(f):
				print "preset file does not exist"
			else:	
				xmlfile = open(f, "r")
				doc = xml.parse(f)

			ischain = None
			
			try:	
				instrument = doc.getElementsByTagName('Chain')[0].getElementsByTagName('instrument')[0].getAttribute('value')
				ischain = 1
			except:
				instrument = None
			
			
			for eff in doc.getElementsByTagName("Effect"):
				paramtags = eff.getElementsByTagName("Parameters")[0]

				for n in paramtags.childNodes:
					if n.nodeType == xml.Node.ELEMENT_NODE:
						if n.getAttribute("type") == "int":
							pass
						elif n.getAttribute("type") == "float":
							pass
						else:
							if n.tagName == "effectelement":
								depslist.append(str(n.getAttribute("value")))
			
			presetname = f.replace(str(Globals.EFFECT_PRESETS_PATH + "/"), "")
			presetfile = presetname
			presetname = presetname.replace(".jpreset", "")
			
			preset["dependencies"] = set(depslist)
			preset["file"] = str(presetfile)
			
			if ischain == 1:
				preset["instrument"] = str(instrument)
			
			self.effectpresetregistry[presetname] = preset
		
		print "...done"
		
	#_____________________________________________________________________
	
	def FillLADSPARegistry(self):
		"""Fill Globals.LADSPA_FACTORY_REGISTRY with effects on the system. This
		is to ensure only presets with effects on the current system are listed."""


		print "Filling LADSPA Registry"
		
		##make sure all the structures are empty before we append to them
		Globals.LADSPA_NAME_MAP=[]
		Globals.LADSPA_FACTORY_REGISTRY = None
		effects = []

		thelist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
		

		
		for f in thelist:
			if "Filter/Effect/Audio/LADSPA" in f.get_klass():
				# from the list of LADSPA effects we check which ones only
				# have a single sink and a single src so we know they work
				if f.get_num_pad_templates() == 2:
					sinkpads = 0
					srcpads = 0
					pads = f.get_static_pad_templates()
				
					for p in pads:
						if p.direction == gst.PAD_SINK:
							sinkpads += 1

						if p.direction == gst.PAD_SRC:
							srcpads += 1
					
					if srcpads == 1 and sinkpads == 1:
						effects.append(f.get_name())
						Globals.LADSPA_NAME_MAP.append((f.get_name(), f.get_longname()))

		print str(len(effects)) + " LADSPA effects loaded"
		Globals.LADSPA_FACTORY_REGISTRY = set(effects)
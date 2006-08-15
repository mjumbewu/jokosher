
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

		chainblock = doc.createElement("Chain")
		head.appendChild(chainblock)
			
		chaindict = {}
		chaindict["instrument"] = instrumenttype

		StoreDictionaryToXML(self, doc, chainblock, chaindict)

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
		print effectelement
		print presetname

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
		print presetname

		presetfile = Globals.EFFECT_PRESETS_PATH + "/" + presetname + ".jpreset"
		print presetfile
			
		if not os.path.exists(presetfile):
			print "preset file does not exist"
		else:	
			xmlfile = open(presetfile, "r")
			doc = xml.parse(presetfile)

		settdict = {}
		
		for eff in doc.getElementsByTagName('Effect'):
			settingstags = eff.getElementsByTagName('Settings')[0]
			#print settingstags
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
						#elif n.getAttribute("type") == "bool":
						#	value = (n.getAttribute("value") == "True")
						#	setattr(self, n.tagName, value)
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
		thelist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
		
		effects = []
		
		for f in thelist:
			if "Filter/Effect/Audio/LADSPA" in f.get_klass():
				effects.append(f.get_name())
				Globals.LADSPA_NAME_MAP[f.get_name()] = f.get_longname()
				
		Globals.LADSPA_FACTORY_REGISTRY = set(effects)
		
		print Globals.LADSPA_NAME_MAP
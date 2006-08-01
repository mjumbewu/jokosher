
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
import gzip

class EffectPresets:
    
    #_____________________________________________________________________    
    
    def __init__(self):
        Globals.EFFECT_PRESETS_VERSION = "0.2"
      
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
        
        f = gzip.GzipFile(Globals.EFFECT_PRESETS_PATH + "/" + label + ".jpreset", "w")
        f.write(doc.toprettyxml())
        f.close()

    #_____________________________________________________________________    

    def SaveEffectChain(self, label, effectlist):
        """Write an effect chain to a preset file"""        
                
        self.effectelement = None
        self.effecttype = None
                
        if not Globals.EFFECT_PRESETS_PATH:
            raise "No save path specified!"    
           
        doc = xml.Document()
        head = doc.createElement("JokosherPreset")
        doc.appendChild(head)
        
        head.setAttribute("version", Globals.EFFECT_PRESETS_VERSION)

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

        f = gzip.GzipFile(Globals.EFFECT_PRESETS_PATH + "/" + label + ".jpreset", "w")
        f.write(doc.toprettyxml())
        f.close()

    #_____________________________________________________________________
        
    def LoadSingleEffectSettings(self):
        pass
    
    #_____________________________________________________________________    
        
    def LoadSingleEffectList(self):
        pass

    #_____________________________________________________________________    
        
    def LoadInstrumentEffectList(self):
        pass
    
    #_____________________________________________________________________    
        
    def LoadInstrumentEffectChain(self):
        pass
    

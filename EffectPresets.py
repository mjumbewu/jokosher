
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
        Globals.EFFECTPRESETSVERSION = "0.2"
 
    #_____________________________________________________________________    
        
    def SaveSingleEffect(self, label, effectdict, effectelement, effecttype):
        print "save single effect"
        print label
        print effectdict

        if not Globals.EFFECTPRESETS_PATH:
            raise "No save path specified!"    
           
        doc = xml.Document()
        head = doc.createElement("JokosherPreset")
        doc.appendChild(head)
        
        head.setAttribute("version", Globals.EFFECTPRESETSVERSION)

        effectblock = doc.createElement("Effect")
        effectblock.setAttribute("element", effectelement)
        effectblock.setAttribute("effectype", effecttype)
        head.appendChild(effectblock)
        
        StoreDictionaryToXML(self, doc, effectblock, effectdict)
        
        f = gzip.GzipFile(Globals.EFFECTPRESETS_PATH + "/" + label + ".jpreset", "w")
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
    
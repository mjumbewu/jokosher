
import gtk
import gtk.glade
import gobject
import pygst
pygst.require("0.10")
import gst
import os
import Globals

class EffectPresets:
    
    #_____________________________________________________________________    
    
    def __init__(self):
        pass
    
    #_____________________________________________________________________    
        
    def SaveSingleEffect(self, label, effectdict):
        print "save single effect"
        print label
        print effectdict
        
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
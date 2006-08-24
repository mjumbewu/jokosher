#!/usr/bin/python
"""Very noddy Cairowaveform displayer
sil, Feb 2006
"""

import sys,gtk,gobject,random
import math, cairo

class WaveformWidget(gtk.DrawingArea):
 def __init__(self,maxpeak):
   "Pass the height of the highest peak possible"
   gtk.DrawingArea.__init__(self)
   self.set_events(gtk.gdk.POINTER_MOTION_MASK |
                               gtk.gdk.BUTTON_PRESS_MASK |
                               gtk.gdk.BUTTON_RELEASE_MASK)
   self.connect("expose_event",self.expose)
   self.connect("motion_notify_event", self.mousemove)
   self.connect("button_press_event", self.mousedown)
   self.connect("button_release_event", self.mouseup)
   self.peaks = []
   self.MAX_PEAK = float(maxpeak)
   self.cursor_target = gtk.gdk.Cursor(gtk.gdk.TARGET)
   self.cursor_updownarrow = gtk.gdk.Cursor(gtk.gdk.SB_V_DOUBLE_ARROW)
   self.arrow_showing = False
   self.target_showing = False
   self.dragging = False
   self.WAVEFORM_PENDING_REFRESH = False
   self.target = None
   self.waveform_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,1000,1000)
   self.overlay_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,1000,1000)
   self.waveform_context = cairo.Context(self.waveform_surface)
   self.overlay_context = cairo.Context(self.overlay_surface)
   self.overlay_context.save() # save as blank!
      
 def set_values(self,peaks):
   if type(peaks) != type([]):
     raise TypeError,"Values must be a list"
   try:
     val = [float(x) for x in peaks]
   except:
     raise TypeError,"Values must be a list of numbers"
   self.peaks = val
   self.update_waveform()

 def append_value(self,i):
   try:
     val = float(i)
   except:
     raise TypeError,"Values must be a number"
   self.peaks.append(val)
   self.update_waveform()
   
 def update_waveform(self):
   if not self.window:
     self.WAVEFORM_PENDING_REFRESH = True
     return
     
   width,height = self.window.get_size()
   # Redraw the waveform surface
   count = 0
   self.waveform_context.move_to(0,height)
   for peak in self.peaks:
     count += 3
     scaled_peak = (peak / self.MAX_PEAK) * height
     if scaled_peak < 0: scaled_peak = -scaled_peak
     if scaled_peak > height: scaled_peak = height
     self.waveform_context.line_to(count,height - int(scaled_peak))
     #print count,scaled_peak
   self.waveform_context.line_to(count,height)
   self.waveform_context.set_source_rgb(0, 1, 0)
   self.waveform_context.fill_preserve()
   self.waveform_context.set_source_rgb(0, 0.7, 0)
   self.waveform_context.stroke_preserve()

   # Refresh the window
   self.refresh()
     
 def set_target(self,coords):
   if coords:
     self.overlay_context.set_operator(cairo.OPERATOR_OVER)
     self.overlay_context.set_source_rgb(1, 0, 0)
     self.overlay_context.arc(coords[0], coords[1], 5, 0, 2.0 * math.pi)
     self.overlay_context.stroke()
     self.target = coords
   else:
     self.overlay_context.set_operator(cairo.OPERATOR_CLEAR)
     self.overlay_context.paint()
     self.target = None

   # Refresh the window
   self.refresh()

 def refresh(self):
   if self.window:
     width,height = self.window.get_size()
     self.window.invalidate_rect(gtk.gdk.Rectangle(0,0,width,height),False)

 def expose(self, widget, event):
   if self.WAVEFORM_PENDING_REFRESH:
     self.WAVEFORM_PENDING_REFRESH = False
     self.update_waveform()
     
   self.context = widget.window.cairo_create()

   # set a clip region for the expose event
   self.context.rectangle(event.area.x, event.area.y,
                          event.area.width, event.area.height)
   self.context.clip()

   # copy waveform_context onto this context
   self.context.set_source_surface(self.waveform_surface,0,0)
   self.context.paint()
   # copy overlay context onto this context
   self.context.set_source_surface(self.overlay_surface,0,0)
   self.context.paint()
   return False

 def mousemove(self,widget,event):
   if not self.window: return
   if self.waveform_context.in_stroke(event.x,event.y):
     if self.target:
       self.window.set_cursor(self.cursor_updownarrow)
       self.arrow_showing = True
     else:
       self.window.set_cursor(self.cursor_target)
       self.target_showing = True
   else:
     if self.dragging:
       print "dragging!"
       pass # do drag!
     else:
       if self.target_showing:
         self.window.set_cursor(None)
         self.target_showing = False
       else:
         if self.arrow_showing:
           self.window.set_cursor(None)
           self.arrow_showing = False

 def mousedown(self,widget,event):
   if not self.window: return
   if self.target:
     if self.waveform_context.in_stroke(event.x,event.y):
       self.dragging = True
       print "Drag start"
     else:
       self.set_target(None)
   else:
     if self.waveform_context.in_stroke(event.x,event.y):
       self.set_target((event.x,event.y))
     else:
       pass
       
 def mouseup(self,widget,event):
   if self.dragging:
     self.window.set_cursor(None)
     self.arrow_showing = False
     self.dragging = False
     print "End drag"     
     
 def __smooth(self,l):
   "Does a rather poor quality average smoothing algorithm"
   weights = [1,2,3,4,3,2,1] # make sure there are an odd number!
   weights_sum = reduce(lambda x,y:x+y, weights)
   sidecount = len(weights) / 2
   extend_l = [0]*sidecount + l + [0]*sidecount 
   rl = []
   for i in range(sidecount,len(l)+sidecount):
     points = extend_l[i-sidecount:i+1+sidecount]
     multiples = zip(weights, points)
     multiplied = ([x[0]*x[1] for x in multiples])
     multipled_sum = reduce(lambda x,y:x+y, multiplied)
     rl.append(multipled_sum / weights_sum)      
   return rl

class RenderPreexistingWaveform:
 def __init__(self):
   window = gtk.Window()
   self.wave = WaveformWidget(30)
   self.wave.set_values([
                        1,3,5,6,9,15,19,25,23,18,7,6,4,2,
                        1,3,5,6,9,15,19,25,23,18,7,6,4,2,
                        1,3,5,6,9,15,19,25,23,18,7,6,4,2,
                        1,3,5,6,9,15,19,25,23,18,7,6,4,2
                        ])

   window.add(self.wave)
   window.connect("destroy", gtk.main_quit)
   window.show_all()


class BuildingWaveform:
 def __init__(self):
   window = gtk.Window()
   self.wave = WaveformWidget(30)

   window.add(self.wave)
   window.connect("destroy", gtk.main_quit)
   window.show_all()

   gobject.timeout_add(30,self.call_notify) # decrease amount to draw faster

 def call_notify(self):
   self.wave.append_value(random.randint(0,30))
   return True


def main():
 print "Rendering a preexisting waveform"
 wf = RenderPreexistingWaveform()
 gtk.main()

 print "Building up a waveform bit by bit"
 #wf = BuildingWaveform()
 #gtk.main()

if __name__ == "__main__":
   main()




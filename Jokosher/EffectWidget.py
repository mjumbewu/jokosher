#!/usr/bin/env python

import gtk
import math
import cairo
import gobject
import string


class EffectWidget(gtk.DrawingArea):
    def __init__(self, effectsdialog, effectname):
        gtk.DrawingArea.__init__(self)
        self.BACKGROUND_RGB = (1, 1, 1)
        self.TEXT_RGB = (0, 0, 0)
        
        self.effectname = effectname
        self.effectsdialog = effectsdialog

        self.set_size_request(150, 80)

        self.set_events(gtk.gdk.POINTER_MOTION_MASK | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.LEAVE_NOTIFY_MASK)


        gtk.DrawingArea.__init__(self)
        self.connect("expose_event", self.expose)
        #self.connect("motion_notify_event", self.OnMouseMove)
        #self.connect("leave_notify_event", self.OnMouseLeave)
        self.connect("button_press_event", self.OnMouseDown)
        #self.connect("button_release_event", self.OnMouseUp)

    def expose(self, widget, event):
        print "exposed"
        self.context = widget.window.cairo_create()
        
        # set a clip region for the expose event
        self.context.rectangle(event.area.x, event.area.y,
                               event.area.width, event.area.height)
        self.context.clip()
        
        self.draw(self.context)
        
        return False
    
    def draw(self, context):
        alloc = self.get_allocation()
        
        # a custom shape, that could be wrapped in a function
        x0 = 10   # parameters like cairo_rectangle
        y0 = 10
        rect_width = alloc.width - 15
        rect_height = alloc.height - 15
        radius = 50 # and an approximate curvature radius */
        
        self.contextwidth = alloc.width
        self.contextheight = alloc.height
        
        x1 = 0
        y1 = 0
        
        x1=x0+rect_width;
        y1=y0+rect_height;
        
        if not rect_width or not rect_height:
            return
        
        if (rect_width / 2) < radius:
            if (rect_height / 2) <radius:
                self.context.move_to  (x0, (y0 + y1)/2)
                self.context.curve_to (x0 ,y0, x0, y0, (x0 + x1)/2, y0)
                self.context.curve_to (x1, y0, x1, y0, x1, (y0 + y1)/2)
                self.context.curve_to (x1, y1, x1, y1, (x1 + x0)/2, y1)
                self.context.curve_to (x0, y1, x0, y1, x0, (y0 + y1)/2)
            else:
                self.context.move_to  (x0, y0 + radius)
                self.context.curve_to (x0 ,y0, x0, y0, (x0 + x1)/2, y0)
                self.context.curve_to (x1, y0, x1, y0, x1, y0 + radius)
                self.context.line_to (x1 , y1 - radius)
                self.context.curve_to (x1, y1, x1, y1, (x1 + x0)/2, y1)
                self.context.curve_to (x0, y1, x0, y1, x0, y1- radius)
        else:
            if (rect_height/2) < radius:
                self.context.move_to  (x0, (y0 + y1)/2)
                self.context.curve_to (x0 , y0, x0 , y0, x0 + radius, y0)
                self.context.line_to (x1 - radius, y0)
                self.context.curve_to (x1, y0, x1, y0, x1, (y0 + y1)/2)
                self.context.curve_to (x1, y1, x1, y1, x1 - radius, y1)
                self.context.line_to (x0 + radius, y1)
                self.context.curve_to (x0, y1, x0, y1, x0, (y0 + y1)/2)
            else:
                self.context.move_to  (x0, y0 + radius)
                self.context.curve_to (x0 , y0, x0 , y0, x0 + radius, y0)
                self.context.line_to (x1 - radius, y0)
                self.context.curve_to (x1, y0, x1, y0, x1, y0 + radius)
                self.context.line_to (x1 , y1 - radius)
                self.context.curve_to (x1, y1, x1, y1, x1 - radius, y1)
                self.context.line_to (x0 + radius, y1)
                self.context.curve_to (x0, y1, x0, y1, x0, y1- radius)

        self.context.close_path()
        
        gradient = cairo.LinearGradient(0.0, 0.0, 0, 100)
        gradient.add_color_stop_rgba(0.2, 252./255, 174./255, 62./255, 1)
        gradient.add_color_stop_rgba(1, 244./255, 120./255, 0./255, 0.5)
        context.set_source(gradient)
        context.fill_preserve()
        
        self.context.set_source_rgba (173, 73, 0, 0.5);
        self.context.stroke()
        
        effecttext = self.formatEffectText(self.effectname)
        labellen = len(effecttext)
        
        self.context.set_source_rgb(0, 0, 0)
        self.context.set_font_size(12)
        
        textheight = self.contextheight / 2
        
        for line in effecttext:
            print line
            
            self.context.move_to((self.contextwidth / 2) - (len(line) * 3), textheight)
            self.context.show_text(line)
            self.context.stroke();
            textheight += 12
            
            x = alloc.x + alloc.width / 2
            y = alloc.y + alloc.height / 2
            
            radius = min(alloc.width / 5, alloc.height / 5) - 5
        
        # delete button
        self.context.arc(alloc.width - (radius + 2), radius + 2, radius, 0, 2 * math.pi)
        self.context.set_source_rgb(2, 0, 0)
        self.context.fill_preserve()
        self.context.set_source_rgb(0, 0, 0)
        self.context.stroke_preserve()
        
        #self.context.move_to(alloc.width - (radius + 1), radius + 1)
        #self.context.set_source_rgb(0, 0, 0)
        #self.context.show_text("X")
        #self.context.stroke();

    def OnMouseDown(self, widget, mouse):
        if self.context.in_fill(mouse.x, mouse.y):
            self.effectsdialog.OnRemoveEffect(self)
        else:
            if mouse.type == gtk.gdk._2BUTTON_PRESS:
                self.effectsdialog.OnEffectSetting(self)
            else:
                print "single click"

    def formatEffectText(self, text):
        words = string.split(text)
        
        finallist = []
        linetext = ""
        
        linelength = 20
        remainder = linelength
        
        for w in words:
            wordlength = len(w)
            
            if wordlength <= remainder:
                remainder -= wordlength + 1
                linetext = linetext + w + " "
            else:
                finallist.append(linetext)
                linetext = ""
                linetext = linetext + w + " "
                remainder = 20 - len(linetext)

        finallist.append(linetext)
        return finallist


#def main():
    #window = gtk.Window()
    #eff = EffectWidget()
    
#    window.add(eff)
    #window.connect("destroy", gtk.main_quit)
    #window.show_all()
    
    #gtk.main()
    
#if __name__ == "__main__":
    #main()

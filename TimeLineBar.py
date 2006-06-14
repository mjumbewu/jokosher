import gtk
import TimeLine

class TimeLineBar(gtk.Fixed):
	def __init__(self, project, parentUpdateMethod):
		gtk.Fixed.__init__(self)
		
		self.project = project
		self.parentUpdateMethod = parentUpdateMethod
		self.timeline = TimeLine.TimeLine(self.project)
		self.Updating = False
		
		# add click / bpm / signature box
		self.clickbutton = gtk.ToggleButton("C")
					
		self.bpmeventbox = gtk.EventBox()
		self.bpmeventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#87d987"))
		self.bpmframe = gtk.Frame()
		self.bpmframe.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
		self.bpmframe.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#87d987"))
		
		self.bpmlabel = gtk.Label()
		self.bpmlabel.set_use_markup(True)
		self.bpmlabel.set_markup("<span foreground='#0b410b'><b>%s</b></span>"%self.project.transport.bpm)
		self.bpmlabel.set_padding(5, 5)
		self.bpmeventbox.add(self.bpmlabel)
		self.bpmframe.add(self.bpmeventbox)
		self.bpmeditPacked = False

		self.sigeventbox = gtk.EventBox()
		self.sigeventbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#87d987"))
		self.sigframe = gtk.Frame()
		self.sigframe.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
		self.sigframe.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#87d987"))

		self.siglabel = gtk.Label()
		self.siglabel.set_use_markup(True)
		self.siglabel.set_markup("<span foreground='#0b410b'><b>%d/%d</b></span>"%(self.project.transport.meter_nom, self.project.transport.meter_denom))
		self.siglabel.set_padding(5, 5)
		self.sigeventbox.add(self.siglabel)
		self.sigframe.add(self.sigeventbox)
		self.sigeditPacked = False

		# set events
		self.bpmeventbox.set_events(gtk.gdk.BUTTON_PRESS_MASK)
		self.bpmeventbox.connect("button_press_event", self.OnEditBPM)
		self.bpmeventbox.connect("enter_notify_event", self.OnMouseMoveBPM)
		self.bpmeventbox.connect("leave_notify_event", self.OnMouseMoveBPM)
		
		self.sigeventbox.set_events(gtk.gdk.BUTTON_PRESS_MASK)
		self.sigeventbox.connect("button_press_event", self.OnEditSig)
		self.sigeventbox.connect("enter_notify_event", self.OnMouseMoveSig)
		self.sigeventbox.connect("leave_notify_event", self.OnMouseMoveSig)
		
		self.headerhbox = gtk.HBox()
		self.headerhbox.set_border_width(5)
		self.headerhbox.set_spacing(5)
		self.headerhbox.pack_start(self.clickbutton, True, True)
		self.headerhbox.pack_start(self.bpmframe, True, True)
		self.headerhbox.pack_start(self.sigframe, True, True)
		
		self.put(self.headerhbox, 0, 0)
		self.headerhbox.connect("check-resize", self.parentUpdateMethod)
	
	#_____________________________________________________________________
	
	def Update(self, width):
		if not self.Updating:
			self.Updating = True
			
			if self.timeline in self.get_children():
				self.remove(self.timeline)
				
			self.put(self.timeline, width, 0)
			self.OnAcceptEditBPM()
			self.OnAcceptEditSig()
			self.timeline.queue_draw()
			
			self.Updating = False
	
	#_____________________________________________________________________
	
	def OnEditBPM(self, widget, event):
		self.parentUpdateMethod()
		if event.type == gtk.gdk.BUTTON_PRESS:
			self.bpmframe.remove(self.bpmeventbox)
						
			self.bpmedit = gtk.Entry()
			self.bpmedit.set_width_chars(3)
			self.bpmedit.set_text(str(self.project.transport.bpm))
			self.bpmedit.connect("activate", self.OnAcceptEditBPM)

			self.bpmframe.add(self.bpmedit)
			self.bpmedit.show()
			self.bpmedit.grab_focus()
			self.bpmeditPacked = True

	#_____________________________________________________________________

	def OnEditSig(self, widget, event):
		self.parentUpdateMethod()
		if event.type == gtk.gdk.BUTTON_PRESS:
			self.sigframe.remove(self.sigeventbox)
			
			self.sigedit = gtk.Entry()
			self.sigedit.set_text("%d/%d"%(self.project.transport.meter_nom, self.project.transport.meter_nom))
			self.sigedit.set_width_chars(5)
			self.sigedit.connect("activate", self.OnAcceptEditSig)

			self.sigframe.add(self.sigedit)
			self.sigedit.show()
			self.sigedit.grab_focus()
			self.sigeditPacked = True
	
	#_____________________________________________________________________
	
	def OnAcceptEditBPM(self, widget=None):
		if self.bpmeditPacked:
			self.bpmframe.remove(self.bpmedit)
			
			self.project.transport.SetBPM(float(self.bpmedit.get_text()))
			
			self.bpmlabel.set_use_markup(True)
			self.bpmlabel.set_markup("<span foreground='#0b410b'><b>%d</b></span>"%self.project.transport.bpm)
			
			self.bpmframe.add(self.bpmeventbox)
			self.bpmedit.destroy()
			self.bpmframe.show_all()
			self.bpmeditPacked = False

	#_____________________________________________________________________

	def OnAcceptEditSig(self, widget=None):
		if self.sigeditPacked:
			self.sigframe.remove(self.sigedit)
			
			nom, denom = self.sigedit.get_text().split("/")
			self.project.transport.SetMeter(int(nom), int(denom))
			
			self.siglabel.set_use_markup(True)
			self.siglabel.set_markup("<span foreground='#0b410b'><b>%d/%d</b></span>"%(self.project.transport.meter_nom, self.project.transport.meter_denom))
			
			self.sigframe.add(self.sigeventbox)
			self.sigedit.destroy()
			self.sigframe.show_all()
			self.sigeditPacked = False
			
	#_____________________________________________________________________
	
	def OnMouseMoveBPM(self, widget, event):
		if not widget.window: 
			return
		if (event.type == gtk.gdk.ENTER_NOTIFY):
			widget.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
		else:
			widget.window.set_cursor(None)
			
	#_____________________________________________________________________
	
	def OnMouseMoveSig(self, widget, event):
		if not widget.window: 
			return
		if (event.type == gtk.gdk.ENTER_NOTIFY):
			widget.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.XTERM))
		else:
			widget.window.set_cursor(None)
		
	#_____________________________________________________________________
	
#=========================================================================
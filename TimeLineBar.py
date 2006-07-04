import gtk
import TimeLine

class TimeLineBar(gtk.Frame):
	def __init__(self, project, projectview, mainview):
		gtk.Frame.__init__(self)
		
		self.project = project
		self.projectview = projectview
		self.mainview = mainview
		self.timeline = TimeLine.TimeLine(self.project, self, mainview)
		self.Updating = False
		
		# add click / bpm / signature box
		self.clickbutton = gtk.ToggleButton("C")
		self.clickbutton.connect("toggled", self.OnClick)
					
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
		# ##### BPM boxes disabled in 0.1 - re-enable for 0.2 #######
		#self.bpmeventbox.set_events(gtk.gdk.BUTTON_PRESS_MASK)
		#self.bpmeventbox.connect("button_press_event", self.OnEditBPM)
		#self.bpmeventbox.connect("enter_notify_event", self.OnMouseMoveBPM)
		#self.bpmeventbox.connect("leave_notify_event", self.OnMouseMoveBPM)
		
		#self.sigeventbox.set_events(gtk.gdk.BUTTON_PRESS_MASK)
		#self.sigeventbox.connect("button_press_event", self.OnEditSig)
		#self.sigeventbox.connect("enter_notify_event", self.OnMouseMoveSig)
		#self.sigeventbox.connect("leave_notify_event", self.OnMouseMoveSig)
		
		# ###########################################################
		
		self.headerhbox = gtk.HBox()
		self.headerhbox.set_border_width(2)
		self.headerhbox.set_spacing(5)
		self.headerhbox.pack_start(self.clickbutton, True, True)
		self.headerhbox.pack_start(self.bpmframe, True, True)
		self.headerhbox.pack_start(self.sigframe, True, True)
		
		self.hbox = gtk.HBox()
		self.hbox.pack_start(self.headerhbox, False, False)
		self.add(self.hbox)
		self.headerhbox.connect("check-resize", self.projectview.Update)
		self.connect("size-allocate", self.OnAllocate)
	
	#_____________________________________________________________________

	def OnAllocate(self, widget, allocation):
		self.allocation = allocation

	#_____________________________________________________________________
	
	def Update(self, width):
		if not self.Updating:
			self.Updating = True
			
			if self.timeline in self.get_children():
				self.remove(self.timeline)
				
			self.hbox.pack_start(self.timeline)
			
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

	def OnClick(self, widget):
		dlg = gtk.MessageDialog(None,
			gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
			gtk.MESSAGE_WARNING,
			gtk.BUTTONS_CLOSE)
		dlg.set_markup("<big>Click Track</big>\n\nThis button enables and disables the Click Track in Jokosher.\n\nThe current version of Jokosher does not have the click track available. It will be ready in version 0.2.")
		dlg.run()
		dlg.destroy()
		
#=========================================================================

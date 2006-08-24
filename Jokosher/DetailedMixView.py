
import gtk
import TimeLineBar
import Globals

class DetailedMixView(gtk.Frame):	
	def __init__(self, project):
		gtk.Container.__init__(self)
		self.project = project
		self.vbox = gtk.VBox()
		self.add(self.vbox)
		
		self.timelinebar = TimeLineBar.TimeLineBar(self.project, self.Update)
		self.vbox.pack_start(self.timelinebar, False, False)
		
		self.hbox = None
		self.Update()
		
	def Update(self):
		self.timelinebar.Update(Globals.INSTRUMENT_HEADER_WIDTH)
		
		if self.hbox:
			self.vbox.remove(self.hbox)
		self.hbox = gtk.HBox()
		for i in self.project.instruments:
			vb = gtk.VBox()
			hb = gtk.HBox()
			sb = gtk.VScrollbar()
			sb.set_size_request(50,50)
			hb.pack_start(sb, False, True)
			pb = gtk.ProgressBar()
			pb.set_orientation(gtk.PROGRESS_BOTTOM_TO_TOP)
			hb.pack_start(pb, True, True)
			vb.pack_start(hb)
			vb.pack_start(gtk.Label(i.name), False, False)
			self.hbox.pack_end(vb)
		self.vbox.pack_start(self.hbox)
		self.show_all()
		#for when being called from gobject thread
		return False


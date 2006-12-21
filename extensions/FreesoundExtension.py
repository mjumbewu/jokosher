# TODO
# give downloaded samples proper names
# when dragging, event doesn't appear for a few secs so it looks like it hadn't worked
# DONE
# don't hang while fetching imagery
# expanding the window shouldn't expand the top search pane
# getting no results fails
# show "searching..." when searching
# NOT DOING FOR 0.2
# make an egg file?
# make the window spaced out properly

import Jokosher.Extension # required
import pygtk
pygtk.require("2.0")
import gtk, gobject
import pygst
pygst.require("0.10")
import gst

import urllib, os, Queue, threading

#########################################################
#########################################################
#########################################################
#     THE FREESOUND LIBRARY 
# included here until extensions can be .egg files
#########################################################
#########################################################
#########################################################
import os.path
import urllib2, urllib
from xml.dom import minidom
from xml.xpath import Evaluate

# First, set up cookie handling!
# from http://www.voidspace.org.uk/python/articles/cookielib.shtml


cj = None
ClientCookie = None
cookielib = None

# Let's see if cookielib is available
try:
    import cookielib
except ImportError:
    # If importing cookielib fails
    # let's try ClientCookie
    try:
        import ClientCookie
    except ImportError:
        # ClientCookie isn't available either
        urlopen = urllib2.urlopen
        Request = urllib2.Request
    else:
        # imported ClientCookie
        urlopen = ClientCookie.urlopen
        Request = ClientCookie.Request
        cj = ClientCookie.LWPCookieJar()

else:
    # importing cookielib worked
    urlopen = urllib2.urlopen
    Request = urllib2.Request
    cj = cookielib.LWPCookieJar()
    # This is a subclass of FileCookieJar
    # that has useful load and save methods


if cj is not None:
# we successfully imported
# one of the two cookie handling modules

    # Now we need to get our Cookie Jar
    # installed in the opener;
    # for fetching URLs
    if cookielib is not None:
        # if we use cookielib
        # then we get the HTTPCookieProcessor
        # and install the opener in urllib2
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        urllib2.install_opener(opener)

    else:
        # if we use ClientCookie
        # then we get the HTTPCookieProcessor
        # and install the opener in ClientCookie
        opener = ClientCookie.build_opener(ClientCookie.HTTPCookieProcessor(cj))
        ClientCookie.install_opener(opener)

SAMPLE_ATTRIBUTES = {
  "date": "/freesound/sample/date",
  "originalFilename": "/freesound/sample/originalFilename",
	"image": "/freesound/sample/image",
	"previewURL": "/freesound/sample/preview",
	"image": "/freesound/sample/image",
	"samplerate": "/freesound/sample/samplerate",
	"bitrate": "/freesound/sample/bitrate",
	"bitdepth": "/freesound/sample/bitdepth",
	"channels": "/freesound/sample/channels",
	"duration": "/freesound/sample/duration",
	"filesize": "/freesound/sample/filesize",
	"description": "/freesound/sample/descriptions/description/text"
}

class Sample:
	def __init__(self, sid):
		self.sid = sid
		
	def fetch(self):
		# fetch thyself
		req = Request("http://freesound.iua.upf.edu/samplesViewSingleXML.php?id=%s" % self.sid)
		handle = urlopen(req)
		data = handle.read()
		dom = minidom.parseString(data)
		for attribute, xpath in SAMPLE_ATTRIBUTES.items():
			try:
				setattr(self,attribute,Evaluate(xpath, dom)[0].firstChild.nodeValue)
			except:
				setattr(self,attribute,None)

class Freesound:
	def __init__(self, username=None, password=None):
		self.loggedIn = False
		if username and password:
			self.login(username, password)
			
	def login(self, username, password):
		try:
			# clear any cookies we might already have set
			# so this is a fresh login attempt
			cj.clear()
		except:
			pass
		data = {"username": username,
            "password": password,
            "login": "1",
            "redirect": "../tests/login.php"}
		req = Request("http://freesound.iua.upf.edu/forum/login.php", 
                urllib.urlencode(data))
		handle = urlopen(req)
		if handle.read().strip() == 'login':
			self.loggedIn = True
		else:
			self.loggedIn = False

	def search(self, txt):
		if not self.loggedIn:
			raise "Not logged in"
		data = {"search": txt, "searchTags":"on"}
		req = Request("http://freesound.iua.upf.edu/searchTextXML.php", 
                urllib.urlencode(data))
		handle = urlopen(req)
		data = handle.read()
		try:
			dom = minidom.parseString(data)
		except:
			raise "Search failed"
		if dom.documentElement.nodeName != "freesound":
			raise "Search failed"
		return [Sample(x.getAttribute("id")) for x in
		        dom.getElementsByTagName('sample')]

#########################################################
#########################################################
#########################################################
# end freesound library
#########################################################
#########################################################
#########################################################

# Note that all the Gtk stuff in this object is added with idle_add.
# this makes sure that, although this object is running in a different
# thread, all the GUI stuff happens on the main thread.
class SearchFreesoundThread(threading.Thread):
	def __init__(self, window_container, username, password, queue):
		super(SearchFreesoundThread, self).__init__()
		self.container = window_container
		self.fs = None
		self.username = username
		self.password = password
		self.queue = queue
		self.searchtext = None
		self.player = gst.element_factory_make("playbin", "player")
		
	def add_sample(self, sample):
		e = gtk.EventBox()
		h = gtk.HBox()
		e.add(h)
		e.drag_source_set(gtk.gdk.BUTTON1_MASK, [('text/plain',0,88)],gtk.gdk.ACTION_COPY)
		e.connect("drag_data_get", self.returndata, sample)
		tmpnam = os.tmpnam()
		print "retrieving sample image to",tmpnam
		imgfile = urllib.urlretrieve(sample.image,tmpnam)
		image = gtk.Image()
		image.set_from_pixbuf(gtk.gdk.pixbuf_new_from_file_at_size(tmpnam,50,50))
		os.unlink(tmpnam)
		h.add(image)
		lbl = gtk.Label(sample.description)
		lbl.set_width_chars(50)
		lbl.set_line_wrap(True)
		h.add(lbl)
		playbtn = gtk.Button(stock=gtk.STOCK_MEDIA_PLAY)
		playbtn.connect("clicked", self.play_streamed_sample, sample.previewURL)
		h.add(playbtn)
		e.show_all()
		self.container.add(e)
		
	def returndata(self, widget, drag_context, selection_data, info, time, sample):
		selection_data.set (selection_data.target,8, sample.previewURL)

	def login(self):
		self.fs = Freesound(self.username, self.password)
		
	def empty_container(self):
		for c in self.container.get_children():
			self.container.remove(c)
			
	def no_results(self):
		self.empty_container()
		self.container.add(gtk.Label("No results for %s" % self.searchtext))
		self.container.show_all()
		
	def add_searching_label(self):
		self.container.add(gtk.Label("Searching..."))
		self.container.show_all()
		
	def search(self, q):
		gobject.idle_add(self.empty_container)
		gobject.idle_add(self.add_searching_label)
		self.searchtext = q
		samples = self.fs.search(q)
		if not samples:
			gobject.idle_add(self.no_results)
		else:
			gobject.idle_add(self.empty_container)
			for sample in samples[:10]:
				sample.fetch()
				gobject.idle_add(self.add_sample, sample)

	def play_streamed_sample(self, event, url):
		if self.player.get_state(0)[1] == gst.STATE_READY:
			self.player.set_property("uri", url)
			self.player.set_state(gst.STATE_PLAYING)
		else:
			self.player.set_state(gst.STATE_READY)
			
		if self.player.get_property("uri") != url:
			self.player.set_property("uri", url)
			self.player.set_state(gst.STATE_PLAYING)

				
	def run(self):
		print "login"
		self.login()
		while 1:
			self.search(self.queue.get()) # blocks until there's an item to search for

class MainWindow:
	def __init__(self, API):
		self.API = API
		self.srchbox = None
		self.container = None
		self.searchqueue = Queue.Queue()

	def ask_for_login_details(self, warning=None):
		h1 = gtk.HBox()
		h1.add(gtk.Label("Username:"))
		lbl_username = gtk.Entry()
		if self.API.get_config_value("username") is not None:
			lbl_username.set_text(self.API.get_config_value("username"))
		h1.add(lbl_username)
		h2 = gtk.HBox()
		h2.add(gtk.Label("Password:"))
		lbl_password = gtk.Entry()
		lbl_password.set_visibility(False)
		if self.API.get_config_value("password") is not None:
			lbl_password.set_text(self.API.get_config_value("password"))
		h2.add(lbl_password)
		d = gtk.Dialog("Freesound username and password",
									None,
									gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
									(gtk.STOCK_OK,gtk.RESPONSE_OK,
									gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL))
		d.vbox.add(h1)
		d.vbox.add(h2)
		if warning:
			d.vbox.add(gtk.Label(warning))
		d.show_all()
		resp = d.run()
		if resp in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
			d.destroy()
			return False
		else:
			# check entered details
			u,p = lbl_username.get_text(), lbl_password.get_text()
			fs = Freesound(u,p)
			d.destroy()
			if fs.loggedIn:
				self.API.set_config_value("username",u)
				self.API.set_config_value("password",p)
				return True
			else:
				self.ask_for_login_details(warning="Login failed!")
				return False

	def do_search(self, event):
		searchtext = self.srchbox.get_text()
		self.searchqueue.put(searchtext)
		self.container.show_all()

	def menu_cb(self, event):
		username = self.API.get_config_value("username")
		password = self.API.get_config_value("password")
		if username is None:
			success = self.ask_for_login_details()
			if not success: return
		global srchbox, container
		self.w = gtk.Window()
		v = gtk.VBox()
		self.w.add(v)
		h = gtk.HBox()
		v.pack_start(h, expand=False)
		self.container = gtk.VBox()
		sw = gtk.ScrolledWindow()
		v.add(sw)
		sw.add_with_viewport(self.container)
		sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
		h.add(gtk.Label("Search freesound:"))
		self.srchbox = gtk.Entry()
		self.srchbox.set_activates_default(True)
		h.add(self.srchbox)
		gobutton = gtk.Button("Search")
		gobutton.set_flags(gtk.CAN_DEFAULT)
		h.add(gobutton)
		gobutton.grab_default()
		username = self.API.get_config_value("username")
		password = self.API.get_config_value("password")
		background_search_thread = SearchFreesoundThread(self.container, 
		    username, password, self.searchqueue)
		background_search_thread.setDaemon(True) # thread exits when jokosher exits
		background_search_thread.start()
		gobutton.connect("clicked", self.do_search)
		self.w.show_all()

gobject.threads_init()

def startup(API):
	global mainwindow, menu_item
	mainwindow = MainWindow(API)
	menu_item = API.add_menu_item("Search Freesound", mainwindow.menu_cb)

def shutdown():
	menu_item.destroy()

def preferences():
	mainwindow.ask_for_login_details()


EXTENSION_NAME = "Freesound search"
EXTENSION_DESCRIPTION = "Searches the Freesound library of " +\
  "freely licenceable and useable sound clips"
EXTENSION_VERSION = "0.01"

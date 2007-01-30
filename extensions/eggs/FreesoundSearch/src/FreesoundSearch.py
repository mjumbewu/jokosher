#
#	THIS FILE IS LICENSED UNDER THE GPL. SEE THE 'COPYING' FILE FOR DETAILS
#
#	FreesoundExtension.py
#	
#	Freesound library browsing extension.
#
#-------------------------------------------------------------------------------

# TODO
# give downloaded samples proper names
# when dragging, event doesn't appear for a few secs so it looks like it hadn't worked
# DONE
# don't hang while fetching imagery
# expanding the window shouldn't expand the top search pane
# getting no results fails
# show "searching..." when searching

import Jokosher.Extension # required in all Jokosher extensions
import pygtk
pygtk.require("2.0")
import gtk, gtk.glade, gobject
import pygst
pygst.require("0.10")
import gst
import urllib, os, Queue, threading
import freesound
import pkg_resources

import gettext
_ = gettext.gettext

#=========================================================================

class FreesoundSearch:
	"""
	Allows the user to search for samples on Freesound with free form queries.
	"""
	
	# necessary extension attributes
	EXTENSION_NAME = _("Freesound search")
	EXTENSION_VERSION = "0.2"
	EXTENSION_DESCRIPTION = _("Searches the Freesound library of freely" + \
							" licenceable and useable sound clips")

	#_____________________________________________________________________

	def startup(self, api):
		"""
		Initializes the extension.
		
		Parameters:
			api -- reference to the Jokosher extension API.
		"""
		gobject.threads_init()
		self.api = api
		self.menuItem = self.api.add_menu_item(_("Search Freesound"), self.OnMenuItemClick)
		self.freeSound = None
		self.showSearch = False
		self.searchQueue = Queue.Queue()

	#_____________________________________________________________________
	
	def shutdown(self):
		"""
		Destroys any object created by the extension when it is disabled.
		"""
		self.menuItem.destroy()
		#TODO: stop the search threads
		
	#_____________________________________________________________________
	
	def preferences(self):
		"""
		Shows the preferences window for changing username/password.
		"""
		self.LoginDetails()
		
	#_____________________________________________________________________
	
	def OnMenuItemClick(self, menuItem=None):
		"""
		Called when the user clicks on this extension's menu item.
		
		Parameters:
			menuItem -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		username = self.api.get_config_value("fsUsername")
		password = self.api.get_config_value("fsPassword")
		
		#TODO: remove this print
		#print "username: %s, password: %s" % (username, password)
		
		if not self.freeSound:
			self.showSearch = True
			self.LoginDetails()
			return
		
		xmlString = pkg_resources.resource_string(__name__,"FreesoundSearch.glade")
		wTree = gtk.glade.xml_new_from_buffer(xmlString, len(xmlString), "FreesoundSearchWindow")
		
		signals = {
			"on_buttonFind_clicked" : self.OnFind,
			"on_destroy" : self.OnDestroy
		}
		wTree.signal_autoconnect(signals)
	
		self.entryFind = wTree.get_widget("entryFind")
		self.buttonFind = wTree.get_widget("buttonFind")
		self.scrollResults = wTree.get_widget("scrolledwindowResults")
		self.statusbar = wTree.get_widget("statusbar")
		self.window = wTree.get_widget("FreesoundSearchWindow")
		self.vboxResults = gtk.VBox(spacing=6)
		
		self.entryFind.set_activates_default(True)
		self.buttonFind.set_flags(gtk.CAN_DEFAULT)
		self.buttonFind.grab_default()
		self.scrollResults.add_with_viewport(self.vboxResults)
		self.api.set_window_icon(self.window)
		
		self.window.show_all()
		
		# set up the result fetching thread
		searchThread = SearchFreesoundThread(self.vboxResults, self.statusbar, username, password, self.searchQueue)
		searchThread.setDaemon(True) # thread exits when Jokosher exits
		searchThread.start()
		
	#_____________________________________________________________________
	
	def OnFind(self, button):
		"""
		Queries Freesound with the user given input.
		
		Parameters:
			button -- reserved for GTK callbacks. Don't use explicitly.
		"""
		searchText = self.entryFind.get_text()
		self.searchQueue.put(searchText)
	
	#_____________________________________________________________________
	
	def OnDestroy(self, window):
		"""
		Called when the search window gets destroyed.
		Destroys the search threads.
		"""
		#TODO: stop the search threads
		pass
	
	#_____________________________________________________________________
	
	def LoginDetails(self, warning=None):
		"""
		Displays the account details dialog.
		
		Parameters:
			warning -- True if the validation failed and the user must be informed.
		"""
		xmlString = pkg_resources.resource_string(__name__, "FreesoundSearch.glade")
		wTree = gtk.glade.xml_new_from_buffer(xmlString, len(xmlString), "LoginDetailsDialog")
		
		signals = {
			"on_buttonOK_clicked" : self.OnAcceptDetails,
			"on_buttonCancel_clicked" : self.OnCancelDetails
		}
		wTree.signal_autoconnect(signals)
	
		self.entryUsername = wTree.get_widget("entryUsername")
		self.entryPassword = wTree.get_widget("entryPassword")
		self.labelWarning = wTree.get_widget("labelWarning")
		self.buttonOK = wTree.get_widget("buttonOK")
		self.loginWindow = wTree.get_widget("LoginDetailsDialog")
		
		self.entryUsername.set_activates_default(True)
		self.entryPassword.set_activates_default(True)
		self.buttonOK.set_flags(gtk.CAN_DEFAULT)
		self.buttonOK.grab_default()
		self.api.set_window_icon(self.loginWindow)
		
		# set the entries's text to the saved values
		if self.api.get_config_value("fsUsername") is not None:
			self.entryUsername.set_text(self.api.get_config_value("fsUsername"))
		if self.api.get_config_value("fsPassword") is not None:
			self.entryPassword.set_text(self.api.get_config_value("fsPassword"))
		
		if warning:
			self.labelWarning.set_label(warning)
			
		self.loginWindow.show_all()
		
	#_____________________________________________________________________
	
	def OnAcceptDetails(self, button):
		"""
		Sets the username/password entered by the user.
		
		Parameters:
			button -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		username, password = self.entryUsername.get_text(), self.entryPassword.get_text()
		self.freeSound = freesound.Freesound(username, password)
		
		if self.freeSound.loggedIn:
			self.api.set_config_value("fsUsername", username)
			self.api.set_config_value("fsPassword", password)
			
			if self.showSearch:
				self.OnMenuItemClick(None)
				self.showSearch = False
				self.loginWindow.destroy()
		else:
			self.LoginDetails(warning=_("Login failed!"))
		
	#_____________________________________________________________________
	
	def OnCancelDetails(self, button):
		"""
		Cancels the username/password editing operation.
		
		Parameters:
			button -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		self.loginWindow.destroy()
		
	#_____________________________________________________________________

# Note that all the Gtk stuff in this object is added with idle_add.
# This makes sure that although this object is running in a different
# thread, all the GUI stuff happens on the main thread.
class SearchFreesoundThread(threading.Thread):
	"""
	Performs searches on Freesound and retrieves the results.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, container, statusbar, username, password, queue):
		"""
		Creates a new instance of SearchFreesoundThread.
		
		Parameters:
			container -- gtk container object to put the results into.
			statusbar -- gtk.statusbar used for displaying information.
			username -- Freesound account username.
			password -- Freesound account password.
			queue -- thread queue with the query text.
		"""
		super(SearchFreesoundThread, self).__init__()
		self.container = container
		self.statusbar = statusbar
		self.freeSound = None
		self.username = username
		self.password = password
		self.queue = queue
		self.searchText = None
		self.player = gst.element_factory_make("playbin", "player")
	
	#_____________________________________________________________________
		
	def AddSample(self, sample):
		evBox = gtk.EventBox()
		hzBox = gtk.HBox()
		evBox.add(hzBox)
		evBox.drag_source_set(gtk.gdk.BUTTON1_MASK, [('text/plain', 0, 88)],gtk.gdk.ACTION_COPY)
		evBox.connect("drag_data_get", self.ReturnData, sample)
		
		tmpnam = os.tmpnam()
		#TODO: remove this print
		print "Retrieving sample image to %s" % tmpnam
		
		imgfile = urllib.urlretrieve(sample.image, tmpnam)
		image = gtk.Image()
		image.set_from_pixbuf(gtk.gdk.pixbuf_new_from_file_at_size(tmpnam, 50, 50))
		os.unlink(tmpnam)
		
		hzBox.add(image)
		sampleDesc = gtk.Label(sample.description)
		sampleDesc.set_width_chars(50)
		sampleDesc.set_line_wrap(True)
		hzBox.add(sampleDesc)
		
		playButton = gtk.Button(stock=gtk.STOCK_MEDIA_PLAY)
		playButton.connect("clicked", self.PlayStreamedSample, sample.previewURL)
		hzBox.add(playButton)
		
		evBox.show_all()
		self.container.add(evBox)
		
	#_____________________________________________________________________
	
	def ReturnData(self, widget, drag_context, selection_data, info, time, sample):
		selection_data.set (selection_data.target, 8, sample.previewURL)

	#_____________________________________________________________________

	def Login(self):
		self.freeSound = freesound.Freesound(self.username, self.password)
		
	#_____________________________________________________________________
	
	def EmptyContainer(self):
		for child in self.container.get_children():
			self.container.remove(child)

	#_____________________________________________________________________
			
	def NoResults(self):
		self.EmptyContainer()
		self.container.add(gtk.Label(_("No results for %s") % self.searchText))
		self.container.show_all()
	
	#_____________________________________________________________________
		
	def SetSearchingStatus(self):
		self.statusbar.push(0, _("Searching..."))

	#_____________________________________________________________________
		
	def Search(self, query):
		gobject.idle_add(self.EmptyContainer)
		gobject.idle_add(self.SetSearchingStatus)
		
		self.searchText = query
		samples = self.freeSound.Search(query)
		if not samples:
			gobject.idle_add(self.NoResults)
		else:
			gobject.idle_add(self.EmptyContainer)
			for sample in samples[:10]:
				sample.Fetch()
				gobject.idle_add(self.AddSample, sample)

	#_____________________________________________________________________

	def PlayStreamedSample(self, event, url):
		if self.player.get_state(0)[1] == gst.STATE_READY:
			self.player.set_property("uri", url)
			self.player.set_state(gst.STATE_PLAYING)
		else:
			self.player.set_state(gst.STATE_READY)
			
		if self.player.get_property("uri") != url:
			self.player.set_property("uri", url)
			self.player.set_state(gst.STATE_PLAYING)

	#_____________________________________________________________________
				
	def run(self):
		self.Login()
		while True:
			self.Search(self.queue.get()) # blocks until there's an item to search for
	#_____________________________________________________________________
	
#=========================================================================		
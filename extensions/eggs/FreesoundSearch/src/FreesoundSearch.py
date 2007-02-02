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
		self.freeSound = freesound.Freesound()
		self.showSearch = False
		self.searchQueue = Queue.Queue()
		self.maxResults = 15

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
		
		if not self.freeSound.loggedIn:
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
		searchThread = SearchFreesoundThread(self.vboxResults, self.statusbar,
											 username, password, self.searchQueue,
											 self.maxResults)
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
		It does this by trying to log in (in a separate thread).
		
		Parameters:
			button -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		username, password = self.entryUsername.get_text(), self.entryPassword.get_text()
		self.labelWarning.set_label(_("Login in..."))
		
		# create a worker thread to avoid blocking the GUI while logging in
		worker = threading.Thread(group=None, target=self.FinishLogin, name="Login", 
					    args=(username, password))
		worker.start()
		
	#_____________________________________________________________________
	
	def FinishLogin(self, username, password):
		"""
		Attempts to login in to confirm the given credentials.
		If successful, they're written to a local file for subsequent use.
		"""
		self.freeSound.Login(username, password)
		
		if self.freeSound.loggedIn:
			self.api.set_config_value("fsUsername", username)
			self.api.set_config_value("fsPassword", password)
			gobject.idle_add(self.loginWindow.destroy)
			
			if self.showSearch:
				self.showSearch = False
				gobject.idle_add(self.OnMenuItemClick)	
		else:
			gobject.idle_add(self.loginWindow.destroy)
			gobject.idle_add(self.LoginDetails, _("Login failed!"))
	
	#_____________________________________________________________________
	
	def OnCancelDetails(self, button):
		"""
		Cancels the username/password editing operation.
		
		Parameters:
			button -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		self.loginWindow.destroy()
		self.showSearch = False
		
	#_____________________________________________________________________

# Note that all the Gtk stuff in this object is added with idle_add.
# This makes sure that although this object is running in a different
# thread, all the GUI stuff happens on the main thread.
class SearchFreesoundThread(threading.Thread):
	"""
	Performs searches on Freesound and retrieves the results.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, container, statusbar, username, password, queue, maxResults):
		"""
		Creates a new instance of SearchFreesoundThread.
		
		Parameters:
			container -- gtk container object to put the results into.
			statusbar -- gtk.statusbar used for displaying information.
			username -- Freesound account username.
			password -- Freesound account password.
			queue -- thread queue with the query text.
			maxResults -- maximum number of query matches to display.
		"""
		super(SearchFreesoundThread, self).__init__()
		self.container = container
		self.statusbar = statusbar
		self.freeSound = None
		self.username = username
		self.password = password
		self.queue = queue
		self.searchText = None
		self.maxResults = maxResults
		self.player = gst.element_factory_make("playbin", "player")
	
	#_____________________________________________________________________
		
	def AddSample(self, sample):
		"""
		Adds a new sample to the results box.
		These samples can be drag and dropped into the recording lanes.
		
		Parameters:
			sample -- the Sample to add to the results box.
		"""
		evBox = gtk.EventBox()
		hzBox = gtk.HBox()
		evBox.add(hzBox)
		evBox.drag_source_set(gtk.gdk.BUTTON1_MASK, [('text/plain', 0, 88)],gtk.gdk.ACTION_COPY)
		evBox.connect("drag_data_get", self.ReturnData, sample)
		
		tmpnam = os.tmpnam()
		# TODO: remove this print
		#print "Retrieving sample image to %s" % tmpnam
		
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
		"""
		Used for drag and drop operations.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use it explicitly.
			drag_context -- reserved for GTK callbacks. Don't use it explicitly.
			selection_data -- reserved for GTK callbacks. Don't use it explicitly.
			info -- reserved for GTK callbacks. Don't use it explicitly.
			time -- reserved for GTK callbacks. Don't use it explicitly.
			sample -- the Sample to add to be dropped into another window.
		"""
		selection_data.set (selection_data.target, 8, sample.previewURL)

	#_____________________________________________________________________

	def Login(self):
		"""
		Attempts to login to Freesound.
		"""
		self.freeSound = freesound.Freesound(self.username, self.password)
		
	#_____________________________________________________________________
	
	def EmptyContainer(self):
		"""
		Empties the results box container.
		"""
		for child in self.container.get_children():
			self.container.remove(child)

	#_____________________________________________________________________
			
	def NoResults(self):
		"""
		Called when the query produces no matches.
		It displays a label to inform the user.
		"""
		self.EmptyContainer()
		self.container.add(gtk.Label(_("No results for %s") % self.searchText))
		self.container.show_all()
	
	#_____________________________________________________________________
		
	def SetSearchingStatus(self):
		"""
		Sets the searching status bar message.
		"""
		self.statusbar.push(0, _("Searching..."))

	#_____________________________________________________________________
	
	def SetFetchingStatus(self):
		"""
		Sets the fetching status bar message.
		"""
		self.statusbar.push(0, _("Fetching samples... please wait"))
		
	#_____________________________________________________________________
		
	def SetIdleStatus(self):
		"""
		Clears the status bar messages.
		"""
		self.statusbar.pop(0)
		
	#_____________________________________________________________________
	
	def Search(self, query):
		"""
		Searches the Freesound database trying to match the given query.
		
		Parameters:
			query -- query to look for in the Freesound database.
		"""
		gobject.idle_add(self.EmptyContainer)
		gobject.idle_add(self.SetSearchingStatus)
		
		self.searchText = query
		samples = self.freeSound.Search(query)
		if not samples:
			gobject.idle_add(self.NoResults)
			gobject.idle_add(self.SetIdleStatus)
		else:
			gobject.idle_add(self.EmptyContainer)
			gobject.idle_add(self.SetIdleStatus)
			gobject.idle_add(self.SetFetchingStatus)
			
			for sample in samples[:self.maxResults]:
				sample.Fetch()
				gobject.idle_add(self.AddSample, sample)
				
			gobject.idle_add(self.SetIdleStatus)

	#_____________________________________________________________________

	def PlayStreamedSample(self, event, url):
		"""
		Plays the selected audio sample.
		
		Parameters:
			event -- reserved for GTK callbacks. Don't use it explicitly.
			url -- url pointing to the sample file.
		"""
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
		"""
		Overrides the default threading.thread run(). Performs the searches
		whenever there is something to search for.
		"""
		self.Login()
		while True:
			self.Search(self.queue.get()) # blocks until there's an item to search for
			
	#_____________________________________________________________________
	
#=========================================================================		
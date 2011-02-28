#
#	THIS FILE IS LICENSED UNDER THE GPL. SEE THE 'COPYING' FILE FOR DETAILS
#
#	FreesoundExtension.py
#	
#	Freesound library browsing extension.
#
#-------------------------------------------------------------------------------

import Jokosher.Extension # required in all Jokosher extensions
import pygtk
pygtk.require("2.0")
import gtk, gobject
import pygst
pygst.require("0.10")
import gst
import urllib, os, Queue, threading
import freesound
import pkg_resources

try:
	import gnomekeyring as gkey
	keyring = True
except:
	keyring = False

import gettext
_ = gettext.gettext

#=========================================================================

# in this extension these globals were defined outside the main class because
# they are used in the search thread
# Note: the following string should not be translated
EXTENSION_DATA_NAME = "freesound"
isSearching = False

class FreesoundSearch:
	"""
	Allows the user to search for samples on Freesound with free form queries.
	"""
	
	# necessary extension attributes
	EXTENSION_NAME = _("Freesound search")
	EXTENSION_VERSION = "0.11"
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
		self.retryLogin = True
		self.searchQueue = Queue.Queue()
		self.maxResults = 15
		
	#_____________________________________________________________________
	
	def shutdown(self):
		"""
		Destroys any object created by the extension when it is disabled.
		"""
		self.menuItem.destroy()
		global isSearching
		isSearching = False
		self.searchQueue.put("quit")
		
	#_____________________________________________________________________
	
	def preferences(self):
		"""
		Shows the preferences window for changing username/password.
		"""
		self.showSearch = False
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
		
		xmlString = pkg_resources.resource_string(__name__, "FreesoundSearch.ui")
		gtkBuilder = gtk.Builder()
		gtkBuilder.add_from_string(xmlString)
		
		signals = {
			"on_buttonFind_clicked" : self.OnFind,
			"on_buttonClose_clicked" : self.OnClose,
			"on_spinbuttonResults_value_changed" : self.OnChangeResults,
			"on_destroy" : self.OnDestroy,
			"on_buttonDelete_clicked" : self.OnDelete,
			"on_buttonCopy_clicked" : self.OnCopy
		}
		gtkBuilder.connect_signals(signals)
		
		self.entryFind = gtkBuilder.get_object("entryFind")
		self.buttonFind = gtkBuilder.get_object("buttonFind")
		self.scrollResults = gtkBuilder.get_object("scrolledwindowResults")
		self.statusbar = gtkBuilder.get_object("statusbar")
		self.imageHeader = gtkBuilder.get_object("imageHeader")
		self.eventBoxHeader = gtkBuilder.get_object("eventboxHeader")
		self.checkDescriptions = gtkBuilder.get_object("checkbuttonDescriptions")
		self.checkTags = gtkBuilder.get_object("checkbuttonTags")
		self.checkFilenames = gtkBuilder.get_object("checkbuttonFilenames")
		self.checkUsernames = gtkBuilder.get_object("checkbuttonUsernames")
		self.spinResults = gtkBuilder.get_object("spinbuttonResults")
		self.window = gtkBuilder.get_object("FreesoundSearchWindow")
		self.treeHistory = gtkBuilder.get_object("treeviewHistory")
		self.vboxResults = gtk.VBox(spacing=6)
		self.clipboard = gtk.Clipboard()
		
		# load the history dict from the extension data
		self.sampleHistory = self.api.get_data_file(EXTENSION_DATA_NAME, "sampleHistory")
		if not self.sampleHistory:
			self.sampleHistory = {}
		
		# create a model for the used samples history and hook it to the GUI
		self.sampleHistoryModel = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		
		# populate the model using the history dictionary
		for author in self.sampleHistory:
			parent = self.sampleHistoryModel.append(None, [author, None])
			for id in self.sampleHistory[author]:
				self.sampleHistoryModel.append(parent, [id, self.sampleHistory[author][id]])
		
		# hook up the model to the GUI
		self.treeHistory.set_model(self.sampleHistoryModel)
		self.treeHistory.get_selection().set_mode(gtk.SELECTION_SINGLE)
		
		# create the columns with their respective renderers and add them
		# these strings are not displayed, so they're not marked as translatable
		self.treeHistory.append_column(gtk.TreeViewColumn("Author-ID", gtk.CellRendererText(), text=0))
		renderer = gtk.CellRendererText()
		#renderer.set_property("wrap-width", -1)
		#renderer.set_property("wrap-mode", pango.WRAP_WORD)
		#renderer.ellipsize = pango.ELLIPSIZE_END
		self.treeHistory.append_column(gtk.TreeViewColumn("Description", renderer, text=1))
		
		# set up other widget properties
		self.eventBoxHeader.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#ffffff"))
		self.spinResults.set_value(self.maxResults)
		self.entryFind.set_activates_default(True)
		self.entryFind.grab_focus()
		self.buttonFind.set_flags(gtk.CAN_DEFAULT)
		self.buttonFind.grab_default()
		self.scrollResults.add_with_viewport(self.vboxResults)
		self.api.set_window_icon(self.window)
		self.imageHeader.set_from_file(pkg_resources.resource_filename(__name__, "images/banner.png"))
		
		self.window.show_all()
		
		# set up the result fetching thread
		searchThread = SearchFreesoundThread(self.api, self.vboxResults, self.statusbar,
											username, password, self.searchQueue,
											self.sampleHistory, self.sampleHistoryModel,
											self.ToggleFindButton)
		searchThread.setDaemon(True) # thread exits when Jokosher exits
		searchThread.start()
		
	#_____________________________________________________________________
	
	def ToggleFindButton(self, status):
		"""
		Toggles the Find button between Find/Stop.
		
		Parameters:
			status -- True for Find, False for Stop.
		"""
		
		if status:
			# change the icon to a search one
			self.buttonFind.set_tooltip_text(_("Search the Freesound library"))
			self.buttonFind.set_label(_("Find"))
			self.buttonFind.set_image(gtk.image_new_from_stock(gtk.STOCK_FIND, gtk.ICON_SIZE_BUTTON))
		else:
			# change the icon to a stop one
			self.buttonFind.set_tooltip_text(_("Stop the current search"))
			self.buttonFind.set_label(_("Stop"))
			self.buttonFind.set_image(gtk.image_new_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_BUTTON))
			
	#_____________________________________________________________________
	
	def OnFind(self, button):
		"""
		Queries Freesound with the user given input.
		Alternatively, stops the current search.
		
		Parameters:
			button -- reserved for GTK callbacks. Don't use explicitly.
		"""
		global isSearching
		
		if not isSearching:
			isSearching = True
			
			# small adapter dict to convert booleans into 1 or 0
			adapter = {True: "1", False: "0"}
			query = [
					{
					"search" : self.entryFind.get_text(),
					"searchDescriptions" : adapter[self.checkDescriptions.get_active()],
					"searchTags" : adapter[self.checkTags.get_active()],
					"searchFilenames" : adapter[self.checkFilenames.get_active()],
					"searchUsernames" : adapter[self.checkUsernames.get_active()]
					},
					self.maxResults
					]
			
			self.searchQueue.put(query)
			self.ToggleFindButton(False)
		else:
			isSearching = False
			self.ToggleFindButton(True)
		
	#_____________________________________________________________________
	
	def OnDelete(self, button):
		"""
		Deletes a used sample history entry.
		
		Parameters:
			button -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		selection = self.treeHistory.get_selection().get_selected()
		
		# return if there is no active selection
		if not selection[1]:
			return

		selection = self.treeHistory.get_selection().get_selected()
		
		# return if there is no active selection
		if not selection[1]:
			return
		
		if self.sampleHistoryModel.iter_depth(selection[1]) == 0:
			# it's an author row
			sampleAuthor = self.sampleHistoryModel[selection[1]][0]
			del self.sampleHistory[sampleAuthor]
		else:
			# it's a sample row
			sampleID = self.sampleHistoryModel[selection[1]][0]
			sampleDesc = self.sampleHistoryModel[selection[1]][1]
			
			for author in self.sampleHistory:
				if sampleID in self.sampleHistory[author]:
					del self.sampleHistory[author][sampleID]
					
					#TODO: finish this bit
					# if the author has no samples listed, delete him/her
					#if len(self.sampleHistory[author]) == 0:
					#	del self.sampleHistory[author]
					#	self.sampleHistoryModel.remove(selection[1])
					
					break
		
		self.sampleHistoryModel.remove(selection[1])
		
		# save the newly updated history dict
		self.api.set_data_file(EXTENSION_DATA_NAME, "sampleHistory", self.sampleHistory)
		
		# if there's a field left, select the first one
		if len(self.sampleHistoryModel) > 0:
			self.treeHistory.set_cursor(0)
		
	#_____________________________________________________________________
		
	def OnCopy(self, button):
		"""
		Copies a used sample history entry to the clipboard.
		
		Parameters:
			button -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		selection = self.treeHistory.get_selection().get_selected()
		
		# return if there is no active selection
		if not selection[1]:
			return
		
		if self.sampleHistoryModel.iter_depth(selection[1]) == 0:
			# it's an author row
			self.clipboard.set_text(_("Author: %s") % self.sampleHistoryModel[selection[1]][0])
		else:
			# it's a sample row
			self.clipboard.set_text(_("Sample ID: %s\nSample description: %s") % (self.sampleHistoryModel[selection[1]][0],
																				self.sampleHistoryModel[selection[1]][1]))
		
	#_____________________________________________________________________
	
	def OnChangeResults(self, spinbutton):
		"""
		Changes maximum amount of query results displayed.
		
		Parameters:
			spinbutton -- gtk.SpinButton whose value changed.
		"""
		self.maxResults = int(spinbutton.get_value())
		
	#_____________________________________________________________________
	
	def OnClose(self, window):
		"""
		Called when the search dialog gets closed.
		Destroys the dialog.
		"""		
		self.window.destroy()
		
	#_____________________________________________________________________
	
	def OnDestroy(self, window):
		"""
		Called when the search window gets destroyed.
		Destroys the search thread.
		"""
		global isSearching
		isSearching = False
		self.searchQueue.put("quit")
	
	#_____________________________________________________________________
	
	def LoginDetails(self, warning=False):
		"""
		Displays the account details dialog.
		
		Parameters:
			warning -- True if the validation failed and the user must be informed.
		"""
		xmlString = pkg_resources.resource_string(__name__, "LoginDialog.ui")
		gtkBuilder = gtk.Builder()
		gtkBuilder.add_from_string(xmlString)
		
		signals = {
			"on_buttonOK_clicked" : self.OnAcceptDetails,
			"on_buttonCancel_clicked" : self.OnCancelDetails
		}
		gtkBuilder.connect_signals(signals)
	
		self.entryUsername = gtkBuilder.get_object("entryUsername")
		self.entryPassword = gtkBuilder.get_object("entryPassword")
		self.labelWarning = gtkBuilder.get_object("labelWarning")
		self.buttonOK = gtkBuilder.get_object("buttonOK")
		self.loginWindow = gtkBuilder.get_object("LoginDetailsDialog")
		
		self.entryUsername.set_activates_default(True)
		self.entryPassword.set_activates_default(True)
		self.buttonOK.set_flags(gtk.CAN_DEFAULT)
		self.buttonOK.grab_default()
		self.api.set_window_icon(self.loginWindow)
	
		# set the entry text to the saved values
		username = self.api.get_config_value("fsUsername")
		if username is not None and keyring:
			password = None
			try:
				items = gkey.find_items_sync(gkey.ITEM_NETWORK_PASSWORD, {"username" : username})
				if len(items) > 0:
					password = items[0].secret
			except gkey.DeniedError, gkey.NoMatchError:
				pass
		else:
			password = self.api.get_config_value("fsPassword")
		
		if username is not None:
			self.entryUsername.set_text(username)
		if password is not None:
			self.entryPassword.set_text(password)
		
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
		self.labelWarning.set_label(_("Logging in..."))
		self.buttonOK.set_sensitive(False)
		
		# create a worker thread to avoid blocking the GUI while logging in
		worker = threading.Thread(group=None, target=self.FinishLogin, name="Login", 
						args=(username, password))
		worker.start()
		
	#_____________________________________________________________________
	
	def FinishLogin(self, username, password):
		"""
		Attempts to login in to confirm the given credentials.
		If successful, the username is written to a local file for subsequent use
		and the password is saved in the user's keyring (if available, or a local
		file otherwise).
		
		The GUI calls are done using gobject.idle_add() to assure they're
		within the main gtk thread.
		"""
		self.freeSound.Login(username, password)
		
		if self.freeSound.loggedIn:
			self.api.set_config_value("fsUsername", username)
			if keyring:
				gkey.item_create_sync(gkey.get_default_keyring_sync(), 
						gkey.ITEM_NETWORK_PASSWORD, 
						EXTENSION_DATA_NAME,
						{"username" : username},
						password,
						True)
			else:
				self.api.set_config_value("fsPassword", password)

			gobject.idle_add(self.loginWindow.destroy)
			
			if self.showSearch:
				self.showSearch = False
				gobject.idle_add(self.OnMenuItemClick)
		else:
			gobject.idle_add(self.loginWindow.destroy)
			
			if self.retryLogin:
				gobject.idle_add(self.LoginDetails, _("Login failed!"))
	
	#_____________________________________________________________________
	
	def OnCancelDetails(self, button):
		"""
		Cancels the username/password editing operation.
		
		Parameters:
			button -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		self.retryLogin = False
		self.showSearch = False
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
	
	def __init__(self, api, container, statusbar, username, password, queue, history, historyModel, ToggleFindButton):
		"""
		Creates a new instance of SearchFreesoundThread.
		
		Parameters:
			api -- Jokosher extension API.
			container -- gtk container object to put the results into.
			statusbar -- gtk.statusbar used for displaying information.
			username -- Freesound account username.
			password -- Freesound account password.
			queue -- thread queue with the query text.
			history -- history dictionary.
			historyModel -- gtk.TreeStore to display the used samples.
			ToggleFindButton -- function used to toggle the find button between Find/Stop.
		"""
		super(SearchFreesoundThread, self).__init__()
		self.api = api
		self.container = container
		self.statusbar = statusbar
		self.freeSound = None
		self.username = username
		self.password = password
		self.queue = queue
		self.query = None
		self.history = history
		self.historyModel = historyModel
		self.ToggleFindButton = ToggleFindButton
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
		#tooltips = gtk.Tooltips()
		
		# create the container
		hzBox.set_border_width(6)
		hzBox.set_spacing(6)
		evBox.add(hzBox)
		evBox.drag_source_set(gtk.gdk.BUTTON1_MASK, [('text/plain', gtk.TARGET_SAME_APP, 88)], gtk.gdk.ACTION_COPY)
		evBox.drag_source_set_icon_pixbuf(sample.image.get_pixbuf())
		evBox.connect("drag-data-get", self.ReturnData, sample)
		evBox.connect("drag-end", self.DragEnd, sample)
		
		# add the image
		hzBox.add(sample.image)
		
		# add the description label
		sampleDesc = gtk.Label(sample.description)
		sampleDesc.set_width_chars(50)
		sampleDesc.set_line_wrap(True)
		sampleDesc.set_alignment(0, 0.5)
		hzBox.add(sampleDesc)
		
		# add the play button
		playButton = gtk.Button(stock=gtk.STOCK_MEDIA_PLAY)
		playButton.connect("clicked", self.PlayStreamedSample, sample.previewURL)
		hzBox.add(playButton)
		
		# set the correct packaging properties for the hzBox children
		# (widget, expand, fill, padding, pack_type)
		hzBox.set_child_packing(sampleDesc, True, True, 0, gtk.PACK_START)
		hzBox.set_child_packing(playButton, True, False, 0, gtk.PACK_START)
		
		# set the tooltips
		#tooltips.set_tip(playButton, _("Play this sample"))
		#tooltips.set_tip(sampleDesc, _("You can drag and drop this sample into your Jokosher project"))
		
		# add everything to the container and then show it
		evBox.show_all()
		self.container.add(evBox)
		
	#_____________________________________________________________________
	
	def ReturnData(self, widget, drag_context, selection_data, info, time, sample):
		"""
		Called when the user drops a sample inside Jokosher.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use it explicitly.
			drag_context -- reserved for GTK callbacks. Don't use it explicitly.
			selection_data -- reserved for GTK callbacks. Don't use it explicitly.
			info -- reserved for GTK callbacks. Don't use it explicitly.
			time -- reserved for GTK callbacks. Don't use it explicitly.
			sample -- the Sample to be dropped into another window.
		"""
		selection_data.set(selection_data.target, 8, sample.previewURL)

	#_____________________________________________________________________
	
	def DragEnd(self, widget, drag_context, sample):
		"""
		Called when a drag and drop operation finishes.
		It adds the dropped Sample to the used sample history dictionary
		and the treeview.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use it explicitly.
			drag_context -- reserved for GTK callbacks. Don't use it explicitly.
			sample -- the sample to be added to the history.
		"""
		# check if the author already exists
		if sample.author in self.history:
			# check if the sample already exists
			if sample.sid in self.history[sample.author]:
				#already listed, nothing to do
				return
			else:
				for row in self.historyModel:
					# match the author name and make sure it's a root level node
					if row[0] == sample.author and self.historyModel.iter_depth(row.iter) == 0:
						self.history[sample.author][sample.sid] = sample.description
						self.historyModel.append(row.iter, [sample.sid, sample.description])
		else:
			self.history[sample.author] = {}
			self.history[sample.author][sample.sid] = sample.description
			
			parent = self.historyModel.append(None, [sample.author, None])
			self.historyModel.append(parent, [sample.sid, sample.description])
		
		# save the newly updated history dict
		self.api.set_data_file(EXTENSION_DATA_NAME, "sampleHistory", self.history)
		
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
		self.container.add(gtk.Label(_("No results for %s") % self.query[0]["search"]))
		self.container.show_all()
	
	#_____________________________________________________________________
		
	def SetSearchingStatus(self):
		"""
		Sets the searching status bar message.
		"""
		self.statusbar.push(0, _("Searching..."))

	#_____________________________________________________________________
	
	def SetFetchingStatus(self, counter, maxResults):
		"""
		Sets the current fetching status bar message to display a
		percentage.
		
		Parameters:
			counter -- number of samples already added to the results.
			maxResults -- number of maximum results to display.
		"""
		self.statusbar.pop(0)
		self.statusbar.push(0, _("Fetching samples... %s%%") % int((counter*100)/maxResults))
		
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
					It's a list with the following format:
					[
					{
					search : "string to match",
					searchDescriptions : "1 or 0",
					searchTags : "1 or 0",
					searchFilenames : "1 or 0",
					searchUsernames : "1 or 0"
					},
					maxResults
					]
			
			*the fields labeled "1 or 0" define whether those fields
			should be included in the search.
		"""
		global isSearching
		
		gobject.idle_add(self.EmptyContainer)
		gobject.idle_add(self.SetIdleStatus)
		gobject.idle_add(self.SetSearchingStatus)
		
		self.query = query
		samples = self.freeSound.Search(query[0])
		counter = 0
		
		if not samples:
			gobject.idle_add(self.NoResults)
			gobject.idle_add(self.SetIdleStatus)
		else:
			gobject.idle_add(self.EmptyContainer)
			gobject.idle_add(self.SetIdleStatus)
			gobject.idle_add(self.SetFetchingStatus, counter, query[1])
			
			for sample in samples[:query[1]]:
				# stop the current search operation if the user requested so
				if not isSearching:
					break
				
				# fetch the sample's metadata and preview image in this thread
				sample.FetchMetaData()
				self.FetchPreviewImage(sample)
				
				# add the sample and update the status bar in the gtk thread
				counter += 1
				gobject.idle_add(self.AddSample, sample)
				gobject.idle_add(self.SetFetchingStatus, counter, query[1])
				
			gobject.idle_add(self.SetIdleStatus)
			gobject.idle_add(self.ToggleFindButton, True)
			
	#_____________________________________________________________________

	def FetchPreviewImage(self, sample):
		"""
		Downloads the preview image for the given sample. It then assigns
		it to the sample's image property.
		
		Parameter:
			sample -- sample whose preview image shoud be fetched.
		"""
		try:
			imgfile = urllib.urlretrieve(sample.image)[0]
		except:
			# TODO: handle the url problems
			return

		image = gtk.Image()
		image.set_from_pixbuf(gtk.gdk.pixbuf_new_from_file_at_size(imgfile, 50, 50))
		sample.image = image
		os.unlink(imgfile)
		
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
			query = self.queue.get() # blocks until there's an item to search for
			
			if query == "quit":
				self.player.set_state(gst.STATE_NULL) # stop any playback
				break
			else:
				self.Search(query)
			
	#_____________________________________________________________________
	
#=========================================================================		

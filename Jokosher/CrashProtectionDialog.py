#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	This class handles restoring projects after a crash has occured.
#
#-------------------------------------------------------------------------------

import gtk.glade
import gobject
import os, time
import xml.dom.minidom as xml
import gzip
import Utils
import Globals
import gettext
_ = gettext.gettext

#=========================================================================

class CrashProtectionDialog:
	"""
	Displays a dialog allowing the user to either select a previously crashed 
	project for restoration or to delete a crash file.
	"""

	#_____________________________________________________________________

	
	def __init__(self, parent, crashed=False):
		self.parent = parent
		
		self.crashedProjectTree = gtk.glade.XML(Globals.GLADE_PATH, "CrashedProjectDialog")
		self.crashedProjectDialog = self.crashedProjectTree.get_widget("CrashedProjectDialog")

		crashMessage = self.crashedProjectTree.get_widget("crashMessage")
		if not crashed:
			crashMessage.hide()

		self.crashedProjectDialog.set_transient_for(self.parent.window)

		closeButton = self.crashedProjectTree.get_widget("CrashDialogCloseButton")	
		closeButton.connect("clicked", lambda dialog: self.crashedProjectDialog.destroy())

		self.populate()

		self.crashedProjectDialog.run()

	#_____________________________________________________________________


	def populate(self):
		backupDir = os.path.join(os.path.expanduser("~"), ".jokosher", "backups")
		crashTable = self.crashedProjectTree.get_widget("crashTable")
		row = 1
		for backupFile in os.listdir(backupDir):
			backup = os.path.join(backupDir, backupFile)
			if backup == self.parent.backupProject:
				#We don't want to restore a backup we've just made in this session
				continue
			Globals.debug("Found backup file: %s" % backup)
			try:
				if os.stat(backup).st_size == 0:
					#This backup file was never written to, so just delete it
					os.remove(backup)
					continue
				backupFD = gzip.GzipFile(backup, "r")
				backupXML = xml.parse(backupFD)
				backupDict = Utils.LoadDictionaryFromXML(backupXML.getElementsByTagName('Parameters')[0])
				saveTime = os.stat(backup).st_mtime
				name = backupDict["name"]
				hbox = gtk.HBox(3)
				crashTable.attach(gtk.Label(name), 0, 1, row, row+1)
				crashTable.attach(gtk.Label(time.ctime(saveTime)), 1, 2, row, row+1)
				restoreButton = gtk.Button(_("Restore"))
				restoreImage = gtk.Image()
				restoreImage.set_from_stock(gtk.STOCK_REVERT_TO_SAVED, gtk.ICON_SIZE_BUTTON)
				restoreButton.set_image(restoreImage)
				deleteButton = gtk.Button(gtk.STOCK_DELETE)
				deleteButton.set_use_stock(True)
				crashTable.attach(restoreButton, 2, 3, row, row+1)
				crashTable.attach(deleteButton, 3, 4, row, row+1)
				#Record the latest processed backup so we know when to report new crashes
				if saveTime > float(Globals.settings.general["lastbackup"]):
					Globals.settings.general["lastbackup"] = saveTime 
					Globals.settings.write()
				row+=1
			except Exception, e:
				Globals.debug("Couldn't read backup file: %s, reason: %s" % (backup, e.message))
		crashTable.show_all()



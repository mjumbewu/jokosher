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

	
	def __init__(self):
		self.crashedProjectTree = gtk.glade.XML(Globals.GLADE_PATH, "CrashedProjectDialog")

		self.crashedProjectDialog = self.crashedProjectTree.get_widget("CrashedProjectDialog")

		closeButton = self.crashedProjectTree.get_widget("CrashDialogCloseButton")	
		closeButton.connect("clicked", lambda dialog: self.crashedProjectDialog.destroy())

		self.populate()

	#_____________________________________________________________________


	def populate(self):
		backupDir = os.path.join(os.path.expanduser("~"), ".jokosher", "backups")
		crashTable = self.crashedProjectTree.get_widget("crashTable")
		row = 1
		for backupFile in os.listdir(backupDir):
			backup = os.path.join(backupDir, backupFile)
			Globals.debug("Found backup file: %s" % backup)
			try:
				if os.stat(backup).st_size == 0:
					#This backup file was never written to, so just delete it
					os.remove(backup)
					continue
				backupFD = gzip.GzipFile(backup, "r")
				backupXML = xml.parse(backupFD)
				backupDict = Utils.LoadDictionaryFromXML(backupXML.getElementsByTagName('Parameters')[0])
				saveTime = int(backupFile.split("-")[0])
				name = backupDict["name"]
				hbox = gtk.HBox(3)
				crashTable.attach(gtk.Label(name), 0, 1, row, row+1)
				crashTable.attach(gtk.Label(time.ctime(saveTime)), 1, 2, row, row+1)
				crashTable.attach(gtk.Button("Restore"), 2, 3, row, row+1)
				crashTable.attach(gtk.Button("Delete"), 3, 4, row, row+1)
				row+=1
				except:
					Globals.debug("Couldn't read backup file: %s" % backup)
		crashTable.show_all()



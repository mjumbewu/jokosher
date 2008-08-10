#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	This class handles restoring projects after a crash has occurred.
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

		self.crashTable = self.crashedProjectTree.get_widget("crashTable")

		closeButton = self.crashedProjectTree.get_widget("CrashDialogCloseButton")	
		closeButton.connect("clicked", lambda dialog: self.crashedProjectDialog.destroy())

		self.populate()

		self.crashedProjectDialog.run()

	#_____________________________________________________________________


	def populate(self):
		backupDir = os.path.join(os.path.expanduser("~"), ".jokosher", "backups")
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
				projectFile = backupDict["projectfile"]
				hbox = gtk.HBox(3)
				self.crashTable.attach(gtk.Label(name), 0, 1, row, row+1)
				self.crashTable.attach(gtk.Label(time.ctime(saveTime)), 1, 2, row, row+1)
				restoreButton = gtk.Button(_("Restore"))
				restoreImage = gtk.Image()
				restoreImage.set_from_stock(gtk.STOCK_REVERT_TO_SAVED, gtk.ICON_SIZE_BUTTON)
				restoreButton.set_image(restoreImage)
				restoreButton.connect("clicked", self.restore, backup, name, saveTime, projectFile)
				deleteButton = gtk.Button(gtk.STOCK_DELETE)
				deleteButton.set_use_stock(True)
				deleteButton.connect("clicked", self.delete, backup, name)
				self.crashTable.attach(restoreButton, 2, 3, row, row+1)
				self.crashTable.attach(deleteButton, 3, 4, row, row+1)
				#Record the latest processed backup so we know when to report new crashes
				if saveTime > float(Globals.settings.general["lastbackup"]):
					Globals.settings.general["lastbackup"] = saveTime 
					Globals.settings.write()
				row+=1
			except Exception, e:
				Globals.debug("Couldn't read backup file: %s, reason: %s" % (backup, e.message))
		self.crashTable.show_all()

	#_____________________________________________________________________


	def delete(self, widget, backup, name):
		message = _("Are you sure you wish to delete the backup for %s?") % name
		dlg = gtk.MessageDialog(self.crashedProjectDialog,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_QUESTION,
				gtk.BUTTONS_NONE,
				message)
		dlg.add_buttons(gtk.STOCK_DELETE, gtk.RESPONSE_DELETE_EVENT,
				gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
		response = dlg.run()
		if response == gtk.RESPONSE_DELETE_EVENT:
			os.remove(backup)
			#Regenerate list of projects
			self.crashTable.foreach(self.crashTable.remove)
			self.populate()
		dlg.destroy()

	#_____________________________________________________________________


	def restore(self, widget, backup, name, saveTime, projectFile):
		if saveTime < os.stat(projectFile).st_mtime:
			#Backup is older than the project file, make sure the user really wants this
			message = _("The project (%s) has been modified more recently than this backup. Are you certain you wish to restore it?") % name
			dlg = gtk.MessageDialog(self.crashedProjectDialog,
					gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
					gtk.MESSAGE_QUESTION,
					gtk.BUTTONS_NONE,
					message)
			dlg.add_buttons(_("Restore"), gtk.RESPONSE_APPLY,
					gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
			response = dlg.run()
			if response == gtk.RESPONSE_CANCEL:
				dlg.destroy()
		
		if self.parent.project and self.parent.project.projectfile == projectFile:
			#We're restoring the currently open project
			#Save the project so we don't prompt the user about unsaved work when we close it
			self.parent.OnSaveProject()
			#Close the project
			self.parent.CloseProject()
			#Restore the backup
			os.rename(projectFile, projectFile + ".old")
			os.rename(backup, projectFile)
			#Reopen project
			self.parent.OpenProjectFromPath(projectFile)
		else:
			#Just restore the backup
			os.rename(projectFile, projectFile + ".old")
			os.rename(backup, projectFile)
		#Regenerate list of projects
		self.crashTable.foreach(self.crashTable.remove)
		self.populate()
		dlg.destroy()


#!/usr/bin/env python

from distutils.core import setup
from subprocess import *
import os
import glob

#Create an array with all the locale filenames
I18NFILES = []
for filepath in glob.glob("locale/*/LC_MESSAGES/*.mo"):
	targetpath = os.path.dirname(os.path.join("share/", filepath))
	I18NFILES.append((targetpath, [filepath]))

#Create an array with all the help documents (docbook)
HELPDOCS = []
for filepath in glob.glob("help/jokosher/*/*.xml"):
	targetpath = os.path.dirname(os.path.join("share/gnome/", filepath))
	HELPDOCS.append((targetpath, [filepath]))


#Create an array with all the help images
HELPIMAGES = []
for filepath in glob.glob("help/jokosher/*/figures/*.png"):
	targetpath = os.path.dirname(os.path.join("share/gnome/", filepath))
	HELPIMAGES.append((targetpath, [filepath]))
	
#Check if scrollkeeper is available
OMFFILES = []
omfdir = None
try:
	process = Popen(args=["scrollkeeper-config", "--omfdir"], stdout=PIPE)
except OSError:
	#Not available. Skip the registration.
	pass
else:
	#Obtain the OMF repository directory to install and register the help files
	omfdir = os.path.join(process.stdout.read().strip(), "jokosher")
	OMFFILES.append((omfdir, glob.glob("help/jokosher/*.omf")))
		
dist = setup(name='jokosher',
	version='0.11.5',
	author='Jokosher Project',
	author_email='jokosher-devel-list@gnome.org',
	maintainer='Jokosher Project',
	maintainer_email='jokosher-devel-list@gnome.org',
	description='Multi-track non-linear audio editing.',
	long_description='Jokosher is a simple yet powerful multi-track studio. With it you can create and record music, podcasts and more, all from an integrated simple environment.',
	url='http://www.jokosher.org/',
	download_url='http://www.jokosher.org/download',
	license='GNU GPL',
	platforms='linux',
	scripts=['bin/jokosher'],
	packages=['Jokosher', 'Jokosher/elements', 'Jokosher/ui', 'Jokosher/PlatformUtils'],
	data_files=[
		('share/jokosher/gtk-builder-ui', glob.glob("gtk-builder-ui/*.ui")),
		('share/jokosher/Instruments', glob.glob("Instruments/*.instr")),
		('share/jokosher/Instruments/images', glob.glob('Instruments/images/*.png')),
		('share/icons/hicolor/48x48/apps', ['images/jokosher.png']),
		('share/pixmaps', ['images/jokosher.png']),
		('share/jokosher/pixmaps', glob.glob("images/*.png")),
		('share/applications', ['bin/jokosher.desktop']),
		('share/mime/packages',	['bin/jokosher.xml']),
		('share/jokosher/extensions', glob.glob("extensions/*.py") + glob.glob("extensions/*.egg"))
		]+I18NFILES+HELPDOCS+HELPIMAGES+OMFFILES
)

#Non-documented way of getting the final directory prefix
installCmd = dist.get_command_obj(command="install_data")
installdir = installCmd.install_dir
installroot = installCmd.root

if not installroot:
	installroot = ""

if installdir:
	installdir = os.path.join(os.path.sep,
			installdir.replace(installroot, ""))

# Update the real URL attribute inside the OMF files
# and register them with scrollkeeper
if omfdir != None and installdir != None and dist != None:
	
	#Create an array with the docbook file locations
	HELPURI = []
	for filepath in glob.glob("help/jokosher/*/jokosher.xml"):
		targeturi = os.path.join(installdir, "share/gnome/", filepath)
		HELPURI.append(targeturi)
	
	#Replace the URL placeholder inside the OMF files
	installedOmfFiles = glob.glob(installroot + omfdir + "/*.omf")
	for fileNum in range(0, len(installedOmfFiles)):
		call(["scrollkeeper-preinstall", HELPURI[fileNum],
			installedOmfFiles[fileNum], installedOmfFiles[fileNum]])
		
	#Update the scrollkeeper catalog
	if os.geteuid() == 0:
		print "Updating the scrollkeeper index..."
		call(["scrollkeeper-update", "-o", installroot + omfdir])

# Update the mime types
if os.geteuid() == 0 and dist != None:
	print "Updating the mime-types...."
	
	#update the mimetypes database
	try:
	    call(["update-mime-database", "/usr/share/mime/"])
	except:
	    pass
	
	#update the .desktop file database
	try:
	   call(["update-desktop-database"])
	except:
	    pass

print "\nInstallation finished! You can now run Jokosher by typing 'jokosher' or through your applications menu icon."
	
## To uninstall manually delete these files/folders:
## /usr/bin/jokosher
## /usr/share/jokosher/
## /usr/share/gnome/help/jokosher/
## /usr/share/icons/hicolor/48x48/apps/jokosher.png
## /usr/share/locale/*/LC_MESSAGES/jokosher.mo
## /usr/share/pixmaps/jokosher.png
## /usr/share/applications/jokosher.desktop
## /usr/lib/python2.X/site-packages/Jokosher/
## /usr/share/omf/jokosher/*.omf

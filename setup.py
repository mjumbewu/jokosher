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
	#This step only makes sense if run as root
	if os.geteuid() == 0:
		omfdir = os.path.join(process.stdout.read().strip(), "jokosher")
		OMFFILES.append((omfdir, glob.glob("help/jokosher/*.omf")))
		
dist = setup(name='jokosher',
	version='0.9',
	author='Jokosher Project',
	author_email='email@jokosher.org',
	maintainer='David Corrales',
	maintainer_email='corrales.david@gmail.com',
	description='Multi-track non-linear audio editing.',
	long_description='Jokosher is a simple yet powerful multi-track studio. With it you can create and record music, podcasts and more, all from an integrated simple environment.',
	url='http://www.jokosher.org/',
	download_url='http://www.jokosher.org/download',
	license='GNU GPL',
	platforms='linux',
	scripts=['bin/jokosher'],
	packages=['Jokosher'],
	data_files=[
		('share/jokosher/', glob.glob("Jokosher/*.glade")),
		('share/jokosher/', ["Jokosher/jokosher-logo.png"]),
		('share/jokosher/Instruments', glob.glob("Instruments/*.instr")),
		('share/jokosher/Instruments/images', glob.glob('Instruments/images/*.png')),
		('share/icons/hicolor/48x48/apps', ['images/jokosher-icon.png']),
		('share/pixmaps', ['images/jokosher-icon.png']),
		('share/jokosher/pixmaps', glob.glob("images/*.png")),
		('share/applications', ['bin/jokosher.desktop']),
		('share/mime/packages',	['bin/jokosher.xml']),
		('share/jokosher/extensions', glob.glob("extensions/*.py") + glob.glob("extensions/*.egg"))
		]+I18NFILES+HELPDOCS+HELPIMAGES+OMFFILES
)

#Update the real URL attribute inside the OMF files and then
#register the docs with scrollkeeper. Also update the mime types.
if omfdir != None and os.geteuid() == 0 and dist != None:
	#Non-documented way of getting the final directory prefix
	installdir = dist.get_command_obj(command="install_data").install_dir
	
	#Create an array with the docbook file locations
	HELPURI = []
	for filepath in glob.glob("help/jokosher/*/jokosher.xml"):
		targeturi = os.path.join(installdir, "share/gnome/", filepath)
		HELPURI.append(targeturi)
	
	#Replace the URL placeholder inside the OMF files using sed
	#We assume that the locale order between omf/docbook will stay the same
	i = 0
	for filepath in glob.glob(omfdir+"/*.omf"):
		expression = "s|PATH_PLACEHOLDER|%s|" % HELPURI[i]
		call(["sed", "-e", expression, filepath, "-i"])
		i += 1
		
	#Update the scrollkeeper catalog and mime types
	print "Updating the scrollkeeper index and mime types..."
	call(["scrollkeeper-update", "-o", omfdir])
	call(["update-mime-database", "/usr/share/mime/"])

print "\nInstallation finished! You can now run Jokosher by typing 'jokosher' or through your applications menu icon."
	
## To uninstall manually delete these files/folders:
## /usr/bin/jokosher
## /usr/share/jokosher/
## /usr/share/gnome/help/jokosher/
## /usr/icons/hicolor/48x48/apps/jokosher-icon.png
## /usr/share/locale/*/LC_MESSAGES/jokosher.mo
## /usr/share/pixmaps/jokosher-icon.png
## /usr/share/applications/jokosher.desktop
## /usr/lib/python2.X/site-packages/Jokosher/
## omfdir/jokosher/*.omf

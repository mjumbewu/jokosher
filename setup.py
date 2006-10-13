#!/usr/bin/env python

from distutils.core import setup
import os
import glob

I18NFILES = []
for filepath in glob.glob("locale/src/mo/*/LC_MESSAGES/*.mo"):
	lang = filepath[len("locale/src/mo/"):]
	targetpath = os.path.dirname(os.path.join("share/locale",lang))
	I18NFILES.append((targetpath, [filepath]))


setup(name='jokosher',
	version='0.2',
	scripts=['Jokosher/Jokosher'],
	packages=['Jokosher'],
	data_files=[('share/jokosher/',
		glob.glob("Jokosher/*.glade")
		),
		('share/jokosher/Instruments',
		glob.glob("Instruments/*.instr")
		),
		('share/jokosher/Instruments/images',
		glob.glob('Instruments/images/*')
		),
		('share/applications',
		glob.glob("*/jokosher.desktop")
		),
		('share/icons/hicolor/48x48/apps',
		['Jokosher/jokosher-logo.png']
		),
		('share/pixmaps',
		glob.glob("images/*.png")
		),
		('share/applications',
		['jokosher.desktop'],
		)
		]+I18NFILES
)


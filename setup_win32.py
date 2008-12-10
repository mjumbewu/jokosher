#!/usr/bin/env python

from distutils.core import setup
from subprocess import *
import os
import glob
import py2exe

dist = setup(name='jokosher',
	version='0.10',
	author='Jokosher Project',
	author_email='jokosher-devel@gnome.org',
	maintainer='Michael Sheldon',
	maintainer_email='mike@mikeasoft.com',
	description='Multi-track non-linear audio editing.',
	long_description='Jokosher is a simple yet powerful multi-track studio. With it you can create and record music, podcasts and more, all from an integrated simple environment.',
	url='http://www.jokosher.org/',
	download_url='http://www.jokosher.org/download',
	license='GNU GPL',
	packages=['Jokosher', 'Jokosher/elements'],
	windows = [
			{
				'script' : 'bin/jokosher'
			}
		],
	options = {
			'py2exe': {
				'packages' : 'encodings, Jokosher, Jokosher.elements',
				'includes' : 'cairo, gtk, gtk.glade, gobject, pango, pangocairo, atk, gst, pygst'
			}
	},
	data_files=[
		"Jokosher\Jokosher.glade",
		"Jokosher\jokosher-logo.png",
		#glob.glob("Instruments\*.instr"),
		#glob.glob('Instruments\images\*.png'),
		#glob.glob("extensions\*.py") + glob.glob("extensions\*.egg"),
		]
)


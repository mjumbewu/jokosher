#!/usr/bin/env python

from distutils.core import setup
from subprocess import *
import os
import glob
import pygst
pygst.require('0.10')
import py2exe

dist = setup(name='jokosher',
	version='0.11.5',
	author='Jokosher Project',
	author_email='jokosher-devel-list@gnome.org',
	maintainer='Michael Sheldon',
	maintainer_email='mike@mikeasoft.com',
	description='Multi-track non-linear audio editing.',
	long_description='Jokosher is a simple yet powerful multi-track studio. With it you can create and record music, podcasts and more, all from an integrated simple environment.',
	url='http://www.jokosher.org/',
	download_url='http://www.jokosher.org/download',
	license='GNU GPL',
	packages=['Jokosher', 'Jokosher/elements', 'Jokosher/ui', 'Jokosher/PlatformUtils'],
	windows = [
			{
				'script' : 'bin/jokosher',
				'icon_resources' : [(1, 'images/jokosher.ico')]
			}
		],
	options = {
			'py2exe': {
				'packages' : 'encodings, Jokosher, Jokosher.elements, Jokosher.ui',
				'includes' : 'cairo, gtk, gobject, pango, pangocairo, atk, gio, gst, pygst, xdg, Queue, xml.etree.ElementTree, gtk.keysyms, code, keyword, re, pkg_resources'
			}
	},
	data_files=[
		#glob.glob("Instruments\*.instr"),
		#glob.glob('Instruments\images\*.png'),
		#glob.glob("extensions\*.py") + glob.glob("extensions\*.egg"),
		]
)


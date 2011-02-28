from setuptools import setup
import sys, os
from shutil import copy

version = "1.1"
setup(name="ExtensionConsole",
	  version=version,
	  author='Laszlo Pandy',
	  author_email='laszlok2@gmail.com',
	  maintainer='Laszlo Pandy',
	  maintainer_email='laszlok2@gmail.com',
	  description='A powerful python console for Jokosher.',
	  long_description="A fully functional python console with access to the extension API and the Jokosher internals",
	  license='GNU GPL',
	  platforms='linux',
	  packages=["ExtensionConsole"],
	  package_dir={"ExtensionConsole":"src"},
	  package_data={"":["pyconsole.py", "ConsoleDialog.ui", "SearchDialog.ui"]},
	  entry_points="""
		[jokosher.extensions]
		extension = ExtensionConsole:ExtensionConsole
		"""
)

# copy egg file to the deployment directory in the svn structure
copy("dist/ExtensionConsole-%s-py%d.%d.egg" % (version, sys.version_info[0], sys.version_info[1]),
	 "../../") 

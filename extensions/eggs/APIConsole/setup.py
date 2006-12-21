from setuptools import setup
import sys, os
from shutil import copy
version="0.1"
setup(name="APIConsole",
version=version,
description="Offers a simple console to acces the Jokosher API",
packages=["APIConsole"],
package_dir={"APIConsole":"src"},
package_data={"":["APIConsole.glade"]},
entry_points="""
[jokosher.extensions]
extension = APIConsole:APIConsole
"""
)
# copy egg file to the deployment directory in the svn structure
copy("dist/APIConsole-%s-py%d.%d.egg" % (version,sys.version_info[0],sys.version_info[1]),
	 "../../") 

from setuptools import setup
import sys, os
from shutil import copy
version="0.1"
setup(name="PidginExtension",
version=version,
description="Sets status in Pidgin buddy list",
packages=["PidginExtension"],
package_dir={"PidginExtension":"src"},
package_data={"":["pidgin.png"]},
entry_points="""
[jokosher.extensions]
extension = PidginExtension:PidginExtension
"""
)
# copy egg file to the deployment directory in the svn structure
copy("dist/PidginExtension-%s-py%d.%d.egg" % (version,sys.version_info[0],sys.version_info[1]),
	 "../../") 
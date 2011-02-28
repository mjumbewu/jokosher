from setuptools import setup
import sys, os
from shutil import copy
version="0.11"
setup(name="SetTempo",
version=version,
description="Sets tempo for current project",
packages=["SetTempo"],
package_dir={"SetTempo":"src"},
package_data={"":["SetTempo.ui"]},
entry_points="""
[jokosher.extensions]
extension = SetTempo:SetTempo
"""
)
# copy egg file to the deployment directory in the svn structure
copy("dist/SetTempo-%s-py%d.%d.egg" % (version,sys.version_info[0],sys.version_info[1]),
	 "../../") 

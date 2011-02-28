from setuptools import setup
import sys, os
from shutil import copy
version="0.11"
setup(name="Minimal",
version=version,
description="Runs a mimimal version of Jokosher",
packages=["Minimal"],
package_dir={"Minimal":"src"},
package_data={"":["Minimal.ui"]},
entry_points="""
[jokosher.extensions]
extension = Minimal:Minimal
"""
)
# copy egg file to the deployment directory in the svn structure
copy("dist/Minimal-%s-py%d.%d.egg" % (version,sys.version_info[0],sys.version_info[1]),
	 "../../") 

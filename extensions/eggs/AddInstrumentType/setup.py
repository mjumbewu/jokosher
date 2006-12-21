from setuptools import setup
import sys, os
from shutil import copy
version="0.1"
setup(name="AddInstrumentType",
version=version,
description="Adds an instrument type to jokosher",
packages=["AddInstrumentType"],
package_dir={"AddInstrumentType":"src"},
package_data={"":["AddInstrumentType.glade"]},
entry_points="""
[jokosher.extensions]
extension = AddInstrumentType:AddInstrumentType
"""
)
# copy egg file to the deployment directory in the svn structure
copy("dist/AddInstrumentType-%s-py%d.%d.egg" % (version,sys.version_info[0],sys.version_info[1]),
	 "../../") 

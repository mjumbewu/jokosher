from setuptools import setup
import sys, os
from shutil import copy
version="0.11"
setup(name="InstrumentTypeManager",
version=version,
description="Adds or Removes an instrument type from jokosher",
packages=["InstrumentTypeManager"],
package_dir={"InstrumentTypeManager":"src"},
package_data={"":["InstrumentTypeManager.ui"]},
entry_points="""
[jokosher.extensions]
extension = InstrumentTypeManager:InstrumentTypeManager
"""
)
# copy egg file to the deployment directory in the svn structure
copy("dist/InstrumentTypeManager-%s-py%d.%d.egg" % (version,sys.version_info[0],sys.version_info[1]),
	 "../../") 

#!/usr/bin/env python

import os, sys

def main():
	if len(sys.argv) != 2:
		print "Usage: %s <launchpad-download-folder>" % sys.argv[0]
		return
	
	files_to_merge = []
	reldir = sys.argv[1]
	for name in os.listdir(reldir):
		if name.endswith(".po") and os.path.exists(os.path.join(reldir, name)):
			files = (os.path.join(reldir, name), name)
			files_to_merge.append(files)
			
	print "Ready to merge %d PO files." % len(files_to_merge)
	for dl_file, file in files_to_merge:
		merge_files(dl_file, file)
	print "Done."
	
	
def merge_files(rosetta_download, bzr_version):
	COMMAND = 'msgmerge "%s" "%s" -o "%s"'
	
	outfile = bzr_version + ".tmp"
	cmd = COMMAND % (rosetta_download, rosetta_download, outfile)
	
	print "=> msgmerge-ing", bzr_version
	os.system(cmd)
	os.rename(outfile, bzr_version)
	
if __name__ == "__main__":
	main()

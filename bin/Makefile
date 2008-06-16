###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh

all :;

install :
	@ echo "              Fix up the n\* in bin/Makefile"
	@ ./mksetup $(EUPS_DIR) $(EUPS_PATH) $(SETUP_ALIASES)
	cp Makefile mksetup setups.{csh,sh} eups eups_setup *.py $(EUPS_DIR)/bin
	@ echo Tell RHL to build .pyc files

clean :
	- /bin/rm -f *~ core

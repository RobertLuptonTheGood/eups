###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh

all :;

install :
	@ ./mksetup $(EUPS_DIR) $(PROD_DIR_PREFIX)
	cp Makefile mksetup {evil,eups_,setups}*[a-z] $(EUPS_DIR)/bin

clean :
	- /bin/rm -f *~ core

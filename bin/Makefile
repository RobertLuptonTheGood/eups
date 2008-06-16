###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh

all :;

install :
	@ echo "              Fix up the n\* in bin/Makefile"
	@ ./nmksetup $(EUPS_DIR) $(EUPS_PATH) $(SETUP_ALIASES)
	cp Makefile mksetup neups eups neups_setup *.py {evil,eups_,setups}*[a-z] $(EUPS_DIR)/bin

clean :
	- /bin/rm -f *~ core

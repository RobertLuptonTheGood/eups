###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh

all :;

install :
	- ./mksetup $(EUPS_DIR) $(PROD_DIR_PREFIX) $(PRODUCTS)
	- cp * $(EUPS_DIR)/bin

clean :
	- /bin/rm -f *~ core

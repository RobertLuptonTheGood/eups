###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# D. Finkbeiner & D. Schlegel
###############################################################################

SHELL = /bin/sh
#
all :;
#
# Install things in their proper places in $(PHOTOOP_DIR)
#
install :
	- ./mksetup $(EUPS_DIR) $(PROD_DIR_PREFIX) $(PRODUCTS)
	- cp * $(EUPS_DIR)/bin

clean :
	- /bin/rm -f *~ core

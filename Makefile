###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# D. Finkbeiner & D. Schlegel
# Modified : Nikhil Padmanabhan
###############################################################################

SHELL = /bin/sh

SUBDIRS = bin etc examples

#
# Install things in their proper places in $(EUPS_DIR)
#
install :
	@echo "You should be sure to have updated before doing this."
	@echo ""
	@if [ "$(EUPS_DIR)" = "" ]; then \
		echo You have not specified a destination directory EUPS_DIR >&2; \
		exit 1; \
	fi 
	@if [ "$(PROD_DIR_PREFIX)" = "" ]; then \
		echo You have not specified PROD_DIR_PREFIX >&2; \
		exit 1; \
	fi 
	@if [ "$(PRODUCTS)" = "" ]; then \
		echo You have not specified a destination directory PRODUCTS >&2; \
		exit 1; \
	fi
	@if [ -d $(EUPS_DIR) ]; then \
		echo The destination directory already exists >&2; \
		echo I will give you 30 seconds to think about this; \
		sleep 30; \
		rm -rf $(EUPS_DIR); \
	fi 
	@echo ""
	@echo "You will be installing in \$$EUPS_DIR=$$EUPS_DIR"
	@echo "I'll give you 5 seconds to think about it"
	@echo sleep 5
	@echo ""
	@ mkdir $(EUPS_DIR)
	@ for f in $(SUBDIRS); do \
		(mkdir $(EUPS_DIR)/$$f; cd $$f ; echo In $$f; $(MAKE) $(MFLAGS) install ); \
	done
	- cp Makefile $(EUPS_DIR)
	- cp README $(EUPS_DIR)
	- cp cvsnotes $(EUPS_DIR)
	@echo "Remember to source setups.[c]sh before using!"
clean :
	- /bin/rm -f *~ core
	@ for f in $(SUBDIRS); do \
		(cd $$f ; echo In $$f; $(MAKE) $(MFLAGS) clean ); \
	done






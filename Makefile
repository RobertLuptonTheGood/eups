###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh

SUBDIRS = bin etc examples

install :
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
		echo The destination directory already exists for EUPS_DIR=$(EUPS_DIR). >&2; \
		echo Please remove any old installation of EvilUPS there first. >&2; \
		exit 1; \
	fi 
	@echo ""
	@echo "You will be installing in \$$EUPS_DIR=$$EUPS_DIR"
	@echo "I'll give you 5 seconds to think about it"
	@echo sleep 5
	@echo ""
	@ mkdir -p $(EUPS_DIR)
	@ mkdir -p $(PROD_DIR_PREFIX)
	@ mkdir -p $(PRODUCTS)
	@ for f in $(SUBDIRS); do \
		(mkdir $(EUPS_DIR)/$$f; cd $$f ; echo In $$f; $(MAKE) $(MFLAGS) install ); \
	done
	- cp Makefile $(EUPS_DIR)
	- cp README $(EUPS_DIR)
	- cp cvsnotes $(EUPS_DIR)
	- cp Release_Notes $(EUPS_DIR)
	- cp gpl.txt $(EUPS_DIR)
	@echo "Remember to source setups.[c]sh before using!"
clean :
	- /bin/rm -f *~ core
	@ for f in $(SUBDIRS); do \
		(cd $$f ; echo In $$f; $(MAKE) $(MFLAGS) clean ); \
	done


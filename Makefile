###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh

SUBDIRS = bin doc examples

install :
	@if [ "$(EUPS_DIR)" = "" ]; then \
		echo You have not specified a destination directory EUPS_DIR >&2; \
		exit 1; \
	fi 
	@if [ "$(PROD_DIR_PREFIX)" = "" ]; then \
		echo You have not specified PROD_DIR_PREFIX >&2; \
		exit 1; \
	fi 
	@if [ 0 = 1 -a "$(PRODUCTS)" = "" ]; then \
		echo You have not specified a destination directory PRODUCTS >&2; \
		exit 1; \
	fi
	@if [ -d $(EUPS_DIR) ]; then \
		echo The destination directory already exists for EUPS_DIR=$(EUPS_DIR). >&2; \
		echo Please remove any old installation of EUPS there first. >&2; \
		exit 1; \
	fi 

	@echo "You will be installing in \$$EUPS_DIR=$$EUPS_DIR"
	@echo "I'll give you 5 seconds to think about it"
	@sleep 5
	@echo ""
	@ mkdir -p $(EUPS_DIR)
	@ mkdir -p $(PROD_DIR_PREFIX)
	@if [ X$(PRODUCTS) != X"" ]; then \
		mkdir -p $(PRODUCTS); \
	else \
		mkdir -p $(PROD_DIR_PREFIX)/ups_db; \
	fi
	@ for f in $(SUBDIRS); do \
		(mkdir $(EUPS_DIR)/$$f; cd $$f ; echo In $$f; $(MAKE) $(MFLAGS) install ); \
	done
	- cp Makefile $(EUPS_DIR)
	- cp README $(EUPS_DIR)
	- cp Release_Notes $(EUPS_DIR)
	- cp gpl.txt $(EUPS_DIR)
	@echo "Remember to source $(EUPS_DIR)/bin/setups.[c]sh"
clean :
	- /bin/rm -f *~ core
	@ for f in $(SUBDIRS); do \
		(cd $$f ; echo In $$f; $(MAKE) $(MFLAGS) clean ); \
	done


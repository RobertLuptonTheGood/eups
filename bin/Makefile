###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh

all :;

install :
	@ ./mksetup $(EUPS_DIR) $(EUPS_PATH) $(SETUP_ALIASES)
	cp Makefile mksetup setups.*sh eups eups_setup eups_setup_impl.py $(EUPS_DIR)/bin
	@ echo Building .pyc files
	@ python -c "import compileall; compileall.compile_dir('$(EUPS_DIR)/bin')"

TAGS :
	etags eups eups_setup *.py

clean :
	- /bin/rm -f *~ core TAGS

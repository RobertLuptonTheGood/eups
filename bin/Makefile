###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh

all :;

install :
	@ ./mksetup $(EUPS_DIR) $(EUPS_PATH) $(SETUP_ALIASES)
	cp Makefile mksetup setups.*sh eups eups_impl.py eups_setup eups_setup_impl.py eupspkg pkgautoversion $(EUPS_DIR)/bin
	@ echo Building .pyc files
	@ $(EUPS_PYTHON) -c "import compileall; compileall.compile_dir('$(EUPS_DIR)/bin')"
# Prevent recompilation by a different python (which can introduce race conditions).
	@ find $(EUPS_DIR)/bin -name "*.pyc" -exec chmod ugo-w {} \;

TAGS :
	etags eups eups_setup *.py

clean :
	- /bin/rm -f *~ core TAGS

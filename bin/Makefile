###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh

all :;

install :
	chmod u+w "$(EUPS_DIR)/bin"
	@ find "$(EUPS_DIR)/bin" -type d -exec chmod u+w {} \;
	@ find "$(EUPS_DIR)/bin" -name "*.pyc" -exec chmod u+w {} \;
	@ ./mksetup "$(EUPS_PYTHON)" "$(EUPS_DIR)" "$(EUPS_PATH)" "$(SETUP_ALIASES)"
	cp Makefile mksetup setups.*sh eups eups_setup eupspkg pkgautoversion "$(EUPS_DIR)/bin"
	@ echo Building .pyc files
	@ "$(EUPS_PYTHON)" -c "import compileall; compileall.compile_dir('$(EUPS_DIR)/bin')"
# Prevent recompilation by a different python (which can introduce race conditions).
	@ find "$(EUPS_DIR)/bin" -name "*.pyc" -exec chmod ugo-w {} \;
	chmod ugo-w "$(EUPS_DIR)/bin"

TAGS :
	etags eups eups_setup *.py

clean :
	- /bin/rm -f *~ core TAGS

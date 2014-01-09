###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh
SYSTEM_PYTHON = $(shell which python)

all :;

install :
	@ ./mksetup $(EUPS_DIR) $(EUPS_PATH) $(SETUP_ALIASES)
	cp Makefile mksetup setups.*sh eups eups_impl.py eups_setup eups_setup_impl.py eupspkg pkgautoversion $(EUPS_DIR)/bin
	@ echo "Forcing eups to use system python"
	@ sed -i 's,\@SYSTEM_PYTHON\@,$(SYSTEM_PYTHON),g' $(EUPS_DIR)/bin/*
	@ echo Building .pyc files
	@ python -c "import compileall; compileall.compile_dir('$(EUPS_DIR)/bin')"

TAGS :
	etags eups eups_setup *.py

clean :
	- /bin/rm -f *~ core TAGS

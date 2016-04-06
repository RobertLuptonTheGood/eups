###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh
PYFILES=eups

all :;

install :
	@ find "$(EUPS_DIR)/bin" -type d -exec chmod u+w {} \;
	@ find "$(EUPS_DIR)/bin" -name "*.pyc" -exec chmod u+w {} \;
	cp -r $(PYFILES) "$(EUPS_DIR)/python"
	@ echo Building .pyc files
	@ "$(EUPS_PYTHON)" -c "import compileall; compileall.compile_dir('$(EUPS_DIR)/python')"
# Prevent recompilation by a different python (which can introduce race conditions).
	@ find "$(EUPS_DIR)/python" -name "*.pyc" -exec chmod ugo-w {} \;
	@ find "$(EUPS_DIR)/python" -type d -exec chmod ugo-w {} \;

TAGS :
	etags *.py

clean :
	- /bin/rm -f *~ core TAGS

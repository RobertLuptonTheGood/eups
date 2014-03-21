###############################################################################
# Sloan Digital Sky Survey (SDSS) -- PHOTO Operations
# N. Padmanabhan, D. Schlegel, & D. Finkbeiner
###############################################################################

SHELL = /bin/sh
PYFILES=eups

all :;

install :
	cp -r $(PYFILES) $(EUPS_DIR)/python
	@ echo Building .pyc files
	@ $(EUPS_PYTHON) -c "import compileall; compileall.compile_dir('$(EUPS_DIR)/python')"
# Prevent recompilation by a different python (which can introduce race conditions).
	@ find $(EUPS_DIR)/python -name "*.pyc" -exec chmod ugo-w {} \;
	chmod ugo-w $(EUPS_DIR)/python

TAGS :
	etags *.py

clean :
	- /bin/rm -f *~ core TAGS

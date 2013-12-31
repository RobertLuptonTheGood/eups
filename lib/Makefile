SHELL = /bin/sh

SUBDIRS=

all :;

install :
	cp bunit.sh eupspkg.sh eupspkg.default "$(EUPS_DIR)/lib"
	@ for f in $(SUBDIRS); do \
		(\
		   if [ ! -d $(EUPS_DIR)/$$f ]; then mkdir $(EUPS_DIR)/lib/$$f; fi; \
		   cd $$f ; \
		   echo In $$f; $(MAKE) $(MFLAGS) install \
                ); \
	done

clean :
	- /bin/rm -f *~ core

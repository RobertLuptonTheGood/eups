SHELL = /bin/sh

SUBDIRS=bash_completion.d

all :;

install :
	cp Makefile ac_eups.m4 "$(EUPS_DIR)/etc"
	@ for f in $(SUBDIRS); do \
		(\
		   if [ ! -d "$(EUPS_DIR)"/$$f ]; then mkdir "$(EUPS_DIR)"/etc/$$f; fi; \
		   cd $$f ; \
		   echo In $$f; $(MAKE) $(MFLAGS) install \
                ); \
	done

clean :
	- /bin/rm -f *~ core

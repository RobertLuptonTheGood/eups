all :
	@: no default actions

install :
	@ \
	EUPS_DB_DIR=`echo $(EUPS_PATH) | sed -e 's/:.*//'`; \
	mkdir -p $$EUPS_DB_DIR/site; \
	for f in startup.py; do \
		if [ -f $$EUPS_DB_DIR/site/$$f ]; then \
			echo "$$EUPS_DB_DIR/site/$$f exists; not overwriting" >&2; \
		else \
			echo cp $$f $$EUPS_DB_DIR/site; \
			cp $$f $$EUPS_DB_DIR/site; \
		fi; \
	done

clean:
	$(RM) *~ core*

distclean: clean
	@: nothing extra to do

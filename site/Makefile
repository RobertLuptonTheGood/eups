all :
	@: no default actions

install :
	@for f in startup.py; do \
		if [ -f $(EUPS_DIR)/site/$$f ]; then \
			echo "$(EUPS_DIR)/site/$$f exists; not overwriting" >&2; \
		else \
			echo cp $$f $(EUPS_DIR)/site; \
			cp $$f $(EUPS_DIR)/site; \
		fi; \
	done

clean:
	$(RM) *~ core*

distclean: clean
	@: nothing extra to do

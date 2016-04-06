SHELL = /bin/sh
LATEXFLAGS = -interaction=nonstopmode

all : doc;

.PHONY : all doc install clean tidy

eups.aux : eups.tex
	@ if ! echo | latex $(LATEXFLAGS) eups.tex; then \
		echo "Could not build eups.aux (ignoring)"; \
	fi

eups.dvi : eups.aux
	@ if ! echo | latex $(LATEXFLAGS) eups.tex; then \
		echo "Could not build eups.dvi (ignoring)"; \
	fi

doc : eups.html eups.pdf;

eups.html : eups.aux
	@ echo "Running latex2html"
	@ if latex2html -dir html -mkdir -noaddress -nonavigation -split 0 eups.tex; then \
		perl -pe 'if(/eups\.css/) { $$_ = "" }; s/eups.html\#/\#/g' html/eups.html > eups.html; \
		$(RM) -r html; \
	else \
		echo "latex2html failed; writing dummy eups.html"; \
		$(RM) eups.html; \
		echo "<HTML>" > eups.html; \
		echo "<TITLE> eups documentation</TITLE>" >> eups.html; \
		echo "<H1><CODE>eups</CODE> documentation</H1>" >> eups.html; \
		echo "We're sorry, but we failed to build the <code>eups</code>" >> eups.html; \
		echo "documentation as we couldn't find <code>latex2html</code>." >> eups.html; \
		echo "The <A HREF=\"$(EUPS_DIR)/doc/eups.pdf\">pdf documentation</A> was built successfully." >> eups.html;\
		echo "</HTML>" >> eups.html; \
	fi

eups.pdf : eups.aux
	@ if ! echo | pdflatex $(LATEXFLAGS) eups.tex; then \
		echo "Could not build eups.pdf (ignoring)"; \
	fi

install : eups.pdf eups.html
	@ if ! cp Makefile *.tex eups.pdf eups.html "$(EUPS_DIR)/doc"; then \
		echo "Not all documentation files copied (ignoring)"; \
	fi

tidy :
	- /bin/rm -rf *~ core eups.{aux,dvi,log,toc}
clean : tidy
	- /bin/rm -rf eups.{html,pdf}

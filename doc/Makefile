SHELL = /bin/sh

all :;

.PHONY : all doc install clean

doc :
	latex2html -dir html -mkdir -noaddress -nonavigation -split 0 eups.tex
	@ perl -pe 'if(/eups\.css/) { $$_ = "" }' html/eups.html > eups.html
	@ $(RM) -r html

install :
	cp Makefile *.tex $(EUPS_DIR)/doc

clean :
	- /bin/rm -rf *~ core eups.html

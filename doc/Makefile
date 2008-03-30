SHELL = /bin/sh

all : doc;

.PHONY : all doc install clean tidy

eups.aux : eups.tex
	latex eups.tex

eups.dvi : eups.aux
	latex eups.tex

doc : eups.html eups.pdf;

eups.html : eups.aux
	@ latex2html -dir html -mkdir -noaddress -nonavigation -split 0 eups.tex
	@ perl -pe 'if(/eups\.css/) { $$_ = "" }; s/eups.html\#/\#/g' html/eups.html > eups.html
	@ $(RM) -r html

eups.pdf : eups.aux
	pdflatex eups.tex

install :
	cp Makefile *.tex $(EUPS_DIR)/doc

tidy :
	- /bin/rm -rf *~ core eups.{aux,dvi,log,toc}
clean : tidy
	- /bin/rm -rf eups.{html,pdf}

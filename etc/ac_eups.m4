dnl
dnl Autoconf macros to configure products that may be known to [e]ups
dnl
dnl After putting
dnl   UPS_WITH_CONFIGURE([cfitsio])
dnl or
dnl  UPS_WITHOUT_CONFIGURE([cfitsio], -lcfitsio, [fitsio.h], [cfitsio,ffopen])
dnl into configure.ac, it should be sufficient to e.g. say
dnl   setup cfitsio
dnl   ./configure
dnl to set the autoconf variables CFITSIO_CFLAGS and CFITSIO_LIBS
dnl
dnl There are macros for products with or without prod-config scripts
dnl

dnl There is also support for setting prefix in a UPSy sort of way.
dnl
dnl The macro UPS_DEFINE_ROOT sets the prefix for a UPS installation,
dnl but only if you say --with-eups=DIR.  More specifically, given
dnl   AC_INIT([product], [X.Y])
dnl   UPS_DEFINE_ROOT(version, flavor)
dnl and
dnl   --with-eups=DIR
dnl are equivalent to
dnl   --prefix=DIR/flavor/product/version
dnl If you don't specify --with-eups, it'll be taken from the first element of EUPS_PATH,
dnl if set
dnl
dnl The version is set based on $1 (which may from dollar-Name: version dollar), or
dnl failing that, from the version given to AC_INIT. If $1 is of the form dollar-Name dollar
dnl but no version is specified, the value of $3 is used (default: cvs)
dnl
dnl The flavor is set based on --with-flavor, $2, eups_flavor, or uname (in that order)
dnl
dnl The variables eups_flavor and eups_version are AC_SUBSTed
dnl
AC_DEFUN([UPS_DEFINE_ROOT], [
	define([eups_product], $PACKAGE_NAME)
	AC_SUBST([[eups_product]], eups_product)

	ifelse($1, ,
	   [AC_MSG_NOTICE([[Using version from ./configure ($PACKAGE_VERSION) in $0]])]
	    [define([eups_version], $PACKAGE_VERSION)],
	    [define([eups_version],
	               $(echo '$1' | perl -pe 'chomp;
		       	      	     	       s/^\$''Name:\s*(\S*)\s*\$/\1/;
		                               if(!$_){$_="ifelse($3, , cvs, $3)"}'))])
	AC_SUBST([[eups_version]], "eups_version")
	AC_MSG_NOTICE([Setting eups version to eups_version])
	AC_ARG_WITH([flavor],
	      [AS_HELP_STRING(--with-flavor=FLAVOR,Use FLAVOR as eups flavor)],
	      eups_flavor="$withval"
	      AC_MSG_NOTICE(Setting flavor to $eups_flavor),
	      eups_flavor="ifelse($2, ,
				        ifelse([$(eups_flavor)], , [$(uname)], [$(eups_flavor)]),
					[$2])"
	                   AC_MSG_NOTICE(Setting flavor to $eups_flavor))
	AC_SUBST(eups_flavor)
	AC_ARG_WITH(eups,
	   [AS_HELP_STRING(--with-eups=DIR,Use DIR as base for installation directories)],
	   [prefix=$withval],
	   [if [[ X"$EUPS_PATH" != X"" ]]; then
	       prefix=$(echo $EUPS_PATH | perl -pe 's/:.*//')
	    fi])
	   if [[ X"$prefix" != X"NONE" ]]; then
	   	   prefix=$prefix/$eups_flavor/eups_product/$(echo eups_version | perl -pe 's/\./_/g')
		   AC_MSG_NOTICE(Setting \$prefix to $prefix)
	   fi
   ])
dnl
dnl Define extra installation directories (not expanding $prefix)
dnl
AC_DEFUN([UPS_INSTALL_DIRS], [
   AC_SUBST(m4dir, '${prefix}/m4')
   AC_SUBST(pythondir, '${prefix}/python')
   AC_SUBST(swigdir, '${prefix}/swig')
   AC_SUBST(srcinstalldir, '${prefix}/src')
   AC_SUBST(testdir, '${prefix}/test')
   AC_SUBST(upsdir, '${prefix}/ups')
   AC_SUBST(xmldir, '${prefix}/xml')
   ])

dnl -------------------------------------------------------------------------
dnl
dnl Configure a product "prod" (== $1), AC_SUBSTing PROD_CFLAGS and PROD_LIBS
dnl
dnl Prod's location may be specified (in order of decreasing priority) by:
dnl     --with-prod=DIR			Location of prod-config
dnl     --with-prod-config=FILE		Name of prod-config file
dnl    eups				(i.e. a $PROD_DIR directory)
dnl    prod-config somewhere in $PATH
dnl
dnl If the product comes from eups, then the path will be specified in
dnl terms of $PROD_DIR.  If it doesn't, then it can be declared to eups
dnl by running bin/eups_import (the directory is guessed from the CFLAGS)
dnl this is done by AC_SUBSTing eups_import_products and eups_import_directories
dnl
AC_DEFUN([UPS_WITH_CONFIGURE],[
	define([ac_eups_prod], ifelse([$1], [], [AC_FATAL([Please specify a product name to $0])], $1))
	define([ac_eups_PROD], translit(ac_eups_prod, a-z, A-Z))
	ac_eups_PROD[]_FROM_UPS=0
	AC_ARG_WITH(ac_eups_prod,
	    [AS_HELP_STRING(--with-ac_eups_prod=DIR, Specify location of ac_eups_prod-config script)],
	    [ac_eups_PROD[]_CONFIG=$withval/ac_eups_prod-config],
	    [AC_ARG_WITH(ac_eups_prod-config,
	        [AS_HELP_STRING(--with-ac_eups_prod-config=FILE, Specify ac_eups_prod-config script)],
	    	[ac_eups_PROD[]_CONFIG=[$]withval],
		[if test "[$]ac_eups_PROD[]_DIR" != ""; then
		   ac_eups_PROD[]_FROM_UPS=1
		   ac_eups_PROD[]_CONFIG="[$]ac_eups_PROD[]_DIR/bin/ac_eups_prod-config"
		else
		   ac_eups_PROD[]_CONFIG=$(which ac_eups_prod-config)
	   	fi])])
	
	if test -z $ac_eups_PROD[]_CONFIG; then
	   AC_MSG_ERROR([Cannot find ac_eups_prod; setup ac_eups_prod or try --with-ac_eups_prod])
	fi
	AC_CHECK_FILE([$]ac_eups_PROD[]_CONFIG,[],
		[AC_MSG_ERROR([Cannot find ac_eups_prod; setup ac_eups_prod or use --with-ac_eups_prod])])
	
	ac_eups_PROD[]_CFLAGS="$([$]{ac_eups_PROD[]_CONFIG} --cflags)"
	ac_eups_PROD[]_LIBS="$([$]{ac_eups_PROD[]_CONFIG} --libs)"
	
	if test $ac_eups_PROD[]_FROM_UPS = 1; then
	   ac_eups_PROD[]_CFLAGS=$(echo $ac_eups_PROD[]_CFLAGS | sed -e "s|$ac_eups_PROD[]_DIR|\\\${ac_eups_PROD[]_DIR}|g")
	   ac_eups_PROD[]_LIBS=$(echo $ac_eups_PROD[]_LIBS | sed -e "s|$ac_eups_PROD[]_DIR|\\\${ac_eups_PROD[]_DIR}|g")
	else
	   ac_eups_dir=$(echo $ac_eups_PROD[]_CFLAGS | perl -pe 's,^\s*-I(\S+).*,[$]1,; s,/include,,')
	   AC_MSG_NOTICE(Guessing that \$ac_eups_PROD[]_DIR is $ac_eups_dir)
	   if test "$ac_eups_dir" != ""; then
	      eups_import_products="$eups_import_products ac_eups_prod"
	      AC_SUBST([eups_import_products])

	      eups_import_directories="$eups_import_directories $ac_eups_dir"
	      AC_SUBST([eups_import_directories])

	      unset ac_eups_dir
	   fi
	fi
		
	AC_SUBST(ac_eups_PROD[]_CFLAGS)
	AC_SUBST(ac_eups_PROD[]_LIBS)

	CFLAGS="$CFLAGS $(eval echo $ac_eups_PROD[]_CFLAGS)"
	LIBS="$LIBS $(eval echo $ac_eups_PROD[]_LIBS)"

	undefine([ac_eups_prod])
	undefine([ac_eups_PROD])])[]dnl

dnl
dnl Configure a product "prod" (== $1), AC_SUBSTing PROD_CFLAGS and PROD_LIBS
dnl
dnl Prod's location may be specified (in order of decreasing priority) by:
dnl     --with-prod=DIR         Location of prod-config
dnl    eups			(i.e. a $PROD_DIR directory)
dnl
dnl Check for header $2, use libraries $3; library:symbol $4; e.g.
dnl   UPS_WITHOUT_CONFIGURE([fftw], [fftw3.h], -lfftw3f, [fftw3f,fftwf_plan_dft_2d])
dnl to configure a eups product fftw, using FFTW_DIR
dnl
dnl If the product comes from eups, then the path will be specified in
dnl terms of $PROD_DIR.  If it doesn't, then it can be declared to eups
dnl by running bin/eups_import; this is done by AC_SUBSTing
dnl eups_import_products and eups_import_directories
dnl
AC_DEFUN([UPS_WITHOUT_CONFIGURE], [
	define([ac_eups_prod], ifelse([$1], [], [AC_FATAL([Please specify a product name to $0])], $1))
	define([ac_eups_PROD], translit(ac_eups_prod, a-z, A-Z))
	ac_eups_PROD[]_FROM_UPS=0
	AC_ARG_WITH(ac_eups_prod,
	   [AS_HELP_STRING(--with-ac_eups_prod=DIR, Specify location of ac_eups_PROD[])],
	   [ac_eups_PROD[]_CFLAGS="-I$withval/include"
	    ac_eups_PROD[]_LIBS="-L$withval/lib"
	    ac_eups_dir=$withval],
	   [if test "$ac_eups_PROD[]_DIR" != ""; then
	      ac_eups_PROD[]_FROM_UPS=1
	      ac_eups_PROD[]_CFLAGS="-I$ac_eups_PROD[]_DIR/include"
	      ac_eups_PROD[]_LIBS="-L$ac_eups_PROD[]_DIR/lib"
	   fi])
	ifelse([$3], [], [], [ac_eups_PROD[]_LIBS="$ac_eups_PROD[]_LIBS $3"])
	
	dnl Save CPPFLAGS/CFLAGS/LDFLAGS so that they can be restored after tests
	TMP_CPPFLAGS=${CPPFLAGS}
	TMP_CFLAGS=${CFLAGS}
	TMP_LDFLAGS=${LDFLAGS}
	
	CFLAGS="${TMP_CFLAGS} ${ac_eups_PROD[]_CFLAGS}"
	CPPFLAGS="${CFLAGS}"
	LDFLAGS="${TMP_LDFLAGS} ${ac_eups_PROD[]_LIBS}"

	ifelse([$2], [], [], [
	   AC_CHECK_HEADERS([$2],[],
	    [AC_MSG_ERROR([Failed to find ac_eups_prod; setup ac_eups_prod or use --with-ac_eups_prod to specify location.])]
	)])

	ifelse([$4], [], [], [
	   TMP_LIBS=${LIBS}
	   AC_CHECK_LIB($4,[],
	     [AC_MSG_ERROR([Failed to find ac_eups_prod; use --with-ac_eups_prod to specify location.])]
	)])
	LIBS=${TMP_LIBS}
	
	dnl restore the CPPFLAGS/CFLAGS/LDFLAGS
	CPPFLAGS=${TMP_CPPFLAGS}
	CFLAGS=${TMP_CFLAGS}
	LDFLAGS=${TMP_LDFLAGS}
	
	if test $ac_eups_PROD[]_FROM_UPS = 1; then
	   ac_eups_PROD[]_CFLAGS=$(echo $ac_eups_PROD[]_CFLAGS | sed -e "s|$ac_eups_PROD[]_DIR|\\\${ac_eups_PROD[]_DIR}|g")
	   ac_eups_PROD[]_LIBS=$(echo $ac_eups_PROD[]_LIBS | sed -e "s|$ac_eups_PROD[]_DIR|\\\${ac_eups_PROD[]_DIR}|g")
	elif test "$ac_eups_dir" != ""; then
	   eups_import_products="$eups_import_products ac_eups_prod"
	   AC_SUBST([eups_import_products])

	   eups_import_directories="$eups_import_directories $ac_eups_dir"
	   AC_SUBST([eups_import_directories])

	   unset ac_eups_dir
	fi
	
	AC_SUBST(ac_eups_PROD[]_CFLAGS)
	AC_SUBST(ac_eups_PROD[]_LIBS)

	CFLAGS="$CFLAGS $(eval echo $ac_eups_PROD[]_CFLAGS)"
	LIBS="$LIBS $(eval echo $ac_eups_PROD[]_LIBS)"

	undefine([ac_eups_prod])
	undefine([ac_eups_PROD])])

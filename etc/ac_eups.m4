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
dnl but only if you say --with-ups=DIR.  More specifically, given
dnl   AC_INIT([product], [X.Y])
dnl   UPS_DEFINE_ROOT(version, flavor)
dnl and
dnl   --with-ups=DIR
dnl are equivalent to
dnl   --prefix=DIR/flavor/product/version
dnl
dnl The version is set based on $1 (which may from dollar-Name: version dollar), or
dnl failing that, from the version given to AC_INIT. If $1 is of the form dollar-Name dollar
dnl but no version is specified, the value of $3 is used (default: cvs)
dnl
dnl The flavor is set based on --with-flavor, $2, or uname (in that order)
dnl
dnl The variables ups_flavor and ups_version are AC_SUBSTed
dnl
AC_DEFUN([UPS_DEFINE_ROOT], [
	define([ups_product], $PACKAGE_NAME)
	AC_SUBST([[ups_product]], ups_product)

	ifelse($1, ,
	   [AC_MSG_NOTICE([[Using version from ./configure ($PACKAGE_VERSION) in $0]])]
	    [define([ups_version], $PACKAGE_VERSION)],
	    [define([ups_version],
	               $(echo '$1' | perl -pe 'chomp;
		       	      	     	       s/^\$''Name:\s*(\S*)\s*\$/\1/;
		                               if(!$_){$_="ifelse($3, , cvs, $3)"}'))])
	AC_SUBST([[ups_version]], "ups_version")
	AC_MSG_NOTICE([Setting ups version to ups_version])
	AC_ARG_WITH([flavor],
	      [AS_HELP_STRING(--with-flavor=FLAVOR,Use FLAVOR as ups flavor)],
	      ups_flavor="$withval"
	      AC_MSG_NOTICE(Setting flavor to $ups_flavor),
	      ups_flavor="ifelse($2, , [$(uname)], [$2])")
	AC_SUBST(ups_flavor)
	AC_ARG_WITH(ups,
	   [AS_HELP_STRING(--with-ups=DIR,Use DIR as base for installation directories)],
	   [prefix=$withval/$ups_flavor/ups_product/$(echo ups_version | perl -pe 's/\./_/g')]
	   AC_MSG_NOTICE(Setting \$prefix to $prefix))
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
dnl    ups				(i.e. a $PROD_DIR directory)
dnl    prod-config somewhere in $PATH
dnl
dnl If the product comes from ups, then the path will be specified in
dnl terms of $PROD_DIR.  If it doesn't, then it can be declared to ups
dnl by running bin/eups_import (the directory is guessed from the CFLAGS)
dnl this is done by AC_SUBSTing ups_import_products and ups_import_directories
dnl
AC_DEFUN([UPS_WITH_CONFIGURE],[
	define([ac_ups_prod], ifelse([$1], [], [AC_FATAL([Please specify a product name to $0])], $1))
	define([ac_ups_PROD], translit(ac_ups_prod, a-z, A-Z))
	ac_ups_PROD[]_FROM_UPS=0
	AC_ARG_WITH(ac_ups_prod,
	    [AS_HELP_STRING(--with-ac_ups_prod=DIR, Specify location of ac_ups_prod-config script)],
	    [ac_ups_PROD[]_CONFIG=$withval/ac_ups_prod-config],
	    [AC_ARG_WITH(ac_ups_prod-config,
	        [AS_HELP_STRING(--with-ac_ups_prod-config=FILE, Specify ac_ups_prod-config script)],
	    	[ac_ups_PROD[]_CONFIG=[$]withval],
		[if test "[$]ac_ups_PROD[]_DIR" != ""; then
		   ac_ups_PROD[]_FROM_UPS=1
		   ac_ups_PROD[]_CONFIG="[$]ac_ups_PROD[]_DIR/bin/ac_ups_prod-config"
		else
		   ac_ups_PROD[]_CONFIG=$(which ac_ups_prod-config)
	   	fi])])
	
	if test -z $ac_ups_PROD[]_CONFIG; then
	   AC_MSG_ERROR([Cannot find ac_ups_prod; setup ac_ups_prod or try --with-ac_ups_prod])
	fi
	AC_CHECK_FILE([$]ac_ups_PROD[]_CONFIG,[],
		[AC_MSG_ERROR([Cannot find ac_ups_prod; setup ac_ups_prod or use --with-ac_ups_prod])])
	
	ac_ups_PROD[]_CFLAGS="$([$]{ac_ups_PROD[]_CONFIG} --cflags)"
	ac_ups_PROD[]_LIBS="$([$]{ac_ups_PROD[]_CONFIG} --libs)"
	
	if test $ac_ups_PROD[]_FROM_UPS = 1; then
	   ac_ups_PROD[]_CFLAGS=$(echo $ac_ups_PROD[]_CFLAGS | sed -e "s|$ac_ups_PROD[]_DIR|\\\${ac_ups_PROD[]_DIR}|g")
	   ac_ups_PROD[]_LIBS=$(echo $ac_ups_PROD[]_LIBS | sed -e "s|$ac_ups_PROD[]_DIR|\\\${ac_ups_PROD[]_DIR}|g")
	else
	   ac_ups_dir=$(echo $ac_ups_PROD[]_CFLAGS | perl -pe 's,^\s*-I(\S+).*,[$]1,; s,/include,,')
	   AC_MSG_NOTICE(Guessing that \$ac_ups_PROD[]_DIR is $ac_ups_dir)
	   if test "$ac_ups_dir" != ""; then
	      ups_import_products="$ups_import_products ac_ups_prod"
	      AC_SUBST([ups_import_products])

	      ups_import_directories="$ups_import_directories $ac_ups_dir"
	      AC_SUBST([ups_import_directories])

	      unset ac_ups_dir
	   fi
	fi
		
	AC_SUBST(ac_ups_PROD[]_CFLAGS)
	AC_SUBST(ac_ups_PROD[]_LIBS)
	undefine([ac_ups_prod])
	undefine([ac_ups_PROD])])[]dnl

dnl
dnl Configure a product "prod" (== $1), AC_SUBSTing PROD_CFLAGS and PROD_LIBS
dnl
dnl Prod's location may be specified (in order of decreasing priority) by:
dnl     --with-prod=DIR         Location of prod-config
dnl    ups			(i.e. a $PROD_DIR directory)
dnl
dnl Check for header $2, use libraries $3; library:symbol $4; e.g.
dnl   UPS_WITHOUT_CONFIGURE([fftw], [fftw3.h], -lfftw3f, [fftw3f,fftwf_plan_dft_2d])
dnl to configure a ups product fftw, using FFTW_DIR
dnl
dnl If the product comes from ups, then the path will be specified in
dnl terms of $PROD_DIR.  If it doesn't, then it can be declared to ups
dnl by running bin/eups_import; this is done by AC_SUBSTing
dnl ups_import_products and ups_import_directories
dnl
AC_DEFUN([UPS_WITHOUT_CONFIGURE], [
	define([ac_ups_prod], ifelse([$1], [], [AC_FATAL([Please specify a product name to $0])], $1))
	define([ac_ups_PROD], translit(ac_ups_prod, a-z, A-Z))
	ac_ups_PROD[]_FROM_UPS=0
	AC_ARG_WITH(ac_ups_prod,
	   [AS_HELP_STRING(--with-ac_ups_prod=DIR, Specify location of ac_ups_PROD[])],
	   [ac_ups_PROD[]_CFLAGS="-I$withval/include"
	    ac_ups_PROD[]_LIBS="-L$withval/lib"
	    ac_ups_dir=$withval],
	   [if test "$ac_ups_PROD[]_DIR" != ""; then
	      ac_ups_PROD[]_FROM_UPS=1
	      ac_ups_PROD[]_CFLAGS="-I$ac_ups_PROD[]_DIR/include"
	      ac_ups_PROD[]_LIBS="-L$ac_ups_PROD[]_DIR/lib"
	   fi])
	ifelse([$3], [], [], [ac_ups_PROD[]_LIBS="$ac_ups_PROD[]_LIBS $3"])
	
	dnl Save CPPFLAGS/CFLAGS/LDFLAGS so that they can be restored after tests
	TMP_CPPFLAGS=${CPPFLAGS}
	TMP_CFLAGS=${CFLAGS}
	TMP_LDFLAGS=${LDFLAGS}
	
	CFLAGS="${TMP_CFLAGS} ${ac_ups_PROD[]_CFLAGS}"
	CPPFLAGS="${CFLAGS}"
	LDFLAGS="${TMP_LDFLAGS} ${ac_ups_PROD[]_LIBS}"

	ifelse([$2], [], [], [
	   AC_CHECK_HEADERS([$2],[],
	    [AC_MSG_ERROR([Failed to find ac_ups_prod; setup ac_ups_prod or use --with-ac_ups_prod to specify location.])]
	)])

	ifelse([$4], [], [], [
	   TMP_LIBS=${LIBS}
	   AC_CHECK_LIB($4,[],
	     [AC_MSG_ERROR([Failed to find ac_ups_prod; use --with-ac_ups_prod to specify location.])]
	)])
	LIBS=${TMP_LIBS}
	
	dnl restore the CPPFLAGS/CFLAGS/LDFLAGS
	CPPFLAGS=${TMP_CPPFLAGS}
	CFLAGS=${TMP_CFLAGS}
	LDFLAGS=${TMP_LDFLAGS}
	
	if test $ac_ups_PROD[]_FROM_UPS = 1; then
	   ac_ups_PROD[]_CFLAGS=$(echo $ac_ups_PROD[]_CFLAGS | sed -e "s|$ac_ups_PROD[]_DIR|\\\${ac_ups_PROD[]_DIR}|g")
	   ac_ups_PROD[]_LIBS=$(echo $ac_ups_PROD[]_LIBS | sed -e "s|$ac_ups_PROD[]_DIR|\\\${ac_ups_PROD[]_DIR}|g")
	elif test "$ac_ups_dir" != ""; then
	   ups_import_products="$ups_import_products ac_ups_prod"
	   AC_SUBST([ups_import_products])

	   ups_import_directories="$ups_import_directories $ac_ups_dir"
	   AC_SUBST([ups_import_directories])

	   unset ac_ups_dir
	fi
	
	AC_SUBST(ac_ups_PROD[]_CFLAGS)
	AC_SUBST(ac_ups_PROD[]_LIBS)
	undefine([ac_ups_prod])
	undefine([ac_ups_PROD])])

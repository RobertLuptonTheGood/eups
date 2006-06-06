dnl
dnl Autoconf macros to configure products that may be known to [e]ups
dnl
dnl It should be sufficient to e.g. say
dnl   setup cfitsio
dnl   ./configure
dnl to set the autoconf variables CFITSIO_CFLAGS and CFITSIO_LIBS
dnl
dnl There are macros for products with oe without prod-config scripts
dnl
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
dnl terms of $PROD_DIR
dnl
m4_define(UPS_WITH_CONFIGURE,[
	m4_define([ac_ups_prod], ifelse([$1], [], [AC_FATAL([Please specify a product name to $0])], $1))
	m4_define([ac_ups_PROD], translit(ac_ups_prod, a-z, A-Z))
	ac_ups_PROD[]_FROM_UPS=0
	AC_ARG_WITH(ac_ups_prod,
	    [AS_HELP_STRING(--with-ac_ups_prod=DIR, Specify location of ac_ups_prod-config script)],
	    [ac_ups_PROD[]_CONFIG=$withval/bin/ac_ups_prod-config],
	    [AC_ARG_WITH(ac_ups_prod-config,
	        [AS_HELP_STRING(--with-ac_ups_prod-config=FILE, Specify ac_ups_prod-config script)],
	    	[ac_ups_PROD[]_CONFIG=[$]withval],
		[if test -n [$]ac_ups_PROD[]_DIR; then
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
	
	if test $ac_ups_PROD[]_FROM_UPS; then
	   ac_ups_PROD[]_CFLAGS=$(echo $ac_ups_PROD[]_CFLAGS | sed -e "s|$ac_ups_PROD[]_DIR|\\\$\(ac_ups_PROD[]_DIR\)|g")
	   ac_ups_PROD[]_LIBS=$(echo $ac_ups_PROD[]_LIBS | sed -e "s|$ac_ups_PROD[]_DIR|\\\$\(ac_ups_PROD[]_DIR\)|g")
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
dnl    ups			(i.e. a $PKG_DIR directory)
dnl
dnl If the product comes from ups, then the path will be specified in
dnl terms of $PKG_DIR
dnl
dnl Use libraries $2; check for header $3, library:symbol $4; e.g.
dnl   UPS_WITHOUT_CONFIGURE([fftw], -lfftw3f -lfftw3, [fftw3.h], [fftw3f,fftwf_plan_dft_2d])
dnl to configure a ups product fftw, using FFTW_DIR
dnl
define([UPS_WITHOUT_CONFIGURE], [
	m4_define([ac_ups_prod], ifelse([$1], [], [AC_FATAL([Please specify a product name to $0])], $1))
	m4_define([ac_ups_PROD], translit(ac_ups_prod, a-z, A-Z))
	ac_ups_PROD[]_FROM_UPS=0
	AC_ARG_WITH(ac_ups_prod,
	   [AS_HELP_STRING(--with-ac_ups_prod=DIR, Specify location of ac_ups_PROD[])],
	   [ac_ups_PROD[]_CFLAGS="-I$withval/include"
	    ac_ups_PROD[]_LIBS="-L$withval/lib"],
	   [if test -n $ac_ups_PROD[]_DIR; then
	      ac_ups_PROD[]_FROM_UPS=1
	      ac_ups_PROD[]_CFLAGS="-I$ac_ups_PROD[]_DIR/include"
	      ac_ups_PROD[]_LIBS="-L$ac_ups_PROD[]_DIR/lib"
	   fi])
	ifelse([$2], [], [], [ac_ups_PROD[]_LIBS="$ac_ups_PROD[]_LIBS $2"])
	
	dnl Save CFLAGS/LDFLAGS so that they can be restored after tests
	TMP_CFLAGS=${CFLAGS}
	TMP_LDFLAGS=${LDFLAGS}
	
	CFLAGS="${TMP_CFLAGS} ${ac_ups_PROD[]_CFLAGS}"
	LDFLAGS="${TMP_LDFLAGS} ${ac_ups_PROD[]_LIBS}"

	ifelse([$3], [], [], [
	   AC_CHECK_HEADERS([$3],[],
	    [AC_MSG_ERROR([Failed to find ac_ups_prod; setup ac_ups_prod or use --with-ac_ups_prod to specify location.])]
	)])
	ifelse([$4], [], [], [
	   TMP_LIBS=${LIBS}
	   AC_CHECK_LIB($4,[],
	     [AC_MSG_ERROR([Failed to find ac_ups_prod; use --with-ac_ups_prod to specify location.])]
	)])
	LIBS=${TMP_LIBS}
	
	dnl restore the CFLAGS/LDFLAGS
	CFLAGS=${TMP_CFLAGS}
	LDFLAGS=${TMP_LDFLAGS}
	
	if test $ac_ups_PROD[]_FROM_UPS; then
	   ac_ups_PROD[]_CFLAGS=$(echo $ac_ups_PROD[]_CFLAGS | sed -e "s|$ac_ups_PROD[]_DIR|\\\$(ac_ups_PROD[]_DIR)|g")
	   ac_ups_PROD[]_LIBS=$(echo $ac_ups_PROD[]_LIBS | sed -e "s|$ac_ups_PROD[]_DIR|\\\$(ac_ups_PROD[]_DIR)|g")
	fi
	
	AC_SUBST(ac_ups_PROD[]_CFLAGS)
	AC_SUBST(ac_ups_PROD[]_LIBS)
	undefine([ac_ups_prod])
	undefine([ac_ups_PROD])])
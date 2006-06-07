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
dnl The version is set based on $1 (which may come from dollar-Name:version dollar), or
dnl failing that, from the version given to AC_INIT
dnl
dnl The flavor is set based on --with-flavor, $2, or uname (in that order)
dnl
dnl The variables ups_flavor and ups_version are AC_SUBSTed
dnl
m4_define(UPS_DEFINE_ROOT, [
	m4_define([ups_product], $PACKAGE_NAME)
	AC_SUBST([[ups_product]], ups_product)
	ifelse($1, ,
	   [AC_MSG_NOTICE([[Using version from ./configure ($PACKAGE_VERSION) in $0]])]
	    [m4_define([ups_version], $PACKAGE_VERSION)],
	    [m4_define([ups_version],
	               $(echo '$1' | perl -pe 'chomp; s/^\$''Name:\s*(\S*)\$/\1/; if(!$_){$_="cvs"}'))])
	AC_SUBST([[ups_version]], "ups_version")
	AC_ARG_WITH(flavor,
	      [AS_HELP_STRING(--with-flavor=FLAVOR,Use FLAVOR as ups flavor)],
	      m4_define([ups_flavor], $withval),
	      m4_define([ups_flavor], ifelse($2, , [$(uname)], [$2])))
	AC_SUBST([[ups_flavor]], "ups_flavor")
	AC_ARG_WITH(ups,
	   [AS_HELP_STRING(--with-ups=DIR,Use DIR as base for installation directories)],
	   [prefix=$withval/ups_flavor/ups_product/$(echo ups_version | perl -pe 's/\./_/g')]
	   AC_MSG_NOTICE(Setting prefix to $prefix))
   ])
dnl
dnl Define extra installation directories (not expanding $prefix)
dnl
m4_define([UPS_INSTALL_DIRS], [
   AC_SUBST(pythondir, '${prefix}/python')
   AC_SUBST(swigdir, '${prefix}/swig')
   AC_SUBST(srcinstalldir, '${prefix}/src')
   AC_SUBST(testdir, '${prefix}/test')
   AC_SUBST(upsdir, '${prefix}/ups')
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
m4_define(UPS_WITH_CONFIGURE,[
	m4_define([ac_ups_prod], ifelse([$1], [], [AC_FATAL([Please specify a product name to $0])], $1))
	m4_define([ac_ups_PROD], translit(ac_ups_prod, a-z, A-Z))
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
	   ac_ups_PROD[]_CFLAGS=$(echo $ac_ups_PROD[]_CFLAGS | sed -e "s|$ac_ups_PROD[]_DIR|\\\$\(ac_ups_PROD[]_DIR\)|g")
	   ac_ups_PROD[]_LIBS=$(echo $ac_ups_PROD[]_LIBS | sed -e "s|$ac_ups_PROD[]_DIR|\\\$\(ac_ups_PROD[]_DIR\)|g")
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
dnl Use libraries $2; check for header $3, library:symbol $4; e.g.
dnl   UPS_WITHOUT_CONFIGURE([fftw], -lfftw3f -lfftw3, [fftw3.h], [fftw3f,fftwf_plan_dft_2d])
dnl to configure a ups product fftw, using FFTW_DIR
dnl
dnl If the product comes from ups, then the path will be specified in
dnl terms of $PROD_DIR.  If it doesn't, then it can be declared to ups
dnl by running bin/eups_import; this is done by AC_SUBSTing
dnl ups_import_products and ups_import_directories
dnl
define([UPS_WITHOUT_CONFIGURE], [
	m4_define([ac_ups_prod], ifelse([$1], [], [AC_FATAL([Please specify a product name to $0])], $1))
	m4_define([ac_ups_PROD], translit(ac_ups_prod, a-z, A-Z))
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
	
	if test $ac_ups_PROD[]_FROM_UPS = 1; then
	   ac_ups_PROD[]_CFLAGS=$(echo $ac_ups_PROD[]_CFLAGS | sed -e "s|$ac_ups_PROD[]_DIR|\\\$(ac_ups_PROD[]_DIR)|g")
	   ac_ups_PROD[]_LIBS=$(echo $ac_ups_PROD[]_LIBS | sed -e "s|$ac_ups_PROD[]_DIR|\\\$(ac_ups_PROD[]_DIR)|g")
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

dnl -----------------------------------------------
dnl
dnl Done with ups macros.  Now some more to support
dnl shareable libraries, python, and swig
dnl

dnl
dnl RHL does not believe that the added complexity of libtool, e.g.
dnl   libtool --mode=execute gdb foo
dnl is warranted, especially since we're using ups to set e.g. LD_LIBRARY_PATH,
dnl so we'll set the variables by hand
dnl

m4_define(RHL_DYNAMIC_LIBS, [
   rhl_uname=$(uname)

   AC_MSG_NOTICE([Setting up shareable libraries for] $rhl_uname)
   if [[ $rhl_uname = "Darwin" ]]; then
      AC_SUBST(SO_LDFLAGS, ["-bundle -undefined suppress -flat_namespace"])
      AC_SUBST(SO, [so])
      AC_SUBST(DYLIB_LDFLAGS, ["-undefined suppress -flat_namespace -dynamiclib"])
      AC_SUBST(DYLIB, [dylib])
      CFLAGS="$CFLAGS -fPIC"
   elif [[ $rhl_uname = "Linux" ]]; then
      AC_SUBST(SO_LDFLAGS, ["-shared"])
      AC_SUBST(SO, [so])
      AC_SUBST(DYLIB_LDFLAGS, ["-shared"])
      AC_SUBST(DYLIB, [so])
     CFLAGS="$CFLAGS -fPIC"
   else
      AC_MSG_ERROR(Unknown O/S for setting up dynamic libraries: rhl_uname)
   fi
])

dnl
dnl Detect python and add appropriate flags to PYTHON_CFLAGS/PYTHON_LIBS
dnl
m4_define(RHL_FIND_PYTHON, [
   AC_ARG_WITH(python,
     [AS_HELP_STRING(--with-python=file,Specify name of python executable.)],
     [PYTHON="$withval"
     if [[ ! -x $PYTHON ]]; then
        PYTHON=""
     fi],
     AC_CHECK_PROG(PYTHON, python, python, ""))

   if [[ "$PYTHON" = "" ]]; then
      AC_MSG_FAILURE([You'll need python; try using --with-python=file.])
   fi

   PYTHON_INCDIR=$($PYTHON -c 'import distutils.sysconfig as ds; print ds.get_python_inc()')
   AC_SUBST(PYTHON_CFLAGS, [-I$PYTHON_INCDIR])
   AC_SUBST(PYTHON_LIBS, [])
])

dnl
dnl Detect numpy and add appropriate flags to PYTHON_CFLAGS/PYTHON_LIBS
dnl If $1 is defined, add it to PYTHON_CFLAGS -- e.g. RHL_FIND_NUMPY([-DUSE_NUMPY=1])
dnl

m4_define(RHL_FIND_NUMPY, [
   AC_ARG_ENABLE(numpy,
       [AS_HELP_STRING(--enable-numpy, Generate numpy code)])

   if [[ "$enable_numpy" = "" -o "$enable_numpy" = "yes" ]]; then
       AC_MSG_CHECKING([numpy])
       NUMPY_INCDIR=$($PYTHON -c 'import numpy; print numpy.get_numpy_include()')
       if [[ $? != 0 ]]; then
          AC_MSG_RESULT([no])
          AC_MSG_WARN([Failed to find numpy; ignoring --enable-numpy])
       else
          AC_MSG_RESULT([ok])
          PYTHON_CFLAGS="$PYTHON_CFLAGS -I$NUMPY_INCDIR"
	  ifelse($1, , ,
             [PYTHON_CFLAGS="$PYTHON_CFLAGS $1"])
       fi
   fi
])

dnl ------------------- swig ---------------------
dnl
dnl Detect swig, possibly via --with-swig
dnl If you provide an argument such as 1.3.27, you'll be warned if the
dnl version found is older than the specified version.  If $2 is defined,
dnl an error is generated
dnl
m4_define(RHL_SWIG, [
   AC_ARG_WITH(swig,
     [AS_HELP_STRING(--with-swig=DIR,Specify location of SWIG executable.)],
     [SWIG="$withval/swig"
     if [[ ! -x $SWIG ]]; then
        SWIG=""
     fi],
     AC_CHECK_PROG(SWIG, swig, swig, ""))

   if [[ "$SWIG" != "" ]]; then
      [SWIG="$SWIG -w301,451 -python -Drestrict= -Dinline="]
   else
      AC_MSG_FAILURE([You'll need swig; try using --with-swig=DIR to specify its location.])
   fi

   ifelse($1, , , [
   swig_version=$($SWIG -version 2>&1 | perl -ne 'if(/^SWIG Version (\d)\.(\d)\.(\d+)/) { print 100000*[$]1 + 1000*[$]2 + [$]3; }')
   desired_swig_version=$(echo $1 | perl -ne 'if(/^(\d)\.(\d)\.(\d+)/) { print 100000*[$]1 + 1000*[$]2 + [$]3; }')

   if [[ "$swig_version" = "" -o $swig_version -lt $desired_swig_version ]]; then
      ifelse($2, ,
	      AC_MSG_NOTICE([You would be better off with a swig version >= $1]),
	      AC_MSG_ERROR([Please provide a swig version >= $1]))
   fi
   unset swig_version; unset desired_swig_version])
])

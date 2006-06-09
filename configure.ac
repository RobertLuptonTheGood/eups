AC_INIT([eups], [X.Y], [rhl@astro.princeton.edu])
dnl
dnl Installation directories
dnl
AC_ARG_WITH(ups,
   [AS_HELP_STRING(--with-ups=DIR, Use DIR as root for installed products)],
   [PROD_DIR_PREFIX=$withval],
   [PROD_DIR_PREFIX=\${prefix}/share])
AC_SUBST(PROD_DIR_PREFIX)

AC_ARG_WITH(ups_db,
   [AS_HELP_STRING(--with-ups_db=DIR, Use DIR as the UPS database directory)],
   [PRODUCTS=$withval],
   [PRODUCTS=\${PROD_DIR_PREFIX}/ups_db])
AC_SUBST(PRODUCTS)

AC_ARG_WITH(eups_dir,
   [AS_HELP_STRING(--with-eups_dir=DIR, [Install eups into DIR/{bin,doc}])],
   [EUPS_DIR=$withval],
   [EUPS_DIR=\${PROD_DIR_PREFIX}/eups])
AC_SUBST(EUPS_DIR)
dnl
dnl Output
dnl
AC_CONFIG_FILES([Makefile])
AC_OUTPUT

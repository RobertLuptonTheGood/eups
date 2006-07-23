AC_INIT([eups], [X.Y], [rhl@astro.princeton.edu])
dnl
dnl Installation directories
dnl
AC_ARG_WITH(ups,
   [AS_HELP_STRING(--with-ups=DIR, [Use DIR as root for installed products (EUPS_PATH)])],
   [EUPS_PATH=$withval],
   [EUPS_PATH=\${prefix}/share])
AC_SUBST(EUPS_PATH)

AC_ARG_WITH(eups_dir,
   [AS_HELP_STRING(--with-eups_dir=DIR, [Install eups into DIR/{bin,doc}])],
   [EUPS_DIR=$withval],
   [EUPS_DIR=\${EUPS_PATH}/eups])
AC_SUBST(EUPS_DIR)
dnl
dnl Output
dnl
AC_CONFIG_FILES([Makefile])
AC_OUTPUT

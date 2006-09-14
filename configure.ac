AC_INIT([eups], [X.Y], [rhl@astro.princeton.edu])
dnl
dnl Protect against typos
dnl
AC_ARG_WITH(ups,
   [AS_HELP_STRING(--with-ups=DIR, [Typo for --with-eups=DIR])],
   AC_MSG_ERROR([Please use --with-eups]))   
AC_ARG_WITH(ups_dir,
   [AS_HELP_STRING(--with-ups_dir=DIR, [Typo for --with-eups_dir=DIR])],
   AC_MSG_ERROR([Please use --with-eups_dir]))
dnl
dnl Installation directories
dnl
AC_ARG_WITH(eups,
   [AS_HELP_STRING(--with-eups=DIR, [Use DIR as root for installed products (EUPS_PATH)])],
   [EUPS_PATH=$withval],
   [if [[ -z $EUPS_PATH ]]; then
       EUPS_PATH=\${prefix}/share
    else
       EUPS_PATH=$EUPS_PATH
    fi
   ])
AC_SUBST(EUPS_PATH)

AC_ARG_WITH(eups_dir,
   [AS_HELP_STRING(--with-eups_dir=DIR, [Install eups into DIR/{bin,doc}])],
   [EUPS_DIR=$withval],
   [EUPS_DIR=$(echo ${EUPS_PATH} | perl -pe 's/:.*$//')/eups])
AC_SUBST(EUPS_DIR)
dnl
dnl Output
dnl
AC_CONFIG_FILES([Makefile])
AC_OUTPUT

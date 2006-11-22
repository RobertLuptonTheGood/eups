AC_INIT([eups], "X.Y", [rhl@astro.princeton.edu])
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

AC_ARG_WITH(eups-db,
   [AS_HELP_STRING(--with-eups-db=name,Select directory containing NAME from $EUPS_PATH)],
   [eups_db=$withval])

AC_ARG_WITH(eups_dir,
   [AS_HELP_STRING(--with-eups_dir=DIR, [Install eups into DIR/{bin,doc}])],
   [EUPS_DIR=$withval],
   [if [[ X"$eups_db" = X"" ]]; then
      eups_dir_in_path=$(perl -e "(\$ed='$EUPS_DIR')=~s|/eups$||; @ep=split(':', '$EUPS_PATH'); print (grep(m|^\$ed\$|, @ep)) . \"\n\"")
      if [[ X$eups_dir_in_path = X"" -a X"$EUPS_DIR" != X"" ]]; then
          AC_MSG_WARN([Ignoring \$EUPS_DIR = $EUPS_DIR (not in EUPS_PATH = $EUPS_PATH)])
	  EUPS_DIR=""         
      fi
      if [[ X"$EUPS_DIR" = X"" ]]; then
         EUPS_DIR=$(echo $EUPS_PATH | perl -pe 's/:.*//')/eups
      fi
   else
      OLD_EUPS_DIR=$EUPS_DIR; EUPS_DIR=NONE
      for d in $(echo $EUPS_PATH | perl -pe 's/:/\n/g'); do
	 case $d in
	  */$eups_db$|$eups_db/*|*/$eups_db/*)
	    EUPS_DIR=$d/eups;;
	  esac
       done			
       if [[ X"$EUPS_DIR" = X"NONE" ]]; then
          AC_MSG_ERROR([I can't find DB \"$eups_db\" in $EUPS_PATH])
       fi
       if [[ X"$OLD_EUPS_DIR" != X"$EUPS_DIR" -a X"$OLD_EUPS_DIR" != X"" ]]; then
          AC_MSG_WARN([Ignoring \$EUPS_DIR = $OLD_EUPS_DIR])
       fi       
    fi])
AC_SUBST(EUPS_DIR)
dnl
dnl Output
dnl
AC_CONFIG_FILES([Makefile ups/eups.table])
AC_OUTPUT

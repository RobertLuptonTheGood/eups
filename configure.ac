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
   [EUPS_PATH=$(echo $withval | perl -pe 's|/*$||')],
   [if [[ -z $EUPS_PATH ]]; then
       EUPS_PATH=\${prefix}/share
    else
       EUPS_PATH=$EUPS_PATH
    fi
   ])
AC_SUBST(EUPS_PATH)

# Allow them to use --prefix as an alias for --with-eups_dir
if test X$prefix != XNONE; then
   with_eups_dir=$prefix
fi

AC_ARG_WITH(eups-db,
   [AS_HELP_STRING(--with-eups-db=name,Select directory containing NAME from $EUPS_PATH)],
   [eups_db=$withval])

AC_ARG_WITH(eups_dir,
   [AS_HELP_STRING(--with-eups_dir=DIR, [Install eups into DIR/{bin,doc} (equivalent to --prefix)])],
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
dnl Allow the user to disable building the documentation
dnl
MAKE_SUBDIRS="bin etc python site ups"
AC_ARG_ENABLE(docs,
   [AS_HELP_STRING(--enable-docs, [Enable building the documentation (YES)])],
   [if [[ $enableval = "yes" ]]; then
       MAKE_SUBDIRS="$MAKE_SUBDIRS doc"
    fi],
   [MAKE_SUBDIRS="$MAKE_SUBDIRS doc"],
   )
AC_SUBST(MAKE_SUBDIRS)
dnl
dnl Aliases for user commands (some people object to "setup", and it conflicts
dnl with a RH linux command in /usr/bin)
dnl
AC_ARG_WITH(setup-aliases,
   [AS_HELP_STRING(--with-setup-aliases=name1:name2,allow name1 as an alias for setup, and name2 for unsetup)],
   [SETUP_ALIASES=$withval])
AC_SUBST(SETUP_ALIASES)
dnl
dnl Output
dnl
AC_CONFIG_FILES([Makefile])
dnl AC_CONFIG_FILES([ups/eups.table])
dnl
dnl This messy perl ensures that multiple EUPS_PATH components are added
dnl separately, which permits us to unsetup eups
dnl
AC_CONFIG_FILES([ups/eups.table], [[perl -ni -e 'if(($b,undef,$ep,$e) = /^(\s*env(Prepend|Append)\(\s*EUPS_PATH\s*,)\s*([^)]+)(.*)$/) { foreach $p (split(":",$ep)) { print "$b ${p}$e\n"} } else { print }' ups/eups.table]])
AC_OUTPUT

if [[ X$SETUP_ALIASES != X ]]; then
   echo "addAlias(`echo $SETUP_ALIASES | sed -e 's/:.*$//'`, setup \$@)" >> ups/eups.table
   echo "addAlias(`echo $SETUP_ALIASES | sed -e 's/^.*://'`, unsetup \$@)" >> ups/eups.table
fi

(export EUPS_DIR=$PWD; cd bin; ./mksetup $EUPS_DIR $EUPS_PATH $SETUP_ALIASES)
make git.version

#!/bin/bash
#
# EupsPkg Distrib Mechanism Default Shell Implementation
#
# Defines utility functions, default implementations of eupspkg verbs, and
# performs common initialization.
#

# Magic tarball-and-patch (TaP) environment variables that can be set in
# eupspkg.cfg.sh files:
#
# TAP_PACKAGE: Set to 1 if the package is TaP, bypassing the heuristics in
#              default_prep()
# TAP_TAR_OPTIONS: Options that can be added to the tar command that extracts
#                  files from the tarball. For example, this can be used to
#                  exclude specific files from being extracted (such as a
#                  ups directory).
# TAP_USE_BUILD_DIR: Set to 1 to untar the files into a subdirectory (_build
#                    by default). This can be used to simplify the resulting
#                    directory structure so that files from the git repository
#                    are not confused with files from the tarball.

set -e

##################### ---- UTILITY FUNCTIONS ---- #####################

#
# Verbosity levels:
#
#   >= -3: Show fatal errors (fatal)
#   >= -2: Show errors (error)
#   >= -1: Show warnings (warn)
#   >=  0: Show messages (msg)
#   >=  1: Show add'l informational messages (info)
#   >=  2: Show debugging messages (debug)
#   >=  3: Activate Bash tracing (set -x)

# We'll use 3 as a "stdlog" descriptor, pointing to stderr if it hasn't
# already been opened by a parent process.
( exec >&3 ) 2>/dev/null || exec 3>&2

# The funny '|| true' construct is there to ensure this works with 'set -e'
die()   { [[ $VERBOSE -ge -3 ]] && echo "eupspkg.${_FUNCNAME:-${FUNCNAME[1]}} (fatal): $@" >&3 || true; exit -1; }
error() { [[ $VERBOSE -ge -2 ]] && echo "eupspkg.${_FUNCNAME:-${FUNCNAME[1]}} (error): $@" >&3 || true; }
warn()  { [[ $VERBOSE -ge -1 ]] && echo "eupspkg.${_FUNCNAME:-${FUNCNAME[1]}} (warning): $@" >&3 || true; }
msg()   { [[ $VERBOSE -ge 0 ]] && echo "eupspkg.${_FUNCNAME:-${FUNCNAME[1]}}: $@" >&3 || true; }
info()  { [[ $VERBOSE -ge 1 ]] && echo "eupspkg.${_FUNCNAME:-${FUNCNAME[1]}} (info): $@" >&3 || true; }
debug() { [[ $VERBOSE -ge 2 ]] && echo "eupspkg.${_FUNCNAME:-${FUNCNAME[1]}} (debug): $@" >&3 || true; }

die_if_empty() { eval VAL_="\$$1"; if [ -z "$VAL_" ]; then die "$1 is not set. refusing to proceed."; fi; }

# File descriptor 4 is opened for writing to EUPS console (for messages to
# the user).  We'll point it to /dev/null if it hasn't already been opened
# by the parent process.
( exec >&4 ) 2>/dev/null || exec 4>/dev/null

eups_console()
{
	# Pipe a message to EUPS console (by convention, file descriptor 4).
	# and to stdout.
	#
	# usage: echo "Message" | eups_console
	#

	while read line
	do
		echo "$line" 1>&4

		local _FUNCNAME="${FUNCNAME[1]}"
		msg "$line"
	done
}

dumpvar()
{
	local cmd="$1"
	shift

	for _VAR in "$@"; do
		eval "$cmd \"$_VAR='\$$_VAR'\""
	done
}

append_pkginfo()
{
	# Append VARNAME=VARVALUE line to pkginfo file
	# Should only be used by the 'create' verb.
	#
	# usage: append_pkginfo <VARNAME> [VARVALUE]
	#
	# If VARVALUE is not given $VARNAME will be evaluated
	#

	die_if_empty PKGINFO

	if [[ $# == 1 ]]; then
		eval VAL_="\$$1";
	else
		VAL_="$2"
	fi

	echo $1="'""$VAL_""'" >> "$PKGINFO"

	info "appended $1='$VAL_' to pkginfo."
}

detect_compiler()
{
	#
	# Properly detects C and C++ compiler types. Dies if the two are not
	# the same. Detects the flag to use with the C++ compiler to enable
	# best available approximations of C++11 and C++14 support.
	#
	# Defines:
	#	COMPILER_TYPE, CXX_COMP_TYPE, C_COMP_TYPE
	#	CXX_CXX11_FLAG, CXX_CXX14_FLAG
	#

	# Construct test source files
	local S="$(mktemp -t comptest.XXXXX)".c
	cat > "$S" <<-EOF
		#include <stdio.h>

		int main()
		{
			#if defined(__clang__)
				printf("clang");
			#elif defined(__ICC) || defined(__INTEL_COMPILER)
				printf("icc");
			#elif defined(__GNUC__) || defined(__GNUG__)
				printf("gcc");
			#elif defined(_MSC_VER)
				printf("msvc");
			#elif defined(__PGI)
				printf("pgcc");
			#else
				printf("unknown");
			#endif

			return 0;
		}
	EOF
	local SCXX="$(mktemp -t comptest.XXXXX)".cxx
	cp "$S" "$SCXX"

	# Build and run the test
	local O=$(mktemp -t comptest.XXXXX)
	local OCXX=$(mktemp -t comptest.XXXXX)
	CC1="${CC:-cc}"
	CXX1="${CXX:-c++}"
	"$CC1" "$S" -o "$O"
	"$CXX1" "$SCXX" -o "$OCXX"
	C_COMP_TYPE=$("$O")
	CXX_COMP_TYPE=$("$OCXX")

	# Check compiler type consistency
	if [[ "$CXX_COMP_TYPE" != "$C_COMP_TYPE" ]]; then
		die "C and C++ compiler versions differ ($CC1 is of type '$C_COMP_TYPE' while $CXX1 is of type '$CXX_COMP_TYPE')"
	fi

	COMPILER_TYPE="$CXX_COMP_TYPE"

	# Test C++ compiler for upper bound of -std argument, and set flags to be
	# used for best available approximations of C++11 and C++14 support
	if "$CXX1" "$SCXX" -std=c++14 -o "$OCXX" 2>/dev/null; then
		CXX_CXX14_FLAG="-std=c++14"
		CXX_CXX11_FLAG="-std=c++11"
	elif "$CXX1" "$SCXX" -std=c++11 -o "$OCXX" 2>/dev/null; then
		CXX_CXX14_FLAG="-std=c++11"
		CXX_CXX11_FLAG="-std=c++11"
	elif "$CXX1" "$SCXX" -std=c++0x -o "$OCXX" 2>/dev/null; then
		CXX_CXX14_FLAG="-std=c++0x"
		CXX_CXX11_FLAG="-std=c++0x"
	else
		CXX_CXX14_FLAG=
		CXX_CXX11_FLAG=
	fi
}

eups_version()
{
	# Return (on stdout) the version of EUPS

	local ev

	ev=$(eups --version)
	ev=${ev#EUPS Version: }

	echo "$ev"
}

require_eups_version()
{
	# Die if EUPS version not greater than or equal than the argument.
	#
	# Usage: require_eups_version <min_version> [error_message]
	#
	# Example: require_eups_version 1.5.4
	#
	# While developing: if envvar NOVERCHECK=1, warn instead of dying

	eups_ver=$(eups_version)

	# Split the version string into an array
	IFS=. read -ra SA <<< "$eups_ver"
	IFS=. read -ra SB <<< "$1"

	# Print the array as zero-padded string, so we can compare it lexicographically
	V1=$(printf "%05d" "${SA[@]}")
	V2=$(printf "%05d" "${SB[@]}")

	if [[ "$V1" < "$V2" ]]; then
		message=${2-"EUPS v$eups_ver too old for this package; v$1 or later required."}
		if [[ $NOVERCHECK != 1 ]]; then
			die "$message"
		else
			warn "$message"
		fi
	fi
}

autoproduct()
{
	# Guess PRODUCT, assuming we were called from a working directory of
	# a git repository.

	if ! hash git 2>/dev/null; then
		die "could not execute 'git' to automatically deduce PRODUCT and VERSION."
	fi

	local REMOTE=$(git config --get remote.origin.url || true)
	if [[ -z "$REMOTE" ]]; then
		die "No git remote named 'origin', or git error. Please specify PRODUCT.";
	fi

	PRODUCT="$(basename "$REMOTE" .git)"

	info "guessed PRODUCT='$PRODUCT'"
}

autoversion()
{
	# Guess VERSION, assuming we were called from a working directory of
	# a git repository.

	VERSION="$VERSION_PREFIX$(pkgautoversion $1)$VERSION_SUFFIX"

	info "guessed VERSION='$VERSION'"
}

install_ups()
{
	# Copy the contents of ups/ to $PREFIX/ups and expand the table files
	#
	# It's necessary to call this if the native install method doesn't
	# copy/expand ups/ content

	[ ! -d ups ] && die "no 'ups' directory to copy to destination (are you running from package root?)";

	mkdir -p "$PREFIX/ups"
	cp -f -a ./ups/* "$PREFIX/ups"

	# Expand the table file, if any
	if [[ -f "$PREFIX/ups/$PRODUCT.table" ]]; then
		eups expandtable -i -W '^(?!LOCAL:)' "$PREFIX/ups/$PRODUCT.table"
		info "expanded table file '$PREFIX/ups/$PRODUCT.table'"
	else
		msg "no table file to expand (looked for '$PREFIX/ups/$PRODUCT.table')".
	fi
}

clean_old_install()
{
	#
	# Remove any existing content in $PREFIX, being extra careful
	# that $PREFIX is sane.
	#
	if [[ -e "$PREFIX" ]]; then
		P0="$PRODUCTS_ROOT"
		P1=$(cd "$PREFIX" && pwd)

		# Delete only if $PREFIX is a proper subdirectory of eups
		# products root
		if [[ "$P0" != "$P1" && "$P1" == "$P0"* ]]; then
			msg "deleting existing install in '$P1'"
			rm -rf "$P1"
		else
			msg "odd install directory '$PREFIX' (not a proper subdir of eups install root). not deleting it out of abundance of caution."
		fi
	fi
}

resolve_repository()
{
	#
	# Resolve the path to git repository, by expanding patterns
	# specified on the RESOLVE_PATH.  If unsuccessful, but $REPOSITORY
	# is not empty, use that.  Otherwise, die.
	#
	# RESOLVE_PATH must be of the form:
	#
	#   'git://server1/dirs1/$PRODUCT.git|http://server2/dirs2/$PRODUCT.git'
	#
	# etc., i.e., a |-delimited string of Bash strings which will be eval-ed
	# in the current environment.
	#
	# Defines: REPOSITORY
	#

	IFS='|' read -ra REPOSITORY_PATH_ARRAY <<< "$REPOSITORY_PATH"
	for PAT in "${REPOSITORY_PATH_ARRAY[@]}"; do
		eval "_REPOSITORY=\"$PAT\""
		info "trying $_REPOSITORY"
		if git ls-remote "$_REPOSITORY" HEAD >/dev/null 2>&1; then
			info "repository resolved to $_REPOSITORY."
			REPOSITORY="$_REPOSITORY"
			return
		fi
	done

	if [[ -z "$REPOSITORY" ]]; then
		die "failed to resolve repository for $PRODUCT-$VERSION using REPOSITORY_PATH='$REPOSITORY_PATH'. Check the path or accessibility of your git repositories."
	fi

	info "using predefined REPOSITORY='$REPOSITORY'"
}

resolve_repoversion()
{
	# Discover the source code revision within the repository
	#
	# If REPOVERSION is already set, use it.
	# Else, if SHA1 is set, use it as REPOVERSION.  Othewise, convert the
	# VERSION into a REPOVERSION by removing +xxxx suffix, any packager-specified
	# VERSION_PREFIX/VERSION_SUFFIX, and replacing all _ with -.
	#
	# Defines: REPOVERSION
	#

	[[ ! -z "$REPOVERSION" ]] && { return 0; }
	[[ ! -z "$SHA1" ]]   && { REPOVERSION="$SHA1"; return 0; }

	# Deduce REPOVERSION from version
	local V="${VERSION%%+*}"	# remove everything past the first + (incl. the '+')

	V="${V#$VERSION_PREFIX}"	# remove VERSION_PREFIX
	V="${V%$VERSION_SUFFIX}"	# remove VERSION_SUFFIX
	V="${V//_/-}"			# convert all _ to -

	REPOVERSION="$V"
}


contains()
{
	#
	# usage: contains <needle> <haystack[1]> [haystack[2]] ...
	#

	local _N="$1"
	shift

	for _H in "${@}"; do
		[[ $_N == $_H ]] && return 0
	done

	return 250
}

copy_function()
{
	# usage: copy_function <old_name> <new_name>
	#
	# Copies function named $1 to name $2. useful when overriding
	# existing functions, but wanting to save (and presumably call) the
	# old implementation.  Adapted from
	# http://stackoverflow.com/questions/1203583/how-do-i-rename-a-bash-function

	declare -F $1 > /dev/null || return 1
	eval "$(echo "$2()"; declare -f $1 | tail -n +2)"
}

fix_autoconf_timestamps()
{
	# git does not preserve timestamps, which makes autoconf very
	# unhappy and elusional about needing to regenerate configure and
	# .in files. This function hacks its way around it.
	#
	# based on http://www.gnu.org/software/automake/manual/html_node/CVS.html

	if [[ -f "$UPSTREAM_DIR/prepared" ]]; then
		# If we're running from a TaP package, assume
		# timestamps are OK.
		info "running from TaP package; not touching autoconf timestamps."
		return
	fi

	find . -name aclocal.m4 -exec touch {} \;
	sleep 1

	find . -name configure -exec touch {} \;
	find . -name config.h.in -exec touch {} \;
	find . -name Makefile.in -exec touch {} \;

	find . -name "*.info" -exec touch {} \;
}

decl()
{
	# Declare the product to EUPS
	#
	# usage: decl [eups declare arguments]
	#

	die_if_empty PRODUCT
	die_if_empty VERSION
	die_if_empty PREFIX

	# Sanity checks
	if [[ ! -d "$PREFIX/ups" ]]; then
		die "directory $PREFIX/ups doesn't exist or is not a directory. did you forget to run 'eupspkg install'?"
	fi

	eups declare "$PRODUCT" "$VERSION" -r "$PREFIX" "$@"

	msg "declared $PRODUCT $VERSION in $PREFIX (eups declare options: ${@:-none})"
}

_clear_environment()
{
	# to the future developers of this file: to quickly list all
	# variables that are used as ${BLA:-...} (i.e., have a default), and
	# don't begin with a _, use the following sed incantation:
	#
	# sed -n 's/\(.*\$\){\(.*\)\(:-.*\)$/\2/p;' lib/eupspkg.sh | sort -u | grep -Ev '^(_|@).*$'

	for _var in \
		FLAVOR PRODUCT VERSION PREFIX \
		SOURCE INCLUDES \
		\
		CONFIGURE_OPTIONS \
		MAKE_BUILD_TARGETS MAKE_INSTALL_TARGETS \
		PYSETUP_INSTALL_OPTIONS \
		\
		VERSION_PREFIX VERSION_SUFFIX \
		\
		PATCHES_DIR UPSTREAM_DIR \
		BUILD_DIR \
		PRODUCTS_ROOT \
		REPOSITORY REPOSITORY_PATH \
		SHA1 REPOVERSION \
	; do
		debug clearing $_var
		unset $_var
	done
}

##################### ---- DEFAULT VERB IMPL ---- #####################

_sha1_for_remote_rev()
{
	# usage: _sha1_for_remote_rev $REPOSITORY $REPOVERSION
	#
	# returns the SHA1 corresponding to $REPOVERSION at remote repository
	# $REPOSITORY.  returns an empty string in case of failiure.

	local SHA1=$(git ls-remote -t "$REPOSITORY" "$REPOVERSION"^{} | awk '{print $1}')		# try tags first
	local SHA1=${SHA1:-$(git ls-remote -h "$REPOSITORY" "$REPOVERSION" | awk '{print $1}')}	# fall back to heads

	echo "$SHA1"
}

default_create()
{
	# Called to create the contents of the package.
	#
	# See the documentation for verb 'create' in eups.distrib.eupspkg
	# module for details.
	# --
	# CWD: Called from the (empty) $pkgdir
	# Env: Nothing guaranteed to be setup-ed
	#

	# safety: refuse to work in a non-empty directory. This will prevent
	# chaos when careless users run eupspkg create in their source
	# directories.
	if [[ ! -z "$(ls -A)" ]]; then
		die "safety first: refusing to run from a non-empty directory."
	fi

	# Make sure the important ones are here
	die_if_empty PRODUCT
	die_if_empty VERSION
	die_if_empty FLAVOR
	die_if_empty SOURCE

	# Define temporary location for pkginfo file. We'll copy
	# it to ups/pkginfo in the end, to avoid it being overwritten
	# by package creation commands below.
	PKGINFO=$(mktemp -t pkginfo.XXXXX)

	# Store the variables we know of to pkginfo
	append_pkginfo PRODUCT
	append_pkginfo VERSION
	append_pkginfo FLAVOR
	append_pkginfo SOURCE

	# Find out the source code repository, and the code revision within that repository
	resolve_repository
	resolve_repoversion

	case "$SOURCE" in
		git)
			# Use git clone to extract ups/eupspkg. Store the SHA1 into $PKGINFO.
			# Note: this is terribly inefficient, but git doesn't provide a
			# mechanism to just fetch a single file given a ref.
			git clone --shared -n -q "$REPOSITORY" tmp

			SHA1=$(cd tmp && git rev-parse "$REPOVERSION"^{})
			append_pkginfo SHA1

			# try to avoid checking out everything (it may be a multi-GB repo)
			(cd tmp && { git checkout -q $SHA1 -- ups 2>/dev/null || git checkout -q "$REPOVERSION"; })

			mkdir ups
			if [[ -e tmp/ups/eupspkg ]]; then
				mv tmp/ups/eupspkg ups
			fi

			rm -rf tmp
			;;
		git-archive)
			# Extract ups/eupspkg using git-archive
			git archive --format=tar.gz --remote="$REPOSITORY" "$REPOVERSION" ups/eupspkg 2>/dev/null | (tar xzf - 2>/dev/null || true)
			# note: the odd tar construct (and PIPESTATUS check) is to account for BSD/gnu tar differences:
			#       BSD tar returns success on broken pipe, gnu tar returns an error.
			if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
				# The failure may have occurred because ups/ does not exist on the remote, or because
				# of a problem with accessing the repository. The former is legal, the latter is not.
				# Find out which one is it and act accordinly.
				git archive --format=tar.gz --remote="$REPOSITORY" "$REPOVERSION" | head -c 1 > /dev/null
				if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
					die "could not access '$REPOSITORY' via git-archive. has it been tagged with '$REPOVERSION'"?
				fi
				mkdir -p ups
			fi

			# Extract the SHA1 of the remote, and store it in pkginfo
			SHA1=$(_sha1_for_remote_rev $REPOSITORY $REPOVERSION)
			[[ ! -z $SHA1 ]] || die "cannot deduce SHA1 for git revision '$REPOVERSION'. bug?"

			append_pkginfo SHA1
			;;
		"package")
			# Extract the full source using git-archive, falling back to git-clone in case of failure.
			debug "attempting to extract the source for package using git-archive (for '$REPOVERSION')"
			git archive --format=tar.gz --remote="$REPOSITORY" "$REPOVERSION" 2>/dev/null | (tar xzf - 2>/dev/null || true)
			# note: the odd tar construct (and PIPESTATUS check) is to account for BSD/gnu tar differences:
			#       BSD tar returns success on broken pipe, gnu tar returns an error.
			if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
				debug "git-archive failed. falling back to git-clone (for '$REPOVERSION')"
				git clone --shared -n -q "$REPOSITORY" .

				SHA1=$(git rev-parse "$REPOVERSION"^{})
				git checkout -q "$SHA1"

				rm -rf .git
			else
				# Extract the SHA1 from the remote, and store it in pkginfo
				SHA1=$(_sha1_for_remote_rev $REPOSITORY $REPOVERSION)
				[[ ! -z $SHA1 ]] || die "cannot deduce SHA1 for git revision '$REPOVERSION'. bug?"
			fi

			append_pkginfo SHA1
			;;
		*)
			echo "eupspkg error: unknown source download mechanism SOURCE='$SOURCE' (known mechanisms: git, git-archive, package)."; exit -1;
	esac

	# if $REPOSITORY is a local directory, see if there's a remote named
	# 'origin' and use it for repository URL.  Otherwise, store as-is.
	if [[ -d "$REPOSITORY" ]]; then
		local URL=$(cd "$REPOSITORY" && git config --get remote.origin.url)
		if [[ ! -z "$URL" ]]; then
			info "detected '$REPOSITORY' is local; recording '$URL' in pkginfo (url of orgin)"
			REPOSITORY="$URL"
		fi
	fi

	append_pkginfo REPOSITORY
	append_pkginfo REPOVERSION

	# move pkginfo file to its final location
	mkdir -p ups
	mv "$PKGINFO" ups/pkginfo
	chmod +r ups/pkginfo

	PKGINFO="ups/pkginfo"

	msg "package contents created for '$PRODUCT-$VERSION', sources will be fetched via '$SOURCE'."
}

default_fetch()
{
	# Called in the 'eups distrib install' phase to obtain the source
	# code and unpack, it so it's the same as when it was checked out
	# from git.
	#
	# For details, see the documentation for verb 'fetch' in
	# eups.distrib.eupspkg module docstring.
	# --
	# CWD: Called from $pkgdir
	# Env: Called in environment with setup-ed dependencies, but not the product itself
	#

	die_if_empty PRODUCT
	die_if_empty VERSION

	case "$SOURCE" in
		git)
			# Obtain the source from a git repository
			die_if_empty REPOSITORY
			die_if_empty REPOVERSION
			die_if_empty SHA1

			info "fetching by git cloning from $REPOSITORY"
			git clone -q "$REPOSITORY" tmp
			(cd tmp && git checkout -q $REPOVERSION)

			# security first: die if the SHA1 has changed (e.g., somebody has been changing tags)
			SHA1r=$(cd tmp && git rev-parse HEAD)
			if [[ "$SHA1r" != "$SHA1" ]]; then
				die "SHA1 of the fetched source ($SHA1r) differs from the expected ($SHA1). refusing to proceed."
			else
				info "remote SHA1 identical to expected SHA1 ($SHA1). ok."
			fi

			rm -rf tmp/.git

			# move everything but the contents of the ups directory (as it already exists)
			find tmp -maxdepth 1 -mindepth 1 ! -name ups -exec mv {} . \;
			# move the contents of the ups directory, excluding eupspkg and pkginfo
			find tmp/ups -maxdepth 1 -mindepth 1 ! \(  -name eupspkg -o -name pkginfo \) -exec mv {} ups \;
			rm -f tmp/ups/eupspkg tmp/ups/pkginfo
			rmdir tmp/ups 2>/dev/null || true

			# the tmp directory must be empty at this point
			rmdir tmp
			;;
		git-archive)
			die_if_empty REPOSITORY
			die_if_empty REPOVERSION
			die_if_empty SHA1

			# note: the odd tar construct (and PIPESTATUS check) is to account for BSD/gnu tar differences:
			#       BSD tar returns success on broken pipe, gnu tar returns an error.
			info "fetching via git-archive from $REPOSITORY, for ref '$REPOVERSION'"
			git archive --format=tar.gz  --remote="$REPOSITORY" "$REPOVERSION" | (tar xzf - --exclude ups/eupspkg --exclude ups/pkginfo 2>/dev/null || true)
			if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
				die could not access "$REPOSITORY" via git-archive. has it been tagged with "$REPOVERSION"?
			fi

			# security first: die if the SHA1 has changed (e.g., somebody has been changing tags)
			SHA1r=$(_sha1_for_remote_rev $REPOSITORY $REPOVERSION)
			if [[ "$SHA1r" != "$SHA1" ]]; then
				die "SHA1 of the fetched source ($SHA1r) differs from the expected ($SHA1). refusing to proceed."
			else
				info "remote SHA1 identical to expected SHA1 ($SHA1). ok."
			fi
			;;
		"package")
			;;
		*)
			die "unknown source '$SOURCE'. Malformed archive?";
			;;
	esac
}

default_prep()
{
	# Prepare the code to be configured (e.g., by applying any patches)
	#
	# For details, see the documentation for verb 'prep' in
	# eups.distrib.eupspkg module docstring.
	# --
	# CWD: Called from $pkgdir
	# Env: Called in environment with setup-ed dependencies, but not the product itself


	# See if this is a "tarball-and-patch" (TaP) package:
	#
	# These have a directory named upstream/ with tarballs to untar
	# into pkgroot, and possibly a directory named patches/ with patches
	# to apply once all tarballs have been expanded.
	#
	# To be recognized as at TaP package, there must be no files (other
	# than those starting with a dot) in the package root directory, and
	# there must be a directory named 'upstream'

	if [[ -d "$UPSTREAM_DIR" ]]; then

		if [[ -f "$UPSTREAM_DIR/prepared" ]]; then
			msg "package already prepared (found '$UPSTREAM_DIR/prepared' flag file)."
			return
		fi

		# verify that there are no files (other than .* or _*) in $pkgdir
		# packagers: it's possible override this check by setting TAP_PACKAGE=1 in eupspkg.cfg.sh
		# (deprecated) can also be overriden by touching a .tap_package file (mistakenly introduced in v1.5.8, will be removed at a later date)
		if [[ "$TAP_PACKAGE" != 1 && ! -f ".tap_package" && ! -z $(find . -maxdepth 1 -mindepth 1 ! -name ".*" ! -name "_*" -a -type f) ]]; then
			die "files found in root directory; guessing this is not a TaP package."
		fi

		reldir="."
		if [[ "$TAP_USE_BUILD_DIR" == 1 ]]; then
			reldir=".."
			mkdir "$BUILD_DIR"
			cd "$BUILD_DIR"
		fi

		# untar the contents of upstream
		for _tb in "$reldir/$UPSTREAM_DIR"/*; do
			if [[ -d "$_tb" ]]; then
				continue;
			fi
			msg "unpacking $_tb ..."
			case $_tb in
				*.tar.gz|*.tgz)  tar xzf "$_tb" --strip-components 1 $TAP_TAR_OPTIONS ;;
				*.tar.bz2|*.tbz) tar xjf "$_tb" --strip-components 1 $TAP_TAR_OPTIONS ;;
				*) die "unrecognized archive format for '$_tb'." ;;
			esac
		done

		# apply patches from patches/ (if any) they must match
		# *.patch.  subdirectories are _NOT_ searched -- it is
		# safe for overrides to place patches they plan to apply
		# into subdirs.
		if [[ -d "$reldir/$PATCHES_DIR" ]]; then
			for _p in $(find "$reldir/$PATCHES_DIR" -maxdepth 1 -mindepth 1 -name "*.patch" ! -type d | sort); do
				msg "applying $_p ..."
				patch -s -p1 < "$_p"
			done
		fi

		cd "$reldir"

		touch "$UPSTREAM_DIR/prepared"
	fi
}

default_config()
{
	# Configure the code so it can be built
	#
	# For details, see the documentation for verb 'config' in
	# eups.distrib.eupspkg module docstring.
	# --
	# CWD: Called from $pkgdir
	# Env: Called in environment with setup-ed product and dependencies
	# --
	# Typical override:
	#   run custom configuration scripts

	reldir="."
	if [[ "$TAP_USE_BUILD_DIR" == 1 ]]; then
		reldir=".."
		cd "$BUILD_DIR"
	fi

	if [[ -f configure ]]; then

		if [[ ! -d "$reldir/$UPSTREAM_DIR" ]]; then
			# fix timestamps only if this wasn't a TaP package
			fix_autoconf_timestamps
		fi

		# Use eval so that quoted strings in $CONFIGURE_OPTIONS
		# expand properly (e.g. --prefix="$PREFIX")
		eval ./configure $CONFIGURE_OPTIONS
	fi

	cd "$reldir"
}

default_build()
{
	# Build the product
	#
	# For details, see the documentation for verb 'config' in
	# eups.distrib.eupspkg module docstring.
	# --
	# CWD: Called from $pkgdir
	# Env: Called in environment with setup-ed product and dependencies

	die_if_empty PRODUCT
	die_if_empty VERSION

	reldir="."
	if [[ "$TAP_USE_BUILD_DIR" == 1 ]]; then
		reldir=".."
		cd "$BUILD_DIR"
	fi

	#
	# Attempt to autodetect the build system
	#
	if [[ -f SConstruct ]]; then
		scons -j$NJOBS prefix="$PREFIX" version="$VERSION" cc="$CC"
	elif [[ -f configure ]]; then
		make -j$NJOBS $MAKE_BUILD_TARGETS
	elif [[ -f Makefile || -f makefile || -f GNUmakefile ]]; then
		make -j$NJOBS prefix="$PREFIX" version="$VERSION" $MAKE_BUILD_TARGETS
	elif [[ -f setup.py ]]; then
		python setup.py build
	else
		msg "no build system detected; assuming no build needed."
	fi

	cd "$reldir"
}

default_install()
{
	# Install the product
        #
	# For details, see the documentation for verb 'config' in
	# eups.distrib.eupspkg module docstring.
	# --
	# CWD: Called from $pkgdir
	# Env: Called in environment with setup-ed product and dependencies

	die_if_empty PRODUCT
	die_if_empty VERSION

	clean_old_install

	reldir="."
	if [[ "$TAP_USE_BUILD_DIR" == 1 ]]; then
		reldir=".."
		cd "$BUILD_DIR"
	fi

	#
	# Attempt to autodetect the build system
	#
	if [[ -f SConstruct ]]; then
		scons -j$NJOBS prefix="$PREFIX" version="$VERSION" cc="$CC" install
	elif [[ -f configure ]]; then
		make -j$NJOBS $MAKE_INSTALL_TARGETS
	elif [[ -f Makefile || -f makefile || -f GNUmakefile ]]; then
		make -j$NJOBS prefix="$PREFIX" version="$VERSION"  $MAKE_INSTALL_TARGETS
	elif [[ -f setup.py ]]; then
		PYDEST="$PREFIX/lib/python"
		mkdir -p "$PYDEST"
		# eval is needed to allow $PYSETUP_INSTALL_OPTIONS to include double quotes
		{
			# the extra options here prevent the installation of dependencies via
			# eups - the installation will error with the name of the package that is needed
			# this only works for setuptools-based packages
			PYTHONPATH="$PYDEST:$PYTHONPATH" \
				eval python setup.py install --single-version-externally-managed --record record.txt  $PYSETUP_INSTALL_OPTIONS
		} || {
			# this block catches distutils-only packages that don't install their
			# dependencies anyways
			PYTHONPATH="$PYDEST:$PYTHONPATH" eval python setup.py install $PYSETUP_INSTALL_OPTIONS
		}
		evil_setuptools_pth_fix "$PYDEST"
	else
		# just copy everything, except for the ups directory
		mkdir -p "$PREFIX"
		cp -a ./ "$PREFIX"
		rm -rf "$PREFIX/ups"
		msg "Copied the product into '$PREFIX'"
	fi

	cd "$reldir"

	# Install ups if the native build system hasn't done it already.
	# We do this check to avoid expanding the table file twice (EUPS has a bug there)
	if [[ -d "ups" && ! -d "$PREFIX/ups" ]]; then
		install_ups
	fi
}

evil_setuptools_pth_fix()
{
	# setuptools does the *IDIOTIC* sys.path manipulation in .pth files,
	# to prepend its own path to sys.path thus making it impossible to
	# override.  The fact this lunacy managed to enter Python proper is
	# a demonstration of what happens when there's no code review.
	#
	# This function tries to remove the offending lines from .pth files.
	#
	# See:
	#   http://stackoverflow.com/questions/5984523/eggs-in-path-before-pythonpath-environment-variable
	# for details.

	for FN in $(find "$PREFIX" -name "*.pth"); do
		sed -i~ '/^import.*/d' "$FN"
	done
}

default_usage()
{
	cat <<-"EOF"
		eupspkg -- EupsPkg builder script

		usage: eupspkg [-hedrk] [-v level] [VAR1=..] [VAR2=..] verb

		  verb  : one of create, fetch, prep, config, build, install

		  v : set verbosity level (-2 through +3, default 0)
		  h : show usage instructions

		  e : activate 'developer mode', product name/version is
		      autodetected
		  d : in developer mode, don't test for dirty source tree
		      when autodetecting versions
		  r : in developer mode, make install $PREFIX for the
		      product point to EUPS binary directory
		  k : keep all pre-set environment variables

		EUPSPKG STANDARD MODE:

		If run with 'create', the script expects to be executed in
		an empty directory and PRODUCT, VERSION, FLAVOR, and PREFIX
		to be passed in as variables on the command line.  Using
		those, it will create './ups/pkginfo' with package
		configuration, as well as prepare the package contents
		depending on the chosen SOURCE.  Any existing
		$PREFIX/ups/pkginfo will be sourced to deduce REPOSITORY and
		SHA1.  If REPOSITORY_PATH is given, it will be preferred
		over REPOSITORY from pkginfo.

		If run with any other verb, the script will look for
		'./ups/pkginfo' to source the configuration.  At least
		PRODUCT, VERSION and FLAVOR must be present.

		Variables can be passed on the command line, after the
		options and before the verb.  These override any from the
		environment or pkginfo. Note that unless -k is specified,
		most script-specific variables won't be taken from the
		environment (run `eupspkg -v 2 echo' to see a list).

		DEVELOPER MODE:

		Developer mode is there to facilitate creation and testing
		of EupsPkg packages.  When active, PRODUCT, VERSION and
		FLAVOR will be autodetected from git.  Unless -r is given,
		PREFIX will point to ./_eupspkg/binary/$PRODUCT/$VERSION.
		The verbs will behave as follows:

		  create   : will create ./_eupspkg/source and run create
		             there.
		  fetch    : will run fetch in ./_eupspkg/source
		  prep     : will run prep in ./_eupspkg/source
		  config,  : if ./_eupspkg/source exists, will run the verb
		  build,     there, otherwise will run it in current dir.
		  install

		Additional verbs will be available:

		  decl    : declare the package to EUPS. Any arguments to
		            decl will be passed on to 'eups declare'
EOF
}

#
# Define default verb implementations
#
create()  { _FUNCNAME=create  default_create "$@"; }
fetch()   { _FUNCNAME=fetch   default_fetch "$@"; }
prep()    { _FUNCNAME=prep    default_prep "$@"; }
config()  { _FUNCNAME=config  default_config "$@"; }
build()   { _FUNCNAME=build   default_build "$@"; }
install() { _FUNCNAME=install default_install "$@"; }
usage()   { _FUNCNAME=usage   default_usage "$@"; }

##################### ---- INITIALIZATION ---- #####################

if [[ -f ./ups/eupspkg.cfg.sh ]]; then
	export EUPSPKG_SCRIPTS="$EUPSPKG_SCRIPTS:$PWD/ups/eupspkg.cfg.sh"
fi

#
# Parse command line options
#
VERBOSE=${EUPSPKG_VERBOSE:-0}
DIRTY_FLAG="--dirty"
DEVMODE=0
INSTALL_TO_EUPS_ROOT=0
KEEP_ENVIRONMENT=0
while getopts ":v:hedrk" opt; do
	case $opt in
		v) VERBOSE="$OPTARG" ;;
		d) DIRTY_FLAG="" ;;
		e) DEVMODE=1 ;;
		k) KEEP_ENVIRONMENT=1 ;;
		r) INSTALL_TO_EUPS_ROOT=1 ;;
		h) usage; exit; ;;
		\?) die "Invalid option: -$OPTARG" ;;
		:) die "Option -$OPTARG requires an argument." ;;
	esac
done
shift $((OPTIND-1))

# Clear the environment so it doesn't accidentally interfere with internally
# used variables (unless the user asks for it).
if [[ $KEEP_ENVIRONMENT != 1 ]]; then
	_clear_environment
else
	debug "not clearing the environment"
fi

# Peek if PREFIX or VERBOSE were given on the command line (to correctly
# find pkginfo).  Also remember the last value as $CMD.  Inelegant, but
# effective...
for _V in "$@"; do
	[[ ! $_V =~ [A-Za-z0-9_]+=.* ]] && break	# stop on first non-assignment
	[[ ! $_V =~ (PREFIX|VERBOSE)=.* ]] && continue	# skip all but PREFIX and VERBOSE

	_KEY="${_V%%=*}"
	_VAL="${_V#*=}"
	eval "$_KEY='$_VAL'"
done
CMD="$_V"

#
# Debug level 3 activates tracing
#
[[ $VERBOSE -ge 3 ]] && set -x

#
# Special handling if we're in dev mode (pre-pkginfo or command line)
#
if [[ $DEVMODE == 1 ]]; then
	# Remember the location of the source, in case we chdir
	_PSOURCE="$PWD"

	# chdir to _eupspkg/source if it exists, unless a) the user is
	# invoking 'create', or b) they're invoking fetch and
	# .__eupspkg_mock_fetch flag is set.
	if [[ -d _eupspkg/source && ! ( $CMD == "create" || $CMD == fetch && -e "_eupspkg/source/.__eupspkg_mock_fetch" ) ]]; then
		msg "switching to ./_eupspkg/source"
		cd _eupspkg/source

		# Now that we've changed the product root, we need to re-setup
		# it in there. Note we can't just call 'setup', since it's an
		# alias that won't propagate into this subshell
		msg "re-running setup in ./_eupspkg/source"
		eval $("$EUPS_DIR/bin/eups_setup" "DYLD_LIBRARY_PATH=${DYLD_LIBRARY_PATH}" -j -r .)
	fi
fi

#
# Source the pkginfo file
#
# EupsPkg API: PREFIX will be set when 'create' is called, pointing to the installed package
# eupspkg uses it to locate pkginfo (assumes . as the default). For other verbs, we'll look for
# pkginfo in ./ups/pkginfo.
#
if [[ $CMD == create ]]; then
	_PKGINFO="${PREFIX:-.}/ups/pkginfo"
else
	_PKGINFO="./ups/pkginfo"
fi

debug "looking for pkginfo in $_PKGINFO."
if [[ -f "$_PKGINFO" ]]; then
	debug "found pkginfo in $_PKGINFO."
	. "$_PKGINFO"
fi

#
# Variables can be set on the command line, to override anything already in
# the environment or (more interestingly) set via pkginfo. Set them here.
#
while [[ $1 =~ [A-Za-z0-9_]+=.* ]]; do
	_KEY="${1%%=*}"
	_VAL="${1#*=}"
	eval "$_KEY='$_VAL'"
	shift
done

# OK with the remaining number of arguments?
[[ $# -ge 1 ]] || { error "insufficient number of arguments."; usage; exit -1; }

#
# Special handling if we're in dev mode (post-pkginfo)
# At this point we have all envvar+pkginfo+cmdline overrides loaded
#
if [[ $DEVMODE == 1 ]]; then
	# Automatically set the version if not running in _eupspkg/source (if
	# running there, create should've populated pkginfo with all that's
	# needed)

	if [[ $PWD != */_eupspkg/source ]]; then
		# making sure version prefix/suffix are declared early.
		# a bit of a hack, since we need them here for proper autoversion inferrence
		VERSION_PREFIX=${VERSION_PREFIX:-$EUPSPKG_VERSION_PREFIX}
		VERSION_SUFFIX=${VERSION_SUFFIX:-$EUPSPKG_VERSION_SUFFIX}

		# Make sure PRODUCT, VERSION, and FLAVOR are set
		[ -z "$PRODUCT" ] && autoproduct
		[ -z "$VERSION" ] && autoversion $DIRTY_FLAG
		FLAVOR=${FLAVOR:-generic}
	fi


	if [[ $1 == "create" ]]; then
		# if invoking create, clean and/or auto-create and enter the _eupspkg/source directory
		# also set the prefix to product source directory (as would EUPS when invoking create)

		[[ $PWD == */_eupspkg/source ]] && die "you probably don't want to rerun 'create' in _eupspkg/source directory. chdir one level up and try again."

		PREFIX=${PREFIX:-"$PWD"}

		rm -rf _eupspkg/source
		mkdir -p _eupspkg/source
		cd _eupspkg/source
	elif [[ $1 == fetch ]]; then
		# If we were left in the working directory for 'fetch', that
		# means that _eupspkg/source doesn't exist, or that it has
		# been created by a previous run of fetch (and can be
		# removed).  Either way, (re)create it by simply copying the
		# current working directory.  This is very handy to test
		# work-in-progress that hasn't yet been pushed upstream (or
		# even committed).
		if [[ $PWD != */_eupspkg/source ]]; then
			# Copy the sources
			rm -rf _eupspkg/source
			mkdir -p _eupspkg/source
			touch _eupspkg/source/.__eupspkg_mock_fetch
			tar cf - --exclude _eupspkg --exclude .git --exclude *~ . | (cd _eupspkg/source && tar xf -)

			# Emulate pkginfo creation
			mkdir -p _eupspkg/source/ups
			PKGINFO="_eupspkg/source/ups/pkginfo"
			append_pkginfo PRODUCT
			append_pkginfo VERSION
			append_pkginfo FLAVOR
			append_pkginfo SOURCE package

			# Don't proceed any further.
			msg "cloned the working directory to _eupspkg/source (note: to test the real fetch verb, run \`eupspkg create' first)."
			exit 0
		fi
	else
		# where should we install the product?
		if [[ $INSTALL_TO_EUPS_ROOT != 1 ]]; then
			PRODUCTS_ROOT=${PRODUCTS_ROOT:-"$_PSOURCE/_eupspkg/binary"}
		fi
	fi
fi

#
# Verify that PRODUCT, VERSION, and FLAVOR have been set.
#
if [[ -z "$PRODUCT" || -z "$VERSION" || -z "$FLAVOR" ]]; then
	die "PRODUCT, VERSION, or FLAVOR were not defined. refusing to proceed."
fi

##################### ---- Defaults ---- #####################
#
# Note: if you add here more variables with defaults, make sure to list them
# in _clear_environment() as well unless you *want* them to be picked up from
# the environment if not overridden on the command line or via pkginfo.
#

SCRIPTS=${SCRIPTS:-"$EUPSPKG_SCRIPTS"}		# ':'-delimited list of scripts to source at the end of this script. Used to mass-customize package creation.

if [[ -z ${EUPSPKG_NJOBS} ]]; then
	if [[ -e /sys/fs/cgroup/cpuset/cpuset.cpus ]]; then
		# Use cgroups information
		NJOBS=$(awk '/-/{i+=$2-$1} {i++} END{print i}' RS=, FS=- /sys/fs/cgroup/cpuset/cpuset.cpus)
	else
		# number of cores on the machine (Darwin & Linux)
		NJOBS=$((sysctl -n hw.ncpu || (test -r /proc/cpuinfo && grep processor /proc/cpuinfo | wc -l) || echo 2) 2>/dev/null)
	fi
	[[ $NJOBS -gt 32 ]] && NJOBS=32		# limit the auto-detected number of jobs to 32 (otherwise we run into problems on massively multicore machines)
else
	NJOBS=${EUPSPKG_NJOBS}
fi

BUILD_DIR=${EUPSPKG_BUILD_DIR:-_build}			# Subdir to use if we are building in a sub dir.
UPSTREAM_DIR=${UPSTREAM_DIR:-upstream}			# For "tarball-and-patch" packages (see default_prep()). Default location of source tarballs.
PATCHES_DIR=${PATCHES_DIR:-patches}			# For "tarball-and-patch" packages (see default_prep()). Default location of patches.

EUPSPKG_SOURCE=${EUPSPKG_SOURCE:-package}
SOURCE=${SOURCE:-$EUPSPKG_SOURCE}			# [package|git|git-archive]. May be passed in via the environment, as EUPSPKG_SOURCE.

VERSION_PREFIX=${VERSION_PREFIX:-$EUPSPKG_VERSION_PREFIX}	# Prefix to be removed from $VERSION when inferring the corresponding git rev
VERSION_SUFFIX=${VERSION_SUFFIX:-$EUPSPKG_VERSION_SUFFIX}	# Suffix to be removed from $VERSION when inferring the corresponding git rev

REPOSITORY_PATH=${REPOSITORY_PATH:-"$EUPSPKG_REPOSITORY_PATH"}	# A '|'-delimited list of repository URL patterns (see resolve_repository() function)
REPOSITORY=${REPOSITORY:-}					# URL to git repository

MAKE_BUILD_TARGETS=${MAKE_BUILD_TARGETS:-}		# Targets for invocation of make in build phase
MAKE_INSTALL_TARGETS=${MAKE_INSTALL_TARGETS:-"install"}	# Targets for invocation of make in test phase

#
# If PRODUCTS_ROOT isn't set, set it from the first writeable element on EUPS_PATH
#
if [ X$PRODUCTS_ROOT = X ]; then
    for d in $(eups path); do
	PRODUCTS_ROOT="$d/$(eups flavor)"
	mkdir -p $PRODUCTS_ROOT &&
	    touch $PRODUCTS_ROOT/.foo > /dev/null 2>&1 &&
	    rm $PRODUCTS_ROOT/.foo &&
	    break
	unset PRODUCTS_ROOT
    done
fi

PRODUCTS_ROOT=${PRODUCTS_ROOT:-"$(eups path 0)/$(eups flavor)"}		# Root directory of EUPS-managed stack.
PREFIX=${PREFIX:-"$PRODUCTS_ROOT/$PRODUCT/$VERSION"}			# Directory to which the product will be installed

CONFIGURE_OPTIONS=${CONFIGURE_OPTIONS:-"--prefix \"$PREFIX\""}		# Options passed to ./configure. Note that --prefix is NOT passed separately!
# The following '--prefix=' is meant to clear any pre-set 'prefix' from a distutils.cfg or ~/.pydistutils.cfg
# We can only specify a value for either --home XOR --prefix, not both.
# So if we specify --home, we have to blank out --prefix:
# See, e.g.,   http://stackoverflow.com/questions/4495120/combine-user-with-prefix-error-with-setup-py-install
PYSETUP_INSTALL_OPTIONS=${PYSETUP_INSTALL_OPTIONS:-"--home \"$PREFIX\" --prefix="}	# Options passed to setup.py install. Note that --home is NOT passed separately!

export CC=${CC:-cc}				# Autoconf prefers to look for gcc first, and the proper thing is to default to cc. This helps on Darwin.
export CXX=${CXX:-c++}				# Autoconf prefers to look for gcc first, and the proper thing is to default to c++. This helps on Darwin.

export SCONSFLAGS=${EUPSPKG_SCONSFLAGS:-"opt=3"}	# Default scons flags

##################################################################
#
# In configurations with many cores, we can sometimes run into a
# limit on the number of processes (ulimit -u). When this happens,
# the build can terminate with hard-to-trace errors (e.g., see
# https://github.com/RobertLuptonTheGood/eups/issues/58. We'll try
# to defend agains this by pre-emptively raising the limit as far
# as we can (to the hard limit). As changing ulimits may be
# administratively prohibited, we won't treat failure as a fatal
# error.
#
ulimit -Su hard >/dev/null 2>&1 \
	&& info "maxproc limit (ulimit -Su) set to $(ulimit -Su)." \
	|| warn "failed to raise the maxproc limit (ulimit -Su); continuing with $(ulimit -Su)."

##################### ------ Overrides ----- #####################
#
# Source config/override files given via SCRIPTS/EUPSPKG_SCRIPTS
#

IFS=':' read -ra _SCRIPTS <<< "$SCRIPTS"
for _script in "${_SCRIPTS[@]}"; do
	if [[ -f "$_script" ]]; then
		info "sourcing '$_script'."
		. "$_script"
	elif [[ -z "$_script" ]]; then
		continue
	else
		die "script '$_script' listed on the SCRIPTS path does not exist."
	fi
done

#
# Dump the state of all key variables (helpful when debugging)
#
dumpvar debug PWD
dumpvar debug VERBOSE
dumpvar debug PRODUCT VERSION FLAVOR
dumpvar debug NJOBS UPSTREAM_DIR PATCHES_DIR SOURCE REPOSITORY REPOSITORY_PATH MAKE_BUILD_TARGETS MAKE_INSTALL_TARGETS
dumpvar debug BUILD_DIR
dumpvar debug PRODUCTS_ROOT PREFIX CONFIGURE_OPTIONS PYSETUP_INSTALL_OPTIONS
dumpvar debug REPOVERSION SHA1
dumpvar debug CC CXX SCONSFLAGS

#
# Run the commands
#
"$@"

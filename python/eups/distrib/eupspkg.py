#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package: a specialization for the "EupsPkg" mechanism
#
# Inspired by the builder.py and lssteups mechanisms by Robert Lupton, Ray
# Plante, and Paul Price.
#
# Maintainer:      Mario Juric <mjuric@lsst.org>
# Original author: Mario Juric <mjuric@lsst.org>
#

r"""
    EupsPkg is a packaging format and package distribution mechanism for
    software products managed by EUPS.  It generates packages ending in
    .eupspkg, similar to .rpm but centered around building from source rather
    than distributing binaries.  It organizes these into a ``distribution
    server'' directory structure, from which they can be installed into an
    EUPS-managed software stack using 'eups distrib install' (similar to
    yum).


    Quick start
    -----------

    EupsPkg packages can only be created from an already installed and
    declared product.  To create one for a product named 'foo' with version
    1.2.3, and release it to a distribution server in directory
    path/to/serverDir, run:

        eups distrib create foo 1.2.3 \
            --server-dir=path/to/serverDir \
            -f generic -d eupspkg \
            -S REPOSITORY_PATH='git://git.example.com/myrepos/$PRODUCT.git'
         
    Here, we assume the git repository at git.example.com/myrepos/foo.git
    contains the source of foo (and has a tag corresponding to the version,
    1.2.3).  The resulting package, named foo-1.2.3.eupspkg and residing in
    path/to/serverDir/products, will contain the sources and all information
    needed to build foo 1.2.3. If foo has any dependencies, EupsPkg packages
    will be created for those as well.

    For the end-user, installing the generated product (and its
    dependencies) should be as easy as setting EUPS_PKGROOT to point to the
    distribution server, and running `eups distrib install', e.g.:
    
        eups distrib install foo 1.2.3


    EupsPkg knows how to build autoconf (i.e., ./configure), make, scons,
    and Python distutils driven products.  Customization of the
    configuration or build process is typically done via the
    ./ups/eupspkg.cfg.sh file (where the leading dot refers to the root
    directory of the product).  For example, having the following:

       ================================================================
       # EupsPkg config file. Sourced by 'eupspkg'

       CONFIGURE_OPTIONS="--prefix=$PREFIX --disable-shared"
       export CFLAGS="$CFLAGS -fPIC"
       ================================================================

    in ./ups/eupspkg.cfg.sh will add --disable-shared to `./configure' command
    line, and make sure that the sources are built with -fPIC.  For a complete
    list of variables one can override, see the bottom of
    $EUPS_DIR/lib/eupspkg.sh file.


    If your product uses an unsupported build system, or needs more complex
    customizations than enabled by simple variable modifications, read more
    below to learn about ./ups/eupspkg.cfg.sh scripts.

    Or, if you prefer to learn by example, look at ./ups/eupspkg.cfg.sh
    scripts in various repositories at:

        https://dev.lsstcorp.org/cgit/LSST/external


    Overview
    --------

    EupsPkg packages are free-formed gzipped tarballs ending in .eupspkg. 
    They carry all information necessary to install a specific EUPS product
    by building it from source.  They may include the source code itself, or
    information on how to fetch it from a (possibly remote) repository.


    When an EupsPkg package is being installed via 'eups distrib install',
    EUPS downloads and unpacks the tarball it into a temporary directory
    (hereafter called $pkgdir).  There, a file named ./ups/eupspkg is
    searched for, and used to fetch, prepare, configure, build and install
    the product.  If the packager hasn't provided one, a default
    implementation is used (residing in $EUPS_DIR/lib/eupspkg.sh); it
    already knows how to build and install products using the most frequent
    build systems (e.g., autoconf+make, make, scons; see below for details),
    but its functionality can be further customized and fine-tuned via a
    ./ups/eupspkg.cfg.sh bash script, which it will source.

    When provided, ./ups/eupspkg must be executable and define "verbs"
    invocable as:
    
       ./ups/eupspkg [KEY1=VAL1 [KEY2=VAL2 [...]]] <verb>

    . The information about the package being created or installed is passed
    to the script by EUPS via KEY=VAL keyword arguments on the command line. 
    The keyword arguments guaranteed to be present on invocation depend on
    the verb, and are further discussed later in this text.  For forwards
    compatibility, a verb implementation must ignore any unrecognized
    keyword arguments.


    For EUPS to be able to install the product from the package, the
    following verbs must be implemented:

       fetch     -- obtain the source code for the product
       prep      -- prepare the source code (e.g., apply patches)
       config    -- configure the source code for build
       build     -- build the product
       install   -- install the binary to its destination

    These are invoked by EUPS, in sequence, from $pkgdir. They must expect
    no named arguments.  For all verbs, EUPS will setup any dependent
    products (obtained from the manifest file) before they're called.  For
    'config', 'build', and 'install', the product being installed will
    itself be additionally setup-ed (i.e., `setup --type=build -k -r .' will
    be executed in $pkgdir).  The eupspkg script must never manipulate the
    EUPS environment on its own, nor declare the product to EUPS upon
    successful completion of installation (both have the potential to
    interfere with locking).  Note that this is different from current
    custom in builder.py's build scripts.

    During `eups distrib install', all invocations of eupspkg occur from an
    auto-generated Bash script named $pkgdir/../build.sh and the results are
    logged to $pkgdir/../build.log.  In case of build problems, the end-user
    can inspect, edit, and rerun build.sh (as well as $pkgdir/ups/eupspkg) as
    necessary.



    To support package creation, the eupspkg script must provide a verb
    named 'create'. It will be invoked by 'eups distrib create' as:

       eupspkg PRODUCT=.. VERSION=.. FLAVOR=.. PREFIX=.. [OPTARGS] create

    to create the contents of the package. It will be invoked from an empty
    temporary directory (hereafter, $pkgdir).  It must copy or otherwise
    generate all files required to be included in the package (including
    ./ups/eupspkg, presumably just a copy of itself).
    
    The arguments to `eupspkg create' are as follows:

       $PRODUCT   -- product name, as given to eups distrib create
       $VERSION   -- product version, as given to eups distrib create
       $FLAVOR    -- product flavor, as given to eups distrib create
       $PREFIX    -- installed product directory

    OPTARGS stands for any KEY=VAL arguments passed via the '-S' option to
    `eups distrib create'.  Two are used often:

       $SOURCE    -- implementation-specific mechanism to retrieve the 
                     product source (e.g., from git, or include it inline,
                     etc.)
       $VERBOSE   -- implementation-specific verbosity level


    Once 'eupspkg create' returns, the contents of $pkgdir is tarballed by
    EUPS and stored to serverDir as $product-$version.eupspkg extension. 
    Metadata (the manifest as well as the table file) are stored to the
    server as well.

    EupsPkg distribution servers have the following structure:
    
       /+-- config.txt  -- distribution server configuration
        |-- products    -- directory with .eupspkg packages
        |-- tags        -- directory with .list files (EUPS tags)
        |-- tables      -- directory of .table files, one per package
        \-- manifests   -- directory of manifests, one per package

    Standard .list files are used to capture tag information.


    eupspkg.sh: the default verb implementation
    -------------------------------------------

    The above requirements on verbs which must be present are all that is
    required of eupspkg scripts.  The creation and building of packages, as
    well as interpretation of additional arguments, such as $SOURCE or
    $VERBOSE, is completely under the eupspkg script's control.  EUPS has no
    awareness of package contents, beyond assuming './ups/eupspkg' is the
    ``entry point'' for package creation and product installs.
    
    This allows for high degree of customization, as the ./ups/eupspkg
    script that the packager may provide is free to internally organize the
    package as it sees fit, or implement different methods of obtaining the
    source (e.g., include it in the package, keep a pointer to a location on
    the web, or a location in a version control system).  Specifically, note
    that there's no requirement that this "eupspkg script" is a shell
    script, as long as it's executable on the end-user's system (e.g., it
    could be written in Python).
    
    In practice, as the number of build systems commonly in use is small. 
    Furthermore, as most adhere to accepted conventions (e.g.,
    "./configure"/"make"/"make install" idioms for autoconf, etc.), a
    reasonable, base, default, eupspkg script can be written that works for
    most products out of the box and can be extended to support others. 
    EupsPkg provides such a default, extensible, implementation, written in
    bash.  This greatly simplify the writing of custom eupspkg scripts, and,
    in a number of cases, obviates the need for them entirely.

    The default eupspkg implementation can be found in:
    
       $EUPS_DIR/lib/eupspkg.sh

    It is guaranteed to be present on any system running EUPS more recent
    than 1.3.0, and will be used automatically if the packager doesn't
    provide ./ups/eupspkg.  This enables completely non-intrusive builds of
    packages for products that eupspkg.sh knows to build.

    The default implementation can be customized on a per-product basis by
    providing a:

       ./ups/eupspkg.cfg.sh

    script in the package. This script will be sourced by eupspkg.sh
    just before the verbs are executed, and can be used to customize them as
    appropriate.  For example, a typical eupspkg.cfg.sh script customizing
    the default implementation may appear as follows:

       ================================================================
       # EupsPkg config file. Sourced by 'eupspkg'

       # ... verb or variable overrides, e.g.:
       CONFIGURE_OPTIONS="--prefix=$PREFIX --disable-shared"
   
       ================================================================

    The script above overrides the CONFIGURE_OPTIONS variable to add the
    --disable-shared flag to it. See $EUPS_DIR/lib/eupspkg.cfg.sh for a list
    of variables that can be overridden (look near the bottom of the file).

    Similarly, the behavior can be customized on a site-wide basis by
    providing a :-delimited list of scripts to source in an EUPSPKG_SCRIPTS
    environment variable. E.g.:
    
       EUPSPKG_SCRIPTS="/a/b/custom1.sh:/b/c/custom2.sh:..."
       
    These will be sourced, in sequence, just before ./ups/eupspkg.cfg.sh is
    sourced.


    eupspkg.sh: implementation of 'create'
    --------------------------------------

    The default implementation of 'create' builds a package that contains
    the source code in tself (default).  Alternatively, it can be instructed
    to record (in ./ups/pkginfo) the URL to a git repository and the
    associated commit SHA1 that can be used to fetch the source at
    install-time.

    The following variables, passed via the '-S' option to 'eups distrib
    create', may be used to control aspects package creation:
    
       SOURCE           -- select the source fetching mechanism

       REPOSITORY_PATH  -- '|'-delimited list of patterns used to construct
                           git repository URLs (default: "")

    These variables can also be set in the environment, but have to be
    prefixed with EUPSPKG_ when so (e.g., EUPSPKG_REPOSITORY_PATH,
    EUPSPKG_SOURCE, etc.).

    The default create verb implementation interprets the SOURCE variable as
    the mechanism by which the source code will be obtained when the package
    is installed.  The following are presently defined:
    
       git-archive  -- use 'git archive' to fetch the source. The $VERSION
                       will be interpreted[*] as a named git ref (tag or
                       branch name) to be checked out.  Note that
                       git-archive can't be used to fetch the source by SHA1
                       or by the result of git describe; a true named ref
                       must be used.

       git          -- use 'git clone' to fetch the source. The $VERSION
                       is interpreted[*] as for git-archive, but any ref
                       parsable by git will work.  Note that this is less
                       efficient since the whole git repository needs to be
                       checked out.  If SHA1=....  argument is given (or
                       present in ./ups/pkginfo of the installed product),
                       it will be used instead of the version.

       package      -- the source is to be included in the package. This is
                       optimal from the user's point of view, since it
                       removes dependencies on git executable or repository
                       to install the package.  Note that git is still used
                       to obtain the source when the package is being
                       created.

       [*] footnote: there is some minimal parsing of $VERSION, such as
           removal of +XXX prefixes (if any), to attempt to convert it to a
           valid git ref. See version_to_gitrev() function for details.

    The ability to define SOURCE at package creation time is quite
    powerful.  It allows one to easily switch from remote git-archive to
    local source storage, or mix-and-match different mechanisms to different
    products.  For example, if a product contains gigabytes of test data, it
    may be better to keep them in a git repository than to have potentially
    hundreds of minimally differing tarballed copies on the distribution
    server.

    The source code of an installed package must be obtained from somewhere;
    `eupspkg create' needs an URL to its git repository.  This URL is
    resolved at `eups distrib create' time from the REPOSITORY_PATH
    argument.  The $REPOSITORY_PATH is a '|'-delimited list of patterns
    expanding to repositories where the source may be found.  An example of
    a typical invocation is as follows:
 
       eups distrib create .... \
         -S REPOSITORY_PATH='git://server1/dir1/$PRODUCT|git://server2/dir2/$PRODUCT'

    or, more commonly:

       export EUPSPKG_REPOSITORY_PATH='git://server1/dir1/$PRODUCT|git://server2/dir2/$PRODUCT'
       eups distrib create ....

    Elements of the path are separated by | (instead of the usual colon). 
    Also note how the path has been enclosed in single quotes, to prevent
    variable expansion on the command line, and the interpretation of |
    by the shell.

    `eupspkg create' will construct a candidate URL from each element of
    $REPOSITORY_PATH, and test for its existence until a matching one is
    found.  The matching URL will be used to obtain the source code for the
    installed product.

    Instead of using matching via $REPOSITORY_PATH, the repository URL can
    be embedded into the eupspkg.cfg.sh file by setting a variable named
    REPOSITORY.  This is more intrusive and often less flexible than the
    REPOSITORY_PATH method.  If both are specified, REPOSITORY_PATH will
    always take precedence.


    All together, a typical invocation of 'eups distrib create' using the
    built-in create verb implementation is therefore:

       export EUPSPKG_REPOSITORY_PATH='....'

       eups distrib create base 7.3.1.1 \
          --server-dir=...serverDir... \
          -f generic -d eupspkg \
          -S SOURCE=git

    If '-S SOURCE' was not given, 'package' would be the default.

    The default create verb implementation uses this information from the
    command line to construct the package.  It also saves any information
    needed to later build it (e.g., the $SHA1, or the resolved $REPOSITORY)
    to ./ups/pkginfo in the package itself.  To restore it, this file is
    sourced by eupspkg.sh at 'eups distrib install' time (see the note about
    the sequence of variable loading near the end of this text).
    

    eupspkg.sh: implementations of install-time verbs
    -------------------------------------------------

    At install time, the default verb implementations will try to detect the
    build system (in the order given below), and handle it as follows:
    
       scons       -- if 'SConstruct' exists in package root, assume the
                      build system is scons. Run 'scons opt=3 prefix=$PREFIX
                      version=$VERSION' to build.
       autoconf    -- if 'configure' exists in package root, assume the
                      build system is autoconf. Run `./configure' in config
                      verb, `make' in build(), and `make install' in install().
       make        -- if 'Makefile' exists in package root, assume the build
                      is driven by simple makefiles. Run `make
                      prefix=$PREFIX' in build() and `make prefix=$PREFIX
                      install' to install.
       distutils   -- if 'setup.py' exists in package root, run `python
                      setup.py' to build and `python setup.py install' to
                      install.
       <default>   -- if no other build system is detected, assume there's
                      nothing to build. Simply copy the source directory to
                      the install directory ($PREFIX).

       TaP         -- the "tarball-and-patch" package; if a directory named
                      'upstream' exists in package root (and no other files
                      are found there or the file ".tap_package" exists),
                      extract any tarballs from 'upstream' and apply any
                      patches found in 'patches', before proceeding to
                      autodetect the build system as described above.

                      This is useful for packages created out of git
                      repositories that are just containers for external
                      packages. Since git doesn't preserve timestamps, it's
                      better to keep these as tarballs + a series of patches
                      (otherwise, automake may try to regenerate ./configure
                      due to timestamp mismatches). It is similar to how
                      sources are stored in source RPMs.

    The default install() verb will copy the ups/ directory to the
    destination directory, and expand the table file using 'eups
    expandtable'. If install() is overridden by the user, and this behavior
    is still desired, call install_ups() from your override.

    Default implementation of prep() does TaP package detection and
    extraction.
    
    For details, and before writing customizations of their own, the
    packagers are *strongly* advised to learn from the implementations of
    these and other verbs in $EUPS_DIR/lib/eupspkg.sh.


    Customizing the behavior of eupspkg.sh
    --------------------------------------

    The behavior of the default implementation is customized on a
    per-package basis by providing a ./ups/eupspkg.cfg.sh script. This script
    will be sourced just before the requested verb is invoked.

    Two types of custiomizations are available via ./ups/eupspkg.cfg.sh:
    setting variables that the default verb implementations use, or
    providing all together new implementations of the verbs themselves (Bash
    functions).  Unless the build process is complex, overriding the
    variables is usually sufficient to achieve the desired customization.

    For the full list of variables that can be overridden, see the bottom of
    the $EUPS_DIR/lib/eupspkg.cfg.sh file, as well as the implementations of
    the verbs.  Here we only list a few of the more commonly used ones:
    
       $REPOSITORY              -- The URL to git repository with the
                                   source. Can use any protocol git
                                   understands (e.g. git://, http://, etc.).
                                   If not specified, $REPOSITORY_PATH must
                                   be passed in via the -S option to `eups
                                   distrib create' to be be searched for a
                                   match (this is the recommended usage).
       $CONFIGURE_OPTIONS       -- Options to be passed to ./configure (if
                                   autoconf is in used). Default:
                                   "--prefix=$PREFIX". If you override this,
                                   don't forget to explicitly specify
                                   --prefix!
       $MAKE_BUILD_TARGETS      -- Targets to make in build step (if 
                                   Makefiles are in use). Not set by
                                   default.
       $MAKE_INSTALL_TARGETS    -- Targets to pass to make in install step.
                                   Default: "install".
       $PYSETUP_INSTALL_OPTIONS -- Options to pass to setup.py in install
                                   step. Default: "--prefix $PREFIX".

    As mentioned, the verbs themselves can also be overridden. For example,
    the eupspkg.cfg.sh file for Boost C++ library overrides the config verb
    as follows:
    
       ================================================================
       config()
       {
           detect_compiler
       
           if [[ "$COMPILER_TYPE" == clang ]]; then
               WITH_TOOLSET="--with-toolset clang"
           fi

           ./bootstrap.sh --prefix="$PREFIX" $WITH_TOOLSET
       }
       ================================================================

    This configures the Boost build system and passes it the correct toolset
    options if running with the clang compiler.  detect_compiler() is a
    utility function defined in eupspkg.sh, defining $COMPILER_TYPE based
    on the detected compiler.  See the source code of the library for the
    list of available functions and their typical usage. 

    There are many other subroutines and options that are present in the
    function library but not documented here.  Browse through the library
    code to get a feel for it. Functions beginning with an underscore ('_')
    are considered internal, may change from release to release, and are not
    be used.


    Development Support
    -------------------

    For developer convenience, an executable named 'eupspkg' is provided
    with EUPS (it's in $EUPS_DIR/bin, and therefore on your path when EUPS
    is setup-ed).  It's a thin wrapper that dispatches the invocation to
    ./ups/eupspkg if it exists, and to $EUPS_DIR/lib/eupspkg.sh
    otherwise.  It gives the developer the convenience of being able to
    write:
    
       eupspkg PRODUCT=a VERSION=b FLAVOR=c config
       
    in the root product directory, and be confident that it will work
    irrespective of whether ./ups/eupspkg or the default eupspkg
    implementation is being used.  This script supports the -h switch (to
    get help), the -v switch (to set verbosity), and a few others, described
    below.


    To assist the development of eupspkg.cfg.sh scripts, eupspkg.sh
    provides a 'developer mode', activated by the -e command line switch. 
    When run in developer mode, eupspkg must be invoked from the root of the
    setup-ed product source code, i.e.:

        [mjuric@gamont pex_config]$ setup -r .
        [mjuric@gamont pex_config]$ eupspkg -e create

    When developer mode is active:
    
        * if PRODUCT, VERSION or FLAVOR are not set, they're autodetected
          from git. The PRODUCT is deduced from the name of the 'origin'
          remote, and VERSION is similar to the output of git describe.
          FLAVOR is currently set to 'generic'.

        * when 'create' is invoked in developer mode, it will be run (and
          the EupsPkg package contents will be created) in the
          ./_eupspkg/source subdirectory.  The PREFIX will be set to the
          source directory.
          
          Note: you only need to run 'create' to test actual package
          creation. To just build the checked out (and potentially modified)
          source tree, you can start with 'fetch' (see examples below).

        * for all other verbs:
          + the PREFIX (the location to which the package
            will be installed to) will be set to ./_eupspkg/binary. This can
            be overridden with -r switch, in which case the PREFIX will be
            set to EUPS' root (i.e., where it would ordinarily be
            installed).
          + for any verb that is invoked, eupspkg.sh will check if
            ./_eupspkg/source exists, and immediately chdir to it before
            continuing execution.  This way, a throw-away test build can
            easily be made w/o polluting the source environment.
          
        * a 'decl' verb is made available, that declares an installed
          package to EUPS (and tags it, if asked).

    All together, these enable the following workflow where the package
    creation and install can be safely tested prior to installing it into a
    real EUPS stack:

        [mjuric@gamont cfitsio]$ git log --decorate --abbrev-commit
        commit 322df44 (HEAD, tag: 3310, origin/master, master)
        Author: Mario Juric <mjuric@lsst.org>
        Date:   Sun Dec 29 04:48:05 2013 -0600

        Renamed pkgbuild to eupspkg
        ...

        [mjuric@gamont cfitsio]$ setup  -r .

        # as noted above, you can skip 'create' if you're testing a
        # local working copy of the source that you haven't yet committed
        # or pushed.
        [mjuric@gamont cfitsio]$ eupspkg -e create
        eupspkg.create: package contents created for 'cfitsio-3310', sources
        will be fetched via 'package'.

        [mjuric@gamont cfitsio]$ eupspkg -e fetch
        ...

        [mjuric@gamont cfitsio]$ eupspkg -e prep
        ....

        [mjuric@gamont cfitsio]$ eupspkg -e config
        ....

        [mjuric@gamont cfitsio]$ eupspkg -e build
        ....

        [mjuric@gamont cfitsio]$ eupspkg -e install
        ....

        [mjuric@gamont cfitsio]$ du _eupspkg
        208     _eupspkg/binary/cfitsio/3310/include
        20      _eupspkg/binary/cfitsio/3310/ups
        8       _eupspkg/binary/cfitsio/3310/lib/pkgconfig
        9560    _eupspkg/binary/cfitsio/3310/lib
        9792    _eupspkg/binary/cfitsio/3310
        9796    _eupspkg/binary/cfitsio
        9800    _eupspkg/binary
        20      _eupspkg/source/ups
        4572    _eupspkg/source/upstream
        4596    _eupspkg/source
        14400   _eupspkg/

    Alternatively, one can use 'config', 'build', and 'install' verbs to
    build a package inline. This way, one is using eupspkg as an abstraction
    of the underlying build system (i.e., `eupspkg -e build' will build the
    source irrespective of whether make or scons are being used natively):

        [mjuric@gamont pex_config]$ rm -rf _eupspkg

        [mjuric@gamont pex_config]$ setup -r .

        [mjuric@gamont pex_config]$ eupspkg -e  build
        scons: Reading SConscript files ...
        Checking who built the CC compiler...(cached) gcc
        Checking for C++ header file tr1/unordered_map... (cached) yes
        Setting up environment to build package 'pex_config'.
        Ignoring prefix /ssd/mjuric/eupspkg/stack/Linux64/pex_config/7.3.1.0 from EUPS_PATH
        Checking whether int64_t is long ... (cached) yes
        scons: done reading SConscript files.
        scons: Building targets ...
        scons: Nothing to be done for `python'.
        buildConfig(["doc/doxygen.conf"], ["doc/doxygen.conf.in"])
        doxygen /ssd/mjuric/eupspkg/sources/pex_config/doc/doxygen.conf
        scons: `tests' is up to date.
        scons: done building targets.

        [mjuric@gamont pex_config]$ eupspkg -e install
        ... same as output for build ...
        buildConfig(["doc/doxygen.conf"], ["doc/doxygen.conf.in"])
        doxygen /ssd/mjuric/eupspkg/sources/pex_config/doc/doxygen.conf
        Install file: "ups/pex_config.cfg" as
        "_eupspkg/binary/pex_config/7.3.1.0/ups/pex_config.cfg"
        Install file: "ups/pex_config.table" as
        "_eupspkg/binary/pex_config/7.3.1.0/ups/pex_config.table"
        DirectoryInstaller(["_eupspkg/binary/pex_config/7.3.1.0/include"], ["include"])
        Install file: "ups/pex_config.build" as "_eupspkg/binary/pex_config/7.3.1.0/ups/pex_config.build"
        DirectoryInstaller(["_eupspkg/binary/pex_config/7.3.1.0/python"], ["python"])
        DirectoryInstaller(["_eupspkg/binary/pex_config/7.3.1.0/tests"], ["tests"])
        eups expandbuild -i --version 7.3.1.0
        _eupspkg/binary/pex_config/7.3.1.0/ups/pex_config.build
        eups expandtable -i -W '^(?!LOCAL:)'
        _eupspkg/binary/pex_config/7.3.1.0/ups/pex_config.table
        DirectoryInstaller(["_eupspkg/binary/pex_config/7.3.1.0/doc"], ["doc"])
        scons: done building targets.

    Note the install directory is still _eupspkg/binary; we're very careful
    not to pollute the real product stack.  If the build/install had the -r
    flag specified, the install destination would be the EUPS product stack
    root.
    
    If that was the case, we could run:
    
        [mjuric@gamont pex_config]$ eupspkg -e decl -t current
        
    to declare the package to EUPS and tag it as 'current'.

    Appendix: Echoing messages to console
    -------------------------------------
    
    To echo a message to console, redirect it to file descriptor 4.
    
    When 'eupspkg distrib install' is run, all output by ups/eupspkg (to
    stdout and stderr; fds 0 and 2) is redirected to a log file and is not
    shown to the user unless there's an error.  If you want to show a
    message to a user, echo it to file description 4. To make this easier,
    eupspkg.sh provides an eups_console() function to be used as:
    
        echo "The user will see this message" | eups_console


    Appendix: Sequence of variable loading
    --------------------------------------

    eupspkg.sh is internally driven by variables such as PRODUCT, VERSION,
    etc.  As these can come from several sources, it's important to
    understand the sequence in which they apply.  The variables are
    logically loaded in the following order:

        1.) Defaults from $EUPS_DIR/lib/eupspkg.sh
        2.) EUPSPKG_-prefixed variables from the environment
        3.) Variables defined in ./ups/pkginfo
        4.) Variables passed as command line KEY=VAL arguments
        5.) Variables set in ./ups/eupspkg.cfg.sh

    and the latter ones override the former.

"""

import sys, os, shutil, tarfile, tempfile, pipes, stat
import eups
import Distrib as eupsDistrib
import server as eupsServer
import eups.hooks


class Distrib(eupsDistrib.DefaultDistrib):
    """A class to implement product distribution based on packages
    ("EupsPkg packages") constructed by builder scripts implementing 
    verbs not unlike RPM's %xxxx macros.
    """

    NAME = "eupspkg"
    PRUNE = True

    def __init__(self, Eups, distServ, flavor=None, tag="current", options=None,
                 verbosity=0, log=sys.stderr):
        eupsDistrib.Distrib.__init__(self, Eups, distServ, flavor, tag, options,
                                     verbosity, log)

        self._msgs = {}

        self.nobuild = self.options.get("nobuild", False)
        self.noclean = self.options.get("noclean", False)

        # Allow the verbosity of eupspkg script to be set separately.
        if "verbose" not in self.options:
            self.options["verbose"] = str(Eups.verbose)

        # Prepare the string with all unrecognized options, to be passed to eupspkg on the command line
        # FIXME: This is not the right way to do it. -S options should be preserved in a separate dict()
        knownopts = set(['config', 'nobuild', 'noclean', 'noaction', 'exact', 'allowIncomplete', 'buildDir', 'noeups', 'installCurrent']);
        self.qopts = " ".join( "%s=%s" % (k.upper(), pipes.quote(str(v))) for k, v in self.options.iteritems() if k not in knownopts )

    # @staticmethod   # requires python 2.4
    def parseDistID(distID):
        """Return a valid package location if and only we recognize the 
        given distribution identifier

        This implementation return a location if it starts with "eupspkg:"
        """
        if distID:
            prefix = "eupspkg:"
            distID = distID.strip()
            if distID.startswith(prefix):
                return distID[len(prefix):]

        return None

    parseDistID = staticmethod(parseDistID)  # should work as of python 2.2

    def initServerTree(self, serverDir):
        """initialize the given directory to serve as a package distribution
        tree.
        @param serverDir    the directory to initialize
        """
        eupsDistrib.DefaultDistrib.initServerTree(self, serverDir)

        config = os.path.join(serverDir, eupsServer.serverConfigFilename)
        if not os.path.exists(config):
            configcontents = """\
# Configuration for a EupsPkg-based server
DISTRIB_CLASS = eups.distrib.eupspkg.Distrib
EUPSPKG_URL = %(base)s/products/%(path)s
LIST_URL = %(base)s/tags/%(tag)s.list
TAGLIST_DIR = tags
"""
            cf = open(config, 'a')
            try:
                cf.write(configcontents)
            finally:
                cf.close()

        # Create the tags storage directory
        tagsDir = os.path.join(serverDir, 'tags')
        if not os.path.exists(tagsDir):
                os.mkdir(tagsDir)


    def getTaggedReleasePath(self, tag, flavor=None):
        """get the file path relative to a server root that will be used 
        store the product list that makes up a tagged release.
        @param tag        the name of the tagged release of interest
        @param flavor         the target flavor for this release.  An 
                                  implementation may ignore this variable.  
        """
        return "tags/%s.list" % tag

    def getManifestPath(self, serverDir, product, version, flavor=None):
        """return the path where the manifest for a particular product will
        be deployed on the server.  In this implementation, all manifest 
        files are deployed into a subdirectory of serverDir called "manifests"
        with the filename form of "<product>-<version>.manifest".  Since 
        this implementation produces generic distributions, the flavor 
        parameter is ignored.

        @param serverDir      the local directory representing the root of 
                                 the package distribution tree.  In this 
                                 implementation, the returned path will 
                                 start with this directory.
        @param product        the name of the product that the manifest is 
                                for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform for the 
                                manifest.  This implementation ignores
                                this parameter.
        """
        return os.path.join(serverDir, "manifests", 
                            "%s-%s.manifest" % (product, version))

    def createPackage(self, serverDir, product, version, flavor=None, overwrite=False):
        """Write a package distribution into server directory tree and 
        return the distribution ID 
        @param serverDir      a local directory representing the root of the 
                                  package distribution tree
        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation
        @param overwrite      if True, this package will overwrite any 
                                previously existing distribution files even if Eups.force is false
        """
        distid = self.getDistIdForPackage(product, version)
        distid = "eupspkg:%s-%s.eupspkg" % (product, version)

        # Make sure it's an absolute path
        serverDir = os.path.abspath(serverDir)

        (baseDir, productDir) = self.getProductInstDir(product, version, flavor)
        eupspkg = os.path.join(baseDir, productDir, "ups", "eupspkg")
        if not os.path.exists(eupspkg):
            # Use the defalt build file
            eupspkg = os.path.join(os.environ["EUPS_DIR"], 'lib', 'eupspkg.sh')

        # Construct the package in a temporary directory
        pkgdir0 = tempfile.mkdtemp(suffix='.eupspkg')
        prodSubdir = "%s-%s" % (product, version)
        pkgdir = os.path.join(pkgdir0, prodSubdir)
        os.mkdir(pkgdir)

        q = pipes.quote
        try:
            # Execute 'eupspkg <create>'
            cmd = ("cd %(pkgdir)s && " + \
                "%(eupspkg)s   PREFIX=%(prefix)s PRODUCT=%(product)s VERSION=%(version)s FLAVOR=%(flavor)s %(qopts)s" + \
                " create") % \
                    {
                      'pkgdir':   q(pkgdir),
                      'prefix':   q(os.path.join(baseDir, productDir)),
                      'product':  q(product),
                      'version':  q(version),
                      'flavor':   q(flavor),
                      'eupspkg':  q(eupspkg),
                      'qopts':    self.qopts,
                    }
            eupsServer.system(cmd)

            # Tarball the result and copy it to $serverDir/products
            productsDir = os.path.join(serverDir, "products")
            if not os.path.isdir(productsDir):
                try:
                    os.makedirs(productsDir)
                except:
                    raise RuntimeError, ("Failed to create %s" % (productsDir))

            tfn = os.path.join(productsDir, "%s-%s.eupspkg" % (product, version))
            if os.path.exists(tfn) and not (overwrite or self.Eups.force):
                if self.Eups.verbose > 1:
                    print >> self.log, "Not recreating", tfn
                return distid

            if not self.Eups.noaction:
                if self.verbose > 1:
                    print >> self.log, "Writing", tfn

                try:
                    cmd = 'cd %s && tar czf %s %s' % (q(pkgdir0), q(tfn), q(prodSubdir))
                    eupsServer.system(cmd)
                except OSError, e:
                    try:
                        os.unlink(tfn)
                    except OSError:
                        pass                        # probably didn't exist
                    raise RuntimeError ("Failed to write %s: %s" % (tfn, e))
        finally:
            shutil.rmtree(pkgdir0)

        return distid

    def getDistIdForPackage(self, product, version, flavor=None):
        """return the distribution ID that for a package distribution created
        by this Distrib class (via createPackage())
        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation.  None means
                                that a non-flavor-specific ID is preferred, 
                                if supported.
        """
        return "eupspkg:%s-%s.eupspkg" % (product, version)

    def packageCreated(self, serverDir, product, version, flavor=None):
        """return True if a distribution package for a given product has 
        apparently been deployed into the given server directory.  
        @param serverDir      a local directory representing the root of the 
                                  package distribution tree
        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation.  None means
                                that the status of a non-flavor-specific package
                                is of interest, if supported.
        """
        location = self.parseDistID(self.getDistIdForPackage(product, version, flavor))
        return os.path.exists(os.path.join(serverDir, "products", location))

    def installPackage(self, location, product, version, productRoot, 
                       installDir, setups=None, buildDir=None):
        """Install a package with a given server location into a given
        product directory tree.
        @param location     the location of the package on the server.  This 
                               value is a distribution ID (distID) that has
                               been stripped of its build type prefix.
        @param productRoot  the product directory tree under which the 
                               product should be installed
        @param installDir   the preferred sub-directory under the productRoot
                               to install the directory.  This value, which 
                               should be a relative path name, may be
                               ignored or over-ridden by the pacman scripts
        @param setups       a list of EUPS setup commands that should be run
                               to properly build this package.  This is usually
                               ignored by the pacman scripts.
        """

        pkg = location
        if self.Eups.verbose >= 1:
            print >> self.log, "[dl]",; self.log.flush()
        tfname = self.distServer.getFileForProduct(pkg, product, version,
                                                   self.Eups.flavor,
                                                   ftype="eupspkg", 
                                                   noaction=self.Eups.noaction)

        logfile = os.path.join(buildDir, "build.log") # we'll log the build to this file
        uimsgfile = os.path.join(buildDir, "build.msg") # messages to be shown on the console go to this file

        # Determine temporary build directory
        if not buildDir:
            buildDir = self.getOption('buildDir', 'EupsBuildDir')
        if self.verbose > 0:
            print >> self.log, "Building package: %s" % pkg
            print >> self.log, "Building in directory:", buildDir
            print >> self.log, "Writing log to: %s" % (logfile)

        if self.Eups.noaction:
            print >> self.log, "skipping [noaction]"
            return

        # Make sure the buildDir is empty (to avoid interference from failed builds)
        shutil.rmtree(buildDir)
        os.mkdir(buildDir)

        # Construct the build script
        q = pipes.quote
        try:
            buildscript = os.path.join(buildDir, "build.sh")
            fp = open(buildscript, 'w')
            try:
                fp.write("""\
#!/bin/bash
# ----
# ---- This script has been autogenerated by 'eups distrib install'.
# ----

set -xe
cd %(buildDir)s

# make sure the EUPS environment is set up
. "$EUPS_DIR/bin/setups.sh"

# sanitize the environment: unsetup any packages that were setup-ed
#
# NOTE: this has been disabled as there are legitimate reasons to have EUPS
# packages other than the explicit dependencies set up (i.e., compilers,
# different version of git, etc.)
#
# for pkg in $(eups list -s | cut -d' ' -f 1); do
#     unsetup -j "$pkg"
# done

# Unpack the eupspkg tarball
tar xzvf %(eupspkg)s

# Enter the directory unpacked from the tarball
PKGDIR="$(find . -maxdepth 1 -type d ! -name ".*" | head -n 1)"
test ! -z $PKGDIR
cd "$PKGDIR"

# If ./ups/eupspkg is not present, symlink in the default
if [[ ! -e ./ups/eupspkg ]]; then
    mkdir -p ./ups
    ln -s "$EUPS_DIR/lib/eupspkg.sh" ups/eupspkg
fi

# eups setup the dependencies
%(setups)s

# show what we're running with (for the log file)
eups list -s

# fetch package source
( ./ups/eupspkg %(qopts)s fetch ) || exit -1

# prepare for build (e.g., apply platform-specific patches)
( ./ups/eupspkg %(qopts)s prep  ) || exit -2

# setup the package being built. note we're using -k
# to ensure setup-ed dependencies aren't overridden by
# the table file. we could've used -j instead, but then
# 'eups distrib install -j ...' installs would fail as 
# these don't traverse and setup the dependencies.
setup --type=build -k -r .

# configure, build, and install
( ./ups/eupspkg %(qopts)s config  ) || exit -3
( ./ups/eupspkg %(qopts)s build   ) || exit -4
( ./ups/eupspkg %(qopts)s install ) || exit -5
"""                 % {
                        'buildDir' : q(buildDir),
                        'eupspkg' : q(tfname),
                        'setups' : "\n".join(setups),
                        'product' : q(product),
                        'version' : q(version),
                        'qopts' : self.qopts,
                      }
                )
            finally:
                fp.close()

            # Make executable (equivalent of 'chmod +x $buildscript')
            st = os.stat(buildscript)
            os.chmod(buildscript, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            #
            # Did they ask to have group permissions honoured?
            #
            self.setGroupPerms(buildDir + "*")

            # Run the build
            cmd = "(%s) >> %s 2>&1 4>%s" % (q(buildscript), q(logfile), q(uimsgfile))
            if not self.nobuild:
                if self.Eups.verbose >= 1:
                    print >> self.log, "[build]",; self.log.flush()
                eupsServer.system(cmd, self.Eups.noaction)

                # Copy the build log into the product install directory. It's useful to keep around.
                installDirUps = os.path.join(self.Eups.path[0], self.Eups.flavor, product, version, 'ups')
                if os.path.isdir(installDirUps):
                    shutil.copy2(logfile, installDirUps)
                    if self.verbose > 0:
                        print >> self.log, "Build log file copied to %s/%s" % (installDirUps, os.path.basename(logfile))
                else:
                    print >> self.log, "Build log file not copied as %s does not exist (this shouldn't happen)." % installDirUps

                # Echo any lines from "messages" file
                # TODO: This should be piped in real time, not written out to a file and echoed.
                if os.path.getsize(uimsgfile) > 0:
                    print >> self.log, ""
                    fp = open(uimsgfile)
                    for line in fp:
                        self.log.write("             %s" % line)
                    fp.close()

        except OSError, e:
            if self.verbose >= 0 and os.path.exists(logfile):
                try: 
                    print >> self.log, "\n\n***** error: from %s:" % logfile
                    eupsServer.system("tail -20 %s 1>&2" % q(logfile))
                except:
                    pass
            raise RuntimeError("Failed to build %s: %s" % (pkg, str(e)))

        if self.verbose > 0:
            print >> self.log, "Install for %s successfully completed" % pkg

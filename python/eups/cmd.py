"""
functions for processing the eups command-line.  See in-line comments for 
how to add new commands.
"""
#######################################################################
# 
#  Adding new commands:
#  1.  Add a new EupsCmd sub-class; see FlavorCmd and DeclareCmd as 
#      examples
#      a. provide a specialized usage template
#      b. provide a specialized command description
#      c. over-ride addOptions() to define additional options beyond 
#           the common set.  
#      d. over-ride the execute() function.  self.opts and self.args
#           contains the options and arguments following the command, 
#           respectively.
#  2.  Register the class via register().  See REGISTER below (at end 
#      of file.  
#
########################################################################

import glob, re, os, pwd, shutil, sys, time
import optparse
import eups
import utils

_errstrm = sys.stderr
_EupsCmdType = "cmd.EupsCmd'>"

class EupsCmd(object):
    """
    A class for defining and executing the EUPS command-line tool.

    The eups tool is a family of command of the form "eups cmd ..."
    where cmd is the name of an operation to execute.  Each tool has its
    own set of appropriate command-line options associated with it.  

    This particular class serves two purposes: to handle tool evocations 
    that do not include a command, and to serve as a base class for 
    specializations that handle each command.  
    """

    usage = "%prog [-h|--help|-V|--version] command [options]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = True

    description = \
"""Manage the software environment.

Supported commands are:
	admin		Administer the eups system
	declare		Declare a product
	distrib		Install a product from a remote distribution,
			or create such a distribution 
	expandbuild	Expand variables in a build file
	expandtable	Insert explicit version tags into a table file
	flags		Show the value of \$EUPS_FLAGS
	flavor		Return the current flavor
	list            List some or all products
        path [n]        Print the current eups path, or an element thereof
        pkgroot [n]     Print the current eups pkgroot, or an element thereof
	pkg-config	Return the options associated with product
	remove          Remove an eups product from the system
	undeclare	Undeclare a product
        uses            List everything which depends on the specified product 
                        and version

Use -h with a command name to see a detailed description, inluding options, 
for that command.  

Common"""

    def addOptions(self):
        self.clo.add_option("-h", "--help", dest="help", action="store_true",
                            help="show command-line help and exit")
        self.clo.add_option("-v", "--verbose", dest="verbose", action="count", 
                            default=0, 
          help="Print extra messages about progress (repeat for ever more chat")
        self.clo.add_option("-q", "--quiet", dest="quiet", 
                            action="store_true", default=False, 
                            help="Suppress messages to user (overrides -v)")
        self.clo.add_option("-V", "--version", dest="version", 
                            action="store_true", default=False, 
                            help="Print eups version number")

    def addCommonOptions(self):
        """
        set the common command line options
        """
        self.clo.add_option("-F", "--force", dest="force", action="store_true", 
                            default=False, help="Force requested behaviour")
        self.clo.add_option("-f", "--flavor", dest="flavor", action="store", 
                      help="Assume this target platform flavor (e.g. 'Linux')")
        self.clo.add_option("-Z", "--database", dest="path", action="store", 
                            help="The colon-separated list of product stacks (databases) to use. Default: $EUPS_PATH")
        self.clo.add_option("-z", "--select-db", dest="dbz", action="store", 
                            metavar="DIR", 
                            help="Select the product paths which contain this directory.  Default: all in path")
        self.clo.add_option("--debug", dest="debug", action="store_true", 
                            default=False,
                            help="turn on debugging behaviors")
        self.clo.add_option("-n", "--noaction", dest="noaction", 
                            action="store_true", default=False,
                   help="Don\'t actually do anything (for debugging purposes)")
        self.clo.add_option("--with-eups", dest="path", action="store", 
                            help="synonym for --database")

    def execute(self):
        """
        execute this command, returning an exit code.  A successful operation
        should return 0.  
        """
        if self.cmd is None:
            if self.opts.help:
                self.clo.print_help()
                return 0

            elif self.opts.version:
                if not self.opts.quiet:
                    print "EUPS Version:", eups.version()
                return 0

            self.err("No command provided\n")
            self.clo.print_help()
            return 9

        ecmd = makeEupsCmd(self.cmd, self.clargs, self.prog)
        if ecmd is None:
            self.err("Unrecognized command: %s" % cmd)
            return 10

        return ecmd.run()


    def __init__(self, args=None, toolname=None, cmd=None):
        """
        @param args       the list of command-line arguments, in order, and 
                           including the option switches.  Defaults to 
                           sys.argv[1:]
        @param toolname   the name to give to the EUPS tool.  Defaults to
                           os.path.basename(sys.argv[0]) or "eups".
        @param cmd        the name of the eups command (e.g. "declare")
        """
        self._errstrm = _errstrm

        if not toolname and len(sys.argv) > 0:
            toolname = os.path.basename(sys.argv[0])
        if not toolname:
            toolname = "eups"
        self.prog = toolname

        if args is None:
            args = sys.argv[1:]
        self.clargs = args[:]

        self.clo = EupsOptionParser(self.usage, self.description, 
                                    not self.noDescriptionFormatting,
                                    self.prog)

        # this allows us to process just the core switches without 
        # generating an error if command line includes non-core
        if self._issubclass():
            self.clo.enable_interspersed_args()
        else:
            self.clo.disable_interspersed_args()

        # set and then parse options
        self.addOptions()
        (self.opts, self.args) = self.clo.parse_args(args)
        if not hasattr(self.opts, "help"):
            raise RuntimeError("Extension Error: help option ('-h') overridden")
        if not hasattr(self.opts, "quiet"):
            raise RuntimeError("Extension Error: quiet option ('-q') overridden")
        if not hasattr(self.opts, "verbose"):
            raise RuntimeError("Extension Error: verbose option ('-v') overridden")
        if self.opts.quiet:
            self.opts.verbose = 0

        if hasattr(self.opts, "flavor") and not self.opts.flavor:
            self.opts.flavor = eups.flavor()

        self.cmd = None
        if len(self.args) > 0:
            self.cmd = self.args.pop(0)
        if cmd:
            self.cmd = cmd

    def run(self):
        if self._issubclass() and self.opts.help and self.cmd is not None:
            self.clo.print_help()
            return 0

        return self.execute()

    def _issubclass(self):
        return not str(type(self)).endswith(_EupsCmdType)

    def err(self, msg, volume=0):
        """
        print an error message to standard error.  The message will only 
        be printed if "-q" was not set and volume <= the number of "-v"
        arguments provided. 
        """
        if not self.opts.quiet and self.opts.verbose >= volume:
            self._errstrm.write(self.prog)
            if self.cmd:
                self._errstrm.write(" %s" % self.cmd)
            print >> self._errstrm, ": %s" % msg

    def createEups(self, opts=None):
        if opts is None:
            opts = self.opts

        if self.cmd in ["admin", "flavor", "flags", "path"]:
            readCache = False
        else:
            readCache = True

        exactver = False
        if hasattr(opts, "exactver"):  exactver = opts.exactver
        ignorever = False
        if hasattr(opts, "ignorever"):  ignorever = opts.ignorever
        keep = False
        if hasattr(opts, "keep"):  keep = opts.keep
            
        return eups.Eups(flavor=opts.flavor, path=opts.path, dbz=opts.dbz, 
                         readCache=readCache, force=opts.force,
                         verbose=opts.verbose, quiet=opts.quiet,
                         noaction=opts.noaction)
        
#=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-==-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

class FlavorCmd(EupsCmd):

    usage = "%prog flavor [-h|--help] [-f FLAVOR]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print the platform flavor that will be assumed by EUPS.  If the -f option
is specified, the given flavor will be returned.
"""

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-f", "--flavor", dest="flavor", action="store", 
                      help="Assume this target platform flavor (e.g. 'Linux')")

    def execute(self):
        if not self.opts.quiet:
            print self.opts.flavor
        return 0

class ListCmd(EupsCmd):

    usage = "%prog list [-h|--help] [options] [product [version]]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print information about the products managaged by EUPS.

With out any switches or arguments, it will list all of the products
available from all EUPS product stacks in EUPS_PATH.  The output can
be restricted to particular stacks via the -Z or -z options.  If the 
product argument is provided, only products with that name are listed.
The listing is further restrict to a specific version by providing the
version argument.  The -t option allows the listing to be restrict to 
products that have been tagged with the given name.  

Normally for each product, printed will be the product name, version,
its currently assigned tags, and whether it is currently setup.  If -v
is given, the EUPS database and and the product installation directory
will also be printed.
"""

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addCommonOptions()

        # these are specific to this command
        self.clo.add_option("-d", "--directory", dest="printdir", 
                            action="store_true", default=False, 
                            help="Include the product's installation directory")
        self.clo.add_option("-D", "--dependencies", dest="depends", 
                            action="store_true", default=False, 
                            help="Print product's dependencies (must also provide the version argument")
        self.clo.add_option("-e", "--exact", dest="exactver", 
                            action="store_true", default=False, 
                            help="Follow the as-installed versions, not the conditionals in the table file (ignored unless -d is specified)")
        self.clo.add_option("-m", "--table", dest="tablefile", 
                            action="store_true", default=False, 
                            help="Print the name of the product's table file")
        self.clo.add_option("-s", "--setup", dest="setup", 
                            action="store_true", default=False, 
                            help="List only product's that are setup.")
        self.clo.add_option("-t", "--tag", dest="tag", action="store", 
                            help="List only versions having this tag name")
        self.clo.add_option("-T", "--type", dest="setuptype", action="store", 
                            help="the setup type to assume (ignored unless -d is specified)")
        

    def execute(self):
        product = version = None
        if len(self.args) > 0:
            product = self.args[0]
        if len(self.args) > 1:
            version = self.args[1]

        try:
            eups.printProducts(sys.stdout, product, version, self.createEups(), 
                               tags=self.opts.tag, setup=self.opts.setup, 
                               tablefile=self.opts.tablefile, 
                               directory=self.opts.printdir, 
                               dependencies=self.opts.depends, 
                               showVersion=self.opts.version, 
                               setupType=self.opts.setuptype)
        except eups.EupsException, e:
            self.err(str(e))
            return 2

        return 0

class FlagsCmd(EupsCmd):

    usage = "%prog flags [-h|--help]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print the value of the EUPS_FLAGS environment variable
"""

    def execute(self):
        if not self.opts.quiet:
            try: 
                print "EUPS_FLAGS == %s" % (os.environ["EUPS_FLAGS"])
            except KeyError:
                print "You have no EUPS_FLAGS set" 
        return 0

class EnvListCmd(EupsCmd):

    def _init(self, what, delim=":"):
        self.what = what
        self.delim = delim

        self.which = None
        if len(self.args) > 0:
            self.which = self.args[0]

    def printEnv(self):
        elems = os.environ.get(self.what, "").split(self.delim)

        if self.which is not None:
            try:
                if not isinstance(self.which, int):
                    self.which = int(self.which)
                elems = [elems[self.which]]
            except IndexError:
                self.err("%s does not have an element a position %s" % 
                         (self.what, self.which))
                return 1
            except ValueError:
                self.err("Not an integer:  %s" % (self.which))
                return 2

        for e in elems:
            print e
        return 0

    def execute(self):
        return self.printEnv()

class PathCmd(EnvListCmd):

    usage = "%prog path [-h|--help] [n]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print the product stack directories given via EUPS_PATH.  An optional
integer argument, n, will cause just the n-th directory to be listed (where
0 is the first element).
"""

    def __init__(self, args=None, toolname=None, cmd=None):
        EnvListCmd.__init__(self, args, toolname, cmd)
        self._init("EUPS_PATH")

class StartupCmd(EnvListCmd):

    usage = "%prog startup [-h|--help] [n]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print the start-up files that customize EUPS as given via EUPS_STARTUP.  
An optional integer argument, n, will cause just the n-th directory to be 
listed (where 0 is the first element).
"""

    def __init__(self, args=None, toolname=None, cmd=None):
        EnvListCmd.__init__(self, args, toolname, cmd)
        self._init("EUPS_STARTUP")

class PkgrootCmd(EnvListCmd):

    usage = "%prog pkgroot [-h|--help] [n]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print the base URLs for the repositories given via EUPS_PKGROOT.  An optional
integer argument, n, will cause just the n-th URL to be listed (where
0 is the first element).
"""

    def __init__(self, args=None, toolname=None, cmd=None):
        EnvListCmd.__init__(self, args, toolname, cmd)
        self._init("EUPS_PKGROOT", "|")

class PkgconfigCmd(EupsCmd):

    usage = "%prog pkgroot [-c|--cflags|-l|--libs] product [version]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print information about products
"""

    def addOptions(self):
        # these are specific to this command
        self.clo.add_option("-c", "--cflags", dest="cflags", 
                            action="store_true", default=False,
                            help="Output all pre-processor and compiler flags")
        self.clo.add_option("-l", "--libs", dest="libs", 
                            action="store_true", default=False,
                            help="Output all linker flags")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addCommonOptions()

    def execute(self):
        if self.opts.cflags == self.opts.libs:
            self.err("Please specify exactly one desired item of information (-c|-l)")
            return 1

        if self.opts.cflags:
            desired = "Cflags"
        elif self.opts.libs:
            self.opts.desired = "Libs"
        else:
            raise RuntimeError("eups pkg-config programming error: complain")

        if len(self.args) < 1:
            self.err("please specify at least a product name")
            print >> self._errstrm, self.clo.get_usage()
            return 2

        productName = self.args[0]
        if len(self.args) > 1:
            versionName = self.args[1]
        else:
            versionName = None

        Eups = self.createEups()

        #
        # Time to do some real work
        #
        PKG_CONFIG_PATH = os.environ.get("PKG_CONFIG_PATH", "").split(":")
        #productList = Eups.findProduct(productName, versionName)
        #
        # Look for the best match
        product = None
        if versionName:
            # prefer explicitly specified version
            prod = Eups.findProduct(productName, versionName)

        if not product:              # try setup version
            tag = eups.Tag("setup")
            prod = Eups.findProduct(productName, tag)

        if not product:              # try most preferred tag
            prod = Eups.findProduct(productName)

        if product:
            PKG_CONFIG_PATH += [os.path.join(product.dir, "etc")]
        
        if not PKG_CONFIG_PATH:
            if versionName:
                self.err("Unable to find %s %s" % (productName, versionName))
                return 3
            else:
                self.err("No version of %s is either setup or current" % 
                         (productName))
                return 4

        pcfile = None
        for dir in PKG_CONFIG_PATH:
            _pcfile = os.path.join(dir, "%s.pc" % productName)

            if os.path.exists(_pcfile):
                pcfile = _pcfile
                break

        if pcfile:
            if Eups.verbose:
                print >> self._errstrm, "Reading %s" % pcfile

            # Time to actually read and process the file.
            symbols = {}
            contents = open(pcfile).readlines()
            #
            # Look for variable definitions
            #
            for line in contents:
                mat = re.search(r"^\s*([^=\s]+)\s*=\s*([^\s]+)", line)
                if mat:
                    symbols[mat.group(1)] = mat.group(2)
            #
            # Expand references to variables in other variable's values
            #
            for k in symbols.keys():
                mat = re.search(r"(?:^|[^$])\${([^\}]+)}", symbols[k])
                if mat:
                    var = mat.group(1)
                    symbols[k] = re.sub(r"(^|[^$])\${([^\}]+)}", r"\1%s" % symbols[var], symbols[k])
            #
            # Look for configuration values
            #
            for line in contents:
                mat = re.search(r"^\s*%s\s*:\s*(.*)" % desired, line, re.IGNORECASE)
                if mat:
                    value = mat.group(1)
                    
                    mat = re.search(r"(?:^|[^$])\${([^\}]+)}", value)
                    if mat:
                        var = mat.group(1)
                        value = re.sub(r"(^|[^$])\${([^\}]+)}", r"\1%s" % symbols[var], value)


                    value = re.sub(r"\$\$", r"$", value)

                    print value
                    break
        else:
            self.err("I am unable to find a .pc file for %s" % productName)

        return 0


class UsesCmd(EupsCmd):

    usage = "%prog uses [-h|--help] [options] product [version]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""List the products that depend on the specified product
"""

    def addOptions(self):
        # these are specific to this command
        self.clo.add_option("-t", "--tag", dest="tag", action="store", 
                help="Look for products that get setup because it has this tag")
        self.clo.add_option("-d", "--depth", dest="depth", 
                            action="store", type="int", default=9999, 
                        help="Only search down this many layers of dependency")
        self.clo.add_option("-e", "--exact", dest="exactver", 
                            action="store_true", default=False, 
                            help="Consider the as-installed versions, not the conditionals in the table file (ignored unless -d is specified)")
        self.clo.add_option("-o", "--optional", dest="optional", 
                            action="store_true", default=False, 
                            help="Show optional setups")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addCommonOptions()

        self.clo.add_option("-c", "--current", dest="current", 
                            action="store_true", default=False, 
                            help="(deprecated)")
        

    def execute(self):
        version = None
        if len(self.args) == 0:
            self.err("Please specify a product name")
            return 3
        product = self.args[0]
        if len(self.args) > 1:
            version = self.args[1]

        try:
            eups.printUses(sys.stdout, product, version, self.createEups(), 
                           depth=self.opts.depth, 
                           showOptional=self.opts.optional,
                           tags=self.opts.tag)
        except eups.EupsException, e:
            self.err(str(e))
            return 2

        return 0

class ExpandbuildCmd(EupsCmd):

    usage = "%prog expandbuild [-h|--help] [options] buildFile -V version [outdir]]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Expand a .build file as part of installing it.

If outDir is provided, the expanded file will be written there;
otherwise it'll be written to stdout unless you specify --inplace.
"""

    def addOptions(self):
        # these are specific to this command
        self.clo.add_option("-c", "--cvs", dest="cvsroot", action="store", 
                         help="A CVS root URL to find source code under")
        self.clo.add_option("-s", "--svn", dest="svnroot", action="store", 
                         help="An SVN root URL to find source code under")
        self.clo.add_option("-i", "--inplace", dest="in_situ", default=False,
                            action="store_true", 
                        help="Modify the given buildfile in situ")
        self.clo.add_option("-p", "--product", dest="prodname", action="store",
                            default="",
                     help="The name of the product that the build file is for")
        self.clo.add_option("-V", "--version", dest="version", action="store", 
                  help="The version of the product that the build file is for")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addCommonOptions()

        self.clo.add_option("--cvsroot", dest="cvsroot", action="store", 
                         help="same as --cvs")
        self.clo.add_option("--svnroot", dest="svnroot", action="store", 
                         help="same as --svn")

    def execute(self):
        outdir = None
        if len(self.args) == 0:
            self.err("Please specify a build file path")
            return 3
        inFile = self.args[0]
        if len(self.args) > 1:
            outdir = self.args[1]

        if self.opts.in_situ and outdir:
            self.err("You may not specify both --inplace and a target directory")
            return 4

        Eups = self.createEups()

        if not self.opts.version:
            self.err("Please specify a version with --version or -V")
            return 2

        backup = None
        if inFile == "-":
            ifd = sys.stdin
        else:
            try:
                if self.opts.in_situ:
                    backup = inFile + ".bak"
                    os.rename(inFile, backup)
                    ifd = open(backup, "r")
                else:
                    ifd = open(inFile)
            except IOError, e:
                if backup and os.path.exists(backup):
                    os.rename(backup, inFile)
                    os.unlink(backup)

                self.err("Failed to open file \"%s\" for read" % inFile)
                return 6

        if outdir:
            outfile = os.path.join(outdir, os.path.basename(inFile))
            if Eups.verbose:
                print "Writing to %s" % outfile

            try:
                ofd = open(outfile, "w")
            except IOError, e:
                self.err("Failed to open file \"%s\" for write" % outfile)
                return 5
        elif in_situ:
            try:
                ofd = open(inFile, "w")
            except Exception:
                if backup and os.path.exists(backup):
                    os.rename(backup, inFile)
                    os.unlink(backup)
        else:
            ofd = sys.stdout

        eups.expandBuildFile(ofd, ifd, self.opts.prodname, self.opts.version,
                            self.opts.svnroot, self.opts.cvsroot, 
                            self.createEups())

        return 0

class ExpandtableCmd(EupsCmd):

    usage = "%prog expandbuild [-h|--help] [options] tablefile [outdir]]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = True

    description = \
"""Modify a ups table file, replacing setupRequired and setupOptional
lines which refer to the current version by the actual version number 
of the currently setup product; e.g.
      setupRequired(astroda)
becomes
      setupRequired(astroda v13_1)

You can override the version with e.g. -p astroda=rhl; more
than one -p command is permitted.

If a directory is specified, the modified table file will be written
there, with the same name as the original; otherwise it is written to
standard out unless you specify --inplace, in which case the
substitution will be done in situ.  You may omit file.table, or
specify it as "-", to read standard input; this implies --inplace.
    
For example, the make target in a ups directory might contain the line:
      eups expandtable -w iop.table $(IOP_DIR)/ups
"""

    def addOptions(self):
        # these are specific to this command
        self.clo.add_option("-i", "--inplace", dest="in_situ", default=False,
                            action="store_true", 
                        help="Modify the given tablefile in situ")
        self.clo.add_option("-p", "--product", dest="prodlist", action="store",
                          help="A set of products of the form 'prod=ver[:...]'")
        self.clo.add_option("-w", "--warn", dest="warn", action="store_true", 
                            default=False, 
                            help="Warn about versions with non-canonical names")
        self.clo.add_option("-W", "--warnRegexp", dest="warnRegexp", 
                            action="store", 
            help="Canonical versions should match this regexp (implies --warn)")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addCommonOptions()

    def execute(self):
        outdir = None
        if len(self.args) == 0:
            self.err("Please specify a table file path")
            return 3
        inFile = self.args[0]
        if len(self.args) > 1:
            outdir = self.args[1]

        if self.opts.in_situ and outdir:
            self.err("You may not specify both --inplace and a target directory")
            return 4

        Eups = self.createEups()

        if not self.opts.version:
            self.err("Please specify a version with --version or -V")
            return 2

        productList = {}
        productVersionPair = self.opts.prodlist
        if productVersionPair:
            for pv in productVersionPair.split(":"):
                p, v = pv.split("=")
                productList[p] = v
        
        if self.opts.warn and not self.opts.warnRegexp:
            self.opts.warnRegexp = "^[vV]"


        backup = None
        if inFile == "-":
            ifd = sys.stdin
        else:
            try:
                if self.opts.in_situ:
                    backup = inFile + ".bak"
                    os.rename(inFile, backup)
                    ifd = open(backup, "r")
                else:
                    ifd = open(inFile)
            except IOError, e:
                if backup and os.path.exists(backup):
                    os.rename(backup, inFile)
                    os.unlink(backup)

                self.err("Failed to open file \"%s\" for read" % inFile)
                return 6

        if outdir:
            outfile = os.path.join(outdir, os.path.basename(inFile))
            if Eups.verbose:
                print "Writing to %s" % outfile

            try:
                ofd = open(outfile, "w")
            except IOError, e:
                self.err("Failed to open file \"%s\" for write" % outfile)
                return 5
        elif in_situ:
            try:
                ofd = open(inFile, "w")
            except Exception:
                if backup and os.path.exists(backup):
                    os.rename(backup, inFile)
                    os.unlink(backup)
        else:
            ofd = sys.stdout

        eups.expandTableFile(ofd, ifd, productList, self.opts.warnRegexp,
                            self.opts.svnroot, self.opts.cvsroot)

        return 0


class DeclareCmd(EupsCmd):

    usage = "%prog declare [-h|--help] [options] product version"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Declare (i.e. allow EUPS to manage) and/or tag a product.  To fully 
declare a product, you must specifiy at least the -r in addition to 
specifying the product name and version.  For declaration to succeed, EUPS
needs to locate a table file; be default, it will look for ups/[product].table 
in the product's root directory or it can be specified explicitly via -m or -M.
(-M is useful when the user cannot write to the product root directory.)
If there is no table file, give "none" to the -m option.  If the product is 
already declared, attempts to redeclare will fail unless -F is used.  If you 
only wish to assign a tag, you should use the -t option but not include 
-r.  
"""

    def addOptions(self):
        # these are specific to this command
        self.clo.add_option("-r", "--root", dest="productDir", action="store", 
                            help="root directory where product is installed")
        self.clo.add_option("-m", "--table", dest="tablefile", 
                            action="store", 
                  help='table file location (may be "none" for no table file)')
        self.clo.add_option("-M", "--import-table", dest="externalTablefile", 
                            action="store", 
                            help='Import the given table file directly into the database (may be "-" for stdin).')
        self.clo.add_option("-t", "--tag", dest="tag", action="store", 
                            help="assign TAG to the specified product")
        
        # these options are used to configure the Eups instance
        self.addCommonOptions()

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-c", "--current", dest="tag", 
                            action="store_const", const="current",
                            help="same as --tag=current (deprecated)")
        

    def execute(self):
        if len(self.args) == 0:
            self.err("Please specify a product name and version")
            return 2
        if len(self.args) < 2:
            self.err("Please also specify a product version")
            return 2
        product = self.args[0]
        version = self.args[1]

        if self.opts.tablefile and self.opts.externalTablefile:
            self.err("You may not specify both -m and -M")
            return 3

        tablefile = self.opts.tablefile
        if self.opts.externalTablefile:
            if self.opts.externalTablefile == "-":
                tablefile = sys.stdin
            else:
                try:
                    tablefile = open(externalTablefile, "r")
                except IOError, e:
                    self.err("Error opening %s: %s" % (externalTablefile, e))
                    return 4

        myeups = self.createEups()

        try:
            eups.declare(product, version, self.opts.productDir, 
                        tablefile=tablefile, tag=self.opts.tag, eupsenv=myeups)
        except eups.EupsException, e:
            self.err(str(e))
            return 2

        return 0

        
class UndeclareCmd(EupsCmd):

    usage = "%prog undeclare [-h|--help] [options] product [version]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Undeclare a product or unassign a tag to it.  If -t is provided, the 
given will be unassigned (the product will remain otherwise declared).  If
no version is provided, the tag will be unassigned from which ever version
currently has the tag.  Without -t, the product will be "forgotten" by EUPS 
and all tags assigned to it will be forgotten as well.  Normally when 
undeclaring a product, a version must be specified unless there is only one 
version currently declared.  
"""

    def addOptions(self):
        # these are specific to this command
        self.clo.add_option("-t", "--tag", dest="tag", action="store", 
                            help="unassign TAG to the specified product")
        
        # these options are used to configure the Eups instance
        self.addCommonOptions()

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-c", "--current", dest="tag", 
                            action="store_const", const="current",
                            help="same as --tag=current (deprecated)")
        

    def execute(self):
        if len(self.args) == 0:
            self.err("Please specify a product name")
            return 3
        product = self.args[0]
        version = None
        if len(self.args) > 1:
            version = self.args[1]

        myeups = self.createEups()

        try:
            eups.undeclare(product, version, tag=self.opts.tag, eupsenv=myeups)
        except eups.EupsException, e:
            self.err(str(e))
            return 2

        return 0

# TODO: admin, distrib, remove
        
        





#=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-==-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

_cmdLookup = {}
_noCmdOverride = True
def register(cmd, clname):
    if _noCmdOverride and _cmdLookup.has_key(cmd):
        raise RuntimeError("Attempt to over-ride command: %s" % cmd)
    _cmdLookup[cmd] = clname

def makeEupsCmd(cmd, args=None, toolname=None):
    if not _cmdLookup.has_key(cmd):
        return None
    return _cmdLookup[cmd](args=args, toolname=toolname, cmd=cmd)
    
#=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-==-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

class EupsOptionParser(optparse.OptionParser):
    """
    a specialization for parsing the eups command line.  In particular, the 
    options that appear in the help messages will depend on the command 
    being accessed.  
    """

    def __init__(self, usage=None, description=None, formatdesc=True, 
                 prog=None, epilog=None):
        optparse.OptionParser.__init__(self, usage=usage, 
                                       description=description, 
                                       epilog=epilog, prog=prog, 
                                       add_help_option=False,
                                       conflict_handler="resolve")

        self._preformattedDescr = not formatdesc

    def format_description(self, formatter):
        """
        a specialization of the optparse.OptionParser method.
        """
        if self._preformattedDescr:
            return self.description
        else:
            return optparse.OptionParser.format_description(self, formatter)

#=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-==-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
#
#  REGISTER
#

register("flavor",       FlavorCmd)
register("path",         PathCmd)
register("startup",      StartupCmd)
register("pkgroot",      PkgrootCmd)
register("flags",        FlagsCmd)
register("list",         ListCmd)
register("pkg-config",   PkgconfigCmd)
register("uses",         UsesCmd)
register("expandbuild",  ExpandbuildCmd)
register("expandtable",  ExpandtableCmd)
register("declare",      DeclareCmd)
register("undeclare",    UndeclareCmd)


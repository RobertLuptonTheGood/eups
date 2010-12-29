"""
functions for processing the eups command-line.  See in-line comments for 
how to add new commands.

To run an eups command from Python, try:

    import sys
    import eups.cmd

    cmd = eups.cmd.EupsCmd()
    status = cmd.run()

The output of run() is a status code appropriate for passing to sys.exit().
"""
#######################################################################
# 
#  Adding new commands:
#  1.  Add a new EupsCmd sub-class; see FlavorCmd and ListCmd as 
#      examples
#      a. provide a specialized usage template
#      b. provide a specialized command description
#      c. over-ride addOptions() to define additional options beyond 
#           the common set.  
#      d. over-ride the execute() function.  self.opts and self.args
#           contains the options and arguments following the command, 
#           respectively.
#      (Note that adding additional distrib subcommands is slightly 
#      different.)
#  2.  Register the class via register().  See REGISTER below (at end 
#      of file.  
#
########################################################################

import glob, re, os, pwd, shutil, sys, time
import optparse
import eups
import utils
import distrib
import hooks
from distrib.server import ServerConf

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

    usage = "%prog [--debug=OPTS|-h|--help|-V|--version|--vro] command [options]"

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
        help            Provide help on eups commands
	list            List some or all products
        path [n]        Print the current eups path, or an element thereof
        pkgroot [n]     Print the current eups pkgroot, or an element thereof
	pkg-config	Return the options associated with product
	remove          Remove an eups product from the system
        tags            List information about supported and known tags
	undeclare	Undeclare a product
        uses            List everything which depends on the specified product 
                        and version
	vro             Show the Version Resolution Order that would be used

Use -h with a command name to see a detailed description, inluding options, 
for that command.  

Common"""

    def addOptions(self):
        self.clo.add_option("--debug", dest="debug", action="store", default="",
                            help="turn on specified debugging behaviors (allowed: raise)")
        self.clo.add_option("-h", "--help", dest="help", action="store_true",
                            help="show command-line help and exit")
        self.clo.add_option("-n", "--noaction", dest="noaction", action="store_true", default=False,
                            help="Don\'t actually do anything (for debugging purposes)")
        self.clo.add_option("-q", "--quiet", dest="quiet", action="store_true", default=False,
                            help="Suppress messages to user (overrides -v)")
        self.clo.add_option("-T", "--type", dest="setupType", action="store", default="",
                            help="the setup type to use (e.g. exact)")
        self.clo.add_option("-v", "--verbose", dest="verbose", action="count", default=0,
                            help="Print extra messages about progress (repeat for ever more chat)")
        self.clo.add_option("-V", "--version", dest="version", action="store_true", default=False,
                            help="Print eups version number")
        self.clo.add_option("--vro", dest="vro", action="store", metavar="LIST",
                            help="Set the Version Resolution Order")
        self.clo.add_option("-Z", "--database", dest="path", action="store",
                            help="The colon-separated list of product stacks (databases) to use. " +
                            "Default: $EUPS_PATH")
        self.clo.add_option("-z", "--select-db", dest="dbz", action="store", metavar="DIR",
                            help="Select the product paths which contain this directory.  " +
                            "Default: all in path")
        self.clo.add_option("--with-eups", dest="path", action="store",
                            help="synonym for -Z/--database")

    def addEupsOptions(self):
        """
        set the common command line options
        """
        self.clo.add_option("-f", "--flavor", dest="flavor", action="store",
                            help="Assume this target platform flavor (e.g. 'Linux')")
        self.clo.add_option("-F", "--force", dest="force", action="store_true", default=False,
                            help="Force requested behaviour")

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
                    self.printVersion(sys.stdout)
                return 0

            self.err("No command provided\n")
            if not self.opts.quiet:
                self.clo.print_help()
            return 9

        ecmd = makeEupsCmd(self.cmd, self.clargs, self.prog)
        if ecmd is None:
            self.err("Unrecognized command: %s" % self.cmd)
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

        self.clo = EupsOptionParser(self._errstrm, self.usage, 
                                    self.description, 
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
        elif hooks.config.Eups.verbose > self.opts.verbose:
            # let the user's configuration mandate a minimum verbosity
            self.opts.verbose = hooks.config.Eups.verbose

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

    def printVersion(self, strm=sys.stderr):
        print >> strm, "EUPS Version:", eups.version()
        return 0

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

    def deprecated(self, msg, volume=1):
        """
        indicate that deprecated arguments were used.  This currently is 
        implemented to print the message to sys.stderr, but in the future,
        it could raise an exception or otherwise cause a fatal error.
        """
        if not self.opts.quiet and self.opts.verbose >= volume:
            preamble = self.prog
            if self.cmd:
                preamble += " %s" % self.cmd
            utils.deprecated("%s: %s" % (preamble, msg), strm=self._errstrm)

    def createEups(self, opts=None, versionName=None, setupType=""):
        if opts is None:
            opts = self.opts

        if self.cmd in "admin flavor flags path".split():
            readCache = False
        else:
            readCache = True

        if hasattr(opts, "exact_version") and opts.exact_version:
            if opts.setupType:
                opts.setupType += ","
            opts.setupType += "exact"
            
        ignorever = False
        if hasattr(opts, "ignorever"):  ignorever = opts.ignorever
        keep = False
        if hasattr(opts, "keep"):  keep = opts.keep
        asAdmin = False
        if hasattr(opts, "asAdmin"):  asAdmin = opts.asAdmin
            
        Eups = eups.Eups(flavor=opts.flavor, path=opts.path, dbz=opts.dbz, 
                         readCache=readCache, force=opts.force, 
                         ignore_versions=ignorever, setupType=self.opts.setupType,
                         keep=keep, verbose=opts.verbose, quiet=opts.quiet, vro=self.opts.vro,
                         noaction=opts.noaction, asAdmin=asAdmin)

        if hasattr(opts, "productDir"):
            productDir = opts.productDir
        else:
            productDir = None
            
        if hasattr(opts, "tag"):
            tag = opts.tag
        else:
            tag = None
        
        Eups.selectVRO(tag, productDir, versionName, opts.dbz)
        
        if Eups.isUserTag(tag):
            Eups.includeUserDataDirInPath()

        try:
            eups.commandCallbacks.apply(Eups, self.cmd, self.opts, self.args)
        except eups.OperationForbidden, e:
            e.status = 255
            raise
        except Exception, e:
            e.status = 9
            raise

        return Eups

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class CommandCallbacks(object):
    """Callback to allow users to customize behaviour by defining hooks in EUPS_STARTUP
        and calling eups.commandCallbacks.add(hook)"""

    callbacks = []

    def __init__(self):
        pass

    def add(self, callback):
        """
        Add a command callback.
        
        The arguments are the command (e.g. "admin" if you type "eups admin")
        and sys.argv, which you may modify;  cmd == argv[1] if len(argv) > 1 else None
        
        E.g.
        if cmd == "fetch":
            argv[1:2] = ["distrib", "install"]
        """
        CommandCallbacks.callbacks += [callback]

    def apply(self, Eups, cmd, opts, args):
        """Call the command callbacks on cmd"""

        for hook in CommandCallbacks.callbacks:
            hook(Eups, cmd, opts, args)

    def clear(self):
        """Clear the list of command callbacks"""
        CommandCallbacks.callbacks = []

    def list(self):
        for hook in CommandCallbacks.callbacks:
            print >> sys.stderr, hook

try:
    type(commandCallbacks)
except NameError:
    commandCallbacks = CommandCallbacks()
        
#=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-==-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

class FlavorCmd(EupsCmd):

    usage = "%prog flavor [-h|--help] [options]"

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
            if not self.opts.flavor:
                self.opts.flavor = eups.flavor()
            print self.opts.flavor
        return 0

class ListCmd(EupsCmd):

    usage = "%prog list [-h|--help] [options] [product [version]]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = True

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
        self.addEupsOptions()

        # these are specific to this command
        self.clo.add_option("-c", "--current", dest="current", action="store_true", default=False,
                            help="same as --tag=current (deprecated)")
        self.clo.add_option("-D", "--dependencies", dest="depends", action="store_true", default=False,
                            help="Print product's dependencies (must specify version if ambiguous). With --setup print the versions of dependent products that are actually setup.")
        self.clo.add_option("--depth", dest="depth", action="store",
                            help="Only list this many layers of dependency")
        self.clo.add_option("-d", "--directory", dest="printdir", action="store_true", default=False,
                            help="Include the product's installation directory")
        self.clo.add_option("-e", "--exact", dest="exact_version", action="store_true", default=False,
                            help="Follow the as-installed versions, not the conditionals in the table file ")
        self.clo.add_option("-r", "--root", dest="productDir", action="store", 
                            help="root directory where product is installed")
        self.clo.add_option("-s", "--setup", dest="setup", action="store_true", default=False,
                            help="List only product's that are setup.")
        self.clo.add_option("-m", "--table", dest="tablefile", action="store_true", default=False,
                            help="Print the name of the product's table file")
        self.clo.add_option("-t", "--tag", dest="tag", action="store",
                            help="List only versions having this tag name")
        self.clo.add_option("-T", "--type", dest="setupType", action="store", default="",
                            help="the setup type to assume (ignored unless -d is specified)")

    def execute(self):
        product = version = None
        if len(self.args) > 0:
            product = self.args[0]
        if len(self.args) > 1:
            version = self.args[1]

        if self.opts.current: 
            self.deprecated("Note: -c|--current is deprecated; use --tag current")
            if self.opts.tag:
                self.opts.tag += " current"
            else:
                self.opts.tag = "current"

        if not self.opts.quiet and \
           self.opts.depth and not self.opts.depends:
            print >> sys.stderr, "Ignoring --depth as it only makes sense with --dependencies"

        try:
            n = eups.printProducts(sys.stdout, product, version, 
                                   self.createEups(versionName=version, setupType=self.opts.setupType),
                                   tags=self.opts.tag, 
                                   setup=self.opts.setup, 
                                   tablefile=self.opts.tablefile, 
                                   directory=self.opts.printdir, 
                                   dependencies=self.opts.depends, 
                                   showVersion=self.opts.version, 
                                   depth=self.opts.depth,
                                   productDir=self.opts.productDir)
            if n == 0:
                msg = 'No products found'

                if product == "distrib":
                    msg += '; Maybe you meant "eups distrib list"?'
                self.err(msg)

        except eups.EupsException, e:
            e.status = 2
            raise

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

    def printEnv(self, elems=None):
        if elems is None:
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

    usage = "%prog startup [-h|--help]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""List the startup files that customize EUPS (including $EUPS_STARTUP).  With -v, show non-existent files
that would be loaded [in brackets].
"""

    def __init__(self, args=None, toolname=None, cmd=None):
        EnvListCmd.__init__(self, args, toolname, cmd)
        self._init("EUPS_STARTUP")

    def execute(self):
        Eups = eups.Eups(path=self.opts.path, dbz=self.opts.dbz)
        path = Eups.path

        for f in hooks.loadCustomization(execute=False, verbose=self.opts.verbose,
                                         quiet=self.opts.quiet, path=path, reset=True):
            
            if not self.opts.verbose and os.stat(f).st_size == 0:
                continue

            print "%-40s" % f

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

    usage = "%prog pkgroot [-h|--help] [options] product [version]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print information about products
"""

    def addOptions(self):
        # these are specific to this command
        self.clo.add_option("-c", "--cflags", dest="cflags", action="store_true", default=False,
                            help="Output all pre-processor and compiler flags")
        self.clo.add_option("-l", "--libs", dest="libs", action="store_true", default=False,
                            help="Output all linker flags")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addEupsOptions()

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
        self.clo.add_option("-d", "--depth", dest="depth", action="store", type="int", default=9999, 
                            help="Only search down this many layers of dependency")
        self.clo.add_option("-e", "--exact", dest="exact_version", action="store_true", default=False, 
                            help="Consider the as-installed versions, not the conditionals in the table file ")
        self.clo.add_option("-o", "--optional", dest="optional", action="store_true", default=False, 
                            help="Show optional setups")
        self.clo.add_option("-t", "--tag", dest="tag", action="store", 
                            help="Look for products that get setup because it has this tag")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addEupsOptions()

        self.clo.add_option("-c", "--current", dest="current", action="store_true", default=False, 
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
            e.status = 2
            raise

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
        self.clo.add_option("-i", "--inplace", dest="in_situ", default=False, action="store_true", 
                            help="Modify the given buildfile in situ")
        self.clo.add_option("-p", "--product", dest="prodname", action="store", default="",
                            help="The name of the product that the build file is for")
        self.clo.add_option("-s", "--svn", dest="svnroot", action="store", 
                            help="An SVN root URL to find source code under")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addEupsOptions()

        self.clo.add_option("-V", "--version", dest="version", action="store", 
                            help="The version of the product that the build file is for")

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

        tmpout = None
        if inFile == "-":
            ifd = sys.stdin
        else:
            if not self.opts.prodname:
                mat = re.search(r"^([^.]+)\.build$", os.path.basename(inFile))
                if not mat:
                    self.err("Unable to guess the product name; please use -p")
                    return 2
                self.opts.prodname = mat.group(1)

            if not os.path.isfile(inFile):
                self.err("%s: not an existing file" % inFile)
                return 6
            try:
                ifd = open(inFile)
            except IOError, e:
                self.err('Failed to open file "%s" for read: %s' % 
                         (inFile, str(e)))
                return 6

        if outdir:
            outfile = os.path.join(outdir, os.path.basename(inFile))
            if Eups.verbose:
                print "Writing to %s" % outfile

            try:
                ofd = open(outfile, "w")
            except IOError, e:
                self.err('Failed to open file "%s" for write: %s' % 
                         (outfile, str(e)))
                return 6

        elif self.opts.in_situ:
            tmpout = os.path.join(os.path.dirname(inFile), 
                                  "."+os.path.basename(inFile)+".tmp")
            try:
                ofd = open(tmpout, "w")
            except IOError, e:
                outfile = os.path.dirname(tmpout)
                if not outfile:  outfile = "."
                self.err('Failed to temporary file in "%s" for write: %s' % 
                         (outfile, str(e)))
                return 6

        else:
            ofd = sys.stdout

        try:
          try:
            eups.expandBuildFile(ofd, ifd, self.opts.prodname, 
                                 self.opts.version, self.opts.svnroot, 
                                 self.opts.cvsroot, self.createEups())
          finally:
            if inFile != "-": ifd.close() 
            if outdir or self.opts.in_situ:  ofd.close()
          if tmpout:
            os.rename(tmpout, inFile)
        finally:
          if tmpout and os.path.exists(tmpout):  
              os.unlink(tmpout)

        return 0

class ExpandtableCmd(EupsCmd):

    usage = "%prog expandtable [-h|--help] [options] tablefile [outdir]]"

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
        self.clo.add_option("-i", "--inplace", dest="in_situ", default=False, action="store_true", 
                            help="Modify the given tablefile in situ")
        self.clo.add_option("-p", "--product", dest="prodlist", action="store",
                            help="A set of products of the form 'prod=ver[:...]'")
        self.clo.add_option("-w", "--warn", dest="warn", action="store_true", default=False, 
                            help="Warn about versions with non-canonical names")
        self.clo.add_option("-W", "--warnRegexp", dest="warnRegexp", action="store", 
                            help="Canonical versions should match this regexp (implies --warn)")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addEupsOptions()

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

        try:
            myeups = self.createEups()
        except eups.EupsException, e:
            e.status = 9
            raise

        productList = {}
        productVersionPair = self.opts.prodlist
        if productVersionPair:
            for pv in productVersionPair.split(":"):
                p, v = pv.split("=")
                productList[p] = v
        
        if self.opts.warn and not self.opts.warnRegexp:
            self.opts.warnRegexp = "^[vV]"


        tmpout = None
        if inFile == "-":
            ifd = sys.stdin
        else:
            if not os.path.isfile(inFile):
                self.err("%s: not an existing file" % inFile)
                return 6
            try:
                ifd = open(inFile)
            except IOError, e:
                self.err('Failed to open file "%s" for read: %s' % 
                         (inFile, str(e)))
                return 6

        if outdir:
            outfile = os.path.join(outdir, os.path.basename(inFile))
            if myeups.verbose:
                print "Writing to %s" % outfile

            try:
                ofd = open(outfile, "w")
            except IOError, e:
                self.err('Failed to open file "%s" for write: %s' % 
                         (outfile, str(e)))
                return 6

        elif self.opts.in_situ:
            tmpout = os.path.join(os.path.dirname(inFile), 
                                  "."+os.path.basename(inFile)+".tmp")
            try:
                ofd = open(tmpout, "w")
            except IOError, e:
                outfile = os.path.dirname(tmpout)
                if not outfile:  outfile = "."
                self.err('Failed to temporary file in "%s" for write: %s' % 
                         (outfile, str(e)))
                return 6

        else:
            ofd = sys.stdout

        try:
          try:

            eups.expandTableFile(ofd, ifd, productList, self.opts.warnRegexp,
                                 myeups)

          finally:
            if inFile != "-": ifd.close() 
            if outdir or self.opts.in_situ:  ofd.close()
          if tmpout:
            os.rename(tmpout, inFile)
        finally:
          if tmpout and os.path.exists(tmpout):  
              os.unlink(tmpout)

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
        self.clo.add_option("-M", "--import-table", dest="externalTablefile", action="store", 
                            help="Import the given table file directly into the database " +
                            "(may be \"-\" for stdin).")
        self.clo.add_option("-m", "--table", dest="tablefile", action="store", 
                            help='table file location (may be "none" for no table file)')
        self.clo.add_option("-t", "--tag", dest="tag", action="store", 
                            help="assign TAG to the specified product")
        
        # these options are used to configure the Eups instance
        self.addEupsOptions()

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-c", "--current", dest="tag", action="store_const", const="current",
                            help="same as --tag=current (deprecated)")
        

    def execute(self):
        product, version = None, None
        if len(self.args) > 0:
            product = self.args[0]
        if len(self.args) > 1:
            version = self.args[1]

        if not product:
            if self.opts.tablefile == "none" or self.opts.externalTablefile != None:
                self.err("Unable to guess product name as product contains no table file")
                return 2

            try:
                ups_dir = os.path.join(self.opts.productDir,"ups")
                if not os.path.isdir(ups_dir):
                    self.err("Unable to guess product name as product has no ups directory")
                    return 2
                product = utils.guessProduct(ups_dir)
            except RuntimeError, msg:
                self.err(msg)
                return 2
            base, v = os.path.split(os.path.abspath(self.opts.productDir))
            base, p = os.path.split(base)

            if product != p:
                self.err("Guessed product %s from ups directory, but %s from path" % (product, p))
                return 2

            version = v

        if not product:
            self.err("Please specify a product name and version")
            return 2
        if not version:
            self.err("Please also specify a product version")
            return 2

        if self.opts.tablefile and self.opts.externalTablefile:
            self.err("You may not specify both -m and -M")
            return 3

        tablefile = self.opts.tablefile
        if self.opts.externalTablefile:
            if self.opts.externalTablefile == "-":
                tablefile = sys.stdin
            else:
                try:
                    tablefile = open(self.opts.externalTablefile, "r")
                except IOError, e:
                    self.err("Error opening %s: %s" % (self.opts.externalTablefile, e))
                    return 4

        try:
            myeups = self.createEups()
        except eups.EupsException, e:
            e.status = 9
            raise

        if self.opts.tag:
            try:
                tag = myeups.tags.getTag(self.opts.tag)

                if myeups.isReservedTag(tag):
                    if self.opts.force:
                        self.err("%s is a reserved tag, but proceeding anyway)" % self.opts.tag)
                    else:
                        self.err("%s is a reserved tag (use --force to set)" % self.opts.tag)
                        return 1
            except eups.TagNotRecognized:
                self.err("%s: Unsupported tag name" % self.opts.tag)
                return 1
            except eups.EupsException, e:
                e.status = 9
                raise

        try:
            eups.declare(product, version, self.opts.productDir, 
                         tablefile=tablefile, tag=self.opts.tag, eupsenv=myeups)
        except eups.EupsException, e:
            e.status = 2
            raise

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
        self.addEupsOptions()

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-c", "--current", dest="tag", action="store_const", const="current",
                            help="same as --tag=current (deprecated)")
        

    def execute(self):
        if len(self.args) == 0:
            self.err("Please specify a product name")
            return 3
        product = self.args[0]
        version = None
        if len(self.args) > 1:
            version = self.args[1]

        try:
            myeups = self.createEups()
        except eups.EupsException, e:
            e.status = 9
            raise

        if self.opts.tag:
            try:
                tag = myeups.tags.getTag(self.opts.tag)

                if myeups.isReservedTag(tag):
                    if self.opts.force:
                        self.err("%s is a reserved tag, but proceeding anyway)" % self.opts.tag)
                    else:
                        self.err("%s is a reserved tag (use --force to unset)" % self.opts.tag)
                        return 1
            except eups.TagNotRecognized:
                self.err("%s: Unsupported tag name" % self.opts.tag)
                return 1

        try:
            eups.undeclare(product, version, tag=self.opts.tag, eupsenv=myeups)
        except eups.EupsException, e:
            e.status = 2
            raise

        return 0


class RemoveCmd(EupsCmd):

    usage = "%prog remove [-h|--help] [options] product version"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Completely remove a product.  In particular, remove its root directory
where it is installed.
"""

    def addOptions(self):
        # these are specific to this command
        self.clo.add_option("-i", "--interactive", dest="interactive", action="store_true",
                            help="Prompt user before actually removing products (default if -R)")
        self.clo.add_option("-N", "--noCheck", dest="noCheck", action="store_true", default=False,
                            help="Don't check whether recursively removed products are needed")
        self.clo.add_option("-R", "--recursive", dest="recursive", action="store_true", default=False,
                            help="Recursively also remove everything that this product depends on")
        self.clo.add_option("--noInteractive", dest="interactive", action="store_false",
                            help="Don't prompt user before actually removing products")
        
        # these options are used to configure the Eups instance
        self.addEupsOptions()

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

    def execute(self):
        if len(self.args) == 0:
            self.err("Please specify a product name and version")
            return 2
        if len(self.args) < 2:
            self.err("Please also specify a product version")
            return 2
        product = self.args[0]
        version = self.args[1]

        try:
            myeups = self.createEups()
        except eups.EupsException, e:
            e.status = 9
            raise

        if myeups.isUserTag(self.opts.tag):
            myeups.includeUserDataDirInPath()
            
        try:
            myeups.remove(product, version, self.opts.recursive,
                          checkRecursive=not self.opts.noCheck, 
                          interactive=self.opts.interactive)
        except eups.EupsException, e:
            e.status = 1
            raise

        return 0


class AdminCmd(EupsCmd):

    usage = "%prog admin [buildCache|clearCache|listCache|clearLocks|clearServerCache|info] [-h|--help] [-r root]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""manage eups internals (e.g. cache data).  By default, these operations apply to the 
user caches; with -A, they will apply to all caches under EUPS_PATH directories
that are writable by the user.  
"""

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addEupsOptions()

        self.clo.add_option("-A", "--admin-mode", dest="asAdmin", action="store_true", default=False, 
                            help="apply cache operations to caches under EUPS_PATH")
        self.clo.add_option("-r", "--root", dest="root", action="store", 
                            help="Location of manifests/buildfiles/tarballs " +
                            "(may be a URL or scp specification).  Default: find in $EUPS_PKGROOT")

        self.clo.disable_interspersed_args() # associate opts with subcommands

    def run(self):
        if len(self.args) > 0:
            return self.execute()
        return EupsCmd.run(self)

    def execute(self):
        if len(self.args) < 1:
            self.err("Please specify an admin subcommand")
            print >> self._errstrm, self.clo.get_usage()
            return 2
        subcmd = self.args[0]

        ecmd = makeEupsCmd("%s %s" % (self.cmd, subcmd), self.clargs, self.prog)
        if ecmd:                        # new way of parsing
            return ecmd.run()

        if subcmd == "clearCache":
            eups.clearCache(inUserDir=not self.opts.asAdmin)
        elif subcmd == "buildCache":
            eups.clearCache(inUserDir=not self.opts.asAdmin)
            eups.Eups(readCache=True, asAdmin=self.opts.asAdmin)
        elif subcmd == "listCache":
            eups.listCache(verbose=self.opts.verbose)
        elif subcmd == "clearLocks":
            eups.Eups(readCache=False, verbose=self.opts.verbose).clearLocks()
        elif subcmd == "clearServerCache":
            pkgroots = self.opts.root
            if pkgroots is None and os.environ.has_key("EUPS_PKGROOT"):
                pkgroots = os.environ["EUPS_PKGROOT"]

            myeups = eups.Eups(readCache=False)
            # FIXME: this is not clearing caches in the user's .eups dir.
            ServerConf.clearConfigCache(myeups, pkgroots, self.opts.verbose)
        else:
            self.err("Unrecognized admin subcommand: %s" % subcmd)
            return 10

        return 0

class AdminInfoCmd(EupsCmd):
    usage = "%prog admin info [-h|--help] [options] product [version]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Provide info about the specified product
"""

    def addOptions(self):
        self.clo.enable_interspersed_args()

        # these options are used to configure the Eups instance
        self.addEupsOptions()

        # this will override the eups option version

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-t", "--tag", dest="tag", action="store",
                            help="[info] list only versions having this tag name")

    def execute(self):
        self.args.pop(0)                # remove the "info"
        
        if len(self.args) == 0:
            self.err("Please specify a product name")
            return 2
        productName = self.args[0]

        versionName = None
        if len(self.args) > 1:
            versionName = self.args[1]

        try:
            myeups = self.createEups()
        except eups.EupsException, e:
            e.status = 9
            raise

        if self.opts.tag:
            if versionName:
                self.err("You may not specify a tag and an explicit version: %s --tag %s %s" %
                         (productName, self.opts.tag, versionName))
                return 2
                
            prod = myeups.findTaggedProduct(productName, self.opts.tag)
            if prod:
                versionName = prod.version
            else:
                self.err("Unable to lookup %s --tag %s" % (productName, self.opts.tag))
                return 2

        if not versionName:
            prod = myeups.findProduct(productName)
            if prod:
                versionName = prod.version
            else:
                self.err("Unable to find a default version of %s" % (productName))
                return 2
            
        if len(self.args) > 2:
            self.err("Unexpected trailing arguments: %s" % self.args[2])
            return 2

        import eups.db.VersionFile as VersionFile

        for eupsDb in myeups.versions.keys():
            db = myeups._databaseFor(eupsDb)
            if self.opts.tag:
                vfile = db.getChainFile(self.opts.tag, productName)
                if vfile:
                    vfile = vfile.file
            else:
                vfile = db._findVersionFile(productName, versionName)
                
            if vfile:
                print vfile
                return 0

        self.err("Unable to lookup version file for %s %s" % (productName, versionName))
        return 1

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class DistribCmd(EupsCmd):

    usage = "%prog distrib [list|install|clean|create] [-h|--help] [options] ..."

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = True

    description = \
"""Interact with package distribution servers either as a user installing 
packages or as a provider maintaining a server.  

An end-user uses the following sub-commands to install packages:
   list      list the available packages from distribution servers
   install   download and install a package
   clean     clean up any leftover build files from an install (that failed)
To use these, the user needs write-access to a product stack and database.

A server provider uses:
   create    create a distribution package from an installed product
To create packages, one must have a write permission to a local server.

Type "eups distrib [subcmd] -h" to get more info on a sub-command.  

Common """

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addEupsOptions()

        self.clo.disable_interspersed_args()

    def run(self):
        if len(self.args) > 0:
            return self.execute()
        return EupsCmd.run(self)

    def execute(self):
        if len(self.args) < 1:
            self.err("Please specify a distrib subcommand")
            print >> self._errstrm, self.clo.get_usage()
            return 2
        subcmd = self.args[0]

        cmd = "%s %s" % (self.cmd, subcmd)
        
        ecmd = makeEupsCmd(cmd, self.clargs, self.prog)
        if ecmd is None:
            self.err("Unrecognized distrib subcommand: %s" % subcmd)
            return 10

        return ecmd.run()

class DistribListCmd(EupsCmd):

    usage = "%prog distrib list [-h|--help] [options] [product [version]]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""List available packages from the package distribution repositories.  
"""

    def addOptions(self):
        self.clo.enable_interspersed_args()

        self.clo.add_option("-D", "--distrib-class", dest="distribClasses", action="append",
                            help="register this Distrib class (repeat as needed)")
        self.clo.add_option("-f", "--flavor", dest="flavor", action="store",
                            help="Specifically list for this flavor")
        self.clo.add_option("-r", "--repository", dest="root", action="append", metavar="BASEURL",
                            help="the base URL for a repository to access (repeat as needed).  " +
                            "Default: $EUPS_PKGROOT")
        self.clo.add_option("-S", "--server-class", dest="serverClasses", action="append",
                            help="register this DistribServer class (repeat as needed)")
        self.clo.add_option("-S", "--server-option", dest="serverOpts", action="append",
                            help="pass a customized option to all repositories " +
                            "(form NAME=VALUE, repeat as needed)")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("--root", dest="root", action="append",
                            help="equivalent to --repository (deprecated)")

    def execute(self):
        # get rid of sub-command arg
        self.args.pop(0)

        product = version = None
        if len(self.args) > 0:
            product = self.args[0]
        if len(self.args) > 1:
            version = self.args[1]

        pkgroots = self.opts.root
        if not pkgroots and os.environ.has_key("EUPS_PKGROOT"):
            pkgroots = os.environ["EUPS_PKGROOT"]
        if not pkgroots:
            self.err("Please specify a repository with -r or $EUPS_PKGROOT")
            return 2

        # FIXME: enable use of these options
        if self.opts.serverClasses and not self.opts.quiet:
            self.err("Warning: --server-class option currently disabled")
        if self.opts.distribClasses and not self.opts.quiet:
            self.err("Warning: --distrib-class option currently disabled")

        options = None
        if self.opts.serverOpts:
            options = {}
            for opt in self.opts.serverOpts:
                try:
                    name, val = opt.split("=",1)
                except ValueError:
                    self.err("server option not of form NAME=VALUE: "+opt)
                    return 3
                options[name] = value

        myeups = eups.Eups(readCache=False)

        try:
            repos = distrib.Repositories(pkgroots, options, myeups, 
                                         verbosity=self.opts.verbose)

            data = repos.listPackages(product, version, self.opts.flavor)
        except eups.EupsException, e:
            e.status = 1
            raise

        primary = "primary"
        for i in xrange(len(data)):
            pkgroot, pkgs = data[i]
            if i == 1:  primary = "secondary"
            if len(pkgs) > 0:
                if len(data) > 1:
                    print "Available products from %s server: %s" % \
                        (primary, pkgroot)
                for (name, ver, flav) in pkgs:
                    print "  %-20s %-10s %s" % (name, flav, ver)
            else:
                print "No matching products available from %s server (%s)" % (primary, pkgroot)

        return 0

        
class DistribInstallCmd(EupsCmd):

    usage = "%prog distrib install [-h|--help] [options] product [version]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Install a product from a distribution package retrieved from a repository.
If a version is not specified, the most version with the most preferred 
tag will be installed.  
"""

    def addOptions(self):
        self.clo.enable_interspersed_args()

        self.clo.add_option("-d", "--declareAs", dest="tagAs", action="append", metavar="TAG",
                            help="tag all newly installed products with this user TAG (repeat as needed)")
        self.clo.add_option("-g", "--groupAccess", dest="groupperm", action="store", metavar="GROUP",
                            help="Give specified group r/w access to all newly installed packages")
        self.clo.add_option("-I", "--install-into", dest="installStack", action="append", metavar="DIR",
                            help="install into this product stack " +
                            "(Default: the first writable stack in $EUPS_PATH)")
        self.clo.add_option("-m", "--manifest", dest="manifest", action="store",
                            help="Use this manifest file for the requested product")
        self.clo.add_option("-U", "--no-server-tags", dest="updateTags", action="store_false", default=True,
                            help="Prevent automatic assignment of server/global tags")
        self.clo.add_option("--noclean", dest="noclean", action="store_true", default=False,
                            help="Don't clean up after successfully building the product")
        self.clo.add_option("-j", "--nodepend", dest="nodepend", action="store_true", default=False,
                            help="Just install product, but not its dependencies")
        self.clo.add_option("-N", "--noeups", dest="noeups", action="store_true", default=False,
                            help="Don't attempt to lookup product in eups (always install)")
        self.clo.add_option("-r", "--repository", dest="root", action="append", metavar="BASEURL",
                            help="the base URL for a repository to access (repeat as needed).  " +
                            "Default: $EUPS_PKGROOT")
        self.clo.add_option("-t", "--tag", dest="tag", action="store",
                            help="preferentially install products with this TAG")
        self.clo.add_option("-T", "--tmp-dir", dest="builddir", action="store", metavar="DIR",
                            help="Build products in this directory")
        self.clo.add_option("--nobuild", dest="nobuild", action="store_true", default=False,
                            help="Don't attempt to build the product; just declare it")

        # these options are used to configure the Eups instance
        self.addEupsOptions()

        self.clo.add_option("-D", "--distrib-class", dest="distribClasses", action="append",
                            help="register this Distrib class (repeat as needed)")
        self.clo.add_option("-S", "--server-option", dest="serverOpts", action="append",
                            help="pass a customized option to all repositories " +
                            "(form NAME=VALUE, repeat as needed)")
        self.clo.add_option("-S", "--server-class", dest="serverClasses", action="append",
                            help="register this DistribServer class (repeat as needed)")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("--recurse", dest="searchDep", action="store_true", default=False, 
                            help="don't assume manifests completely specify dependencies")
        self.clo.add_option("--root", dest="root", action="append",
                            help="equivalent to --repository (deprecated)")
        self.clo.add_option("-C", "--current", dest="current", action="store_true", default=False, 
                            help="deprecated (use --tag or --no-server-tags)")

    def execute(self):
        # get rid of sub-command arg
        self.args.pop(0)

        if len(self.args) < 1:
           self.err("please specify at least a product name")
           print >> self._errstrm, self.clo.get_usage()
           return 5

        product = self.args[0]
        if len(self.args) > 1:
            version = self.args[1]
        else:
            version = None

        if self.opts.installStack:
            if not utils.isDbWritable(self.opts.installStack) and \
               not utils.isDbWritable(os.path.join(self.opts.installStack,Eups.ups_db)):
                self.err("Requested install stack not writable: " +
                         self.opts.installStack)
                return 2

            # place install root at front of the path given to Eups
            if self.opts.path is None:
                if os.environ.has_key("EUPS_PATH"):
                    self.opts.path = os.environ["EUPS_PATH"]
            if self.opts.path is None:
                self.opts.path = self.opts.installStack
            else:
                self.opts.path = "%s:%s" % (self.opts.installStack, self.opts.path)

        try:
            myeups = self.createEups()
        except eups.EupsException, e:
            e.status = 9
            raise

        if self.opts.tag:
            try:
                tag = myeups.tags.getTag(self.opts.tag)
                prefs = myeups.getPreferredTags()
                myeups.setPreferredTags([self.opts.tag] + prefs)
                if not version:  version = tag
            except eups.TagNotRecognized, e:
                self.err(str(e))
                return 4

        if self.opts.tagAs:
            unrecognized = []
            nonuser = []
            for tag in self.opts.tagAs:
                try:
                    tag = myeups.tags.getTag(tag)
                    if not tag.isUser():
                        nonuser.append(tag.name)
                except eups.TagNotRecognized, e:
                    unrecognized.append(tag.name)

            if nonuser:
                self.err("Can only assign user tags; Non-user tags: " +
                         ", ".join(nonuser))
            if unrecognized:
                self.err("Unrecognized user tags: " + ", ".join(unrecognized))
            if nonuser or unrecognized:
                return 4

        dopts = {}
        # handle extra options
        dopts = { 'config': {} }
        dopts['noeups']     = self.opts.noeups
        dopts['noaction']   = self.opts.noaction
        dopts['nobuild']   = self.opts.nobuild
        dopts['noclean']   = self.opts.noclean
        if self.opts.serverOpts:
            for opt in self.opts.serverOpts:
                try:
                    name, val = opt.split("=",1)
                except ValueError:
                    self.err("server option not of form NAME=VALUE: "+opt)
                    return 3
                dopts[name] = value


        if not self.opts.root:
            if not os.environ.has_key("EUPS_PKGROOT"):
                self.err("No repositories specified; please set -r or EUPS_PKGROOT")
                return 3
            self.opts.root = os.environ["EUPS_PKGROOT"]

        log = None
        if self.opts.quiet:
            log = open("/dev/null", "w")

        try:
            repos = distrib.Repositories(self.opts.root, dopts, myeups, 
                                         self.opts.flavor, 
                                         verbosity=self.opts.verbose, log=log)
            repos.install(product, version, self.opts.updateTags, 
                          self.opts.tagAs, self.opts.nodepend, 
                          self.opts.noclean, self.opts.noeups, dopts, 
                          self.opts.manifest, self.opts.searchDep)
        except eups.EupsException, e:
            e.status = 1
            if log:
                log.close()
            raise

        if log:  log.close()
        return 0


class DistribCleanCmd(EupsCmd):

    usage = "%prog distrib clean [-h|--help] [options] product version"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Clean out the remnants of a package installation for a given product.  
This will remove the build directory as well as (if possible) a partially 
installed product if they exist.  If the -R is provided, the installed 
product will be fully removed, even if its installation was successful.
"""

    def addOptions(self):
        self.clo.enable_interspersed_args()

        self.clo.add_option("-P", "--product-dir", dest="pdir", action="store", metavar="DIR",
                            help="Assume the DIR is the product's installation/root directory")
        self.clo.add_option("-R", "--remove", dest="remove", action="store_true", default=False,
                            help="Also remove the named product after cleaning")
        self.clo.add_option("-r", "--repository", dest="root", action="append", metavar="BASEURL",
                            help="the base URL for a repository to access (repeat as needed).  " +
                            "Default: $EUPS_PKGROOT")
        self.clo.add_option("-T", "--tmp-dir", dest="builddir", action="store", metavar="DIR",
                            help="Assume the build was done under DIR")

        # these options are used to configure the Eups instance
        self.addEupsOptions()
 
        self.clo.add_option("-D", "--distrib-class", dest="distribClasses", action="append",
                            help="register this Distrib class (repeat as needed)")
        self.clo.add_option("-S", "--server-class", dest="serverClasses", action="append",
                            help="register this DistribServer class (repeat as needed)")
        self.clo.add_option("-S", "--server-option", dest="serverOpts", action="append",
                            help="pass a customized option to all repositories (form NAME=VALUE, repeat as needed)")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("--root", dest="root", action="append",
                            help="equivalent to --repository (deprecated)")

    def execute(self):
        # get rid of sub-command arg
        self.args.pop(0)

        if len(self.args) == 0:
            self.err("Please specify a product name and version")
            return 2
        if len(self.args) < 2:
            self.err("Please also specify a product version")
            return 2
        product = self.args[0]
        version = self.args[1]

        if not self.opts.root:
            if not os.environ.has_key("EUPS_PKGROOT"):
                self.err("No repositories specified; please set -r or EUPS_PKGROOT")
                return 4
            self.opts.root = os.environ["EUPS_PKGROOT"]

        dopts = {}
        if self.opts.serverOpts:
            for opt in self.opts.serverOpts:
                try:
                    name, val = opt.split("=",1)
                except ValueError:
                    self.err("server option not of form NAME=VALUE: "+opt)
                    return 3
                dopts[name] = value

        log = None
        if self.opts.quiet:
            log = open("/dev/null", "w")

        try:
            myeups = self.createEups()
        except eups.EupsException, e:
            e.status = 9
            raise

        try:
            repos = distrib.Repositories(self.opts.root, dopts, myeups, 
                                         self.opts.flavor, 
                                         verbosity=self.opts.verbose, log=log)
            repos.clean(product, version, self.opts.flavor, dopts, 
                        self.opts.pdir, self.opts.remove)

        except eups.EupsException, e:
            e.status = 1
            if log:
                log.close()
            raise

class DistribCreateCmd(EupsCmd):

    usage = "%prog distrib create [-h|--help] [options] product version"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Create a distribution package for a specified product
"""

    def addOptions(self):
        self.clo.enable_interspersed_args()

        self.clo.add_option("-a", "--as", dest="packageId", action="store",
                            help="Create a distribution with this name")
        self.clo.add_option("-d", "--distribType", dest="distribTypeName", action="store",
                            help="Create a distribution with this type name (e.g. 'tarball', 'builder')")
        self.clo.add_option("-I", "--incomplete", dest="allowIncomplete", action="store_true",
                            help="Allow a manifest including packages we don't know how to install")
        self.clo.add_option("-m", "--manifest", dest="manifest", action="store",
                            help="Use this manifest file for the requested product")
        self.clo.add_option("-j", "--nodepend", dest="nodepend", action="store_true", default=False,
                            help="Just create package for named product, not its dependencies")
        self.clo.add_option("-r", "--repository", dest="repos", action="append", metavar="BASEURL",
                            help="the base URL for other repositories to consult (repeat as needed).  " +
                            "Default: $EUPS_PKGROOT")
        self.clo.add_option("-s", "--server-dir", dest="serverDir", action="store", metavar="DIR",
                            help="the directory tree to save created packages under")

        # these options are used to configure the Eups instance
        self.addEupsOptions()

        # this will override the eups option version
        self.clo.add_option("-D", "--distrib-class", dest="distribClasses", action="append",
                            help="register this Distrib class (repeat as needed)")
        self.clo.add_option("-S", "--server-class", dest="serverClasses", action="append",
                            help="register this DistribServer class (repeat as needed)")
        self.clo.add_option("-S", "--server-option", dest="serverOpts", action="append",
                            help="pass a customized option to all repositories " +
                            "(form NAME=VALUE, repeat as needed)")
        self.clo.add_option("-f", "--use-flavor", dest="useflavor", action="store_true", default=False,
                            help="Create an installation specialised to the current flavor")
        self.clo.add_option("--flavor", dest="flavor", action="store",
                            help="Assume this target platform flavor (e.g. 'Linux')")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-C", "--current", dest="current", action="store_true", default=False, 
                            help="deprecated (ignored)")

    def execute(self):
        # get rid of sub-command arg
        self.args.pop(0)

        if len(self.args) == 0:
            self.err("Please specify a product name and version")
            return 2
        if len(self.args) < 2:
            self.err("Please also specify a product version")
            return 2
        product = self.args[0]
        version = self.args[1]

        if not self.opts.repos:
            if os.environ.has_key("EUPS_PKGROOT"):
                self.opts.repos = os.environ["EUPS_PKGROOT"].split("|")
            else:
                self.opts.repos = []
        if not self.opts.serverDir:
            for pkgroot in repos:
                if utils.isDbWritable(pkgroot):
                    self.opts.serverDir = pkgroot
                    break
        elif not os.path.exists(self.opts.serverDir):
            self.err("Server directory does not exist: " + self.opts.serverDir)
            return 3
        elif not utils.isDbWritable(self.opts.serverDir):
            self.err("Server directory is not writable: " + self.opts.serverDir)
            return 3
        if not self.opts.serverDir:
            self.err("No writeable package server found; use --serverDir")
            return 3

        try:
            myeups = self.createEups()
        except eups.EupsException, e:
            e.status = 9
            raise

        dopts = {}
        # handle extra options
        dopts = { 'config': {} }
        dopts['noeups']     = self.opts.noeups
        dopts['noaction']   = self.opts.noaction
        if self.opts.serverOpts:
            for opt in self.opts.serverOpts:
                try:
                    name, val = opt.split("=",1)
                except ValueError:
                    self.err("server option not of form NAME=VALUE: "+opt)
                    return 3
                dopts[name] = value

        if not self.opts.distribTypeName:
            self.err("Please specify a distribution type name (e.g. -d tarball, etc)")
            return 4

        log = None
        if self.opts.quiet:
            log = open("/dev/null", "w")

        try:
            repos = None
            if not self.opts.force:
                repos = distrib.Repositories(self.opts.repos, dopts, myeups,
                                             self.opts.flavor, 
                                             verbosity=self.opts.verbose, 
                                             log=log)

            server = distrib.Repository(myeups, self.opts.serverDir, 
                                        self.opts.flavor, options=dopts, 
                                        verbosity=self.opts.verbose, log=log)
            server.create(self.opts, self.opts.distribTypeName, product,
                          version, nodepend=self.opts.nodepend, options=dopts,
                          manifest=self.opts.manifest, 
                          packageId=self.opts.packageId, repositories=repos)

        except eups.EupsException, e:
            e.status = 1
            raise

        return 0
        
class TagsCmd(EupsCmd):

    usage = "%prog tags [-h|--help] [options]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print information about known tags
"""

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-F", "--force", dest="force", action="store_true", default=False,
                            help="Force requested behaviour")

    def execute(self):
        myeups = eups.Eups(readCache=True, force=self.opts.force)

        print " ".join(myeups.tags.getTagNames(omitPseudo=True))

        return 0

class VroCmd(EupsCmd):

    usage = "%prog vro [-h|--help] [options] product [version]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print information about the Version Resolution Order (VRO) to use if issuing the setup command with the
same arguments.
"""

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-e", "--exact", dest="exact_version", action="store_true", default=False, 
                            help="Consider the as-installed versions, not the conditionals in the table file ")
        self.clo.add_option("-F", "--force", dest="force", action="store_true", default=False,
                            help="Force requested behaviour")
        self.clo.add_option("-r", "--root", dest="productDir", action="store", 
                            help="root directory where product is installed")
        self.clo.add_option("-t", "--tag", dest="tag", action="store",
                            help="List only versions having this tag name")
        self.clo.add_option("-z", "--select-db", dest="dbz", action="store", metavar="DIR",
                            help="Select the product paths which contain this directory.  " +
                            "Default: all in path")

    def execute(self):
        if len(self.args) == 0:
            product = None
        else:
            product = self.args[0]      # product's value is not actually used

        if len(self.args) > 1:
            versionName = self.args[1]
        else:
            versionName = None

        if self.opts.exact_version:
            if self.opts.setupType:
                self.opts.setupType += ","
            self.opts.setupType += "exact"

        myeups = eups.Eups(readCache=True, force=self.opts.force, setupType=self.opts.setupType)

        myeups.selectVRO(self.opts.tag, self.opts.productDir, versionName, self.opts.dbz)

        if myeups.isUserTag(self.opts.tag):
            myeups.includeUserDataDirInPath()
            
        print " ".join(myeups.getVRO())

        return 0

class HelpCmd(EupsCmd):

    usage = "%prog help [-h|--help]"

    # set this to True if the description is preformatted.  If false, it 
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Provide help on eups commands; equivalent to --help
"""

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

    def execute(self):
        if not self.opts.quiet:
            if self.opts.version:
                self.printVersion()
            cmd = EupsCmd(["-h"], self.prog)
            cmd.clo.print_help()
        return 0


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

    def __init__(self, helpstrm=None, usage=None, description=None, 
                 formatdesc=True, prog=None):
                 
        optparse.OptionParser.__init__(self, usage=usage, 
                                       description=description, 
                                       prog=prog, 
                                       add_help_option=False,
                                       conflict_handler="resolve")

        self._preformattedDescr = not formatdesc
        if not helpstrm:
            helpstrm = _errstrm
        self._helpstrm = helpstrm

    def print_help(self):
        optparse.OptionParser.print_help(self, self._helpstrm) # optparse.OptionParser is an old-style class, damn them

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
register("remove",       RemoveCmd)
register("admin",        AdminCmd)
register("admin info",   AdminInfoCmd)
register("distrib",      DistribCmd)
register("distrib list",    DistribListCmd)
register("distrib install", DistribInstallCmd)
register("distrib clean",   DistribCleanCmd)
register("distrib create",  DistribCreateCmd)
register("tags",         TagsCmd)
register("vro",          VroCmd)
register("help",         HelpCmd)


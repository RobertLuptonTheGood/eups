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

from __future__ import absolute_import, print_function
import re
import os
import sys
import copy
import optparse
import eups
from . import lock
from . import tags
from . import utils
from . import distrib
from . import hooks
from .distrib.server import ServerConf, Mapping, importClass

_errstrm = utils.stderr

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
	flags		Show the value of $EUPS_FLAGS
	flavor		Return the current flavor
        help            Provide help on eups commands
	list            List some or all products
        path [n]        Print the current eups path, or an element thereof
        pkgroot [n]     Print the current eups pkgroot, or an element thereof
	pkg-config	Return the options associated with product
	remove          Remove an eups product from the system
        startup         List files used (or potentially used) to configure eups
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
                            help="turn on specified debugging behaviors (allowed: debug, profile, raise)")
        self.clo.add_option("-h", "--help", dest="help", action="store_true",
                            help="show command-line help and exit")
        self.clo.add_option("--noCallbacks", dest="noCallbacks", action="store_true",
                            help="Disable all user-defined callbacks")
        self.clo.add_option("-n", "--noaction", dest="noaction", action="store_true", default=False,
                            help="Don\'t actually do anything (for debugging purposes)")
        self.clo.add_option("--nolocks", dest="nolocks", action="store_true", default=False,
                            help="Disable locking of eups's internal files")
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

        ecmd = makeEupsCmd(self.cmd, self)
        if ecmd is None:
            self.err("Unrecognized command: %s" % self.cmd)
            return 10

        if ecmd.opts.help:
            ecmd.lockType = None

        locks = lock.takeLocks(ecmd.cmd, eups.Eups.setEupsPath(ecmd.opts.path, ecmd.opts.dbz),
                               ecmd.lockType, nolocks=ecmd.opts.nolocks,
                               verbose=ecmd.opts.verbose - ecmd.opts.quiet)

        try:
            return ecmd.run()
        except:
            raise
        finally:
            lock.giveLocks(locks, ecmd.opts.verbose)

    def __init__(self, args=None, toolname=None, cmd=None, lockType=lock.LOCK_EX):
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

        # move -h/--help to the front of the list so they're always interpreted
        largs, rargs = [], []
        for a in args:
            if re.search(r"^(-h|--h(e(l(p)?)?)?)$", a):
                largs.append(a)
            else:
                rargs.append(a)
        args = largs + rargs
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

        self.lockType = lockType

    def run(self):
        if self._issubclass() and self.opts.help and self.cmd is not None:
            self.clo.print_help()
            return 0

        return self.execute()

    def printVersion(self, strm=sys.stderr):
        print("EUPS Version:", eups.version(), file=strm)
        return 0

    def _issubclass(self):
        return isinstance(self, EupsCmd) and type(self) != EupsCmd

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
            print(": %s" % msg, file=self._errstrm)

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

    def createEups(self, opts=None, versionName=None, readCache=None, quiet=0):
        if opts is None:
            opts = self.opts

        try:
            eups.commandCallbacks.apply(None, self.cmd, self.opts, self.args)
        except eups.OperationForbidden as e:
            e.status = 255
            raise
        except Exception as e:
            e.status = 9
            raise

        if readCache is None:
            if self.cmd in "admin flavor flags path".split():
                readCache = False
            else:
                readCache = True

        setupType = self.opts.setupType.split()

        ignorever = hasattr(opts, "ignorever") and opts.ignorever
        keep = hasattr(opts, "keep") and opts.keep
        asAdmin = hasattr(opts, "asAdmin") and opts.asAdmin
        exact_version = hasattr(opts, "exact_version") and opts.exact_version

        if hasattr(opts, "flavor"):
            flavor = opts.flavor
        else:
            flavor = None
        if hasattr(opts, "force"):
            force = opts.force
        else:
            force = None

        myeups = eups.Eups(flavor=flavor, path=opts.path, dbz=opts.dbz,
                         readCache=readCache, force=force,
                         ignore_versions=ignorever, setupType=setupType, cmdName=self.cmd,
                         keep=keep, verbose=opts.verbose, quiet=opts.quiet + quiet, vro=self.opts.vro,
                         noaction=opts.noaction, asAdmin=asAdmin, exact_version=exact_version)

        if hasattr(opts, "productDir"):
            productDir = opts.productDir
        else:
            productDir = None

        if hasattr(opts, "tag") and opts.tag:
            tag = opts.tag
            if utils.is_string(tag):
                tag = [tag]
        else:
            tag = None

        myeups.selectVRO(tag, productDir, versionName, opts.dbz)

        if True or (tag and myeups.isUserTag(tag[0])): # we always need the local definitions
            myeups.includeUserDataDirInPath()

        try:
            eups.commandCallbacks.apply(myeups, self.cmd, self.opts, self.args)
        except eups.OperationForbidden as e:
            e.status = 255
            raise
        except Exception as e:
            e.status = 9
            raise

        return myeups

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
        and sys.argv, which you may modify;  cmd == argv[1] if len(argv) > 1 otherwise None

        E.g.
        if cmd == "fetch":
            argv[1:2] = ["distrib", "install"]
        """
        CommandCallbacks.callbacks += [callback]

    def apply(self, myeups, cmd, opts, args):
        """Call the command callbacks on cmd"""

        if opts.noCallbacks:
            return

        for hook in CommandCallbacks.callbacks:
            hook(myeups, cmd, opts, args)

    def clear(self):
        """Clear the list of command callbacks"""
        CommandCallbacks.callbacks = []

    def list(self):
        for hook in CommandCallbacks.callbacks:
            print(hook, file=sys.stderr)

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
            print(self.opts.flavor)
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
        self.clo.add_option("-c", "--current", dest="currentTag", action="store_true", default=False,
                            help="same as --postTag=current")
        self.clo.add_option("-D", "--dependencies", dest="depends", action="store_true", default=False,
                            help="Print product's dependencies (must specify version if ambiguous). With --setup print the versions of dependent products that are actually setup.")
        self.clo.add_option("--depth", dest="depth", action="store",
                            help="Only list this many layers of dependency")
        self.clo.add_option("-d", "--directory", dest="printdir", action="store_true", default=False,
                            help="Include the product's installation directory")
        self.clo.add_option("-e", "--exact", dest="exact_version", action="store_true", default=False,
                            help="Follow the as-installed versions, not the dependencies in the table file ")
        self.clo.add_option("--name", dest="showName", action="store_true", default=False,
                            help="Print the product's name")
        self.clo.add_option("-r", "--root", dest="productDir", action="store",
                            help="root directory where product is installed")
        self.clo.add_option("--raw", action="store_true",
                            help="generate \"raw\" output (suitable for further processing)")
        self.clo.add_option("-s", "--setup", dest="setup", action="store_true", default=False,
                            help="List only product's that are setup.")
        self.clo.add_option("-S", "--showTags", dest="showTagsGlob", metavar="glob", default="*",
                            help="Only show tags that match this glob")
        self.clo.add_option("-m", "--table", dest="tablefile", action="store_true", default=False,
                            help="Print the name of the product's table file")
        self.clo.add_option("-t", "--tag", dest="tag", action="append",
                            help="List only versions having this tag name")
        self.clo.add_option("-T", "--type", dest="setupType", action="store", default="",
                            help="the setup type to assume (ignored unless -d is specified)")
        self.clo.add_option("--topological", dest="topological", action="store_true", default=False,
                            help="Return dependencies after a topological sort")
        self.clo.add_option("--checkCycles", action="store_true", default=False,
                            help="Generate an error if topological sort turns up a cycle")
        self.clo.add_option("-V", "--version", dest="version", action="store_true", default=False,
                            help="Print product version")

    def execute(self):
        product = version = None
        if len(self.args) > 0:
            product = self.args[0]
        if len(self.args) > 1:
            version = self.args[1]

        if self.opts.currentTag:
            if not self.opts.tag:
                self.opts.tag = []
            self.opts.tag.append("current")

        if not self.opts.quiet and \
           self.opts.depth and not self.opts.depends:
            print("Ignoring --depth as it only makes sense with --dependencies", file=utils.stdwarn)

        try:
            n = eups.printProducts(sys.stdout, product, version,
                                   self.createEups(self.opts, versionName=version, quiet=1),
                                   tags=self.opts.tag,
                                   setup=self.opts.setup,
                                   tablefile=self.opts.tablefile,
                                   directory=self.opts.printdir,
                                   dependencies=self.opts.depends,
                                   showVersion=self.opts.version, showName=self.opts.showName,
                                   showTagsGlob=self.opts.showTagsGlob,
                                   depth=self.opts.depth,
                                   productDir=self.opts.productDir, topological=self.opts.topological,
                                   checkCycles=self.opts.checkCycles,
                                   raw=self.opts.raw
                                   )
            if n == 0:
                msg = 'No products found'
                self.err(msg)

        except eups.ProductNotFound as e:
            msg = e.getMessage()
            if product == "distrib":
                e.msg += '; Maybe you meant "eups distrib list"?'
            e.status = 1
            raise

        except eups.EupsException as e:
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
                print("EUPS_FLAGS == %s" % (os.environ["EUPS_FLAGS"]))
            except KeyError:
                print("You have no EUPS_FLAGS set")
        return 0

class EnvListCmd(EupsCmd):

    def _init(self, what=None, delim=":"):
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
                self.err("%s does not have an element at position %s" %
                         (self.what, self.which))
                return 1
            except ValueError:
                self.err("Not an integer:  %s" % (self.which))
                return 2

        for e in elems:
            print(e)
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

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        # these options are used to configure the Eups instance
        self.addEupsOptions()

    def __init__(self, **kwargs):
        EnvListCmd.__init__(self, **kwargs)

    def execute(self):
        self._init()
        path = self.createEups(self.opts).path
        if not self.opts.verbose:
            path = [e for e in path if e != utils.defaultUserDataDir()]
        return self.printEnv(path)

class StartupCmd(EnvListCmd):

    usage = "%prog startup [-h|--help]"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""List the startup files that customize EUPS (including $EUPS_STARTUP).  With -v, show non-existent files
that would be loaded [in brackets].
"""

    def __init__(self, **kwargs):
        EnvListCmd.__init__(self, **kwargs)
        self._init("EUPS_STARTUP")

    def execute(self):
        myeups = eups.Eups(path=self.opts.path, dbz=self.opts.dbz)
        path = myeups.path

        for f in hooks.loadCustomization(execute=False, verbose=self.opts.verbose,
                                         quiet=self.opts.quiet, path=path, reset=True, includeAllFiles=True):

            if not self.opts.verbose and os.stat(f).st_size == 0:
                continue

            print("%-40s" % f)

        if self.opts.verbose > 1:
            print("See also $EUPS_STARTUP and/or $EUPS_USERDIR")

class PkgrootCmd(EnvListCmd):

    usage = """%prog pkgroot [-h|--help] [n]

Deprecated:  Use eups distrib path
"""

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print the base URLs for the repositories given via EUPS_PKGROOT.  An optional
integer argument, n, will cause just the n-th URL to be listed (where
0 is the first element).
"""

    def __init__(self, **kwargs):
        EnvListCmd.__init__(self, **kwargs)
        self.deprecated("this command is deprecated; please use eups distrib path")

        self._init("EUPS_PKGROOT", "|")

class PkgconfigCmd(EupsCmd):

    usage = "%prog pkgconfig [-h|--help] [options] product [version]"

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
            print(self.clo.get_usage(), file=self._errstrm)
            return 2

        productName = self.args[0]
        if len(self.args) > 1:
            versionName = self.args[1]
        else:
            versionName = None

        myeups = self.createEups()

        #
        # Time to do some real work
        #
        PKG_CONFIG_PATH = os.environ.get("PKG_CONFIG_PATH", "").split(":")
        #productList = myeups.findProduct(productName, versionName)
        #
        # Look for the best match
        product = None
        if versionName:
            # prefer explicitly specified version
            product = myeups.findProduct(productName, versionName)

        if not product:              # try setup version
            tag = eups.Tag("setup")
            product = myeups.findProduct(productName, tag)

        if not product:              # try most preferred tag
            product = myeups.findProduct(productName)

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
            if myeups.verbose:
                print("Reading %s" % pcfile, file=self._errstrm)

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

                    print(value)
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
                            help="Consider the as-installed versions, not the dependencies in the table file ")
        self.clo.add_option("-o", "--optional", dest="optional", action="store_true", default=False,
                            help="Show optional setups")
        self.clo.add_option("--pickle", dest="pickleFile", action="store",
                            help="Pickle the \"User\" data to pickleFile (or read it if it starts <)")
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
                           tags=self.opts.tag, pickleFile=self.opts.pickleFile)
        except eups.EupsException as e:
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

        self.clo.add_option("--repoversion", dest="repoversion", action="store",
                            help="The version name within the repository")

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

        myeups = self.createEups()

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
            except IOError as e:
                self.err('Failed to open file "%s" for read: %s' %
                         (inFile, str(e)))
                return 6

        if outdir:
            outfile = os.path.join(outdir, os.path.basename(inFile))
            if myeups.verbose:
                print("Writing to %s" % outfile)

            try:
                ofd = open(outfile, "w")
            except IOError as e:
                self.err('Failed to open file "%s" for write: %s' %
                         (outfile, str(e)))
                return 6

        elif self.opts.in_situ:
            tmpout = os.path.join(os.path.dirname(inFile),
                                  "."+os.path.basename(inFile)+".tmp")
            try:
                ofd = open(tmpout, "w")
            except IOError as e:
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
                                 self.opts.cvsroot, self.opts.repoversion,
                                 self.createEups())
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
        self.clo.add_option("-N", "--noVersionExpressions", dest="expandVersions",
                            action="store_false", default=True,
                            help="Don't add any relative versions to the expanded table")
        self.clo.add_option("--noExact", dest="addExactBlock",
                            action="store_false", default=True,
                            help="Don't add an exact block to the expanded table")
        self.clo.add_option("-P", "--productName", dest="toplevelName", action="store",
                            help="The product which owns the table file")
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
        except eups.EupsException as e:
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
            inFile = "stdin"
            ifd = sys.stdin
        else:
            if not os.path.isfile(inFile):
                self.err("%s: not an existing file" % inFile)
                return 6
            try:
                ifd = open(inFile)
            except IOError as e:
                self.err('Failed to open file "%s" for read: %s' %
                         (inFile, str(e)))
                return 6

        if outdir:
            outfile = os.path.join(outdir, os.path.basename(inFile))
            if myeups.verbose:
                print("Writing to %s" % outfile)

            try:
                ofd = open(outfile, "w")
            except IOError as e:
                self.err('Failed to open file "%s" for write: %s' %
                         (outfile, str(e)))
                return 6

        elif self.opts.in_situ:
            tmpout = os.path.join(os.path.dirname(inFile),
                                  "."+os.path.basename(inFile)+".tmp")
            try:
                ofd = open(tmpout, "w")
            except IOError as e:
                outfile = os.path.dirname(tmpout)
                if not outfile:  outfile = "."
                self.err('Failed to temporary file in "%s" for write: %s' %
                         (outfile, str(e)))
                return 6

        else:
            ofd = sys.stdout
        #
        # We'd like to know what product we're setting up (so as to avoid recursive setups), but this
        # may not be possible
        #
        toplevelName = self.opts.toplevelName
        if not toplevelName:
            mat = re.search(r"^(.*).table$", os.path.split(inFile)[1])
            if mat:
                toplevelName = mat.group(1)
            else:
                toplevelName = None

        try:
            try:
                try:                    # older pythons don't support try except finally
                    eups.expandTableFile(ofd, ifd, productList, self.opts.warnRegexp, myeups, self.opts.force,
                                         expandVersions=self.opts.expandVersions,
                                         addExactBlock=self.opts.addExactBlock,
                                         toplevelName=toplevelName)
                except Exception as e:
                    e.args = ["Processing %s: %s" % (inFile, e)]
                    raise

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
        self.clo.add_option("-L", "--import-file", dest="externalFileList", action="append", default=[],
                            help="Import the given file directly into $PRODUCT_DIR_EXTRA")
        self.clo.add_option("-M", "--import-table", dest="externalTablefile", action="store",
                            help="Import the given table file directly into the database " +
                            "(may be \"-\" for stdin).")
        self.clo.add_option("-m", "--table", dest="tablefile", action="store",
                            help='table file location (may be "none" for no table file)')
        self.clo.add_option("-t", "--tag", dest="tag", action="append",
                            help="assign TAG to the specified product")

        # these options are used to configure the Eups instance
        self.addEupsOptions()

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-c", "--current", dest="currentTag", action="store_true", default=False,
                            help="same as --tag=current")

    def execute(self):
        try:
            myeups = self.createEups()
        except eups.EupsException as e:
            e.status = 9
            raise

        externalFileList = []
        product, version = None, None
        if len(self.args) > 0:
            product = self.args[0]
        if len(self.args) > 1:
            version = self.args[1]

        if self.opts.currentTag:
            if not self.opts.tag:
                self.opts.tag = []
            self.opts.tag.append("current")
        if self.opts.tag:
            if len(self.opts.tag) > 1:
                self.err("You may only set one tag at a time: %s" % ", ".join(self.opts.tag))
                return 4

            self.opts.tag = self.opts.tag[0]

        if not product:
            if self.opts.tablefile == "none":
                self.err("Unable to guess product name from table file name %s" % self.opts.tablefile)
                return 2
            if self.opts.externalTablefile != None:
                self.err("Unable to guess product name from external table file \"%s\"" %
                         self.opts.externalTablefile)
                return 2

            if not self.opts.productDir:
                self.err("Unable to guess product name as you didn't specify a directory")
                return 2
            if self.opts.productDir == "none":
                self.err("Unable to guess product name as product has no directory")
                return 2

            try:
                ups_dir = os.path.join(self.opts.productDir,"ups")
                if not os.path.isdir(ups_dir):
                    self.err("Unable to guess product name as product has no ups directory")
                    return 2
                product = utils.guessProduct(ups_dir)
            except RuntimeError as msg:
                self.err(msg)
                return 2
            base, v = os.path.split(os.path.abspath(self.opts.productDir))
            base, p = os.path.split(base)

            if product == p:
                if not version:
                    version = v
            else:
                if not (version or self.opts.tag):
                    self.err("Guessed product %s from ups directory, but %s from path" % (product, p))
                    return 2

        if not version and self.opts.tag:
            version = "tag:%s" % self.opts.tag # We're declaring a tagged version so we don't need a name

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
                except IOError as e:
                    self.err("Error opening %s: %s" % (self.opts.externalTablefile, e))
                    return 4

        if self.opts.verbose:
            print("Declaring %s %s" % (product, version), file=utils.stdinfo)

        for f0 in self.opts.externalFileList:
            if f0 == "-":
                print("eups declare --import-file does not interpret \"-\" as stdin; ask RHL nicely", file=_errstrm)
                return 4

            f = f0.split(":")
            fileNameIn = f.pop(0)

            if not os.path.exists(fileNameIn):
                print("File %s does not exist" % fileNameIn, file=_errstrm)
                return 4

            dirName, fileName = "", None
            if f:
                arg = f.pop(0)
                if f:
                    print("Unexpected trailing text on %s: %s" % (f, ":".join(f)), file=utils.stdwarn)

                if re.search("/", arg):
                    dirName, fileName = os.path.split(arg)
                else:
                    fileName = arg

            if not fileName:
                fileName = fileNameIn
                if re.search("/", fileName):
                    fileName = os.path.split(fileName)[1]

            externalFileList.append((fileNameIn, os.path.join(dirName, fileName),))

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
            except eups.EupsException as e:
                e.status = 9
                raise

        try:
            eups.declare(product, version, self.opts.productDir,
                         tablefile=tablefile, externalFileList=externalFileList,
                         tag=self.opts.tag, eupsenv=myeups)
        except eups.EupsException as e:
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
                            help="same as --tag=current")
        self.clo.add_option("-U", "--undeclareVersion", action="store_true",
                            help="Declare the version as well as the tag")

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
        except eups.EupsException as e:
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
        elif self.opts.undeclareVersion:
            self.err("--undeclareVersion only makes sense when you specify a tag")
            return 1

        try:
            eups.undeclare(product, version, tag=self.opts.tag, eupsenv=myeups,
                           undeclareVersionAndTag=self.opts.undeclareVersion)
        except eups.EupsException as e:
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
        self.clo.add_option("-t", "--tag", dest="tag", action="store", help="Delete this tag")

        # these options are used to configure the Eups instance
        self.addEupsOptions()

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

    def execute(self):
        try:
            myeups = self.createEups()
        except eups.EupsException as e:
            e.status = 9
            raise

        tagName = self.opts.tag
        if tagName and not self.args: # we're deleting a tag
            pass
        else:
            if len(self.args) == 0:
                self.err("Please specify a product name and version or tag")
                return 2
            product = self.args[0]

            if len(self.args) < 2:
                if tagName:
                    versions = [p.version for p in myeups.findProducts(product, tags=[tagName])]
                    if not versions:
                        self.err("Failed to lookup tag %s for product %s" % (tagName, product))
                        return 2
                    elif len(versions) == 1:
                        version = versions[0]
                        tagName = None
                    else:
                        self.err("Tag %s for product %s is applied to more than one version: %s" %
                                 (product, ", ".join(versions)))
                        return 2
                else:
                    self.err("Please also specify a product version")
                    return 2
            else:
                version = self.args[1]

        if tagName:
            try:
                tag = myeups.tags.getTag(tagName)

                if myeups.isReservedTag(tag):
                    if self.opts.force:
                        self.err("%s is a reserved tag, but proceeding anyway)" % tagName)
                    else:
                        self.err("%s is a reserved tag (use --force to unset)" % tagName)
                        return 1
            except eups.TagNotRecognized:
                self.err("%s: Unsupported tag name" % tagName)
                return 1

            for prod in myeups.findProducts(None, None, [tag]):
                if self.opts.verbose:
                    print("Untagging %s %s" % (prod.name, prod.version), file=sys.stderr)

                myeups.unassignTag(tag, prod.name, prod.version)

            return 0
        try:
            myeups.remove(product, version, self.opts.recursive,
                          checkRecursive=not self.opts.noCheck,
                          interactive=self.opts.interactive)
        except eups.EupsException as e:
            e.status = 1
            raise

        return 0


class AdminCmd(EupsCmd):

    usage = "%prog admin [buildCache|clearCache|listCache|clearLocks|listLocks|clearServerCache|info|show] [-h|--help] [-r root]"

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

        self.clo.disable_interspersed_args() # associate opts with subcommands

    def run(self):
        if len(self.args) > 0:
            return self.execute()
        return EupsCmd.run(self)

    def execute(self):
        if len(self.args) < 1:
            self.err("Please specify an admin subcommand")
            print(self.clo.get_usage(), file=self._errstrm)
            return 2
        subcmd = self.args[0]

        ecmd = makeEupsCmd("%s %s" % (self.cmd, subcmd), self)
        if not ecmd:
            self.err("Unrecognized admin subcommand: %s" % subcmd)
            return 10

        lock.takeLocks(ecmd.cmd, eups.Eups.setEupsPath(ecmd.opts.path, ecmd.opts.dbz),
                       ecmd.lockType, nolocks=ecmd.opts.nolocks, verbose=ecmd.opts.verbose - ecmd.opts.quiet)

        return ecmd.run()

        return 0

class AdminBuildCacheCmd(EupsCmd):

    usage = "%prog admin buildCache [-h|--help] [options]"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Rebuild the cache"""

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-A", "--admin-mode", dest="asAdmin", action="store_true", default=False,
                            help="apply cache operations to caches under EUPS_PATH")

    def execute(self):
        self.args.pop(0)                # remove the "admin"

        if len(self.args) > 0:
            self.err("Unexpected arguments: %s" % " ".join(self.args))
            return 1

        eups.clearCache(inUserDir=not self.opts.asAdmin, verbose=self.opts.verbose)
        eups.Eups(readCache=True, asAdmin=self.opts.asAdmin)

        return 0

class AdminClearCacheCmd(EupsCmd):

    usage = "%prog admin clearCache [-h|--help] [options]"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Clear all cache files"""

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-A", "--admin-mode", dest="asAdmin", action="store_true", default=False,
                            help="apply cache operations to caches under EUPS_PATH")


    def execute(self):
        self.args.pop(0)                # remove the "admin"

        if len(self.args) > 0:
            self.err("Unexpected arguments: %s" % " ".join(self.args))
            return 1

        eups.clearCache(inUserDir=not self.opts.asAdmin, verbose=self.opts.verbose)

        return 0

class AdminClearLocksCmd(EupsCmd):

    usage = "%prog admin clearLocks [-h|--help] [options]"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Clear all locks held by eups
"""
    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

    def execute(self):
        self.args.pop(0)                # remove the "admin"

        if len(self.args) > 0:
            self.err("Unexpected arguments: %s" % " ".join(self.args))
            return 2

        path = self.createEups(self.opts, readCache=False).path
        for d in path:
            if lock.getLockPath(d) is None:
                print("Locks are disabled for %s" % (d), file=utils.stdinfo)

        try:
            lock.clearLocks(path, self.opts.verbose, self.opts.noaction)
        except IOError:
            pass

        return 0

class AdminListLocksCmd(EupsCmd):

    usage = "%prog admin listLocks [-h|--help] [options]"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""List all locks held by eups
"""
    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

    def execute(self):
        self.args.pop(0)                # remove the "admin"

        if len(self.args) > 0:
            self.err("Unexpected arguments: %s" % " ".join(self.args))
            return 2

        path = self.createEups(self.opts, readCache=False).path
        for d in path:
            if lock.getLockPath(d) is None:
                print("Locks are disabled for %s" % (d), file=utils.stdinfo)

        try:
            lock.listLocks(path, self.opts.verbose, self.opts.noaction)
        except IOError:
            pass

        return 0

class AdminClearServerCacheCmd(EupsCmd):

    usage = "%prog admin clearServerCache [-h|--help] [options]"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Clear all distrib server cache files"""

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-r", "--root", "--server-dir", dest="root", action="store",
                            help="Location of manifests/buildfiles/tarballs " +
                            "(may be a URL or scp specification).  Default: find in $EUPS_PKGROOT")

    def execute(self):
        self.args.pop(0)                # remove the "admin"

        if len(self.args) > 0:
            self.err("Unexpected arguments: %s" % " ".join(self.args))
            return 1

        pkgroots = self.opts.root
        if pkgroots is None and "EUPS_PKGROOT" in os.environ:
            pkgroots = os.environ["EUPS_PKGROOT"]

        myeups = eups.Eups(readCache=False)
        # FIXME: this is not clearing caches in the user's .eups dir.
        ServerConf.clearConfigCache(myeups, pkgroots, self.opts.verbose)

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
        self.args.pop(0)                # remove the "admin"

        if len(self.args) == 0:
            self.err("Please specify a product name")
            return 2
        productName = self.args[0]

        versionName = None
        if len(self.args) > 1:
            versionName = self.args[1]

        try:
            myeups = self.createEups()
        except eups.EupsException as e:
            e.status = 9
            raise

        tag = myeups.tags.getTag(self.opts.tag)

        if tag:
            if versionName:
                self.err("You may not specify a tag and an explicit version: %s --tag %s %s" %
                         (productName, tag, versionName))
                return 2

            prod = myeups.findTaggedProduct(productName, tag)
            if not prod:
                self.err("Unable to lookup %s --tag %s" % (productName, tag))
                return 2

        if not (versionName or tag):
            prod = myeups.findProduct(productName)
            if prod:
                versionName = prod.version
            else:
                self.err("Unable to find a default version of %s" % (productName))
                return 2

        if len(self.args) > 2:
            self.err("Unexpected trailing arguments: %s" % self.args[2])
            return 2

        for eupsDb in myeups.versions.keys():
            db = myeups._databaseFor(eupsDb)
            if tag:
                try:
                    vfile = db.getChainFile(tag, productName, searchUserDB=True)
                except eups.ProductNotFound:
                    vfile = None

                if vfile:
                    vfile = vfile.file
            else:
                vfile = db._findVersionFile(productName, versionName)

            if vfile:
                print(vfile)
                return 0

        if tag:
            fileType = "tag \"%s\"'s chain" % tag
        else:
            fileType = "version"

        msg = "Unable to find %s file for %s" % (fileType, productName)
        if versionName:
            msg += " %s" % (versionName)

        self.err(msg)
        return 1

class AdminShowCmd(EupsCmd):
    usage = "%prog admin show [-h|--help] [options] what"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Tell me about something
"""

    def addOptions(self):
        self.clo.enable_interspersed_args()

        # these options are used to configure the Eups instance
        self.addEupsOptions()

        # this will override the eups option version

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

    def execute(self):
        self.args.pop(0)                # remove the "show"

        if len(self.args) == 0:
            self.err("Please tell me what you're interested in")
            return 2
        what = self.args[0]

        if what == "python":
            print(sys.executable)
            return 0
        else:
            msg = "I don't know anything about \"%s\"" % (what)
            self.err(msg)
            return 1

class AdminListCacheCmd(EupsCmd):

    usage = "%prog admin listCache [-h|--help] [options]"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""List all cache files"""

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.addEupsOptions()           # e.g. --flavor
        
    def execute(self):
        self.args.pop(0)                # remove the "admin"

        if len(self.args) > 0:
            self.err("Unexpected arguments: %s" % " ".join(self.args))
            return 1

        eups.listCache(verbose=self.opts.verbose, flavor=self.opts.flavor)

        return 0

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class DistribCmd(EupsCmd):

    usage = "%prog distrib [clean|create|declare|install|list|path] [-h|--help] [options] ..."

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = True

    description = \
"""Interact with package distribution servers either as a user installing
packages or as a provider maintaining a server.

An end-user uses the following sub-commands to install packages:
   list      list the available packages from distribution servers
   path      list the distribution servers
   install   download and install a package
   clean     clean up any leftover build files from an install (that failed)
To use these, the user needs write-access to a product stack and database.

A server provider uses:
   create    create a distribution package from an installed product
   declare   declare global tags
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
            print(self.clo.get_usage(), file=self._errstrm)
            return 2
        subcmd = self.args[0]

        cmd = "%s %s" % (self.cmd, subcmd)

        ecmd = makeEupsCmd(cmd, self)
        if ecmd is None:
            self.err("Unrecognized distrib subcommand: %s" % subcmd)
            return 10

        lock.takeLocks(ecmd.cmd, eups.Eups.setEupsPath(ecmd.opts.path, ecmd.opts.dbz),
                       ecmd.lockType, nolocks=ecmd.opts.nolocks, verbose=ecmd.opts.verbose - ecmd.opts.quiet)

        return ecmd.run()

class DistribDeclareCmd(EupsCmd):

    usage = "%prog distrib declare [-h|--help] [options] [product [version] [tagname]]"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Declare a tag for an available package from the package distribution repositories.

If no product or version is provided, all defined tags are defined.
"""

    def addOptions(self):
        self.clo.enable_interspersed_args()

        self.clo.add_option("-f", "--flavor", dest="useFlavor", action="store", default=None,
                            help="Create tag for this flavor")
        self.clo.add_option("-s", "--server-dir", dest="serverDir", action="store", metavar="DIR",
                            help="the directory tree to save created packages under")
        self.clo.add_option("-t", "--tag", dest="tag", action="store",
                            help="Declare product to have this tag")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

    def execute(self):
        # get rid of sub-command arg
        self.args.pop(0)

        productName = versionName = None
        tagName = None                  # the tag we're declaring
        if self.args:
            productName = self.args.pop(0)
        if self.args:
            versionName = self.args.pop(0)
        if self.args:
            tagName = self.args.pop(0)

        myeups = eups.Eups(readCache=False)

        if productName and not versionName:
            if self.opts.tag:
                prod = myeups.findTaggedProduct(productName, self.opts.tag)

                if prod:
                    versionName = prod.version

        if not tagName:
            tagName = self.opts.tag

        if not tagName:
            self.err("Please specify a tag to use after the version or via -t")
            return 2

        if productName:
            if not versionName:
                self.err("Please specify a product version")
                return 2
            products = [(productName, versionName),]
        else:
            myeups = self.createEups(self.opts)
            products = [(p.name, p.version) for p in myeups.findProducts(None, None, [tagName])]

        pkgroot = self.opts.serverDir
        if not pkgroot:
            self.err("Please use --server-dir to specify where you want to declare this tag")
            return 2

        server = distrib.Repository(myeups, pkgroot)
        clsname = server.distServer.getConfigProperty('DISTRIB_CLASS', 'eups.distrib.Distrib.DefaultDistrib').split(':')[-1]
        distribClass = importClass(clsname)
        dist = distribClass(myeups, server.distServer, verbosity=self.opts.verbose)

        pl = dist.getTaggedRelease(pkgroot, tagName)
        if not pl:
            pl = distrib.server.TaggedProductList(tagName)
        #
        # Due to the structure of the TaggedProductList class it cannot store tags for
        # objects with multiple flavors for a given product
        #
        # Because we want a tag to always mean the same thing, we'll simply disallow
        # anything but "generic".  The code that reads the TaggedProductList handles
        # this by replacing "generic" by the current flavor.  This is a bit of a
        # hack (it'd be better to rewrite TaggedProductList), but it's OK for now
        #
        if self.opts.useFlavor:
            print("Ignoring --flavor in \"eups distrib declare\"", file=utils.stdwarn)
            self.opts.useFlavor = None

        for productName, versionName in products:
            pl.addProduct(productName, versionName, flavor=self.opts.useFlavor)
            dist.writeTaggedRelease(pkgroot, tagName, pl, self.opts.useFlavor, True)

        return 0


class DistribListCmd(EupsCmd):

    usage = "%prog distrib list [-h|--help] [options] [product [version]]"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""List available packages from the package distribution repositories.

N.b. The flavors available may be imprecise unless you specify --precise
(or --verbose);  in this case the command will run significantly more
slowly as each product's availability will be checked.
"""

    def addOptions(self):
        self.clo.enable_interspersed_args()

        self.clo.add_option("-f", "--flavor", dest="flavor", action="store", default=None,
                            help="Specifically list for this flavor")
        self.clo.add_option("-p", "--precise", dest="precise", action="store_true",
                            help="Check that the flavor information is correct (slows things down)")
        self.clo.add_option("-r", "--repository", "-s", "--server-dir",
                            dest="root", action="append", metavar="PKGURL",
                            help="Servers to query (Default: $EUPS_PKGROOT)")
        self.clo.add_option("-S", "--server-option", dest="serverOpts", action="append",
                            help="pass a customized option to all repositories " +
                            "(form NAME=VALUE, repeat as needed)")
        self.clo.add_option("-t", "--tag", dest="tag", action="store",
                            help="List only versions having this tag name")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("--root", dest="root", action="append",
                            help="equivalent to --server-dir (deprecated)")

    def execute(self):
        myeups = eups.Eups(readCache=False)
        if self.opts.tag:
            # Note: tag may not yet be registered locally, yet; though it may be
            # defined on a server
            from eups.tags import Tag
            tag = Tag.parse(self.opts.tag)
            if not myeups.tags.isRecognized(self.opts.tag) and tag.isGlobal():
                # register it in case we find it on a server
                myeups.tags.registerTag(tag)

        # get rid of sub-command arg
        self.args.pop(0)

        product = version = None
        if len(self.args) > 0:
            product = self.args[0]
        if len(self.args) > 1:
            version = self.args[1]

        if self.opts.root:
            pkgroots = "|".join(self.opts.root)
        else:
            pkgroots = os.environ.get("EUPS_PKGROOT")

        if not pkgroots:
            self.err("Please specify a repository with --server-dir or $EUPS_PKGROOT")
            return 2

        options = None
        if self.opts.serverOpts:
            options = {}
            for opt in self.opts.serverOpts:
                try:
                    name, val = opt.split("=",1)
                except ValueError:
                    self.err("server option not of form NAME=VALUE: "+opt)
                    return 3
                options[name] = val

        try:
            repos = distrib.Repositories(pkgroots, options, myeups, verbosity=self.opts.verbose)

            data = repos.listPackages(product, version, self.opts.flavor,
                                      tag=myeups.tags.getTag(self.opts.tag))
        except eups.EupsException as e:
            e.status = 1
            raise

        if len(data) == 1 and len(data[0][1]) == 1:
            indent = ""
        else:
            indent = "  "

        primary = "primary"
        for pkgroot, pkgs in data:
            if len(pkgs) > 0:
                if len(data) > 1:
                    print("Available products from %s server: %s" % \
                        (primary, pkgroot))
                for (name, ver, flav) in pkgs:
                    if self.opts.precise or self.opts.verbose:
                        try:
                            man = repos.repos[pkgroot].getManifest(name, ver, flav)
                        except RuntimeError: # unavailable with that flavor
                            continue

                    print("%s%-20s %-10s %s" % (indent, name, flav, ver))
                    if self.opts.verbose:
                        for dep in man.getProducts():
                            print("%s  %-18s %-10s %s" % (indent, dep.product, dep.version, dep.flavor))
            else:
                print("No matching products available from %s server (%s)" % (primary, pkgroot))

            primary = "secondary"

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

        self.clo.add_option("-d", "--declareAs", dest="alsoTag", action="append", metavar="TAG",
                            help="tag all newly installed products with this user TAG (repeat as needed)")
        self.clo.add_option("-g", "--groupAccess", dest="groupperm", action="store", metavar="GROUP",
                            help="Give specified group r/w access to all newly installed packages")
        self.clo.add_option("-I", "--install-into", dest="installStack", metavar="DIR",
                            help="install into this product stack " +
                            "(Default: the first writable stack in $EUPS_PATH)")
        self.clo.add_option("-m", "--manifest", dest="manifest", action="store",
                            help="Use this manifest file for the requested product")
        self.clo.add_option("-U", "--no-server-tags", dest="updateTags", action="store_false", default=True,
                            help="Prevent automatic assignment of server/global tags")
        self.clo.add_option("--noclean", dest="noclean", action="store_true", default=False,
                            help="Don't clean up after successfully building the product")
        self.clo.add_option("-j", "--nodepend", dest="depends", action="store_const",
                            const=distrib.Repositories.DEPS_NONE,
                            help="Just install product, but not its dependencies")
        self.clo.add_option("-o", "--onlydepend", dest="depends", action="store_const",
                            const=distrib.Repositories.DEPS_ONLY,
                            help="Just install product dependencies, not the product itself")
        self.clo.set_defaults(depends=distrib.Repositories.DEPS_ALL)
        self.clo.add_option("-N", "--noeups", dest="noeups", action="store_true", default=False,
                            help="Don't attempt to lookup product in eups (always install)")
        self.clo.add_option("-r", "--repository", "--server-dir",
                            dest="root", action="append", metavar="BASEURL",
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
        self.clo.add_option("-C", "--current-all", dest="installCurrent", action="store_true", default=False,
                            help="Include current among the server tags that are installed")
        self.clo.add_option("-c", "--current", dest="current", action="store_true", default=False,
                            help="Make top level product current (equivalent to --tag current)")

    def execute(self):
        try:
            _opts = copy.deepcopy(self.opts)
            _opts.tag = None
            myeups = self.createEups(_opts)
        except eups.EupsException as e:
            e.status = 9
            raise

        # get rid of sub-command arg
        self.args.pop(0)

        if len(self.args) < 1:
           self.err("please specify at least a product name")
           print(self.clo.get_usage(), file=self._errstrm)
           return 5

        productName = self.args[0]
        if len(self.args) > 1:
            versionName = self.args[1]
        else:
            versionName = None

        if self.opts.installStack:
            if not utils.isDbWritable(self.opts.installStack) and \
               not utils.isDbWritable(os.path.join(self.opts.installStack, eups.Eups.ups_db)):
                self.err("Requested install stack not writable: " +
                         self.opts.installStack)
                return 2

            # place install root at front of the path given to Eups
            if self.opts.path is None:
                if "EUPS_PATH" in os.environ:
                    self.opts.path = os.environ["EUPS_PATH"]
            if self.opts.path is None:
                self.opts.path = self.opts.installStack
            else:
                self.opts.path = "%s:%s" % (self.opts.installStack, self.opts.path)

        if self.opts.current:
            if self.opts.tag:
                # self.opts.tag += " current"  # list is not supported
                self.err("--tag is set; ignoring --current")
            else:
                self.opts.tag = "current"

        if self.opts.tag:
            # Note: tag may not yet be registered locally, yet; though it may be
            # defined on a server
            from eups.tags import Tag
            tag = Tag.parse(self.opts.tag)
            if not myeups.tags.isRecognized(self.opts.tag) and tag.isGlobal():
                # register it in case we find it on a server
                myeups.tags.registerTag(tag)
            try:
                prefs = myeups.getPreferredTags()
                myeups.setPreferredTags([self.opts.tag] + prefs)
            except eups.TagNotRecognized as e:
                self.err(str(e))
                return 4
            if not versionName:  versionName = tag

        if self.opts.alsoTag:
            unrecognized = []
            nonuser = []
            for tag in self.opts.alsoTag:
                try:
                    tag = myeups.tags.getTag(tag)
                    if not tag.isUser():
                        nonuser.append(tag.name)
                except eups.TagNotRecognized as e:
                    unrecognized.append(tag)

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
        dopts['noeups']   = self.opts.noeups
        dopts['noaction'] = self.opts.noaction
        dopts['nobuild']  = self.opts.nobuild
        dopts['noclean']  = self.opts.noclean
        dopts["installCurrent"] = self.opts.installCurrent
        dopts['flavor']   = myeups.flavor

        if self.opts.serverOpts:
            for opt in self.opts.serverOpts:
                try:
                    name, value = opt.split("=",1)
                except ValueError:
                    self.err("server option not of form NAME=VALUE: "+opt)
                    return 3
                dopts[name] = value

        if self.opts.root:
            self.opts.root = "|".join(self.opts.root)
        else:
            if "EUPS_PKGROOT" not in os.environ:
                self.err("No repositories specified; please set --server-dir or $EUPS_PKGROOT")
                return 3
            self.opts.root = os.environ["EUPS_PKGROOT"]

        if not self.opts.root:
            self.err("No repositories specified; please set --server-dir or $EUPS_PKGROOT and try again")
            return 3

        log = None
        if self.opts.quiet:
            log = open("/dev/null", "w")

        updateTags = None if self.opts.updateTags else self.opts.tag
        try:
            repos = distrib.Repositories(self.opts.root, dopts, myeups,
                                         self.opts.flavor,
                                         verbosity=self.opts.verbose, log=log)
            repos.install(productName, versionName, updateTags,
                          self.opts.alsoTag, self.opts.depends,
                          self.opts.noclean, self.opts.noeups, dopts,
                          self.opts.manifest, self.opts.searchDep)
        except eups.EupsException as e:
            e.status = 1
            if log:
                log.close()
            raise

        if self.opts.tag:               # just the top-level product
            try:
                myeups.assignTag(self.opts.tag, productName, versionName)
            except eups.ProductNotFound:
                # this may have been a "pseudo"-package, one that just
                # ensures the installation of other packages.
                # It may alternatively have been that the version of the
                # installed package was requested via a server tag name;
                # in this case, tag has already been assigned
                #
                # self.err("Note: product %s %s itself was not installed; ignoring --tag request" %
                #          (ex.name, ex.version))
                pass

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
        self.clo.add_option("-r", "--repository", "--server-dir",
                            dest="root", action="append", metavar="BASEURL",
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
            if "EUPS_PKGROOT" not in os.environ:
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
                dopts[name] = val

        log = None
        if self.opts.quiet:
            log = open("/dev/null", "w")

        try:
            myeups = self.createEups()
        except eups.EupsException as e:
            e.status = 9
            raise

        try:
            repos = distrib.Repositories(self.opts.root, dopts, myeups,
                                         self.opts.flavor, allowEmptyPkgroot=True,
                                         verbosity=self.opts.verbose, log=log)
            repos.clean(product, version, self.opts.flavor, dopts,
                        self.opts.pdir, self.opts.remove)

        except eups.EupsException as e:
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
        self.clo.add_option("-r", "--repository", "--server-dir",
                            dest="repos", action="append", metavar="BASEURL",
                            help="the base URL for other repositories to consult (repeat as needed).  " +
                            "Default: $EUPS_PKGROOT")
        self.clo.add_option("-s", "--server-dir", dest="serverDir", action="store", metavar="DIR",
                            help="the directory tree to save created packages under")

        # these options are used to configure the Eups instance
        self.addEupsOptions()

        # this will override the eups option version
        self.clo.add_option("-D", "--distrib-class", dest="distribClasses", action="append",
                            help="register this Distrib class (repeat as needed)")
        self.clo.add_option("-R", "--rebuild", dest="rebuildProductVersion", default=[], action="append",
                            help="Create a new distribution given that product:version's ABI has changed")
        self.clo.add_option("-S", "--server-class", dest="serverClasses", action="append",
                            help="register this DistribServer class (repeat as needed)")
        self.clo.add_option("-S", "--server-option", dest="serverOpts", action="append",
                            help="pass a customized option to all repositories " +
                            "(form NAME=VALUE, repeat as needed)")
        self.clo.add_option("-e", "--exact", dest="exact_version", action="store_true", default=False,
                            help="Follow the as-installed versions, not the dependencies in the table file")
        self.clo.add_option("-f", "--use-flavor", dest="useFlavor", action="store", default=None,
                            help="Create an installation specialised to the specified flavor")
        self.clo.add_option("-t", "--tag", dest="tag", action="append",
                            help="Set the VRO based on this tag name")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-C", "--current", dest="current", action="store_true", default=False,
                            help="deprecated (ignored)")

    def incrBuildVersion(self, myeups, productName, inVersion):
        """Given a version of a product, use the registered function to increment the build version"""
        outVersion = inVersion
        oldVersions = list()
        while myeups.findProduct(productName, outVersion) is not None:
            oldVersions.append(outVersion)
            try:
                outVersion = hooks.config.Eups.versionIncrementer(productName, outVersion)
            except Exception as e:
                raise RuntimeError("Unable to call hooks.Eups.config.versionIncrementer for %s %s (%s)" %
                                   (productName, outVersion, e))
            if outVersion in oldVersions:
                raise RuntimeError("hooks.Eups.config.versionIncrementer for %s %s didn't increment: %s" %
                                   (productName, inVersion, oldVersions))

        if self.opts.verbose:
            print("Incremented build version name for %s: %s --> %s" % (productName, inVersion, outVersion))

        return outVersion


    def execute(self):
        # get rid of sub-command arg
        self.args.pop(0)

        try:
            myeups = self.createEups()
        except eups.EupsException as e:
            e.status = 9
            raise

        if self.opts.current:
            self.err("Flag -C/--current is no longer supported.  Please use \"eups distrib declare\"")
            return 2

        if len(self.args) == 0:
            self.err("Please specify a product name and version")
            return 2
        productName = self.args[0]

        if len(self.args) < 2:
            version = None
        else:
            version = self.args[1]

        if not self.opts.repos:
            if "EUPS_PKGROOT" in os.environ:
                self.opts.repos = os.environ["EUPS_PKGROOT"].split("|")
            else:
                self.opts.repos = []

        if not self.opts.useFlavor:
            self.opts.useFlavor = self.opts.flavor

        if not self.opts.setupType:
            self.opts.setupType = "build"

        if self.opts.serverDir:
            self.opts.serverDir = os.path.expandvars(os.path.expanduser(self.opts.serverDir))

        if not self.opts.serverDir:
            for pkgroot in self.opts.repos:
                if utils.isDbWritable(pkgroot):
                    self.opts.serverDir = pkgroot
                    break
        elif not os.path.exists(self.opts.serverDir):
            self.err("Server directory %s does not exist; creating " % self.opts.serverDir)
            os.makedirs(self.opts.serverDir)
        elif not utils.isDbWritable(self.opts.serverDir):
            self.err("Server directory %s is not writable: " % self.opts.serverDir)
            return 3
        if not self.opts.serverDir:
            self.err("No writeable package server found; use --server-dir")
            return 3

        myeups.selectVRO(self.opts.tag, None, None, self.opts.dbz)

        if not version:
            if self.opts.tag:
                prod = myeups.findTaggedProduct(productName, self.opts.tag[0])

                if prod:
                    version = prod.version
                else:
                    self.err("Failed to find product %s with tag %s" % (productName, self.opts.tag[0]))
                    return 2

        if not version:
            self.err("Please specify a product version")
            return 2

        dopts = {}
        # handle extra options
        dopts = { 'config': {} }
        dopts['noaction']   = self.opts.noaction
        dopts["allowIncomplete"] = self.opts.allowIncomplete
        dopts["exact"] = self.opts.exact_version
        if self.opts.serverOpts:
            for opt in self.opts.serverOpts:
                try:
                    name, val = opt.split("=",1)
                except ValueError:
                    self.err("server option not of form NAME=VALUE: %s" % (opt))
                    return 3
                dopts[name] = val

        if not self.opts.distribTypeName:
            self.err("Please specify a distribution type name (e.g. -d tarball, etc)")
            return 4


        def isDependent(product, searchList):
            """Return whether a product is dependent upon one of the packages named in the searchList"""
            dependencies = [q[0].name for q in myeups.getDependentProducts(product)]
            for name in searchList:
                if name in dependencies:
                    return True
            return False

        #
        # If they specified --rebuild, they want us to figure out what needs to be rebuilt
        # after an ABI change, and then generate "letter versions" for those new products (e.g. afw 2.3.0a)
        #
        if len(self.opts.rebuildProductVersion) > 0:
            # Parse list of products to rebuild
            rebuildProducts = {}
            for rebuildProductVersion in self.opts.rebuildProductVersion:
                try:
                    rebuildName, rebuildVersion = re.split(r"[:,]|\s+", rebuildProductVersion, maxsplit=1)
                except ValueError as e:
                    raise RuntimeError("Please specify product:version, not \"%s\"" % rebuildProductVersion)

                if rebuildName in rebuildProducts:
                    if rebuildVersion == rebuildProducts[rebuildName]:
                        continue
                    raise RuntimeError("Product %s already specified for rebuild, version mismatch: %s vs %s" %
                                       (rebuildName, rebuildVersion, rebuildProducts[rebuildName]))

                rebuildProducts[rebuildName] = rebuildVersion

            # Check to see if the specified versions should also be rebuilt
            # (one of the other products is in its dependency tree)
            rebuildProductSet = set(rebuildProducts.keys())
            for rebuildName, rebuildVersion in rebuildProducts.items():
                rebuildProduct = myeups.findProduct(rebuildName, rebuildVersion)
                if not rebuildProduct:
                    raise RuntimeError("I can't find product %s %s" % (rebuildName, rebuildVersion))

                rebuildProductDeps = myeups.getDependentProducts(rebuildProduct)
                for p in rebuildProductDeps:
                    if p[0].name in rebuildProductSet and p[0].version != rebuildProducts[p[0].name]:
                        rebuildProducts[rebuildName] = self.incrBuildVersion(myeups, rebuildName,
                                                                             rebuildVersion)

            #
            # We need a new letter version for the top-level product even if it needn't be rebuilt,
            # as it records the versions of sub-products that we _do_ need
            #
            topProduct = myeups.findProduct(productName, version)
            if not topProduct:
                raise RuntimeError("I can't find product %s %s" % (productName, version))

            mapping = Mapping()
            mapping.add(inProduct=productName, inVersion=version,
                        outVersion=self.incrBuildVersion(myeups, productName, version))

            foundRebuilds = set()
            for p, optional, recursionDepth in myeups.getDependentProducts(topProduct, topological=True):
                if p.name in rebuildProducts:
                    mapping.add(inProduct=p.name, inVersion=p.version, outVersion=rebuildProducts[p.name])
                    foundRebuilds.add(p.name)
                    continue

                if not isDependent(p, rebuildProducts.keys()):
                    continue

                # If the product has a config file that claims that it has no binary components (and thus
                # needn't worry about ABI changes) we needn't bump its letter version
                doRebuild = True
                try:
                    doRebuild = not p.getConfig("distrib", "binary", getType=bool)
                except:
                    pass
                if doRebuild:
                    if self.opts.verbose:
                        print("Creating rebuild version %s %s" % (p.name, mapping.apply(p.name, p.version)[1]))
                    mapping.add(inProduct=p.name, inVersion=p.version,
                                outVersion=self.incrBuildVersion(myeups, p.name, p.version))

                if len(foundRebuilds) == len(rebuildProducts):
                    # Not going to find any more products to rebuild
                    break

            if len(foundRebuilds) != len(rebuildProducts):
                raise RuntimeError("Unable to find rebuild products %s as dependencies of %s:%s" %
                                   (set(rebuildProducts.keys()).difference(foundRebuilds),
                                    productName, version))

            dopts["rebuildMapping"] = mapping

            if not self.opts.quiet:
                print("Creating distribution for %s %s (not %s)" % (productName,
                                                                    mapping.apply(productName, version)[1],
                                                                    version))
                print("Don't forget to install this distribution to pick up the rebuild versions!")

        if myeups.noaction:
            print("Skipping repository and server creation.")
        else:
            log = None
            if self.opts.quiet:
                log = open("/dev/null", "w")

            try:
                repos = None
                if not self.opts.force:
                    repos = distrib.Repositories(self.opts.repos, dopts, myeups,
                                                 self.opts.flavor, allowEmptyPkgroot=True,
                                                 verbosity=self.opts.verbose,
                                                 log=log)
                server = distrib.Repository(myeups, self.opts.serverDir,
                                            self.opts.useFlavor, options=dopts,
                                            verbosity=self.opts.verbose, log=log)
                server.create(self.opts.distribTypeName, productName,
                              version, nodepend=self.opts.nodepend, options=dopts,
                              manifest=self.opts.manifest,
                              packageId=self.opts.packageId, repositories=repos)

            except eups.EupsException as e:
                e.status = 1
                raise

        return 0

class DistribPathCmd(EnvListCmd):

    usage = "%prog distrib path [-h|--help] [n]"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print the base URLs for the repositories given via EUPS_PKGROOT.  An optional
integer argument, n, will cause just the n-th URL to be listed (where
0 is the first element).
"""

    def __init__(self, **kwargs):
        EnvListCmd.__init__(self, **kwargs)

        # get rid of sub-command arg
        self.args.pop(0)

        self._init("EUPS_PKGROOT", "|")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
class DistribTagsCmd(EupsCmd):

    usage = "%prog distrib tags [-h|--help] [options] [tagname]"

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""List available tags from the package distribution repositories.

The tagname may be a glob pattern.
"""

    def addOptions(self):
        self.clo.enable_interspersed_args()

        self.clo.add_option("-f", "--flavor", dest="flavor", action="store", default=None,
                            help="Specifically list for this flavor")
        self.clo.add_option("-r", "--repository", "-s", "--server-dir",
                            dest="root", action="append", metavar="PKGURL",
                            help="Servers to query (Default: $EUPS_PKGROOT)")

        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("--root", dest="root", action="append",
                            help="equivalent to --server-dir (deprecated)")

    def execute(self):
        myeups = eups.Eups(readCache=False)

        # get rid of sub-command arg
        self.args.pop(0)

        if len(self.args):
            import fnmatch
            globPattern = self.args.pop(0)
        else:
            globPattern = None

        if self.opts.root:
            pkgroots = "|".join(self.opts.root)
        else:
            pkgroots = os.environ.get("EUPS_PKGROOT")

        if not pkgroots:
            self.err("Please specify a repository with --server-dir or $EUPS_PKGROOT")
            return 2

        options = None
        repos = distrib.Repositories(pkgroots, options, myeups, verbosity=self.opts.verbose)

        tags = {}
        for pkgroot in repos.pkgroots:
            tags[pkgroot] = []

            for tag in repos.repos[pkgroot].distServer.getTagNames(flavor=None, noaction=False):
                if not globPattern or fnmatch.fnmatch(tag, globPattern):
                    tags[pkgroot].append(tag)

        if len(repos.pkgroots) == 1 and len(list(tags.values())[0]) == 1:
            indent = ""
        else:
            indent = "  "

        primary = "primary"
        for pkgroot in repos.pkgroots:
            if len(tags[pkgroot]) > 0:
                print("Available tags from %s server: %s" % (primary, pkgroot))
                for name in tags[pkgroot]:
                    print("%s%-20s" % (indent, name))
            else:
                print("No matching tags available from %s server (%s)" % (primary, pkgroot))

            primary = "secondary"

        return 0

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

        
class TagsCmd(EupsCmd):

    usage = """%prog tags [-h|--help] [options] [tagname] [product]

    When listing tags, tagname and product may be glob patterns
    """

    # set this to True if the description is preformatted.  If false, it
    # will be automatically reformatted to fit the screen
    noDescriptionFormatting = False

    description = \
"""Print information about known tags, or clone or delete a tag
"""

    def addOptions(self):
        # always call the super-version so that the core options are set
        EupsCmd.addOptions(self)

        self.clo.add_option("-F", "--force", dest="force", action="store_true", default=False,
                            help="Force requested behaviour")
        self.clo.add_option("--clone", action="store", default=None,
                            help="Specify a tag to clone (must also specify new tag). May specify a product")
        self.clo.add_option("--delete", action="store", default=None,
                            help="Specify a tag to delete")

    def execute(self):
        myeups = self.createEups(self.opts)

        if self.opts.clone:
            oldTag = self.opts.clone
            if not len(self.args):
                self.err("You must specify a tag to set: eups tags --clone OLD NEW")
                return 1

            newTag = self.args.pop(0)
            productList = self.args     # may be []

            failedToTag = tags.cloneTag(myeups, newTag, oldTag, productList)

            if failedToTag:
                print("Failed to clone tag %s for %s" % (oldTag, ", ".join(failedToTag)), file=utils.stdwarn)
            return 0
        elif self.opts.delete:
            if self.args:
                if len(self.args) == 1:
                    _s = ""
                else:
                    _s = "s"

                self.err("Unexpected argument%s: %s" % (_s, ", ".join(self.args)))
                return 1

            tags.deleteTag(myeups, self.opts.delete)
            return 0
        else:
            pass                        # just list the tags

        nargs = len(self.args)
        if nargs == 0:
            globPattern = None
        else:
            globPattern = self.args.pop(0)
            nargs -= 1

        if nargs == 0:
            productName = None
        else:
            productName = self.args.pop(0)
            nargs -= 1

        if nargs:
            if nargs == 1:
                _s = ""
            else:
                _s = "s"

            self.err("Unexpected argument%s: %s" % (_s, ", ".join(self.args)))
            return 1

        tagNames = myeups.tags.getTagNames(omitPseudo=True)
        if globPattern:
            import fnmatch

            tagNames = [n for n in tagNames if fnmatch.fnmatch(n, globPattern)]

        if productName:
            matchedTagNames = []
            for t in tagNames:
                if self.createEups(self.opts).findProducts(productName, tags=[t]):
                    matchedTagNames.append(t)
            tagNames = matchedTagNames

        try:
            isatty = os.isatty(sys.stdout.fileno())
        except:
            isatty = False

        if isatty:
            sep = " "
        else:
            sep = "\n"
        print(sep.join(tagNames))

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

        self.clo.add_option("-c", "--current", dest="current", action="store_true", default=False,
                            help="same as --postTag=current")
        self.clo.add_option("-e", "--exact", dest="exact_version", action="store_true", default=False,
                            help="Consider the as-installed versions, not the dependencies in the table file ")
        self.clo.add_option("-F", "--force", dest="force", action="store_true", default=False,
                            help="Force requested behaviour")
        self.clo.add_option("-r", "--root", dest="productDir", action="store",
                            help="root directory where product is installed")
        self.clo.add_option("-T", "--postTag", dest="postTag", action="append",
                            help="Put TAG after version(Expr)? in VRO (may be repeated; precedence is left-to-right)")
        self.clo.add_option("-t", "--tag", dest="tag", action="append",
                            help="Set the VRO based on this tag name")
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

        if self.opts.current:
            if not self.opts.postTag:
                self.opts.postTag = []
            self.opts.postTag += ['current']

        if True:
            myeups = self.createEups(self.opts)
        else:
            if self.opts.setupType:
                setupType = self.opts.setupType.split()
            else:
                setupType = []

            myeups = eups.Eups(readCache=True, force=self.opts.force, setupType=setupType,
                               exact_version=self.opts.exact_version)

        myeups._processDefaultTags(self.opts)

        isUserTag = False
        if self.opts.tag:
            for t in self.opts.tag:
                if myeups.isUserTag(t):
                    isUserTag = True
                    break
        if isUserTag:
            myeups.includeUserDataDirInPath()

        myeups.selectVRO(self.opts.tag, self.opts.productDir, versionName, self.opts.dbz,
                         postTag=self.opts.postTag)

        print(" ".join(myeups.getVRO()))

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
def register(cmd, clname, lockType=lock.LOCK_EX):
    if _noCmdOverride and cmd in _cmdLookup:
        raise RuntimeError("Attempt to over-ride command: %s" % cmd)
    _cmdLookup[cmd] = (clname, lockType)

def makeEupsCmd(cmdName, cmd):
    args, toolname = cmd.clargs, cmd.prog
    cmdFunc, lockType = _cmdLookup.get(cmdName, (None, None))

    if not cmdFunc:
        return None

    ecmd = cmdFunc(args=args, toolname=toolname, cmd=cmdName, lockType=lockType)
    #
    # Merge options set in cmd into ecmd
    #
    baseCmd = EupsCmd(); baseCmd.addOptions()
    baseOptDefaults = baseCmd.clo.values # default options

    for k, v in vars(cmd).items():
        try:
            dv = getattr(baseOptDefaults, k) # get the default value
        except AttributeError:
            continue

        if getattr(cmd, k) == dv:       # not set in cmd
            continue

        if hasattr(ecmd, k):            # ecmd has the attribute
            ev = getattr(ecmd, k)

            if ev is None:
                setattr(ecmd, k, v)
            elif isinstance(ev, int):
                setattr(ecmd, k, ev + v)

    return ecmd

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
register("flavor",       FlavorCmd, lockType=None)
register("path",         PathCmd, lockType=None)
register("startup",      StartupCmd, lockType=None)
register("pkgroot",      PkgrootCmd, lockType=None)
register("flags",        FlagsCmd, lockType=None)
register("list",         ListCmd, lockType=lock.LOCK_SH)
register("pkg-config",   PkgconfigCmd, lockType=lock.LOCK_SH)
register("uses",         UsesCmd, lockType=lock.LOCK_SH)
register("expandbuild",  ExpandbuildCmd, lockType=lock.LOCK_SH)
register("expandtable",  ExpandtableCmd, lockType=lock.LOCK_SH)
register("declare",      DeclareCmd)
register("undeclare",    UndeclareCmd)
register("remove",       RemoveCmd)
register("admin",                  AdminCmd, lockType=None) # must be None, as subcommands take locks
register("admin buildCache",       AdminBuildCacheCmd)
register("admin clearCache",       AdminClearCacheCmd)
register("admin clearServerCache", AdminClearServerCacheCmd)
register("admin clearLocks",       AdminClearLocksCmd, lockType=None)
register("admin listLocks",        AdminListLocksCmd, lockType=None)
register("admin listCache",        AdminListCacheCmd, lockType=lock.LOCK_SH)
register("admin info",             AdminInfoCmd, lockType=lock.LOCK_SH)
register("admin show",             AdminShowCmd, lockType=None)
register("distrib",         DistribCmd, lockType=None) # must be None, as subcommands take locks
register("distrib clean",   DistribCleanCmd)
register("distrib create",  DistribCreateCmd)
register("distrib declare", DistribDeclareCmd)
register("distrib install", DistribInstallCmd)
register("distrib list",    DistribListCmd, lockType=lock.LOCK_SH)
register("distrib path",    DistribPathCmd)
register("distrib tags",    DistribTagsCmd)
register("tags",         TagsCmd, lockType=lock.LOCK_SH)
register("vro",          VroCmd, lockType=None)
register("help",         HelpCmd, lockType=None)

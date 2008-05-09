# -*- python -*-
import glob, re, os, pwd, sys
import cPickle
import pdb
import eupsLock
import eupsParser

def debug(*args, **kwargs):
    """Print args to stderr; useful while debugging as we source the stdout when setting up.
    Specify eol=False to suppress newline"""

    print >> sys.stderr, "Debug:", # make sure that this routine is only used for debugging
    
    for a in args:
        print >> sys.stderr, a,

    if kwargs.get("eol", True):
        print >> sys.stderr

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def _svnRevision(file=None, lastChanged=False):
    """Return file's Revision as a string; if file is None return
    a tuple (oldestRevision, youngestRevision, flags) as reported
    by svnversion; e.g. (4123, 4168, ("M", "S")) (oldestRevision
    and youngestRevision may be equal)
    """

    if file:
        info = getInfo(file)

        if lastChanged:
            return info["Last Changed Rev"]
        else:
            return info["Revision"]

    if lastChanged:
        raise RuntimeError, "lastChanged makes no sense if file is None"

    res = os.popen("svnversion . 2>&1").readline()

    if res == "exported\n":
        raise RuntimeError, "No svn revision information is available"

    mat = re.search(r"^(?P<oldest>\d+)(:(?P<youngest>\d+))?(?P<flags>[MS]*)", res)
    if mat:
        matches = mat.groupdict()
        if not matches["youngest"]:
            matches["youngest"] = matches["oldest"]
        return matches["oldest"], matches["youngest"], tuple(matches["flags"])

    raise RuntimeError, ("svnversion returned unexpected result \"%s\"" % res[:-1])

def version():
    """Set a version ID from an svn ID string (dollar HeadURL dollar)"""

    versionString = r"$HeadURL: svn+ssh://svn.lsstcorp.org/eups/trunk/neups.py $"

    version = "unknown"

    if re.search(r"^[$]HeadURL:\s+", versionString):
        # SVN.  Guess the tagname from the last part of the directory
        try:
            version = re.search(r"/([^/]+)$", os.path.split(versionString)[0]).group(1)

            if version == "trunk":
                version = "svn"
                try:                    # try to add the svn revision to the version
                    (oldest, youngest, flags) = _svnRevision()
                    version += youngest
                except IOError:
                    pass
        except RuntimeError:
            pass

    return version

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Current(object):
    """A class that represents a current.chain file"""

    def __init__(self, currentFile):
        """Parse a current file"""
        
        self.file = currentFile
        self.productName = None
        self.current = None
        self.info = {}

        self._read(currentFile)

    def _read(self, currentFile):
        fd = file(currentFile)

        flavor = None
        lineNo = 0                      # line number in input file, for diagnostics
        for line in fd.readlines():
            lineNo += 1
            line = re.sub(r"\n", "", line)

            if False:
                print line
                continue

            line = re.sub(r"^\s*", "", line)
            line = re.sub(r"#.*$", "", line)
        
            if not line:
                continue
            #
            # Get key = value
            #
            mat = re.search(r"^(\w+)\s*=\s*(.*)", line, re.IGNORECASE)
            if mat:
                key = mat.group(1).lower()
                value = re.sub(r"^\"|\"$", "", mat.group(2))
            else:
                raise RuntimeError, \
                      ("Unexpected line \"%s\" at %s:%d" % (line, self.file, lineNo))
            #
            # Check for information about product
            #
            if key == "file":
                if value.lower() != "version":
                    raise RuntimeError, \
                          ("Expected \"File = Version\"; saw \"%s\" at %s:%d" % (line, self.file, lineNo))
            elif key == "product":
                self.productName = value
            elif key == "chain":
                self.chain = value
            elif key == "flavor": # Now look for flavor-specific blocks
                flavor = value
                self.info[flavor] = {}
            else:
                value = re.sub(r"^\"(.*)\"$", r"\1", mat.group(2)) # strip ""

                if key == "qualifiers":
                    if False and value:
                        raise RuntimeError, ("Unsupported qualifiers \"%s\" at %s:%d" % (value, self.file, lineNo))
                    else:
                        continue
                else:
                    self.info[flavor][key] = value

    def __str__(self):
        s = ""
        s += "Product: %s  Chain: %s" % (self.productName, self.chain)

        flavors = self.info.keys(); flavors.sort()
        for flavor in flavors:
            s += "\n------------------"
            s += "\nFlavor: %s" % flavor
            keys = self.info[flavor].keys(); keys.sort()
            for key in keys:
                s += "\n%-20s : %s" % (key, self.info[flavor][key])

        return s
    
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-


class Action(object):
    """An action in a table file"""

    # Possible actions; the comments apply to the field that _read adds to an Action: (cmd, args, extra)
    addAlias = "addAlias"
    envAppend = "envAppend"             # not used
    envPrepend = "envPrepend"           # extra: bool append
    envRemove = "envRemove" 
    envSet = "envSet"
    envUnset = "envUnset" 
    prodDir = "prodDir"
    setupEnv = "setupEnv"
    setupOptional = "setupOptional"     # not used
    setupRequired = "setupRequired"     # extra: bool optional

    def __init__(self, cmd, args, extra):
        self.cmd = cmd
        self.args = args
        self.extra = extra

    def __str__(self):
        return "%s %s %s" % (self.cmd, self.args, self.extra)

    def execute(self, eups, nestedLevel, fwd=True):
        """Execute an action"""

        if self.cmd == Action.setupRequired:
            if nestedLevel == eups.max_depth + 1:
                return

            self.execute_setupRequired(eups, nestedLevel, fwd)
        elif self.cmd == Action.envPrepend:
            self.execute_envPrepend(eups, fwd)
        elif self.cmd == Action.envSet:
            self.execute_envSet(eups, fwd)
        elif self.cmd == Action.addAlias:
            self.execute_addAlias(eups, fwd)
        else:
            print >> sys.stderr, "Unimplemented action", self.cmd
    #
    # Here are the real execute routines
    #
    def execute_setupRequired(self, eups, nestedLevel, fwd=True):
        """Execute setupRequired"""

        optional = self.extra

        _args = self.args; args = []
        i = -1
        while i < len(_args) - 1:
            i += 1
            if _args[i] == "-f":    # a flavor specification -- ignore
                i += 1               # skip next argument (the flavor)
                continue
            args += [_args[i]]

        productName = args[0]
        if len(args) > 1:
            vers = " ".join(args[1:])
        else:
            vers = None

        productOK, vers = eups.setup(productName, vers, fwd, nestedLevel)
        if not productOK and not optional:
            raise RuntimeError, ("Failed to setup required product %s %s" % (productName, vers))

    def execute_envPrepend(self, eups, fwd=True):
        """Execute envPrepend"""

        args = self.args
        append = self.extra

        envVar = args[0]                # environment variable to set
        value = args[1]                 # add/subtract this value to the variable
        if len(args) > 2:
            delim = args[2]
        else:
            delim = ":"

        opath = eups.environ.get(envVar, "") # old value of envVar (generally a path of some sort, hence the name)

        prepend_delim = re.search(r"^%s" % delim, opath) # should we prepend an extra :?
        append_delim = re.search(r"%s$" % delim, opath) # should we append an extra :?

        opath = filter(lambda el: el, opath.split(delim)) # strip extra : at start or end

        if fwd:
            try:                            # look for values that are optional environment variables: $?{XXX}
                key = re.search(r"^$\?{([^}]*)}", value).group(0)
                if eups.environ.has_key(key):
                    value = eups.environ[key]
                else:
                  if eups.verbose > 0:
                      print >> sys.stderr, "$%s is not defined; not setting %s" % (key, value)
                      return
            except AttributeError:
                pass

            if not value:
                return

        if fwd:
            if append:
                npath = opath + [value]
            else:
                npath = [value] + opath
        else:
            npath = filter(lambda d: d != value, opath)

        npath = self.pathUnique(npath) # remove duplicates

        npath = delim.join(npath)     # convert back to a string
        
        if prepend_delim and not re.search(r"^%s" % delim, npath):
            npath = delim + npath
        if append_delim and not re.search(r"%s$" % delim, npath):
            npath += delim

        if eups.force and eups.oldEnviron[envVar]:
            del eups.oldEnviron[envVar]

        eups.setEnv(envVar, npath, interpolateEnv=True)

    def execute_addAlias(self, eups, fwd=True):
        """Execute addAlias"""

        args = self.args

        key = args[0]
        if fwd:
            value = " ".join(args[1:])
        if eups.force and eups.oldAliases[key]:
            del eups.oldAliases[key]    # Does this actually work? 

        if fwd:
            eups.setAlias(key, value)
        else:
            eups.unsetAlias(key)

    def execute_envSet(self, eups, fwd=True):
        """Execute envSet"""

        args = self.args

        key = args[0]
        if fwd:
            value = args[1]

        if eups.force and eups.oldEnviron[key]:
            del oldEnviron[key]

        if fwd:
            try:                            # look for values that are optional environment variables: $?{XXX}
                vkey = re.search(r"^$\?{([^}]*)}", value).group(0)
                if eups.environ.has_key(vkey):
                    value = eups.environ[vkey]
                else:
                  if eups.verbose > 0:
                      print >> sys.stderr, "$%s is not defined; not setting %s" % (vkey, key)
                      return
            except AttributeError:
                pass

            eups.setEnv(key, value, interpolateEnv=True)
        else:
            eups.unsetEnv(key)

    def pathUnique(self, path):
        """Remove repeated copies of an element in a delim-delimited path; e.g. aa:bb:aa:cc -> aa:bb:cc"""

        pp = []
        for d in path:
            if d not in pp:
                pp += [d]
                
        return pp

class Table(object):
    """A class that represents a eups table file"""

    def __init__(self, tableFile):
        """Parse a tablefile"""

        self.file = tableFile
        self.old = False
        self._actions = []

        self._read(tableFile)

    def _rewrite(self, contents):
        """Rewrite the contents of a tablefile to the canonical form; each
line is returned as a tuple (lineNo, line)

The rewritten table file has certain old lines removed, and both forms
of conditional (old and new) rewritten as explicit if(...) { ... } blocks,
but no other interpretation is applied
"""

        ncontents = []                  # new value of contents[]
        inGroup = False                 # in a Group...Common...End block
        inNewGroup = False              # in a Flavor=XXX ... Flavor=YYY block
        lineNo = 0                      # line number in input file, for diagnostics
        for line in contents:
            lineNo += 1

            line = re.sub(r"\n", "", line)
            line = re.sub(r"^\s*", "", line)
            line = re.sub(r"#.*$", "", line)

            if not line:
                continue
            #
            # Check for certain archaic forms:
            #
            mat = re.search(r"^File\s*=\s*(\w+)", line, re.IGNORECASE)
            if mat:
                self.old = True

                if mat.group(1).lower() != "table":
                    raise RuntimeError, \
                          ("Expected \"File = Table\"; saw \"%s\" at %s:%d" % (line, self.versionFile, lineNo))
                continue
            elif self.old:
                if re.search(r"^Product\s*=\s*(\w+)", line, re.IGNORECASE):
                    continue
            # Older synonyms for eups variables in table files
            line = re.sub(r"\${PROD_DIR}", "${PRODUCT_DIR}", line)
            line = re.sub(r"\${UPS_PROD_DIR}", "${PRODUCT_DIR}", line)
            line = re.sub(r"\${UPS_PROD_FLAVOR}", "${PRODUCT_FLAVOR}", line)
            line = re.sub(r"\${UPS_PROD_NAME}", "${PRODUCT_NAME}", line)
            line = re.sub(r"\${UPS_PROD_VERSION}", "${PRODUCT_VERSION}", line)
            line = re.sub(r"\${UPS_DB}", "${PRODUCTS}", line)
            line = re.sub(r"\${UPS_UPS_DIR}", "${UPS_DIR}", line)
            #
            # Check for lines that we think are always the same (and can thus be ignored)
            #
            mat = re.search(r"^Action\s*=\s*([\w+.]+)", line, re.IGNORECASE)
            if mat:
                if not re.search(r"setup", mat.group(1), re.IGNORECASE):
                    raise RuntimeError, ("Unsupported action \"%s\" at %s:%d" % (mat.group(1), self.file, lineNo))
                continue

            mat = re.search(r"^Qualifiers\s*=\s*\"([^\"]*)\"", line, re.IGNORECASE)
            if mat:
                if mat.group(1):
                    raise RuntimeError, ("Unsupported qualifiers \"%s\" at %s:%d" % (mat.group(1), self.file, lineNo))
                continue
            #
            # Parse Group...Common...End, replacing by a proper If statement
            #
            if re.search(r"^Group:\s*$", line, re.IGNORECASE):
                inGroup = True
                conditional = ""
                continue

            if inGroup:
                if re.search(r"^Common:\s*$", line, re.IGNORECASE):
                    ncontents += [(lineNo, "if (" + conditional + ") {")]
                    continue

                if re.search(r"^End:\s*$", line, re.IGNORECASE):
                    inGroup = False
                    ncontents += [(lineNo, "}")]
                    continue

                mat = re.search(r"^Flavor\s*=\s*([\w+.]+)", line, re.IGNORECASE)
                if mat:
                    if conditional:
                        conditional += " || "

                    flavor = mat.group(1)
                    if flavor.lower() == "any":
                        conditional += "FLAVOR =~ .*"
                    else:
                        conditional += "FLAVOR == %s" % flavor
                    continue
            #
            # New style blocks (a bad design by RHL) begin with one or more Flavor=XXX
            # lines, and continue to the next Flavor=YYY line
            #
            if inNewGroup == "inFlavors": # we're reading a set of FLAVOR=XXX lines
                mat = re.search(r"^Flavor\s*=\s*([\w+.]+)", line, re.IGNORECASE)
                if mat:                 # and we've found another
                    conditional += " || FLAVOR == %s" % mat.group(1)
                    continue
                else:                   # not FLAVOR=XXX; start of the block's body
                    ncontents += [(lineNo, "if (" + conditional + ") {")]
                    inNewGroup = True
            else:                       # Not reading FLAVOR=XXX, so a FLAVOR=XXX starts a new block
                mat = re.search(r"^Flavor\s*=\s*([\w+.]+)", line, re.IGNORECASE)
                if mat:
                    if inNewGroup:
                        ncontents += [(lineNo, "}")]

                    inNewGroup = "inFlavors"
                    conditional = "FLAVOR == %s" % mat.group(1)
                    continue

            ncontents += [(lineNo, line)]

        if inNewGroup:
            ncontents += [(lineNo, "}")]
            
        return ncontents

    def expandEupsVariables(self, product):
        """Expand eups-related variables such as $PRODUCT_DIR"""

        for action in self._actions:
            for a in action[1]:
                for i in range(len(a.args)):
                    value = a.args[i]

                    value = re.sub(r"\${PRODUCTS}", product.db, value)
                    if product.dir:
                        value = re.sub(r"\${PRODUCT_DIR}", product.dir, value)
                    value = re.sub(r"\${PRODUCT_FLAVOR}", product.eups.flavor, value)
                    value = re.sub(r"\${PRODUCT_NAME}", product.name, value)
                    value = re.sub(r"\${PRODUCT_VERSION}", product.version, value)
                    value = re.sub(r"\${UPS_DIR}", os.path.dirname(self.file), value)

                    a.args[i] = value

        return self
    
    def _read(self, tableFile):
        """Read and parse a table file, setting _actions"""

        if not tableFile:               # nothing to do
            return

        try:
            fd = file(tableFile)
        except IOError, e:
            raise RuntimeError, e

        contents = fd.readlines()
        contents = self._rewrite(contents)

        logical = "True"                 # logical condition required to execute block
        block = []
        for lineNo, line in contents:
            if False:
                print line
                continue
            #
            # Is this the start of a logical condition?
            #
            mat = re.search(r"^(:?if\s*\((.*)\)\s*{\s*|})$", line, re.IGNORECASE)
            if mat:
                if block:
                    self._actions += [(logical, block)]
                    block = []

                if mat.group(2) == None: # i.e. we saw a }
                    logical = "True"
                else:
                    logical = mat.group(2)

                continue
            #
            # Is line of the form action(...)?
            #
            mat = re.search(r'^(\w+)\s*\(([^)]*)\)', line, re.IGNORECASE)
            if mat:
                cmd = mat.group(1).lower()
                args = re.sub(r'^"(.*)"$', r'\1', mat.group(2))
                args = filter(lambda s: s, re.split("[, ]", args, 2))
                args = map(lambda s: re.sub(r'^"(.*)"$', r'\1', s), args) # remove quotes

                cmd = {
                    "addalias" : Action.addAlias,
                    "envappend" : Action.envAppend,
                    "envprepend" : Action.envPrepend,
                    "envset" : Action.envSet,
                    "envremove" : Action.envRemove,
                    "envunset" : Action.envUnset,
                    "pathappend" : Action.envAppend,
                    "pathprepend" : Action.envPrepend,
                    "pathset" : Action.envSet,
                    "proddir" : Action.prodDir,
                    "setupenv" : Action.setupEnv,
                    "setenv" : Action.envSet,
                    "setuprequired" : Action.setupRequired,
                    "setupoptional" : Action.setupOptional,
                    }[cmd]

            else:
                cmd = line; args = []

            extra = None
            if cmd == Action.prodDir or cmd == Action.setupEnv:
                pass                 # the actions are always executed
            elif cmd == Action.addAlias:
                pass
            elif cmd == Action.setupOptional or cmd == Action.setupRequired:
                if cmd == Action.setupRequired:
                    extra = False       # optional?
                else:
                    cmd = Action.setupRequired
                    extra = True        # optional?
            elif cmd == Action.envAppend or cmd == Action.envPrepend:
                if cmd == Action.envAppend:
                    cmd = Action.envPrepend
                    extra = True        # append?
                else:
                    extra = False       # append?

                if len(args) < 2 or len(args) > 3:
                    raise RuntimeError, ("%s expected 2 (or 3) arguments, saw %s" % (cmd, " ".join(args)))
            elif cmd == Action.envSet:
                if len(args) != 2:
                    raise RuntimeError, ("%s expected 2 arguments, saw %s" % (cmd, " ".join(args)))
            elif cmd == Action.envRemove or cmd == Action.envUnset:
                print >> sys.stderr, "Ignoring unsupported entry %s at %s:%d" % (line, self.file, lineNo)
                continue
            else:
                print >> sys.stderr, "Unrecognised line: %s at %s:%d" % (line, self.file, lineNo)
                continue

            block += [Action(cmd, args, extra)]
        #
        # Push any remaining actions onto current logical block
        #
        if block:
            self._actions += [(logical, block)]

    def actions(self, flavor):
        """Return a list of actions for the specified flavor"""

        if not self._actions:
            return []

        for logical, block in self._actions:
            parser = eupsParser.Parser(logical)
            parser.define("flavor", flavor)

            if parser.eval():
                return block

        raise RuntimeError, ("Table %s has no entry for flavor %s" % (self.file, flavor))

    def __str__(self):
        s = ""
        for logical, block in self._actions:
            s += "\n------------------"
            s += '\n' + str(logical)
            for a in block:
                s += '\n' + str(a)

        return s

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Version(object):
    """A class that represents a version file"""

    def __init__(self, versionFile):
        """Parse a version file"""
        
        self.file = versionFile
        self.productName = None
        self.version = None
        self.info = {}

        self._read(versionFile)

    def _read(self, versionFile):
        fd = file(versionFile)

        flavor = None
        lineNo = 0                      # line number in input file, for diagnostics
        for line in fd.readlines():
            lineNo += 1
            line = re.sub(r"\n", "", line)

            if False:
                print line
                continue

            line = re.sub(r"^\s*", "", line)
            line = re.sub(r"#.*$", "", line)
        
            if not line:
                continue
            #
            # Ignore Group: and End:
            #
            if re.search(r"^(Group|End)\s*:", line):
                continue
            #
            # Get key = value
            #
            mat = re.search(r"^(\w+)\s*=\s*(.*)", line, re.IGNORECASE)
            if mat:
                key = mat.group(1).lower()
                value = re.sub(r"^\"|\"$", "", mat.group(2))
            else:
                raise RuntimeError, \
                      ("Unexpected line \"%s\" at %s:%d" % (line, self.file, lineNo))
            #
            # Check for information about product
            #
            if key == "file":
                if value.lower() != "version":
                    raise RuntimeError, \
                          ("Expected \"File = Version\"; saw \"%s\" at %s:%d" % (line, self.file, lineNo))
            elif key == "product":
                self.productName = value
            elif key == "version":
                self.version = value
            elif key == "flavor": # Now look for flavor-specific blocks
                flavor = value
                if not self.info.has_key(flavor):
                    self.info[flavor] = {}
            else:
                value = re.sub(r"^\"(.*)\"$", r"\1", mat.group(2)) # strip ""

                if key == "qualifiers":
                    if value:           # flavor becomes e.g. Linux:build
                        flavor += ":%s" % value
                        self.info[flavor] = {}
                else:
                    self.info[flavor][key] = value

    def __str__(self):
        s = ""
        s += "Product: %s  Version: %s" % (self.productName, self.version)

        flavors = self.info.keys(); flavors.sort()
        for flavor in flavors:
            s += "\n------------------"
            s += "\nFlavor: %s" % flavor
            keys = self.info[flavor].keys(); keys.sort()
            for key in keys:
                s += "\n%-20s : %s" % (key, self.info[flavor][key])

        return s

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Product(object):
    """Represent a version of a product"""

    def __init__(self, eups, productName=None, version=None, noInit=False, productPathDirs=None):
        """Initialize a Product with the specified product and (maybe) version,
        using the eups parameters"""
        self.eups = eups

        self.name = productName         # product's name
        self.version = version          # product's version
        self.db = None                  # ups_db that we found the product in
        self.dir = None                 # product's directory
        self.table = None               # product's Table
        self._current = False           # is product current?

        if self.name and not noInit:
            mat = re.search(r"^LOCAL:(.*)", version)
            if mat:                     # a local setup
                productDir = mat.group(1)
                self.initFromDirectory(productDir)
            else:
                self.version, self.db, self.dir, tablefile = \
                              self.eups.findVersion(productName, version, productPathDirs=productPathDirs)
                self.table = Table(tablefile).expandEupsVariables(self)

    def init(self, version, flavor, productPathDir):
        """Initialize a product given full information about a product"""

        mat = re.search(r"^LOCAL:(.*)", version)
        if mat:
            productDir = mat.group(1)
            self.initFromDirectory(productDir)
        else:
            self.version, self.db, self.dir, tablefile = \
                          self.eups.findFullySpecifiedVersion(self.name, version, flavor, productPathDir)
            self.table = Table(tablefile).expandEupsVariables(self)

    def tableFileName(self):
        """Return a fully qualified tablefile name"""
        
        return os.path.join(self.dir, "ups", "%s.table" % self.name)

    def initFromDirectory(self, productDir):
        """Initialize product eups itself, given only its directory.  This is needed for
        LOCAL setups, as well as eups which can be initialised by sourcing setups.c?sh rather
        than via a setup command; in the former case it needn't even be declared to eups"""

        self.version = "LOCAL:" + productDir
        self.eups.localVersions[self.name] = productDir
        self.db = "(none)"
        self.dir = productDir
        self.table = Table(self.tableFileName()).expandEupsVariables(self)
        
    def __str__(self):
        s = ""
        s += "%s %s -f %s -Z %s" % (self.name, self.version, self.eups.flavor, self.db)

        return s

    def envarDirName(self):
        """Return the name of the product directory's environment variable"""
        return self.name.upper() + "_DIR"

    def envarSetupName(self):
        """Return the name of the product's how-I-was-setup environment variable"""
        return "SETUP_" + self.name

    def setupVersion(self):
        """Return the name, version, flavor and productPathDir for an already-setup product"""

        eups = self.eups

        productName, version, flavor, productPathDir = None, None, None, None

        try:
            args = eups.environ[self.envarSetupName()].split()
        except KeyError:
            return version, flavor, productPathDir

        productName = args.pop(0)
        if productName != self.name:
            if self.eups.verbose > 1:
                print >> sys.stderr, \
                      "Warning: product name %s != %s (probable mix of old and new eups)" %(self.name, productName)
        
        if not args: # you can get here if you initialised eups by sourcing setups.c?sh
            return version, flavor, productPathDir

        if len(args) > 1 and args[0] != "-f":
            version = args.pop(0)
            
        if len(args) > 1 and args[0] == "-f":
            args.pop(0);  flavor = args.pop(0)

        if len(args) > 1 and args[0] == "-Z":
            args.pop(0);  productPathDir = args.pop(0)

        assert not args

        return version, flavor, productPathDir

    def checkCurrent(self, isCurrent=None):
        """check if product is current.  This shouldn't be needed if update the db when declaring products"""
        if isCurrent != None:
            self._current = isCurrent
        else:
            try:
                cdb, cversion, cvinfo = self.eups.findCurrentVersion(self.name)
                self._current = (cdb == self.db and cversion == self.version)
            except RuntimeError:
                self._current = False

    def isCurrent(self):
        """Is the Product current?"""
        return self._current

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Eups(object):
    """Control eups"""

    def __init__(self, flavor=None, path=None, dbz=None, root=None, readCache=True,
                 shell=None, verbose=False, noaction=False, force=False, ignore_versions=False,
                 keep=False, max_depth=-1):
                 
        self.verbose = verbose

        if not shell:
            try:
                shell = os.environ["SHELL"]
            except KeyError:
                raise RuntimeError, "I cannot guess what shell you're running as $SHELL isn't set"

            if re.search(r"(^|/)(bash|ksh|sh)$", shell):
                shell = "sh"
            elif re.search(r"(^|/)(csh|tcsh)$", shell):
                shell = "csh"
            else:
                raise RuntimeError, ("Unknown shell type %s" % shell)    

        self.shell = shell

        if not flavor:
            flavor = getFlavor()
        self.flavor = flavor

        if not path:
            if os.environ.has_key("EUPS_PATH"):
                path = os.environ["EUPS_PATH"]
            else:
                path = []

        if isinstance(path, str):
            path = filter(lambda el: el, path.split(":"))
                
        if dbz:
            path = filter(lambda p: re.search(r"/%s(/|$)" % dbz, p), path)

        self.path = []
        for p in path:
            if not os.path.isdir(p):
                if self.verbose:
                    print >> sys.stderr, \
                          "%s in $EUPS_PATH does not contain a ups_db directory, and is being ignored" % p
                continue

            self.path += [p]        

        if not self.path and not root:
            if dbz:
                raise RuntimeError, ("No EUPS_PATH is defined that matches \"%s\"" % dbz)
            else:
                raise RuntimeError, ("No EUPS_PATH is defined")

        self.environ = os.environ.copy() # the environment variables that we want when we're done
        self.oldEnviron = os.environ.copy() # the initial version of the environment

        self.aliases = {}               # aliases that we should set
        self.oldAliases = {}            # initial value of aliases.  This is a bit of a fake, as we
                                        # don't know how to set it but (un)?setAlias knows how to handle this

        self.who = pwd.getpwuid(os.getuid())[4]

        if root:
            root = re.sub(r"^~", os.environ["HOME"], root)
            if not re.search(r"^/", root):
                root = os.path.join(os.getcwd(), root)
            root = os.path.normpath(root)
            
        self.root = root
            
        self.quiet = 0
        self.keep = keep
        self.noaction = noaction
        self.force = force
        self.ignore_versions = ignore_versions
        self.max_depth = max_depth      # == 0 => only setup toplevel package

        self._msgs = {}                 # used to suppress messages
        self._msgs["setup"] = {}        # used to suppress messages about setups
        #
        # Check for unsupported features
        #
        if self.keep:
            raise RuntimeError, "Option keep is not (yet) supported"
        #
        # Find locally-setup products in the environment
        #
        self.localVersions = {}

        for k in self.environ.keys():
            mat = re.search(r"^SETUP_(.*)", k)
            if mat:
                name = mat.group(1)

                product = self.Product(name, noInit=True)
                version, flavor, db = product.setupVersion()

                if re.search(r"^LOCAL:", version):
                    self.localVersions[product.name] = self.environ[product.envarDirName()]
        #
        # Read the cached version information
        #
        self.versions = {}
        self.readCache = readCache

        if readCache:
            for p in self.path:
                self.readDB(p)

    def Product(self, *args, **kwargs):
        """Create a Product"""
        return Product(self, *args, **kwargs)
    
    def getPersistentDB(self, p):
        """Get the name of the persistent database given a toplevel directory"""
        return os.path.join(self.getUpsDB(p), ".pickleDB")

    def getLockfile(self, p):
        """Get the name of the lockfile given a toplevel directory"""
        return os.path.join(self.getUpsDB(p), ".lock")

    def lockDB(self, p, unlock=False):
        """Lock a DB in path p"""

        lockfile = self.getLockfile(p)
        
        if unlock:
            if self.noaction:
                if self.verbose > 2:
                    print >> sys.stderr, "unlock(%s)" % lockfile
            else:
                eupsLock.unlock(lockfile)
        else:
            if self.noaction:
                if self.verbose > 2:
                    print >> sys.stderr, "lock(%s)" % lockfile
            else:
                eupsLock.lock(lockfile, self.who, max_wait=10)

    def unlinkDB(self, productPathDir):
        """Delete a persistentDB"""
        
        persistentDB = self.getPersistentDB(productPathDir)

        if not os.path.exists(persistentDB):
            return

        self.lockDB(productPathDir)

        try:
            if self.noaction:
                print >> sys.stderr, "rm %s" % persistentDB
            else:
                os.unlink(persistentDB)
        except Exception, e:
            self.lockDB(productPathDir, unlock=True)

        self.lockDB(productPathDir, unlock=True)

    def getCacheInfo(self, productPathDir):
        """Return information about a cached DB"""

        persistentDB = self.getPersistentDB(productPathDir)

        if not os.path.exists(persistentDB):
            return persistentDB, False, False

        db_mtime = os.stat(persistentDB).st_mtime # last modification date for cache

        for dirpath, dirnames, filenames in os.walk(self.getUpsDB(productPathDir)):
            break
        dirnames = map(lambda d: os.path.join(dirpath, d), dirnames)

        upToDate = True                # is cache up to date?
        for dir in dirnames:
            for dirpath, dirnames, filenames in os.walk(dir):
                for file in filenames:
                    file = os.path.join(dirpath, file)
                    mtime = os.stat(file).st_mtime # last modification date file in ups_db
                    if mtime > db_mtime:
                        upToDate = False                # cache isn't up to date
                        break
                break
            if not upToDate:
                break

        return persistentDB, True, upToDate

    def readDB(self, productPathDir):
        """Read a saved version DB from persistentDB"""
        
        persistentDB, exists, upToDate = self.getCacheInfo(productPathDir)

        if not exists or not upToDate:
            if self.verbose:
                if not exists:
                    reason, verb = "doesn't exist", "build"
                else:
                    reason, verb = "is out of date", "rebuild"
                print >> sys.stderr, "Product cache in %s %s; I'll %s it for you" % \
                      (self.getUpsDB(productPathDir), reason, verb)
                
            self.buildCache(productPathDir)
            return

        self.lockDB(productPathDir)

        try:
            fd = open(persistentDB)
            unpickled = cPickle.Unpickler(fd)
        except Exception, e:
            print >> sys.stderr, e
            self.lockDB(productPathDir, unlock=True)
            raise

        self.lockDB(productPathDir, unlock=True)

        try:
            type(self.versions)
        except:
            self.versions = {}

        versions = unpickled.load()
        
        for flavor in versions.keys():
            if not self.versions.has_key(flavor):
                self.versions[flavor] = {}

            for db in versions[flavor].keys():
                if not self.versions[flavor].has_key(db):
                    self.versions[flavor][db] = {}

                    for p in versions[flavor][db].keys():
                        if not self.versions[flavor][db].has_key(p):
                            self.versions[flavor][db][p] = {}

                            for v in versions[flavor][db][p]:
                                self.versions[flavor][db][p][v] = versions[flavor][db][p][v]
    
    def writeDB(self, productPathDir, force=False):
        """Write productPathDir's version DB to a persistent DB"""

        if not force and not self.readCache:
            if self.verbose > 2:
                print >> sys.stderr, "Not writing cache for %s as I didn't read it" % productPathDir
            return

        if isinstance(productPathDir, str):
            try:
                versions = self.versions[self.flavor][productPathDir]
            except KeyError:
                return

            persistentDB = self.getPersistentDB(productPathDir)
            
            self.lockDB(productPathDir)
            
            try:
                fd = open(persistentDB, "w")
                cPickle.dump(self.versions, fd, protocol=2)
            except Exception, e:
                print >> sys.stderr, e
                self.lockDB(productPathDir, unlock=True)
                raise

            self.lockDB(productPathDir, unlock=True)
        else:
            for p in productPathDir:
                self.writeDB(p, force)

    def clearCache(self):
        """Clear the products cache"""
        for p in self.path:
            self.unlinkDB(p)

        self.versions = {}
            
    def clearLocks(self):
        """Clear all lock files"""

        for p in self.path:
            self.lockDB(p, unlock=True)

    def getUpsDB(self, productPathDir):
        """Return the ups database directory given a directory from self.path"""
        
        return os.path.join(productPathDir, "ups_db")
    
    def setEnv(self, key, val, interpolateEnv=False):
        """Set an environmental variable"""
            
        if interpolateEnv:              # replace ${ENV} by its value if known
            val = re.sub(r"(\${([^}]*)})", lambda x : self.environ.get(x.group(2), x.group(1)), val)

        self.environ[key] = val

    def unsetEnv(self, key):
        """Unset an environmental variable"""

        if self.environ.has_key(key):
            del self.environ[key]

    def setAlias(self, key, val):
        """Set an alias.  The value is in sh syntax --- we'll mangle it for csh later"""

        self.aliases[key] = val

    def unsetAlias(self, key):
        """Unset an alias"""

        if self.aliases.has_key(key):
            del self.aliases[key]
        self.oldAliases[key] = None # so it'll be deleted if no new alias is defined

    def findCurrentVersion(self, productName, path=None):
        """Find current version of a product, returning the db and vinfo"""

        if not path:
            path = self.path
        elif isinstance(path, str):
            path = [path]

        vinfo = None
        for productPathDir in path:
            ups_db = self.getUpsDB(productPathDir)

            cfile = os.path.join(ups_db, productName, "current.chain")
            if os.path.exists(cfile):
                try:
                    version = Current(cfile).info[self.flavor]["version"]

                    vfile = os.path.join(ups_db, productName, "%s.version" % version)
                    if os.path.exists(vfile):
                        vers = Version(vfile)
                        if vers.info.has_key(self.flavor):
                            vinfo = vers.info[self.flavor]
                            return productPathDir, version, vinfo

                    raise RuntimeError, ("Unable to find current version %s of %s for flavor %s" %
                                         (version, productName, self.flavor))
                except KeyError:
                    raise RuntimeError, ("Product %s has no current version for flavor %s" % (productName, self.flavor))

        if not vinfo:                       # no version is available
            raise RuntimeError, ("Unable to locate a current version of %s for flavor %s" % (productName, self.flavor))

    def findVersion(self, productName, version=None, productPathDirs=None):
        """Find a version of a product (if no version is specified, return current version)"""
        
        if self.ignore_versions:
           version = ""

        if isinstance(productPathDirs, str):
            productPathDirs = [productPathDirs]

        if not productPathDirs:
            productPathDirs = self.path

        if not version:
            # If no version explicitly specified, get the first db with a current one.
            productPathDir, version, vinfo = self.findCurrentVersion(productName, path=productPathDirs)

            productPathDirs = [productPathDir]

        vinfo = None
        if re.search(Eups._relop_re, version): # we have a relational expression
            expr = re.sub(r"^\s*", "", version)
            version = None
            matched_productPathDir = None
            
            for productPathDir in productPathDirs: # search for the first match
                if matched_productPathDir:       # we got one in the last iteration
                    productPathDir = matched_productPathDir
                    break
                    
                dir = os.path.join(self.getUpsDB(productPathDir), productName)

                versions = []
                for vfile in glob.glob(os.path.join(dir, "*.version")):
                    vers = Version(vfile)
                    if vers.info.has_key(self.flavor):
                        versions += [(vers.version, vers.info[self.flavor])]

                versions.sort(lambda a, b: self.version_cmp(a[0], b[0]))
                versions.reverse() # so we'll try the latest version first
                #
                # Include the current version;  if it matches we'll use it
                #
                try:
                    cproductPathDir, cversion, cvinfo = self.findCurrentVersion(productName, productPathDir)
                    if cvinfo:
                        versions += [(cversion, cvinfo)]
                except RuntimeError:
                    cvinfo = None
                    pass
                #
                # We have a list of possible versions, go through them in order
                #
                for vname, _vinfo in versions:
                    if self.version_match(vname, expr):
                        matched_productPathDir = productPathDir
                        version = vname
                        vinfo = _vinfo

                        if cvinfo and version != cversion and self.verbose > 0 + self.quiet:
                            print >> sys.stderr, "Using version %s to satisfy \"%s\" (%s is current)" % \
                                  (version, expr, cversion)

                        extra = ""
                        if self.verbose >= 3 + self.quiet:
                            extra = "in %s " % root

                        if self.verbose >= 2 + self.quiet:
                            print >> sys.stderr, "Version %s %ssatisfies condition \"%s\" for product %s" % \
                                  (version, extra, expr, productName)

                        break
        else:
            for productPathDir in productPathDirs:
                ups_db = self.getUpsDB(productPathDir)
                vfile = os.path.join(ups_db, productName, "%s.version" % version)
                if os.path.exists(vfile):
                    vers = Version(vfile)
                    if vers.info.has_key(self.flavor):
                        vinfo = vers.info[self.flavor]
                        break

        if not vinfo:                       # no version is available
            raise RuntimeError, "Unable to locate %s %s for flavor %s" % (productName, version, self.flavor)

        return self._finishFinding(vinfo, productName, version, productPathDir)

    def findFullySpecifiedVersion(self, productName, version, flavor, productPathDir):
        """Find a version given full details of where to look"""
        
        vinfo = None
        ups_db = self.getUpsDB(productPathDir)
        vfile = os.path.join(ups_db, productName, "%s.version" % version)
        if os.path.exists(vfile):
            vers = Version(vfile)
            if vers.info.has_key(flavor):
                vinfo = vers.info[flavor]

        if not vinfo:                       # no version is available
            raise RuntimeError, "Unable to locate %s %s for flavor %s in %s" % \
                  (productName, version, flavor, productPathDir)

        return self._finishFinding(vinfo, productName, version, productPathDir)

    def _finishFinding(self, vinfo, productName, version, productPathDir):
        productDir = vinfo["prod_dir"]
        if productDir == "none":
            productDir = None
        else:
            if not re.search(r"^/", productDir):
                productDir = os.path.join(productPathDir, productDir)

            if not os.path.isdir(productDir):
                raise RuntimeError, ("Product %s %s has non-existent productDir %s" % (productName, version, productDir))
        #
        # Look for the directory with the tablefile
        #
        ups_db = self.getUpsDB(productPathDir)

        ups_dir = vinfo["ups_dir"]
        if productDir:
            ups_dir = re.sub(r"\$PROD_DIR", productDir, ups_dir)
        ups_dir = re.sub(r"\$UPS_DB", ups_db, ups_dir)

        tablefile = vinfo["table_file"]
        if tablefile == "none":
            tablefile = None
        else:
            tablefile = os.path.join(ups_dir, vinfo["table_file"])
            
            if not os.path.exists(tablefile):
                raise RuntimeError, ("Product %s %s has non-existent tablefile %s" % (productName, version, tablefile))

        return version, productPathDir, productDir, tablefile

    def getProduct(self, productName, version, productPathDirs=None):
        """Return a Product, preferably from the cache but the hard way if needs be"""

        """N.b. we should be getting current information from the cached info, but eups declare
        doesn't do that yet"""

        if productPathDirs:
            dbs = productPathDirs
        elif self.versions.has_key(self.flavor):
            dbs = self.versions[self.flavor].keys() # known eups databases
        else:
            dbs = []
            
        if version:
            foundCurrent = False
        else:
            foundCurrent = True
            db, version, vinfo = self.findCurrentVersion(productName)
            dbs = [db] + filter(lambda d: d != db, dbs) # but db with current version first in the path
        #
        # Try to look it up in the db/product/version dictionary
        #
        for db in dbs:
            try:
                product = self.versions[self.flavor][db][productName][version]
                if self.verbose > 2:
                    print >> sys.stderr, "Found %s %s in cache" % (productName, version)

                if foundCurrent:
                    product.checkCurrent(True)
                else:
                    product.checkCurrent()          # check if it's current

                return product
            except KeyError:
                pass

        product = self.Product(productName, version)

        if foundCurrent:
            product.checkCurrent(True)
        else:
            product.checkCurrent()      # check if it's current

        self.intern(product)            # save it in the cache

        return product

    def buildCache(self, productPathDir=None):
        """Build the persistent version cache"""

        if not productPathDir:
            for pb in self.path:
                self.buildCache(pb)
            return

        re_version = re.compile(r"^(.*).version$")
        for dirpath, dirnames, filenames in os.walk(self.getUpsDB(productPathDir)):
            productName = os.path.basename(dirpath)
            for file in filenames:
                mat = re.search(re_version, file)
                if mat:
                    version = mat.group(1)

                    try:
                        self.getProduct(productName, version, [productPathDir])
                    except RuntimeError, e:
                        # We only checked for the existance of the file, but when we tried to get the product
                        # we checked for a valid flavor. Don't want to tell the user about those failures
                        if re.search(r"for flavor %s$" % self.flavor, e.__str__()):
                            continue
                        print >> sys.stderr, e

        self.writeDB(productPathDir, force=True)

    def isSetup(self, product, version=None, productPathDir=None):
        """Is specified Product already setup?"""

        if isinstance(product, str):
            product = self.Product(product, noInit=True)

        if not self.environ.has_key(product.envarSetupName()):
            return False
        
        sversion, sflavor, sproductPathDir = product.setupVersion()

        if version:
            return version == sversion
        elif productPathDir:
            return productPathDir == sproductPathDir
        else:
            return True

    def unsetupSetupProduct(self, product):
        """ """

        if not self.isSetup(product):
            return
    
        version, flavor, productPathDir = product.setupVersion()

        oldProduct = self.Product(product.name, noInit=True)
        if product.name == "eups" and not version: # you can get here if you setup eups by sourcing setups.c?sh
            oldProduct.initFromDirectory(self.environ[product.envarDirName()])
        else:
            oldProduct.init(version, flavor, productPathDir)

        self.setup(oldProduct, fwd=False)  # do the actual unsetup

    # Permitted relational operators
    _relop_re = r"<=?|>=?|==";

    def version_cmp(self, v1, v2, suffix=False):
        """Compare two version strings

    The strings are split on [._] and each component is compared, numerically
    or as strings as the case may be.  If the first component begins with a non-numerical
    string, the other must start the same way to be declared a match.

    If one version is a substring of the other, the longer is taken to be the greater

    If the version string includes a '-' (say VV-EE) the version will be fully sorted on VV,
    and then on EE iff the two VV parts are different.  VV sorts to the RIGHT of VV-EE --
    e.g. 1.10.0-rc2 comes to the LEFT of 1.10.0

    Additionally, you can specify another modifier +FF; in this case VV sorts to the LEFT of VV+FF
    e.g. 1.10.0+hack1 sorts to the RIGHT of 1.10.0

    As an alternative appealing to cvs users, you can replace -EE by mEE or +FF by pFF, but in
    this case EE and FF must be integers
    """
        def split_version(version):
            # Split a version string of the form VVV([m-]EEE)?([p+]FFF)?
            if not version:
                return "", "", ""

            mat = re.search(r"^([^-+]+)((-)([^-+]+))?((\+)([^-+]+))?", version)
            vvv, eee, fff = mat.group(1), mat.group(4), mat.group(7)

            if not eee and not fff:             # maybe they used VVVm# or VVVp#?
                mat = re.search(r"(m(\d+)|p(\d+))$", version)
                if mat:
                    suffix, eee, fff = mat.group(1), mat.group(2), mat.group(3)
                    vvv = re.sub(r"%s$" % suffix, "", version)

            return vvv, eee, fff

        prim1, sec1, ter1 = split_version(v1)
        prim2, sec2, ter2 = split_version(v2)

        if prim1 == prim2:
            if sec1 or sec2 or ter1 or ter2:
                if sec1 or sec2:
                    if (sec1 and sec2):
                        ret = self.version_cmp(sec1, sec2, True)
                    else:
                        if sec1:
                            return -1
                        else:
                            return 1

                    if ret == 0:
                        return self.version_cmp(ter1, ter2, True)
                    else:
                        return ret

                return self.version_cmp(ter1, ter2, True)
            else:
                return 0

        c1 = re.split(r"[._]", prim1)
        c2 = re.split(r"[._]", prim2)
        #
        # Check that leading non-numerical parts agree
        #
        if not suffix:
            prefix = ""
            mat = re.search(r"^([^0-9]+)", c1[0])
            if mat:
                prefix = mat.group(1)

                if not re.search(r"^%s" % prefix, c2[0]):
                    return -1
            else:
                mat = re.search(r"^([^0-9]+)", c2[0])
                if mat:
                    prefix = mat.group(1)

                    if not re.search(r"^%s" % prefix, c2[0]):
                        return -1

            c1[0] = re.sub(r"^%s" % prefix, "", c1[0])
            c2[0] = re.sub(r"^%s" % prefix, "", c2[0])

        n1 = len(c1); n2 = len(c2)
        if n1 < n2:
            n = n1
        else:
            n = n2

        for i in range(n):
            different = cmp(c1[i], c2[i])
            if different:
                return different

        # So far, the two versions are identical.  The longer version should sort later
        return cmp(n1, n2)

    def version_match(self, vname, expr):
        """Return vname if it matches the logical expression expr"""

        expr = filter(lambda x: x != "", re.split(r"\s*(%s|\|\|)\s*" % Eups._relop_re, expr))

        oring = True;                       # We are ||ing primitives
        i = -1
        while i < len(expr) - 1:
            i += 1

            if re.search(Eups._relop_re, expr[i]):
                op = expr[i]; i += 1
                v = expr[i]
            elif re.search(r"^[-+.\w]+$", expr[i]):
                op = "=="
                v = expr[i]
            elif expr == "||" or expr == "or":
                oring = True;                     # fine; that is what we expected to see
                continue
            else:
                print >> sys.stderr, "Unexpected operator %s in \"%s\"" % (expr[i], expr)
                break

            if oring:                # Fine;  we have a primitive to OR in
                if self.version_match_prim(op, vname, v):
                    return vname

                oring = False
            else:
                print >> sys.stderr, "Expected logical operator || in \"%s\" at %s" % (expr, v)

        return None

    def version_match_prim(self, op, v1, v2):
        """
    Compare two version strings, using the specified operator (< <= == >= >), returning
    true if the condition is satisfied

    Uses version_cmp to define sort order """

        if op == "<":
            return self.version_cmp(v1, v2) <  0
        elif (op == "<="):
            return self.version_cmp(v1, v2) <= 0
        elif (op == "=="):
            return self.version_cmp(v1, v2) == 0
        elif (op == ">"):
            return self.version_cmp(v1, v2) >  0
        elif (op == ">="):
            return self.version_cmp(v1, v2) >= 0
        else:
            print >> sys.stderr, "Unknown operator %s used with %s, %s--- complain to RHL", (op, v1, v2)
    #
    # Here is the externally visible API
    #
    def intern(self, product, updateDB=True):
        """Remember a product in the proper place; if updateDB is true, also save it to disk"""

        d = self.versions

        if not d.has_key(product.eups.flavor):
            d[product.eups.flavor] = {}
        d = d[product.eups.flavor]            

        if not d.has_key(product.db):
            d[product.db] = {}
        d = d[product.db]
            
        if not d.has_key(product.name):
            d[product.name] = {}
        d = d[product.name]
        
        d[product.version] = product
    
        if updateDB:
            self.writeDB(product.db)

    def setup(self, productName, version=None, fwd=True, nestedLevel=0):
        """The workhorse for setup.  Return (success?, version, actions) where actions is a list of shell
        commands that we need to issue"""
        #
        # Look for product directory
        #
        if isinstance(productName, Product): # it's already a full Product
            assert nestedLevel == 0
            product = productName
        else:
            if self.root and nestedLevel == 0:
                product = self.Product(productName, noInit=True)
                product.initFromDirectory(self.root)
            else:
                try:
                    product = self.getProduct(productName, version)
                except RuntimeError, e:
                    if self.verbose:
                        print >> sys.stderr, e

                    return False, version
        #
        # We have all that we need to know about the product to proceed
        #
        table = product.table
            
        try:
            actions = table.actions(self.flavor)
        except RuntimeError, e:
            print >> sys.stderr, "product %s %s: %s" % (product.name, product.version, e)
            return False, product.version
        #
        # Ready to go
        #
        if fwd and self.verbose:
            # self._msgs["setup"] is used to suppress multiple messages about setting up the same product
            if nestedLevel == 0:
                self._msgs["setup"] = {}
            
            setup_msgs = self._msgs["setup"]

            indent = "| " * (nestedLevel/2)
            if nestedLevel%2 == 1:
                indent += "|"

            key = "%s:%s:%s" % (product.name, self.flavor, product.version)
            if self.verbose > 1 or not setup_msgs.has_key(key):
                print >> sys.stderr, "Setting up: %-30s  Flavor: %-10s Version: %s" % \
                      (indent + product.name, self.flavor, product.version)
                setup_msgs[key] = 1

        if fwd:
            #
            # Are we already setup?
            #
            sversion, sflavor, sproductPathDir = product.setupVersion()
            if version and sversion:
                if version == sversion: # already setup
                    if nestedLevel == 0: # top level should be resetup if that's what they asked for
                        pass
                    else:
                        return True, version
                else:
                    print >> sys.stderr, "You setup %s %s, and are now setting up %s" % \
                          (product.name, sversion, version)
                
            self.unsetupSetupProduct(product)

            self.setEnv(product.envarDirName(), product.dir)
            self.setEnv(product.envarSetupName(),
                        "%s %s -f %s -Z %s" % (product.name, product.version, product.eups.flavor, product.db))
        else:
            if product.dir in self.localVersions.keys():
                del self.localVersions[product.dir]

            self.unsetEnv(product.envarDirName())
            self.unsetEnv(product.envarSetupName())
        #
        # Process table file
        #
        for a in actions:
            a.execute(self, nestedLevel + 1, fwd)

        return True, product.version

    def listProducts(self, productName=None, productVersion=None,
                     current=False, setup=False, tablefile=False, directory=False):
        productList = []

        if not self.versions.has_key(self.flavor):
            return productList
        #
        # Find all products on path (cached in self.versions, of course)
        #
        for db in self.path:
            if not self.versions[self.flavor].has_key(db):
                continue
            
            for name in self.versions[self.flavor][db].keys():
                if productName and name != productName:
                    continue
                
                for version in self.versions[self.flavor][db][name].keys():
                    if productVersion and version != productVersion:
                        continue

                    product = self.versions[self.flavor][db][name][version]

                    isCurrent = product.isCurrent()
                    isSetup = self.isSetup(product, version, db)

                    if current and not isCurrent:
                        continue

                    if setup and not isSetup:
                        continue

                    values = []
                    values += [name]
                    values += [version, db, product.dir, isCurrent, isSetup]
                    productList += [values]
        #
        # Add in LOCAL: setups
        #
        for productDir in self.localVersions.values():
            product.initFromDirectory(productDir)

            values = []
            values += [product.name]
            values += [product.version, product.db, product.dir, False, True]
            productList += [values]
        #
        # And sort them for the end user
        #
        def sort_versions(a, b):
            if a[0] == b[0]:
                return self.version_cmp(a[1], b[1])
            else:
                return cmp(a[0], b[0])
            
        productList.sort(sort_versions)

        return productList

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def flavor():
    """Return the current flavor"""
    
    if os.environ.has_key("EUPS_FLAVOR"):
        return os.environ["EUPS_FLAVOR"]

    uname = str.split(os.popen('uname -s').readline(), "\n")[0]
    mach = str.split(os.popen('uname -m').readline(), "\n")[0]

    if uname == "Linux":
       if re.search(r"_64$", mach):
           flav = "Linux64"
       else:
           flav = "Linux"
    elif uname == "Darwin":
       if re.search(r"i386$", mach):
           flav = "DarwinX86"
       else:
           flav = "Darwin"
    else:
        raise RuntimeError, ("Unknown flavor: (%s, %s)" % (uname, mach))

    return flav    
    
getFlavor = flavor                      # useful in this file if you have a variable named flavor

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def setup(eups, productName, version=None, fwd=True):
    """Return a filename which, when sourced, will setup a product (if fwd is false, unset it up)"""

    ok, version = eups.setup(productName, version, fwd)
    if ok:
        import tempfile

        tfd, tmpfile = tempfile.mkstemp("", "eups")
        tfd = os.fdopen(tfd, "w")
        #
        # Set new variables
        #
        for key in eups.environ.keys():
            val = eups.environ[key]
            try:
                if val == eups.oldEnviron[key]:
                    continue
            except KeyError:
                pass

            if not re.search(r"^['\"].*['\"]$", val) and \
                   re.search(r"[\s<>|&;]", val):   # quote characters that the shell cares about
                val = "'%s'" % val

            if eups.shell == "sh":
                cmd = "export %s=%s" % (key, val)
            elif eups.shell == "csh":
                cmd = "setenv %s %s" % (key, val)

            if eups.noaction:
                if eups.verbose < 2 and re.search(r"SETUP_", key):
                    continue            # the SETUP_PRODUCT variables are an implementation detail

                cmd = "echo \"%s\"" % cmd

            tfd.write(cmd + "\n")
        #
        # unset ones that have disappeared
        #
        for key in eups.oldEnviron.keys():
            if re.search(r"^EUPS_(DIR|PATH)$", key): # the world will break if we delete these
                continue        

            if eups.environ.has_key(key):
                continue

            if eups.shell == "sh":
                cmd = "unset %s" % (key)
            elif eups.shell == "csh":
                cmd = "unsetenv %s" % (key)

            if eups.noaction:
                if eups.verbose < 2 and re.search(r"SETUP_", key):
                    continue            # an implementation detail

                cmd = "echo \"%s\"" % cmd

            tfd.write(cmd + "\n")
        #
        # Now handle aliases
        #
        for key in eups.aliases.keys():
            value = eups.aliases[key]

            try:
                if value == eups.oldAliases[key]:
                    continue
            except KeyError:
                pass

            if eups.shell == "sh":
                cmd = "function %s { %s ; }; export -f %s" % (key, value, key)
            elif eups.shell == "csh":
                value = re.sub(r"\$@", r"\!*", value)
                cmd = "alias %s \'%s\'" % (key, value)

            if eups.noaction:
                cmd = "echo \"%s\"" % re.sub(r"`", r"\`", cmd)

            tfd.write(cmd + "\n")
        #
        # and unset ones that used to be present, but are now gone
        #
        for key in eups.oldAliases.keys():
            if eups.aliases.has_key(key):
                continue

            if eups.shell == "sh":
                cmd = "unset %s" % (key)
            elif eups.shell == "csh":
                cmd = "unalias %s" (key)

            if eups.noaction:
                cmd = "echo \"%s\"" % cmd

            tfd.write(cmd + "\n")
        #
        # Make the file cleanup after itself
        #    
        if eups.verbose > 3:
            print >> sys.stderr, "Not deleting %s" % tmpfile
        else:
            tfd.write("/bin/rm -f %s\n" % tmpfile)

        return tmpfile
    else:
        print >> sys.stderr, "Failed to setup %s %s" % (productName, version)
        return ""

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def unsetup(eups, productName, version=None):
    """ """

    return setup(eups, productName, version, fwd=False)

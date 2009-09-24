#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import os
import re, sys
import pdb

from exceptions import BadTableContent, TableFileNotFound
from Parser import Parser
import utils

class Table(object):
    """A class that represents a eups table file"""

    def __init__(self, tableFile):
        """
        Parse a tablefile
        @throws TableError       if an IOError occurs while reading the table file
        @throws BadTableContent  if the table file parser encounters unparseable 
                                   content.  Note that BadTableContent is a subclass
                                   of TableError.
        """

        self.file = tableFile
        self.old = False
        self._actions = []

        if utils.isRealFilename(tableFile):
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
                    msg = "Expected \"File = Table\"; saw \"%s\" at %s:%d" % (line, self.versionFile, lineNo)
                    raise BadTableContent(self.file, msg=msg)
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
                    msg = "Unsupported action \"%s\" at %s:%d" % (mat.group(1), self.file, lineNo)
                    raise BadTableContent(self.file, msg=msg)
                continue

            mat = re.search(r"^Qualifiers\s*=\s*\"([^\"]*)\"", line, re.IGNORECASE)
            if mat:
                if mat.group(1):
                    if False:
                        msg = "Unsupported qualifiers \"%s\" at %s:%d" % (mat.group(1), self.file, lineNo)
                        raise BadTableContent(self.file, msg=msg)
                    else:
                        print >> sys.stderr, "Ignoring qualifiers \"%s\" at %s:%d" % (mat.group(1), self.file, lineNo)
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

                    root = product.stackRoot()
                    if root:
                        value = re.sub(r"\${PRODUCTS}", root, value)
                    elif re.search(r"\${PRODUCTS}", value):
                        print >> sys.stderr, "Unable to expand PRODUCTS in %s" % self.file

                    if re.search(r"\${PRODUCT_DIR}", value):
                        if product.dir:
                            value = re.sub(r"\${PRODUCT_DIR}", product.dir, value)
                        elif re.search(r"\${PRODUCT_DIR}", value):
                            print >> sys.stderr, "Unable to expand PRODUCT_DIR in %s" % self.file

                    if product.flavor:
                        value = re.sub(r"\${PRODUCT_FLAVOR}", product.flavor, value)
                    elif re.search(r"\${PRODUCT_FLAVOR}", value):
                        print >> sys.stderr, "Unable to expand PRODUCT_FLAVOR in %s" % self.file

                    value = re.sub(r"\${PRODUCT_NAME}", product.name, value)
                    if re.search(r"\${PRODUCT_VERSION}", value):
                        if product.version:
                            value = re.sub(r"\${PRODUCT_VERSION}", product.version, value)
                        elif re.search(r"\${PRODUCT_VERSION}", value):
                            print >> sys.stderr, "Unable to expand PRODUCT_VERSION in %s" % self.file

                    value = re.sub(r"\${UPS_DIR}", os.path.dirname(self.file), value)
                    #
                    # EUPS_PATH is really an environment variable, but handle it here
                    # if the user chose to subscript it, e.g. ${EUPS_PATH[0]}
                    #
                    mat = re.search(r"\${EUPS_PATH\[(\d+)\]}", value)
                    if mat:
                        ind = int(mat.group(1))
                        value = re.sub(r"\[(\d+)\]}$", "", value) + "}"

                        if not os.environ.has_key("EUPS_PATH"):
                            print >> sys.stderr, "%s is not defined; not setting %s" % (value, a.args[0])
                            continue

                        try:
                            value = os.environ["EUPS_PATH"].split(":")[ind]
                        except IndexError:
                            if product.Eups.verbose > 0:
                                print >> sys.stderr, "Invalid index %d for \"%s\"; not setting %s" % \
                                      (ind, os.environ["EUPS_PATH"], a.args[0])

                    a.args[i] = value

        return self
    
    def _read(self, tableFile):
        """Read and parse a table file, setting _actions"""

        if not tableFile:               # nothing to do
            return

        try:
            fd = file(tableFile)
        except IOError, e:
            raise TableError(tablefile, str(e))

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
                #
                # Special case cmd(..., " ") by protecting " " as "\001"
                #
                args = re.sub(r',\s*"(\s)"', r'\1"%c"' % 1, args)

                args = filter(lambda s: s, re.split("[, ]", args))
                args = map(lambda s: re.sub(r'^"(.*)"$', r'\1', s), args) # remove quotes
                args = map(lambda s: re.sub(r'%c' % 1, r' ', s), args) # reinstate \001 as a space

                try:
                    cmd = {
                        "addalias" : Action.addAlias,
                        "envappend" : Action.envAppend,
                        "envprepend" : Action.envPrepend,
                        "envremove" : Action.envRemove,
                        "envset" : Action.envSet,
                        "envunset" : Action.envUnset,
                        "pathappend" : Action.envAppend,
                        "pathprepend" : Action.envPrepend,
                        "pathremove" : Action.envRemove,
                        "pathset" : Action.envSet,
                        "proddir" : Action.prodDir,
                        "setupenv" : Action.setupEnv,
                        "setenv" : Action.envSet,
                        "setuprequired" : Action.setupRequired,
                        "setupoptional" : Action.setupOptional,
                        "sourcerequired" : Action.sourceRequired,
                        }[cmd]
                except KeyError:
                    print >> sys.stderr, "Unexpected line in %s:%d: %s" % (tableFile, lineNo, line)
                    continue
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
                    msg = "%s expected 2 (or 3) arguments, saw %s at %s:%d" % \
                        (cmd, " ".join(args), self.file, lineNo)
                    raise BadTableContent(self.file, msg=msg)

            elif cmd == Action.envSet:
                if len(args) < 2:
                    msg = "%s expected 2 arguments, saw %s at %s:%d" % \
                        (cmd, " ".join(args), self.file, lineNo)
                    raise BadTableContent(self.file, msg=msg)

                else:
                    args = [args[0], " ".join(args[1:])]
            elif cmd == Action.envRemove or cmd == Action.envUnset or cmd == Action.sourceRequired:
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

    def actions(self, flavor, setupType=None):
        """Return a list of actions for the specified flavor"""

        actions = []
        if not self._actions:
            return actions

        for logical, block in self._actions:
            parser = Parser(logical)
            parser.define("flavor", flavor)
            if setupType:
                parser.define("type", setupType)

            if parser.eval():
                actions += block

        if len(actions) == 0 and False:
            msg = "Table %s has no entry for flavor %s" % (self.file, flavor)
            print >> sys.stderr, msg
        return actions

    def __str__(self):
        s = ""
        for logical, block in self._actions:
            s += "\n------------------"
            s += '\n' + str(logical)
            for a in block:
                s += '\n' + str(a)

        return s

    _versionre = re.compile(r"(.*)\s+\[([^\]]+)\]\s*")

    def dependencies(self, Eups, eupsPathDirs=None, recursive=None, recursionDepth=0, setupType=None):
        """
        Return the product dependencies as specified in this table as a list 
        of (Product, optional) tuples

        @param Eups            an Eups instance to use to locate packages
        @param eupsPathDirs    the product stacks to restrict searches to
        @param recursive       if True, this function will be called 
                                  recursively on each of the dependency 
                                  products in this table.
        """

        if recursive and not isinstance(recursive, bool):
            recursiveDict = recursive
        else:
            recursiveDict = {}          # dictionary of products we've analysed
        prodkey = lambda p: "%s-%s" % (p.name, p.version)

        deps = []
        for a in self.actions(Eups.flavor, setupType=setupType):
            if a.cmd == Action.setupRequired:
                productName = a.args[0]
                if len(a.args) > 1:
                    versionArg = " ".join(args[1:])
                else:
                    versionArg = None
                
                mat = re.search(versionre, versionArg)
                if mat:
                    exactVersion, logicalVersion = mat.groups()
                    if Eups.exact_version:
                        versionArg = exactVersion
                    else:
                        versionArg = logicalVersion

                        args = (args[0], otherArgs)

                try:
                    product = Eups.getProduct(productName, versionArg)

                    val = [product, a.extra]
                    if recursive:
                        val += [recursionDepth]
                    deps += [val]

                    if recursive and not recursiveDict.has_key(prodkey(product)):
                        recursiveDict[prodkey(product)] = 1
                        deptable = product.getTable()
                        if deptable:
                            deps += deptable.dependencies(eupsPathDirs, recursiveDict, recursionDepth+1)
                        
                except ProductNotFound, e:
                    if a.extra:         # product is optional
                        continue
                    raise

        return deps

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Action(object):
    """
    An action in a table file

    Action instances are typically created internally by a Table constructor 
    via a Parser.
    """

    # Possible actions; the comments apply to the field that _read adds to an Action: (cmd, args, extra)
    addAlias = "addAlias"
    envAppend = "envAppend"             # not used
    envPrepend = "envPrepend"           # extra: bool append
    envRemove = "envRemove"             # not supported
    envSet = "envSet"
    envUnset = "envUnset"               # not supported
    prodDir = "prodDir"
    setupEnv = "setupEnv"
    setupOptional = "setupOptional"     # not used
    setupRequired = "setupRequired"     # extra: bool optional
    sourceRequired = "sourceRequired"   # not supported

    def __init__(self, cmd, args, extra):
        """
        Create the Action.  
        @param cmd      the name of the command (as it appears in the table file
                          command line)
        @param args     the list of arguments passed to the command as 
                          instantiated in a table file.
        @param extra    extra, command-specific data passed by the parser to 
                          control the execution of the command.  
        """
        self.cmd = cmd
        try:
            i = args.index("-f")
            del args[i:i+2]
        except ValueError:
            pass
        self.args = args
        self.extra = extra

    def __str__(self):
        return "%s %s %s" % (self.cmd, self.args, self.extra)

    def execute(self, Eups, recursionDepth, fwd=True, noRecursion=False):
        """Execute an action"""

        if self.cmd == Action.setupRequired:
            if noRecursion or recursionDepth == Eups.max_depth + 1:
                return

            self.execute_setupRequired(Eups, recursionDepth, fwd)
        elif self.cmd == Action.envPrepend:
            self.execute_envPrepend(Eups, fwd)
        elif self.cmd == Action.envSet:
            self.execute_envSet(Eups, fwd)
        elif self.cmd == Action.addAlias:
            self.execute_addAlias(Eups, fwd)
        elif self.cmd == Action.prodDir or self.cmd == Action.setupEnv:
            pass
        else:
            print >> sys.stderr, "Unimplemented action", self.cmd
    #
    # Here are the real execute routines
    #
    def execute_setupRequired(self, Eups, recursionDepth, fwd=True):
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

        if vers:  
            # see if a version of the form "logical [exact]"
            mat = re.search(r"(\S*)\s*\[([^\]]+)\]\s*", vers)
            if mat:
                exactVersion, logicalVersion = mat.groups()
                if Eups.exact_version:
                    if not exactVersion:
                        if Eups.verbose > 1 - fwd:
                            if fwd:
                                verb = "setup"
                            else:
                                verb = "unsetup"
                            print >> sys.stderr, \
                                  "You asked me to %s an exact version of %s but I only found an expression; using %s" % \
                                  (verb, productName, logicalVersion)
                        vers = logicalVersion
                    else:
                        vers = exactVersion
                else:
                    vers = logicalVersion

        productOK, vers, reason = Eups.setup(productName, vers, fwd, recursionDepth)
            
        if not productOK and fwd:
            if optional:                # setup the pre-existing version (if any)
                try:
                    product = Eups.findSetupProduct(productName, Eups.oldEnviron)
                    if product:
                        q = utils.Quiet(Eups)
                        productOK, vers, reason = Eups.setup(productName, product.version, fwd, recursionDepth)
                        del q
                        if productOK:
                            if Eups.verbose > 0:
                                print >> sys.stderr, "            %sKept previously setup %s %s" % \
                                    (recursionDepth*" ", product.name, product.version)
                        else:
                            #utils.debug(reason)
                            pass
                except RuntimeError, e:
                    pass
            else:
                raise RuntimeError, ("Failed to setup required product %s %s: %s" % (productName, vers, reason))

    def execute_envPrepend(self, Eups, fwd=True):
        """Execute envPrepend"""

        args = self.args
        append = self.extra

        envVar = args[0]                # environment variable to set
        value = args[1]                 # add/subtract this value to the variable
        if len(args) > 2:
            delim = args[2]
        else:
            delim = ":"

        opath = os.environ.get(envVar, "") # old value of envVar (generally a path of some sort, hence the name)

        prepend_delim = re.search(r"^%s" % delim, opath) # should we prepend an extra :?
        append_delim = re.search(r"%s$" % delim, opath) # should we append an extra :?

        opath = filter(lambda el: el, opath.split(delim)) # strip extra : at start or end

        if fwd:
            try:                            # look for values that are optional environment variables: $?{XXX}
                                            # if they don't exist, ignore the entire line
                varRE = r"^\$\?{([^}]*)}"                                            
                key = re.search(varRE, value).group(1)
                if os.environ.has_key(key):
                    value = re.sub(varRE, os.environ[key], value)
                else:
                  if Eups.verbose > 0:
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

        if Eups.force and Eups.oldEnviron.has_key(envVar):
            del Eups.oldEnviron[envVar]

        Eups.setEnv(envVar, npath, interpolateEnv=True)

    def execute_addAlias(self, Eups, fwd=True):
        """Execute addAlias"""

        args = self.args

        key = args[0]
        if fwd:
            value = " ".join(args[1:])
        if Eups.force and Eups.oldAliases[key]:
            del Eups.oldAliases[key]    # Does this actually work? 

        if fwd:
            Eups.setAlias(key, value)
        else:
            Eups.unsetAlias(key)

    def execute_envSet(self, Eups, fwd=True):
        """Execute envSet"""

        args = self.args

        key = args[0]
        if fwd:
            value = args[1]

        if Eups.force and Eups.oldEnviron[key]:
            del oldEnviron[key]

        if fwd:
            try:                            # look for values that are optional environment variables: $?{XXX}
                                            # if they don't exist, ignore the entire line
                varRE = r"^\$\?{([^}]*)}"
                vkey = re.search(varRE, value).group(1)
                if os.environ.has_key(vkey):
                    value = re.sub(varRE, os.environ[vkey], value)
                else:
                    if Eups.verbose > 0:
                        print >> sys.stderr, "$%s is not defined; not setting %s" % (vkey, key)
                    return
            except AttributeError:
                pass

            Eups.setEnv(key, value, interpolateEnv=True)
        else:
            Eups.unsetEnv(key)

    def pathUnique(self, path):
        """Remove repeated copies of an element in a delim-delimited path; e.g. aa:bb:aa:cc -> aa:bb:cc"""

        pp = []
        for d in path:
            if d not in pp:
                pp += [d]
                
        return pp

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Expand a table file
#
def expandTableFile(Eups, ofd, ifd, productList, versionRegexp=None):
    """Expand a table file, reading from ifd and writing to ofd"""
    #
    # Here's the function to do the substitutions
    #
    subs = {}                               # dictionary of substitutions

    def subSetup(match):
        cmd = match.group(1)
        args = match.group(2).split()

        original = match.group(0)

        flags = []; words = []

        i = -1
        while True:
            i += 1
            if i == len(args):
                break
            
            a = args[i]

            if re.search(r"^-[fgHmMqrUz]", a):
                i += 1

                if i == len(args):
                    raise RuntimeError, ("Flag %s expected an argument" % a)

                flags += ["%s %s" % (a, args[i])]
            elif re.search(r"^-[cdejknoPsvtV0-3]", a):
                flags += [a]
            elif re.search(r"^-[BO]", a):
                print >> sys.stderr, "I don't know how to process %s" % a
            elif re.search(r"^-", a):
                print >> sys.stderr, "Unknown setup flag %s" % a
            else:                       # split [expr] into separate words for later convenience
                mat = re.search(r"^\[\s*(.*)\s*\]?$", a)
                if mat:
                    words += ["["]
                    a = mat.group(1)

                mat = re.search(r"^(.*)\s*\]$", a)
                if mat:
                    words += [mat.group(1), "]"]
                else:
                    words += [a]
        try:
            productName = words.pop(0)
        except IndexError:
            print >> sys.stderr, "I cannot find a product in %s; passing through unchanged" % original
            return original

        try:
            version = words.pop(0)
        except IndexError:
            version = None
        # 
        #
        # Is version actually a logical expression?  If so, we'll want to save it
        # as well as the exact version being installed
        #
        logical = None;
        #
        # Is there already a logical expression [in square brackets]? If so, we want to keep it
        #
        if "[" in words and "]" in words:
            left, right = words.index("["), words.index("]")
            logical = " ".join(words[left + 1 : right])
            del words[left : right + 1]

        if version and Eups.versionIsRelative(version):
            if logical:                 # how did this happen? Version is logical and also a [logical]
                print >> sys.stderr, "Two logical expressions are present in %s; using first" % original
                
            logical = " ".join([version] + words)
            version = None

        version = productList.get(productName, version) # accept the explicit version if provided

        if not version:
            try:
                product = Eups.findSetupProduct(productName)
                version = product.version
            except RuntimeError, e:
                print >> sys.stderr, e

        if logical:
            if not Eups.version_match(version, logical):
                print >> sys.stderr, "Warning: %s %s failed to match condition \"%s\"" % (productName, version, logical)
        else:
            if version and not re.search(r"^LOCAL:", version):
                logical = ">= %s" % version

        args = flags + [productName]
        if version:
            args += [version]
            if versionRegexp and not re.search(versionRegexp, version):
                print >> sys.stderr, "Suspicious version for %s: %s" % (productName, version)
        #
        # Here's where we record the logical expression, if provided
        #
        if logical:
            args += ["[%s]" % logical]

        rewrite = "%s(%s)" % (cmd, " ".join(args))

        return rewrite
    #
    # Actually do the work
    #
    
    for line in ifd:
        if re.search(r"^\s*#", line):
            print >> ofd, line,
            continue
            
        # Attempt substitutions
        line = re.sub(r'(setupRequired|setupOptional)\("?([^"]*)"?\)', subSetup, line)

        print >> ofd, line,

#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import os
import re, sys

import eups
from exceptions import BadTableContent, TableFileNotFound, ProductNotFound
import Product
from tags       import TagNotRecognized
from VersionParser import VersionParser
import utils
import hooks

class Table(object):
    """A class that represents a eups table file"""

    def __init__(self, tableFile, topProduct=None, addDefaultProduct=None):
        """
        Parse a tablefile
        @param  The tablefile we're reading
        @param  The Product that owns this tablefile
        @throws TableError       if an IOError occurs while reading the table file
        @throws BadTableContent  if the table file parser encounters unparseable 
                                   content.  Note that BadTableContent is a subclass
                                   of TableError.
        """

        self.file = tableFile
        self.topProduct = topProduct
        self.old = False
        self._actions = []

        if utils.isRealFilename(tableFile):
            self._read(tableFile, addDefaultProduct)

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

    def expandEupsVariables(self, product, quiet=False):
        """Expand eups-related variables such as $PRODUCT_DIR"""

        for logical, ifBlock, elseBlock in self._actions: 
            for a in ifBlock + elseBlock:
                for i in range(len(a.args)):
                    value = a.args[i]

                    root = product.stackRoot()
                    if root:
                        value = re.sub(r"\${PRODUCTS}", root, value)
                    elif re.search(r"\${PRODUCTS}", value):
                        if not quiet:
                            print >> sys.stderr, "Unable to expand PRODUCTS in %s" % self.file

                    mat = re.search(r"\$(\?)?{PRODUCT_DIR}", value)
                    if mat:
                        optional = mat.group(1)
                        if optional and product.dir == "none":
                            productDir = None
                        else:
                            productDir = product.dir
                        
                        if productDir:
                            value = re.sub(r"\$\??{PRODUCT_DIR}", productDir, value)
                        else:
                            if not optional and not quiet:
                                print >> sys.stderr, "Unable to expand PRODUCT_DIR in %s" % self.file
                    #
                    # Be nice; they should say PRODUCT_DIR but sometimes PRODUCT is spelled out, e.g. EUPS_DIR
                    #
                    regexp = r"\${%s}" % utils.dirEnvNameFor(product.name)
                    if re.search(regexp, value):
                        if product.dir:
                            value = re.sub(regexp, product.dir, value)
                        else:
                            if not quiet:
                                print >> sys.stderr, "Unable to expand %s in %s" % \
                                      (self.file, utils.dirEnvNameFor(product.name))

                    if product.flavor:
                        value = re.sub(r"\${PRODUCT_FLAVOR}", product.flavor, value)
                    elif re.search(r"\${PRODUCT_FLAVOR}", value):
                        if not quiet:
                            print >> sys.stderr, "Unable to expand PRODUCT_FLAVOR in %s" % self.file

                    value = re.sub(r"\${PRODUCT_NAME}", product.name, value)
                    if re.search(r"\${PRODUCT_VERSION}", value):
                        if product.version:
                            value = re.sub(r"\${PRODUCT_VERSION}", product.version, value)
                        else:
                            if not quiet:
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
                            if not quiet:
                                print >> sys.stderr, "%s is not defined; not setting %s" % (value, a.args[0])
                            continue

                        try:
                            value = os.environ["EUPS_PATH"].split(":")[ind]
                        except IndexError:
                            if product.Eups.verbose > 0 and not quiet:
                                print >> sys.stderr, "Invalid index %d for \"%s\"; not setting %s" % \
                                      (ind, os.environ["EUPS_PATH"], a.args[0])

                    a.args[i] = value

        return self
    
    def _read(self, tableFile, addDefaultProduct):
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
        ifBlock = []
        for lineNo, line in contents:
            if False:
                print line
                continue
            #
            # Is this the start of a logical condition?
            #
            mat = re.search(r"^(?:if\s*\((.*)\)\s*{\s*|}\s*(?:(else)\s*{)?)$", line, re.IGNORECASE)
            if mat:
                if block:
                    if mat.group(2) == "else": # i.e. we saw an } else {
                        ifBlock = block
                    else:
                        if ifBlock:
                            elseBlock = block
                        else:
                            ifBlock = block
                            elseBlock = []
                            
                        self._actions += [(logical, ifBlock, elseBlock)]
                        ifBlock = []
                    block = []

                if mat.group(1) != None:
                    logical = mat.group(1)
                else:
                    if mat.group(2) == None:   # we got to }
                        logical = "True"

                continue
            #
            # Is line of the form action(...)?
            #
            mat = re.search(r'^(\w+)\s*\(([^)]*)\)', line, re.IGNORECASE)
            if mat:
                cmd = mat.group(1).lower()
                args = re.sub(r'^"(.*)"$', r'\1', mat.group(2))
                #
                # Protect \" by replacing it with "\002"
                #
                args = args.replace(r'\"', r'%c' % 2)
                #
                # Special case cmd(..., " ") by protecting " " as "\001"
                #
                args = re.sub(r',\s*"(\s)"', r'\1"%c"' % 1, args)
                #
                # Replace " " within quoted strings with \1 too
                #
                args = re.sub(r"(\"[^\"]+\")", lambda s: re.sub(" ", "\1", s.group(0)), args)

                args = filter(lambda s: s, re.split("[, ]", args))
                args = map(lambda s: re.sub(r'^"(.*)"$', r'\1', s), args) # remove quotes
                args = map(lambda s: re.sub(r'%c' % 1, r' ', s), args) # reinstate \001 as a space
                args = map(lambda s: re.sub(r'%c' % 2, r'"', s), args) # reinstate \002 as "

                try:
                    cmd = {
                        "addalias" : Action.addAlias,
                        "declareoptions" : Action.declareOptions, 
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

            extra = {}
            if cmd == Action.prodDir or cmd == Action.setupEnv:
                pass                 # the actions are always executed
            elif cmd == Action.addAlias:
                pass
            elif cmd == Action.declareOptions: 
                pass
            elif cmd == Action.setupOptional or cmd == Action.setupRequired:
                if cmd == Action.setupRequired:
                    extra["optional"] = False
                else:
                    cmd = Action.setupRequired
                    extra["optional"] = True
            elif cmd == Action.envAppend or cmd == Action.envPrepend:
                if cmd == Action.envAppend:
                    cmd = Action.envPrepend
                    extra["append"] = True
                else:
                    extra["append"] = False

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
                print >> sys.stderr, "Unrecognized line: %s at %s:%d" % (line, self.file, lineNo)
                continue

            block += [Action(tableFile, cmd, args, extra)]
        #
        # Push any remaining actions onto current logical block
        #
        if block:
            self._actions += [(logical, block, [])]
        #
        # Setup the default product, usually "toolchain"
        #
        if addDefaultProduct is not False and hooks.config.Eups.defaultProduct["name"]:
            args = [hooks.config.Eups.defaultProduct["name"]]
            if hooks.config.Eups.defaultProduct["version"]:
                args.append(hooks.config.Eups.defaultProduct["version"])
            if hooks.config.Eups.defaultProduct["tag"]:
                args.append("--tag")
                args.append(hooks.config.Eups.defaultProduct["tag"])

            self._actions += [('True',
                               [Action("implicit", "setupRequired", args,
                                       {"optional": True, "silent" : True})],
                               [])]

    def actions(self, flavor, setupType=[], verbose=0):
        """Return a list of actions for the specified flavor"""

        actions = []
        if not self._actions:
            return actions

        for logical, ifBlock, elseBlock in self._actions:
            parser = VersionParser(logical)
            parser.define("flavor", flavor)
            if setupType:
                parser.define("type", setupType)

            if parser.eval():
                actions += ifBlock
            else:
                actions += elseBlock

        if len(actions) == 0 and verbose > 1:
            msg = "Table %s has no entry for flavor %s" % (self.file, flavor)
            if setupType:
                msg += ", type " + ", ".join(setupType)
            print >> sys.stderr, msg
        return actions

    def __str__(self):
        s = ""
        for logical, ifBlock, elseBlock in self._actions:
            s += "\n------------------"
            s += '\n' + str(logical)
            for a in ifBlock:
                s += '\n' + str(a)
            s += '\n else'
            for a in elseBlock:
                s += '\n' + str(a)

        return s

    _versionre = re.compile(r"(.*)\s*\[([^\]]+)\]\s*")

    def dependencies(self, Eups, eupsPathDirs=None, recursive=None, recursionDepth=0, followExact=None,
                     productDictionary=None, addDefaultProduct=None):
        """
        Return the product dependencies as specified in this table as a list 
        of (Product, optional?, recursionDepth) tuples

        @param Eups            an Eups instance to use to locate packages
        @param eupsPathDirs    the product stacks to restrict searches to
        @param recursive       if True, this function will be called 
                                  recursively on each of the dependency 
                                  products in this table.
        @param followExact     follow the exact, as-built versions in the 
                                  table file.  If None or not specified,
                                  it defaults to Eups.exact_version.
        @param productDictionary add each product as a member of this dictionary (if non-NULL) and with the
                               value being that product's dependencies as a list of
                               (Product, optional? recursionDepth)
        @param addDefaultProduct If not False add the defaultProduct to any table file
        """

        if followExact is None:
            followExact = Eups.exact_version

        setupType = Eups.setupType
        if not followExact:
            setupType = [t for t in setupType if t != "exact"]

        if recursive and not isinstance(recursive, bool):
            recursiveDict = recursive
        else:
            recursiveDict = {}          # dictionary of products we've analysed
        prodkey = lambda p: "%s-%s" % (p.name, p.version)

        if productDictionary is None:
            productDictionary = {}

        if not productDictionary.has_key(self.topProduct):
            productDictionary[self.topProduct] = []
            
        if addDefaultProduct is None and self.topProduct.name == hooks.config.Eups.defaultProduct["name"]:
            addDefaultProduct = False

        deps = []
        for a in self.actions(Eups.flavor, setupType=setupType):
            if a.cmd == Action.setupRequired:
                optional = a.extra["optional"]

                requestedVRO, productName, vers, versExpr, noRecursion = a.processArgs(Eups)

                Eups.pushStack("vro", requestedVRO)

                q = None
                if optional:
                    q = utils.Quiet(Eups)

                try:
                    product, vroReason = Eups.findProductFromVRO(productName, vers, versExpr)
                    if not product:
                        raise ProductNotFound(productName)

                    val = [product]
                    val.append(a.extra["optional"])
                    if recursive:
                        val.append(recursionDepth)
                    else:
                        val.append(None)
                    deps += [val]

                    if recursive and not noRecursion and not recursiveDict.has_key(prodkey(product)):
                        recursiveDict[prodkey(product)] = 1
                        deptable = product.getTable(addDefaultProduct=addDefaultProduct)
                        if deptable:
                            deps += deptable.dependencies(Eups, eupsPathDirs, recursiveDict,
                                                          recursionDepth + 1, followExact, productDictionary,
                                                          addDefaultProduct)
                        
                except (ProductNotFound, TableFileNotFound), e:
                    product = Product.Product(productName, vers) # it doesn't exist, but it's still a dep.

                    val = [product, a.extra["optional"]]
                    if recursive:
                        val.append(recursionDepth)
                    else:
                        val.append(None)
                    deps += [val]

                del q

                productDictionary[self.topProduct].append(val)

                Eups.popStack("vro")

        return deps

    def getDeclareOptions(self):
        """Return a dictionary of any declareOptions commands in the table file

        E.g. declareOptions(flavor=NULL,   name = foo) => {'flavor': 'NULL', 'name': 'foo'}
        """

        opts = {}
        for logical, ifBlock, elseBlocl in self._actions:
            if logical:
                block = ifBlock
            else:
                block = elseBlock

            for a in block:
                if a.cmd == Action.declareOptions:
                    # Get all the args merged together into a list k0 v0 k1 v1 k2 v2 ...
                    args = []
                    for opt in a.args:
                        args += re.split(r"\s*=\s*", opt)

                    args = [a for a in args if a]
                    for i in range(0, len(args) - 1, 2):
                        k, v = args[i], args[i + 1]
                        opts[k] = v

        return opts

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Action(object):
    """
    An action in a table file

    Action instances are typically created internally by a Table constructor.
    """

    # Possible actions; the comments apply to the field that _read adds to an Action: (cmd, args, extra)
    addAlias = "addAlias"
    declareOptions = "declareOptions"
    envAppend = "envAppend"             # not used
    envPrepend = "envPrepend"           # extra: "append"
    envRemove = "envRemove"             # not supported
    envSet = "envSet"
    envUnset = "envUnset"               # not supported
    prodDir = "prodDir"
    setupEnv = "setupEnv"
    setupOptional = "setupOptional"     # not used
    setupRequired = "setupRequired"     # extra: "optional"
    sourceRequired = "sourceRequired"   # not supported

    def __init__(self, tableFile, cmd, args, extra):
        """
        Create the Action.
        @param tableFile  the parent tableFile; used in user messages
        @param cmd      the name of the command (as it appears in the table file
                          command line)
        @param args     the list of arguments passed to the command as 
                          instantiated in a table file.
        @param extra    dictionary of extra, command-specific data passed by the parser to 
                          control the execution of the command.  
        """
        self.tableFile = tableFile
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
        elif self.cmd == Action.declareOptions: 
            pass                        # used at declare time 
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

    def processArgs(self, Eups, fwd=True):
        """Process the arguments in a setup command found in a table file"""

        optional = self.extra["optional"]

        if optional:
            cmdStr = "setupOptional"    # name of this command, used in diagnostics
        else:
            cmdStr = "setupRequired"

        _args = self.args; args = []
        i = -1

        requestedFlavor = None; requestedBuildType = None; noRecursion = False; requestedTag = None
        requestedVRO = None
        ignoredOpts = []
        while i < len(_args) - 1:
            i += 1
            if re.search(r"^-", _args[i]):
                if _args[i] in ("-f", "--flavor"): # a flavor specification
                    requestedFlavor = _args[i + 1]
                    i += 1              # skip the argument
                elif _args[i] in ("-j", "--just"):  # setup just this product
                    noRecursion = True
                elif _args[i] == "-T":  # e.g. -T build
                    requestedBuildType = _args[i + 1]
                    i += 1              # skip the argument
                elif _args[i] in ("-t", "--tag"): # e.g. -t current
                    requestedTag = _args[i + 1]
                    i += 1              # skip the argument
                elif _args[i] in ("--vro"): # e.g. --vro version
                    requestedVRO = _args[i + 1]
                    i += 1              # skip the argument
                else:
                    ignoredOpts.append(_args[i]) 

                continue

            args += [_args[i]]

        productName = args[0]

        vers = None
        if not fwd:                     # unsetup
            product = Eups.findSetupProduct(productName)
            if product:
                vers = product.version
        elif Eups.ignore_versions:
            vers = None                 # Setting and then ignoring vers generates confusing error messages
        elif len(args) > 1:
            vers = " ".join(args[1:])

        if ignoredOpts:
            if Eups.verbose > 0: 
                print >> sys.stderr, "Ignoring options %s for %s %s" % \
                      (" ".join(ignoredOpts), productName, vers) 

        if fwd and requestedFlavor and requestedFlavor != Eups.flavor:
            print >> sys.stderr, "Ignoring --flavor option in \"%s(%s)\"" % (cmdStr, " ".join(_args))


        versExpr = None                 # relational expression for version
        if vers:  
            # see if a version of the form "exact [logical]"
            mat = re.search(r"(?:(\S*)\s+)?\[([^\]]+)\]\s*", vers)
            if mat:
                vers, versExpr = mat.groups()

        if not fwd:
            requestedTag = None         # ignore if not setting up

        if requestedTag and vers:
            print >> sys.stderr, "You specified version \"%s\" and tag \"%s\"; ignoring the latter" % \
                  (vers, requestedTag)
            requestedTag = None

        if requestedTag and requestedVRO:
            print >> sys.stderr, "You specified vro \"%s\" and tag \"%s\"; ignoring the latter" % \
                  (requestedVRO, requestedTag)
            requestedTag = None

        if requestedTag:
            try:
                Eups.tags.getTag(requestedTag)
            except TagNotRecognized, e:
                print >> sys.stderr, "%s in \"%s(%s)\"" % (e, cmdStr, " ".join(_args))
                requestedTag = None

        vro = Eups.getPreferredTags()
        if requestedVRO:
            pass
        elif requestedTag:
            requestedVRO = [requestedTag] + vro
        else:
            requestedVRO = vro

        return requestedVRO, productName, vers, versExpr, noRecursion

    #
    # Here are the real execute routines
    #
    def execute_setupRequired(self, Eups, recursionDepth, fwd=True):
        """Execute setupRequired"""

        optional = self.extra["optional"]
        silent = self.extra.get("silent", False)

        requestedVRO, productName, vers, versExpr, noRecursion = self.processArgs(Eups, fwd)

        Eups.pushStack("env")
        Eups.pushStack("vro", requestedVRO)
                
        q = None
        if optional:
            q = utils.Quiet(Eups)

        try:
            productOK, vers, reason = \
                       Eups.setup(productName, vers, fwd, recursionDepth, noRecursion=noRecursion,
                                  versionExpr=versExpr, optional=optional)
        except Exception, e:
            productOK, reason = False, e

        del q

        Eups.popStack("vro")

        if productOK:                   # clean up the stack, dropping the value we pushed
            Eups.dropStack("env")       # forget the value we just pushed
        else:
            Eups.popStack("env")
            if fwd:
                if optional:
                    if Eups.verbose and not silent:
                        msg = "... optional setup %s failed" % (productName)
                        if Eups.verbose > 1:
                            msg += ": %s" % reason
                        print >> sys.stderr, "            %s%s" % (recursionDepth*" ", msg)
                else:
                    if isinstance(reason, str):
                        utils.debug("reason is a str", reason)

                    reason.msg = "in file %s: %s" % (self.tableFile, reason)
                    raise reason

    def execute_envPrepend(self, Eups, fwd=True):
        """Execute envPrepend"""

        args = self.args
        append = self.extra["append"]

        envVar = args[0]                # environment variable to set
        value = args[1]                 # add/subtract this value to the variable
        if len(args) > 2:
            delim = args[2]
        else:
            delim = ":"

        opath = os.environ.get(envVar, "") # old value of envVar, generally a path of some sort hence the name

        # should we prepend an extra :?
        pat = "^" + delim
        prepend_delim = re.search(pat, value)
        value = re.sub(pat, "", value)
        # should we append an extra :?
        pat = delim + "$"
        append_delim = re.search(pat, value)
        value = re.sub(pat, "", value)

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

        if delim in value:
            msg = "In %s value \"%s\" contains a delimiter '%s'" % (self.tableFile, value, delim)
            raise BadTableContent(self.tableFile, msg=msg)

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
        if Eups.force and Eups.oldAliases.has_key(key):
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

        if Eups.force and Eups.oldEnviron.has_key(key):
            del Eups.oldEnviron[key]

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

        if version and Eups.isLegalRelativeVersion(version):
            if logical:                 # how did this happen? Version is logical and also a [logical]
                print >> sys.stderr, "Two logical expressions are present in %s; using first" % original
                
            logical = " ".join([version] + words)
            version = None

        version = productList.get(productName, version) # accept the explicit version if provided

        if version:
            product = None
        else:
            product = Eups.findSetupProduct(productName)
            if product:
                version = product.version
            if not version:
                if cmd == "setupRequired":
                    print >> sys.stderr, "Failed to find setup version of", productName
                return original     # it must not have been setup

        if logical:
            if not Eups.version_match(version, logical):
                print >> sys.stderr, "Warning: %s %s failed to match condition \"%s\"" % (productName, version, logical)
        else:
            if product and version and not re.search("^" + product.LocalVersionPrefix, version):
                logical = ">= %s" % version

        args = [productName] + flags
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
    # Read the input and split it into "blocks" which are either all setup commands, or all
    # some other sort of command.
    #
    products = []                       # all the (top-level) products that we're setting up

    setupBlocks = []                    # sets of contiguous setup commands
    block = [False, []]                 # [isSetupBlock, [current set of contiguous commands]]
    setupBlocks.append(block)

    lastSetupBlock = None               # index of the _last_ block of setups

    for line in ifd:
        if re.search(r"^\s*(#.*)?$", line):
            block[1].append(line)
            continue

        # Attempt substitutions
        rex = r'(setupRequired|setupOptional)\("?([^"]*)"?\)'

        line = re.sub(rex, subSetup, line)

        mat = re.search(rex, line)
        if mat:                         # still in same setup block
            if not block[0]:
                block = [True, []]
                setupBlocks.append(block)
                lastSetupBlock = len(setupBlocks) - 1

            args = mat.group(2)
            if args:
                products.append((args.split(" ")[0], mat.group(1) == "setupOptional"))
        else:
            if block[0]:
                block = [False, []]
                setupBlocks.append(block)

        if not re.search(r"^\s*}", line):
            block[1].append(line)
    #
    # Figure out the complete list of products that this table file will setup; only list each once
    #
    # Note that these are the complete dependencies of all the products in the table file, but with
    # the versions that are currently setup
    #
    desiredProducts = []
    for productName, optional in products:
        NVL = []
        if productList.has_key(productName):
            NVL.append((productName, productList[productName], None))
        else:
            try:
                NVL.append((productName, eups.getSetupVersion(productName), None))
            except ProductNotFound:
                if not optional:
                    raise
                    
        try:
            NVL += eups.getDependencies(productName, None, Eups, setup=True, shouldRaise=True)
        except:
            if not optional:
                raise

        for name, version, level in NVL:
            if re.search("^" + Product.Product.LocalVersionPrefix, version):
                print >> sys.stderr, "Warning: exact product specification \"%s %s\" is local" % \
                      (name, version)

            key = (name, version)
            if desiredProducts.count(key) == 0:
                desiredProducts.append(key)
    #
    # Generate the outputs.  We want to replace the _last_ setups block by an if (type == exact) { } else { }
    # block;  actually we could do this line by line but that'd make an unreadable table file
    #
    indent = "   "
    i = 0
    while i < len(setupBlocks):
        isSetupBlock, block = setupBlocks[i]
        
        if not isSetupBlock:
            if len(block) == 1 and re.search(r"if\s*\(type\s*==\s*exact\)\s*{", block[0]):
                # We've found a pre-existing exact block
                # This is FRAGILE!!  Should count forward past matching braces
                i += 3
                setupBlocks[i - 1] = (False, []) # the closing "}"
                continue
            
            for line in block:
                print >> ofd, line,
        else:
            if i == lastSetupBlock:
                print >> ofd, "if (type == exact) {"

                for n, v in desiredProducts:
                    print >> ofd, "%ssetupRequired(%-15s -j %s)" % (indent, n, v)

                print >> ofd, "} else {"
            else:
                print >> ofd, "if (type != exact) {"

            needCloseBrace = True
            for j in range(len(block)):
                line = block[j].strip()
                if j == len(block) - 1: # this is just cosmetics in the generated file
                    if not line:
                        print >> ofd, "}\n"
                        needCloseBrace = False
                        break
                print >> ofd, indent + line

            if needCloseBrace:
                print >> ofd, "}"

        i += 1
    #
    # Now write a block that fully specifies all the required products
    #

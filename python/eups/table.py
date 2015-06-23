#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import os
import re, sys

import eups
from exceptions import BadTableContent, TableError, TableFileNotFound, ProductNotFound
import Product
from tags       import TagNotRecognized
from VersionParser import VersionParser
import utils
import hooks

class Table(object):
    """A class that represents a eups table file"""

    def __init__(self, tableFile, topProduct=None, addDefaultProduct=None, verbose=0):
        """
        Parse a tablefile
        @param  tableFile          the tablefile we're reading
        @param  topProduct         the Product that owns this tablefile
        @param  addDefaultProduct  if True or None, automatically add a 
                                     "setupOptional" action for the product
                                     specified in hooks.config.Eups.defaultProduct
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
            self._read(tableFile, addDefaultProduct, verbose, topProduct)

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
                        print >> utils.stdwarn, "Ignoring qualifiers \"%s\" at %s:%d" % (mat.group(1), self.file, lineNo)
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

        for actions in self._actions: 
            for logicalOrBlock in actions:
                if not isinstance(logicalOrBlock, list): # a logical expression as a string
                    continue

                for a in logicalOrBlock:
                    for i in range(len(a.args)):
                        value = a.args[i]

                        root = product.stackRoot()
                        if root:
                            value = re.sub(r"\${PRODUCTS}", root, value)
                        elif re.search(r"\${PRODUCTS}", value):
                            if not quiet:
                                print >> utils.stderr, "Unable to expand PRODUCTS in %s" % self.file

                        mat = re.search(r"(\$(\?)?{PRODUCT_DIR(_EXTRA)?})", value)
                        if mat:
                            var = mat.group(1)
                            optional = mat.group(2)
                            extra = mat.group(3)
                            if extra:
                                newValue = product.extraProductDir()
                                if optional and not os.path.exists(newValue):
                                    newValue = None
                            else:
                                newValue = product.dir
                                if optional and newValue == "none":
                                    newValue = None

                            if newValue:
                                value = re.sub(re.sub(r"([$?.])", r"\\\1", var), newValue, value)
                            else:
                                if not optional and not quiet:
                                    print >> utils.stderr, "Unable to expand %s in %s" % (var, self.file)
                        #
                        # Be nice; they should say PRODUCT_DIR but sometimes PRODUCT is spelled out, e.g. EUPS_DIR
                        #
                        regexp = r"\${%s}" % utils.dirEnvNameFor(product.name)
                        if re.search(regexp, value):
                            if product.dir:
                                value = re.sub(regexp, product.dir, value)
                            else:
                                if not quiet:
                                    print >> utils.stdwarn, "Unable to expand %s in %s" % \
                                          (self.file, utils.dirEnvNameFor(product.name))

                        if product.flavor:
                            value = re.sub(r"\${PRODUCT_FLAVOR}", product.flavor, value)
                        elif re.search(r"\${PRODUCT_FLAVOR}", value):
                            if not quiet:
                                print >> utils.stdwarn, "Unable to expand PRODUCT_FLAVOR in %s" % self.file

                        value = re.sub(r"\${PRODUCT_NAME}", product.name, value)
                        if re.search(r"\${PRODUCT_VERSION}", value):
                            if product.version:
                                value = re.sub(r"\${PRODUCT_VERSION}", product.version, value)
                            else:
                                if not quiet:
                                    print >> utils.stdwarn, "Unable to expand PRODUCT_VERSION in %s" % self.file

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
                                    print >> utils.stdwarn, "%s is not defined; not setting %s" % (value, a.args[0])
                                continue

                            try:
                                value = os.environ["EUPS_PATH"].split(":")[ind]
                            except IndexError:
                                if product.Eups.verbose > 0 and not quiet:
                                    print >> utils.stderr, "Invalid index %d for \"%s\"; not setting %s" % \
                                          (ind, os.environ["EUPS_PATH"], a.args[0])

                        a.args[i] = value

        return self
    
    def _read(self, tableFile, addDefaultProduct, verbose=0, topProduct=None):
        """Read and parse a table file, setting _actions"""

        if not tableFile:               # nothing to do
            return

        try:
            fd = file(tableFile)
        except IOError, e:
            raise TableError(tableFile, msg=str(e))

        contents = fd.readlines()
        contents = self._rewrite(contents)

        logical = "True"                # logical condition required to execute block
        block = []
        ifBlock = []
        logicalBlocks = []              # list of [logical1, action1, (logical2, action2)*, actionN]
                                        # corresponding to
                                        # if(logical1) {
                                        #    action1
                                        # } else if(logical2} {
                                        #    action2
                                        # } else {
                                        #    actionN
                                        # }
        for lineNo, line in contents:
            #
            # Is this the start of a logical condition?
            #
            mat = re.search(r"^(?:if\s*\((.*)\)\s*{\s*|}\s*(?:(else(?:\s*if\s*\((.*)\))?)\s*{)?)$", \
                                line, re.IGNORECASE)
            if mat:
                if block:
                    if mat.group(2) == "else": # i.e. we saw an } else {
                        ifBlock = block
                    elif mat.group(3) != None: # i.e. we saw an } else if (...) {
                        logicalBlocks += [logical, block,]
                        block = False
                        logical = mat.group(3)
                    else:               # we saw an }
                        if ifBlock:
                            elseBlock = block
                        else:
                            ifBlock = block
                            elseBlock = []
                            
                        logicalBlocks += [logical, ifBlock, elseBlock,]

                        if logicalBlocks and mat.group(1) != None:
                            self._actions.append(logicalBlocks)
                            ifBlock = []
                            logicalBlocks = []
                        
                    block = []

                if mat.group(1) != None:
                    logical = mat.group(1)
                else:
                    if mat.group(2) == None:   # we got to }
                        logical = "True"
                        if logicalBlocks:
                            self._actions.append(logicalBlocks)
                            ifBlock = []
                            logicalBlocks = []

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
                #
                # Replace , within quoted strings with "\003"
                #
                args = re.sub(r"(\"[^\"]+\")", lambda s: re.sub(",", "%c" % 3, s.group(0)), args)

                args = filter(lambda s: s, re.split("[, ]", args))
                args = map(lambda s: re.sub(r'^"(.*)"$', r'\1', s), args) # remove quotes
                args = map(lambda s: re.sub(r'%c' % 1, r' ', s), args) # reinstate \001 as a space
                args = map(lambda s: re.sub(r'%c' % 2, r'"', s), args) # reinstate \002 as "
                args = map(lambda s: re.sub(r'%c' % 3, r',', s), args) # reinstate \003 as ,

                try:
                    cmd = {
                        "addalias" : Action.addAlias,
                        "declareoptions" : Action.declareOptions, 
                        "envappend" : Action.envAppend,
                        "envprepend" : Action.envPrepend,
                        "envset" : Action.envSet,
                        "envunset" : Action.envUnset,
                        "pathappend" : Action.envAppend,
                        "pathprepend" : Action.envPrepend,
                        "pathremove" : Action.envUnset,
                        "pathset" : Action.envSet,
                        "print" : Action.doPrint,
                        "proddir" : Action.prodDir,
                        "setupenv" : Action.setupEnv,
                        "setenv" : Action.envSet,
                        "unsetenv" : Action.envUnset,
                        "setuprequired" : Action.setupRequired,
                        "setupoptional" : Action.setupOptional,
                        "sourcerequired" : Action.sourceRequired,
                        "unsetuprequired" : Action.unsetupRequired,
                        "unsetupoptional" : Action.unsetupOptional,
                        }[cmd]
                except KeyError:
                    print >> utils.stderr, "Unexpected line in %s:%d: %s" % (tableFile, lineNo, line)
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
            elif cmd == Action.unsetupOptional or cmd == Action.unsetupRequired:
                if cmd == Action.unsetupRequired:
                    extra["optional"] = False
                else:
                    cmd = Action.unsetupRequired
                    extra["optional"] = True
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
            elif cmd == Action.envUnset:
                if len(args) != 1:
                    msg = "%s expected 1 argument, saw %s at %s:%d" % \
                        (cmd, " ".join(args), self.file, lineNo)
                    raise BadTableContent(self.file, msg=msg)

                if self.topProduct:
                    pdirVar = utils.dirEnvNameFor(self.topProduct.name) # e.g. FOO_DIR
                else:
                    pdirVar = None

                if args[0] == "PRODUCT_DIR":
                    args[0] = pdirVar
                    
                if args[0] != pdirVar:  # only allow the unsetting of this one variable
                    if pdirVar and verbose > 0:
                        print >> utils.stdwarn, "Attempt to unset $%s at %s:%d" % (args[0], self.file, lineNo)
                    continue                
            elif cmd == Action.sourceRequired:
                print >> utils.stderr, "Ignoring unsupported directive %s at %s:%d" % (line, self.file, lineNo)
                continue
            elif cmd == Action.doPrint:
                pass
            else:
                print >> utils.stderr, "Unrecognized line: %s at %s:%d" % (line, self.file, lineNo)
                continue

            block += [Action(tableFile, cmd, args, extra, topProduct=topProduct)]
        #
        # Push any remaining actions onto current logical block
        #
        if logicalBlocks:
            self._actions.append(logicalBlocks)
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

        for LBB in self._actions:       # LBB: Logical Block Block[s]
            while LBB:
                logical, ifBlock, elseBlock = LBB[0], LBB[1], LBB[2:]
                parser = VersionParser(logical)
                parser.define("flavor", flavor)
                if setupType:
                    parser.define("type", setupType)

                if parser.eval():
                    actions += ifBlock
                    break
                else:
                    if len(elseBlock) == 1: # just a block
                        actions += elseBlock[0]
                        LBB = None
                    else:
                        LBB = elseBlock # another Logical Block Block[s]

        if len(actions) == 0 and verbose > 1:
            msg = "Table %s has no entry for flavor %s" % (self.file, flavor)
            if setupType:
                msg += ", type " + ", ".join(setupType)
            print >> utils.stdinfo, msg
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

    def dependencies(self, Eups=None, eupsPathDirs=None, recursive=None, recursionDepth=0, followExact=None,
                     productDictionary=None, addDefaultProduct=None, requiredVersions={}):
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
        @param requiredVersions  Dict with version required for products
        """

        if Eups is None:
            Eups = eups.Eups()

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
            
        if addDefaultProduct is None and \
               self.topProduct and self.topProduct.name == hooks.config.Eups.defaultProduct["name"]:
            addDefaultProduct = False

        deps = []
        for a in self.actions(Eups.flavor, setupType=setupType):
            if a.cmd == Action.unsetupRequired:
                if True:
                    optional = a.extra["optional"]
                      
                    requestedVRO, productName, productDir, vers, versExpr, noRecursion = a.processArgs(Eups)
                    #
                    # Remove all mention of the unsetup product
                    #
                    try:
                        thisProduct = [val for val in deps if val[0].name == productName][0][0]
                    except IndexError:
                        continue
                    table = thisProduct.getTable()

                    unsetupProducts = [thisProduct.name]
                    if table and not noRecursion:
                        subDeps = table.dependencies(Eups, eupsPathDirs=eupsPathDirs,
                                                    recursive=True, followExact=followExact)
                        unsetupProducts += [val[0].name for val in subDeps]

                    for pn in unsetupProducts:
                        for i in reversed(sorted([i for i, val in enumerate(deps) if val[0].name == pn])):
                            del deps[i]
                        
            elif a.cmd == Action.setupRequired:
                optional = a.extra["optional"]
                if addDefaultProduct is False and a.tableFile == "implicit":
                    continue

                requestedVRO, productName, productDir, vers, versExpr, noRecursion = a.processArgs(Eups)

                Eups.pushStack("vro", requestedVRO)

                q = None
                if optional:
                    q = utils.Quiet(Eups)

                try:
                    if requiredVersions and productName in requiredVersions:
                        product = Eups.findProduct(productName, requiredVersions[productName])
                    else:
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
                                                          addDefaultProduct, requiredVersions=requiredVersions)
                        
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

    def getDeclareOptions(self, flavor, setupType):
        """Return a dictionary of any declareOptions commands in the table file

        E.g. declareOptions(flavor=NULL,   name = foo) => {'flavor': 'NULL', 'name': 'foo'}
        """

        opts = {}
        for LBB in self._actions:
            while LBB:                  # LBB: Logical Block Block[s]
                logical, ifBlock, elseBlock = LBB[0], LBB[1], LBB[2:]

                if len(elseBlock) > 13:
                    print "Oh dear. Please type w at the pdb prompt and notify rhl@astro.princeton.edu"
                    import pdb; pdb.set_trace() 

                parser = VersionParser(logical)
                parser.define("flavor", flavor)
                if setupType:
                    parser.define("type", setupType)

                if parser.eval():
                    block = ifBlock
                    LBB = None
                else:
                    if len(elseBlock) == 1: # just a block
                        block = elseBlock[0]
                        LBB = None
                    else:
                        LBB = elseBlock # another Logical Block Block[s]
                        continue

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
    envSet = "envSet"
    envUnset = "envUnset"               # not supported
    prodDir = "prodDir"
    doPrint = "print"
    setupEnv = "setupEnv"
    setupOptional = "setupOptional"     # not used
    setupRequired = "setupRequired"     # extra: "optional"
    unsetupOptional = "unsetupOptional" # not used
    unsetupRequired = "unsetupRequired" # extra: "optional"
    sourceRequired = "sourceRequired"   # not supported

    def __init__(self, tableFile, cmd, args, extra, topProduct=None):
        """
        Create the Action.
        @param tableFile  the parent tableFile; used in user messages
        @param cmd      the name of the command (as it appears in the table file
                          command line)
        @param args     the list of arguments passed to the command as 
                          instantiated in a table file.
        @param extra    dictionary of extra, command-specific data passed by the parser to 
                          control the execution of the command.
        @param topProduct The top-level Product that we're setting up
        """
        self.tableFile = tableFile
        try:
            i = args.index("-f")
            del args[i:i+2]
        except ValueError:
            pass

        self.args = args
        self.extra = extra
        self.topProduct = topProduct

        self.cmd = cmd
        self.cmdName = cmd              # used only for diagnostics
        if self.cmdName in ("setupRequired", "unsetupRequired",) and self.extra.get("optional"):
            self.cmdName = re.sub("Required", "Optional", self.cmdName)

    def __str__(self):
        return "%s %s %s" % (self.cmd, self.args, self.extra)

    def execute(self, Eups, recursionDepth, fwd=True, noRecursion=False, tableProduct=None,
                implicitProduct=False):
        """Execute an action"""

        if self.cmd == Action.setupRequired:
            if noRecursion or recursionDepth == Eups.max_depth + 1:
                return

            self.execute_setupRequired(Eups, recursionDepth, fwd, tableProduct, implicitProduct)
        elif self.cmd == Action.unsetupRequired:
            if noRecursion or recursionDepth == Eups.max_depth + 1:
                return

            self.execute_unsetupRequired(Eups, recursionDepth, fwd, tableProduct)
        elif self.cmd == Action.declareOptions: 
            pass                        # used at declare time 
        elif self.cmd == Action.envPrepend:
            self.execute_envPrepend(Eups, fwd)
        elif self.cmd == Action.envSet:
            self.execute_envSet(Eups, fwd)
        elif self.cmd == Action.envUnset:
            self.execute_envUnset(Eups, fwd)
        elif self.cmd == Action.addAlias:
            self.execute_addAlias(Eups, fwd)
        elif self.cmd == Action.prodDir or self.cmd == Action.setupEnv:
            pass
        elif self.cmd == Action.doPrint: 
            self.execute_print(Eups, fwd)
        else:
            print >> utils.stderr, "Unimplemented action", self.cmd

    def processArgs(self, Eups, fwd=True):
        """Process the arguments in a setup command found in a table file"""

        _args = self.args; args = []
        i = -1

        requestedFlavor = None; requestedBuildType = None; noRecursion = False; requestedTags = []
        productDir = False; keep = False; requestedVRO = None
        ignoredOpts = []
        while i < len(_args) - 1:
            i += 1
            if re.search(r"^-", _args[i]):
                if _args[i] in ("-f", "--flavor"): # a flavor specification
                    requestedFlavor = _args[i + 1]
                    i += 1              # skip the argument
                elif _args[i] in ("-j", "--just"):  # setup just this product
                    noRecursion = True
                elif _args[i] in ("-k", "--keep"):  # keep already-setup versions of this product
                    keep = True
                elif _args[i] == "-r":  # e.g. -r productDir
                    productDir = _args[i + 1]
                    i += 1              # skip the argument
                elif _args[i] == "-T":  # e.g. -T build
                    requestedBuildType = _args[i + 1]
                    i += 1              # skip the argument
                elif _args[i] in ("-t", "--tag"): # e.g. -t current
                    requestedTags.append(_args[i + 1])
                    i += 1              # skip the argument
                elif _args[i] in ("--vro"): # e.g. --vro version
                    requestedVRO = _args[i + 1]
                    i += 1              # skip the argument
                else:
                    ignoredOpts.append(_args[i]) 

                continue

            args += [_args[i]]

        if args:
            productName = args.pop(0)
        else:
            productName = None

        if productDir:
            productDir = os.path.expanduser(self.expandEnvironmentalVariable(productDir, Eups.verbose))
            if not os.path.isabs(productDir):
                if self.topProduct:
                    toplevelDir = self.topProduct.dir
                else:
                    toplevelDir = "."
                if (fwd and Eups.verbose > 0) or Eups.verbose > 1:
                    print >> utils.stdwarn, "Interpreting directory %s relative to %s in %s" % \
                        (productDir, toplevelDir, self.tableFile)

                productDir = os.path.join(toplevelDir, productDir)

            productDir = os.path.abspath(productDir)
            productName = utils.guessProduct(os.path.join(productDir, "ups"), productName)

        vers = None
        if not fwd:                     # unsetup
            product = Eups.findSetupProduct(productName)
            if product:
                vers = product.version
        elif Eups.ignore_versions:
            vers = None                 # Setting and then ignoring vers generates confusing error messages
        elif args:
            vers = " ".join(args)

        if ignoredOpts:
            if fwd or Eups.verbose > 1: 
                print >> utils.stdwarn, "Ignoring options %s for %s %s" % \
                      (" ".join(ignoredOpts), productName, vers) 

        if fwd and requestedFlavor and requestedFlavor != Eups.flavor:
            print >> utils.stdwarn, "Ignoring --flavor option in \"%s(%s)\"" % (self.cmdName, " ".join(_args))


        versExpr = None                 # relational expression for version
        if vers:  
            # see if a version of the form "exact [logical]"
            mat = re.search(r"(?:(\S*)\s+)?\[([^\]]+)\]\s*", vers)
            if mat:
                vers, versExpr = mat.groups()

        if not fwd:
            requestedTag = []           # ignore if not setting up

        vro = Eups.getPreferredTags()

        if requestedVRO:
            if keep:
                if fwd:
                    if Eups.verbose > 0:
                        extraText = " in %s" % self.tableFile 
                    else:
                        extraText = ""

                    print >> utils.stdwarn, \
                        "You specified vro \"%s\" and --keep for %s%s; ignoring the latter" % \
                        (requestedVRO, productName, extraText)
                keep = False

            if requestedVRO == "version!":
                if "keep" in vro:
                    if fwd and Eups.verbose > 0:
                        if Eups.verbose > 1:
                            extraText = " in %s" % self.tableFile
                        else:
                            extraText = ""

                        print >> utils.stdinfo, \
                            "You are setting up --keep and specifying %s --vro \"%s\"%s. Ignoring --keep" % \
                            (productName, requestedVRO, extraText)
            else:
                keep = "keep" in vro
        elif not keep:
            keep = "keep" in vro

        if requestedTags and requestedVRO:
            print >> utils.stdinfo, "You specified vro \"%s\" and tag[s] \"%s\"; ignoring the latter" % \
                  (requestedVRO, "\", \"".join(requestedTags))
            requestedTags = []

        if requestedTags:
            tags = []
            for tag in requestedTags:
                try:
                    Eups.tags.getTag(tag)
                    tags.append(tag)
                except TagNotRecognized, e:
                    print >> utils.stdwarn, "%s in \"%s(%s)\"" % (e, self.cmdName, " ".join(_args))

            requestedTags = tags

        if requestedVRO:
            requestedVRO = requestedVRO.split()
        elif requestedTags:
            requestedVRO = requestedTags + vro
        else:
            requestedVRO = vro

        if keep:
            requestedVRO[0:0] = ["keep"]

        if not productName:
            raise RuntimeError("I was unable to find a product specification in \"%s\"" % " ".join(_args))

        return requestedVRO, productName, productDir, vers, versExpr, noRecursion

    def expandEnvironmentalVariable(self, value, verbose=0):
        # look for values that are optional environment variables: ${XXX} or $?{XXX}
        # If desired, specify a default value as e.g. ${XXX-value}
        # if they don't exist, ignore the entire line if marked optional; raise an error otherwise
        varRE = r"\$(\?)?{([^-}]*)(?:-([^}]+))?}"
        mat = re.search(varRE, value)
        if not mat:
            return value
        
        optional, key, default = mat.groups()

        if os.environ.has_key(key):
            return re.sub(varRE, os.environ[key], value)
        elif default:
            return re.sub(varRE, default, value)

        if optional:
            if verbose > 0:
                print >> utils.stdinfo, "$%s is not defined; skipping line containing %s" % (key, value)

            return None
        else:
            raise RuntimeError("$%s is not defined; unable to expand %s" % (key, value))           

    #
    # Here are the real execute routines
    #
    def execute_setupRequired(self, Eups, recursionDepth, fwd=True, tableProduct=None, implicitProduct=False):
        """Execute setupRequired"""

        optional = self.extra["optional"]
        silent = self.extra.get("silent", False)

        requestedVRO, productName, productDir, vers, versExpr, noRecursion = \
            self.processArgs(Eups, fwd)
        if productDir:
            productDir = self.expandEnvironmentalVariable(productDir, Eups.verbose)
            if productDir is None:
                return

        Eups.pushStack("env")
        Eups.pushStack("vro", requestedVRO)
                
        q = None
        if optional:
            q = utils.Quiet(Eups)

        try:
            productOK, vers, reason = \
                       Eups.setup(productName, vers, fwd, recursionDepth, noRecursion=noRecursion,
                                  versionExpr=versExpr, productRoot=productDir, optional=optional,
                                  implicitProduct=implicitProduct)
        except Exception, e:
            productOK, reason = False, e

        del q

        Eups.popStack("vro")

        if productOK:                   # clean up the stack, dropping the value we saved
            Eups.dropStack("env")       # (and thus accepting the values that setup set)
        else:
            Eups.popStack("env")
            if fwd:
                if optional:
                    if Eups.verbose and not silent:
                        msg = "... optional setup %s" % (productName)
                        if tableProduct:
                            msg += " requested by %s" % tableProduct.name
                            if tableProduct.version is not None:
                                msg += " %s" % tableProduct.version
                        msg += " failed"
                        if Eups.verbose > 1:
                            msg += ": %s" % reason
                        print >> utils.stdinfo, "            %s%s" % (recursionDepth*" ", msg)
                else:
                    if isinstance(reason, str):
                        utils.debug("reason is a str", reason)

                    reason.msg = "in file %s: %s" % (self.tableFile, reason)
                    raise reason

    def execute_unsetupRequired(self, Eups, recursionDepth, fwd, tableProduct=None):
        """Execute unsetupRequired"""

        if not fwd:
            return

        optional = self.extra["optional"]
        silent = self.extra.get("silent", False)

        requestedVRO, productName, productDir, vers, versExpr, noRecursion = self.processArgs(Eups, fwd=False)

        Eups.pushStack("env")
        Eups.pushStack("verbose")
        Eups.verboseUnsetup = Eups.verbose

        try:
            productOK, vers, reason = Eups.unsetup(productName, vers, recursionDepth,
                                                   noRecursion=noRecursion, optional=optional)
                                                   
        except Exception, e:
            productOK, reason = False, e

        Eups.popStack("verbose")

        if productOK:                   # clean up the stack, dropping the value we saved
            Eups.dropStack("env")       # (and thus accepting the changes that unsetup made)
        else:
            Eups.popStack("env")
            if fwd:
                if optional:
                    if Eups.verbose and not silent:
                        msg = "... optional unsetup %s" % (productName)
                        if tableProduct:
                            msg += " requested by %s" % tableProduct.name
                            if tableProduct.version is not None:
                                msg += " %s" % tableProduct.version
                        msg += " failed"
                        if Eups.verbose > 1:
                            msg += ": %s" % reason
                        print >> utils.stdinfo, "            %s%s" % (recursionDepth*" ", msg)
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
            value = self.expandEnvironmentalVariable(value, Eups.verbose)
            if value is None:
                return

        if delim in value:
            if Eups.verbose > 1:
                print >> utils.stdwarn, \
                    "In %s value \"%s\" contains a delimiter '%s'" % (self.tableFile, value, delim)

        npath = opath
        for value in value.split(delim):
            if fwd:
                if append:
                    npath = npath + [value]
                else:
                    npath = [value] + npath
            else:
                npath = filter(lambda d: d != value, npath)

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
            value = self.expandEnvironmentalVariable(value, Eups.verbose)
            if not value:
                return

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

    def execute_print(self, Eups, fwd=True):
        """Execute print"""

        if not fwd:
            return                      # Only generate messages on setup, not unsetup

        args = self.args
        if args[0].lower() in ("stdout", "stderr", "stdwarn", "stdinfo"):
            dest = args[0].lower(); args = args[1:]
        else:
            dest = "stdout"

        if dest == "stderr":
            dest = utils.stderr
        elif dest in ("stdout", "stdok"):
            dest = utils.stdok
        elif dest == "stdwarn":
            dest = utils.stdwarn
        elif dest == "stdinfo":
            dest = utils.stdinfo
        else:
            raise RuntimeError("Impossible destination: %s" % dest)

        print >> dest, " ".join(args)
        
    def execute_envUnset(self, Eups, fwd=True):
        """Execute envUnset"""

        if not fwd:
            return                      # we don't know how to reset a value. Sorry

        key = self.args[0]

        try:
            del os.environ[key]
        except KeyError:
            pass

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Expand a table file
#
def expandTableFile(Eups, ofd, ifd, productList, versionRegexp=None, force=False,
                    expandVersions=True, addExactBlock=True, toplevelName=None,
                    recurse=True):
    """Expand a table file, reading from ifd and writing to ofd
    If force is true, missing required dependencies are converted to optional
    """
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
                print >> utils.stderr, "I don't know how to process %s" % a
            elif re.search(r"^-", a):
                print >> utils.stderr, "Unknown setup flag %s" % a
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
            print >> utils.stderr, "I cannot find a product in %s; passing through unchanged" % original
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
                print >> utils.stdwarn, "Two logical expressions are present in %s; using first" % original
                
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
                    print >> utils.stdwarn, "Failed to find setup version of", productName
                return original     # it must not have been setup

        if logical:
            if not Eups.version_match(version, logical):
                print >> utils.stdwarn, "Warning: %s %s failed to match condition \"%s\"" % (productName, version, logical)
        else:
            if product and version and not re.search("^" + product.LocalVersionPrefix, version):
                logical = ">= %s" % version

        args = [productName] + flags
        if version:
            args += [version]
            if versionRegexp and not re.search(versionRegexp, version):
                print >> utils.stdwarn, "Suspicious version for %s: %s" % (productName, version)
        #
        # Here's where we record the logical expression, if provided
        #
        if expandVersions and logical:
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
        line = re.sub(r"\s*#.*$", "", line) # strip comments running to the end of the line

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

        block[1].append(line)
    #
    # Figure out the complete list of products that this table file will setup; only list each once
    #
    # Note that these are the complete dependencies of all the products in the table file, but with
    # the versions that are currently setup.
    #
    desiredProducts = []
    optionalProducts = {}
    notFound = {}
    for productName, optional in products:
        if productName == toplevelName:
            continue                    # Don't include product foo in foo.table

        NVOL = []
        version = None
        if productList.has_key(productName):
            version = productList[productName]
        else:
            try:
                version = eups.getSetupVersion(productName, eupsenv=Eups)
            except ProductNotFound:
                notFound[productName] = True
                if not optional:
                    if not force:
                        raise
                continue

        NVOL.append((productName, version, optional, None))

        if recurse:
            try:
                NVOL += eups.getDependencies(productName, version, Eups, setup=True, shouldRaise=True)
            except:
                if not optional:
                    if not force:
                        raise
                continue

        for name, version, opt, level in NVOL:
            if re.search("^" + Product.Product.LocalVersionPrefix, version):
                print >> utils.stdwarn, "Warning: exact product specification \"%s %s\" is local" % \
                      (name, version)

            key = (name, version)
            if desiredProducts.count(key) == 0:
                desiredProducts.append(key)
                if opt:
                    optionalProducts[key] = True
    #
    # Generate the outputs.  We want to replace the _last_ setups block by an if (type == exact) { } else { }
    # block;  actually we could do this line by line but that'd make an unreadable table file
    #
    def output(ofd, indentLevel, line):
        print >> ofd, "%s%s" % (indentLevel*indent, line.strip())

    indentLevel = 0
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

            if len(block) >= 1 and re.search(r"{\s*$", block[0]):
                output(ofd, indentLevel, block[0])
                indentLevel += 1
                block.pop(0)
            elif len(block) >= 1 and re.search(r"^\s*}\s*$", block[0]):
                indentLevel -= 1
                output(ofd, indentLevel, block[0])
                block.pop(0)

            for line in block:
                output(ofd, indentLevel, line)
        else:
            if addExactBlock:
                indentedBlock = True
                if i == lastSetupBlock:
                    output(ofd, indentLevel, "if (type == exact) {")
                    indentLevel += 1

                    for n, v in desiredProducts:
                        if optionalProducts.get((n, v)) or notFound.get(n):
                            cmd = "setupOptional"
                        else:
                            cmd = "setupRequired"

                        output(ofd, indentLevel, "%s(%-15s -j %s)" % (cmd, n, v))

                    output(ofd, indentLevel - 1, "} else {")
                else:
                    output(ofd, indentLevel, "if (type != exact) {")
                    indentLevel += 1
            else:
                indentedBlock = False

            for j in range(len(block)):
                line = block[j].strip()
                if j == len(block) - 1: # this is just cosmetics in the generated file
                    if not line and indentLevel > 0:
                        break
                    
                output(ofd, indentLevel, line)

            if indentedBlock:
                indentLevel -= 1
                output(ofd, indentLevel, "}")

        i += 1

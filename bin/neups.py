# -*- python -*-
import re, os, sys
import pdb

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Current(object):
    """A class that represents a current.chain file"""

    def __init__(self, currentFile):
        """Parse a current file"""
        
        self.file = currentFile
        self.product = None
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
                self.product = value
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
        s += "Product: %s  Chain: %s" % (self.product, self.chain)

        flavors = self.info.keys(); flavors.sort()
        for flavor in flavors:
            s += "\n------------------"
            s += "\nFlavor: %s" % flavor
            keys = self.info[flavor].keys(); keys.sort()
            for key in keys:
                s += "\n%-20s : %s" % (key, self.info[flavor][key])

        return s
    
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Table(object):
    """A class that represents a eups table file"""
    
    # Possible actions; the comments apply to the field that _read adds to its tuples: (cmd, args, extra)
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
                    conditional += "FLAVOR == %s" % mat.group(1)
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

    def _read(self, tableFile):
        """Read and parse a table file, returning a list of tuples (logical, [action, [arguments], optional])
where the actions are symbols such as Table.envAppend, e.g.
   ('envAppend', ['PYTHONPATH', '${PRODUCT_DIR}/python'], True)
"""
        fd = file(tableFile)

        contents = fd.readlines()
        contents = self._rewrite(contents)

        logical = True                  # logical condition required to execute block
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
                    logical = True
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
                args = filter(lambda s: s, re.split("[, ]", args))
                args = map(lambda s: re.sub(r'^"(.*)"$', r'\1', s), args)

                cmd = {
                    "addalias" : Table.addAlias,
                    "envappend" : Table.envAppend,
                    "envprepend" : Table.envPrepend,
                    "envset" : Table.envSet,
                    "envremove" : Table.envRemove,
                    "envunset" : Table.envUnset,
                    "pathappend" : Table.envAppend,
                    "pathprepend" : Table.envPrepend,
                    "pathset" : Table.envSet,
                    "proddir" : Table.prodDir,
                    "setupenv" : Table.setupEnv,
                    "setenv" : Table.envSet,
                    "setuprequired" : Table.setupRequired,
                    "setupoptional" : Table.setupOptional,
                    }[cmd]

            else:
                cmd = line; args = []

            extra = None
            if cmd == Table.prodDir or cmd == Table.setupEnv:
                pass                 # the actions are always executed
            elif cmd == Table.addAlias:
                pass
            elif cmd == Table.setupOptional or cmd == Table.setupRequired:
                if cmd == Table.setupRequired:
                    extra = False       # optional?
                else:
                    cmd = Table.setupRequired
                    extra = True        # optional?
            elif cmd == Table.envAppend or cmd == Table.envPrepend:
                if cmd == Table.envAppend:
                    extra = True        # append?
                else:
                    cmd = Table.envPrepend
                    extra = False       # append?
            elif cmd == Table.envSet:
                pass
            elif cmd == Table.envRemove or cmd == Table.envUnset:
                print >> sys.stderr, "Ignoring unsupported entry %s at %s:%d" % (line, self.file, lineNo)
                continue
            else:
                print >> sys.stderr, "Unrecognised line: %s at %s:%d" % (line, self.file, lineNo)
                continue

            block += [(cmd, args, extra)]
        #
        # Push any remaining actions onto current logical block
        #
        if block:
            self._actions += [(logical, block)]

    def actions(self, flavor):
        """Return a list of actions for the specified flavor"""

        for logical, block in self._actions:
            parser = Parser(logical)
            parser.define("flavor", flavor)

            if parser.eval():
                return block

        raise RuntimeError, ("Table has no entry for flavor %s" % flavor)

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
        self.product = None
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
                self.product = value
            elif key == "version":
                self.version = value
            elif key == "flavor": # Now look for flavor-specific blocks
                flavor = value
                self.info[flavor] = {}
            else:
                value = re.sub(r"^\"(.*)\"$", r"\1", mat.group(2)) # strip ""

                if key == "qualifiers":
                    if value:
                        raise RuntimeError, ("Unsupported qualifiers \"%s\" at %s:%d" % (value, self.file, lineNo))
                    else:
                        continue
                else:
                    self.info[flavor][key] = value

    def __str__(self):
        s = ""
        s += "Product: %s  Version: %s" % (self.product, self.version)

        flavors = self.info.keys(); flavors.sort()
        for flavor in flavors:
            s += "\n------------------"
            s += "\nFlavor: %s" % flavor
            keys = self.info[flavor].keys(); keys.sort()
            for key in keys:
                s += "\n%-20s : %s" % (key, self.info[flavor][key])

        return s
    
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def flavor():
    """Return the current flavor"""
    
    if os.environ.has_key("EUPS_FLAVOR"):
        return os.environ["EUPS_FLAVOR"]
    #
    # These are all the posix-defined uname options
    #
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

class Eups(object):
    """Control eups"""
    
    def __init__(self, shell, flavor=None, path=None, dbz=None, root=None, verbose=False, noaction=False):

        if not flavor:
            flavor = getFlavor()
        self.flavor = flavor

        if not path:
            path = os.environ["EUPS_PATH"]

            if isinstance(path, str):
                path = path.split(":")
                
        if dbz:
            path = filter(lambda p: re.search(r"/%s(/|$)" % dbz, p), path)

        if not path:
            if dbz:
                raise RuntimeError, ("No EUPS_PATH is defined that matches \"%s\"" % dbz)
            else:
                raise RuntimeError, ("No EUPS_PATH is defined")

        self.path = path

        self.root = root
        self.verbose = verbose
        self.noaction = noaction

        if shell != "sh" and shell != "csh":
            raise RuntimeError, ("Unknown type of shell: %s" % shell)

        self.shell = shell

    def setEnv(self, key, val):
        """Set an environmental variable"""
        
        if self.shell == "sh":
            return "export %s=%s" % (key, val)
        elif self.shell == "csh":
            return "setenv %s %s" % (key, val)

    def unsetEnv(self, key):
        """Unset an environmental variable"""
        
        if self.shell == "sh":
            return "unset %s" % (key)
        elif self.shell == "csh":
            return "unsetenv %s" % (key)

    def findVersionInfo(self, product, version):
        vinfo = None
        for product_base in self.path:
            ups_db = os.path.join(product_base, "ups_db")

            if not version:
                cfile = os.path.join(ups_db, product, "current.chain")
                if os.path.exists(cfile):
                    try:
                        version = Current(cfile).info[self.flavor]["version"]
                    except KeyError:
                        raise RuntimeError, "Product %s has no current version for flavor %s" % (product, self.flavor)

            if version:
                vfile = os.path.join(ups_db, product, "%s.version" % version)
                if os.path.exists(vfile):
                    vers = Version(vfile)
                    if vers.info.has_key(self.flavor):
                        vinfo = vers.info[self.flavor]
                        break

        if not vinfo:                       # no version is available
            raise RuntimeError, "Unable to locate %s/%s for flavor %s" % (product, version, self.flavor)

        product_dir = vinfo["prod_dir"]
        if not re.search(r"^/", product_dir):
            product_dir = os.path.join(product_base, vinfo["prod_dir"])

        if not os.path.isdir(product_dir):
            raise RuntimeError, ("Product %s/%s has non-existent product_dir %s" % (product, version, product_dir))
        #
        # Look for the directory with the tablefile
        #
        ups_dir = vinfo["ups_dir"]
        ups_dir = re.sub(r"\$PROD_DIR", product_dir, ups_dir)
        ups_dir = re.sub(r"\$UPS_DB", ups_db, ups_dir)

        tablefile = os.path.join(ups_dir, vinfo["table_file"])

        if not os.path.exists(tablefile):
            raise RuntimeError, ("Product %s/%s has non-existent tablefile %s" % (product, version, tablefile))

        return version, product_dir, tablefile

    def setup(self, indent, product, version):
        """The workhorse for setup.  Return (status, actions) where actions is a list of shell
        commands that we need to issue"""

        shellActions = []                   # actions that we need to take
        #
        # Look for product directory
        #
        try:
            version, product_dir, tablefile = self.findVersionInfo(product, version)
        except RuntimeError, e:
            if self.verbose:
                print >> sys.stderr, e

            return False, shellActions
        #
        # We have the product_dir and tablefile, along with the actual version found
        #
        table = Table(tablefile)

        if True:                        # play with pickling
            import cPickle;

            tables = {tablefile : table}

            dumpfile = "dump.bin"
            fd = open(dumpfile, "w")
            cPickle.dump(tables, fd, protocol=2)
            del fd
            del table; del tables

            fd = open(dumpfile)
            up = cPickle.Unpickler(fd)
            del fd
            
            tables = up.load()
            table = tables[tablefile]
            
        try:
            actions = table.actions(self.flavor)
        except RuntimeError, e:
            print table.file, table._actions
            print "product  %s/%s: %s" % (product, version, e)
            return False, shellActions
        #
        # Ready to go
        #
        if self.verbose:
            print >> sys.stderr, "Setting up: %-30s  Flavor: %-10s Version: %s" % \
                  (indent + product, self.flavor, version)
        shellActions += [self.setEnv(product.upper() + "_DIR", product_dir)]

        if len(indent)%2 == 0:
            indent += "|"
        else:
            indent += " "

        for cmd, args, optional in actions:
            if cmd == Table.setupRequired:
                _args = args; args = []
                i = -1
                while i < len(_args) - 1:
                    i += 1
                    if _args[i] == "-f": # a flavor specification -- ignore
                        i += 1       # skip next argument (the flavor)
                        continue
                    args += [_args[i]]

                prod = args.pop(0)
                if args:
                    vers = args.pop(0)
                else:
                    vers = None

                productOK, more_actions = self.setup(indent, prod, vers)
                if not productOK and not optional:
                    raise RuntimeError, ("Failed to setup required product %s/%s" % (prod, vers))
                shellActions += more_actions

        return True, shellActions
    
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def setup(product, version=None, flavor=None, path=None, dbz=None, root=None, verbose=True, noaction=False):
    """ """

    eupsCtrl = Eups("sh", flavor, path, dbz, root, verbose, noaction)

    return eupsCtrl.setup("", product, version)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Parser(object):
    """Evaluate a logical expression, returning a Bool.  The grammar is:

        expr : term
               expr || term          (or  is also accepted)
               expr && term          (and is also accepted)

        term : prim == prim
               prim != prim
               prim < prim
               prim <= prim
               prim > prim
               prim >= prim

	prim : int
               string
               name
               ( expr )

names are declared using Parser.declare()
        """
    def __init__(self, exprStr):
        self._tokens = re.split(r"([\w.+]+|\s+|==|!=|<=|>=|[()<>])", exprStr)
        self._tokens = filter(lambda p: p and not re.search(r"^\s*$", p), self._tokens)
        
        self._symbols = {}
        self._caseSensitive = False

    def define(self, key, value):
        """Define a symbol, which may be substituted using _lookup"""
        
        self._symbols[key] = value

    def _lookup(self, key):
        """Attempt to lookup a key in the symbol table"""
        key0 = key
        
        if not self._caseSensitive:
            key = key.lower()

        try:
            return self._symbols[key]
        except KeyError:
            return key0        

    def _peek(self):
        """Return the next terminal symbol, but don't pop it off the lookahead stack"""
        
        if not self._tokens:
            return "EOF"
        else:
            tok = self._lookup(self._tokens[0])
            try:
                tok = int(tok)
            except ValueError:
                pass

            return tok

    def _push(self, tok):
        """Push a token back onto the lookahead stack"""

        if tok != "EOF":
            self._tokens = [tok] + self._tokens
    
    def _next(self):
        """Return the next terminal symbol, popping it off the lookahead stack"""
        
        tok = self._peek()
        if tok != "EOF":
            self._tokens.pop(0)

        return tok
    
    def eval(self):
        """Evaluate the logical expression, returning a Bool"""
        val = self._expr()              # n.b. may not have consumed all tokens as || and && short circuit

        if val == "EOF":
            return False
        else:
            return val

    def _expr(self):
        lhs = self._term()

        while True:
            op = self._next()

            if op == "||" or op == "or":
                lhs = lhs or self._term()
            elif op == "&&" or op == "and":
                lhs = lhs and self._term()
            else:
                self._push(op)
                return lhs

    def _term(self):
        lhs = self._prim()
        op = self._next()

        if op == "EOF":
            return lhs

        if op == "==":
            return lhs == self._prim()
        elif op == "!=":
            return lhs != self._prim()
        elif op == "<":
            return lhs < self._prim()
        elif op == "<=":
            return lhs <= self._prim()
        elif op == ">":
            return lhs > self._prim()
        elif op == ">=":
            return lhs >= self._prim()
        else:
            self._push(op)
            return lhs

    def _prim(self):
        next = self._peek()

        if next == "(":
            self._next()

            term = self._expr()
            
            next = self._next()
            if next != ")":
                raise RuntimeError, ("Saw next = \"%s\" in prim" % next)

            return term

        return self._next()

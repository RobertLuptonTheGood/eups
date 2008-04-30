# -*- python -*-
import re, os, sys
import cPickle
import pdb
import eupsLock
import eupsParser

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

    def _read(self, tableFile):
        """Read and parse a table file, returning a list of tuples (logical, [action, [arguments], optional])
where the actions are symbols such as Table.envAppend, e.g.
   ('envAppend', ['PYTHONPATH', '${PRODUCT_DIR}/python'], True)
"""
        fd = file(tableFile)

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

class Product(object):
    """Represent a version of a product"""

    def __init__(self, eups, product, version=None):
        """Initialize a Product with the specified product and (maybe) version,
        using the Eups parameters"""
        self.eups = eups

        self.name = product
        self.version, self.db, self.dir, tablefile = self.eups.findVersion(product, version)
        self.table = Table(tablefile)
        
    def __str__(self):
        s = ""
        s += "%s %s -f %s -Z %s" % (self.name, self.version, self.eups.flavor, self.db)

        return s

    def envarDirName(self):
        """Return the name of the product directory's environment variable"""
        return self.name.upper() + "_DIR"

    def envarSetupName(self):
        """Return the name of the product's how-I-was-setup environment variable"""
        return "SETUP_" + self.name.upper()

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Eups(object):
    """Control eups"""
    
    def __init__(self, flavor=None, path=None, dbz=None, root=None, readCache=True, who="???",
                 shell=None, verbose=False, noaction=False):

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

        self.who = who
        self.root = root
        self.verbose = verbose
        self.noaction = noaction

        self._msgs = {}                 # used to suppress messages
        self._msgs["setup"] = {}        # used to suppress messages about setups

        self.locked = {}                # place holder for proper locking
        #
        # Read the cached version information
        #
        self.versions = {}
        if readCache:
            for p in self.path:
                self.readDB(p)

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
                print "unlock(%s)" % lockfile
            else:
                eupsLock.unlock(lockfile)
        else:
            if self.noaction:
                print "lock(%s)" % lockfile
            else:
                eupsLock.lock(lockfile, self.who, max_wait=10)

    def unlinkDB(self, product_base):
        """Delete a persistentDB"""
        
        persistentDB = self.getPersistentDB(product_base)

        if not os.path.exists(persistentDB):
            return

        self.lockDB(product_base)

        try:
            if self.noaction:
                print "rm %s" % persistentDB
            else:
                os.unlink(persistentDB)
        except Exception, e:
            self.lockDB(product_base, unlock=True)

        self.lockDB(product_base, unlock=True)

    def readDB(self, product_base):
        """Read a saved version DB from persistentDB"""
        
        persistentDB = self.getPersistentDB(product_base)

        if not os.path.exists(persistentDB):
            return

        self.lockDB(product_base)

        try:
            fd = open(persistentDB)
            unpickled = cPickle.Unpickler(fd)
        except Exception, e:
            print >> sys.stderr, e
            self.lockDB(product_base, unlock=True)
            raise

        self.lockDB(product_base, unlock=True)

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
    
    def writeDB(self, product_base):
        """Write product_base's version DB to a persistent DB"""

        if isinstance(product_base, str):
            try:
                versions = self.versions[self.flavor][product_base]
            except KeyError:
                return

            persistentDB = self.getPersistentDB(product_base)
            
            self.lockDB(product_base)
            
            try:
                fd = open(persistentDB, "w")
                cPickle.dump(self.versions, fd, protocol=2)
            except Exception, e:
                print >> sys.stderr, e
                self.lockDB(product_base, unlock=True)
                raise

            self.lockDB(product_base, unlock=True)
        else:
            for p in product_base:
                self.writeDB(p)

    def getUpsDB(self, product_base):
        """Return the ups database directory given a directory from self.path"""
        
        return os.path.join(product_base, "ups_db")
    
    def setEnv(self, key, val):
        """Set an environmental variable"""

        if re.search(r"[\s<>]", val):
            val = "'%s'" % val
        
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

    def findCurrentVersion(self, product):
        """Find current version of a product, returning the db and version"""
        
        vinfo = None
        for product_base in self.path:
            ups_db = self.getUpsDB(product_base)

            cfile = os.path.join(ups_db, product, "current.chain")
            if os.path.exists(cfile):
                try:
                    version = Current(cfile).info[self.flavor]["version"]
                    return product_base, version
                except KeyError:
                    raise RuntimeError, "Product %s has no current version for flavor %s" % (product, self.flavor)

        if not vinfo:                       # no version is available
            raise RuntimeError, "Unable to locate %s/%s for flavor %s" % (product, version, self.flavor)

    def findVersion(self, product, version=None):
        """Find a version of a product (if no version is specified, return current version)"""
        
        if not version:
            product_base, version = self.findCurrentVersion(product)
            product_bases = [product_base]
        else:
            product_bases = self.path

        vinfo = None
        for product_base in product_bases:
            ups_db = self.getUpsDB(product_base)
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

        return version, product_base, product_dir, tablefile

    def getProduct(self, product, version):
        """Return a Product, preferably from the cache but the hard way if needs be"""

        if not version:
            db, version = self.findCurrentVersion(product)
        #
        # Try to look it up in the db/product/version dictionary
        #
        if self.versions.has_key(self.flavor):
            for db in self.versions[self.flavor].keys():
                try:
                    prod = self.versions[self.flavor][db][product][version]
                    if self.verbose > 2:
                        print "Found %s/%s in cache" % (product, version)

                    return prod
                except KeyError:
                    pass

        prod = Product(self, product, version)

        self.intern(prod)               # save it in the cache

        return prod

    def buildCache(self, product_base):
        """Build the persistent version cache"""

        self.writeDB(product_base)
    #
    # Here is the externally visible API
    #
    def intern(self, product):
        """ Declare a product"""

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
    
        self.writeDB(product.db)

    def setup(self, product, version, indent=""):
        """The workhorse for setup.  Return (status, actions) where actions is a list of shell
        commands that we need to issue"""

        shellActions = []                   # actions that we need to take
        #
        # Look for product directory
        #
        try:
            product = self.getProduct(product, version)
        except RuntimeError, e:
            if self.verbose:
                print >> sys.stderr, e

            return False, shellActions
        #
        # We have all that we need to know about the product to proceed
        #
        table = product.table
            
        try:
            actions = table.actions(self.flavor)
        except RuntimeError, e:
            print "product %s/%s: %s" % (product.name, product.version, e)
            return False, shellActions
        #
        # Ready to go
        #
        if self.verbose:
            # self._msgs["setup"] is used to suppress multiple messages about setting up the same product
            if indent == "":
                self._msgs["setup"] = {}
            setup_msgs = self._msgs["setup"]

            key = "%s:%s:%s" % (product.name, self.flavor, product.version)
            if self.verbose > 1 or not setup_msgs.has_key(key):
                print >> sys.stderr, "Setting up: %-30s  Flavor: %-10s Version: %s" % \
                      (indent + product.name, self.flavor, product.version)
                setup_msgs[key] = 1
                
        shellActions += [self.setEnv(product.envarDirName(), product.dir)]
        shellActions += [self.setEnv(product.envarSetupName(),
                                     "%s %s -f %s -Z %s" % (product.name, product.version,
                                                            product.eups.flavor, product.db))]

        if len(indent)%2 == 0:
            indent += "|"
        else:
            indent += " "
        #
        # Process table file
        #
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

                productOK, more_actions = self.setup(prod, vers, indent)
                if not productOK and not optional:
                    raise RuntimeError, ("Failed to setup required product %s/%s" % (prod, vers))
                shellActions += more_actions

        return True, shellActions
    
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

def clearCache(flavor=None, path=None, dbz=None, root=None, verbose=True, noaction=False):
    """Remove the cached product information stored in the ups DBs"""

    eups = Eups(flavor, path, dbz, root=root, who="user:RHL", verbose=verbose, noaction=noaction, readCache=False)

    for p in eups.path:
        eups.unlinkDB(p)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def clearLocks(flavor=None, path=None, dbz=None, root=None, verbose=True, noaction=False):
    """Remove lockfiles"""

    eups = Eups(flavor, path, dbz, root=root, who="user:RHL", verbose=verbose, noaction=noaction, readCache=False)

    for p in eups.path:
        eups.lockDB(p, unlock=True)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def setup(product, version=None, flavor=None, path=None, dbz=None, root=None, verbose=True, noaction=False):
    """ """

    eups = Eups(flavor, path, dbz, root=root, who="user:RHL", verbose=verbose, noaction=noaction)

    ok, actions = eups.setup(product, version)
    if ok:
        for a in actions:
            if False:
                print a

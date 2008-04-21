#!/usr/bin/env python

# Routines that talk to eups; all currently use popen on eups shell commands,
# but you're not supposed to know that

import os
import re
import shutil
import sys

if not os.environ.has_key('SHELL'):
    os.environ['SHELL'] = '/bin/sh'

def path():
    """Return the eups path as a python list"""
    try:
        return str.split(os.environ['EUPS_PATH'], ":")
    except KeyError:
        raise RuntimeError, "Please set EUPS_PATH and try again"

def setPath(*args):
    """Set eups' path to the arguments, which may be strings or lists"""

    newPath = []
    for a in args:
        if isinstance(a, str):
            a = [a]

        if a:
            newPath += a

    if newPath:
        os.environ["EUPS_PATH"] = ":".join(newPath)
    else:
        raise RuntimeError, "New eups path is empty"

    return path()

def selectPathComponent(dbz=0, eups_path=None):
    """Return a component of a eups path given a specifier (as in the -z option) or
    an index, and optionally a value of EUPS_PATH (default: path());
    the path may be a string or a list of values"""

    if not eups_path:
        eups_path = path()

    if isinstance(eups_path, str):
        eups_path = eups_path.split(":")

    try:
        db = eups_path[dbz]
    except TypeError:
        if dbz:
            db = filter(lambda x: re.search("/%s/" % dbz, x), eups_path)
            if len(db) == 0:
                raise RuntimeError, ("DB %s is not found in EUPS_PATH: %s" % (dbz, str.join(" ", eups_path)))
            elif len(db) == 1:
                db = db[0]
            else:
                raise RuntimeError, ("Choice of DB %s is ambiguous: %s" % (dbz, " ".join(db)))
        else:
            db = eups_path[0]

    if not os.path.isdir(db):
        raise RuntimeError, ("Products directory %s doesn't exist" % db)

    return db

def findVersion(product, version=None):
    """Return the requested version of product; may be "current" (== None), "setup", or a version string"""
    if version == None or version == "current":
        return current(product)
    elif version == "setup":
        return setup(product)
    else:
        return version

def current(product="", dbz="", flavor = ""):
    """Return the current version of a product; if product is omitted,
    return a list of (product, version) for all products"""

    return _current_or_setup("current", product, dbz, flavor)

def setup(product="", dbz="", flavor = ""):
    """Return the setup version of a product; if product is omitted,
    return a list of (product, version) for all products"""

    return _current_or_setup("setup", product, dbz, flavor)

def _current_or_setup(characteristic, product="", dbz="", flavor = ""):
    """Return the \"characteristic\" (e.g. current) version of a product; if product is omitted,
    return a list of (product, version) for all products"""

    opts = ""
    if dbz:
        opts += " --select-db %s" % (dbz)
    if flavor:
        opts += " --flavor %s" % (flavor)

    products = []
    for line in os.popen("eups list --%s %s %s 2>&1" % (characteristic, opts, product)).readlines():
        if re.search(r"^ERROR", line):
            raise RuntimeError, line
        elif re.search(r"^WARNING", line):
            continue

        if re.search(r"^No version is declared current", line) and product:
            return None
            
        match = re.findall(r"\S+", line)
        if product:
            return match[0]

        products += [match[0:2]]

    return products

def declare(product, version, flavor, dbz, tablefile, products_root, product_dir, declare_current = False,
            noaction = False):
    """Declare a product.  product_dir may be None to just declare the product current (or
    use declareCurrent)"""

    opts = ""
    if declare_current:
        opts += " -c"
    if dbz:
        opts += " -z %s" % dbz

    if product_dir:
        if product_dir != "/dev/null":
            opts += " --root %s" % os.path.join(products_root, product_dir)

        tableopt = "-m"
        if tablefile != "none":
            if ("%s.table" % (product)) != tablefile:
                tableopt = "-M"
        opts += " %s %s" % (tableopt, tablefile)

    try:
        cmd = "eups_declare --flavor %s%s %s %s" % \
              (flavor, opts, product, version)
        if noaction:
            print cmd
        else:
            if os.system(cmd) != 0:
                raise RuntimeError, cmd
    except KeyboardInterrupt:
        raise
    except:
        raise RuntimeError, "Failed to declare product %s (version %s, flavor %s)" % \
              (product, version, flavor)

def declareCurrent(product, version, flavor, dbz, noaction = False):
    """Declare a product current"""

    declare(product, version, flavor, dbz, None, None, None, declare_current=True,
            noaction=noaction)

def undeclare(product, version, flavor=None, dbz=None, undeclare_current=False,
              noaction = False, force=False):
    """Undeclare a product."""

    opts = ""
    if undeclare_current:
        opts += " -c"
    if dbz:
        opts += " -z %s" % dbz
    if flavor:
        opts += " --flavor %s" % flavor
    if force:
        opts += " --force"

    try:
        cmd = "eups_undeclare%s %s %s" % (opts, product, version)
        if noaction:
            print cmd
        else:
            if os.system(cmd) != 0:
                raise RuntimeError, cmd
    except KeyboardInterrupt:
        raise
    except:
        print >> sys.stderr, "Failed to undeclare product %s (version %s, flavor %s)" % \
              (product, version, flavor)
        return False

    return True

def undeclareCurrent(flavor, dbz, product, version, noaction = False):
    """Undeclare a product current"""

    undeclare(product, version, flavor, dbz, undeclare_current=True,
              noaction=noaction)

def remove(product, version, flavor=None, dbz=None, recursive=False, force=False, checkRecursive=False, noaction=False,
           topProduct=None, topVersion=None, userInfo=None, interactive=False):
    """Undeclare and remove a product.  If recursive is true also remove everything that
    this product depends on; if checkRecursive is True, you won't be able to remove any
    product that's in use elsewhere unless force is also True.  N.b. The checkRecursive
    option is quite slow (it has to read every table file on the system).  If you're
    calling remove repeatedly, you can pass in a userInfo object (returned by uses(None, None))
    to save remove() having to read all those table files on every call.    
    """

    if not topProduct:
        topProduct = product
    if not topVersion:
        topVersion = version

    #
    # Gather the required information
    #
    if checkRecursive and not userInfo:
        userInfo = uses()
    #
    # Figure out what to remove
    #
    productsToRemove = _remove(product, version, flavor, dbz, recursive, force, checkRecursive, noaction,
                               topProduct, topVersion, userInfo)

    productsToRemove = blist(set(productsToRemove)) # remove duplicates
    #
    # Actually wreak destruction. Don't do this in _remove as we're relying on the static userInfo
    #
    default_yn = "y"                    # default reply to interactive question
    for product, version in productsToRemove:
        dir = directory(product, version)
        if not dir:
            raise RuntimeError, ("Product %s with version %s doesn't seem to exist" % (product, version))

        if interactive:
            while True:
                yn = raw_input("Remove %s %s: [%s] " % (product, version, default_yn))
                
                if yn == "":
                    yn = default_yn
                if yn == "y" or yn == "n":
                    default_yn = yn
                    break
                else:
                    print >> sys.stderr, "Please answer y or n, not %s" % yn

            if yn == "n":
                continue

        if not undeclare(product, version, flavor, dbz, False, noaction, force):
            raise RuntimeError, ("Not removing %s %s" % (product, version))

        if dir and dir != "none":
            if noaction:
                print "rm -rf %s" % dir
            else:
                try:
                    shutil.rmtree(dir)
                except OSError, e:
                    raise RuntimeError, e

def _remove(product, version, flavor, dbz, recursive, force, checkRecursive, noaction,
            topProduct, topVersion, userInfo):
    """The workhorse for remove"""
    
    if recursive:
        try:
            deps = dependencies(product, version, dbz, flavor)
        except RuntimeError, e:
            raise RuntimeError, ("product %s %s doesn't seem to exist" % (product, version))

        productsToRemove = []
        for p, v, f, o in deps:
            if checkRecursive:
                usedBy = filter(lambda el: el[0] != topProduct or el[1] != topVersion, userInfo.users(p, v))

                if usedBy:
                    tmp = []
                    for user in usedBy:
                        tmp += ["%s %s" % (user[0], user[1])]

                    if len(tmp) == 1:
                        plural = ""
                        tmp = str(tmp[0])
                    else:
                        plural = "s"
                        tmp = "(%s)" % "), (".join(tmp)

                    msg = "%s %s is required by product%s %s" % (p, v, plural, tmp)

                    if force:
                        print >> sys.stderr, "%s; removing anyway" % (msg)
                    else:
                        print >> sys.stderr, "%s; specify --force to remove" % (msg)
                        continue
                
            productsToRemove += _remove(p, v, f, dbz, (p != product), force, checkRecursive, noaction,
                                        topProduct=topProduct, topVersion=topVersion, userInfo=userInfo)
        return productsToRemove

    return [(product, version)]

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def dependencies(product, version, dbz="", flavor="", depth=9999):
    """Return a product's dependencies in the form of a list of tuples
    (product, version, flavor, optional)
    Only return depth levels of dependencies (0 -> just top level)
"""

    if not flavor:
        flavor = getFlavor()

    global dep_products; dep_products = {}

    optional = False
    productList = dependencies_from_table(table(product, version, dbz, flavor, quiet=True))
    deps = [(product, version, flavor, optional)] + \
           _dependencies(productList, dbz, flavor, optional, depth - 1)
    #
    # We have potentially got both optional and non-optional setups in deps, so
    # go through and keep the required one if it's there
    #
    def key(p, v, f):
        return "%s:%s:%s" % (p, v, f)
    #
    # Find which products are optional (i.e. never required)
    #
    optional = {}
    for p, v, f, o in deps:
        k = key(p, v, f)
        if not optional.has_key(k):
            optional[k] = o
        else:
            optional[k] = optional[k] and o
    #
    # Use optional{} to generate the list of unique products
    #
    seen = {}
    udeps = []
    for p, v, f, o in deps:
        k = key(p, v, f)
        if not seen.has_key(k):
            udeps += [(p, v, f, optional[k])]
            seen[k] = 1

    return udeps

def _dependencies(productList, dbz, flavor, optional, depth):
    """Here's the workhorse for dependencies"""

    if depth < 0 or not productList:
        return []

    productList.reverse()               # we want to keep the LAST occurrence

    global dep_products
    deps = []

    for oneProduct, oneVersion, oneOptional in productList:
        oneOptional = optional or oneOptional

        if not oneVersion:
            oneVersion = findVersion(oneProduct, "current")

        oneDep = (oneProduct, oneVersion, flavor, oneOptional)

        # prune repeats of identical product version/flavor/optional
        versionHash = "%s:%s:%d" % (oneVersion, flavor, oneOptional)
        if dep_products.has_key(oneProduct) and dep_products[oneProduct] == versionHash:
            continue

        dep_products[oneProduct] = versionHash

        oneProductList = dependencies_from_table(table(oneProduct, oneVersion, dbz, flavor, quiet=True))
        deps += [_dependencies(oneProductList, dbz, flavor, optional, depth - 1)]

        deps += [[oneDep]]

    deps.reverse() # we reversed productList to keep the last occurence; switch back
    
    return sum(deps, [])                # flatten the list

def dependencies_from_table(tableFile, verbose=0):
    """Return a list of tuples (product, version) that need to be
    setup, given a table file.

    N.b. This is the top-level requirements, it isn't computed recursively"""

    if not tableFile:
        return []

    try:
        fd = open(tableFile)
    except IOError:
        return []

    products = []
    for line in fd:
        mat = re.search(r"^\s*(setupRequired|setupOptional)\s*\(\s*([^)]+)\s*\)", line)
        if mat:
            args = []
            optional = not not re.search(r"^\s*setupOptional", mat.group(1))
            ignore = False;             # ignore next argument
            for a in re.sub(r'^"|"$', "", mat.group(2)).split():
                if a == "-f" or a == "--flavor": # ignore flavor specifications
                    ignore = True
                    continue
                    
                if ignore:
                    ignore = False
                else:
                    args += [a]
            
            if len(args) == 1:
                args += [None]
            elif len(args) == 2:
                pass
            else:
                version_properties = list(args[0], "".join(args[1:])) # maybe a conditional
                if version_properties:
                    version = version_properties[0]

                    if verbose > 2:
                        print >> sys.stderr, "%-30s -> %s" % (" ".join(args), version)
                    args = args[0:1] + [version]

                if len(args) == 2:
                    pass
                else:
                    print >> sys.stderr, "Failed to parse: ", line,
                    args = args[0:2]

            args += [optional]

            products += [tuple(args)]

    return products

#
# Cache for the Uses tree
#
class Uses(object):
    def __init__(self):
        self._depends_on = {} # info about products that depend on key
        self._setup_by = {}       # info about products that setup key, directly or indirectly

    def _getKey(self, p, v):
        return "%s:%s" % (p, v)

    def _remember(self, p, v, info):
        key = self._getKey(p, v)

        if not self._depends_on.has_key(key):
            self._depends_on[key] = []

        self._depends_on[key] += [info]

    def _do_invert(self, product, version, k, depth, optional=False):
        """Workhorse for _invert"""
        if depth <= 0 or not self._depends_on.has_key(k):
            return
        
        for p, v, o in self._depends_on[k]:
            o = o or optional

            key = self._getKey(p, v)
            if not self._setup_by.has_key(key):
                self._setup_by[key] = []

            self._setup_by[key] += [(product, version, (v, o))]

            self._do_invert(product, version, self._getKey(p, v), depth - 1, o)

    def _invert(self, depth):
        """ Invert the dependencies to tell us who uses what, not who depends on what"""
        pattern = re.compile(r"^(?P<product>[\w]+):(?P<version>[\w.+\-]+)")

        self._setup_by = {}
        for k in self._depends_on.keys():
            mat = pattern.match(k)
            assert mat

            product = mat.group("product")
            version = mat.group("version")

            self._do_invert(product, version, k, depth)

        if False:
            for k in self._depends_on.keys():
                print "%-30s" % k, self._depends_on[k]
        if False:
            print; print "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"; print
        if False:
            for k in self._setup_by.keys():
                print "XX %-20s" % k, self._setup_by[k]
        #
        # Make values in _setup_by unique
        #
        for k in self._setup_by.keys():
            self._setup_by[k] = blist(set(self._setup_by[k]))

    def users(self, product, version=None):
        """Return a list of the users of product/productVersion; each element of the list is:
        (user, userVersion, (productVersion, optional)"""
        if version:
            version = re.escape(version)
        else:
            version = r"[\w.+\-]+"
            
        version = r"(?P<version>%s)" % version

        pattern = re.compile(r"^%s$" % self._getKey(product, version))
        consumerList = []
        for k in self._setup_by.keys():
            mat = pattern.match(k)
            if mat:
                consumerList += (self._setup_by[k])
        #
        # Be nice; sort list
        #
        def pvsort(a,b):
            """Sort by product then version then information"""

            if a[0] == b[0]:
                if a[1] == b[1]:
                    return cmp(a[2], b[2])
                else:
                    return cmp(a[1], b[1])
            else:
                return cmp(a[0], b[0])

        consumerList.sort(pvsort)
        
        return consumerList
        
def uses(product=None, version=None, dbz="", flavor="", depth=9999, quiet=False):
    """Return a list of all products which depend on the specified product in the form of a list of tuples
    (product, productVersion, (versionNeeded, optional))

    depth tells you how indirect the setup is (depth==1 => product is setup in table file,
    2 => we set up another product with product in its table file, etc.)

    version may be None in which case all versions are returned.  If product is also None,
    a Uses object is returned which may be used to perform further uses searches efficiently
"""
    useInfo = Uses()

    if not product and version:
        raise RuntimeError, ("You may not specify a version \"%s\"but not a product" % version)

    if True:
        productList = list(None, dbz=dbz, flavor=flavor)
    else:                               # debug code only!
        prods = ("test", "test2", "test3", "boo", "goo", "hoo")
        #prods = (["test"])
        #prods = (["astrotools"])
        #prods = (["afw"])

        productList = []
        for p in prods:
            try:
                for pl in list(p, dbz=dbz, flavor=flavor):
                    productList += [[p] + pl]
            except TypeError:
                continue

    if not productList:
        return []

    for (p, v, db, dir, isCurrent, isSetup) in productList: # for every known product
        for pd, vd, fd, od in dependencies(p, v, dbz, flavor, 1): # lookup top-level dependencies
            if p == pd and v == vd:
                continue

            useInfo._remember(p, v, (pd, vd, od))
    useInfo._invert(depth)
    #
    # OK, we have the information stored away
    #
    if not product:
        return useInfo

    consumerList = useInfo.users(product, version)

    return consumerList

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def flavor():
    """Return the current flavor"""
    
    if os.environ.has_key("EUPS_FLAVOR"):
        return os.environ["EUPS_FLAVOR"]
    return str.split(os.popen('eups_flavor').readline(), "\n")[0]

getFlavor = flavor                      # useful in this file if you have a variable named flavor

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

from __builtin__ import list as blist

def list(product, version = "", dbz = "", flavor = "", quiet=False):
    """Return a list of declared versions of a product; if the
    version is specified, just return the properties of that version.
    The version may be "current" or "setup" to return the current
    or setup version.

    The return value for each product is a list of lists:
       [[version, database, directory, isCurrent, isSetup], ...]
    (if only one version matches, the return is a single list; if no versions
    match, you'll get None)

    If you specify product as "" (or None) the inner list will have an extra
    field, the product name.
    """

    if not product:
        product = ""

    versionRequested = False         # did they specify a version, even if none is current or setup?
    if version:
        versionRequested = True
        version = findVersion(product, version)

    if versionRequested and not product:
        raise RuntimeError, "You may not request a specific version but not choose a product"

    opts = ""
    if dbz:
        opts += " --select-db %s" % (dbz)
    if flavor:
        opts += " --flavor %s" % (flavor)

    result = []
    for info in os.popen("eups list %s --quiet --verbose %s '%s'" % (opts, product, version)).readlines():
        oneResult = re.findall(r"\S+", info)

        if not product:
            p = oneResult[0]
            oneResult = oneResult[1:]

        if len(oneResult) == 3:
            oneResult += [False]
        else:
            if oneResult[3] == "Current":
                oneResult[3] = True
            else:
                oneResult[3:3] = [False]

        if len(oneResult) == 4:
            oneResult += [False]
        else:
            assert (oneResult[4] == "Setup")
            oneResult[4] = True
        assert len(oneResult) == 5

        if not product:
            oneResult = [p] + oneResult

        result += [oneResult]

        if versionRequested:
            return oneResult
        
    if len(result):
        return result
    else:
        None

def database(product, version="current", dbz = "", flavor = ""):
    """Return the database for the specified product and version"""

    vals = list(product, version, dbz, flavor)
    if vals:
        return vals[1]
    else:
        None        

def directory(product, version="current", dbz = "", flavor = ""):
    """Return the PRODUCT_DIR for the specified product and version"""

    vals = list(product, version, dbz, flavor)
    if vals:
        return vals[2]
    else:
        None

productDir = directory                  # provide an alias

def isCurrent(product, version, dbz = "", flavor = ""):
    """Return True iff the the specified product and version is current"""

    vals = list(product, version, dbz, flavor)
    if vals:
        return vals[3]
    else:
        False       

def isSetup(product, version, dbz = "", flavor = ""):
    """Return True iff the the specified product and version is setup"""

    vals = list(product, version, dbz, flavor)
    if vals:
        return vals[4]
    else:
        False

def table(product, version, dbz="", flavor="", quiet=False):
    """Return the full path of a product's tablefile"""

    version = findVersion(product, version)

    opts = ""
    if dbz:
        opts += " --select-db %s" % (dbz)
    if flavor:
        opts += " --flavor %s" % (flavor)
        
    try:
        info = os.popen("eups list %s --table %s %s" % \
                        (opts, product, version)).readlines()[0].split("\n")
    except IndexError:
        if not quiet:
            print >> sys.stderr, ("Unable to find table file for %s %s" % (product, version))

        return None

    for i in info:
        if re.search("^WARNING", i):
            print >> sys.stderr, i
        else:
            if len(i) > 0:
                return re.findall(r"\S+", i)[0]

    return None

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def version(versionString='$HeadURL$'):
    """Return a version name based on a cvs or svn ID string (dollar name dollar or dollar HeadURL dollar)"""

    if re.search(r"^[$]Name:\s+", versionString):
        # CVS.  Extract the tagname
        version = re.search(r"^[$]Name:\s+([^ $]*)", versionString).group(1)
        if version == "":
            version = "cvs"
    elif re.search(r"^[$]HeadURL:\s+", versionString):
        # SVN.  Guess the tagname from whatever follows "tags" (or "TAGS") in the URL
        version = "svn"                 # default
        parts = versionString.split("/")
        for i in range(0, len(parts) - 1):
            if parts[i] == "tags" or parts[i] == "TAGS":
                version = parts[i + 1]
                break
    else:
        version = "unknown"

    return version


#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

# Like getopt.getopt, but supports a dictionary options of recognised
# options, supports long option names, allows aliases, allows options
# to follow arguments, and sets the values of flag options to the
# number of occurrences of the flag

class Getopt:
    def __init__(self, options, argv = sys.argv, aliases = {}, msg = None):
        """A class to represent the processed command line arguments.

options is a dictionary whose keys are is the short name of the option
(and the one that it'll be indexed as), and the value is a tuple; the
first element is a boolean specifying if the option takes a value; the
second (if not None) is a long alias for the option, and the third is
a help string.  E.g.
    ["-i", (False, "--install", "Extract and install the specified package")],

aliases is another dictionary, with values that specify additional long versions
of options; e.g.
    ["-i", ["--extract"]],

Options may be accessed as Getopt.options[], and non-option arguments as Getopt.argv[]

msg is the help message associated with the command
        
"""
        if msg:
            self.msg = msg
        else:
            self.msg = "Command [options] arguments"
        #
        # Provide a -h/--help option if -h is omitted
        #
        if not options.has_key('-h'):
            options["-h"] = (False, "--help", "Print this help message")        
        #
        # Build the options string for getopt() and a hash of the long options
        #
        optstr = ""
        longopts = {}
        for opt in options.keys():
            optstr += opt[1]
            if options[opt][0]:
                optstr += ":"

            if options[opt][1]:
                longopts[options[opt][1]] = opt

        for opt in aliases.keys():
            longopts[aliases[opt][0]] = opt
        #
        # Massage the arguments
        #
        nargv = []
        opts = {}
        verbose = 0
        i = 0
        while i < len(argv) - 1:
            i = i + 1
            a = argv[i]

            if a == "" or re.search(r"^[^-]", a):
                nargv += [a]
                continue

            mat = re.search(r"^([^=]+)=(.*)$", a)
            if mat:
                (a, val) = mat.groups()
            else:
                val = None            

            if longopts.has_key(a):
                a = longopts[a]

            if options.has_key(a):
                if options[a][0]:
                    if val:
                        opts[a] = val
                    else:
                        try:
                            opts[a] = argv[i + 1]; i += 1
                        except IndexError:
                            raise RuntimeError, ("Option %s expects a value" % a)
                else:
                    if opts.has_key(a):
                        opts[a] += 1
                    else:
                        opts[a] = 1
            else:
                raise RuntimeError, ("Unrecognised option %s" % a)
        #
        # Save state
        #
        self.cmd_options = options  # possible options
        self.cmd_aliases = aliases  # possible aliases
        self.options = opts         # the options provided
        self.argv = nargv           # the surviving arguments

    def has_option(self, opt):
        """Whas the option "opt" provided"""
        return self.options.has_key(opt)

    def usage(self):
        """Print a usage message based on the options list"""

        print >> sys.stderr, """\
Usage:
    %s
Options:""" % self.msg

        def asort(a,b):
            """Sort alphabetically, so -C, --cvs, and -c appear together"""

            a = self.cmd_options[a][1]
            b = self.cmd_options[b][1]

            a = re.sub(r"^-*", "", a)       # strip leading -
            b = re.sub(r"^-*", "", b)       # strip leading -

            if a.upper() != b.upper():
                a = a.upper(); b = b.upper()

            if a < b:
                return -1
            elif a == b:
                return 0
            else:
                return 1

        skeys = self.cmd_options.keys(); skeys.sort(asort) # python <= 2.3 doesn't support "sorted"
        for opt in skeys:
            popt = opt
            if ord(popt[1]) < ord(' '): # not printable; only long option matters
                popt = ""
            optstr = "%2s%1s %s" % \
                     (popt,
                      ((not popt or not self.cmd_options[opt][1]) and [""] or [","])[0],
                      self.cmd_options[opt][1] or "")
            optstr = "%-16s %s" % \
                     (optstr, (not self.cmd_options[opt][0] and [""] or ["arg"])[0])
            
            print >> sys.stderr, "   %-23s %s" % \
                  (optstr, ("\n%27s"%"").join(self.cmd_options[opt][2].split("\n")))
            if self.cmd_aliases.has_key(opt):
                print >> sys.stderr, "                           Alias%s:" % \
                      (len(self.cmd_aliases[opt]) == 1 and [""] or ["es"])[0], " ".join(self.cmd_aliases[opt])
#
# Expand a build file
#
def expandBuildFile(ofd, ifd, product, version, verbose=False, svnroot=None, cvsroot=None):
    """Expand a build file, reading from ifd and writing to ofd"""
    #
    # A couple of functions to set/guess the values that we'll be substituting
    # into the build file
    #
    # Guess the value of CVSROOT
    #
    def guess_cvsroot(cvsroot):
        if cvsroot:
            pass
        elif os.environ.has_key("CVSROOT"):
            cvsroot = os.environ["CVSROOT"]
        elif os.path.isdir("CVS"):
            try:
                rfd = open("CVS/Root")
                cvsroot = re.sub(r"\n$", "", rfd.readline())
                del rfd
            except IOError, e:
                print >> sys.stderr, "Tried to read \"CVS/Root\" but failed: %s" % e

        return cvsroot    
    #
    # Guess the value of SVNROOT
    #
    def guess_svnroot(svnroot):
        if svnroot:
            pass
        elif os.environ.has_key("SVNROOT"):
            svnroot = os.environ["SVNROOT"]
        elif os.path.isdir(".svn"):
            try:
                rfd = os.popen("svn info .svn")
                for line in rfd:
                    mat = re.search(r"^Repository Root: (\S+)", line)
                    if mat:
                        svnroot = mat.group(1)
                        break

                if not svnroot:         # Repository Root is absent in svn 1.1
                    rfd = os.popen("svn info .svn")
                    for line in rfd:
                        mat = re.search(r"^URL: ([^/]+//[^/]+)", line)
                        if mat:
                            svnroot = mat.group(1)
                            break

                del rfd
            except IOError, e:
                print >> sys.stderr, "Tried to read \".svn\" but failed: %s" % e

        return svnroot
    #
    # Here's the function to do the substitutions
    #
    subs = {}                               # dictionary of substitutions
    subs["CVSROOT"] = guess_cvsroot(cvsroot)
    subs["SVNROOT"] = guess_svnroot(svnroot)
    subs["PRODUCT"] = product
    subs["VERSION"] = version

    def subVar(name):
        var = name.group(1).upper()
        if subs.has_key(var):
            if not subs[var]:
                raise RuntimeError, "I can't guess a %s for you -- please set $%s" % (var, var)
            return subs[var]

        return "XXX"
    #
    # Actually do the work
    #
    for line in ifd:
        # Attempt substitutions
        line = re.sub(r"@([^@]+)@", subVar, line)
        line = re.sub(r"/tags/svn", "/trunk -r ", line);

        print >> ofd, line,

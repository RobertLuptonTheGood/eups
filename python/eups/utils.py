"""
Utility functions used across EUPS classes.
"""
import time, os, sys, glob, re, tempfile
from cStringIO import StringIO

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

    versionString = re.sub(r'/python/eups/\w+.py\s*\$\s*$', '$',
                           r"$HeadURL$")

    version = "unknown"

    if re.search(r"^[$]HeadURL:\s+", versionString):
        # SVN.  Guess the tagname from the last part of the directory
        try:
            branch = ['', '']
            mat = re.search(r'/([^/]+)(/([^/]+))\s*\$\s*$', versionString)
            if mat:
                branch[0] = mat.group(1)
                branch[1] = mat.group(3)
                if branch[1] == 'trunk':
                    branch = [branch[1], '']

            if branch[0] == "tags":
                version = branch[1]
                return version
            elif branch[0] == "tickets":
                version = "ticket%s+svn" % branch[1]
            else:
                version = "svn"

            try:                    # try to add the svn revision to the version
                (oldest, youngest, flags) = _svnRevision()
                version += youngest
            except IOError:
                pass
        except RuntimeError:
            pass

    return version

def debug(*args, **kwargs):
    """
    Print args to stderr; useful while debugging as we source the stdout 
    when setting up.  Specify eol=False to suppress newline"""

    print >> sys.stderr, "Debug:", # make sure that this routine is only used for debugging
    
    for a in args:
        print >> sys.stderr, a,

    if kwargs.get("eol", True):
        print >> sys.stderr

def deprecated(msg, quiet=False, strm=sys.stderr):
    """
    Inform the user that an deprecated API was employed.  Currently, this is 
    done by printing a message, but in the future, it might raise an exception.
    @param msg     the message to print
    @param quiet   if true, this message will not be printed.  
    @param strm    the stream to write to (default: sys.stderr)
    """
    # Note quiet as bool converts transparently to int (0 or 1)
    if quiet < 0:  quiet = 0
    if not quiet:
        print >> strm, "Warning:", msg

def dirEnvNameFor(productName):
    """
    return the name of the environment variable containing a product's
    root/installation directory.  This is of the form "product_DIR"
    """
    return productName.upper() + "_DIR"

def setupEnvNameFor(productName):
    """
    return the name of the environment variable that provides the 
    setup information for a product.  This is of the form, "SETUP_prod".
    """
    # Return the name of the product's how-I-was-setup environment variable
    name = "SETUP_" + productName

    if os.environ.has_key(name):
        return name                 # exact match

    envNames = filter(lambda k: re.search(r"^%s$" % name, k, re.IGNORECASE), os.environ.keys())
    if envNames:
        return envNames[0]
    else:
        return name.upper()

def userStackCacheFor(eupsPathDir, userDataDir=None):
    """
    return cache directory for a given EUPS product stack in the user's 
    data directory.  None is returned if a directory cannot be determined
    @param eupsPathDir   the product stack to return a cache directory for
    @param userDataDir   the user's personal data directory.  If not given,
                            it is set to the value returned by 
                            defaultUserDataDir() (by default ~/.eups).
    """
    if not userDataDir:
        userDataDir = defaultUserDataDir()
    if not userDataDir:
        return None

    return os.path.join(userDataDir,"_caches_", eupsPathDir[1:])

def defaultUserDataDir():
    """
    return the default user data directory.  This will be the value of 
    $EUPS_USERDATA if set; otherwise, it is ~/.eups. 
    """

    if os.environ.has_key("EUPS_USERDATA"):
        userDataDir = os.environ["EUPS_USERDATA"]
    else:
        userDataDir = os.path.join(os.path.expanduser("~"), ".eups")

    return userDataDir

def ctimeTZ(t=None):
    """Return a string-formatted timestampe with time zone"""

    if not t:
        t = time.localtime()

    return time.strftime("%Y/%m/%d %H:%M:%S %Z", t)

def isRealFilename(filename):
    """
    Return True iff "filename" is a real filename, not a placeholder.  
    It need not exist.  The following names are considered placeholders:
    ["none", "???", "(none)"].
    """
    if filename is None:
        return False
    elif filename in ("none", "???", "(none)"):
        return False
    else:
        return True
    
def isDbWritable(dbpath):
    """
    return true if the database is updatable.  A non-existent
    directory is considered not writable.  If the path is not a
    directory, an exception is raised.  

    The database must be writable to:
      o  declare new products
      o  set or update global tags
      o  update the product cache
    """
    return os.access(dbpath, (os.F_OK|os.R_OK|os.W_OK))

def findWritableDb(pathdirs):
    """return the first directory in the eups path that the user can install 
    stuff into
    """
    if isinstance(pathdirs, str):
        pathdirs = pathdirs.split(':')
    if not isinstance(pathdirs, list):
        raise TypeError("findWritableDb(): arg is not list or string: " + 
                        pathdirs)
    for path in pathdirs:
        if isDbWritable(path):
            return path

    return None

def version_cmp(v1, v2, suffix=False):
    """Here's the internal routine that _version_cmp uses.
    It's split out so that we can pass it to the callback
    """

    def split_version(version):
        # Split a version string of the form VVV([m-]EEE)?([p+]FFF)?
        if not version:
            return "", "", ""

        if len(version.split("-")) > 2: # a version string such as rel-0-8-2 with more than one hyphen
            return version, "", ""

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
                    ret = version_cmp(sec1, sec2, True)
                else:
                    if sec1:
                        return -1
                    else:
                        return 1

                if ret == 0:
                    return version_cmp(ter1, ter2, True)
                else:
                    return ret

            return version_cmp(ter1, ter2, True)
        else:
            return 0

    c1 = re.split(r"[._]", prim1)
    c2 = re.split(r"[._]", prim2)
    #
    # Check that leading non-numerical parts agree
    #
    if not suffix:
        prefix1, prefix2 = "", ""
        mat = re.search(r"^([^0-9]+)", c1[0])
        if mat:
            prefix1 = mat.group(1)

        mat = re.search(r"^([^0-9]+)", c2[0])
        if mat:
            prefix2 = mat.group(1)

        if len(prefix1) > len(prefix2): # take shorter prefix
            prefix = prefix2
            if not re.search(r"^%s" % prefix, c1[0]):
                return +1
        else:
            prefix = prefix1
            if not re.search(r"^%s" % prefix1, c2[0]):
                return -1

        c1[0] = re.sub(r"^%s" % prefix, "", c1[0])
        c2[0] = re.sub(r"^%s" % prefix, "", c2[0])

    n1 = len(c1); n2 = len(c2)
    if n1 < n2:
        n = n1
    else:
        n = n2

    for i in range(n):
        try:                        # try to compare as integers, having stripped a common prefix
            _c2i = None             # used in test for a successfully removing a common prefix

            mat = re.search(r"^([^\d]+)\d+$", c1[i])
            if mat:
                prefixi = mat.group(1)
                if re.search(r"^%s\d+$" % prefixi, c2[i]):
                    _c1i = int(c1[i][len(prefixi):])
                    _c2i = int(c2[i][len(prefixi):])

            if _c2i is None:
                _c1i = int(c1[i])
                _c2i = int(c2[i])

            c1[i] = _c1i
            c2[i] = _c2i
        except ValueError:
            pass

        different = cmp(c1[i], c2[i])
        if different:
            return different

    # So far, the two versions are identical.  The longer version should sort later
    return cmp(n1, n2)

def determineFlavor():
    """Return the current flavor"""
    
    if os.environ.has_key("EUPS_FLAVOR"):
        return os.environ["EUPS_FLAVOR"]

    uname = os.uname()[0]
    mach =  os.uname()[4]

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
    
def guessProduct(dir, productName=None):
    """Guess a product name given a directory containing table files.  If you provide productName,
    it'll be chosen if present; otherwise if dir doesn't contain exactly one product we'll raise RuntimeError"""

    if not os.path.isdir(dir):
        if productName:
            return productName

        # They may have specified XXX but dir == XXX/ups
        root, leaf = os.path.split(dir)
        if leaf == "ups" and not os.path.isdir(root):
            dir = root
            
        raise RuntimeError, ("%s isn't a directory" % dir)
            
    productNames = map(lambda t: re.sub(r".*/([^/]+)\.table$", r"\1", t), glob.glob(os.path.join(dir, "*.table")))

    if not productNames:
        if productName:
            # trust the suggestion
            return productName
        raise RuntimeError, ("I can't find any table files in %s" % dir)

    if productName:
        if productName in productNames:
            return productName
        else:
            raise RuntimeError, ("You chose product %s, but I can't find its table file in %s" % (productName, dir))
    elif len(productNames) == 1:
        return productNames[0]
    else:
        raise RuntimeError, \
              ("I can't guess which product you want; directory %s contains: %s" % (dir, " ".join(productNames)))

class Flavor(object):
    """A class to handle flavors"""

    def __init__(self):
        try:
            Flavor._fallbackFlavors
        except AttributeError:
            Flavor._fallbackFlavors = {}

            self.setFallbackFlavors(None)
        
    def setFallbackFlavors(self, flavor=None, fallbackList=None):
        """
        Set a list of alternative flavors to be used if a product can't 
        be found with the given flavor.  The defaults are set in hooks.py
        """
        if fallbackList is None:
            fallbackList = []
        Flavor._fallbackFlavors[flavor] = fallbackList

    def getFallbackFlavors(self, flavor=None, includeMe=False):
        """
        Return the list of alternative flavors to use if the specified 
        flavor is unavailable.  The alternatives to None are always available

        If includeMe is true, include flavor as the first element 
        of the returned list of flavors
        """
        try:
            fallbacks = Flavor._fallbackFlavors[flavor]
        except KeyError:
            fallbacks = Flavor._fallbackFlavors[None]

        if flavor and includeMe:
            fallbacks = [flavor] + fallbacks

        return fallbacks

# Note: setFallbackFlavors is made available to our beloved users via 
# eups/__init__.py
# 
# setFallbackFlavors = Flavor().setFallbackFlavors 

class Quiet(object):
    """A class whose members, while they exist, make Eups quieter"""

    def __init__(self, Eups):
        self.Eups = Eups
        self.Eups.quiet += 1

    def __del__(self):
        self.Eups.quiet -= 1

class ConfigProperty(object):
    """
    This class emulates a properties used in configuration files.  It 
    represents a set of defined property names that are accessible as 
    attributes.  The names of the attributes are locked in at construction
    time.  If an attribute value is itself contains a ConfigProperty, that
    value cannot be over-written.  If one attempts to either over-write a
    ConfigProperty instance or set a non-existent attribute, an 
    AttributeError will not be raised; instead, an error message is 
    written and the operation is otherwise ignored.  
    """
    def __init__(self, attrnames, parentName=None):
        """
        define up the properties as attributes.
        @param attrnames    a list of property names to define as attributes
        @param parentName   a dot-delimited name of the parent property; if 
                               None (default), the property is assumed to 
                               have no parent.
        @param errstrm      a file stream to write error messages to.
        """
        object.__setattr__(self,'_parent', parentName)
        object.__setattr__(self,'_types', {})
        for attr in attrnames:
            object.__setattr__(self, attr, None)

    def setType(self, name, typ):
        if not self.__dict__.has_key(name):
            raise AttributeError(self._errmsg(name, 
                                              "No such property name defined"))
        if not callable(typ):
            raise ValueError(self._errmsg(name, "setType(): type not callable"))
        object.__getattribute__(self,'_types')[name] = typ

    def __setattr__(self, name, value):
        if not self.__dict__.has_key(name):
            raise AttributeError(self._errmsg(name, 
                                              "No such property name defined"))
        if isinstance(getattr(self, name), ConfigProperty):
            raise AttributeError(self._errmsg(name, 
                            "Cannot over-write property with sub-properties"))
        types = object.__getattribute__(self,'_types')
        if types.has_key(name):
            value = types[name](value)
        object.__setattr__(self, name, value)

    def _errmsg(self, name, msg):
        return "%s: %s" % (self._propName(name), msg)

    def _propName(self, name, strm=None):
        if strm is None:
            strm = StringIO()
        if self._parent:
            strm.write(self._parent)
            strm.write('.')
        strm.write(name)
        return strm.getvalue()

    def properties(self):
        out = self.__dict__.fromkeys(filter(lambda a: not a.startswith('_'), 
                                            self.__dict__.keys()))
        for k in out.keys():
            if isinstance(self.__dict__[k], ConfigProperty):
                out[k] = self.__dict__[k]._props()
            else:
                out[k] = self.__dict__[k]
        return out

    def __str__(self):
        return str(self._props())

def canPickle():
    """
    run a pickling test to see if python is late enough to allow EUPS to
    cache product info.
    """
    try:
        import cPickle
        cPickle.dump(None, None, protocol=2)
    except TypeError:
        return False
    except ImportError:
        return False

    return True

def createTempDir(path):
    """
    Create and return a temporary directory ending in some path.  

    Typically this path will be created under /tmp; however, this base
    directory is controlled by the python module, tempfile.

    @param path  the path to create a temporary directory for. 
    """
    tmpdir = os.path.dirname(tempfile.NamedTemporaryFile().name) # directory that tempfile's using
    path = re.sub(r"^/", "", path)      # os.path.join won't work if path is an absolute path

    path = os.path.join(tmpdir, "eups", path)
    #
    # We need to create this path, and set all directory permissions to 777
    # It'd be better to use a eups group, but this may be hard for some installations
    #
    if not os.path.isdir(path):
        dir = "/"
        for d in filter(lambda el: el, path.split(os.path.sep)):
            dir = os.path.join(dir, d)
            
            if not os.path.isdir(dir):
                os.mkdir(dir)
                os.chmod(dir, 0777)

    return path


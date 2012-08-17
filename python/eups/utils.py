"""
Utility functions used across EUPS classes.
"""
import time, os, sys, glob, re, shutil, tempfile
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

import os, re

def version():
    """Get the eups version from git; if this isn't available consult git.version in $EUPS_DIR"""

    eups_dir = os.environ.get("EUPS_DIR", ".")
    dot_git = os.path.join(eups_dir, ".git")
    dot_version = os.path.join(eups_dir, "git.version")
    
    if not os.path.exists(dot_git):
        if os.path.exists(dot_version):
            version = open(dot_version).readline().strip()
        else:
            version = "unknown"
            print >> stderr, \
                "Cannot guess version without .git directory or git.version file; version will be set to \"%s\"" % version
        return version

    version = os.popen("(cd %s; git describe --tags --always)" % eups_dir).readline().strip()

    status = os.popen("(cd %s; git status --porcelain --untracked-files=no)" % eups_dir).readline()
    if status.strip():
        print >> stdwarn, "Warning: EUPS source has uncommitted changes"
        version += "M"

    return version

def debug(*args, **kwargs):
    """
    Print args to stderr; useful while debugging as we source the stdout 
    when setting up.  Specify eol=False to suppress newline"""

    print >> stdinfo, "Debug:", # make sure that this routine is only used for debugging
    
    for a in args:
        print >> stdinfo, a,

    if kwargs.get("eol", True):
        print >> stdinfo

def deprecated(msg, quiet=False, strm=None):
    """
    Inform the user that an deprecated API was employed.  Currently, this is 
    done by printing a message, but in the future, it might raise an exception.
    @param msg     the message to print
    @param quiet   if true, this message will not be printed.  
    @param strm    the stream to write to (default: utils.stdinfo)
    """
    # Note quiet as bool converts transparently to int (0 or 1)
    if quiet < 0:  quiet = 0
    if not quiet:
        print >> stdinfo, "Warning:", msg

def dirEnvNameFor(productName):
    """
    return the name of the environment variable containing a product's
    root/installation directory.  This is of the form "product_DIR"
    """
    return productName.upper() + "_DIR"

def dirExtraEnvNameFor(productName):
    """
    return the name of the environment variable containing a product's
    extra root/installation directory.  This is of the form "product_DIR_EXTRA"
    """

    return dirEnvNameFor(productName) + "_EXTRA"

def extraDirPath(flavor, productName, versionName):
    """Return the path to the "extra dir", relative to EUPS_PATH/ups_db"""
    return os.path.join(flavor, productName, versionName)

def setupEnvPrefix():
    """Return the prefix used for the implementation-detail environment variable
    describing how the setup was carried out
    """
    return "SETUP_"

def setupEnvNameFor(productName):
    """
    return the name of the environment variable that provides the 
    setup information for a product.  This is of the form "setupEnvPrefix() + prod".
    """
    name = setupEnvPrefix() + productName

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

def defaultUserDataDir(user=""):
    """
    return the default user data directory.  This will be the value of 
    $EUPS_USERDATA if set; otherwise, it is ~/.eups. 
    """

    if not user and os.environ.has_key("EUPS_USERDATA"):
        userDataDir = os.environ["EUPS_USERDATA"]
    else:
        home = os.path.expanduser("~%s" % user)
        if home[0] == "~":              # failed to expand
            raise RuntimeError("%s doesn't appear to be a valid username" % user)
        userDataDir = os.path.join(home, ".eups")

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
       if re.search(r"(^x86_64|i386)$", mach):
           flav = "DarwinX86"
       else:
           flav = "Darwin"
    elif uname == "SunOS":
        if re.search(r"^sun4", mach):
            flav = "SunOS"
        else:
            flav = "SunOSX86"
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

        if os.path.exists(dir):
            raise RuntimeError, ("%s isn't a directory" % dir)
        else:
            raise RuntimeError, ("%s doesn't seem to exist" % dir)
            
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

def issamefile(file1, file2):
    """Are two files identical?"""

    try:
        return os.path.samefile(file1, file2)
    except OSError:
        pass

    return False

def copyfile(file1, file2):
    """Like shutil.copy2, but don't fail copying a file onto itself"""

    if issamefile(file1, file2):
        return

    try:
        os.unlink(file2)
    except OSError:
        pass

    shutil.copy2(file1, file2)


#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Color(object):
    classes = dict(
        OK    = "green",
        WARN  = "yellow",
        INFO  = "cyan",
        ERROR = "red",
        )

    colors = {
        "black"  : 0,
        "red"    : 1,
        "green"  : 2,
        "yellow" : 3,
        "blue"   : 4,
        "magenta": 5,
        "cyan"   : 6,
        "white"  : 7,
        }

    _colorize = False

    def __init__(self, text, color):
        """Return a string that should display as coloured on a conformant terminal"""
        self.rawText = str(text)
        x = color.lower().split(";")
        self.color, bold = x.pop(0), False
        if x:
            props = x.pop(0)
            if props in ("bold",):
                bold = True

        try:
            self._code = "%s" % (30 + Color.colors[self.color])
        except KeyError:
            raise RuntimeError("Unknown colour: %s" % self.color)

        if bold:
            self._code += ";1"

    def colorize(val=None):
        """Should I colour strings?  With an argument, set the value"""
        if val is not None:
            Color._colorize = val

            if isinstance(val, dict):
                unknown = []
                for k in val.keys():
                    if Color.classes.has_key(k):
                        try:
                            Color("foo", val[k]) # check if colour's valid
                            Color.classes[k] = val[k]
                        except RuntimeError, e:
                            print >> stderr, "Setting colour for %s: %s" % (k, e)
                    else:
                        unknown.append(k)

                if unknown:
                    print >> stderr, "Unknown colourizing class found in hooks: %s" % " ".join(unknown)

        return Color._colorize

    colorize = staticmethod(colorize)

    def __str__(self):
        if not self.colorize():
            return self.rawText

        base = "\033["

        prefix = base + self._code + "m"
        suffix = base + "m"

        return prefix + self.rawText + suffix
    
class coloredFile(object):
    """Like sys.stderr, but colourize text first"""

    def __init__(self, fileObj, cclass):
        """Write to file object fileObj, but colour according to cclass (e.g. "ERROR") if isatty"""
        self._fileObj = fileObj
        self._class = cclass
        self._isatty = hasattr(fileObj, 'fileno') and os.isatty(fileObj.fileno())

    def write(self, text):
        """Write text to fileObj"""

        if self._isatty:
            text = Color(text, Color.classes[self._class])

        self._fileObj.write(str(text))

    def flush(self):
        self._fileObj.flush()

stderr =  coloredFile(sys.stderr, "ERROR")
stdinfo = coloredFile(sys.stderr, "INFO")
stdwarn = coloredFile(sys.stderr, "WARN")
stdok =   coloredFile(sys.stderr, "OK")

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
"""
   Tarjan's algorithm and topological sorting implementation in Python

   by Paul Harrison

   Public domain, do with it as you will

"""

def stronglyConnectedComponents(graph):
    """ Find the strongly connected components in a graph using
        Tarjan's algorithm.

        graph should be a dictionary mapping node names to
        lists of successor nodes.
        """

    result = []
    stack = []
    low = {}

    def visit(node):
        if node in low: return

        num = len(low)
        low[node] = num
        stack_pos = len(stack)
        stack.append(node)

        for successor in graph[node]:
            visit(successor)
            low[node] = min(low[node], low[successor])

        if num == low[node]:
            component = tuple(stack[stack_pos:])
            del stack[stack_pos:]
            result.append(component)
            for item in component:
                low[item] = len(graph)

    for node in graph:
        visit(node)

    return result


def _topological_sort(graph):
    count = { }
    for node in graph:
        count[node] = 0
    for node in graph:
        for successor in graph[node]:
            count[successor] += 1

    ready = [ node for node in graph if count[node] == 0 ]

    result = [ ]
    while ready:
        node = ready.pop(-1)
        result.append(node)

        for successor in graph[node]:
            count[successor] -= 1
            if count[successor] == 0:
                ready.append(successor)

    return result


def topologicalSort(graph, verbose=False, checkCycles=False):
    """
    If checkCycles is True, throw RuntimeError if any cycles are detected

    From http://code.activestate.com/recipes/577413-topological-sort (but converted back to python 2.4)

    Author Paddy McCarthy, under the MIT license

    Returns a generator;
           print [str(t) for t in utils.topologicalSort(graph)]
    returns a list of keys, where the earlier elements sort _after_ the later ones.
    """

    for k, v in graph.items():
        graph[k] = set(v)

    for k, v in graph.items():
        v.discard(k) # Ignore self dependencies

    extra_items_in_deps = reduce(set.union, graph.values()) - set(graph.keys())
    for item in extra_items_in_deps:
        graph[item] = set()

    #
    # If there are strongly-connected components, make these components the keys
    # in the graph, not single elements
    #
    def name(p):
        """Return a p's name (if a Product), else str(p)"""
        try:
            return p.name
        except AttributeError:
            return str(p)

    def nameVersion(p):
        try:
            return "[%s %s]" % (p.name, p.version)
        except AttributeError:
            return str(p)


    components = stronglyConnectedComponents(graph)

    cycles = []
    for ccomp in components:
        if len(ccomp) > 1:
            cycles.append(ccomp)

    msg = []
    for ccomp in cycles:
        msg.append(", ".join([nameVersion(c) for c in ccomp]))

    if msg:
        msg = "(%s)" % ("), (".join(msg))

        if verbose:
            if len(msg) == 0:
                s = ""
            else:
                s = "s"
            print >> stdwarn, "Detected cycle%s: %s" % (s, msg)
            
        if checkCycles:
            raise RuntimeError("".join(msg))
    #
    # Rebuild the graph using tuples, so as to handle connected components
    #
    node_component = {}         # index for which component each node belongs in
    for component in components:
        for node in component:
            node_component[node] = component

    component_graph = {}        # our new graph, indexed by component
    for component in components:
        component_graph[component] = set()

    for node in graph:
        node_c = node_component[node]
        for successor in graph[node]:
            successor_c = node_component[successor]
            if node_c != successor_c: # here's where we break the cycle
                component_graph[node_c].add(successor_c)

    graph = component_graph

    while True:
        ordered = set(item for item, dep in graph.items() if not dep)
        if not ordered:
            break
        flattened_ordered = [p for comp in list(ordered)
                               for p    in comp]
        yield sorted(flattened_ordered)
        ngraph = {}
        for item, dep in graph.items():
            if item not in ordered:
                ngraph[item] = (dep - ordered)

        graph = ngraph; del ngraph

    if graph:
        raise RuntimeError("A cyclic dependency exists amongst %s" %
                           " ".join(sorted([name([x for x in p]) for p in graph.keys()])))

if __name__ == "__main__":
    data = {
        'des_system_lib':   set('std synopsys std_cell_lib des_system_lib dw02 dw01 ramlib ieee'.split()),
        'dw01':             set('ieee dw01 dware gtech'.split()),
        'dw02':             set('ieee dw02 dware'.split()),
        'dw03':             set('std synopsys dware dw03 dw02 dw01 ieee gtech'.split()),
        'dw04':             set('dw04 ieee dw01 dware gtech'.split()),
        'dw05':             set('dw05 ieee dware'.split()),
        'dw06':             set('dw06 ieee dware'.split()),
        'dw07':             set('ieee dware'.split()),
        'dware':            set('ieee dware'.split()),
        'gtech':            set('ieee gtech'.split()),
        'ramlib':           set('std ieee'.split()),
        'std_cell_lib':     set('ieee std_cell_lib'.split()),
        'synopsys':         set(),
        }
    data["dware"].add("dw03")
    print "\n".join([str(e) for e in topologicalSort(data, True)])

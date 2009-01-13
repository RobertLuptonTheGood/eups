# -*- python -*-
import glob, re, os, pwd, shutil, sys, time
import filecmp
import fnmatch
import cPickle
import tempfile
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
        and sys.argv, which you may modify;  cmd == argv[1] if len(argv) > 1 else None
        
        E.g.
        if cmd == "fetch":
            argv[1:2] = ["distrib", "install"]
        """
        CommandCallbacks.callbacks += [callback]

    def apply(self, cmd, argv, verbose=0):
        """Call the command callbacks on cmd, argv"""

        argv[0] = os.path.basename(argv[0])

        argv0 = argv[:]                 # used for helpful messages
        for hook in CommandCallbacks.callbacks:
            hook(cmd, argv)

        if verbose > 1 and argv != argv0:
            print >> sys.stderr, "Command hooks rewrote \"%s\" as \"%s\"" % \
                  (" ".join(argv0), " ".join(argv))

    def clear(self):
        """Clear the list of command callbacks"""
        CommandCallbacks.callbacks = []

    def list(self):
        for hook in CommandCallbacks.callbacks:
            print >> sys.stderr, hook

try:
    type(commandCallbacks)
except NameError:
    commandCallbacks = CommandCallbacks()

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class VersionCallbacks(object):
    """Callback to allow users to customize behaviour by defining hooks in EUPS_STARTUP
        and calling eups.versionCallbacks.add(hook)"""

    callbacks = []

    def __init__(self):
        pass

    def add(self, callback):
        """
        Add a version callback.
        
        The arguments are the two version strings, and the return value is the
        (maybe modified) versions that you prefer
        """
        VersionCallbacks.callbacks += [callback]

    def apply(self, v1, v2):
        """Call the version callbacks on v1, v2"""

        if v1:
            v1 = v1[:]
        if v2:
            v2 = v2[:]
        
        for hook in VersionCallbacks.callbacks:
            v1, v2 = hook(v1, v2)

        return v1, v2

    def clear(self):
        """Clear the list of version callbacks"""
        VersionCallbacks.callbacks = []

try:
    type(versionCallbacks)
except NameError:
    versionCallbacks = VersionCallbacks()

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

    versionString = r"$HeadURL: svn+ssh://svn.lsstcorp.org/eups/trunk/eups.py $"

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

def eupsTmpdir(path):
    """Create and return a directory somewhere in /tmp that ends with path

The path /tmp is not actually hardcoded;  use whatever tempfile uses
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

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def ctimeTZ(t=None):
    """Return a time with time zone"""

    if not t:
        t = time.localtime()

    return time.strftime("%Y/%m/%d %H:%M:%S %Z", t)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def defineValidSetupTypes(*types):
    """Define a permissible type of setup (e.g. build)"""
    global validSetupTypes

    if not types:
        validSetupTypes = []
    else:
        validSetupTypes += types

    #
    # Make tags unique (and don't use set as it isn't in python 2.3)
    #
    tmp = {}
    for t in validSetupTypes:
        tmp[t] = 1

    validSetupTypes = tmp.keys()
    validSetupTypes.sort()

def getValidSetupTypes():
    """Return (a copy of) all valid types of setup (e.g. build)"""
    return validSetupTypes[:]

def isValidSetupType(stype):
    """Is type of setup valid?"""
    return validSetupTypes.count(stype) > 0

defineValidSetupTypes()                      # reset list
defineValidSetupTypes("build")               # valid values of type

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

try:                                    # don't redefine _Current if we reload this file; object
                                        # identity is essential as we test Current() == Current()
    type(_Current)
except NameError:
    class _Current(object):
        """A class used to specify the current version (e.g. versionName=Current())"""
        _tags = {}

        def __init__(self, tag):
            if tag:
                tag = re.sub(r"^tag:", "", tag)
            self.tag = tag

        def __str__(self):
            return "tag:%s" % self.tag

        def filename(self):
            return "%s.chain" % self.tag
#
# Define which tag is used if we don't specify one
#
try:                                    # don't redefine setDefaultTag as it'd reset the default
    setDefaultTag                                        
except NameError:
    def setDefaultTag(tag=None):
        """Set the default tag (i.e. current)"""
        if tag:
            try:
                if isValidTag(tag):
                    setDefaultTag._tag = tag
                else:
                    raise RuntimeError, ("%s is not a valid tag" % tag)
            except NameError:           # isValidTag doesn't exist while sourcing this file, and Current() is called
                setDefaultTag._tag = tag

        return setDefaultTag._tag

    def getDefaultTag():
        """Return the current iterpretation of "current" """
        return setDefaultTag(None)

    setDefaultTag("current")                # the default-default tag is "current"

def Current(tag=None):
    """Factory function to return exactly one instantiation of each tag type of _Current"""

    if isinstance(tag, _Current):
        return tag

    if not tag:
        tag = getDefaultTag()

    if not _Current._tags.has_key(tag):
        _Current._tags[tag] = _Current(tag)

    return _Current._tags[tag]

def Setup():
    """Return the sole instantiation of a class used to specify the setup version (e.g. versionName=Setup())"""

    return Current("setup")

def isSpecialVersion(versionName, setup=True):
    """Is versionName special? If setup's False, treat Setup() as normal"""
    if versionName in _Current._tags.values():
        if setup and versionName == Setup():
            return False
        return True
    else:
        return False

class CurrentChain(object):
    """A class that represents a chain file"""

    def __init__(self,  Eups, productName=None, versionName=None, productDir=None, currentType=None):
        """Parse a current file; currentType (defaults to Eups.currentType) may specify that it is a file for some other tag (e.g. stable)"""
        
        self.file = None
        self.productName = productName
        self.current = None
        self.info = {}

        self._fields = [                # fields in output file, in order.  Values are in info[]
            "DECLARER",
            "DECLARED",
            "MODIFIER",
            "MODIFIED",
            ]

        if not isinstance(Eups, _ClassEups):
            filename = Eups          # really a filename
            assert not productName and not versionName and not productDir

            self._read(filename)
            return
        
        if not currentType:
            tag = Eups.currentType.tag
        elif not isinstance(currentType, str):
            tag = currentType.tag

        self.chain = tag
        #
        # We have to do the work ourselves
        #
        self.info[Eups.flavor] = {}
        self.info[Eups.flavor]["productDir"] = productDir
        self.info[Eups.flavor]["version"] = versionName

    def _read(self, currentFile):
        self.file = currentFile
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
            #
            # Ignore Group: and End:
            #
            elif re.search(r"^(End|Group)\s*:", line):
                continue
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

    def write(self, fd=sys.stdout):
        """Write a CurrentChain to a file"""

        print >> fd, """FILE = version
PRODUCT = %s
CHAIN = %s
#***************************************\
""" % (self.productName, self.chain)

        for fq in self.info.keys():
            mat = re.search(r"^([^:]+)(:?:(.*)$)?", fq)
            flavor = mat.group(1)
            qualifier = mat.group(2)
            if not qualifier:
                qualifier = ""

            print >> fd, """
#Group:
   FLAVOR = %s
   VERSION = %s
   QUALIFIERS = "%s"\
""" % (flavor, self.info[flavor]["version"], qualifier)

            for field in self._fields:
                k = field.lower()

                if self.info[fq].has_key(k):
                    value = self.info[fq][k]
                    if not value:
                        continue

                    print >> fd, "   %s = %s" % (field.upper(), value)

            print >> fd, "#End:"

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

    def merge(self, old, who):
        """Merge old CurrentChain into this one; set modifier to who"""

        if not old:
            return

        assert isinstance(old, CurrentChain)

        if not (self.productName == old.productName):
            raise RuntimeError, ("Product must be identical to merge CurrentChains; saw %s and %s" % \
                                 (self.productName, old.productName))
        #
        # Make a copy of the old info
        #
        self_info = old.info.copy()
        for flavor in old.info.keys():
            self_info[flavor] = old.info[flavor].copy()
        #
        # Overwrite the copy of the old with the new info (but handle declare[rd] and modifie[rd] specially)
        #
        for flavor in self.info.keys():
            if not self_info.has_key(flavor):
                self_info[flavor] = {}

            for k in self.info[flavor].keys():
                if k not in ["declared", "declarer"]:
                    self_info[flavor][k] = self.info[flavor][k]

            self_info[flavor]["modifier"] = who
            self_info[flavor]["modified"] = ctimeTZ()
        #
        # And update self.info
        #
        self.info = self_info
    
    def remove(self, unwanted):
        """Remove flavors in unwanted from self"""
        
        if not unwanted:
            return

        assert isinstance(unwanted, CurrentChain)

        if not (self.productName == unwanted.productName):
            raise RuntimeError, ("Product must be identical to merge CurrentChains; saw %s and %s" % \
                                 (self.productName, unwanted.productName))

        for flavor in unwanted.info.keys():
            if self.info.has_key(flavor):
                del self.info[flavor]

        return self
    
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class ValidTag(object):
    """A valid tag"""

    def __init__(self, tag, fallbackTags=None):
        self.tag = tag
        if not fallbackTags:
            fallbackTags = []
        self.fallbackTags = fallbackTags

def defineValidTag(tag=None, fallbackTags=[Current()]):
    """Define a permissible tag name (e.g. stable), and a list of tags to check if the tag can't be found.

    If tag is None, reset the list of valid tags to empty
    """
    global validTags

    if fallbackTags:
        if isinstance(fallbackTags, str):
            fallbackTags = [fallbackTags]
            
        for i in range(len(fallbackTags)):
            if isinstance(fallbackTags[i], str):
                fallbackTags[i] = Current(fallbackTags[i])

    if not tag:
        validTags = {}
    else:
        validTags[tag] = ValidTag(tag, fallbackTags)

def defineValidTags(*tags):
    """Backwards compatibility to define a set of tags;  note that these tags fallback only to Current()"""
    for t in tags:
        defineValidTag(t)

def getValidTags():
    """Return (a copy of) all valid tags"""

    vtags = validTags.keys()
    vtags.sort()

    return vtags

def getValidTagFallbacks(tag):
    try:
        return validTags[tag].fallbackTags
    except KeyError:
        return []

def isValidTag(tag):
    """Is tag valid?"""

    if isinstance(tag, _Current):
        tag = tag.tag
        
    return validTags.has_key(tag)

def checkValidTag(tag):
    """Check if tag is valid, returning the tag if so (and raising RuntimeError if it isn't)"""
    if tag and not isValidTag(tag):
        raise RuntimeError, "\"%s\" is not a valid tag; please choose one of \"%s\"" % (tag, '" "'.join(getValidTags()))

    return tag

defineValidTag()                       # reset list
defineValidTag("current") 
defineValidTag("stable", ["beta"]) 

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def _isRealFilename(filename):
    """Return True iff \"filename\" is a real filename, not a placeholder.  It need not exist"""

    if filename is None:
        return False
    elif filename in ("none", "???"):
        return False
    else:
        return True
    
class Table(object):
    """A class that represents a eups table file"""

    def __init__(self, tableFile):
        """Parse a tablefile"""

        self.file = tableFile
        self.old = False
        self._actions = []

        if _isRealFilename(tableFile):
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
                    if False:
                        raise RuntimeError, \
                              ("Unsupported qualifiers \"%s\" at %s:%d" % (mat.group(1), self.file, lineNo))
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

                    value = re.sub(r"\${PRODUCTS}", product.db, value)

                    if re.search(r"\${PRODUCT_DIR}", value):
                        if product.dir:
                            value = re.sub(r"\${PRODUCT_DIR}", product.dir, value)
                        else:
                            print >> sys.stderr, "Unable to expand PRODUCT_DIR in %s" % self.file

                    value = re.sub(r"\${PRODUCT_FLAVOR}", product.Eups.flavor, value)
                    value = re.sub(r"\${PRODUCT_NAME}", product.name, value)
                    if re.search(r"\${PRODUCT_VERSION}", value):
                        if product.version:
                            value = re.sub(r"\${PRODUCT_VERSION}", product.version, value)
                        else:
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
                    raise RuntimeError, ("%s expected 2 (or 3) arguments, saw %s at %s:%d" % (cmd, " ".join(args), self.file, lineNo))
            elif cmd == Action.envSet:
                if len(args) < 2:
                    raise RuntimeError, ("%s expected 2 arguments, saw %s at %s:%d" % (cmd, " ".join(args), self.file, lineNo))
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
            parser = eupsParser.Parser(logical)
            parser.define("flavor", flavor)
            if setupType:
                parser.define("type", setupType)

            if parser.eval():
                actions += block

        if actions:
            return actions
        else:
            raise RuntimeError, ("Table %s has no entry for flavor %s" % (self.file, flavor))

    def __str__(self):
        s = ""
        for logical, block in self._actions:
            s += "\n------------------"
            s += '\n' + str(logical)
            for a in block:
                s += '\n' + str(a)

        return s

    def dependencies(self, Eups, eupsPathDirs=None, recursive=False, recursionDepth=0, setupType=None):
        """Return self's dependencies as a list of (Product, optional, currentRequested) tuples

        N.b. the dependencies are not calculated recursively unless recursive is True"""

        deps = []
        for a in self.actions(Eups.flavor, setupType=setupType):
            if a.cmd == Action.setupRequired:
                try:
                    args = a.args[:]
                    if len(args) == 1:
                        args = (args[0], Current())
                        currentRequested = True
                    else:
                        otherArgs = " ".join(args[1:])

                        mat = re.search(r"(.*)\s+\[([^\]]+)\]\s*", otherArgs)
                        if mat:
                            exactVersion, logicalVersion = mat.groups()
                            if Eups.exact_version:
                                otherArgs = exactVersion
                            else:
                                otherArgs = logicalVersion

                        args = (args[0], otherArgs)
                        currentRequested = False
                    try:
                        product = Eups.getProduct(args[0], args[1], eupsPathDirs)
                    except RuntimeError, e:
                        product = Product(Eups, args[0], args[1], noInit=True)
                        pass

                    val = [product, a.extra, currentRequested]
                    if recursive:
                        val += [recursionDepth]
                    deps += [val]

                    if recursive:
                        deps += product.dependencies(eupsPathDirs, True, recursionDepth+1)
                        
                except RuntimeError, e:
                    if a.extra:         # product is optional
                        continue

                    raise

        return deps

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Action(object):
    """An action in a table file"""

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
            vers = Current()

        if not isSpecialVersion(vers):  # see if we have a version of the form "logical [exact]"
            mat = re.search(r"(.*)\s+\[([^\]]+)\]\s*", vers)
            if mat:
                exactVersion, logicalVersion = mat.groups()
                if Eups.exact_version:
                    vers = exactVersion
                else:
                    vers = logicalVersion

        productOK, vers, reason = Eups.setup(productName, vers, fwd, recursionDepth)
        if not productOK and fwd:
            if optional:                # setup the pre-existing version (if any)
                try:
                    product = Eups.Product(productName, noInit=True).initFromSetupVersion(Eups.oldEnviron)
                    q = Quiet(Eups)
                    productOK, vers, reason = Eups.setup(productName, product.version, fwd, recursionDepth)
                    del q
                    if productOK:
                        if Eups.verbose > 0:
                            print >> sys.stderr, "            %sKept previously setup %s %s" % \
                                  (recursionDepth*" ", product.name, product.version)
                    else:
                        #debug(reason)
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

class VersionFile(object):
    """A class that represents a version file"""

    def __init__(self, Eups, productName=None, versionName=None, productDir=None, tablefile=None, ups_dir=None):
        """If argument Eups is actually a file, it's a version file to be parsed,
        otherwise create a Version for the specified product

        If tablefile is None, use productName.table"""

        self.productName = productName
        self.version = versionName
        self.file = None
        self.info = {}

        self._fields = [                # fields in output file, in order.  Values are in info[]
            "DECLARER",
            "DECLARED",
            "MODIFIER",
            "MODIFIED",
            "PROD_DIR",
            "UPS_DIR",
            "TABLE_FILE",
            ]

        if not isinstance(Eups, _ClassEups):
            filename = Eups             # really a filename
            assert not productName and not versionName and not productDir

            self._read(filename)

            return
        #
        # We have to do the work ourselves
        #
        if tablefile is None:
            tablefile = "%s.table" % productName

        self.info[Eups.flavor] = {
            "productDir" : productDir,
            "declarer" : Eups.who,
            "declared" : ctimeTZ(),
            "table_file" : tablefile,
            }
        if ups_dir:
            self.info[Eups.flavor]["ups_dir"] = ups_dir
        
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
            # Ignore Group: and End:, but check for needed fields.
            #
            # N.b. End is sometimes omitted, so a Group opens a new group
            #
            if re.search(r"^(End|Group)\s*:", line):
                if flavor:
                    if not self.info[flavor].has_key("productDir"):
                        print >> sys.stderr, "Corrupt version file %s: product %s %s has no PROD_DIR for %s" % \
                              (versionFile, self.productName, self.version, flavor)

                        self.info[flavor]["productDir"] = "none"

                    if not self.info[flavor].has_key("table_file"):
                        print >> sys.stderr, "Corrupt version file %s: product %s %s has no TABLE_FILE for %s" % \
                              (versionFile, self.productName, self.version, flavor)

                        self.info[flavor]["table_file"] = "none"

                    tablefile = self.info[flavor]["table_file"]
                    if not self.info[flavor].has_key("ups_dir") and _isRealFilename(tablefile):
                        if tablefile != ("%s.table" % self.productName) and not os.path.isabs(tablefile):
                            print >> sys.stderr, "You must specify UPS_DIR if you specify tablefile == %s" % tablefile
                        self.info[flavor]["ups_dir"] = "ups"

                continue
            #
            # Get key = value
            #
            mat = re.search(r"^(\w+)\s*=\s*(.*)", line, re.IGNORECASE)
            if mat:
                key = mat.group(1).lower()
                if key == "prod_dir":
                    key = "productDir"

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

    def merge(self, old, who):
        """Merge old Version into this one; set modifier to who"""

        if not old:
            return

        assert isinstance(old, VersionFile)

        if not (self.productName == old.productName and self.version == old.version):
            raise RuntimeError, ("Product and version must be identical to merge Versions; saw %s %s and %s %s" % \
                                 (self.productName, self.version, old.productName, old.version))
        #
        # Make a copy of the old info
        #
        self_info = old.info.copy()
        for flavor in old.info.keys():
            self_info[flavor] = old.info[flavor].copy()
        #
        # Overwrite the copy of the old with the new info (but handle declare[rd] and modifie[rd] specially)
        #
        for flavor in self.info.keys():
            if not self_info.has_key(flavor):
                self_info[flavor] = {}

            for k in self.info[flavor].keys():
                if k not in ["declared", "declarer"]:
                    self_info[flavor][k] = self.info[flavor][k]

            self_info[flavor]["modifier"] = who
            self_info[flavor]["modified"] = ctimeTZ()
        #
        # And update self.info
        #
        self.info = self_info

    def remove(self, unwanted):
        """Remove flavors in unwanted from self"""
        
        if not unwanted:
            return

        assert isinstance(unwanted, VersionFile)

        if not (self.productName == unwanted.productName):
            raise RuntimeError, ("Product must be identical to merge VersionFiles; saw %s and %s" % \
                                 (self.productName, unwanted.productName))

        for flavor in unwanted.info.keys():
            if self.info.has_key(flavor):
                del self.info[flavor]

        return self

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

    def write(self, fd=sys.stdout):
        """Write a Version to a file"""

        print >> fd, """FILE = version
PRODUCT = %s
VERSION = %s
#***************************************\
""" % (self.productName, self.version)

        for fq in self.info.keys():
            mat = re.search(r"^([^:]+)(:?:(.*)$)?", fq)
            flavor = mat.group(1)
            qualifier = mat.group(2)
            if not qualifier:
                qualifier = ""

            print >> fd, """
Group:
   FLAVOR = %s
   QUALIFIERS = "%s"\
""" % (flavor, qualifier)

            for field in self._fields:
                if field == "PROD_DIR":
                    k = "productDir"
                else:
                    k = field.lower()

                if self.info[fq].has_key(k):
                    value = self.info[fq][k]
                    if not value:
                        if k == "productDir":
                            value = "none"
                        elif k == "table_file":
                            #debug("Setting table_file")
                            value = "none"
                        else:
                            continue

                    print >> fd, "   %s = %s" % (field.upper(), value)

        print >> fd, "End:"
        
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Product(object):
    """Represent a version of a product"""

    def __init__(self, Eups, productName=None, version=None, noInit=False, eupsPathDirs=None):
        """Initialize a Product with the specified product and (maybe) version,
        using the eups parameters"""
        self.Eups = Eups

        self.name = productName         # product's name
        self.version = version          # product's version
        self.db = None                  # ups_db that we found the product in
        self.dir = None                 # product's directory
        self.table = None               # product's Table
        self._current = {}              # is product current? A dictionary as "current" might mean "stable" or ...

        if eupsPathDirs and isinstance(eupsPathDirs, str):
            eupsPathDirs = [eupsPathDirs]

        if eupsPathDirs and len(eupsPathDirs) == 1:
            self.db = eupsPathDirs[0]

        if self.name and not noInit:
            try:
                mat = re.search(r"^LOCAL:(.*)", version)
            except TypeError:
                mat = None
                
            if mat:                     # a local setup
                productDir = mat.group(1)
                self.initFromDirectory(productDir)
            else:
                self.version, self.db, self.dir, tablefile = \
                              self.Eups.findVersion(productName, version, eupsPathDirs=eupsPathDirs)
                self.table = Table(tablefile).expandEupsVariables(self)

    def init(self, versionName, flavor, eupsPathDir):
        """Initialize a Product given full information about a product"""

        if self.name == "eups" and not eupsPathDir: # eups was setup by sourcing setups.[c]sh
            self.version = versionName
            return
        
        mat = not isSpecialVersion(versionName) and re.search(r"^LOCAL:(.*)", versionName)
        if mat:
            productDir = mat.group(1)
            self.initFromDirectory(productDir)
        else:
            try:
                product = self.Eups.getProduct(self.name, versionName, eupsPathDir)
                self.version, self.db, self.dir, self.table = product.version, product.db, product.dir, product.table
                return
            except RuntimeError, e:
                pass

            self.version, self.db, self.dir, tablefile = \
                          self.Eups.findFullySpecifiedVersion(self.name, versionName, flavor, eupsPathDir)
            self.table = Table(tablefile).expandEupsVariables(self)

    def initFromSetupVersion(self, environ=None):
        """Initialize a Product that's already setup"""

        versionName, eupsPathDir, productDir, tablefile, flavor = self.getSetupVersion(environ)
        if not versionName:
            raise RuntimeError, ("%s is not setup" % self.name)

        self.init(versionName, flavor, eupsPathDir)

        return self

    def tableFileName(self):
        """Return a fully qualified tablefile name"""

        if not self.name and self.dir:
            try:
                self.name = guessProduct(os.path.join(self.dir, "ups"))
            except RuntimeError:
                pass

        if self.name:
            return os.path.join(self.dir, "ups", "%s.table" % self.name)
        else:
            return None

    def currentFileName(self, currentType=None, all=False):
        """Return a tag's chain file's fully qualified name; if all is true, return list of all chain files"""

        if not currentType:
            currentType = self.Eups.currentType

        dir = os.path.join(self.Eups.getUpsDB(self.db), self.name)
        if all:
            return glob.glob(os.path.join(dir, "*.chain"))
        else:
            return os.path.join(dir, currentType.filename())

    def versionFileName(self):
        """Return a fully qualified versionfile name"""

        return os.path.join(self.Eups.getUpsDB(self.db), self.name, "%s.version" % self.version)
        
    def initFromDirectory(self, productDir):
        """Initialize product given only its directory.  This is needed for
        LOCAL setups, as well as eups which can be initialised by sourcing setups.c?sh rather
        than via a setup command; in the former case it needn't even be declared to eups"""

        self.version = "LOCAL:" + productDir
        self.Eups.localVersions[self.name] = productDir
        self.db = "(none)"
        self.dir = productDir
        self.table = Table(self.tableFileName()).expandEupsVariables(self)
        
    def __str__(self):
        if self.Eups:
            flavor = self.Eups.flavor
        else:
            flavor = getFlavor()
        s = ""
        s += "%s %s -f %s -Z %s" % (self.name, self.version, flavor, self.db)

        return s

    def envarDirName(self):
        """Return the name of the product directory's environment variable"""
        return self.name.upper() + "_DIR"

    def envarSetupName(self):
        """Return the name of the product's how-I-was-setup environment variable"""
        name = "SETUP_" + self.name

        if os.environ.has_key(name):
            return name                 # exact match

        envNames = filter(lambda k: re.search(r"^%s$" % name, k, re.IGNORECASE), os.environ.keys())
        if envNames:
            return envNames[0]
        else:
            return name.upper()

    def getSetupVersion(self, environ=None):
        """Return the version, eupsPathDir, productDir, tablefile, and flavor for an already-setup product"""

        return self.Eups.findSetupVersion(self.name, environ)

    def checkCurrent(self, isCurrent=None, currentType=None):
        """check if product is current.  This shouldn't be needed if update the db when declaring products"""

        if not currentType:
            currentType = self.Eups.currentType

        if isCurrent != None:
            self._current[currentType] = isCurrent
        else:
            self._current[currentType] = None
            try:
                cdb, cversion, cvinfo = self.Eups.findCurrentVersion(self.name,
                                                                     currentType=currentType, currentTypesToTry=[])
                if cdb == self.db and cversion == self.version:
                    self._current[currentType] = currentType
            except RuntimeError:
                pass

        return self._current[currentType]

    def isCurrent(self):
        """Is the Product current?"""
        return self._current[self.Eups.currentType]

    def dependencies(self, eupsPathDirs=None, recursive=False, recursionDepth=0, setupType=None):
        """Return self's dependencies as a list of (Product, optional, currentRequested) tuples"""

        val = []
        if not recursive:
            val += [(self, False, False)]
            
        if self.table:
            val += self.table.dependencies(self.Eups, eupsPathDirs, recursive=recursive,
                                           recursionDepth=recursionDepth, setupType=setupType)

        return val

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Quiet(object):
    """A class whose members, while they exist, make Eups quieter"""

    def __init__(self, Eups):
        self.Eups = Eups
        self.Eups.quiet += 1

    def __del__(self):
        self.Eups.quiet -= 1

class Eups(object):
    """Control eups"""

    cacheVersion = "1.1"                # revision number for cache; must match
    def __init__(self, flavor=None, path=None, dbz=None, root=None, readCache=True,
                 shell=None, verbose=False, quiet=0,
                 noaction=False, force=False, ignore_versions=False, exact_version=False,
                 keep=False, max_depth=-1, currentType=Current()):
                 
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
            elif re.search(r"(^|/)(zsh)$", shell):
                shell = "zsh"
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
            os.environ["EUPS_PATH"] = ":".join(path)

        self.path = []
        for p in path:
            if not os.path.isdir(p):
                print >> sys.stderr, \
                      "%s in $EUPS_PATH does not contain a ups_db directory, and is being ignored" % p
                continue

            self.path += [os.path.normpath(p)]

        if not self.path and not root:
            if dbz:
                raise RuntimeError, ("No element of EUPS_PATH matches \"%s\"" % dbz)
            else:
                raise RuntimeError, ("No EUPS_PATH is defined")

        self.oldEnviron = os.environ.copy() # the initial version of the environment

        self.aliases = {}               # aliases that we should set
        self.oldAliases = {}            # initial value of aliases.  This is a bit of a fake, as we
                                        # don't know how to set it but (un)?setAlias knows how to handle this

        self.who = re.sub(r",.*", "", pwd.getpwuid(os.getuid())[4])

        if root:
            root = re.sub(r"^~", os.environ["HOME"], root)
            if not os.path.isabs(root):
                root = os.path.join(os.getcwd(), root)
            root = os.path.normpath(root)
            
        self.root = root

        self.setCurrentType(currentType)
        self.quiet = quiet
        self.keep = keep
        self.noaction = noaction
        self.force = force
        self.ignore_versions = ignore_versions
        self.exact_version = exact_version
        self.max_depth = max_depth      # == 0 => only setup toplevel package

        self.locallyCurrent = {}        # products declared local only within self

        self._msgs = {}                 # used to suppress messages
        self._msgs["setup"] = {}        # used to suppress messages about setups
        #
        # Read the cached version information
        #
        self.versions = {}
        for p in self.path:
            self.versions[p] = {}

        self.readCache = readCache

        if readCache:
            for p in self.path:
                self.readDB(p)
        #
        # Find locally-setup products in the environment
        #
        self.localVersions = {}

        q = Quiet(self)
        for product in self.getSetupProducts():
            try:
                if re.search(r"^LOCAL:", product.version):
                    self.localVersions[product.name] = os.environ[product.envarDirName()]
            except TypeError:
                pass

    def setCurrentType(self, currentType):
        """Set type of "Current" we want (e.g. current, stable, ...)"""

        if not currentType:
            currentType = Current()

        self.currentType = currentType  # our Current type
        # list of currentTypes to try if this one fails
        self.currentTypesToTry = getValidTagFallbacks(currentType.tag)

    def Product(self, *args, **kwargs):
        """Create a Product"""
        return Product(self, *args, **kwargs)
    
    def getPersistentDB(self, p):
        """Get the name of the persistent database given a toplevel directory"""
        return os.path.join(self.getUpsDB(p), "%s.%s" % (self.flavor, "pickleDB"))

    def getLockfile(self, path, upsDB=True):
        """Get the name of the lockfile given a toplevel directory"""
        if upsDB:
            path = self.getUpsDB(path)
        #
        # Create lockfile in /tmp (or other chosen temporary directory)
        # 
        path = eupsTmpdir(path)

        return os.path.join(path, ".lock")

    def lockDB(self, path, force=False, upsDB=True):
        """Return a lock for a DB in path; if upsDB is false, the directory p itself will be locked"""

        return eupsLock.Lock(self.getLockfile(path, upsDB), self.who, max_wait=10, force=force,
                             verbose=self.verbose, noaction=self.noaction)

    def unlinkDB(self, eupsPathDir):
        """Delete a persistentDB"""
        
        persistentDB = self.getPersistentDB(eupsPathDir)

        if not os.path.exists(persistentDB):
            return

        lock = self.lockDB(eupsPathDir)

        if self.noaction:
            print >> sys.stderr, "rm %s" % persistentDB
        else:
            os.unlink(persistentDB)

    def getCacheInfo(self, eupsPathDir):
        """Return information about a cached DB"""

        persistentDB = self.getPersistentDB(eupsPathDir)

        if not os.path.exists(persistentDB):
            return persistentDB, False, False

        db_mtime = os.stat(persistentDB).st_mtime # last modification date for cache

        for dirpath, dirnames, filenames in os.walk(self.getUpsDB(eupsPathDir)):
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

    def readDB(self, eupsPathDir):
        """Read a saved version DB from persistentDB"""
        
        persistentDB, exists, upToDate = self.getCacheInfo(eupsPathDir)

        if not exists or not upToDate:
            if self.verbose:
                if not exists:
                    reason, verb = "doesn't exist", "build"
                else:
                    reason, verb = "is out of date", "rebuild"
                print >> sys.stderr, "Product cache in %s %s; I'm %sing it for you" % \
                      (self.getUpsDB(eupsPathDir), reason, verb)
                
            self.buildCache(eupsPathDir)
            return

        lock = self.lockDB(eupsPathDir)

        if self.verbose > 3:
            print >> sys.stderr, "Reading %s" % persistentDB

        try:
            fd = open(persistentDB)
            unpickled = cPickle.Unpickler(fd)
        except Exception, e:
            msg = "Corrupted cache in %s: %s" % (eupsPathDir, e)
            print >> sys.stderr, msg
            raise RuntimeError(e)

        try:
            type(self.versions)
        except:
            self.versions = {}

        try:
            versions = {eupsPathDir : unpickled.load()}
        except Exception, e:
            msg = "Corrupted cache in %s: %s" % (eupsPathDir, e)
            print >> sys.stderr, msg
            raise RuntimeError(e)
        
        for db in versions.keys():      # i.e. eupsPathDir
            if not self.versions.has_key(db):
                self.versions[db] = {}

            for flavor in versions[db].keys():
                if flavor == "version":
                    cacheVersion = versions[db][flavor]

                    if cacheVersion != Eups.cacheVersion:
                        raise RuntimeError, \
                              ("Saw cache version %s (expected %s) in %s; please run \"eups admin buildCache\"" % 
                               (cacheVersion, Eups.cacheVersion, eupsPathDir))

                    self.versions[db][flavor] = cacheVersion

                    continue

                if not self.versions[db].has_key(flavor):
                    self.versions[db][flavor] = {}

                for p in versions[db][flavor].keys():
                    if not self.versions[db][flavor].has_key(p):
                        self.versions[db][flavor][p] = {}

                        for v in versions[db][flavor][p]:
                            self.versions[db][flavor][p][v] = versions[db][flavor][p][v]
                            #
                            # Convert old-style caches
                            #
                            if True:
                                prod = self.versions[db][flavor][p][v]

                                if isinstance(prod._current, bool): # old style _current, pre #523 changes
                                    tmp = prod._current
                                    prod._current = {}
                                    prod.currentType = Current()
                                    prod._current[prod.currentType] = tmp
                            
    
    def writeDB(self, eupsPathDir, force=False):
        """Write eupsPathDir's version DB to a persistent DB"""

        try:
            cPickle.dump(None, None, protocol=2) # does this version of python support protocol?
                                        # find out before we trash the cache
        except TypeError:
            if not self._msgs.has_key("cache"):
                self._msgs["cache"] = {}
                
            if not self._msgs["cache"].has_key("nowrite"):
                self._msgs["cache"]["nowrite"] = True
                
                print >> sys.stderr, "Not writing cache as your version of python's cPickle is too old"

            return

        if not force and not self.readCache:
            if self.verbose > 2:
                print >> sys.stderr, "Not writing cache for %s as I didn't read it" % eupsPathDir
            return

        if isinstance(eupsPathDir, str):
            try:
                versions = self.versions[eupsPathDir][self.flavor]
            except KeyError:
                return

            persistentDB = self.getPersistentDB(eupsPathDir)
            
            persistentDBDir = os.path.dirname(persistentDB)
            if not os.path.isdir(persistentDBDir):
                os.makedirs(persistentDBDir)

            self.versions[eupsPathDir]["version"] = Eups.cacheVersion

            lock = self.lockDB(eupsPathDir)
            try:
                fd = open(persistentDB, "w")
                cPickle.dump(self.versions[eupsPathDir], fd, protocol=2)
            except Exception, e:
                print >> sys.stderr, e
                raise
        else:
            for p in eupsPathDir:
                self.writeDB(p, force)

    def clearCache(self):
        """Clear the products cache"""
        for p in self.path:
            self.unlinkDB(p)

        self.versions = {}
            
    def listCache(self):
        """List all the products in the cache"""

        if not self.readCache:
            self.readCache = True
            for db in self.path:
                self.readDB(db)

        if not self.versions:
            return

        for db in self.path:
            try:
                productNames = self.versions[db][self.flavor].keys()
                productNames.sort()

                if self.verbose:
                    colon = ":"
                else:
                    colon = ""

                print "%-30s (%d products) [cache version %s]%s" % (db, len(productNames),
                                                                    self.versions[db].get("version", "unknown"), colon)

                if not self.verbose:
                    continue

                for productName in productNames:
                    versionNames = self.versions[db][self.flavor][productName].keys()
                    versionNames.sort(self.version_cmp)

                    print "  %-20s %s" % (productName, " ".join(versionNames))
            except IndexError, e:
                pass
            
    def clearLocks(self):
        """Clear all lock files"""

        for p in self.path:
            lockfile = self.getLockfile(p)
            if os.path.exists(lockfile):
                try:
                    os.remove(lockfile)
                except Exception, e:
                    print >> sys.stderr, ("Error deleting %s: %s" % (lockfile, e))

    def getUpsDB(self, eupsPathDir):
        """Return the ups database directory given a directory from self.path"""
        
        return os.path.join(eupsPathDir, "ups_db")
    
    def getSetupProducts(self, requestedProductName=None):
        """Return a list of all Products that are currently setup (or just the specified product)"""

        re_setup = re.compile(r"^SETUP_(\w+)$")

        productList = []

        for key in filter(lambda k: re.search(re_setup, k), os.environ.keys()):
            try:
                productName = os.environ[key].split()[0]
            except IndexError:          # Oh dear;  $SETUP_productName must be malformed
                continue

            if requestedProductName and productName != requestedProductName:
                continue

            try:
                product = self.Product(productName, noInit=True).initFromSetupVersion()
            except RuntimeError, e:
                if not self.quiet:
                    print >> sys.stderr, e
                continue

            productList += [product]

        return productList
        
    def setEnv(self, key, val, interpolateEnv=False):
        """Set an environmental variable"""
            
        if interpolateEnv:              # replace ${ENV} by its value if known
            val = re.sub(r"(\${([^}]*)})", lambda x : os.environ.get(x.group(2), x.group(1)), val)

        if val == None:
            val = ""
        os.environ[key] = val

    def unsetEnv(self, key):
        """Unset an environmental variable"""

        if os.environ.has_key(key):
            del os.environ[key]

    def setAlias(self, key, val):
        """Set an alias.  The value is in sh syntax --- we'll mangle it for csh later"""

        self.aliases[key] = val

    def unsetAlias(self, key):
        """Unset an alias"""

        if self.aliases.has_key(key):
            del self.aliases[key]
        self.oldAliases[key] = None # so it'll be deleted if no new alias is defined

    def findCurrentVersion(self, productName, path=None, currentType=None, currentTypesToTry=None):
        """Find current version of a product, returning eupsPathDir, version, vinfo"""

        if not currentType:
            currentType = self.currentType
        if currentTypesToTry is None:
            currentTypesToTry = self.currentTypesToTry

        if currentType == Current() and self.locallyCurrent.has_key(productName):
            versionName = self.locallyCurrent[productName]
            
            try:
                info = self.findVersion(productName, versionName)
            except RuntimeError, e:
                return [None, versionName, None]

            vinfo = { "productDir" : info[2], "table_file" : None }
            return [info[1], self.locallyCurrent[productName], vinfo]
        
        if not path:
            path = self.path
        elif isinstance(path, str):
            path = [path]

        vinfo = None
        for eupsPathDir in path:
            ups_db = self.getUpsDB(eupsPathDir)

            cfile = os.path.join(ups_db, productName, currentType.filename())
            if os.path.exists(cfile):
                try:
                    versionName = CurrentChain(cfile).info[self.flavor]["version"]

                    vfile = os.path.join(ups_db, productName, "%s.version" % versionName)
                    if os.path.exists(vfile):
                        vers = VersionFile(vfile)
                        if vers.info.has_key(self.flavor):
                            vinfo = vers.info[self.flavor]
                            return eupsPathDir, versionName, vinfo

                    raise RuntimeError, ("Unable to find current version %s of %s for flavor %s" %
                                         (versionName, productName, self.flavor))
                except KeyError:
                    pass                # not current in this eupsPathDir

        if not vinfo:                   # no currentType version is available
            for otherCurrentType in currentTypesToTry:
                if otherCurrentType == currentType: # we've tried this one already
                    continue
                try:
                    if not isValidTag(currentType) or self.verbose > 2:
                        print >> sys.stderr, "Unable to locate a %s version of %s, trying %s" % \
                              (currentType.tag, productName, otherCurrentType)

                    vers = self.findCurrentVersion(productName, path=path,
                                                   currentType=otherCurrentType, currentTypesToTry=[])

                    if not self.quiet and self.verbose > 1:
                        print >> sys.stderr, "Unable to locate a %s version of %s, using %s" % \
                              (currentType.tag, productName, otherCurrentType)

                    return vers
                except RuntimeError:
                    pass

            raise RuntimeError, \
                  ("Unable to locate a %s version of %s for flavor %s" %
                   (currentType.tag, productName, self.flavor))

    def findSetupVersion(self, productName, environ=None):
        """Find setup version of a product, returning the version, eupsPathDir, productDir, None (for tablefile), and flavor
        If environ is specified search it for environment variables; otherwise look in os.environ
        """

        if not environ:
            environ = os.environ

        product = self.Product(productName, noInit=True)

        versionName, eupsPathDir, productDir, tablefile, flavor = Setup(), None, None, None, None
        try:
            args = environ[product.envarSetupName()].split()
        except KeyError:
            return None, eupsPathDir, productDir, tablefile, flavor

        try:
            sproductName = args.pop(0)
        except IndexError:          # Oh dear;  $SETUP_productName must be malformed
            return None, eupsPathDir, productDir, tablefile, flavor
            
        if sproductName != productName:
            if self.verbose > 1:
                print >> sys.stderr, \
                      "Warning: product name %s != %s (probable mix of old and new eups)" %(productName, sproductName)

        if productName == "eups" and not args: # you can get here if you initialised eups by sourcing setups.c?sh
            args = ["LOCAL:%s" % environ["EUPS_DIR"], "-Z", "(none)"]

        if len(args) > 0 and args[0] != "-f":
            versionName = args.pop(0)

        if len(args) > 1 and args[0] == "-f":
            args.pop(0);  flavor = args.pop(0)

        if len(args) > 1 and args[0] == "-Z":
            args.pop(0);  eupsPathDir = args.pop(0)

        assert not args

        if isSpecialVersion(versionName, setup=False):
            q = Quiet(self)
            versionName = self.findCurrentVersion(productName, eupsPathDir)[1]

        try:
            productDir = environ[product.envarDirName()]
        except KeyError:
            pass
            
        return versionName, eupsPathDir, productDir, tablefile, flavor

    def findVersion(self, productName, versionName=Current(), eupsPathDirs=None, allowNewer=False):
        """Find a version of a product (if no version is specified, return current version)
The return value is: versionName, eupsPathDir, productDir, tablefile

If allowNewer is true, look for versions that are >= the specified version if an exact
match fails.
        """

        input_versionName = versionName
        
        if self.ignore_versions:
           versionName = ""

        if versionName == Setup():
            versionName, eupsPathDir, productDir, tablefile, flavor = self.findSetupVersion(productName)
            return versionName, eupsPathDir, productDir, tablefile

        if isinstance(eupsPathDirs, str):
            eupsPathDirs = [eupsPathDirs]

        if not eupsPathDirs:
            eupsPathDirs = self.path

        if not versionName or isSpecialVersion(versionName, setup=False):
            # If no version explicitly specified, get the first db with a current one.
            eupsPathDir, versionName, vinfo = self.findCurrentVersion(productName, path=eupsPathDirs)

            if not eupsPathDir:         # a locally-declared product that doesn't really exist
                return [versionName, eupsPathDir, None, None]

            eupsPathDirs = [eupsPathDir]

        vinfo = None

        if self.versionIsRelative(versionName): # we have a relational expression
            expr = re.sub(r"^\s*", "", versionName)
            versionName = None
            matched_eupsPathDir = None
            
            for eupsPathDir in eupsPathDirs: # search for the first match
                if matched_eupsPathDir:       # we got one in the last iteration
                    eupsPathDir = matched_eupsPathDir
                    break
                    
                dir = os.path.join(self.getUpsDB(eupsPathDir), productName)

                versionNames = []
                for vfile in glob.glob(os.path.join(dir, "*.version")):
                    vers = VersionFile(vfile)
                    if vers.info.has_key(self.flavor):
                        versionNames += [(vers.version, vers.info[self.flavor])]

                versionNames.sort(lambda a, b: self.version_cmp(a[0], b[0]))
                versionNames.reverse() # so we'll try the latest version first
                #
                # Include the current version;  if it matches we'll use it
                #
                try:
                    ceupsPathDir, cversionName, cvinfo = self.findCurrentVersion(productName, eupsPathDir)
                    if cvinfo:
                        versionNames = [(cversionName, cvinfo)] + versionNames
                except RuntimeError:
                    cvinfo = None
                    pass
                #
                # We have a list of possible versions, go through them in order
                #
                for vname, _vinfo in versionNames:
                    if self.version_match(vname, expr):
                        matched_eupsPathDir = eupsPathDir
                        versionName = vname
                        vinfo = _vinfo

                        if cvinfo and versionName != cversionName and self.verbose > 0 + self.quiet:
                            print >> sys.stderr, "Using %s %s to satisfy \"%s\" (%s is current)" % \
                                  (productName, versionName, expr, cversionName)

                        extra = ""
                        if self.verbose >= 3 + self.quiet:
                            extra = "in %s " % eupsPathDir

                        if self.verbose >= 2 + self.quiet:
                            print >> sys.stderr, "Version %s %ssatisfies condition \"%s\" for product %s" % \
                                  (versionName, extra, expr, productName)

                        break
        else:
            for eupsPathDir in eupsPathDirs:
                ups_db = self.getUpsDB(eupsPathDir)
                vfile = os.path.join(ups_db, productName, "%s.version" % versionName)
                if os.path.exists(vfile):
                    vers = VersionFile(vfile)
                    if vers.info.has_key(self.flavor):
                        vinfo = vers.info[self.flavor]
                        break

        if not vinfo:                       # no version is available
            msg = "Unable to locate product %s %s for flavor %s" % (productName, input_versionName, self.flavor)

            if allowNewer and versionName and not self.versionIsRelative(versionName):
                if self.verbose:
                    print >> sys.stderr, "%s; trying \">= %s\"" % (msg, versionName)
                return self.findVersion(productName, ">= %s" % versionName, eupsPathDirs)

            raise RuntimeError, msg

        return self._finishFinding(vinfo, productName, versionName, eupsPathDir)

    def findFullySpecifiedVersion(self, productName, versionName, flavor, eupsPathDir):
        """Find a version given full details of where to look"""
        
        vinfo = None
        ups_db = self.getUpsDB(eupsPathDir)
        vfile = os.path.join(ups_db, productName, "%s.version" % versionName)

        if os.path.exists(vfile):
            vers = VersionFile(vfile)
            if vers.info.has_key(flavor):
                vinfo = vers.info[flavor]

        if not vinfo:                   # no version is available
            if versionName == Setup():    # just get the version that's setup
                product = self.Product(productName, noInit=True)
                product.dir = os.environ[product.envarDirName()]
                return None, eupsPathDir, product.dir, product.tableFileName()
            else:
                raise RuntimeError, "Unable to locate %s %s for flavor %s in %s" % \
                      (productName, versionName, flavor, eupsPathDir)

        return self._finishFinding(vinfo, productName, versionName, eupsPathDir)

    def _finishFinding(self, vinfo, productName, versionName, eupsPathDir):
        productDir = vinfo["productDir"]

        if not _isRealFilename(productDir) or productDir == "/dev/null":
            productDir = None
        else:
            if not os.path.isabs(productDir):
                productDir = os.path.join(eupsPathDir, productDir)

            if not os.path.isdir(productDir):
                if self.verbose >= 1 + self.quiet:
                    print >> sys.stderr, \
                          "Product %s %s has non-existent productDir %s" % (productName, versionName, productDir)
        #
        # Look for the directory with the tablefile
        #
        ups_db = self.getUpsDB(eupsPathDir)

        tablefile = vinfo["table_file"]
        if tablefile is None:
            tablefile = "none"

        if vinfo.has_key("ups_dir"):
            ups_dir = vinfo["ups_dir"]
            if productDir:
                ups_dir = re.sub(r"\$PROD_DIR", productDir, ups_dir)
            ups_dir = re.sub(r"\$UPS_DB", ups_db, ups_dir)

            if not os.path.isabs(ups_dir) and productDir: # interpret wrt productDir
                ups_dir = os.path.join(productDir, ups_dir)
        else:
            if _isRealFilename(tablefile):
                print >> sys.stderr, "You must specify UPS_DIR if you specify tablefile == %s" % tablefile

        if _isRealFilename(tablefile):
            if not os.path.isabs(tablefile):
                tablefile = os.path.join(ups_dir, vinfo["table_file"])
            
            if not os.path.exists(tablefile):
                if self.verbose >= 1 + self.quiet:
                    print >> sys.stderr, \
                          "Product %s %s has non-existent tablefile %s" % (productName, versionName, tablefile)
                tablefile = "???"

        return versionName, eupsPathDir, productDir, tablefile

    def getProduct(self, productName, versionName=Current(), eupsPathDirs=None):
        """Return a Product, preferably from the cache but the hard way if needs be"""

        """N.b. we should be getting current information from the cached info, but eups declare
        doesn't do that yet"""

        if isinstance(eupsPathDirs, str):
            eupsPathDirs = [eupsPathDirs]

        if eupsPathDirs:
            if isinstance(eupsPathDirs, str):
                eupsPathDirs = [eupsPathDirs]
                
            dbs = eupsPathDirs
        else:
            dbs = self.versions.keys()  # known eups databases
            
        foundCurrent, eupsPathDir = False, None
        if isSpecialVersion(versionName, setup=False):
            foundCurrent = True
            eupsPathDir, versionName, vinfo = self.findCurrentVersion(productName)
        elif versionName == Setup():
            versionName, eupsPathDir, productDir, tablefile, flavor = self.findSetupVersion(productName)
            if not versionName:
                if self.verbose:
                    print >> sys.stderr, "Product %s is not setup" % productName
                return None

        if eupsPathDir:
            dbs = [eupsPathDir] + filter(lambda d: d != eupsPathDir, dbs) # put chosen version first in eupsPath
        #
        # Try to look it up in the db/product/version dictionary
        #
        for db in dbs:
            if not os.path.isdir(db):
                print >> sys.stderr, "Path %s in cached product list for %s is not a directory" % \
                      (db, self.flavor)
                continue

            try:
                product = self.versions[db][self.flavor][productName][versionName]
                if self.verbose > 2:
                    print >> sys.stderr, "Found %s %s in cache" % (productName, versionName)

                product.Eups = self     # don't use the cached Eups

                if foundCurrent:
                    product.checkCurrent(True)
                else:
                    product.checkCurrent()          # check if it's current

                return product
            except KeyError:
                pass

        product = self.Product(productName, versionName)

        if foundCurrent:
            product.checkCurrent(True)
        else:
            product.checkCurrent()      # check if it's current
        #
        # if version was an expression we may not have known that it was cached, so check now we know exact version
        #
        cached = False
        for db in dbs:
            try:
                self.versions[db][self.flavor][product.name][product.version]
                cached = True
                break
            except KeyError:
                pass

        if not cached and product.db != "(none)":
            if self.verbose > 2:
                print >> sys.stderr, "Writing %s %s to %s's cache" % (product.name, product.version, db)
                
            self.intern(product)    # save it in the cache

        return product

    def buildCache(self, eupsPathDir=None):
        """Build the persistent version cache"""

        if not eupsPathDir:
            for pb in self.path:
                self.buildCache(pb)
            return

        if self.verbose:
            print >> sys.stderr, "Building cache for %s" % eupsPathDir

        #
        # We want an entry even if nothing's declared, otherwise we'll
        # check everytime
        #
        if not self.versions.has_key(eupsPathDir):
            self.versions[eupsPathDir] = {}

        if not self.versions[eupsPathDir].has_key(self.flavor):
            self.versions[eupsPathDir][self.flavor] = {}

        re_version = re.compile(r"^(.*).version$")
        for dirpath, dirnames, filenames in os.walk(self.getUpsDB(eupsPathDir)):
            productName = os.path.basename(dirpath)

            if filenames and self.verbose > 2:
                print >> sys.stderr, "   %s" % productName

            for file in filenames:
                mat = re.search(re_version, file)
                if mat:
                    version = mat.group(1)

                    try:
                        self.getProduct(productName, version, eupsPathDir)
                    except RuntimeError, e:
                        # We only checked for the existance of the file, but when we tried to get the product
                        # we checked for a valid flavor. Don't want to tell the user about those failures
                        if re.search(r"for flavor %s$" % self.flavor, e.__str__()):
                            continue
                        print >> sys.stderr, e

        self.writeDB(eupsPathDir, force=True)

    def isSetup(self, product, versionName=None, eupsPathDir=None):
        """Is specified Product already setup?"""

        if isinstance(product, str):
            product = self.Product(product, noInit=True)
        else:
            assert not versionName
            versionName = product.version
            eupsPathDir = product.db

        if not os.environ.has_key(product.envarSetupName()):
            return False
        
        try:
            sversion, seupsPathDir, sproductDir, stablefile, sflavor = product.getSetupVersion()
        except RuntimeError:
            return False

        if not sversion:
            return False

        if versionName and versionName != sversion:
            return False
        elif eupsPathDir and seupsPathDir and eupsPathDir != seupsPathDir:
            return False
        else:
            return True

    def unsetupSetupProduct(self, product):
        """ """

        versionName, eupsPathDir, productDir, tablefile, flavor = product.getSetupVersion()

        if not versionName or not (eupsPathDir or re.search(r"^LOCAL:", versionName)):
            return 

        oldProduct = self.Product(product.name, noInit=True)
        try:
            oldProduct.init(versionName, flavor, eupsPathDir)

            self.setup(oldProduct, fwd=False)  # do the actual unsetup
        except RuntimeError, e:
            # This can happen if the product's setup but you mess with the ups db by hand
            print >> sys.stderr, "Unable to unsetup %s %s: %s" % (product.name, versionName, e)

    # Permitted relational operators
    _relop_re = r"<=?|>=?|==";

    def versionIsRelative(self, versionName):
        if isSpecialVersion(versionName):
            return False
        else:
            return re.search(Eups._relop_re, versionName)

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

        v1, v2 = versionCallbacks.apply(v1, v2)

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

    def version_match(self, vname, expr):
        """Return vname if it matches the logical expression expr"""

        expr0 = expr
        expr = filter(lambda x: not re.search(r"^\s*$", x), re.split(r"\s*(%s|\|\||\s)\s*" % Eups._relop_re, expr))

        oring = True;                       # We are ||ing primitives
        i = -1
        while i < len(expr) - 1:
            i += 1

            if re.search(Eups._relop_re, expr[i]):
                op = expr[i]; i += 1
                v = expr[i]
            elif re.search(r"^[-+.:/\w]+$", expr[i]):
                op = "=="
                v = expr[i]
            elif expr[i] == "||" or expr[i] == "or":
                oring = True;                     # fine; that is what we expected to see
                continue
            else:
                print >> sys.stderr, "Unexpected operator %s in \"%s\"" % (expr[i], expr0)
                break

            if oring:                # Fine;  we have a primitive to OR in
                if self.version_match_prim(op, vname, v):
                    return vname

                oring = False
            else:
                print >> sys.stderr, "Expected logical operator || in \"%s\" at %s" % (expr0, v)

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

    def intern(self, product, updateDB=True, delete=False):
        """Remember a product in the proper place (or forget it if delete is True);
        if updateDB is true, also save it to disk"""

        if isSpecialVersion(product.version):
            return                      # don't intern e.g. Current or Setup

        d = self.versions

        if not d.has_key(product.db):
            d[product.db] = {}
        d = d[product.db]

        if not d.has_key(product.Eups.flavor):
            d[product.Eups.flavor] = {}
        d = d[product.Eups.flavor]            
            
        if not d.has_key(product.name):
            d[product.name] = {}
        d = d[product.name]

        if delete:
            try:
                del d[product.version]
                if len(self.versions[product.db][product.Eups.flavor][product.name]) == 0:
                    del self.versions[product.db][product.Eups.flavor][product.name]
            except KeyError:
                pass
        else:
            d[product.version] = product
    
        if updateDB:
            self.writeDB(product.db)
    #
    # Here is the externally visible API
    #
    def setup(self, productName, versionName=Current(), fwd=True, recursionDepth=0,
              setupToplevel=True, noRecursion=False, setupType=None):
        """The workhorse for setup.  Return (success?, version) and modify self.{environ,aliases} as needed;
        eups.setup() generates the commands that we need to issue to propagate these changes to your shell"""
        #
        # Look for product directory
        #
        if isinstance(productName, Product): # it's already a full Product
            product = productName; productName = product.name
        elif not fwd:
            productList = self.getSetupProducts(productName)
            if productList:
                product = productList[0]
            else:
                msg = "I can't unsetup %s as it isn't setup" % productName
                if self.verbose > 1 and not self.quiet:
                    print >> sys.stderr, msg

                if not self.force:
                    return False, versionName, msg
                #
                # Fake enough to be able to unset the environment variables
                #
                product = self.Product(productName, noInit=True)
                product.table = Table("none")

            if versionName and not isSpecialVersion(versionName):
                if not self.version_match(product.version, versionName):
                    if not self.quiet:
                        print >> sys.stderr, \
                              "You asked to unsetup %s %s but version %s is currently setup; unsetting up %s" % \
                              (product.name, versionName, product.version, product.version)
        else:
            if self.root and recursionDepth == 0:
                product = self.Product(productName, noInit=True)
                product.initFromDirectory(self.root)
            else:
                try:
                    product = self.getProduct(productName, versionName)
                except RuntimeError, e:
                    if False and self.verbose:
                        print >> sys.stderr, e
                    #
                    # We couldn't find it, but maybe it's already setup locally? That'd be OK
                    #
                    if self.keep and self.alreadySetupProducts.has_key(productName):
                        product = self.alreadySetupProducts[productName]
                    else:
                        return False, versionName, e

        if setupType and not isValidSetupType(setupType):
            raise RuntimeError, ("Unknown type %s; expected one of \"%s\"" % \
                                 (setupType, "\" \"".join(getValidSetupTypes())))
        #
        # We have all that we need to know about the product to proceed
        #
        # If we're the toplevel, get a list of all products that are already setup
        #
        if recursionDepth == 0:
            if fwd:
                q = Quiet(self)
                self.alreadySetupProducts = {}
                for p in self.getSetupProducts():
                    self.alreadySetupProducts[p.name] = p
                del q

        table = product.table

        try:
            actions = table.actions(self.flavor, setupType=setupType)
        except RuntimeError, e:
            print >> sys.stderr, "product %s %s: %s" % (product.name, product.version, e)
            return False, product.version, e
        #
        # Ready to go
        #
        # self._msgs["setup"] is used to suppress multiple messages about setting up the same product
        if recursionDepth == 0:
            self._msgs["setup"] = {}

        indent = "| " * (recursionDepth/2)
        if recursionDepth%2 == 1:
            indent += "|"

        setup_msgs = self._msgs["setup"]
        if fwd and self.verbose and recursionDepth >= 0:
            key = "%s:%s:%s" % (product.name, self.flavor, product.version)
            if self.verbose > 1 or not setup_msgs.has_key(key):
                print >> sys.stderr, "Setting up: %-30s  Flavor: %-10s Version: %s" % \
                      (indent + product.name, self.flavor, product.version)
                setup_msgs[key] = 1

        if fwd and setupToplevel:
            #
            # Are we already setup?
            #
            try:
                sversionName, seupsPathDir, sproductDir, stablefile, sflavor = product.getSetupVersion()
            except RuntimeError, e:
                sversionName = None

            if product.version and sversionName:
                if product.version == sversionName or productDir == sproductDir: # already setup
                    if recursionDepth == 0: # top level should be resetup if that's what they asked for
                        pass
                    elif self.force:   # force means do it!; so do it.
                        pass
                    else:
                        if self.verbose > 1:
                            print >> sys.stderr, "            %s %s is already setup; skipping" % \
                                  (len(indent)*" " + product.name, product.version)
                            
                        return True, product.version, None
                else:
                    if recursionDepth > 0: # top level shouldn't whine
                        pversionName = product.version

                        if self.keep:
                            verb = "requesting"
                        else:
                            verb = "setting up"

                        msg = "%s %s is setup, and you are now %s %s" % \
                              (product.name, sversionName, verb, pversionName)

                        if self.quiet <= 0 and self.verbose > 0 and not (self.keep and setup_msgs.has_key(msg)):
                            print >> sys.stderr, "            %s%s" % (recursionDepth*" ", msg)
                        setup_msgs[msg] = 1

            if recursionDepth > 0 and self.keep and product.name in self.alreadySetupProducts.keys():
                keptProduct = self.alreadySetupProducts[product.name]

                resetup = True          # do I need to re-setup this product?
                if self.isSetup(keptProduct):
                    resetup = False
                    
                if self.version_cmp(product.version, keptProduct.version) > 0:
                    keptProduct = product                     
                    self.alreadySetupProducts[product.name] = product # keep this one instead
                    resetup = True

                if resetup:
                    #
                    # We need to resetup the product, but be careful. We can't just call
                    # setup recursively as that'll just blow the call stack; but we do
                    # want keep to be active for dependent products.  Hence the two
                    # calls to setup
                    #
                    self.setup(keptProduct, recursionDepth=-9999, noRecursion=True)
                    self.setup(keptProduct, recursionDepth=recursionDepth, setupToplevel=False)

                if keptProduct.version != product.version and self.keep and \
                       ((self.quiet <= 0 and self.verbose > 0) or self.verbose > 2):
                    msg = "%s %s is already setup; keeping" % \
                          (keptProduct.name, keptProduct.version)

                    if not setup_msgs.has_key(msg):
                        if not self.verbose:
                            print >> sys.stderr, msg
                        else:
                            print >> sys.stderr, "            %s" % (len(indent)*" " + msg)
                        setup_msgs[msg] = 1

                return True, keptProduct.version, None

            q = Quiet(self)
            self.unsetupSetupProduct(product)
            del q

            self.setEnv(product.envarDirName(), product.dir)
            self.setEnv(product.envarSetupName(),
                        "%s %s -f %s -Z %s" % (product.name, product.version, product.Eups.flavor, product.db))
            #
            # Remember that we've set this up in case we want to keep it later
            #
            if not self.alreadySetupProducts.has_key(product.name):
                self.alreadySetupProducts[product.name] = product
        elif fwd:
            assert not setupToplevel
        else:
            if product.dir in self.localVersions.keys():
                del self.localVersions[product.dir]

            self.unsetEnv(product.envarDirName())
            self.unsetEnv(product.envarSetupName())
        #
        # Process table file
        #
        for a in actions:
            a.execute(self, recursionDepth + 1, fwd, noRecursion=noRecursion)

        if recursionDepth == 0:            # we can cleanup
            if fwd:
                del self.alreadySetupProducts
                del self._msgs["setup"]

        return True, product.version, None

    def unsetup(self, productName, versionName=None):
        """Unsetup a product"""

        self.setup(productName, versionName, fwd=False)

    def declare(self, productName, versionName, productDir, eupsPathDir=None, tablefile=None, declareCurrent=None):
        """Declare a product.  productDir may be None if declareCurrent is True.  N.b. tablefile=None means that the
        default "productName.table" table should be used;  set tablefile="none" if you want no table
        "tablefile" may be an open file descriptor, in which case we'll write the tablefile for you.
        """

        if re.search(r"[^a-zA-Z_0-9]", productName):
            raise RuntimeError, ("Product names may only include the characters [a-zA-Z_0-9]: saw %s" % productName)

        if productDir and not productName:
            productName = guessProduct(os.path.join(productDir, "ups"))

        if not productDir or not tablefile:
            if declareCurrent:
                try:
                    if eupsPathDir:
                        info = self.findFullySpecifiedVersion(productName, versionName, self.flavor, eupsPathDir)
                    else:
                        info = self.findVersion(productName, versionName)

                    if not productDir:
                        productDir = info[2]
                    if not tablefile:
                        tablefile = info[3] # we'll check the other fields later

                    if not productDir:
                        productDir = "none"

                except RuntimeError:
                    pass

        if not productDir or productDir == "/dev/null":
            #
            # Look for productDir on self.path
            #
            for eupsProductDir in self.path:
                _productDir = os.path.join(eupsProductDir, self.flavor, productName, versionName)
                if os.path.isdir(_productDir):
                    productDir = _productDir
                    break

        if not productDir:
            raise RuntimeError, \
                  ("Please specify a productDir for %s %s (maybe \"none\")" % (productName, versionName))

        if productDir == "/dev/null":   # Oh dear, we failed to find it
            productDir = "none"
            print >> sys.stderr, "Failed to find productDir for %s %s; assuming \"%s\"" % \
                  (productName, versionName, productDir)

        if _isRealFilename(productDir) and not os.path.isdir(productDir):
            raise RuntimeError, \
                  ("Product %s %s's productDir %s is not a directory" % (productName, versionName, productDir))

        if tablefile is None:
            tablefile = "%s.table" % productName

        if _isRealFilename(productDir):
            if os.environ.has_key("HOME"):
                productDir = re.sub(r"^~", os.environ["HOME"], productDir)
            if not os.path.isabs(productDir):
                productDir = os.path.join(os.getcwd(), productDir)
            productDir = os.path.normpath(productDir)

        if not eupsPathDir:             # look for proper home on self.path
            for d in self.path:
                if os.path.commonprefix([productDir, d]) == d:
                    eupsPathDir = d
                    break

            if not eupsPathDir:
                eupsPathDir = self.path[0]

        if not eupsPathDir:             # can happen with no self.path and self.root != None
            raise RuntimeError, \
                  ("No EUPS_PATH is defined; I can't guess where to declare %s %s" % (productName, versionName))

        ups_dir, tablefileIsFd = "ups", False
        if not _isRealFilename(tablefile):
            ups_dir = None
        elif tablefile:
            if isinstance(tablefile, file):
                tablefileIsFd = True
                tfd = tablefile

                tablefile = "%s.table" % versionName

                ups_dir = os.path.join("$UPS_DB",               productName, self.flavor)
                tdir = os.path.join(self.getUpsDB(eupsPathDir), productName, self.flavor)

                if not os.path.isdir(tdir):
                    os.makedirs(tdir)
                ofd = open(os.path.join(tdir, tablefile), "w")
                for line in tfd:
                    print >> ofd, line,
                del ofd
        #
        # Check that tablefile exists
        #
        assert tablefile
        if not tablefileIsFd and _isRealFilename(tablefile):
            if _isRealFilename(productDir):
                if ups_dir:
                    try:
                        full_tablefile = os.path.join(ups_dir, tablefile)
                    except Exception, e:
                        raise RuntimeError, ("Unable to generate full tablefilename: %s" % e)
                    
                    if not os.path.isfile(full_tablefile) and not os.path.isabs(full_tablefile):
                        full_tablefile = os.path.join(productDir, full_tablefile)

                else:
                    full_tablefile = tablefile
            else:
                full_tablefile = os.path.join(productDir, ups_dir, tablefile)

            if not os.path.isfile(full_tablefile):
                raise RuntimeError, ("I'm unable to declare %s as tablefile %s does not exist" %
                                     (productName, full_tablefile))
        #
        # See if we're redeclaring a product and complain if the new declaration conflicts with the old
        #
        try:
            _version, _eupsPathDir, _productDir, _tablefile = \
                      self.findFullySpecifiedVersion(productName, versionName, self.flavor, eupsPathDir)

            assert _version == versionName
            assert eupsPathDir == _eupsPathDir
        except RuntimeError:
            _productDir, _tablefile = productDir, tablefile

        differences = []
        if _productDir and productDir != _productDir:
            differences += ["%s != %s" % (productDir, _productDir)]
        if _tablefile and tablefile != _tablefile:
            # Different names; see if they're different content too
            diff = ["%s != %s" % (tablefile, _tablefile)] # possible difference
            try:
                if not filecmp.cmp(tablefile, _tablefile):
                    differences += diff
            except OSError:
                differences += diff

        redeclare = True
        if _productDir and _tablefile and not differences:
            redeclare = False
        else:
            if declareCurrent:
                if not differences:
                    redeclare = False
            else:
                if not self.force:
                    info = ""
                    if differences and self.verbose:
                        info = " (%s)" % " ".join(differences)
                    raise RuntimeError, ("Redeclaring %s %s%s; specify force to proceed" %
                                         (productName, versionName, info))
        #
        # Is the product really declared?
        #
        if not redeclare:
            try:
                self.getProduct(productName, versionName, eupsPathDir)
            except RuntimeError, e:
                redeclare = True
        #
        # Arguments are checked; we're ready to go
        #
        if redeclare:
            if self.noaction or self.verbose:
                info = "Declaring"
                if self.noaction or self.verbose > 1:
                    if productDir == "/dev/null":
                        info += " \"none\" as"
                    else:
                        info += " %s as" % productDir
                info += " %s %s" % (productName, versionName)
                if declareCurrent:
                    info += " %s" % self.currentType
                info += " in %s" % (eupsPathDir)

                print >> sys.stderr, info
            #
            # Create a Version
            #
            version = VersionFile(self, productName, versionName, productDir, tablefile, ups_dir)
            #
            # Merge in the old version of that VersionFile, if it exists, and write the new file;
            # it may have declarations for other flavors
            #
            lock = self.lockDB(eupsPathDir)

            try:
                product = self.getProduct(productName, versionName, eupsPathDir)
            except RuntimeError: 
                product = self.Product(productName, versionName, eupsPathDirs=eupsPathDir, noInit=True)

            try:
                version.merge(VersionFile(product.versionFileName()), self.who)
            except IOError:
                pass                    # no previous declaration exists

            vfile = ""
            try:
                vfile = product.versionFileName()

                vdir = os.path.dirname(vfile)
                if not os.path.isdir(vdir):
                    os.makedirs(vdir)

                if not self.noaction:
                    fd = open(vfile + ".new~", "w")
                    version.write(fd)
                    del fd

                    shutil.move(vfile + ".new~", vfile) # actually update the file
            except Exception, e:
                print >> sys.stderr, "Unable to update %s: %s" % (vfile, e)
        #
        # If this is the only instance of this product, declare it current
        # This you to install product A which depends on product B by first installing and declaring B,
        # and then blithely setup A (e.g. setup -r .) without a version specified for B.
        #
        if not declareCurrent and len(self.listProducts(productName)) == 0: # 0: the count when we created our Eups
            declareCurrent = True
        #
        # Declare it current if needs be
        #
        if declareCurrent:
            current = CurrentChain(self, productName, versionName, productDir)

            lock = self.lockDB(eupsPathDir)

            product = self.getProduct(productName, versionName, eupsPathDir)
            try:
                current.merge(CurrentChain(product.currentFileName()), self.who)
            except IOError:
                pass

            cfile = ""
            try:
                cfile = product.currentFileName()

                cdir = os.path.dirname(cfile)
                if not os.path.isdir(cdir):
                    os.makedirs(cdir)

                if not self.noaction:
                    fd = open(cfile + ".new~", "w")
                    current.write(fd)
                    del fd

                    shutil.move(cfile + ".new~", cfile) # actually update the file
            except Exception, e:
                print >> sys.stderr, "Unable to update %s: %s" % (cfile, e)
        #
        # Update the cache
        #
        if not self.noaction:
            product = self.getProduct(productName, versionName, eupsPathDir)
            self.intern(product, updateDB=False, delete=True)
            
            self.getProduct(productName, versionName, eupsPathDir) # update the cache

    def declareCurrent(self, productName, versionName, eupsPathDir=None, local=False):
        """Declare a product current.

        If local is true, this is only done in self's scope, and the product/version
        needn't even be known to eups"""

        if local:
            self.locallyCurrent[productName] = versionName

            return
        
        return self.declare(productName, versionName, None, eupsPathDir=eupsPathDir, declareAs=True)
    
    def removeCurrent(self, product, eupsPathDir, currentType=None):
        """Remove the CurrentChain for productName/versionName from the live current chain (of type currentType)"""

        current = CurrentChain(self, product.name, product.version, eupsPathDir, currentType=currentType)

        lock = self.lockDB(eupsPathDir)

        updatedChain = CurrentChain(product.currentFileName(currentType)).remove(current)

        cfile = ""
        try:
            cfile = product.currentFileName(currentType)

            if self.verbose or self.noaction:
                print >> sys.stderr, "Removing %s %s from %s chain for %s" % \
                      (product.name, product.version, Current(currentType).tag, eupsPathDir)

            if not self.noaction:
                if len(updatedChain.info.keys()) == 0: # not declared for any flavor
                    os.unlink(cfile)
                else:
                    fd = open(cfile + ".new~", "w")
                    updatedChain.write(fd)
                    del fd

                    shutil.move(cfile + ".new~", cfile) # actually update the file
        except Exception, e:
            raise RuntimeError, ("Unable to update %s: %s" % (cfile, e))

    def undeclare(self, productName, versionName=None, eupsPathDir=None, undeclareCurrent=None):
        """Undeclare a product."""

        if not versionName:
            productList = self.listProducts(productName)
            versionList = map(lambda el: el[1], productList)
            
            if len(versionList) == 1:
                versionName = versionList[0]
            elif len(versionList) > 1:
                raise RuntimeError, ("Product %s has versions \"%s\"; please choose one and try again" %
                                     (productName, "\" \"".join(versionList)))

        try:
            product = self.getProduct(productName, versionName, eupsPathDir)
        except RuntimeError, e:
            product = None
            print >> sys.stderr, e

        if not product:
            raise RuntimeError, ("Product %s %s is not declared" % (productName, versionName))
            
        if self.isSetup(product):
            if self.force:
                print >> sys.stderr, "Product %s %s is currently setup; proceeding" % (productName, versionName)
            else:
                raise RuntimeError, \
                      ("Product %s %s is already setup; specify force to proceed" % (productName, versionName))

        eupsPathDir = product.db
        #
        # Deal with current products (undeclaring always makes them non-current, of course)
        #
        if not product.isCurrent():
            if undeclareCurrent:
                if self.verbose:
                    print >> sys.stderr, "Product %s %s is already not tagged %s" % (productName, versionName,
                                                                                     Current(self.currentType).tag)
        else:
            try:
                self.removeCurrent(product, eupsPathDir, self.currentType)
            except RuntimeError, e:
                print >> sys.stderr, e

        if undeclareCurrent:           # we're done
            return True
        #
        # Create a Version
        #
        version = VersionFile(self, productName, versionName)
        #
        # Remove the old version of that Version, if it exists, and write the new file
        #
        lock = self.lockDB(eupsPathDir)
        #
        # Remove the VersionFile that we just created from productName from the live version list
        #
        try:
            updatedVersion = VersionFile(product.versionFileName()).remove(version)
        except IOError:
            updatedVersion = None   # OK, so it didn't exist

        vfile = ""
        try:
            vfile = product.versionFileName()

            if self.verbose or self.noaction:
                print >> sys.stderr, "Removing %s %s from version list for %s" % \
                      (productName, versionName, eupsPathDir)

            if not self.noaction:
                if not updatedVersion or len(updatedVersion.info.keys()) == 0: # not declared for any flavor
                    os.unlink(vfile)
                else:
                    fd = open(vfile + ".new~", "w")
                    updatedVersion.write(fd)
                    del fd

                    shutil.move(vfile + ".new~", vfile) # actually update the file
        except OSError, e:
            pass
        except Exception, e:
            print >> sys.stderr, "Unable to update %s: %s" % (vfile, e)
        #
        # See if any product had any other tags attached to it
        #
        currentTypes = map(lambda f: os.path.splitext(os.path.basename(f))[0], product.currentFileName(all=True))
        for c in currentTypes:
            self.removeCurrent(product, eupsPathDir, currentType=Current(c))

        self.intern(product, delete=True)

        return True

    def listProducts(self, productName=None, productVersion=None, current=None, setup=False):
        """Return a list of (name, version, db, product.dir, isCurrent, isSetup)
        If provided, restrict list to those matching productName and/or productVersion;
        matching is a la shell globbing (i.e. using fnmatch)
        """

        productList = []
        #
        # Maybe they wanted Setup or some sort of Current?
        #
        if productVersion == Setup():
            setup = True
        elif isSpecialVersion(productVersion, setup=False):
            current = productVersion

        if current or setup:
            productVersion = None
        #
        # Find all products on path (cached in self.versions, of course)
        #
        for db in self.path:
            if not self.versions.has_key(db) or not self.versions[db].has_key(self.flavor):
                continue
            
            for name in self.versions[db][self.flavor].keys():
                if productName and not fnmatch.fnmatchcase(name, productName):
                    continue
                
                for version in self.versions[db][self.flavor][name].keys():
                    if productVersion and not fnmatch.fnmatchcase(version, productVersion):
                        continue

                    product = self.versions[db][self.flavor][name][version]
                    product.Eups = self     # don't use the cached Eups

                    isCurrent = product.checkCurrent(currentType=current)
                    isSetup = self.isSetup(product)

                    if current and current != isCurrent:
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
        for lproductName in self.localVersions.keys():
            product = self.Product(lproductName, noInit=True)

            if not setup and (productName and productName != lproductName): # always print local setups of productName
                continue

            try:
                product.initFromDirectory(self.localVersions[product.name])
            except RuntimeError, e:
                if not self.quiet:
                    print >> sys.stderr, ("Problem with product %s found in environment: %s" % (lproductName, e))
                continue

            if productName and not fnmatch.fnmatchcase(product.name, productName):
                continue
            if productVersion and not fnmatch.fnmatchcase(product.version, productVersion):
                continue

            thisCurrent = current
            if current:
                isCurrent = product.checkCurrent()
                if current != isCurrent:
                    if productName == lproductName and current != Current():
                        thisCurrent = Current(" ") # they may have setup -r . --tag=XXX
                    else:
                        continue

            values = []
            values += [product.name]
            values += [product.version, product.db, product.dir, thisCurrent, True]
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

    def dependencies_from_table(self, tablefile, eupsPathDirs=None, setupType=None):
        """Return self's dependencies as a list of (Product, optional, currentRequested) tuples

        N.b. the dependencies are not calculated recursively"""
        dependencies = []
        if _isRealFilename(tablefile):
            for (product, optional, currentRequested) in \
                    Table(tablefile).dependencies(self, eupsPathDirs, setupType=setupType):
                dependencies += [(product, optional, currentRequested)]

        return dependencies

    def remove(self, productName, versionName, recursive, checkRecursive=False, interactive=False, userInfo=None):
        """Undeclare and remove a product.  If recursive is true also remove everything that
        this product depends on; if checkRecursive is True, you won't be able to remove any
        product that's in use elsewhere unless force is also True.

        N.b. The checkRecursive option is quite slow (it has to parse
        every table file on the system).  If you're calling remove
        repeatedly, you can pass in a userInfo object (returned by
        self.uses(None)) to save remove() having to processing those
        table files on every call."""
        #
        # Gather the required information
        #
        if checkRecursive and not userInfo:
            if self.verbose:
                print >> sys.stderr, "Calculating product dependencies recursively..."
            userInfo = self.uses(None)
        else:
            userInfo = None

        topProduct = productName
        topVersion = versionName
        #
        # Figure out what to remove
        #
        productsToRemove = self._remove(productName, versionName, recursive, checkRecursive,
                                        topProduct, topVersion, userInfo)

        productsToRemove = list(set(productsToRemove)) # remove duplicates
        #
        # Actually wreak destruction. Don't do this in _remove as we're relying on the static userInfo
        #
        default_yn = "y"                    # default reply to interactive question
        removedDirs = {}                    # directories that have already gone (useful if more than one product
                                            # shares a directory)
        removedProducts = {}                # products that have been removed (or the user said no)
        for product in productsToRemove:
            dir = product.dir
            if False and not dir:
                raise RuntimeError, \
                      ("Product %s with version %s doesn't seem to exist" % (product.name, product.version))
            #
            # Don't ask about the same product twice
            #
            pid = product.__str__()
            if removedProducts.has_key(pid):
                continue

            removedProducts[pid] = 1

            if interactive:
                yn = default_yn
                while yn != "!":
                    yn = raw_input("Remove %s %s: (ynq!) [%s] " % (product.name, product.version, default_yn))

                    if yn == "":
                        yn = default_yn
                    if yn == "y" or yn == "n" or yn == "!":
                        default_yn = yn
                        break
                    elif yn == "q":
                        return
                    else:
                        print >> sys.stderr, "Please answer y, n, q, or !, not %s" % yn

                if yn == "n":
                    continue

            if not self.undeclare(product.name, product.version, undeclareCurrent=None):
                raise RuntimeError, ("Not removing %s %s" % (product.name, product.version))

            if removedDirs.has_key(dir): # file is already removed
                continue

            if _isRealFilename(dir):
                if self.noaction:
                    print "rm -rf %s" % dir
                else:
                    try:
                        shutil.rmtree(dir)
                    except OSError, e:
                        raise RuntimeError, e

            removedDirs[dir] = 1

    def _remove(self, productName, versionName, recursive, checkRecursive, topProduct, topVersion, userInfo):
        """The workhorse for remove"""

        try:
            product = Product(self, productName, versionName)
        except RuntimeError, e:
            raise RuntimeError, ("product %s %s doesn't seem to exist" % (productName, versionName))

        deps = [(product, False, False)]
        if recursive:
            deps += product.dependencies()

        productsToRemove = []
        for product, o, currentRequested in deps:
            if checkRecursive:
                usedBy = filter(lambda el: el[0] != topProduct or el[1] != topVersion,
                                userInfo.users(product.name, product.version))

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

                    msg = "%s %s is required by product%s %s" % (product.name, product.version, plural, tmp)

                    if self.force:
                        print >> sys.stderr, "%s; removing anyway" % (msg)
                    else:
                        raise RuntimeError, ("%s; specify force to remove" % (msg))

            if recursive:
                productsToRemove += self._remove(product.name, product.version, (product.name != productName),
                                                 checkRecursive, topProduct=topProduct, topVersion=topVersion,
                                                 userInfo=userInfo)

            productsToRemove += [product]
                
        return productsToRemove

    def uses(self, productName=None, versionName=None, depth=9999):
        """Return a list of all products which depend on the specified product in the form of a list of tuples
        (productName, productVersion, (versionNeeded, optional))

        depth tells you how indirect the setup is (depth==1 => product is setup in table file,
        2 => we set up another product with product in its table file, etc.)

        versionName may be None in which case all versions are returned.  If product is also None,
        a Uses object is returned which may be used to perform further uses searches efficiently
    """
        if not productName and versionName:
            raise RuntimeError, ("You may not specify a version \"%s\" but not a product" % versionName)

        self.exact_version = True

        if True:
            productList = self.listProducts(None)
        else:                               # debug code only!
            prods = ("test", "test2", "test3", "boo", "goo", "hoo")
            #prods = (["test"])
            #prods = (["astrotools"])
            #prods = (["afw"])

            productList = []
            for p in prods:
                for pl in self.list(p):
                    productList += [pl]

        if not productList:
            return []

        useInfo = Uses()

        for (p, v, db, dir, isCurrent, isSetup) in productList: # for every known product
            try:
                q = Quiet(self)
                deps = Product(self, p, v).dependencies() # lookup top-level dependencies
                del q
            except RuntimeError, e:
                print >> sys.stderr, ("%s %s: %s" % (p, v, e))
                continue

            for pd, od, currentRequested in deps:
                if p == pd.name and v == pd.version:
                    continue

                useInfo._remember(p, v, (pd.name, pd.version, od, currentRequested))

        useInfo._invert(depth)
        #
        # OK, we have the information stored away
        #
        if not productName:
            return useInfo

        return useInfo.users(productName, versionName)

_ClassEups = Eups                       # so we can say, "isinstance(Eups, _ClassEups)"

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
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

    def _do_invert(self, productName, versionName, k, depth, optional=False):
        """Workhorse for _invert"""
        if depth <= 0 or not self._depends_on.has_key(k):
            return
        
        for p, v, o, c in self._depends_on[k]:
            o = o or optional

            key = self._getKey(p, v)
            if not self._setup_by.has_key(key):
                self._setup_by[key] = []

            self._setup_by[key] += [(productName, versionName, (v, o, c))]

            self._do_invert(productName, versionName, self._getKey(p, v), depth - 1, o)

    def _invert(self, depth):
        """ Invert the dependencies to tell us who uses what, not who depends on what"""

        pattern = re.compile(r"^(?P<product>[\w]+):(?P<version>[\w.+\-]+)")

        self._setup_by = {}
        for k in self._depends_on.keys():
            mat = pattern.match(k)
            assert mat

            productName = mat.group("product")
            versionName = mat.group("version")

            self._do_invert(productName, versionName, k, depth)

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
            self._setup_by[k] = list(set(self._setup_by[k]))

    def users(self, productName, versionName=None):
        """Return a list of the users of productName/productVersion; each element of the list is:
        (user, userVersion, (productVersion, optional)"""
        if versionName:
            versionName = re.escape(versionName)
        else:
            versionName = r"[\w.+\-]+"
            
        versionName = r"(?P<version>%s)" % versionName

        pattern = re.compile(r"^%s$" % self._getKey(productName, versionName))
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
        
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def flavor():
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
    
getFlavor = flavor                      # useful in this file if you have a variable named flavor

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def setup(Eups, productName, version=Current(), fwd=True, setupType=None):
    """Return a set of commands which, when sourced, will setup a product (if fwd is false, unset it up)"""

    cmds = []

    ok, version, reason = Eups.setup(productName, version, fwd, setupType=setupType)
    if ok:
        #
        # Set new variables
        #
        for key in os.environ.keys():
            val = os.environ[key]
            try:
                if val == Eups.oldEnviron[key]:
                    continue
            except KeyError:
                pass

            if val and not re.search(r"^['\"].*['\"]$", val) and \
                   re.search(r"[\s<>|&;()]", val):   # quote characters that the shell cares about
                val = "'%s'" % val

            if Eups.shell == "sh" or Eups.shell == "zsh":
                cmd = "export %s=%s" % (key, val)
            elif Eups.shell == "csh":
                cmd = "setenv %s %s" % (key, val)

            if Eups.noaction:
                if Eups.verbose < 2 and re.search(r"SETUP_", key):
                    continue            # the SETUP_PRODUCT variables are an implementation detail

                cmd = "echo \"%s\"" % cmd

            cmds += [cmd]
        #
        # unset ones that have disappeared
        #
        for key in Eups.oldEnviron.keys():
            if re.search(r"^EUPS_(DIR|PATH)$", key): # the world will break if we delete these
                continue        

            if os.environ.has_key(key):
                continue

            if Eups.shell == "sh" or Eups.shell == "zsh":
                cmd = "unset %s" % (key)
            elif Eups.shell == "csh":
                cmd = "unsetenv %s" % (key)

            if Eups.noaction:
                if Eups.verbose < 2 and re.search(r"SETUP_", key):
                    continue            # an implementation detail

                cmd = "echo \"%s\"" % cmd

            cmds += [cmd]
        #
        # Now handle aliases
        #
        for key in Eups.aliases.keys():
            value = Eups.aliases[key]

            try:
                if value == Eups.oldAliases[key]:
                    continue
            except KeyError:
                pass

            if Eups.shell == "sh":
                cmd = "function %s { %s ; }; export -f %s" % (key, value, key)
            elif Eups.shell == "csh":
                value = re.sub(r"\$@", r"\!*", value)
                cmd = "alias %s \'%s\'" % (key, value)
            elif Eups.shell == "zsh":
                cmd = "%s() { %s ; }" % (key, value, key)

            if Eups.noaction:
                cmd = "echo \"%s\"" % re.sub(r"`", r"\`", cmd)

            cmds += [cmd]
        #
        # and unset ones that used to be present, but are now gone
        #
        for key in Eups.oldAliases.keys():
            if Eups.aliases.has_key(key):
                continue

            if Eups.shell == "sh" or Eups.shell == "zsh":
                cmd = "unset %s" % (key)
            elif Eups.shell == "csh":
                cmd = "unalias %s" (key)

            if Eups.noaction:
                cmd = "echo \"%s\"" % cmd

            cmds += [cmd]
    elif fwd and version == Current():
        print >> sys.stderr, "No version of %s is declared current" % productName
        cmds += ["false"]               # as in /bin/false
    else:
        if fwd:
            versionName = version

            if isSpecialVersion(versionName):
                versionName = ""

            if versionName:
                versionName = " " + versionName
        
            print >> sys.stderr, "Failed to setup %s%s: %s" % (productName, versionName, reason)
        else:
            print >> sys.stderr, "Failed to unsetup %s: %s" % (productName, reason)

        cmds += ["false"]               # as in /bin/false

    return cmds

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def unsetup(Eups, productName, version=None):
    """ """

    return setup(Eups, productName, version, fwd=False)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-


def productDir(productName, versionName=Setup(), Eups=None):
    """Return the PRODUCT_DIR for the specified product and version (default: Setup)
    If you specify a version other than Setup, you'll also need to provide an instance
    of Eups
    """

    if not productName:
        raise RuntimeError, "Please specify a product name"

    if not Eups:                        # only setup version is available
        if versionName != Setup():
            raise RuntimeError, \
                  ("I can only lookup a non-setup version of %s if you provide an instance of class Eups" % productName)
        Eups = _ClassEups()

    try:
        return Eups.listProducts(productName, versionName)[0][3]
    except IndexError:
        None

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
        
def guessProduct(dir, productName=None):
    """Guess a product name given a directory containing table files.  If you provide productName,
    it'll be chosen if present; otherwise if dir doesn't contain exactly one product we'll raise RuntimeError"""

    productNames = map(lambda t: re.sub(r".*/([^/]+)\.table$", r"\1", t), glob.glob(os.path.join(dir, "*.table")))

    if not productNames:
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

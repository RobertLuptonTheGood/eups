import os, re, sys, copy
from eups.utils import ctimeTZ, isRealFilename, stdwarn, stderr, getUserName, defaultUserDataDir
import cPickle as pickle

who = getUserName(full=True)

class ChainFileCache(object):

    def __init__(self):
        # initialize instance variables
        self._caches = dict()
        self._staleCacheFiles = set()

        # register self.autosave to run on interpreter exit
        # this will save any dirty caches, for future invocations
        import atexit
        atexit.register(self.autosave)

    def _cacheFilenameFor(self, dirName):
        dirName = os.path.normpath(dirName)
        return os.path.join(defaultUserDataDir(), '_chain_caches_', dirName[1:], "__chains__.pkl")

    def _getCacheFor(self, fn):
    	dirName = os.path.dirname(fn)

        # Cache already loaded?
        try:
            cache, mtime = self._caches[dirName]
            return cache, dirName
        except KeyError:
            #print >>sys.stderr, "Cache miss:", dirName
            pass

        # Already on disk (and valid)?
        mtimeDir = os.path.getmtime(dirName)
        try:
            cacheFn = self._cacheFilenameFor(dirName)
            fp = open(cacheFn)
        except IOError:
            pass
        else:
            cache, mtime = self._caches[dirName] = pickle.load(fp)
            fp.close()

            if mtimeDir <= mtime:
                return cache, dirName

        # Return an empty cache
        cache, mtime = self._caches[dirName] = dict(), mtimeDir
        return cache, dirName

    # Called to obtain an instance of ChainFile
    def __getitem__(self, fn):
        # Get a cache for the directory
        cache, _ = self._getCacheFor(fn)
        return cache[fn]

    def __setitem__(self, fn, chainData):
        cache, dirName = self._getCacheFor(fn)
        cache[fn] = chainData

        # Update mtime, and mark cache as stale
        self._caches[dirName] = cache, os.path.getmtime(os.path.dirname(fn))
        self._staleCacheFiles.add(dirName)

    def __delitem__(self, fn):
        cache, _ = self._getCacheFor(fn)
        del cache[fn]

    def _writeDirCache(self, cacheFn, cacheData):
        # Ensure the directory exists
        try:
            os.makedirs(os.path.dirname(cacheFn))
        except OSError:
            pass

        # Safely write the file
        tmpFn = cacheFn + ".tmp"

        fp = open(tmpFn, "w")
        pickle.dump(cacheData, fp, -1)
        fp.close()

        os.rename(tmpFn, cacheFn)

    def autosave(self):
        # check if there are any dirty caches and write them out
        for dirName in self._staleCacheFiles:
            self._writeDirCache(self._cacheFilenameFor(dirName), self._caches[dirName])

# chain cache singleton
chainCache = ChainFileCache()

class ChainFile(object):
    """
    a representation of the data contained in a product tag chain file.  
    This file records which version of a product a particular tag is 
    assigned to.

    @author: Raymond Plante
    """

    # Per-flavor metadata fields in file, in order of appearance.  
    # Values are stored in self.info
    _fields = [      
      "DECLARER",
      "DECLARED",
      "MODIFIER",
      "MODIFIED",
    ]

    def __init__(self, file, productName=None, tag=None, verbosity=0, 
                 readFile=True):

        # the file containing the tag information
        self.file = file

        # the name of the product.
        self.name = productName

        # the name of the tag being described
        self.tag = tag

        # tag assignment attributes as a dictionary.  Each key is a flavor 
        # name and its value is a properties set of named metadata.
        self.info = {}

        if readFile:
            try:
                self._read(self.file, verbosity)
            except IOError, e:
                # It's not an error if the file didn't exist
                if e.errno != errno.ENOENT:
	            raise


    def getFlavors(self):
        """
        return the flavors described by this chain.

        @return string[] :  the supported flavor names
        """
        return self.info.keys()

    def hasFlavor(self, flavor):
        """
        return true if the product is declared for a given flavor 
        """
        return self.info.has_key(flavor)

    def getVersion(self, flavor):
        """
        return the version that has been assigned this tag or None if the 
        tag is not assigned to the flavor.

        @param flavor : the name of the flavor to get the tagged versions for. 
        @return string : the version tag is assigned to
        """
        try:
            return self.info[flavor]["version"]
        except KeyError:
            return None

    def setVersion(self, version, flavors=None):
        """
        assign this tag to a version.

        @param version : the version to assign this tag to
        @param flavors : the flavors to update tags for as a list or a single
                           string (for a single flavor).  If None, tag all 
                           previously tagged flavors will be retagged.
        """
        if flavors is None:
            return self.setVersion(self.getFlavors())
        if not isinstance(flavors, list):
            flavors = [flavors]

        for flavor in flavors:
            if self.info.has_key(flavor):
                info = self.info[flavor].copy()
                info["modifier"] = who
                info["modified"] = ctimeTZ()
            else:
                info = { "declarer": who, "declared": ctimeTZ() } 

            info["version"] = version
            self.info[flavor] = info

    def removeVersion(self, flavors=None):
        """
        remove the version tagging for the given flavors.  Return false 
        if the tag was not previously assigned for any of the flavors.

        @param flavors : the flavors to remove the tag for.  If None, the 
                            tag for all available flavors will be removed.  
        @return bool : False if tag was not assigned for the given flavors.
        """
        if flavors is None:
            return self.removeVersion(self.getFlavors())
        if not isinstance(flavors, list):
            flavors = [flavors]

        updated = False
        for flavor in flavors:
            if self.info.has_key(flavor):
                del self.info[flavor]
                updated = True

        return updated

    def hasNoAssignments(self):
        """
        return true if there are no currently set  assignments of this tag.
        """
        return (len(self.info.keys()) == 0)

    def write(self, file=None):
        """
        write the tag assingment data out to a file.  Note that if the tag
        is not currently assigned to any flavor, the file will be removed 
        from disk.

        @param file : the file to write the data to.  If None, the 
                       configured file will be used.  
        """
        if not file:
            file = self.file
        if self.hasNoAssignments():
            if os.path.exists(file):  os.remove(file)
            try:
                del chainCache[file]
            except KeyError:
                pass
            return

        fd = open(file, "w")

        # Should really be "FILE = chain", but eups checks for version.  I've changed it to allow 
 	# chain, but let's not break backward compatibility with old eups versions 
        print >> fd, """FILE = version
PRODUCT = %s
CHAIN = %s
#***************************************\
""" % (self.name, self.tag)

        for fq in self.info.keys():
            mat = re.search(r"^([^:]+)(:?:(.*)$)?", fq)
            flavor = mat.group(1)
            qualifier = mat.group(3)
            if not qualifier:
                qualifier = ""

            print >> fd, """
#Group:
   FLAVOR = %s
   VERSION = %s
   QUALIFIERS = "%s"\
""" % (flavor, self.info[fq]["version"], qualifier)

            for field in self._fields:
                k = field.lower()

                if self.info[fq].has_key(k):
                    value = self.info[fq][k]
                    if not value:
                        continue

                    print >> fd, "   %s = %s" % (field.upper(), value)

            print >> fd, "#End:"

        fd.close()

        chainCache[file] = self.name, self.tag, copy.deepcopy(self.info)

    REGEX_KEYVAL = re.compile(r"^(\w+)\s*=\s*(.*)", flags = re.IGNORECASE)
    REGEX_GROUPEND = re.compile(r"^(End|Group)\s*:")

    def _read(self, file=None, verbosity=0):
        """
        read in data from a file, possibly overwring previously tagged products

        @param file : the file to read
        """
        if not file:
            file = self.file

        try:
            self.name, self.tag, self.info = chainCache[file]
            return
        except KeyError:
            pass

        try:
            fd = open(file)
        except IOError:
            return

        flavor = None
        for at, line in enumerate(fd):
            line = line.lstrip()  # remove any leading whitespace
            if not line or line.startswith('#'):
                continue

            #
            # Get key = value
            #
            mat = ChainFile.REGEX_KEYVAL.search(line)
            if mat:
                key = mat.group(1).lower()
                value = mat.group(2).strip('"')

            #
            # Ignore Group: and End:
            #
            elif ChainFile.REGEX_GROUPEND.search(line):
                continue
            else:
                raise RuntimeError, \
                      ("Unexpected line \"%s\" at %s:%d" % \
                         (line, self.file, at+1))

            #
            # Check for information about product
            #
            if key == "file":
                if value.lower() not in ["chain", "version"]:
                    raise RuntimeError, \
                          ("Expected \"File = Version\"; saw \"%s\" at %s:%d" \
                             % (line, self.file, at+1))

            elif key == "product":
                if not self.name:
                    self.name = value
                elif self.name != value:
                  if verbosity >= 0:
                    print >> stdwarn, \
                        "Warning: Unexpected product name, %s, in chain file; expected %s,\n  file=%s" % \
                        (value, self.name, file)

            elif key == "chain":
                if not self.tag:
                    self.tag = value
                elif self.tag != value:
                  if verbosity >= 0:
                    print >> stdwarn, \
                        "Warning: Unexpected tag/chain name, %s, in chain file; expected %s,\n  file=%s" % \
                        (value, self.tag, file)

            elif key == "flavor": # Now look for flavor-specific blocks
                flavor = value
                self.info[flavor] = {}
            else:
                if key == "qualifiers":
                    if value:           # flavor becomes e.g. Linux:build
                        newflavor = "%s:%s" % (flavor, value)
                        self.info[newflavor] = self.info[flavor]
                        del self.info[flavor]
                        flavor = newflavor
                else:
                    self.info[flavor][key] = value

        fd.close()

        chainCache[file] = self.name, self.tag, copy.deepcopy(self.info)

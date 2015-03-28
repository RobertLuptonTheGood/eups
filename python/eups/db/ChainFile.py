import os, re, sys, copy, glob
from eups.utils import ctimeTZ, isRealFilename, stdwarn, stderr, getUserName, defaultUserDataDir
import cPickle as pickle

who = getUserName(full=True)

class ChainFileCache(object):
    """
        Pickle cache for directories of .chain files

        Speeds up the access to data in .chain files, by keeping a pickle
        file of the contents. Exposes two public methods:

          __getitem__(chainFilename):
            - returns the (name, tag, info) tuple corresponding to data in
              the chainFilename, that can be used to initialize the
              ChainFile object

          getChainsInDir(dirName):
            - return a dictionary of chainFilename -> (name, tag, info) pairs
              for all .chain files in directory dirName

        The cache is stored in _chain_caches_ subdir of
        defaultUserDataDir(), typically ~/.eups.  Cache validity is checked
        by testing for mtime of the directory containing the .chain files;
        if it's greater than the time recorded in the pickle jar, it's
        assumed the directory has changed and needs to be regenerated.

        IMPORTANT: because of this strategy, any change to a .chain file in
        the directory must be followed by a change to directory mtime; if
        the modification is done by deleting the old file, and creating a
        new one (the current strategy employed by ChainFile), this is satisfied
        automatically.
   
    """

    def __init__(self):
        # Dictionary of per-directory caches.
        #   key = chain directory name, value = (cache, dir mtime),
        #   where cache: dict(key = chain file name, value = parsed file contents)
        self._caches = dict()

        # A set of keys from self._caches that need to be written to disk on
        # exit
        self._staleCacheFiles = set()

        # register self.autosave to run on interpreter exit, to write out
        # any stale caches
        import atexit
        atexit.register(self.autosave)

    def _cacheFilenameFor(self, dirName):
        """ Return the filename of the .pkl cache """
        dirName = os.path.normpath(dirName)
        return os.path.join(defaultUserDataDir(), '_chain_caches_', dirName[1:], "__chains__.pkl")

    def _refreshCache(self, dirName, dirCacheOld):
        """
            Refresh the cache of directory dirName, using the old cache to
            speed up the refresh.

            Do the refresh by iterating through all .chain files in dirName,
            loading the ones whose mtime is greatr than the old cache's
            mtime, and re-using the old cache entries for the rest.

            Returns the new (cache, dir mtime) tuple.

            NOTE: This method does not write the refreshed cache to the disk
                  -- the writing is deferred until interpreter exit, when
                  self.autosave() will be called.
        """
        cacheOld, mtimeOld = dirCacheOld
	cache = dict()

        chains = glob.glob(dirName + "/*.chain")
        print >>sys.stderr, "REBUILD CACHE:", dirName, mtimeOld, os.path.getmtime(dirName), len(chains), len([x for x in chains if(os.path.getmtime(x) > mtimeOld)])
        for chainFn in chains:
            if mtimeOld == 0 or os.path.getmtime(chainFn) > mtimeOld:		# mtimeOld == 0 is an optimization to avoid a getmtime call
                # load from .chain file
                print >>sys.stderr, "  ", chainFn, os.path.getsize(chainFn)
                cf = ChainFile(chainFn, readFile=False)
                cf._read()
                cache[chainFn] = ( cf.name, cf.tag, copy.deepcopy(cf.info) )
            else:
                # re-use existing entry
                cache[chainFn] = cacheOld[chainFn]

        return cache, os.path.getmtime(dirName)

    def getChainsInDir(self, dirName):
        """
            Return a dictionary of chainFilename -> (name, tag, info) pairs
            for all .chain files in directory dirName.

            Fetch the information from the cache, whenever possible.
        """

        # Cache already loaded?
        try:
            cache, mtime = self._caches[dirName]
        except KeyError:
            # Exists on disk?
            try:
                fp = open(self._cacheFilenameFor(dirName))
                cache, mtime = self._caches[dirName] = pickle.load(fp)
                fp.close()
                print >>sys.stderr, "LOAD:", dirName, len(cache)
            except:
                # Any exception while loading the cache (e.g., no file, or
                # corrupted pickle file, etc.) will invalidate it
                cache, mtime = dict(), 0

        # Do we need refreshing?
        mtimeDir = os.path.getmtime(dirName)
        if mtimeDir > mtime:
            cache, _ = self._caches[dirName] = self._refreshCache(dirName, (cache, mtime))
            self._staleCacheFiles.add(dirName)

        return cache

    def __getitem__(self, fn):
        """
            Return the (name, tag, info) tuple corresponding to data in the
            .chain file fn.  This tuple can be used to initialize the
            ChainFile object
        """
        cache = self.getChainsInDir(os.path.dirname(fn))
        return cache[fn]

    def _writeCacheForDir(self, cacheFn, dirCache):
        print >>sys.stderr, "WRITING:", cacheFn
        # Ensure the directory exists
        try:
            os.makedirs(os.path.dirname(cacheFn))
        except OSError:
            pass

        # Safely write the file
        tmpFn = cacheFn + ".tmp"

        fp = open(tmpFn, "w")
        pickle.dump(dirCache, fp, -1)
        fp.close()

        os.rename(tmpFn, cacheFn)

    def autosave(self):
        # write out any stale caches
        for dirName in self._staleCacheFiles:
            dirCache = self._refreshCache(dirName, self._caches[dirName])
            self._writeCacheForDir(self._cacheFilenameFor(dirName), dirCache )

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
                 readFile=True, info=None):

        # the file containing the tag information
        self.file = file

        # the name of the product.
        self.name = productName

        # the name of the tag being described
        self.tag = tag

        # tag assignment attributes as a dictionary.  Each key is a flavor 
        # name and its value is a properties set of named metadata.
        if info is None:
            self.info = {}
        else:
            self.info = info

        if readFile:
            try:
                self.name, self.tag, self.info = chainCache[file]
            except KeyError:
                pass

    @staticmethod
    def iterTagsInDir(dirName):
        for fn, (name, tag, info) in chainCache.getChainsInDir(dirName).iteritems():
            yield ChainFile(fn, name, tag, readFile=False, info=info)

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
            print >>sys.stderr, "  removing: ", file
            if os.path.exists(file):  os.remove(file)
            return

        print >>sys.stderr, "  writing: ", file
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

    REGEX_KEYVAL = re.compile(r"^(\w+)\s*=\s*(.*)", flags = re.IGNORECASE)
    REGEX_GROUPEND = re.compile(r"^(End|Group)\s*:")

    def _read(self, file=None, verbosity=0):
        """
        read in data from a file, possibly overwring previously tagged products
        
        Note: Can only be called from ChainFileCache._buildCache

        @param file : the file to read
        """
        if not file:
            file = self.file

        fd = open(file)

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

"""
The Eups class 
"""
import glob, re, os, pwd, shutil, sys, time
import filecmp
import fnmatch
import tempfile

import utils
from stack      import ProductStack, CacheOutOfSync
from db         import Database
from tags       import Tags, Tag, TagNotRecognized
from exceptions import ProductNotFound, EupsException, TableError, TableFileNotFound
from table      import Table
from Product    import Product
from Uses       import Uses
import hooks

class Eups(object):
    """
    An application interface to EUPS functionality.

    This class allows one to:
      o  query about versions of products known to EUPS
      o  declare new versions of products, making them known to EUPS
      o  set up the environment needed for using selected products
      o  assign tags (such as "stable" or "beta") to versions of products

    This class also maintains state about the user's preferences, including:
      o  the software stacks to be managed by EUPS (i.e. EUPS_PATH)
      o  behavioral preferences such as verbosity, overriding safe-guards 
         (the "force" option), etc.
    """

    debugFlag = False                   # set via --debug=debug

    # static variable:  the name of the EUPS database directory inside a EUPS-
    #  managed software stack
    ups_db = "ups_db"

    # staticmethod;  would use a decorator if we knew we had a new enough python
    def setEupsPath(path=None, dbz=None):
        if not path:
            path = os.environ.get("EUPS_PATH", [])

        if isinstance(path, str):
            path = path.split(":")

        if dbz:
            # if user provides dbz, restrict self.path to those directories that include /dbz/
            dbzRe = r"/%s(/|$)" % dbz
            path = [p for p in path if re.search(dbzRe, p)]

        eups_path = []
        for p in path:
            if not os.path.isdir(p):
                print >> sys.stderr, \
                      "%s in $EUPS_PATH does not contain a ups_db directory, and is being ignored" % p
                continue

            eups_path += [os.path.normpath(p)]

        os.environ["EUPS_PATH"] = ":".join(eups_path)
        return eups_path

    setEupsPath = staticmethod(setEupsPath)

    def __init__(self, flavor=None, path=None, dbz=None, root=None, readCache=True,
                 shell=None, verbose=0, quiet=0,
                 noaction=False, force=False, ignore_versions=False,
                 keep=False, max_depth=-1, preferredTags=None,
                 # above is the backward compatible signature
                 userDataDir=None, asAdmin=False, setupType=[], validSetupTypes=None, vro={},
                 exact_version=None, useLocks=True
                 ):
        """
        @param path             the colon-delimited list of product stack 
                                  directories to find products in.
        @param root             used during setup(), this is the directory to 
                                  find the top-level target product.  Its 
                                  dependencies can be found in any of the 
                                  directories in path.  
        @param userDataDir      the directory where per-user information is 
                                  cached.  If None, this defaults to ~/.eups.
        @param asAdmin          if True, product caches will be saved in the
                                  database directories rather than under the 
                                  user directory.  User tags will not be 
                                  available for writable stacks in path.  
        @param setupType        the setup type.  This will cause conditional
                                  sections of the table filebased on "type" 
                                  (e.g. "if (type == build) {...}") to be 
                                  executed.  If setupType is a list then the conditional will
                                  be interpreted as "if (build in type) {...}"
        @param validSetupTypes  the names to recognize as valid setupTypes.  
                                  This list can be given either as a 
                                  space-delimited string or a python list of 
                                  strings (each being a separate name).  If 
                                  None, the list will be set according to the
                                  user's configuration.
        @param preferredTags      List of tags to process in order; None will be intepreted as the default
        @param exact_version      Where possible, use the exact versions that were previously declared
        """

        self.verbose = verbose

        if not shell:
            try:
                shell = os.environ["SHELL"]
            except KeyError:
                raise EupsException("I cannot guess what shell you're running as $SHELL isn't set")

            if re.search(r"(^|/)(bash|ksh|sh)$", shell):
                shell = "sh"
            elif re.search(r"(^|/)(csh|tcsh)$", shell):
                shell = "csh"
            elif re.search(r"(^|/)(zsh)$", shell):
                shell = "zsh"
            else:
                raise EupsException("Unknown shell type %s" % shell)    

        self.shell = shell

        if not flavor:
            flavor = utils.determineFlavor()
        self.flavor = flavor

        self.path = Eups.setEupsPath(path, dbz)

        if not self.path and not root:
            if dbz:
                raise EupsException("No element of EUPS_PATH matches \"%s\"" % dbz)
            else:
                raise EupsException("No EUPS_PATH is defined")

        #
        # Load local customisations
        #
        path = self.path[:]; path.reverse()  # the first elements on EUPS_PATH have the highest priority
        hooks.loadCustomization(verbose, path=path)
                 
        self.oldEnviron = os.environ.copy() # the initial version of the environment

        self.aliases = {}               # aliases that we should set
        self.oldAliases = {}            # initial value of aliases.  This is a bit of a fake, as we
                                        # don't know how to set it but (un)?setAlias knows how to handle this

        self.who = re.sub(r",.*", "", pwd.getpwuid(os.getuid())[4])

        if root:
            root = os.path.expanduser(root)
            if not os.path.isabs(root):
                root = os.path.join(os.getcwd(), root)
            root = os.path.normpath(root)

        # product directory to assume for a (local) setup request
        self.root = root

        self.version_cmp = hooks.version_cmp
        self.quiet = quiet
        self.keep = keep

        # set the valid setup types
        if isinstance(validSetupTypes, str):
            validSetupTypes = validSetupTypes.split()
        self._validSetupTypes = validSetupTypes
        if self._validSetupTypes is None:
            self._validSetupTypes = hooks.config.Eups.setupTypes
            if isinstance(self._validSetupTypes, str):
                utils.deprecated("Setting config.Eups.setupTypes with a string is deprecated; " +
                                 "please use a list.", self.quiet)
                self._validSetupTypes.split()
        #
        # Split and check our setupType
        #
        if setupType in (None, ""):
            self.setupType = []
        elif isinstance(setupType, str):
            if re.search(r"[\s,]", setupType):
                self.setupType = re.split(r"[\s,]+", setupType)
            else:
                self.setupType = [setupType]
        else:
            self.setupType = setupType

        for st in self.setupType:
            if not self._isValidSetupType(st):
                raise EupsException('Unknown setup type %s; valid types are: "%s"' % \
                                    (st, '", "'.join(self._validSetupTypes)))
        #
        # a look-up of the products that have been setup since the life 
        # of this instance.  Used by setup().
        #
        self.alreadySetupProducts = {}

        self.noaction = noaction
        self.force = force
        self.ignore_versions = ignore_versions
        if exact_version is not None and exact_version and self.setupType.count("exact") == 0:
            self.setupType.append("exact")

        self.exact_version = self.setupType.count("exact") > 0
        self.max_depth = max_depth      # == 0 => only setup toplevel package

        self.locallyCurrent = {}        # products declared local only within self

        self._msgs = {}                 # used to suppress messages
        self._msgs["setup"] = {}        # used to suppress messages about setups

        self._stacks = {}               # used for saving/restoring state
        self._stacks["env"] = []        # environment that we'll setup
        self._stacks["vro"] = []        # the VRO
        #
        # The Version Resolution Order.  The entries may be a string (which should be split), or a dictionary
        # indexed by dictionary names in the EUPS_PATH (as set by -z); each value in this dictionary should
        # be split
        #
        if vro:
            self.userVRO = True
        else:
            self.userVRO = False
            vro = hooks.config.Eups.VRO

        if not isinstance(vro, dict):
            vro = {"commandLine" : vro}

        self._vroDict = {}
        for key, v in vro.items():
            if isinstance(v, dict):
                _v = {}
                for k, v in v.items():
                    _v[k] = v.split()
                v = _v
            else:
                v = v.split()

            self._vroDict[key] = v

        self._vro = None                # the actual VRO to use
        # 
        # determine the user data directory.  This is a place to store 
        # user preferences and caches of product information.
        # 
        if not userDataDir:
            userDataDir = utils.defaultUserDataDir()
            if not userDataDir and self.quiet <= 0:
                print >> sys.stderr, "Warning: Unable to find home directory!"

        if userDataDir and not self.getUpsDB(userDataDir, noRaise=True):
            if self.quiet <= 0:
                print >> sys.stderr, \
                    "Creating user data directory: " + userDataDir
            self.getUpsDB(userDataDir, create=True)

        if userDataDir and not utils.isDbWritable(userDataDir):
            userDataDir = None

        if userDataDir and not os.path.isdir(userDataDir):
            raise EupsException("User data directory not found (as a directory): " + userDataDir)
                                
        self.userDataDir = userDataDir
        self.asAdmin = asAdmin

        #
        # Get product information:  
        #   * read the cached version of product info
        #
        self.versions = {}
        neededFlavors = utils.Flavor().getFallbackFlavors(self.flavor, True)
        if readCache:
          for p in self.path:

            # the product cache.  If cache is non-existent or out of date,
            # the product info will be refreshed from the database
            dbpath = self.getUpsDB(p)
            cacheDir = dbpath
            userCacheDir = self._makeUserCacheDir(p)
            if not self.asAdmin or not utils.isDbWritable(p):
                # use a user-writable alternate location for the cache
                cacheDir = userCacheDir
            self.versions[p] = ProductStack.fromCache(dbpath, neededFlavors, 
                                                      persistDir=cacheDir, 
                                                      userTagDir=userCacheDir,
                                                      updateCache=True, 
                                                      autosave=False,
                                                      verbose=self.verbose)
        #
        # 
        fallbackList = hooks.config.Eups.fallbackFlavors
        if not isinstance(fallbackList, dict):
            fallbackList = {None : fallbackList}
        for flavor, fbl in fallbackList.items():
            if isinstance(fbl, str):
                fbl = fbl.split()
            utils.Flavor().setFallbackFlavors(flavor, fbl)
        # 
        # load up the recognized tags.
        # 
        user = pwd.getpwuid(os.geteuid())[0] # our username is always a valid user tag (if not already global)
        if hooks.config.Eups.userTags.count(user) == 0 and \
           hooks.config.Eups.globalTags.count(user) == 0:
            hooks.config.Eups.userTags.append(user)

        self.tags = Tags()
        self.commandLineTagNames = []   # names of tags specified on the command line; set in selectVRO

        for tags, group in [
            (hooks.config.Eups.globalTags, None), # None => global
            (["newest",], None),
            (hooks.config.Eups.userTags, Tags.user),
            (["commandLine", "keep", "path", "setup", "type",
              "version", "versionExpr", "warn",], Tags.pseudo),
            ]:
            if isinstance(tags, str):
                tags = tags.split()
            for tag in tags:
                try:
                    self.tags.registerTag(tag, group)
                except RuntimeError, e:
                    raise RuntimeError("Unable to process tag %s: %s" % (tag, e))

        self._loadServerTags(useLocks=useLocks)
        self._loadUserTags(useLocks=useLocks)
        #
        # Handle preferred tags; this is a list where None means hooks.config.Eups.preferredTags
        #
        if preferredTags is None:
            preferredTags = [None]

        pt, preferredTags = preferredTags, []
        for tags in pt:
            if not tags:
                tags = hooks.config.Eups.preferredTags
            if isinstance(tags, str):
                tags = tags.split()

            for t in tags:
                preferredTags.append(t)
                
        q = utils.Quiet(self)
        self._kindlySetPreferredTags(preferredTags)
        del q
        #
        # Find which tags are reserved to the installation
        #
        self._reservedTags = hooks.config.Eups.reservedTags
        if self._reservedTags is None:
            self._reservedTags = []
        elif isinstance(self._reservedTags, str):
            self._reservedTags = self._reservedTags.split()
        #
        # Some tags are always reserved
        #
        for k in ["newest",]:
            if not self._reservedTags.count(k):
                self._reservedTags.append(k)
        #
        # and some are used internally by eups
        #
        self._internalTags = []
        for k in ["commandLine", "keep", "type", "version", "versionExpr", "warn"]:
            self._internalTags.append(k)
        #
        # Check that nobody's used an internal tag by mistake (setup -t keep would be bad...)
        #
        for t in self.tags.getTags():
            if (t.isUser() or t.isGlobal()) and self.isInternalTag(t, True):
                pass
        #
        # Find locally-setup products in the environment
        #
        self.localVersions = {}

        q = utils.Quiet(self)
        for product in self.getSetupProducts():
            try:
                if product.version.startswith(Product.LocalVersionPrefix):
                    self.localVersions[product.name] = os.environ[self._envarDirName(product.name)]
            except TypeError:
                pass

    def pushStack(self, what, value=None):
        """Push some state onto a stack; see also popStack() and dropStack()

The what argument tells us what sort of state is expected (allowed values are defined in __init__)
        """
        if not self._stacks.has_key(what):
            raise RuntimeError, ("Programming error: attempt to use stack \"%s\"" % what)

        if what == "env":
            value = os.environ.copy()
        elif what == "vro":
            self.setPreferredTags(value)

        self._stacks[what].append(value)

        self.__showStack("push", what)

    def popStack(self, what):
        """Pop some state off a stack, restoring the previous value; see also pushStack() and dropStack()

The what argument tells us what sort of state is expected (allowed values are defined in __init__)
        """
        if not self._stacks.has_key(what):
            raise RuntimeError, ("Programming error: attempt to use stack \"%s\"" % what)

        try:
            value = self._stacks[what].pop()
        except IndexError:
            raise RuntimeError, ("Programming error: stack \"%s\" doesn't have an element to pop" % what)

        if what == "env":
            os.environ = value
        elif what == "vro":
            self.setPreferredTags(value)

        self.__showStack("pop", what)

    def dropStack(self, what):
        """Drop the bottom element of a stack; see also pushStack() and popStack()

The what argument tells us what sort of state is expected (allowed values are defined in __init__)
        """
        if not self._stacks.has_key(what):
            raise RuntimeError, ("Programming error: attempt to use stack \"%s\"" % what)

        try:
            self._stacks[what].pop()
        except IndexError:
            raise RuntimeError, ("Programming error: stack \"%s\" doesn't have an element to drop" % what)

        self.__showStack("drop", what)

    def __showStack(self, op, what):
        """Debugging routine for stack"""
        if False:
            values = [e.has_key("BASE_DIR") for e in self._stacks["env"] + [os.environ]]
            values.insert(-1, ":")
            utils.debug("%-5s" % op, len(self._stacks[what]), values)

    def _databaseFor(self, eupsPathDir, dbpath=None):
        if not dbpath:
            dbpath = self.getUpsDB(eupsPathDir)
        return Database(dbpath, userTagRoot=self._userStackCache(eupsPathDir))

    def _userStackCache(self, eupsPathDir):
        if not self.userDataDir:
            return None
        return utils.userStackCacheFor(eupsPathDir, self.userDataDir)

    def _makeUserCacheDir(self, eupsPathDir):
        cachedir = self._userStackCache(eupsPathDir)
        if cachedir and not os.path.exists(cachedir):
            os.makedirs(cachedir)
            try:
                readme = open(os.path.join(cachedir,"README"), "w")
                try:
                    print >> readme, "User cache directory for", eupsPathDir
                finally:
                    readme.close()
            except:
                pass
        return cachedir

    def _loadServerTags(self, useLocks=True):
        tags = {}
        for path in self.path:
            tags[path] = Tags()

            # start by looking for a cached list
            cachedTags = self.tags.loadFromEupsPath(path, self.verbose)
            if cachedTags:
                for t in cachedTags:
                    tags[path].registerTag(t)
                continue

            # if no list cached, try asking the cached product stack
            tagNames = set()
            tagUsedInProducts = None    # used for better diagnostics

            if self.versions.has_key(path):
                for t in self.versions[path].getTags():
                    tagNames.add(t)

            for t in tagNames:
                t = Tag.parse(t)
                if not (t.isUser() or self.tags.isRecognized(t.name)):
                    msg = "Unknown tag found in %s stack: \"%s\"" % (path, t)
                    if self.verbose:
                        if tagUsedInProducts is None:
                            tagUsedInProducts = {}
                            db = Database(self.getUpsDB(path))
                            for pname in db.findProductNames():
                                for tag, v, f in db.getTagAssignments(pname):
                                    tagNames.add(tag)
                                    if not tagUsedInProducts.has_key(tag):
                                        tagUsedInProducts[tag] = []
                                    tagUsedInProducts[tag].append(pname)

                        if tagUsedInProducts.has_key(t.name):
                            msg += " (in [%s])" % (", ".join(sorted(tagUsedInProducts[t.name])))

                    if True or self.force:
                        print >> sys.stderr, "%s; defining" % (msg)

                        tags[path].registerTag(t.name, t.group)
                    else:
                        print >> sys.stderr, "%s (consider --force)" % (msg)
                        sys.exit(1)

            if self.asAdmin and utils.isDbWritable(p):
                # cache the global tags
                dbpath = self.getUpsDB(path)
                for group in tags[path].bygrp.keys():
                    tags[path].saveGroup(group, dbpath)

            # now register them with self.tags; this can only happen with --force
            for tag in tags[path].getTags():
                if not (tag.isUser() or self.tags.isRecognized(tag)):
                    self.tags.registerTag(tag.name, tag.group)

        return tags

    def _loadUserTags(self, useLocks=True):
        for path in self.path:
            # start by looking for a cached list
            dirName = self._userStackCache(path)
            if not dirName or not os.path.isdir(dirName) or self.tags.loadUserTags(dirName, useLocks=useLocks):
                continue

            # if no list cached, try asking the cached product stack
            tags = Tags()
            if self.versions.has_key(path):
                for t in self.versions[path].getTags():
                    t = Tag.parse(t)
                    if t.isUser() and not self.tags.isRecognized(t.name):
                        tags.registerUserTag(t.name)

            else:
                # consult the individual User tag Chain files (via Database)
                db = Database(self.getUpsDB(path), dirName)
                for pname in db.findProductNames():
                    for tag, v, f in db.getTagAssignments(pname):
                        t = Tag.parse(tag)
                        if not t.isUser() and self.tags.isRecognized(t.name):
                            tags.registerTag(t.name, t.group)

            # cache the user tags:
            tags.saveUserTags(dirName)

            # now register them with self.tags:
            for tag in tags.getTags():
                if tag.isUser() and not self.tags.isRecognized(tag):
                    self.tags.registerUserTag(tag.name)
        #
        # Now see if we need to read some other user's tags
        #
        db = Database(self.getUpsDB(path))

        for tag, owner in self.tags.owners.items():
            for p in self.path:
                userCacheDir = utils.userStackCacheFor(p, userDataDir=utils.defaultUserDataDir(owner))
                extraDb = Database(self.getUpsDB(p), userCacheDir)

                db.addUserTagDb(userCacheDir, p, userId=owner)

                if not self.versions.has_key(p):
                    continue

                for productName in extraDb.findProductNames():
                    for etag, versionName, flavor in extraDb.getTagAssignments(productName, glob=False):
                        if Tag(etag) != tag:
                            continue

                        try:
                            self.versions[p].lookup[flavor][productName].tags[etag] = versionName
                        except KeyError:
                            continue
                
    def setPreferredTags(self, tags):
        """
        set a list of tags to prefer when selecting products.  The 
        list order indicates the order of preference with the most 
        preferred tag being first.
        @param tags   the tags as a list or a space-delimited string.
                        Unrecognized tag names will be ignored.
        """
        self._kindlySetPreferredTags(tags, True)

    def _kindlySetPreferredTags(self, tags, strict=False):

        if isinstance(tags, str):
            tags = tags.split()
        if not isinstance(tags, list):
            raise TypeError("Eups.setPreferredTags(): arg not a list")

        _tags = tags
        tags = []; notokay = []
        for t in _tags:
            if re.search(r"^file:", t):
                t0 = t
                t = os.path.expanduser(re.sub(r"^file:", "", t))
                if os.path.isfile(t):
                    tags.append(t)
                else:
                    notokay.append("%s [no such file]" % t0)
            elif re.search(r":.+$", t):
                tbase, suffix = t.split(":")

                if self.tags.isRecognized(tbase):
                    tags.append(t)
                else:
                    notokay.append(t)
            elif self.tags.isRecognized(t) or re.search(r"^(:|\d+)$", t):
                tags.append(t)
            elif os.path.isfile(t):
                tags.append(t)
            else:
                notokay.append(t)

        if notokay:
            if strict:
                raise TagNotRecognized(str(notokay), 
                                       msg="Unsupported tag(s): " + 
                                           ", ".join(notokay))
            elif self.quiet <= 0:
                print >> sys.stderr, \
                      "Ignoring unsupported tags:", ", ".join(notokay)
                tags = filter(self.tags.isRecognized, tags)

        if len(tags) == 0:
            if self.quiet <= 0 or self.verbose > 1:
                print >> sys.stderr, \
                      "Warning: No recognized tags; not updating preferred list"
        else:
            self.preferredTags = tags

    def getPreferredTags(self):
        """
        Return the list of  tags to prefer when selecting products.  The 
        list order indicates the order of preference with the most 
        preferred tag being first.
        """
        return list(self.preferredTags)

    def clearLocks(self):
        """Clear all lock files"""
        locations = self.path
        if self.userDataDir:
            locations.append(self.userDataDir)
        
        for p in locations:
            for root, dirs, files in os.walk(p):
                for lockfile in filter(lambda f: f.endswith(".lock"), files):
                    lockfile = os.path.join(root, lockfile)
                    if self.verbose:
                        print "Removing", lockfile
                    try:
                        os.remove(lockfile)
                    except Exception, e:
                        print >> sys.stderr, ("Error deleting %s: %s" % (lockfile, e))

    def findSetupVersion(self, productName, environ=None):
        """Find setup version of a product, returning the version, eupsPathDir, productDir, None (for tablefile), and flavor
        If environ is specified search it for environment variables; otherwise look in os.environ
        """

        if not environ:
            environ = os.environ

        versionName, eupsPathDir, productDir, tablefile, flavor = "setup", None, None, None, None
        try:
            args = environ[self._envarSetupName(productName)].split()
        except KeyError:
            return None, eupsPathDir, productDir, tablefile, flavor

        try:
            sproductName = args.pop(0)
        except IndexError:          # Oh dear;  "$setupEnvPrefix()_productName" must be malformed
            return None, eupsPathDir, productDir, tablefile, flavor
            
        if sproductName != productName:
            if self.verbose > 1:
                print >> sys.stderr, \
                      "Warning: product name %s != %s (probable mix of old and new eups)" %(productName, sproductName)

        if productName == "eups" and not args: # you can get here if you initialised eups by sourcing setups.c?sh
            args = ["%s%s" % (Product.LocalVersionPrefix, environ["EUPS_DIR"]), "-Z", "(none)"]

        if len(args) > 0 and args[0] != "-f":
            versionName = args.pop(0)

        if len(args) > 1 and args[0] == "-f":
            args.pop(0);  flavor = args.pop(0)

        if len(args) > 1 and (args[0] == "-Z" or args[0] == "-z"):
            args.pop(0);  eupsPathDir = args.pop(0)

        if len(args) > 1 and (args[0] == "-m"):
            args.pop(0);  tablefile = args.pop(0)

        if args:
            raise RuntimeError, ("Unexpected arguments: %s" % args)

        if versionName.startswith(Product.LocalVersionPrefix):
            productDir = None           # If we set productDir, the Product ctor ignores the local version
        else:
            if self.tags.isRecognized(versionName) and utils.isRealFilename(eupsPathDir):
                # It might be a tag; see if it's a regular version
                product = self.findProduct(productName, versionName, eupsPathDirs=eupsPathDir, flavor=flavor)
                if not product:
                    # get qualified tag name (the database needs to see user tags as "user:...")
                    tag = str(self.tags.getTag(versionName))
                    vers = self._databaseFor(eupsPathDir).getTaggedVersion(tag, productName, flavor,
                                                                           searchUserDB=True)
                    if vers is not None:
                        versionName = vers

            try:
                productDir = environ[self._envarDirName(productName)]
                if productDir and not tablefile:
                    tablefile = os.path.join(productDir,"ups",productName+".table")
                    if not os.path.exists(tablefile):
                        tablefile = "none"
            except KeyError:
                pass
            
        return versionName, eupsPathDir, productDir, tablefile, flavor

    def _envarSetupName(self, productName):
        # Return the name of the product's how-I-was-setup environment variable
        return utils.setupEnvNameFor(productName)

    def _envarDirName(self, productName):
        # Return the name of the product directory's environment variable
        return utils.dirEnvNameFor(productName)


    def findProductFromVRO(self, name, version=None, versionExpr=None, eupsPathDirs=None, flavor=None,
                           noCache=False, recursionDepth=0, vro=None, optional=False):
        """
        return a product matching the given constraints by searching the VRO (we also return info about the
        VRO element that matched).  By default, the cache will be searched when available; otherwise, the
        product database will be searched.  Return (None, []) if a match was not found.
        
        @param name          the name of the desired product
        @param version       the desired version.  This can in one of the 
                                following forms:
                                 *  an explicit version 
                                 *  a version expression (e.g. ">=3.3") (see also versionExpr)
                                 *  a Tag instance 
                                 *  null, in which case, the (most) preferred 
                                      version will be returned.
        @param versionExpr   An expression specifying the constraints on the version
        @param eupsPathDirs  the EUPS path directories to search.  (Each should 
                                have a ups_db sub-directory.)  If None (def.),
                                configured EUPS_PATH directories will be 
                                searched.
        @param flavor        the desired flavor.  If None (default), the 
                                default flavor will be searched for.
        @param noCache       if true, the software inventory cache should not be 
                                used to find products; otherwise, it will be used
                                to the extent it is available.  
        @param recursionDepth Recursion depth (0 => top, so e.g. keep should be ignored)
        """

        if not flavor:
            flavor = self.flavor
        if eupsPathDirs is None:
            eupsPathDirs = self.path
        if isinstance(eupsPathDirs, str):
            eupsPathDirs = [eupsPathDirs]

        product, vroReason = None, None

        if not vro:
            vro = self.getPreferredTags()

        for i in range(len(vro)):
            vroTag = vro[i]
            vroTag0 = vroTag            # we may modify vroTag

            preVro =  vro[0    :i]
            postVro = vro[i + 1:]
            
            if vroTag in ("path"):
                continue

            elif recursionDepth > 0 and vroTag in ("keep",):
                product = self.alreadySetupProducts.get(name)
                if product:
                    product = product[0]
                    vroReason = [vroTag, None]
                    break
                    
            elif vroTag == "commandLine":
                if self.alreadySetupProducts.has_key(name): # name is already setup
                    oproduct, ovroReason = self.alreadySetupProducts[name]
                    if ovroReason and ovroReason[0] == "commandLine":
                        product, vroReason = oproduct, ovroReason
                        break

            elif vroTag in ("version", "versionExpr",):

                if not version or self.ignore_versions:
                    continue

                if self.isLegalRelativeVersion(version): # version is actually a versionExpr
                    if vroTag == "version":
                        if "versionExpr" in postVro:
                            continue
                        else:
                            print >> sys.stderr, "Failed to find %s %s for flavor %s" % \
                                  (name, version, flavor)
                            break
                    
                    versionExpr = version
                    
                if vroTag == "versionExpr" and versionExpr:
                    if self.isLegalRelativeVersion(versionExpr):  # raises exception if bad syntax used
                        products = self._findProductsByExpr(name, versionExpr, eupsPathDirs, flavor, noCache)
                        product = self._selectPreferredProduct(products, ["newest"])

                        if product:
                            vroReason = [vroTag, versionExpr]
                            break
                #
                # If we failed to find a versionExpr, we can still use the explicit version
                #
                # Search path for an explicit version
                #
                vroTag = "version"
                for root in eupsPathDirs:
                    if noCache or not self.versions.has_key(root) or not self.versions[root]:
                        # go directly to the EUPS database
                        if not os.path.exists(self.getUpsDB(root)):
                            if self.verbose:
                                print >> sys.stderr, "Skipping missing EUPS stack:", dbpath
                            continue

                        try:
                            product = self._databaseFor(root).findProduct(name, version, flavor)
                            if product:
                                vroReason = [vroTag, version]
                                break
                        except ProductNotFound:
                            product = None
                    else:
                        # consult the cache
                        try:
                            self.versions[root].ensureInSync(verbose=self.verbose)
                            product = self.versions[root].getProduct(name, version, flavor)
                            vroReason = [vroTag, version]
                            break
                        except ProductNotFound:
                            pass

                if product:
                    if recursionDepth == 0:
                        vroReason[0] = "commandLine"
                else:
                    if not "version" in postVro and not "versionExpr" in postVro:
                        if self.verbose > self.quiet:
                            print >> sys.stderr, "Failed to find %s %s for flavor %s" % \
                                  (name, version, flavor)
                        break

            elif re.search(r"^warn(:\d+)?$", vroTag):
                debugLevel = int(vroTag.split(":")[1])

                if optional:
                    debugLevel += 2
                if self.quiet:
                    debugLevel += 0
                    
                if self.verbose >= debugLevel:
                    if version:
                        vname = version
                    else:
                        vname = "\"\""

                    if recursionDepth:
                        indent = "            "
                    else:
                        indent = ""

                    msg = "%sVRO [%s] failed to match for %s version %s" % \
                          (indent, ", ".join(filter(lambda x: not re.search("^warn(:\d+)?$", x), preVro)),
                           name, vname,)
                    if postVro:
                        msg += "; trying [%s]" % \
                               (", ".join(filter(lambda x: not re.search("^warn(:\d+)?$", x), postVro)))
                    if flavor:
                        msg += " (Flavor: %s)" % flavor

                    print >> sys.stderr, msg

            elif self.tags.isRecognized(vroTag) or os.path.isfile(vroTag):
                # search for a tagged version
                if os.path.isfile(vroTag):
                    product = self._findTaggedProductFromFile(name, vroTag, eupsPathDirs, flavor, noCache)
                else:
                    product = self._findTaggedProduct(name, self.tags.getTag(vroTag), eupsPathDirs,
                                                  flavor, noCache)

                if not product:
                    continue
                
                vroReason = [vroTag, None]

            elif re.search(r"^type:(.+)$", vroTag):
                setupType = vroTag.split(":")[1]
                self.setupType += [setupType]

                if setupType == "exact":
                    self.exact_version = True
                    self.makeVroExact()

            else:
                print >> sys.stderr, "YOU CAN'T GET HERE", vroTag
                if False:
                    product = self.findProduct(name, version=Tag(vroTag), eupsPathDirs=eupsPathDirs,
                                               flavor=flavor, noCache=noCache)

            if product:
                break

        if product:
            if self.alreadySetupProducts.has_key(name): # name is already setup
                oproduct, ovroReason = self.alreadySetupProducts[name]
                if ovroReason:              # we setup this product
                    ovroTag = ovroReason[0] # tag used to select the product last time we saw it

                    try:
                        if vro.count(ovroTag) and \
                               vro.index(vroTag0) > vro.index(ovroTag): # old vro tag takes priority
                            if self.verbose > 1:
                                print >> sys.stderr, "%s%s has higher priority than %s in your VRO; keeping %s %s" % \
                                      (13*" ", ovroTag, vroTag0, oproduct.name, oproduct.version)
                                
                            product, vroReason, vroTag = oproduct, ovroReason, ovroTag
                    except Exception, e:
                        utils.debug("RHL", name, vroTag, vro, vroReason, e)
                        pass
                else:                   # setup by previous setup command
                    if oproduct.version != product.version:
                        if self.verbose > 1:
                            print >> sys.stderr, "%s%s %s replaces previously setup %s %s" % (13*" ",
                                                                             product.name, product.version,
                                                                             oproduct.name, oproduct.version)

            if self.verbose > 2:
                print >> sys.stderr, ("VRO used %-20s " % (vroTag)),
            
        return [product, vroReason]

    def findProduct(self, name, version=None, eupsPathDirs=None, flavor=None,
                    noCache=False):
        """
        return a product matching the given constraints.  By default, the 
        cache will be searched when available; otherwise, the product 
        database will be searched.  Return None if a match was not found.
        @param name          the name of the desired product
        @param version       the desired version.  This can in one of the 
                                following forms:
                                 *  an explicit version 
                                 *  a version expression (e.g. ">=3.3")
                                 *  a Tag instance 
                                 *  null, in which case, the (most) preferred 
                                      version will be returned.
        @param eupsPathDirs  the EUPS path directories to search.  (Each should 
                                have a ups_db sub-directory.)  If None (def.),
                                configured EUPS_PATH directories will be 
                                searched.
        @param flavor        the desired flavor.  If None (default), the 
                                default flavor will be searched for.
        @param noCache       if true, the software inventory cache should not be 
                                used to find products; otherwise, it will be used
                                to the extent it is available.  
        """

        if not version or (not isinstance(version, Tag) and self.ignore_versions):
            return self.findPreferredProduct(name, eupsPathDirs, flavor, noCache=noCache)

        if not flavor:
            flavor = self.flavor
        if eupsPathDirs is None:
            eupsPathDirs = self.path
        if isinstance(eupsPathDirs, str):
            eupsPathDirs = [eupsPathDirs]

        if isinstance(version, str):
            if self.isLegalRelativeVersion(version):  # raises exception if bad syntax used
                return self._findPreferredProductByExpr(name, version, 
                                                        eupsPathDirs, flavor, 
                                                        noCache)

        if isinstance(version, Tag):
            # search for a tagged version
            return self._findTaggedProduct(name, version, eupsPathDirs, flavor, noCache)

        # search path for an explicit version 
        for root in eupsPathDirs:
            if noCache or not self.versions.has_key(root) or not self.versions[root]:
                # go directly to the EUPS database
                if not os.path.exists(self.getUpsDB(root)):
                    if self.verbose:
                        print >> sys.stderr, "Skipping missing EUPS stack:", self.getUpsDB(root)
                    continue

                try:
                    product = self._databaseFor(root).findProduct(name, version, flavor)
                except ProductNotFound:
                    product = None
    
                if product:
                    return product

            else:
                # consult the cache
                try:
                    self.versions[root].ensureInSync(verbose=self.verbose)
                    return self.versions[root].getProduct(name, version, flavor)
                except ProductNotFound:
                    pass

        return None

    def findTaggedProduct(self, name, tag, eupsPathDirs=None, flavor=None,
                          noCache=False):
        """
        return a version of a product that has a given tag assigned to it.  
        By default, the cache will be searched when available; otherwise, 
        the product database will be searched.  Return None if a match was 
        not found.
        @param name          the name of the desired product
        @param tag           the desired tag.  This can either be string 
                                giving the tag name or a Tag instance.  
        @param eupsPathDirs  the EUPS path directories to search.  (Each should 
                                have a ups_db sub-directory.)  If None (def.),
                                configured EUPS_PATH directories will be 
                                searched.
        @param flavor        the desired flavor.  If None (default), the 
                                default flavor will be searched for.
        @param noCache       if true, the software inventory cache should not 
                                be used to find products; otherwise, it will 
                                be used to the extent it is available.  
        @throws TagNotRecongized  if the given tag is not valid
        """
        if not flavor:
            flavor = self.flavor
        if eupsPathDirs is None:
            eupsPathDirs = self.path
        if isinstance(eupsPathDirs, str):
            eupsPathDirs = [eupsPathDirs]

        try:
            tag = self.tags.getTag(tag)
            return self._findTaggedProduct(name, tag, eupsPathDirs, flavor, noCache)
        except TagNotRecognized:
            return self._findTaggedProductFromFile(name, tag, eupsPathDirs, flavor, noCache)

    def _findTaggedProduct(self, name, tag, eupsPathDirs=None, flavor=None, noCache=False):
        """
        find the first version assigned a given tag.
        @param name          the name of the product
        @param tag           the desired tag as a Tag instance
        @param eupsPathDirs  the Eups path directories to search
        @param flavor        the desired flavor
        @param noCache       if true, do not use the product inventory cache;
                               else (the default), a cache will be used if
                               available.
        """

        if not flavor:
            flavor = self.flavor
        if eupsPathDirs is None:
            eupsPathDirs = self.path
        if isinstance(eupsPathDirs, str):
            eupsPathDirs = [eupsPathDirs]

        if tag.name == "newest":
            return self._findNewestProduct(name, eupsPathDirs, flavor)

        if tag.name == "setup":
            out = self.findSetupProduct(name)
            if out is not None and out.flavor != flavor:
                # not the requested flavor
                out = None
            return out

        for root in eupsPathDirs:
            if noCache or not self.versions.has_key(root) or not self.versions[root]:
                # go directly to the EUPS database
                if not os.path.exists(self.getUpsDB(root)):
                    if self.verbose:
                        print >> sys.stderr, "Skipping missing EUPS stack:", dbpath
                    continue

                db = self._databaseFor(root)
                try:
                    version = db.getTaggedVersion(tag, name, flavor,searchUserDB=True)
                    if version is not None:
                        prod = db.findProduct(name, version, flavor)
                        if prod:
                            return prod
                        else:
                            if self.verbose > 0:
                                print >> sys.stderr, "Tag %s is declared in %s for %s, but is missing" % \
                                      (tag, name, root)
                except ProductNotFound:
                    # product by this name not found in this database
                    continue

            else:
                # consult the cache
                try: 
                    self.versions[root].ensureInSync(verbose=self.verbose)
                    prod = self.versions[root].getTaggedProduct(name, flavor, tag)
                    if prod:
                        return prod
                except ProductNotFound:
                    pass

        return None

    def _findTaggedProductFromFile(self, name, fileName, eupsPathDirs=None, flavor=None, noCache=False):
        """
        find the first product listed in a tagFile, i.e. a file containing lines of
           productName    version [....]
           (optionally prefixed by some number or "|" and " ", as put out by "eups list -D -s")
        or
           setupRequired(productName [-X ...] version ...)
           
        @param name          the name of the product
        @param tag           the file listing productNames and versions
        @param eupsPathDirs  the Eups path directories to search
        @param flavor        the desired flavor
        @param noCache       if true, do not use the product inventory cache;
                               else (the default), a cache will be used if
                               available.
        """

        if not flavor:
            flavor = self.flavor
        if eupsPathDirs is None:
            eupsPathDirs = self.path
        if isinstance(eupsPathDirs, str):
            eupsPathDirs = [eupsPathDirs]
        #
        # Read file seeing if it lists a desired version of product name
        #
        fileName = re.sub(r"^file:", "", fileName)
        fileName = os.path.expanduser(fileName)

        try:
            fd = open(fileName, "r")
        except IOError:
            raise TagNotRecognized(str(fileName))

        version = None

        lineNo = 0                      # for diagnostics
        for line in fd.readlines():
            lineNo += 1
            line = re.sub("^[|\s]*", "", line)
            line = re.sub("\s*$", "", line)

            if not line or re.search(r"^#", line):
                continue
            #
            # The line may either be "product version [...]" or # "setupRequired(product version)"
            #
            mat = re.search(r"^setupRequired\(([^)]+)\)", line)
            if mat:
                fields = mat.group(1)
                fields = re.sub(r"-\S+\s+", "", fields) # strip options without arguments; we chould do better
                fields = re.sub(r"\s*\[[^]]+\]", "", fields) # strip relative expression

                fields = fields.split()
                if len(fields) > 2:
                    raise TagNotRecognized("Suspicious line %d in %s: \"%s\"" % (lineNo, fileName, line))

            else:
                fields = line.split()

            if len(fields) < 2:
                import pdb; pdb.set_trace() 
                raise TagNotRecognized("Invalid line %d in %s: \"%s\"" % (lineNo, fileName, line))

            productName, versionName = fields[0:2]

            if productName == name:
                version = versionName
                break

        if not version:
            return None                 # not found in this file

        product = self.findProduct(name, version, eupsPathDirs, flavor, noCache)

        if not product:
            msg = "Unable to find product %s %s specified in %s" % (name, version, fileName)
            if self.force:
                print >> sys.stderr, msg + "; ignoring version specification"
                return None

            msg += " (specify --force to continue)"
            raise RuntimeError(msg)

        return product

    def _findNewestProduct(self, name, eupsPathDirs, flavor, minver=None, 
                           noCache=False):
        # find the newest version of a product.  If minver is not None, 
        # the product must have a version matching this or newer.  
        out = None

        for root in eupsPathDirs:
            if noCache or not self.versions.has_key(root) or not self.versions[root]:
                # go directly to the EUPS database
                if not os.path.exists(self.getUpsDB(root)):
                    if self.verbose:
                        print >> sys.stderr, "Skipping missing EUPS stack:", dbpath
                    continue

                products = self._databaseFor(root).findProducts(name, flavors=flavor)
                latest = self._selectPreferredProduct(products, [ Tag("newest") ])
                if latest is None:
                    continue

                # is newest version in this stack newer than minimum version?
                if minver and self.version_cmp(latest.version, minver) < 0:
                    continue

                if out == None or self.version_cmp(latest.version, 
                                                    out.version) > 0:
                    # newest one in this stack is newest one seen
                    out = latest

            else:
                # consult the cache
                try: 
                    vers = self.versions[root].getVersions(name, flavor)
                    vers.sort(self.version_cmp)
                    if len(vers) == 0:
                        continue

                    # is newest version in this stack newer than minimum version?
                    if minver and self.version_cmp(vers[-1], minver) < 0:
                        continue

                    if out == None or self.version_cmp(vers[-1], 
                                                        out.version) > 0:
                        # newest one in this stack is newest one seen
                        out = self.versions[root].getProduct(name, vers[-1], flavor)

                except ProductNotFound:
                    continue

        return out

    def _findPreferredProductByExpr(self, name, expr, eupsPathDirs, flavor, 
                                    noCache):
        return self._selectPreferredProduct(
            self._findProductsByExpr(name, expr, eupsPathDirs, flavor, noCache))

    def _findProductsByExpr(self, name, expr, eupsPathDirs, flavor, noCache):
        # find the products that satisfy the given expression
        out = []
        outver = []
        for root in eupsPathDirs:
            if noCache or not self.versions.has_key(root) or not self.versions[root]:
                # go directly to the EUPS database
                if not os.path.exists(self.getUpsDB(root)):
                    if self.verbose:
                        print >> sys.stderr, "Skipping missing EUPS stack:", dbpath
                    continue

                products = self._databaseFor(root).findProducts(name, flavors=flavor)
                if len(products) == 0: 
                    continue

                products = filter(lambda z: self.version_match(z.version, expr), products)
                for prod in products:
                    if prod.version not in outver:
                        out.append(prod)
                        outver.append(prod.version)

            else:
                # consult the cache
                try: 
                    vers = self.versions[root].getVersions(name, flavor)
                    vers = filter(lambda z: self.version_match(z, expr), vers)
                    if len(vers) == 0:
                        continue
                    for ver in vers:
                        if ver not in outver:
                            prod = self.versions[root].getProduct(name, ver, flavor)
                            out.append(prod)
                            outver.append(prod.version)
                
                except ProductNotFound:
                    continue

        return out

    def _selectPreferredProduct(self, products, preferredTags=None):
        # return the product in a list that is most preferred.
        # None is returned if no products are so tagged.
        # The special "newest" tag will select the product with the latest 
        # version.  
        if not products:
            return None
        if preferredTags is None:
            preferredTags = self.preferredTags

        for tag in preferredTags:
            tag = self.tags.getTag(tag)  # should not fail
            if tag.name == "newest":
                # find the latest version; first order the versions
                vers = map(lambda p: p.version, products)
                vers.sort(self.version_cmp)

                # select the product with the latest version
                if len(vers) > 0:
                    for p in products:
                        if p.version == vers[-1]:
                            return p
            elif tag.name == "setup":
                for p in products:
                    if self.isSetup(p.name, p.version, p.stackRoot()):
                        return p
            else:
                for p in products:
                    if p.isTagged(tag):
                        return p
                
        return None

    def findPreferredProduct(self, name, eupsPathDirs=None, flavor=None, 
                             preferred=None, noCache=False):
        """
        return the most preferred version of a product.  The versions parameter
        gives a list of versions to look for in preferred order; the first one
        found will be returned.  Each version will be search for in all of the 
        directories given in eupsPathDirs.
        @param name           the name of the desired product
        @param eupsPathDirs  the EUPS path directories to search.  (Each 
                                should have a ups_db sub-directory.)  If 
                                None (def.), configured EUPS_PATH 
                                directories will be searched.
        @param flavor        the desired flavor.  If None (default), the 
                                default flavor will be searched for.
        @param preferred     a list of preferred versions.  Each item
                                may be an explicit version, a tag name, or 
                                Tag instance.  The first version found will 
                                be returned.
        @param noCache       if true, the software inventory cache should not 
                                be used to find products; otherwise, it will 
                                be used to the extent it is available.  
        """
        if not flavor:
            flavor = self.flavor
        if eupsPathDirs is None:
            eupsPathDirs = self.path

        if preferred is None:
            preferred = self.preferredTags
        if not preferred and self.quiet <= 0:
            print >> sys.stderr, "Warning: no preferred tags are set"

        found = None
        for vers in preferred:
            if vers == ":" or re.search(r"^\d+$", vers):
                continue
            vers = self.tags.getTag(vers)
            found = self.findProduct(name, vers, eupsPathDirs, flavor, noCache)
            if found:
                break
        return found

    def getUpsDB(self, eupsPathDir, create=False, noRaise=False):
        """Return the ups database directory given a directory from self.path"""
        if not utils.isRealFilename(eupsPathDir):
            return "none"
        upsDB = os.path.join(eupsPathDir, self.ups_db)

        if not os.path.isdir(upsDB):
            if create:
                os.makedirs(upsDB)                

        if not os.path.isdir(upsDB):
            if noRaise:
                return None
            raise OSError("%s does not contain a %s directory" % (eupsPathDir, self.ups_db))

        return upsDB
    

    def includeUserDataDirInPath(self, dataDir=None, useLock=True):
        """Include the ~/.eups versions of directories on self.path in the search path"""
        if not dataDir:
            dataDir = self.userDataDir
            
        if os.path.isdir(self.getUpsDB(dataDir)):
            self.path.append(dataDir)

            self.versions[dataDir] = ProductStack.fromCache(self.getUpsDB(dataDir), [self.flavor],
                                                            updateCache=True, autosave=False,
                                                            useLock=useLock, verbose=self.verbose)

    def getSetupProducts(self, requestedProductName=None):
        """Return a list of all Products that are currently setup (or just the specified product)"""

        re_setup = re.compile(r"^%s(\w+)$" % utils.setupEnvPrefix())

        productList = []

        for key in filter(lambda k: re.search(re_setup, k), os.environ.keys()):
            try:
                productInfo = os.environ[key].split()
            except IndexError:          # Oh dear;  "$setupEnvPrefix()_productName" must be malformed
                continue

            productName = productInfo[0]
            try:
                versionName = productInfo[1]
            except IndexError:
                versionName = None

            if requestedProductName and productName != requestedProductName:
                continue

            try:
                product = self.findSetupProduct(productName)
                if not product:
                    if self.quiet <= 0:
                        print >> sys.stderr, "Unable to find %s %s although it is seen in the environment" % \
                              (productName, versionName)
                    continue

            except EupsException, e:
                if self.quiet <= 0:
                    print >> sys.stderr, e
                continue

            productList += [product]

        return productList

    def findSetupProduct(self, productName, environ=None):
        """
        return a Product instance for a currently setup product.  None is 
        returned if a product with the given name is not currently setup.
        """
        versionName, eupsPathDir, productDir, tablefile, flavor = \
            self.findSetupVersion(productName, environ)
        if versionName is None:
            return None

        if versionName.startswith(Product.LocalVersionPrefix): # they setup -r
            return Product(productName, versionName, flavor, productDir,
                           tablefile, db=self.getUpsDB(eupsPathDir))
        else:                           # a real product, fully identified by a version (and flavor, -Z)
            return self.findProduct(productName, versionName, eupsPathDirs=[eupsPathDir],
                                    flavor=flavor, noCache=False)
        
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

    def getProduct(self, productName, versionName=None, eupsPathDirs=None, noCache=False):
        """
        select the most preferred product with a given name.  This function is 
        equivalent to 
           findProduct(productName, versionName, eupsPathDirs, flavor=None, 
                       noCache=noCache)
        except that it throws a ProductNotFound exception if it is not found.

        @param name          the name of the desired product
        @param version       the desired version.  This can in one of the 
                                following forms:
                                 *  an explicit version 
                                 *  a version expression (e.g. ">=3.3")
                                 *  a string tag name
                                 *  a Tag instance 
                                 *  null, in which case, the (most) preferred 
                                      version will be returned.
        @param eupsPathDirs  the EUPS path directories to search.  (Each should 
                                have a ups_db sub-directory.)  If None (def.),
                                configured EUPS_PATH directories will be 
                                searched.
        @param noCache       if true, the software inventory cache should not be 
                                used to find products; otherwise, it will be used
                                to the extent it is available.  
        """
        out = self.findProduct(productName, versionName, eupsPathDirs, 
                               noCache=noCache)
        if out is None:
            raise ProductNotFound(productName, versionName, self.flavor)
        return out

    def isSetup(self, product, versionName=None, eupsPathDir=None):
        """
        return true if product is setup.

        For backward compatibility, the product parameter can be a Product instance,
        inwhich case, the other parameters are ignored.
        """
        if isinstance(product, Product):
            if product.version is not None:
                versionName = product.version
            if product.db is not None:
                eupsPathDir = product.stackRoot()
            product = product.name

        if not os.environ.has_key(self._envarSetupName(product)):
            return False
        elif versionName is None and eupsPathDir is not None:
            return True

        prod = self.findSetupProduct(product)
        if not prod or \
           (eupsPathDir is not None and eupsPathDir != prod.stackRoot()):
            return False

        return versionName is None or versionName == prod.version

    def unsetupSetupProduct(self, product):
        """ 
        if the given product is setup, unset it up.  
        @param product     a Product instance or a product name
        """
        if isinstance(product, Product):
            product = product.name

        prod = self.findSetupProduct(product)
        if prod is not None:
            try:
                self.setup(prod.name, fwd=False)
            except EupsException, e:
                print >> sys.stderr, \
                    "Unable to unsetup %s %s: %s" % (prod.name, prod.version, e)

    # Permitted relational operators
    _relop_re = re.compile(r"<=?|>=?|==")
    _bad_relop_re = re.compile(r"^\s*=\s+\S+")

    def isLegalRelativeVersion(self, versionName):
        if versionName is None:
            return False
        if self._relop_re.search(versionName):
            return True
        if self._bad_relop_re.match(versionName):
            raise EupsException("Bad expr syntax: %s; did you mean '=='?" % 
                                versionName)
        return False

    def version_match(self, vname, expr):
        """Return vname if it matches the logical expression expr"""

        expr0 = expr
        expr = filter(lambda x: not re.search(r"^\s*$", x), re.split(r"\s*(%s|\|\||\s)\s*" % self._relop_re.pattern, expr0))

        oring = True;                       # We are ||ing primitives
        i = -1
        while i < len(expr) - 1:
            i += 1

            if self._relop_re.search(expr[i]):
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
                try:
                    if self.version_match_prim(op, vname, v):
                        return vname
                except ValueError, e:           # no sort order is defined
                    return None

                oring = False
            else:
                print >> sys.stderr, "Expected logical operator || in \"%s\" at %s" % (expr0, v)

        return None

    def version_match_prim(self, op, v1, v2):
        """
    Compare two version strings, using the specified operator (< <= == >= >), returning
    true if the condition is satisfied

    Uses version_cmp to define sort order """

        try:
            cmp = self.version_cmp(v1, v2, mustReturnInt=False)
        except ValueError, e:           # no sort order is defined
            if self.verbose > 2:
                print >> sys.stderr, e
            raise

        if op == "<":
            return cmp <  0
        elif (op == "<="):
            return cmp <= 0
        elif (op == "=="):
            return cmp == 0
        elif (op == ">"):
            return cmp >  0
        elif (op == ">="):
            return cmp >= 0
        else:
            print >> sys.stderr, "Unknown operator %s used with %s, %s", (op, v1, v2)

    def _isValidSetupType(self, setupType):
        return setupType in self._validSetupTypes

    def setup(self, productName, versionName=None, fwd=True, recursionDepth=0,
              setupToplevel=True, noRecursion=False,
              productRoot=None, tablefile=None, versionExpr=None, optional=False):
        """
        Update the environment to use (or stop using) a specified product.  

        The environment is updated by updating environment variables in 
        os.environ as well as an internal list of shell command aliases.
        (The app.setup() wrapper function is responsible for generating
        the actual commands that should be run by the shell to update
        the shell environment.)

        @param productName      the name of the product desired
        @param versionName      the version of the product desired.  This is 
                                  can either be a actual version name or an
                                  instance of Tag.  See also versionExpr
        @param fwd              if False, the product will be unset; otherwise
                                  it will be setup.
        @param recursionDepth   the number of dependency levels this setup 
                                  command represents.  If the requested product
                                  is being setup because it is required by 
                                  another product, this value should > 0.  
                                  Normally, this parameter is only used 
                                  internally, not by external applications.
        @param setupToplevel    if False, this request is being called to 
                                  setup a dependency product.  This is primarily
                                  for internal use; application use will 
                                  normally leave this to its default value of
                                  True.
        @param noRecursion      if True, dependency products should not be 
                                  setup.  The default is False.
        @param productRoot      the directory where the product is installed
                                  to assume.  This is useful for products 
                                  that are not currently declared.

        @param tablefile        use this table file to setup the product
        @param versionExpr      An expression specifying the desired version
        """

        if isinstance(versionName, str) and versionName.startswith(Product.LocalVersionPrefix):
            productRoot = versionName[len(Product.LocalVersionPrefix):]

        if productRoot is None:
            productRoot = self.root

        #
        # Look for product directory
        #
        setupFlavor = self.flavor         # we may end up using e.g. "generic"

        product = None
        if isinstance(productName, Product): # it's already a full Product
            raise RuntimeError("Product type passed to setup")
            # product = productName
            # productName = product.name

        elif not fwd:
            # on unsetup, get the product to unsetup
            product = self.findSetupProduct(productName)
            if not product:
                msg = "I can't unsetup %s as it isn't setup" % productName
                if self.verbose > 1 and self.quiet <= 0:
                    print >> sys.stderr, msg

                if not self.force:
                    return False, versionName, msg
                #
                # Fake enough to be able to unset the environment variables
                #
                product = Product(productName, None)
                product.tablefile = "none"

            if isinstance(versionName, Tag):
                # resolve a tag to a version
                tag = self.tags.getTag(versionName) # may raise TagNotRecognized
                p = self._findTaggedProduct(productName, tag)
                if p and p.version:
                    versionName = p.version

            if not product.version:  
                product.version = versionName
            elif versionName and not self.version_match(product.version, versionName):
                if self.quiet <= 0:
                    print >> sys.stderr, \
                        "You asked to unsetup %s %s but version %s is currently setup; unsetting up %s" % \
                        (product.name, versionName, product.version, product.version)

        else:  # on setup (fwd = True)
            # get the product to setup
            if productRoot:
                if not os.path.isdir(productRoot):
                    raise EupsException("Product %s's productDir %s is not a directory" % \
                                        (productName, productRoot))

                vro = self.getPreferredTags()
                if len(vro) > 0 and vro.count("commandLine") == 0:
                    if self.verbose:
                        print >> sys.stderr, "Using %s, although \"commandLine\" is not specified in VRO %s" % \
                              (productRoot, vro)

                vroReason = ["commandLine", productRoot]
                if self.verbose > 2:
                    print >> sys.stderr, ("VRO used %-12s " % vroReason[0]),
                product = Product.createLocal(productName, productRoot, self.flavor, tablefile=tablefile)
            else:
                product = None
                for fallbackFlavor in utils.Flavor().getFallbackFlavors(self.flavor, includeMe=True):
                    vro = self.getPreferredTags()
                    while not product and vro:
                        product, vroReason = self.findProductFromVRO(productName, versionName, versionExpr,
                                                                     flavor=fallbackFlavor, optional=optional,
                                                                     recursionDepth=recursionDepth, vro=vro)

                        if not product and self.alreadySetupProducts.has_key(productName):
                            # We couldn't find it, but maybe it's already setup 
                            # locally?   That'd be OK
                            product = self.alreadySetupProducts[productName][0]
                            if not self.keep and product.version != versionName:
                                product = None
                                break   # no-where else to search

                        if product and versionName and recursionDepth == 0: # Check we got the desired version
                            if product.version != versionName:
                                #
                                # Maybe we'll find the product again further down the VRO
                                #
                                vro = vro[vro.index(vroReason[0]) + 1:]

                                if self.verbose > 1:
                                    msg = ("Requested %s version %s; " + 
                                           "version %s found on VRO as \"%s\" is not acceptable") % \
                                          (productName, versionName, product.version, vroReason[0])
                                    if vro:
                                        msg += "; proceeding"
                                    print >> sys.stderr, msg
                                product = None
                                continue

                        if product:         # got it
                            if setupFlavor != fallbackFlavor:
                                setupFlavor = fallbackFlavor
                                if self.verbose > 2:
                                    print >> sys.stderr, "Using flavor %s for %s %s" % \
                                          (setupFlavor, productName, versionName)
                        else:
                            break       # no product, and we've searched the vro already.  Try next flavour
                        
                    if product:
                        break

                if not product:
                    return False, versionName, ProductNotFound(productName, versionName)
        #
        # We have all that we need to know about the product to proceed
        #
        # If we're the toplevel, get a list of all products that are already setup
        #
        if recursionDepth == 0:
            if fwd:
                q = utils.Quiet(self)
                self.alreadySetupProducts = {}
                for p in self.getSetupProducts():
                    self.alreadySetupProducts[p.name] = (p, None)
                del q

                self.alreadySetupProducts[product.name] = (product, vroReason)

        try:
            table = product.getTable(quiet=not fwd)
        except TableFileNotFound, e:
            if fwd:
                raise

            if not self.force:
                raise

            table = None
            print >> sys.stderr, "Warning: %s" % e
        
        if table:
            try:
                verbose = self.verbose
                if not fwd:
                    verbose -= 1
                actions = table.actions(setupFlavor, setupType=self.setupType, verbose=verbose)
            except TableError, e:
                print >> sys.stderr, "product %s %s: %s" % (product.name, product.version, e)
                return False, product.version, e
        else:
            actions = []

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
                      (indent + product.name, setupFlavor, product.version)
                setup_msgs[key] = 1

        if fwd and setupToplevel:
            #
            # Are we already setup?
            #
            sprod = self.findSetupProduct(product.name)
            if sprod is None:
                sversionName = None

            if sprod and sprod.version and product.version:
                if product.version == sprod.version or product.dir == sprod.dir: # already setup
                    if recursionDepth == 0: # top level should be resetup if that's what they asked for
                        pass
                    elif self.force:    # force means do it!; so do it.
                        pass
                    else:
                        # already setup and no need to go further
                        if self.verbose > 1:
                            print >> sys.stderr, "            %s %s is already setup; skipping" % \
                                  (len(indent)*" " + product.name, product.version)
                            
                        return True, product.version, None
                else:

                    # the currently setup version is different from what was requested
                    if recursionDepth > 0 and not (False and self.keep): 

                        # Warn the user that we're switching versions (top level shouldn't whine)
                        msg = "%s %s is currently setup; overriding with %s" % \
                              (product.name, sprod.version, product.version)

                        if self.quiet <= 0 and self.verbose > 0 and not (self.keep and setup_msgs.has_key(msg)):
                            print >> sys.stderr, "            %s%s" % (recursionDepth*" ", msg)
                        setup_msgs[msg] = 1

            q = utils.Quiet(self)
            self.unsetupSetupProduct(product)
            del q

            setup_product_str = "%s %s -f %s -Z %s" % (
                product.name, product.version, setupFlavor, product.stackRoot())
            if tablefile:
                setup_product_str += " -m %s" % (tablefile)

            self.setEnv(self._envarDirName(product.name), product.dir)
            self.setEnv(self._envarSetupName(product.name), setup_product_str)
            #
            # Remember that we've set this up in case we want to keep it later
            #
            self.alreadySetupProducts[product.name] = (product, vroReason)
        elif fwd:
            assert not setupToplevel
        else:
            if product.dir in self.localVersions.keys():
                del self.localVersions[product.dir]

            self.unsetEnv(self._envarDirName(product.name))
            self.unsetEnv(self._envarSetupName(product.name))

        #
        # Process table file
        #
        for a in actions:
            a.execute(self, recursionDepth + 1, fwd, noRecursion=noRecursion)

        if recursionDepth == 0:            # we can cleanup
            if fwd:
                del self._msgs["setup"]
        #
        # we made a copy of os.environ so the usual magic putenv doesn't happen
        #
        for key, val in os.environ.items():
            os.putenv(key, val)         

        return True, product.version, None

    def unsetup(self, productName, versionName=None):
        """Unsetup a product"""

        return self.setup(productName, versionName, fwd=False)

    def assignTag(self, tag, productName, versionName, eupsPathDir=None, eupsPathDirForRead=None):
        """
        assign the given tag to a product.  The product that it will be
        assigned to will be the first product found in the EUPS_PATH
        with the given name and version.  If the product is not found
        a ProductNotFound exception is raised.  If the tag is not 
        supported, a TagNotRecognized exception will be raised
        @param tag           the tag to assign as tag name or Tag instance 
        @param productName   the name of the product to tag
        @param versionName   the version of the product
        """
        # convert tag name to a Tag instance; may raise TagNotRecognized
        tag = self.tags.getTag(tag)

        if not eupsPathDirForRead:
            eupsPathDirForRead = eupsPathDir

        product = self.getProduct(productName, versionName, eupsPathDirForRead)
        root = product.stackRoot()

        if tag.isGlobal() and not utils.isDbWritable(product.db):
            raise EupsException(
                "You don't have permission to assign a global tag %s in %s" % (tag, product.db))

        # update the database.  If it's a user tag, 
        db = Database(product.db, self._userStackCache(root))
        db.assignTag(tag, productName, versionName, self.flavor)

        # update the cache
        if self.versions.has_key(root) and self.versions[root]:
            self.versions[root].ensureInSync(verbose=self.verbose)
            self.versions[root].assignTag(tag, productName, versionName, self.flavor)
            try:
                self.versions[root].save(self.flavor)
            except CacheOutOfSync, e:
                if self.quiet <= 0:
                    print >> sys.stderr, "Warning: " + str(e)
                    print >> sys.stderr, "Correcting..."
                self.versions[root].refreshFromDatabase()

    def unassignTag(self, tag, productName, versionName=None, eupsPathDir=None, eupsPathDirForRead=None):
        """
        unassign the given tag on a product.    
        @param tag           the tag to assign as tag name or Tag instance 
        @param productName   the name of the product to tag
        @param versionName   the version of the product.  If None, choose the
                                 version that currently has the tag.
        @param eupsPathDir   the EUPS stack to find the product in.  If None,
                                 the first product in the stack with that tag
                                 will be chosen.
        """
        # convert tag name to a Tag instance; may raise TagNotRecognized
        tag = self.tags.getTag(tag)

        if not eupsPathDirForRead:
            eupsPathDirForRead = eupsPathDir

        if not eupsPathDir and self.isUserTag(tag):
            assert self.userDataDir in self.path

        msg = None
        if versionName:
            # user asked for a specific version
            prod = self.findProduct(productName, versionName, eupsPathDir, self.flavor)
            if prod is None:
                raise ProductNotFound(productName, versionName, self.flavor, eupsPathDir)
            dbpath = prod.db
            eupsPathDir = prod.stackRoot()

            if str(tag) not in prod.tags:
                msg = "Product %s is not tagged \"%s\"" % (productName, tag.name)
                if eupsPathDir:
                    msg += " in [%s]" % " ".join(self.path)

        elif not eupsPathDir or isinstance(eupsPathDir, list):
            prod = self.findProduct(productName, tag, eupsPathDir, self.flavor)
            if prod is None:
                # This tag is not assigned to this product.  Is it 
                # because the product doesn't exist?
                prod = self.findProduct(productName, versionName)
                if prod is None:
                    raise ProductNotFound(productName, versionName, self.flavor)
                msg = "Tag %s not assigned to product %s" % \
                    (tag.name, productName)
                if eupsPathDir:
                    msg += " within %s" % str(eupsPathDir)

            dbpath = prod.db
            eupsPathDir = prod.stackRoot()
        else:
            dbpath = self.getUpsDB(eupsPathDir)

        if msg is not None:
            if self.quiet <= 0:
                print >> sys.stderr, msg
            return

        if tag.isGlobal() and not utils.isDbWritable(dbpath):
            raise EupsException(
                "You don't have permission to unassign a global tag %s in %s" %
                (str(tag), product.db))

        # update the database
        if not self._databaseFor(eupsPathDir,dbpath).unassignTag(str(tag), productName, self.flavor):
            if self.verbose:
                print >> sys.stderr, "Tag %s not assigned to %s %s" % \
                    (productName, versionName)

        # update the cache
        if self.versions.has_key(eupsPathDir) and self.versions[eupsPathDir]:
            self.versions[eupsPathDir].ensureInSync(verbose=self.verbose)
            if self.versions[eupsPathDir].unassignTag(str(tag), productName, self.flavor):
                try:
                    self.versions[eupsPathDir].save(self.flavor)
                except CacheOutOfSync, e:
                    if self.quiet <= 0:
                        print >> sys.stderr, "Warning: " + str(e)
                        print >> sys.stderr, "Correcting..."
                    self.versions[eupsPathDir].refreshFromDatabase()

            elif self.verbose:
                print >> sys.stderr, "Tag %s not assigned to %s %s" % \
                    (productName, versionName)
                

    def declare(self, productName, versionName, productDir=None, eupsPathDir=None, tablefile=None, 
                tag=None, declareCurrent=None):
        """ 
        Declare a product.  That is, make this product known to EUPS.  

        If the product is already declared, this method can be used to
        change the declaration.  The most common type of
        "redeclaration" is to only assign a tag.  (Note that this can 
        be accomplished more efficiently with assignTag() as well.)
        Attempts to change other data for a product requires self.force
        to be true. 

        If the product has not installation directory or table file,
        these parameters should be set to "none".  If either are None,
        some attempt is made to surmise what these should be.  If the 
        guessed locations are not found to exist, this method will
        raise an exception.  

        If the tablefile is an open file descriptor, it is assumed that 
        a copy should be made and placed into product's ups directory.
        This directory will be created if it doesn't exist.

        For backward compatibility, the declareCurrent parameter is
        provided but its use is deprecated.  It is ignored unless the
        tag argument is None.  A value of True is equivalent to 
        setting tag="current".  If declareCurrent is None and tag is
        boolean, this method assumes the boolean value is intended for 
        declareCurrent.  

        @param productName   the name of the product to declare
        @param versionName   the version to declare.
        @param productDir    the directory where the product is installed.
                               If set to "none", there is no installation
                               directory (and tablefile must be specified).
                               If None, an attempt to determine the 
                               installation directory (from eupsPathDir) is 
                               made.
        @param eupsPathDir   the EUPS product stack to install the product 
                               into.  If None, then the first writable stack
                               in EUPS_PATH will be installed into.
        @param tablefile     the path to the table file for this product.  If
                               "none", the product has no table file.  If None,
                               it is looked for under productDir/ups.  If set
                               to a file stream, its contents will get written
                               into the product database.
        @param tag           the tag to assign to this product.  If the 
                               specified product is already registered with
                               the same product directory and table file,
                               then use of this input will simple assign this
                               tag to the variable.  (See also above note about 
                               backward compatibility.)
        @param declareCurrent  DEPRECATED, if True and tag=None, it is 
                               equivalent to tag="current".  
        """
        if re.search(r"[^a-zA-Z_0-9]", productName):
            raise EupsException("Product names may only include the characters [a-zA-Z_0-9]: saw %s" % productName)

        # this is for backward compatibility
        if isinstance(tag, bool) or (tag is None and declareCurrent):
            tag = "current"
            utils.deprecated("Eups.declare(): declareCurrent param is deprecated; use tag param.", self.quiet)

        if productDir and productDir != "none":
            productDir = os.path.abspath(productDir)
            if not productName:
                productName = utils.guessProduct(os.path.join(productDir,"ups"))

        if tag and (not productDir or productDir == "/dev/null" or not tablefile):
            for flavor in utils.Flavor().getFallbackFlavors(self.flavor, True):
                info = self.findProduct(productName, versionName, eupsPathDir, flavor)
                if info is not None:
                    if not productDir:
                        productDir = info.dir
                    if not tablefile:
                        if productDir == info.dir:     # we didn't change the definition
                            tablefile = info.tablefile # we'll check the other fields later
                    if not productDir:
                        productDir = "none"
                    break

        if not productDir or productDir == "/dev/null":
            #
            # Look for productDir on self.path
            #
            for eupsProductDir in self.path:
                for flavor in utils.Flavor().getFallbackFlavors(self.flavor, True): 
                    _productDir = os.path.join(eupsProductDir, flavor, productName, versionName) 
                    if os.path.isdir(_productDir): 
                        productDir = _productDir 
                        break 
                if productDir:
                    break

        if not productDir:
            raise EupsException("Please specify a productDir for %s %s (maybe \"none\")" % (productName, versionName))

        if productDir == "/dev/null":   # Oh dear, we failed to find it
            productDir = "none"
            print >> sys.stderr, "Failed to find productDir for %s %s; assuming \"%s\"" % \
                  (productName, versionName, productDir)

        if utils.isRealFilename(productDir):
            productDir = os.path.expanduser(productDir)
            if not os.path.isabs(productDir):
                productDir = os.path.join(os.getcwd(), productDir)
            productDir = os.path.normpath(productDir)
            assert productDir

            if not os.path.isdir(productDir):
                raise EupsException("Product %s %s's productDir %s is not a directory" % \
                                    (productName, versionName, productDir))

        if tablefile is None:
            tablefile = "%s.table" % productName

        eupsPathDirForRead = eupsPathDir # eups_path directory where we can find (but not modify) the product
        if eupsPathDir:
            if not utils.isDbWritable(eupsPathDir):
                eupsPathDir = None
        else:                           # look for proper home on self.path
            for d in self.path:
                if os.path.commonprefix([productDir, d]) == d:
                    eupsPathDir = d
                    eupsPathDirForRead = d
                    break

            if not eupsPathDirForRead:
                eupsPathDirForRead = eupsPathDir
                
            if not eupsPathDir or not utils.isDbWritable(self.getUpsDB(eupsPathDir)):
                eupsPathDir = utils.findWritableDb(self.path)

            if not eupsPathDirForRead:
                eupsPathDirForRead = eupsPathDir

        if self.isUserTag(tag):
            ups_db = self.getUpsDB(self.userDataDir)
            if not os.path.isdir(ups_db):
                os.makedirs(ups_db)
            eupsPathDir = self.userDataDir

        if not eupsPathDir: 
            raise EupsException(
                "Unable to find writable stack in EUPS_PATH to declare %s %s" % 
                (productName, versionName))

        if not eupsPathDirForRead:
            raise RuntimeError("eupsPathDirForRead is None; complain to RHL")

        ups_dir, tablefileIsFd = "ups", False
        if not utils.isRealFilename(tablefile):
            ups_dir = None
        elif tablefile:
            # is this a filestream?
            # 
            # Instead of checking on the type, e.g:
            #   if isinstance(tablefile, file):
            # look for file-like methods; this accepts StringIO objects
            #
            if hasattr(tablefile,"readlines") and hasattr(tablefile,"next"):
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
        if not tablefileIsFd and utils.isRealFilename(tablefile):
            if utils.isRealFilename(productDir):
                if ups_dir:
                    try:
                        full_tablefile = os.path.join(ups_dir, tablefile)
                    except Exception, e:
                        raise EupsException("Unable to generate full tablefilename: %s" % e)
                    
                    if not os.path.isabs(full_tablefile):
                        #
                        # We can't simply check os.path.isfile(full_tablefile) as a file of the name might
                        # exist locally (it often will if we're declaring from the toplevel product directory),
                        # but that's not the file we want
                        #
                        possible_full_tablefile = os.path.join(productDir, full_tablefile)
                        if os.path.isfile(possible_full_tablefile):
                            full_tablefile = possible_full_tablefile

                else:
                    full_tablefile = tablefile
            else:
                if utils.isRealFilename(tablefile):
                    if utils.isRealFilename(productDir):
                        full_tablefile = os.path.join(productDir, ups_dir, tablefile)
                    else:
                        full_tablefile = tablefile

            if not os.path.isfile(full_tablefile):
                raise EupsException("I'm unable to declare %s as tablefile %s does not exist" %
                                     (productName, full_tablefile))
        else:
            full_tablefile = None
        #
        # Are there any declaration options in the table file?
        #
        declareOptions = Table(full_tablefile).getDeclareOptions()
        try:
            self.flavor = declareOptions["flavor"]
        except KeyError:
            pass
        #
        # If no tags are being assigned and this'll be the first version of this product declared,
        # we'll declare this product current
        #
        if not tag and not self.findProducts(productName):
            tag = "current"
        #
        # See if we're redeclaring a product and complain if the new declaration conflicts with the old
        #
        dodeclare = True
        prod = self.findProduct(productName, versionName, eupsPathDirForRead)
        if prod is not None and not self.force:
            _version, _eupsPathDir, _productDir, _tablefile = \
                      prod.version, prod.stackRoot(), prod.dir, prod.tablefile

            assert _version == versionName
            assert _eupsPathDir == eupsPathDirForRead

            differences = []
            if _productDir and productDir != _productDir:
                differences += ["%s != %s" % (productDir, _productDir)]

            if full_tablefile:
                if _tablefile and tablefile != _tablefile:
                    # Different names; see if they're different content too
                    diff = ["%s != %s" % (tablefile, _tablefile)] # possible difference
                    try:
                        if not filecmp.cmp(full_tablefile, _tablefile):
                            differences += diff
                    except OSError:
                        differences += diff
            elif tablefileIsFd:
                differences += ["table file from stdin"]

            if differences:
                # we're redeclaring the product in a non-trivial way
                info = ""
                if self.verbose:
                    info = " (%s)" % " ".join(differences)
                raise EupsException("Redeclaring %s %s%s; specify force to proceed" %
                                     (productName, versionName, info))

            elif _productDir and _tablefile:
                # there's no difference with what's already declared
                dodeclare = False

        # Last bit of tablefile path tweaking...
        if not tablefile.startswith('$') and not os.path.isabs(tablefile) and full_tablefile:
            tablefile = full_tablefile

        #
        # Arguments are checked; we're ready to go
        #
        verbose = self.verbose
        if self.noaction:
            verbose = 2
        if dodeclare:
            # Talk about doing a full declare.  
            if verbose:
                info = "Declaring"
                if verbose > 1:
                    if productDir == "/dev/null":
                        info += " \"none\" as"
                    else:
                        info += " %s as" % productDir
                info += " %s %s" % (productName, versionName)
                if tag:
                    info += " %s" % tag
                info += " in %s" % (eupsPathDir)

                print >> sys.stderr, info
            if self.noaction:  
                return
            #
            # now really declare the product.  This will also update the tags
            #
            dbpath = self.getUpsDB(eupsPathDir)
            if tag:
                tag = [self.tags.getTag(tag)]
            product = Product(productName, versionName, self.flavor, productDir, 
                              tablefile, tag, dbpath, ups_dir=ups_dir)

            # update the database
            self._databaseFor(eupsPathDir, dbpath).declare(product)

            # update the cache (if in use)
            if self.versions.has_key(eupsPathDir) and self.versions[eupsPathDir]:

                self.versions[eupsPathDir].ensureInSync(verbose=self.verbose)
                self.versions[eupsPathDir].addProduct(product)

                try:
                    self.versions[eupsPathDir].save(self.flavor)
                except CacheOutOfSync, e:
                    if self.quiet <= 0:
                        print >> sys.stderr, "Note: " + str(e)
                        print >> sys.stderr, "Correcting..."
                    self.versions[eupsPathDir].refreshFromDatabase()
                
        if tag:
            # we just want to update the tag
            if verbose:
                info = "Assigning tag \"%s\" to %s %s" % (tag[0].name, productName, versionName)
                print >> sys.stderr, info
            if not self.noaction:
                if isinstance(tag, str):
                    tag = [self.tags.getTag(tag)]

                eupsDirs = [eupsPathDirForRead, eupsPathDir]
                #
                # Delete all old occurrences of this tag
                #
                for p in self.findProducts(productName, None, tag):
                    self.unassignTag(tag[0], productName, None, p.stackRoot(), eupsPathDir)
                #
                # And set it in the Proper Place
                #                        
                for eupsDir in eupsDirs:
                    try:
                        self.assignTag(tag[0], productName, versionName, eupsPathDir, eupsDir)
                        break
                    except ProductNotFound:
                        if eupsDir == eupsDirs[-1]: # no more to try
                            raise

    def undeclare(self, productName, versionName=None, eupsPathDir=None, tag=None, 
                  undeclareCurrent=None):
        """
        Undeclare a product.  That is, remove knowledge of this
        product from EUPS.  This method can also be used to just
        remove a tag from a product without fully undeclaring it.

        A tag parameter that is not None indicates that only a 
        tag should be de-assigned.  (Note that this can 
        be accomplished more efficiently with unassignTag() as 
        well.)  In this case, if versionName is None, it will 
        apply to any version of the product.  If eupsPathDir is None,
        this method will attempt to undeclare the first matching 
        product in the default EUPS path.  

        For backward compatibility, the undeclareCurrent parameter is
        provided but its use is deprecated.  It is ignored unless the
        tag argument is None.  A value of True is equivalent to 
        setting tag="current".  If undeclareCurrent is None and tag is
        boolean, this method assumes the boolean value is intended for 
        undeclareCurrent.  

        @param productName   the name of the product to undeclare
        @param versionName   the version to undeclare; this can be None if 
                               there is only one version declared; otherwise
                               an EupsException is raised.  
        @param eupsPathDir   the product stack to undeclare the product from.
                               ProductNotFound is raised if the product 
                               is not installed into this stack.  
        @param tag           if not None, only unassign this tag; product
                                will not be undeclared.  
        @param undeclareCurrent  DEPRECATED; if True, and tag is None, this
                                is equivalent to tag="current".  
        """
        # this is for backward compatibility
        if isinstance(tag, bool) or (tag is None and undeclareCurrent):
            tag = "current"
            utils.deprecated("Eups.undeclare(): undeclareCurrent param is deprecated; use tag param.", self.quiet)

        if tag:
            stat = self.unassignTag(tag, productName, versionName, eupsPathDir)
            if self.isUserTag(tag):
                # We may have declared this version (in ~/.eups/ups_db) as well as tagging it, but
                # we aren't going to delete it now.  It does no harm, as the DB is generally only
                # consulted when processing user tags.
                pass
            return stat

        product = None
        if not versionName:
            productList = self.findProducts(productName, eupsPathDirs=eupsPathDir) 
            if len(productList) == 0:
                raise ProductNotFound(productName, stack=eupsPathDir)

            elif len(productList) > 1:
                versionList = map(lambda el: el.version, productList)
                raise EupsException("Product %s has versions \"%s\"; please choose one and try again" %
                                     (productName, "\" \"".join(versionList)))

            else:
                versionName = productList[0].version
            
        # this raises ProductNotFound if not found
        product = self.getProduct(productName, versionName, eupsPathDir)
        eupsPathDir = product.stackRoot()

        if not utils.isDbWritable(product.db):
            raise EupsException("You do not have permission to undeclare products from %s" % eupsPathDir)
            
        if self.isSetup(product):
            if self.force:
                print >> sys.stderr, "Product %s %s is currently setup; proceeding" % (productName, versionName)
            else:
                raise EupsException("Product %s %s is already setup; specify force to proceed" % (productName, versionName))

        if self.verbose or self.noaction:
            print >> sys.stderr, "Removing %s %s from version list for %s" % \
                (product.name, product.version, product.stackRoot())
        if self.noaction:
            return True

        if not self._databaseFor(eupsPathDir).undeclare(product):
            # this should not happen
            raise ProductNotFound(product.name, product.version, product.flavor, product.db)
            
        if self.versions.has_key(eupsPathDir) and self.versions[eupsPathDir]:

            self.versions[eupsPathDir].ensureInSync(verbose=self.verbose)
            self.versions[eupsPathDir].removeProduct(product.name, 
                                                     product.flavor,
                                                     product.version)

            try:
                self.versions[eupsPathDir].save(product.flavor)
            except CacheOutOfSync, e:
                if self.quiet <= 0:
                    print >> sys.stderr, "Warning: " + str(e)
                    print >> sys.stderr, "Correcting..."
                self.versions[eupsPathDir].refreshFromDatabase()

        return True

    def findProducts(self, name=None, version=None, tags=None,
                     eupsPathDirs=None, flavors=None):
        """
        Return a list of Product objects for products we know about
        with given restrictions.  This will include currently setup 
        products which may not be currently declared.  

        The returned list will be restricted by the name, version,
        and/or tag assignment using the productName, productVersion,
        and tags parameters, respectively.  productName and 
        productVersion can have shell wildcards (like *); in this 
        case, they will be matched in a shell globbing-like way 
        (using fnmatch).  
        @param name          the name or name pattern for the products of
                               interest
        @param version       the version or version pattern for the products
                               of interest
        @param tags          a list of tag names; if provided, the list of 
                               returned products will be restricted to those
                               assigned at least one of these tags.  This can
                               be one of the following:
                                 o  a single tag name string
                                 o  a list of tag name strings
                                 o  a single Tag instance
                                 o  a single Tags instance
        @param eupsPathDirs  search these products stacks for the products;
                               if None, search EUPS_PATH.
        @param flavors       restrict products to these flavors; if None, 
                               the current flavor and all fallback flavors
                               will be searched.  
        """
        if flavors is None:
            flavors = utils.Flavor().getFallbackFlavors(self.flavor, True)

        if tags is not None:
            if isinstance(tags, Tags):
                tags = Tags.getTagNames()
            elif isinstance(tags, Tag):
                tags = [str(tags)]
            if not isinstance(tags, list):
                tags = [tags]

            # check for unsupported tags and convert them to their 
            # qualified names (i.e. user tags start with "user:")
            bad = []
            for i in xrange(len(tags)):
                try:
                    tags[i] = str(self.tags.getTag(tags[i]))
                except TagNotRecognized:
                    bad.append(tags[i])
            if len(bad) > 0:
                if False:
                    raise TagNotRecognized(str(bad))
                else:
                    pass

        prodkey = lambda p: "%s:%s:%s:%s" % (p.name,p.flavor,p.db,p.version)
        tagset = _TagSet(self, tags)
        out = []
        newest = None

        # first get all the currently setup products.  We will integrate these
        # into the list
        setup = {}
        if not tags or "setup" in tags:
            prods = self.getSetupProducts()
            for prod in prods:
                if name and not fnmatch.fnmatch(prod.name, name):
                    continue
                if version and (not prod.version or \
                                not fnmatch.fnmatch(prod.version, version)):
                    continue

                if not prod.flavor or prod.flavor not in flavors:
                    continue

                # If we haven't limited the stack paths, accept a product
                # in any stack.
                if eupsPathDirs and (not prod.db or \
                                     prod.stackRoot() not in eupsPathDirs):
                    continue
                setup[prodkey(prod)] = prod

        # now look for products in the cache.  By default, we'll search
        # the stacks in the EUPS_PATH.  
        if eupsPathDirs is None:
            eupsPathDirs = self.path
        if not isinstance(eupsPathDirs, list):
            eupsPathDirs = [eupsPathDirs]

        # start by iterating through each stack path
        for d in eupsPathDirs:
            if not self.versions.has_key(d):
                continue
            stack = self.versions[d]
            stack.ensureInSync(verbose=self.verbose)

            # iterate through the flavors of interest
            haveflavors = stack.getFlavors()
            for flavor in flavors:
                if flavor not in haveflavors:
                    continue

                # match the product name
                prodnames = stack.getProductNames(flavor)
                if name:
                    prodnames = fnmatch.filter(prodnames, name)
                prodnames.sort()

                for pname in prodnames:
                    if tags:
                        for t in tags:
                            prod = self.findTaggedProduct(pname, t)
                            if prod:
                                out.append(prod)

                    # peel off newest version if specifically desired 
                    if tags and "newest" in tags:
                        newest = self.findTaggedProduct(pname, "newest", d, flavor)

                    # select out matched versions
                    vers = stack.getVersions(pname, flavor)
                    if version:
                        vers = fnmatch.filter(vers, version)
                    vers.sort(self.version_cmp)

                    # only include newest if it passes the version constraint
                    if newest is not None and newest.version not in vers:
                        newest = None

                    for ver in vers:
                        prod = stack.getProduct(pname, ver, flavor)

                        # match against the desired tags
                        if tags:
                            if newest and newest.version == ver:
                                # we'll add this on the end so as not to 
                                # double-list it
                                continue

                            if tagset.intersects(prod.tags):
                                out.append(prod)

                            elif "setup" in tags and self.isSetup(prod.name, prod.version, d):
                                out.append(prod)
                                
                        else:
                            out.append(prod)

                        # remove this product from the setup list if it is 
                        # setup:
                        key = prodkey(prod)
                        if setup.has_key(key):  del setup[key]

                    # add newest if we have/want it
                    if newest:
                        out.append(newest)
                        key = prodkey(newest)
                        if setup.has_key(key):  del setup[key]
                        newest = None

                    # append any matched setup products having current
                    # name, flavor and stack directory
                    for key in filter(lambda k: k.startswith("%s:%s:%s" % (pname, flavor, d)), setup.keys()):
                        out.append(setup[key])
                        del setup[key]

        if not version or \
           (isinstance(version,str) and version.startswith(Product.LocalVersionPrefix)) or \
           (tags and "setup" in tags):

            # Add in LOCAL: setups
            #
            sunames = setup.keys()
            sunames.sort()
            for pname in sunames:
                prod = setup[pname]
                if name and not fnmatch.fnmatch(prod.name, name):
                    continue
                if version and not fnmatch.fnmatch(prod.version, version):
                    continue
                out.append(prod)

        return out
                

    def dependencies_from_table(self, tablefile, eupsPathDirs=None):
        """Return self's dependencies as a list of (Product, optional, recursionDepth) tuples

        N.b. the dependencies are not calculated recursively"""
        dependencies = []
        if utils.isRealFilename(tablefile):
            for vals in Table(tablefile).dependencies(self, eupsPathDirs):
                dependencies += [vals]

        return dependencies

    def remove(self, productName, versionName, recursive=False, checkRecursive=False, interactive=False, userInfo=None):
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

        productsToRemove = _set(productsToRemove) # remove duplicates
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
                raise ProductNotFound("Product %s with version %s doesn't seem to exist" % 
                                      (product.name, product.version))
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

            if not self.undeclare(product.name, product.version):
                raise EupsException("Not removing %s %s" % (product.name, product.version))

            if removedDirs.has_key(dir): # file is already removed
                continue

            if utils.isRealFilename(dir):
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

        product = self.getProduct(productName, versionName)  # can raise ProductNotFound
        deps = [(product, False)]
        if recursive:
            tbl = product.getTable()
            if tbl:
                deps += tbl.dependencies(self)

        productsToRemove = []
        for product, o in deps:
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
                        raise EupsException("%s; specify force to remove" % (msg))

            if recursive:
                productsToRemove += self._remove(product.name, product.version, (product.name != productName),
                                                 checkRecursive, topProduct=topProduct, topVersion=topVersion,
                                                 userInfo=userInfo)

            productsToRemove += [product]
                
        return productsToRemove

    def uses(self, productName=None, versionName=None, depth=9999):
        """Return a list of all products which depend on the specified product in the form of a list of tuples
        (productName, productVersion, (versionNeeded, optional, tags)) 
        (where tags is a list of tag names).  

        depth tells you how indirect the setup is (depth==1 => product is setup in table file,
        2 => we set up another product with product in its table file, etc.)

        versionName may be None in which case all versions are returned.  If product is also None,
        a Uses object is returned which may be used to perform further uses searches efficiently
    """
        if not productName and versionName:
            raise EupsException("You may not specify a version \"%s\" but not a product" % versionName)

        old_exact_version = self.exact_version
        self.exact_version = True       # we want to know exactly which versions were specified

        # start with every known product
        productList = self.findProducts()

        if not productList:
            return []

        useInfo = Uses()

        for pi in productList:          # for every known product
            try:
                q = utils.Quiet(self)
                tbl = pi.getTable()

                if not tbl:
                    del q
                    continue

                deps = tbl.dependencies(self, followExact=True) # lookup top-level dependencies
                del q
            except Exception, e:
                if not self.quiet:
                    print >> sys.stderr, ("Warning: %s" % (e))
                continue

            for dep_product, dep_versionExpr, dep_optional in deps:
                if pi.name == dep_product.name and pi.version == dep_product.version:
                    continue

                useInfo._remember(pi.name, pi.version, (dep_product.name, dep_product.version, dep_optional))

        useInfo._invert(depth)

        self.exact_version = old_exact_version

        #
        # OK, we have the information stored away
        #
        if not productName:
            return useInfo

        return useInfo.users(productName, versionName)

    def supportServerTags(self, tags, eupsPathDir=None):
        """
        support the list of tags provided by a server
        @param tags     the list of tags either as a python list or a space-
                          delimited string.   
        @param persist  If non-NULL the tag names will be saved to disk. 
        """
        if isinstance(tags, str):
            tags = tags.split()

        stacktags = None
        if eupsPathDir and utils.isDbWritable(eupsPathDir):
            stacktags = self._loadServerTags().get(eupsPathDir)

        needPersist = False
        for tag in tags:
            if isinstance(tag, Tag):
                tag = tag.name
            if not self.tags.isRecognized(tag):
                self.tags.registerTag(tag)
            if stacktags and not stacktags.isRecognized(tag):
                stacktags.registerTag(tag)
                needPersist = True

        if stacktags and needPersist:
            stacktags.saveGlobalTags(eupsPathDir)
    

    # =-=-=-=-=-=-=-=-=-= DEPRECATED METHODS =-=-=-=-=-=-=-=-=-=-=

    def setCurrentType(self, currentType):
        """Set type of "Current" we want (e.g. current, stable, ...)"""
        utils.deprecated("Deprecated function: Eups.setCurrentType(); use setPreferredTags()", self.quiet)
        return setPreferredTag(currentType)

    def getCurrent(self):
        utils.deprecated("Deprecated function: Eups.getCurrent(); use getPreferredTags()", self.quiet)
        return self.preferredTags[0]

    def findVersion(self, productName, versionName=None, eupsPathDirs=None, allowNewer=False, flavor=None):
        """
        Find a version of a product.  This function is DEPRECATED; use
        findProduct() instead.  

        If no version is specified, the most preferred tagged version
        is returned.  The return value is: versionName, eupsPathDir,
        productDir, tablefile 

        If allowNewer is true, look for versions that are >= the
        specified version if an exact match fails.
        """
        if not flavor:
            flavor = self.flavor

        prod = self.findVersion(productName, versionName, eupsPathDirs, flavor)

        msg = "Unable to locate product %s %s for flavor %s." 
        if not prod and allowNewer:
            # an explicit version given; try to find a newer one
            if self.quiet <= 0:
                print >> sys.stderr, msg % (productName, versionName, flavor), \
                    ' Trying ">= %s"' % versionName

            if self.tags.isRecognized(versionName):
                versionName = None
            prod = self._findNewestVersion(productName, eupsPathDirs, flavor, 
                                           versionName)
        if not prod:
            raise RuntimeError(msg %s (productName, versionName, flavor))

    def findCurrentVersion(self, productName, path=None, currentType=None, currentTypesToTry=None):
        """
        Find current version of a product, returning eupsPathDir, version, vinfo, currentTag.
        DEPRECATED: use findPreferredProduct()
        """
        if not path:
            path = self.path
        elif isinstance(path, str):
            path = [path]

        preferred = currentTypesToTry
        if preferred is None:
            preferred = []
        if currentType is None:
            preferred.insert(currentType, 0)
        if not preferred:
            preferred = None

        out = self.findPreferredProduct(productName, path, self.flavor, preferred)

        if not out:
            raise RuntimeError("Unable to locate a preferred version of %s for flavor %s" % (productName, self.flavor))

        return out

    def findFullySpecifiedVersion(self, productName, versionName, flavor, eupsPathDir):
        """
        Find a version given full details of where to look
        DEPRECATED: use findProduct()
        """
        try: 
            out = self.findProduct(productName, versionName, eupsPathDir, flavor)
            if not out:
                raise ProductNotFound(productName, versionName, flavor, eupsPathDir)
        except ProductNotFound, e:
            raise RuntimeError(e.getMessage())

    def declareCurrent(self, productName, versionName, eupsPathDir=None, local=False):
        """Declare a product current.
        DEPRECATED: use assignTag()
        """
        utils.deprecated("Warning: Eups.declareCurrent() DEPRECATED; use assignTag()", self.quiet)

        # this will raise an exception if "current" is not allowed
        tag = self.tags.getTag("current")
        self.assignTag(tag, productName, versionName, eupsPathDir)

    def removeCurrent(self, product, eupsPathDir, currentType=None):
        """Remove the CurrentChain for productName/versionName from the live current chain (of type currentType)
        DEPRECATED: use assignTag()
        """
        utils.deprecated("Warning: Eups.remvoeCurrent() DEPRECATED; use unassignTag()", self.quiet)

        # this will raise an exception if "current" is not allowed
        if currentType is None:
            currentType = "current"
        tag = self.tags.getTag(currentType)
        self.unassignTag(tag, product, eupsPathDir=eupsPathDir)

    def listProducts(self, productName=None, productVersion=None,
                     current=False, setup=False):
        """
        Return a list of Product objects for products we know about
        with given restrictions. 

        This method is DEPRECATED; use findProducts() instead. 

        The returned list will be restricted by the name, version,
        and/or tag assignment using the productName, productVersion,
        and tags parameters, respectively.  productName and 
        productVersion can have shell wildcards (like *); in this 
        case, they will be matched in a shell globbing-like way 
        (using fnmatch).  

        current and setup are provided for backward compatibility, but
        are deprecated.  
        """
        utils.deprecated("Eups.listProducts() is deprecated; use Eups.findProducts() instead.", self.quiet)

        tags = []
        if current or setup:
            if current:  tags.append("current")
            if setup:  tags.append("setup")

        return self.findProducts(productName, productVersion, tags)

    def isReservedTag(self, tagName):
        """Is tagName the name of a reserved tag?"""
        return self._reservedTags.count(str(tagName)) > 0

    def isInternalTag(self, tagName, abort=False):
        """Is tagName the name of an internal tag such as "keep"?"""
        isInternal = self._internalTags.count(str(tagName)) > 0

        if isInternal and abort:
            raise RuntimeError, ("Error: tag \"%s\" is reserved to the implementation" % tagName)

    def isUserTag(self, tagName):
        """Is tagName the name of a user tag?"""
        return self.tags.groupFor(tagName) == self.tags.user

    def selectVRO(self, tag=None, productDir=None, versionName=None, dbz=None, inexact_version=False):
        """Set the VRO to use given a tag or pseudo-tag (e.g. "current", "version")
        @param inexact_version    Process the VRO to remove type:exact?
        """

        # Note that the order of these tests is significant
        vroTag = None
        if tag:
            for t in tag:
                self.isInternalTag(tag, True) # will abort if tag is internal
                if not vroTag and self._vroDict.has_key(t):
                    vroTag = t

            self.commandLineTagNames = tag

        if vroTag:
            pass                        # already set
        elif productDir and productDir != 'none':
            vroTag = "path"
        elif versionName:
            vroTag = "commandLine"
        else:
            vroTag = "default"

        if self.userVRO:
            tag = None                  # no need to prepend it to VRO as they set this tag's VRO explicitly
        elif self._vroDict.has_key(vroTag):            
            pass
        elif self._vroDict.has_key("default"):
            vroTag = "default"
        else:
            raise RuntimeError, ("Unable to lookup vroTag == %s in %s" % (vroTag, self._vroDict))

        vro = self._vroDict[vroTag]

        if isinstance(vro, dict):
            if vro.has_key(dbz):
                self._vro = vro[dbz]
            elif vro.has_key("default"):
                self._vro = vro["default"]
                if versionName:
                    self._vro[0:0] = ["commandLine"]
            else:
                raise RuntimeError, ("Unable to find entry for %s in VRO dictionary for tag %s" %
                                     (dbz, vroTag))
        else:
            self._vro = vro

        if self.keep:
            self._vro[0:0] = ["keep"]

        extra = ""                                  # extra string for message to user
        if tag:                                     # need to put tag near the front of the VRO,
            if True:
                where = 0
                for i, v in enumerate(self._vro): # don't put tag before commandLine or a type:SSS entry
                    if v == "commandLine" or re.search(r"^type:.+", v):
                        where = i + 1

                for t in reversed(tag):
                    self._vro[where:where] = [str(t)]
            else:
                for t in reversed(tag): # old version?
                    where = 0
                    for el in ("commandLine",):
                        if self._vro.count(el):
                            w = self._vro.index(el) + 1
                            if w > where:
                                where = w

                    self._vro[where:where] = [str(t)]

            extra = " + tag \"%s\"" % t
        #
        # Clean the VRO to remove duplicates
        #
        entries = {}
        uniqueVro = []
        for e in self._vro:
            if not entries.has_key(e):
                if re.search(r"^warn(:\d+)?$", e): # allow multiple warnings on VRO
                    if not re.search(r"^warn:\d+$", e): # change warn --> warn:1
                        e = "warn:1"
                else:
                    entries[e] = 1      # we've seen this one

                uniqueVro.append(e)
        self._vro = uniqueVro

        self._vro = Eups.__mergeWarnings(self._vro)
        #
        # They might have explicitly asked to add/remove type:exact entries
        #
        if not self.userVRO:
            if self.exact_version:          # this is a property of self
                self.makeVroExact()
            if inexact_version:             # this is a request to not process type:exact in the vro
                self._vro = filter(lambda el: el != "type:exact", self._vro)
        if self.verbose > 1:
            print >> sys.stderr, "Using VRO for \"%s\"%s: %s" % (vroTag, extra, self._vro)
        #
        # The VRO used to be called the "preferredTags";  for now use the old name
        #
        q = None # utils.Quiet(self)
        self._kindlySetPreferredTags(self._vro)
        del q

    # staticmethod;  would use a decorator if we knew we had a new enough python
    def __mergeWarnings(vro):
        """Replace consecutive sequences of warn:X by warn:min (otherwise we may get repeated warnings);
such sequences can be generated while rewriting the VRO"""

        vro = vro[:]; vro.append(None) # use None as an end-marker
        cleanedVro = []

        e, i = True, -1
        while e is not None:
            i += 1
            e = vro[i]

            debugLevelMin = None
            for j in range(i, len(vro)):
                e = vro[j]
                mat = e and re.search(r"^warn:(\d+)$", e)
                if not mat:             # neither warn:XXX nor the end-marker
                    if debugLevelMin is not None:
                        cleanedVro.append("warn:%d" % debugLevelMin)
                    i = j
                    break

                debugLevel = int(mat.group(1))
                if debugLevelMin is None or debugLevel < debugLevelMin:
                    debugLevelMin = debugLevel

            if e:
                cleanedVro.append(e)

        return cleanedVro

    __mergeWarnings = staticmethod(__mergeWarnings)

    def makeVroExact(self):
        """Modify the VRO to support setup --exact even if the table files don't have an
           if(type == exact) { block }"""
        # Move all user or global tags (and non-recognized strings) to the end of the VRO

        if self.userVRO:
            return

        vro0 = self._vro

        tagVroEntries = []              # user/global tags found on the VRO
        movedTags = False               # did we actually move any tags?
        vro = []
        for v in self._vro:
            # v may be of form warn:nnn or type:XXX so only the pre-: string is a tagname
            v0 = v.split(":")[0]

            if \
                   not self.tags.isRecognized(v0) or \
                   (not (v0 in self.commandLineTagNames) and
                    (self.tags.getTag(v0).isGlobal() or self.tags.getTag(v0).isUser())):
                if not tagVroEntries.count(v):
                    tagVroEntries.append(v)
            else:
                if tagVroEntries:       # there are tags to be moved, so ...
                    movedTags = True    # ... we'll move them
                vro.append(v)

        if tagVroEntries:
            if movedTags:
                if not filter(lambda x: re.search(r"^warn:[01]", x), vro):
                    vro += ["warn:1"]

            vro += tagVroEntries

        self._vro = vro

        if False:
            # ensure that "version" and "versionExpr" are on the VRO, after "path" and "version" respectively
            for v, vv in [("version", "path"), ("versionExpr", "version")]:
                if not self._vro.count(v):
                    if self._vro.count(vv):             # ... but not before vv
                        where = self._vro.index(vv) + 1
                    else:
                        where = 0
                    self._vro[where:where] = [v]

        if tagVroEntries:               # we moved tags to the end of the VRO
            if self.verbose > 1 and movedTags and vro0 != self._vro:
                print >> sys.stderr, "Moved [%s] to end of VRO as exact versions are desired" % \
                      ", ".join(tagVroEntries)

    def getVRO(self):
        """Return the VRO (as chosen by selectVRO)"""

        if not self._vro:
            self.selectVRO()

        return self._vro

_ClassEups = Eups                       # so we can say, "isinstance(Eups, _ClassEups)"


class _TagSet(object):
    def __init__(self, eups, tags):
        self.eups = eups
        self.lu = {}
        if tags:
            for tag in tags:
                self.lu[tag] = True
    def intersects(self, tags):
        for tag in tags:
            try:
                tag = str(self.eups.tags.getTag(tag)) # make sure that we have e.g. user: prefix
            except TagNotRecognized:
                return False
            if self.lu.has_key(tag):
                return True
        return False

def _set(iterable):
    """
    return the unique members of a given list.  This is used in lieu of 
    a python set to support python 2.3 and earlier.
    """
    out = []
    for i in iterable:
        if i not in out:
            out.append(i)
    return out

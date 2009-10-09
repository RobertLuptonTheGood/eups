"""
common high-level EUPS functions appropriate for calling from an application.
"""

import re, os, sys, time
from Eups           import Eups
from exceptions     import ProductNotFound
from tags           import Tag, TagNotRecognized
from stack          import ProductStack, persistVersionName as cacheVersion
from distrib.server import ServerConf
import utils, table, distrib.builder, hooks


def printProducts(ostrm, productName=None, versionName=None, eupsenv=None, 
                  tags=None, setup=False, tablefile=False, directory=False, 
                  dependencies=False, showVersion=False, setupType=None):
    """
    print out a listing of products
    @param ostrm           the output stream to send listing to
    @param productName     restrict the listing to this product
    @param versionName     restrict the listing to this version of the product.
    @param eupsenv         the Eups instance to use; if None, a default 
                              will be created.  
    @param tags            restrict the listing to products with these tag names
    @param setup           restrict the listing to products that are currently
                              setup
    @param tablefile       include the path to each product's table file
    @param directory       include each product's installation directory
    @param dependencies    
    @param showVersion     
    @param setupType       
    """

    if not eupsenv:
        eupsenv = Eups()
    if tags:
        tags = tags.split()
        badtags = filter(lambda t: not eupsenv.tags.isRecognized(t), tags)
        if badtags:
            raise TagNotRecognized(str(badtags), 
                                   msg="Unsupported tag(s): %s" % 
                                       ", ".join(badtags))
        if setup:
            tags.append("setup")
    elif setup:
        tags = ["setup"]


    productNameIsGlob = productName and re.search(r"[\[\]?*]", productName) # is productName actually a glob?

    productList = eupsenv.findProducts(productName, versionName, tags)
    
    if dependencies:
        _msgs = {}               # maintain list of printed dependencies
        recursionDepth, indent = 0, ""
        
    productTags = {}                    # list of tags indexed by product

    for pi in productList:
        name, version, db = pi.name, pi.version, pi.db # for convenience
        info = ""

        if dependencies:
            if not info:
                if eupsenv.verbose or not _msgs.has_key(name):
                    _msgs[name] = version
                    info += "%-40s %s" % (name, version)

            prodtbl = pi.getTable()
            if prodtbl:

                for product, optional, recursionDepth in \
                        prodtbl.dependencies(eupsenv, recursive=True, 
                                             recursionDepth=1, 
                                             setupType=setupType):

                    if eupsenv.verbose or not _msgs.has_key(product.name):
                        _msgs[product.name] = product.version

                        if info:
                            info += "\n"

                        indent = "| " * (recursionDepth/2)
                        if recursionDepth%2 == 1:
                            indent += "|"

                        versionName = product.version
                        info += "%-40s %s" % (("%s%s" % (indent, product.name)), versionName)

        elif directory or tablefile:
            if eupsenv.verbose:
                info += "%-10s" % (version)

            if directory:
                if pi.dir:
                    info += pi.dir
                else:
                    info += ""
            if tablefile:
                if info:
                    info += "\t"

                if pi.tablefile:
                    info += pi.tablefile
                else:
                    info += "none"

        elif showVersion:
            info += "%-10s" % (version)

        else:
            if productName and not productNameIsGlob:
                info += "   "
            else:
                info += "%-21s " % (name)
            info += "%-10s" % (version)
            if eupsenv.verbose:
                if eupsenv.verbose > 1:
                    info += "%-10s" % (pi.flavor)

                info += "%-20s %-55s" % (db, pi.dir)


            extra = pi.tags

            if eupsenv.isSetup(pi.name, pi.version, pi.stackRoot()):
                extra += ["setup"]
            if extra:
                info += "\t" + " ".join(extra)

        if info:
            print info

def printUses(outstrm, productName, versionName=None, eupsenv=None, 
              depth=9999, showOptional=False, tags=None):
    """
    print a listing of products that make use of a given product.  
    @param outstrm       the output stream to write the listing to 
    @parma productName   the name of the product to find usage of for
    @param versionName   the product version to query.  If None, all
                            versions will be considered
    @param eupsenv       the Eups instance to use; if None, a default will
                            be created.
    @param depth         maximum number of dependency levels to examine
    @param showOptional  if True, indicate if a dependency is optional.  
    @param tags          the preferred set of tags to choose when examining
                            dependencies.  
    """
    if not eupsenv:
        eupsenv = Eups()
    if tags:
        eupsenv.setPreferredTags(tags)

    #
    # To work
    #
    userList = eupsenv.uses(productName, versionName, depth)

    if len(userList) == 0:              # nobody cares.  Maybe the product doesn't exist?
        productList = eupsenv.findProducts(productName, versionName)
        if len(productList) == 0:
            raise ProductNotFound(productName, versionName)

    fmt = "%-25s %-15s"
    str = fmt % ("product", "version")

    if versionName:                             # we know the product version, so don't print it again
        fmt2 = None
    else:
        fmt2 = " %-15s"
        str += fmt2 % ("%s version" % productName)
    print >> outstrm, str

    for (p, pv, requestedInfo) in userList:
        requestedVersion, optional, productDepth = requestedInfo

        if optional and not showOptional:
            continue

        str = fmt % (("%*s%s" % (depth - productDepth, "", p)), pv)
        if fmt2:
            str += fmt2 % (requestedVersion)

        if showOptional:
            if optional:
                str += "Optional"

        print >> outstrm, str

def expandBuildFile(ofd, ifd, product, version, svnroot=None, cvsroot=None,
                    eupsenv=None):
    """
    expand the template variables in a .build script to produce an 
    explicitly executable shell scripts.  

    @param ofd      the output file stream to write expanded script to.
    @param ifd      the input file stream to read the build template from.
    @param product  the name of the product to assume for this build file
    @param version  the version to assume
    @param svnroot  An SVN root URL to find source code under.
    @param cvsroot  A CVS root URL to find source code under.
    @param eupsenv  the Eups instance to use; if None, a default will
                       be created.
    """
    if not eupsenv:
        eupsenv = eups.Eups()
    productList = {}
    productList[product] = version

    return _expandFile(eupsenv, ifd, ofd, productList, "build") 


def expendTableFile(ofd, ifd, productList, versionRegexp=None, eupsenv=None):
    if not eupsenv:
        eupsenv = eups.Eups()
    return _expandFile(eupsenv, ofd, ifd, productList, "table", 
                       versionRegexp=versionRegexp)


def _expandFile(eupsenv, ifd, ofd, productList, fileType=None, **kwargs):
    """Expand a build or table file"""

    assert fileType
    
    if fileType == "build":
        assert len(productList.keys()) == 1
        
        productName = productList.keys()[0]
        versionName = productList[productName]

        cvsroot = kwargs.get("cvsroot")
        svnroot = kwargs.get("svnroot")
        #
        # Guess the value of PRODUCT
        #
        if productName:
            pass
        else:
            mat = re.search(r"^([^.]+)\.build$", os.path.basename(inFile))
            if mat:
                productName = mat.group(1)
    elif fileType == "table":
        versionRegexp = kwargs.get("versionRegexp")
    else:
        raise RuntimeError, ("Unknown file type: %s" % fileType)
    
    #
    # Actually do the work
    #
    try:
        if fileType == "build":
            distrib.builder.expandBuildFile(ofd, ifd, productName, 
                                            versionName, eupsenv.verbose, 
                                            svnroot=svnroot, cvsroot=cvsroot)
                                            
                                               
        elif fileType == "table":
            table.expandTableFile(eupsenv, ofd, ifd, productList, versionRegexp)
        else:
            raise AssertionError, ("Impossible fileType: %s" % fileType)
    except Exception:
        if backup and os.path.exists(backup):
            os.rename(backup, inFile)
        raise

    if backup and os.path.exists(backup):
        os.unlink(backup)

def declare(productName, versionName, productDir=None, eupsPathDir=None, 
            tablefile=None, tag=None, eupsenv=None):
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
                           it is looked for under productDir/ups.
    @param tag           the tag to assign to this product.  If the 
                           specified product is already registered with
                           the same product directory and table file,
                           then use of this input will simple assign this
                           tag to the variable.  (See also above note about 
                           backward compatibility.)
    @param eupsenv       the Eups instance to assume.  If None, a default 
                           will be created.  
    """
    if not eupsenv:
        eupsenv = Eups()
    return eupsenv.declare(productName, versionName, productDir, eupsPathDir,
                           tablefile, tag)
           
def undeclare(productName, versionName=None, eupsPathDir=None, tag=None,
              eupsenv=None):
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
                           a RuntimeError is raised.  
    @param eupsPathDir   the product stack to undeclare the product from.
                           ProductNotFound is raised if the product 
                           is not installed into this stack.  
    @param tag           if not None, only unassign this tag; product
                            will not be undeclared.  
    @param eupsenv       the Eups instance to assume.  If None, a default 
                           will be created.  
    """
    if not eupsenv:
        eupsenv = Eups()
    return eupsenv.undeclare(productName, versionName, eupsPathDir, tag)
                             
def clearCache(path=None, flavors=None):
    """
    remove the product cache for given stacks/databases and flavors
    @param path     the stacks to clear caches for.  This can be given either
                        as a python list or a colon-delimited string.  If 
                        None (default), EUPS_PATH will be used.
    @param flavors  the flavors to clear the cache for.  This can either 
                        be a python list or space-delimited string.  If None,
                        clear caches for all flavors.
    """
    if path is None:
        path = os.environ["EUPS_PATH"]
    if isinstance(path, str):
        path = path.split(":")

    if isinstance(flavors, str):
        flavors = flavors.split()

    for p in path:
        dbpath = os.path.join(p, Eups.ups_db)

        flavs = flavors
        if flavs is None:
            flavs = ProductStack.findCachedFlavors(dbpath)
        if not flavs:
            continue

        # FIXME: this does not clear caches in user's .eups directory;
        #        by default, it only clears current platform's flavors
        ProductStack.fromCache(dbpath, flavs, autosave=False).clearCache()

def listCache(path=None, verbose=0, flavor=None):
    if path is None:
        path = os.environ["EUPS_PATH"]
    if isinstance(path, str):
        path = path.split(":")

    if not flavor:
        flavor = utils.determineFlavor()

    for p in path:
        dbpath = os.path.join(p, Eups.ups_db)
        cache = ProductStack.fromCache(dbpath, flavor, updateCache=False, 
                                       autosave=False)
                                       
                                       

        productNames = cache.getProductNames()
        productNames.sort()

        colon = ""
        if verbose:
            colon = ":"

        print "%-30s (%d products) [cache verison %s]%s" % \
            (p, len(productNames), cacheVersion, colon)

        if not verbose:
            continue

        for productName in productNames:
            versionNames = cache.getVersions(productName)
            versionNames.sort(hooks.version_cmp)

            print "  %-20s %s" % (productName, " ".join(versionNames))

def Current():
    """
    a deprecated means of specifying a preferred tag.  This will return
    None, which is consistent with how it was typically once used as a 
    value for a version parameter to a function.  Now, passing None to 
    version means that the version assigned with the most preferred tag 
    is desired.
    """
    print >> sys.stderr, "Note to Scripters: Use of Current() is deprecated", \
        "(and ignored)."
    return None

def osetup(Eups, productName, version=None, fwd=True, setupType=None):
    """
    Identical to setup() but with a deprecated signature.
    """
    return setup(productName, version, None, setupType, Eups, fwd)

def setup(productName, version=None, prefTags=None, productRoot=None, 
          setupType=None, eupsenv=None, fwd=True):
    """
    Return a set of shell commands which, when sourced, will setup a product.  
    (If fwd is false, unset it up.)

    Note that if the first argument is found to be an instance of Eups,
    this function will assume that the old setup() signature is expected
    by the caller, and the parameters will be forwarded to osetup().

    @param productName     the name of the desired product to setup.  
    @param version         the desired version of the product.  This can 
                             either a string giving an explicit version
                             or a Tag instance.  
    @param prefTags        the preferred tags, in order, for choosing 
                             versions of product dependencies.  If set,
                             the Eups instance will be temporarily altered 
                             to prepend this list to the Eups' set of 
                             preferred tags.  
    @param productRoot     the root directory where the product is installed.
                             If set, Eups will not consult its database for
                             the product's location, but rather set it up as
                             a "LOCAL" product.  
    @param setupType       the setup type.  This will cause conditional
                             sections of the table filebased on "type" 
                             (e.g. "if (type == build) {...") to be 
                             executed.  
    @param eupsenv         the Eups instance to use to do the setup.  If 
                             None, one will be created for it.
    @param fwd             If False, actually do an unsetup.
    """
    if isinstance(productName, Eups):
        # Note: this probably won't work if a mix of key-worded and 
        # non-keyworded parameters are used.
        if productName.quiet < 1:
            print >> sys.stderr, "setup(): assuming deprecated function signature"
        if productRoot is None:  productRoot = True
        return osetup(productName, version, prefTags, productRoot, setupType)

    if not eupsenv:
        eupsenv = Eups(readCache=False)

    if isinstance(prefTags, str):
        prefTags = prefTags.split()
    elif isinstance(prefTags, Tag):
        prefTags = [prefTags]

    oldPrefTags = None
    if prefTags:
        badtags = filter(lambda t: not eupsenv.tags.isRecognized(t), prefTags)
        if badtags:
            raise TagNotRecognized(str(badtags),
                                   msg="Unsupported tags: %s" % 
                                       map(lambda t: str(t), badtags))
        prefTags = map(lambda t: t.name, map(eupsenv.tags.getTag, prefTags))

        # prepend the given tags to the preferred list.
        oldPrefTags = eupsenv.getPreferredTags()
        eupsenv.setPreferredTags(prefTags + oldPrefTags)

    cmds = []

    ok, version, reason = eupsenv.setup(productName, version, fwd, 
                                        setupType=setupType, 
                                        productRoot=productRoot)
    if ok:
        #
        # Set new variables
        #
        for key in os.environ.keys():
            val = os.environ[key]
            try:
                if val == eupsenv.oldEnviron[key]:
                    continue
            except KeyError:
                pass

            if val and not re.search(r"^['\"].*['\"]$", val) and \
                   re.search(r"[\s<>|&;()]", val):   # quote characters that the shell cares about
                val = "'%s'" % val

            if eupsenv.shell == "sh" or eupsenv.shell == "zsh":
                cmd = "export %s=%s" % (key, val)
            elif eupsenv.shell == "csh":
                cmd = "setenv %s %s" % (key, val)

            if eupsenv.noaction:
                if eupsenv.verbose < 2 and re.search(r"SETUP_", key):
                    continue            # the SETUP_PRODUCT variables are an implementation detail

                cmd = "echo \"%s\"" % cmd

            cmds += [cmd]
        #
        # unset ones that have disappeared
        #
        for key in eupsenv.oldEnviron.keys():
            if re.search(r"^EUPS_(DIR|PATH)$", key): # the world will break if we delete these
                continue        

            if os.environ.has_key(key):
                continue

            if eupsenv.shell == "sh" or eupsenv.shell == "zsh":
                cmd = "unset %s" % (key)
            elif eupsenv.shell == "csh":
                cmd = "unsetenv %s" % (key)

            if eupsenv.noaction:
                if eupsenv.verbose < 2 and re.search(r"SETUP_", key):
                    continue            # an implementation detail

                cmd = "echo \"%s\"" % cmd

            cmds += [cmd]
        #
        # Now handle aliases
        #
        for key in eupsenv.aliases.keys():
            value = eupsenv.aliases[key]

            try:
                if value == eupsenv.oldAliases[key]:
                    continue
            except KeyError:
                pass

            if eupsenv.shell == "sh":
                cmd = "function %s { %s ; }; export -f %s" % (key, value, key)
            elif eupsenv.shell == "csh":
                value = re.sub(r"\$@", r"\!*", value)
                cmd = "alias %s \'%s\'" % (key, value)
            elif eupsenv.shell == "zsh":
                cmd = "%s() { %s ; }" % (key, value, key)

            if eupsenv.noaction:
                cmd = "echo \"%s\"" % re.sub(r"`", r"\`", cmd)

            cmds += [cmd]
        #
        # and unset ones that used to be present, but are now gone
        #
        for key in eupsenv.oldAliases.keys():
            if eupsenv.aliases.has_key(key):
                continue

            if eupsenv.shell == "sh" or eupsenv.shell == "zsh":
                cmd = "unset %s" % (key)
            elif eupsenv.shell == "csh":
                cmd = "unalias %s" (key)

            if eupsenv.noaction:
                cmd = "echo \"%s\"" % cmd

            cmds += [cmd]
    elif fwd and version is None:
        print >> sys.stderr, \
            "Unable to find a preferred version of", productName
        cmds += ["false"]               # as in /bin/false
    else:
        if fwd:
            versionName = version

            if eupsenv.isLegalRelativeVersion(versionName):
                versionName = ""

            if versionName:
                versionName = " " + versionName
        
            print >> sys.stderr, "Failed to setup %s%s: %s" % (productName, versionName, reason)
        else:
            print >> sys.stderr, "Failed to unsetup %s: %s" % (productName, reason)

        cmds += ["false"]               # as in /bin/false

    if oldPrefTags is not None:
        eupsenv.setPreferredTags(oldPrefTags)
    return cmds

def unsetup(productName, version=None, eupsenv=None):
    """ 
    Return a set of shell commands which, when sourced, will unsetup a product.
    This is equivalent to setup(productName, version, fwd=False). 
    """
    return setup(productName, version, fwd=False)

    

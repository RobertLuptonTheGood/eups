"""
common high-level EUPS functions appropriate for calling from an application.
"""

import re, os, sys, time
from Eups           import Eups
from exceptions     import ProductNotFound
from tags           import Tags, Tag, TagNotRecognized
from VersionParser  import VersionParser
from stack          import ProductStack, persistVersionName as cacheVersion
from distrib.server import ServerConf
import utils, table, distrib.builder, hooks


def printProducts(ostrm, productName=None, versionName=None, eupsenv=None, 
                  tags=None, setup=False, tablefile=False, directory=False, 
                  dependencies=False, showVersion=False, setupType=None,
                  depth=None, giveHints=True):
    """
    print out a listing of products.  Returned is the number of products listed.
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
    @param depth           a string giving an expression for determining
                             whether a dependency of a certain depth should
                             be included.  This string can be a simple integer
                             which will be taken to mean, print all depths
                             <= that integer.  An expression having just a
                             a logical operator and an integer (e.g. 
                             "> 3") implies a comparison with the depth
                             of each dependency (i.e. "depth > 3").  
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
    productList.sort(lambda a,b: cmp(a, b), 
                     lambda p: ":".join([p.name, p.version]))
    
    if dependencies:
        _msgs = {}               # maintain list of printed dependencies
        recursionDepth, indent = 0, ""
        
    productTags = {}             # list of tags indexed by product

    oinfo = None                 # previous value of "info"; used to suppress repetitions due to e.g. 
                                 # listing directories when there's a NULL and Linux declaration 

    if depth is None: 
        depth = "True" 
    else: 
        try: 
            depth = "<= %d" % int(depth) 
        except ValueError: 
            pass 
 
        if not re.search(r"depth", depth): 
            depth = "depth" + depth 
         
    def includeProduct(recursionDepth): 
        """Should we include a product at this recursionDepth in the listing?""" 
        depthExpr = VersionParser(depth)
        depthExpr.define("depth", recursionDepth) 
        return depthExpr.eval() 

    nprod = len(productList)
    for pi in productList:
        name, version, root = pi.name, pi.version, pi.stackRoot() # for convenience
        if root == "none":  root = " (none)"
        info = ""

        if dependencies:
            recursionDepth = 0 
#             if not info:
#                 if eupsenv.verbose or not _msgs.has_key(name):
#                     _msgs[name] = version
#                     info += "%-40s %s" % (name, version)
            if includeProduct(recursionDepth):
                info += "%-40s %s" % (name, version)

            prodtbl = pi.getTable()
            if prodtbl:

                for product, optional, recursionDepth in \
                        prodtbl.dependencies(eupsenv, recursive=True, 
                                             recursionDepth=1, 
                                             setupType=setupType):

                    if not includeProduct(recursionDepth):
                        continue

                    if eupsenv.verbose or not _msgs.has_key(product.name):
                        _msgs[product.name] = product.version

                        if info:
                            info += "\n"

                        if not re.search(r"==", depth): 
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

                info += "%-20s %-55s" % (root, pi.dir)


            extra = pi.tags

            if eupsenv.isSetup(pi.name, pi.version, pi.stackRoot()):
                extra += ["setup"]
            if extra:
                info += "\t" + " ".join(extra)

        if info:
            if info != oinfo: 
                print info 
                oinfo = info

    return nprod

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
                    verbose=0):
    """
    expand the template variables in a .build script to produce an 
    explicitly executable shell scripts.  

    @param ofd      the output file stream to write expanded script to.
    @param ifd      the input file stream to read the build template from.
    @param product  the name of the product to assume for this build file
    @param version  the version to assume
    @param svnroot  An SVN root URL to find source code under.
    @param cvsroot  A CVS root URL to find source code under.
    @param verbose  an integer verbosity level where larger values result 
                       in more messages
    """
    distrib.builder.expandBuildFile(ofd, ifd, product, version, verbose,
                                    svnroot=svnroot, cvsroot=cvsroot)


def expandTableFile(ofd, ifd, productList, versionRegexp=None, eupsenv=None):
    """
    expand the version specifications in a table file.  When a version in 
    the original table file is expressed as an expression, the expression is 
    enclosed in brackets and the actual product version used to build the 
    table file's product.  

    @param ofd          the output file stream to write expanded tablefile to.
    @param ifd          the input file stream to read the tablefile from.
    @param productList  a lookup dictionary of the as-built versions.  The 
                           keys are product names and the values are the 
                           versions.
    @param versionRegexp  an unparsed regular expression string
    @param eupsenv      an Eups instance to assume.  If not provided, a 
                           default will be created.  
    """
    if not eupsenv:
        eupsenv = eups.Eups()

    table.expandTableFile(eupsenv, ofd, ifd, productList, versionRegexp)


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
                             
def clearCache(path=None, flavors=None, inUserDir=False):
    """
    remove the product cache for given stacks/databases and flavors
    @param path     the stacks to clear caches for.  This can be given either
                        as a python list or a colon-delimited string.  If 
                        None (default), EUPS_PATH will be used.
    @param flavors  the flavors to clear the cache for.  This can either 
                        be a python list or space-delimited string.  If None,
                        clear caches for all flavors.
    @param inUserDir  if True (default), it will be assumed that it is the
                        cache in the user's data directory that should be
                        cleared.
    """
    if path is None:
        path = os.environ["EUPS_PATH"]
    if isinstance(path, str):
        path = path.split(":")

    userDataDir = None
    if inUserDir:
        userDataDir = utils.defaultUserDataDir()

    if isinstance(flavors, str):
        flavors = flavors.split()

    for p in path:
        dbpath = os.path.join(p, Eups.ups_db)

        persistDir = dbpath
        if userDataDir:
            persistDir = utils.userStackCacheFor(p, userDataDir)

        flavs = flavors
        if flavs is None:
            flavs = ProductStack.findCachedFlavors(persistDir)
        if not flavs:
            continue

        ProductStack.fromCache(dbpath, flavs, persistDir=persistDir,
                               autosave=False).clearCache()

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
    utils.deprecated("Use of Current() is deprecated (and ignored).")
    return None

def Setup():
    """
    a deprecated means of getting an instance of the standard setup tag.
    Prefer eups.Tag("setup") instead.
    """
    return Tag("setup")

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
        utils.deprecated("setup(): assuming deprecated function signature", 
                         productName.quiet)
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
        # Check that we got the desired tag
        #
        if prefTags:
            for tag in prefTags:
                taggedVersion = eupsenv.findTaggedProduct(productName, tag)
                if taggedVersion:
                    break

            if taggedVersion:
                if version == taggedVersion.version: # OK, we got it
                    pass
                else:
                    print >> sys.stderr, "Requested version tagged %s == \"%s\"; got version \"%s\"" % \
                          (",".join(prefTags), taggedVersion.version, version)
            else:
                if not re.search(r"^LOCAL:", version):
                    print >> sys.stderr, "No versions of %s are tagged %s; setting up %s" % \
                          (productName, ",".join(prefTags), version)

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
                value = re.sub(r"\"?\$@\"?", r"\!*", value)
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

def productDir(productName, versionName=Setup(), eupsenv=None):
    """
    return the installation directory (PRODUCT_DIR) for the specified 
    product.  None is returned if no matching product can be found
    @param productName   the name of the product of interest
    @param version       the desired version.  This can in one of the 
                         following forms:
                          *  an explicit version 
                          *  a version expression (e.g. ">=3.3")
                          *  a Tag instance 
                          *  None, in which case, the (most) preferred 
                               version will be returned.
                         The default is the global tag "setup".  
    @param eupsenv       The Eups instance to use to find the product.  If 
                            not provided, a default will created.  
    """
    if not productName:
        raise EupsException("productDir(): no product name specified")
    if not eupsenv:
        eupsenv = Eups()

    prod = eupsenv.findProduct(productName, versionName)
    if not prod:
        return None
    return prod.dir

def getSetupVersion(productName, eupsenv=None):
    """
    return the version name for the currently setup version of a given product.
    This is equivalent to eupsenv.
    @param productName   the name of the setup product
    @param eupsenv       the Eups instance to use; if None (default), a 
                             default will be created.
    @throws ProductNotFound  if the requested product is not setup
    """
    if not eupsenv:
        eupsenv = Eups()
    version = eupsenv.findSetupVersion(productName)[0]
    if not version:
        raise ProductNotFound(productName, msg="%s is not setup" % productName)
    return version

"""
common high-level EUPS functions appropriate for calling from an application.
"""

from __future__ import absolute_import, print_function
import re
import os
try:
    import cPickle as pickle
except ImportError:
    import pickle
from .Eups           import Eups
from .exceptions     import ProductNotFound
from .tags           import Tag, checkTagsList
from .Product import Product
from .VersionParser  import VersionParser
from .stack          import ProductStack, persistVersionName as cacheVersion
from . import utils, table, hooks
from .exceptions import EupsException

def printProducts(ostrm, productName=None, versionName=None, eupsenv=None, 
                  tags=None, setup=False, tablefile=False, directory=False, 
                  dependencies=False, showVersion=False, showName=False,
                  depth=None, productDir=None, topological=False, checkCycles=False, raw=False):
    """
    print out a listing of products.  Returned is the number of products listed.
    @param ostrm           the output stream to send listing to
    @param productName     restrict the listing to this product
    @param versionName     restrict the listing to this version of the product.
    @param eupsenv         the Eups instance to use; if None, a default 
                              will be created.  
    @param tags            restrict the listing to products with these tag names
    @param setup           restrict the listing to products that are currently
                              setup (or print actually setup versions with dependencies)
    @param tablefile       include the path to each product's table file
    @param directory       include each product's installation directory
    @param dependencies    print the product's dependencies
    @param showVersion     Only print the product{'s,s'} version[s] (e.g. eups list -V -s afw)
    @param showName        Only print the product{'s,s'} name[s] (e.g. eups list --name -t rhl)
    @param depth           a string giving an expression for determining
                             whether a dependency of a certain depth should
                             be included.  This string can be a simple integer
                             which will be taken to mean, print all depths
                             <= that integer.  An expression having just a
                             a logical operator and an integer (e.g. 
                             "> 3") implies a comparison with the depth
                             of each dependency (i.e. "depth > 3").  
    @param topological     List dependencies in topological-sorted order
    @param checkCycles     Raise RuntimeError if topological sort detects a cycle
    @param raw             Generate "raw" output (suitable for further processing)
    """

    if not eupsenv:
        eupsenv = Eups()
    if tags:
        if isinstance(tags, str):
            tags = tags.split()
        checkTagsList(eupsenv, tags)
    elif setup and not dependencies:
        tags = ["setup"]

    # If productDir is provided only list its dependencies;  we do this by setting it up
    if productDir:
        if not dependencies:
            raise EupsException("-r only makes sense with --dependencies")

        if productDir:
            ups_dir = os.path.join(productDir, "ups")
            if not os.path.isdir(ups_dir):
                raise EupsException("Unable to guess product name as product has no ups directory")

            p = utils.guessProduct(ups_dir)

            if productName:
                if p != productName:
                    raise EupsException("Guessed product %s from ups directory, but %s from path" % \
                                        (productName, p))
            else:
                productName = p  

        if tags:
            tag = tags[0]
        else:
            tag = None

        eupsenv.setup(productName, versionName, productRoot=os.path.abspath(productDir))
        setup = True                    # only list this version

    productNameIsGlob = productName and re.search(r"[\[\]?*]", productName) # is productName actually a glob?

    productList = eupsenv.findProducts(productName, versionName, tags)
    if not productList:
        if productName:
            msg = productName
            if versionName:
                msg += " %s" % versionName
            if tags:
                msg += " tagged \"%s\"" % ", ".join([Tag(t).name for t in tags])

            raise ProductNotFound(productName, versionName, msg="Unable to find product %s" % msg)

    productList.sort(lambda a,b: cmp(a, b), 
                     lambda p: ":".join([p.name, p.version]))
    
    if dependencies:
        _msgs = {}               # maintain list of printed dependencies
        recursionDepth, indent = 0, ""

        if len(productList) > 1:
            if setup:
                productList = eupsenv.getSetupProducts(productName)
            else:
                raise EupsException("Please choose the version you want listed (%s)" %
                                    (", ".join([p.version for p in productList])))
    else:
        if topological:
            raise EupsException("--topological only makes sense with --dependencies")
        
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

    if dependencies:
        recursionDepth = 0 

        product = productList[0]

        if includeProduct(recursionDepth) and not (checkCycles and not topological):
            if raw:
                fmt = "%s|%s"
            else:
                fmt = "%-40s %s"
            print(fmt % (product.name, product.version))

        for product, optional, recursionDepth in eupsenv.getDependentProducts(product, setup,
                                                                              topological=topological,
                                                                              checkCycles=checkCycles):
            if not includeProduct(recursionDepth) or (checkCycles and not topological):
                continue

            if eupsenv.verbose or not _msgs.has_key(product.name):
                _msgs[product.name] = product.version

                if not re.search(r"==", depth): 
                    indent = "| " * (recursionDepth/2) 
                    if recursionDepth%2 == 1: 
                        indent += "|" 

                if raw:
                    print("%s|%s" % (product.name, product.version))
                else:
                    print("%-40s %s" % (("%s%s" % (indent, product.name)), product.version))

        return 1
    #
    # See if some tag appears more than once;  if so, they are from different stacks
    #
    tagsSeen = {}
    for pi in productList:
        for t in pi.tags:
            if not tagsSeen.has_key(t):
                tagsSeen[t] = {}
            if not tagsSeen[t].has_key(pi.name):
                tagsSeen[t][pi.name] = 0

            tagsSeen[t][pi.name] += 1
    #
    # Actually list the products
    #
    nprod = len(productList)
    for pi in productList:
        name, version, root = pi.name, pi.version, pi.stackRoot() # for convenience
        if root == "none":  root = " (none)"
        info = ""

        if setup:
            if not eupsenv.isSetup(pi.name, pi.version, pi.stackRoot()):
                continue
        else:
            if not pi._prodStack:       # only found in the environment
                if False:           
                    continue            # Exclude environment-only products
        
        if directory or tablefile:
            if eupsenv.verbose:
                if raw:
                    if info:
                        info += "|"
                    info += version
                else:
                    info += "%-10s" % (version)

            if directory:
                if pi.dir:
                    if raw and info:
                        info += "|"
                    info += pi.dir
                else:
                    info += ""
            if tablefile:
                if info:
                    if raw:
                        info += "|"
                    else:
                        info += "\t"

                if pi.tablefile:
                    info += pi.tablefile
                else:
                    info += "none"
        elif showName:
            if raw:
                if info:
                    info += "|"
                info += name
            else:
                info += "%-10s" % (name)
        elif showVersion:
            info += "%-10s" % (version)
        else:
            if raw:
                if info:
                    info += "|"
                info += name + "|" + version
            else:
                if productName and not productNameIsGlob:
                    info += "   "
                else:
                    info += "%-21s " % (name)
                info += "%-10s " % (version)
            if eupsenv.verbose:
                if raw:
                    if info:
                        info += "|"
                if eupsenv.verbose > 1:
                    if raw:
                        info += pi.flavor + "|"
                    else:
                        info += "%-10s" % (pi.flavor)

                if raw:
                    info += root + "|" + pi.dir
                else:
                    info += "%-20s %-55s" % (root, pi.dir)

                extra = pi.tags
            else:
                extra = []
                for t in pi.tags:
                    if not eupsenv.verbose:
                        t = Tag(t).name # get the bare tag name, not e.g. user:foo
                    if tagsSeen.get(t) and tagsSeen[t].get(pi.name) > 1:
                        t = "%s[%s]" % (t, root)
                    extra.append(t)

            if eupsenv.isSetup(pi.name, pi.version, pi.stackRoot()):
                extra += ["setup"]
            if raw and info:
                info += "|"

            if extra:
                if raw:
                    info += ":".join(extra)
                else:
                    info += "\t" + " ".join(extra)

        if info:
            if info != oinfo: 
                print(info) 
                oinfo = info

    return nprod

def printUses(outstrm, productName, versionName=None, eupsenv=None, 
              depth=9999, showOptional=False, tags=None, pickleFile=None):
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
    @param pickleFile    file to save uses dependencies to (or read from if starts with <)
    """
    if not eupsenv:
        eupsenv = Eups()
    if tags:
        eupsenv.setPreferredTags(tags)

    #
    # To work
    #
    if pickleFile and pickleFile[0] == "<": # read it
        fd = open(pickleFile[1:])
        usesInfo = cPickle.load(fd)
        fd.close()
    else:
        usesInfo = eupsenv.uses()
        if pickleFile:
            fd = open(pickleFile, "w")
            cPickle.dump(usesInfo, fd)
            fd.close()

    userList = eupsenv.uses(productName, versionName, depth, usesInfo=usesInfo)

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
    print(str, file=outstrm)

    for (p, pv, requestedInfo) in userList:
        if requestedInfo.optional and not showOptional:
            continue

        str = fmt % (("%*s%s" % (0*requestedInfo.depth, "", p)), pv)
        if fmt2:
            str += fmt2 % (requestedInfo.version)

        if showOptional:
            if requestedInfo.optional:
                str += "Optional"

        print(str, file=outstrm)

def getDependencies(productName, versionName=None, eupsenv=None, setup=False, shouldRaise=False,
                    followExact=None, topological=False):
    """
    Return a list of productName's dependent products : [(productName, VersionName, optional, recursionDepth), ...]
    @param productName     Desired product's name
    @param versionName     Desired version of product
    @param eupsenv         the Eups instance to use; if None, a default will be created.  
    @param setup           Return the versions of dependent products that are actually setup
    @param shouldRaise     Raise an exception if setup is True and a required product isn't setup
    @param followExact     If None use the exact/inexact status in eupsenv; if non-None set desired exactness

    See also Eups.getDependentProducts()
    """

    if not eupsenv:
        eupsenv = Eups()

    topProduct = eupsenv.findProduct(productName, versionName)
    if not topProduct:                  # it's never been declared (at least not with this version)
        return []
        
    return [(product.name, product.version, optional, recursionDepth) for product, optional, recursionDepth in
            eupsenv.getDependentProducts(topProduct, setup, shouldRaise, followExact,
                                         topological=topological)]

def expandBuildFile(ofd, ifd, product, version, svnroot=None, cvsroot=None, repoVersion=None,
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
    @param repoVersion  the version name within the repository
    @param verbose  an integer verbosity level where larger values result 
                       in more messages
    """
    builderVars = hooks.config.distrib["builder"]["variables"]

    if cvsroot:
        builderVars["CVSROOT"] = cvsroot
    if svnroot:
        builderVars["SVNROOT"] = svnroot

    distrib.builder.expandBuildFile(ofd, ifd, product, version, verbose, builderVars,
                                    repoVersionName=repoVersion)


def expandTableFile(ofd, ifd, productList, versionRegexp=None, eupsenv=None, force=False,
                    expandVersions=True, addExactBlock=True, toplevelName=None):
    """
    expand the version specifications in a table file.  When a version in 
    the original table file is expressed as an expression, the expression is 
    enclosed in brackets and the actual product version used to build the 
    table file's product is added.  

    @param ofd          the output file stream to write expanded tablefile to.
    @param ifd          the input file stream to read the tablefile from.
    @param productList  a lookup dictionary of the as-built versions.  The 
                           keys are product names and the values are the 
                           versions.
    @param versionRegexp  an unparsed regular expression string
    @param eupsenv      an Eups instance to assume.  If not provided, a 
                           default will be created.  
    @param force        convert missing required dependencies to optional
    """
    if not eupsenv:
        eupsenv = eups.Eups()

    try:
        table.expandTableFile(eupsenv, ofd, ifd, productList, versionRegexp, force,
                              expandVersions, addExactBlock, toplevelName)
    except ProductNotFound:
        raise

def declare(productName, versionName, productDir=None, eupsPathDir=None, 
            tablefile=None, externalFileList=[], tag=None, eupsenv=None):
    """
    Declare a product.  That is, make this product known to EUPS.  

    If the product is already declared, this method can be used to
    change the declaration.  The most common type of
    "redeclaration" is to only assign a tag.  (Note that this can 
    be accomplished more efficiently with assignTag() as well.)
    Attempts to change other data for a product requires self.force
    to be true. 

    If the product has no installation directory or table file,
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
    @param externalFileList  List of tuples (infile, outfile) of files that should be
                         saved in the product's "Extra" directory
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
                           tablefile, externalFileList=externalFileList, tag=tag)
           
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
                             
def clearCache(path=None, flavors=None, inUserDir=False, verbose=0):
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
    @params verbose   chattiness
    """
    if path is None:
        path = os.environ["EUPS_PATH"]
    if isinstance(path, str):
        path = path.split(":")

    userDataDir = utils.defaultUserDataDir()
    path.append(userDataDir)
    
    if not inUserDir:
        userDataDir = None              # Clear the system cache, not the one in userDataDir

    if isinstance(flavors, str):
        flavors = flavors.split()

    for p in path:
        dbpath = os.path.join(p, Eups.ups_db)

        persistDir = dbpath
        if p != userDataDir:            # no need to use a surrogate directory as we can write userDataDir
            persistDir = utils.userStackCacheFor(p, userDataDir)

        if not os.path.exists(persistDir):
            print("No cache yet for %s; skipping..." % p, file=utils.stdwarn)
            continue

        flavs = flavors
        if flavs is None:
            flavs = ProductStack.findCachedFlavors(persistDir)
        if not flavs:
            continue

        ProductStack.fromCache(dbpath, flavs, persistDir=persistDir,
                               autosave=False).clearCache(verbose=verbose)

def listCache(path=None, verbose=0, flavor=None):
    if path is None:
        path = os.environ["EUPS_PATH"]
    if isinstance(path, str):
        path = path.split(":")

    if not flavor:
        flavor = utils.determineFlavor()

    userDataDir = utils.defaultUserDataDir()
    if not userDataDir in path:
        path.append(userDataDir)
        
    for p in path:
        dbpath = os.path.join(p, Eups.ups_db)
        cache = ProductStack.fromCache(dbpath, flavor, updateCache=False, 
                                       autosave=False)

        productNames = cache.getProductNames()
        productNames.sort()

        colon = ""
        if verbose:
            colon = ":"

        print("%-30s (%-3d products) [cache verison %s]%s" % \
            (p, len(productNames), cacheVersion, colon))

        if not verbose:
            continue

        for productName in productNames:
            versionNames = cache.getVersions(productName)
            versionNames.sort(hooks.version_cmp)

            print("  %-20s %s" % (productName, " ".join(versionNames)))

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

def osetup(Eups, productName, version=None, fwd=True, setupType=[]):
    """
    Identical to setup() but with a deprecated signature.
    """
    return setup(productName, version, None, setupType, Eups, fwd)

def setup(productName, version=None, prefTags=None, productRoot=None, 
          eupsenv=None, fwd=True, tablefile=None, exact_version=False, postTags=[]):
    """
    Return a set of shell commands which, when sourced, will setup a product.  
    (If fwd is false, unset it up.)

    Note that if the first argument is found to be an instance of Eups,
    this function will assume that the old setup() signature is expected
    by the caller, and the parameters will be forwarded to osetup().

    @param productName     the name of the desired product to setup.  
    @param version         the desired version of the product.  This can be
                             either a string giving an explicit version
                             or a Tag instance.  
    @param prefTags        the list of requested tags (n.b. the VRO already knows about them)
    @param postTags        the list of requested post-tags (n.b. the VRO already knows about them)
    @param productRoot     the root directory where the product is installed.
                             If set, Eups will not consult its database for
                             the product's location, but rather set it up as
                             a "LOCAL" product.  
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
        return osetup(productName, version, prefTags, productRoot, productName.setupType)

    if not eupsenv:
        eupsenv = Eups(readCache=False, exact_version=exact_version)
        if version:
            eupsenv.selectVRO(versionName=version)

    if isinstance(prefTags, str):
        prefTags = prefTags.split()
    elif isinstance(prefTags, Tag):
        prefTags = [prefTags]

    if prefTags is None:
        prefTags = []
    if postTags is None:
        postTags = []

    if prefTags:
        checkTagsList(eupsenv, prefTags)
    if postTags:
        checkTagsList(eupsenv, postTags)

    versionRequested = version
    ok, version, reason = eupsenv.setup(productName, version, fwd,
                                        productRoot=productRoot, tablefile=tablefile)
        
    cmds = []
    if ok:
        #
        # Check that we got the desired tag
        #
        if eupsenv.quiet <= 0 and (prefTags or postTags) and not versionRequested:
            taggedVersion = None
            for tag in prefTags:
                taggedVersion = eupsenv.findTaggedProduct(productName, tag)
                if taggedVersion:
                    break
            if not taggedVersion:
                for tag in postTags:
                    taggedVersion = eupsenv.findTaggedProduct(productName, tag)
                    if taggedVersion:
                        break

            if taggedVersion:
                if version == taggedVersion.version: # OK, we got it
                    pass
                elif productRoot:       # they asked for a particular directory
                    pass
                else:
                    print("Requested version tagged %s == \"%s\"; got version \"%s\"" % \
                          (",".join(prefTags + postTags), taggedVersion.version, version), file=utils.stderr)
            else:
                if not re.search(r"^" + Product.LocalVersionPrefix, version):
                    if (fwd and eupsenv.verbose >= 0) or (not fwd and eupsenv.verbose > 0):
                        extra = ""
                        if os.path.isfile((prefTags + postTags)[0]):
                            extra = " in"

                        print("No versions of %s are tagged%s %s; setup version is %s" % \
                              (productName, extra, ",".join(prefTags + postTags), version), file=utils.stdwarn)

        #
        # Set new variables
        #
        for key, val in os.environ.items():
            try:
                if val == eupsenv.oldEnviron[key]:
                    continue
            except KeyError:
                pass

            if val and not re.search(r"^['\"].*['\"]$", val) and \
                   re.search(r"[\s<>|&;()]", val):   # quote characters that the shell cares about
                val = "'%s'" % val

            if eupsenv.shell in ("sh", "zsh",):
                cmd = "export %s=%s" % (key, val)
            elif eupsenv.shell in ("csh",):
                cmd = "setenv %s %s" % (key, val)

            if eupsenv.noaction:
                if eupsenv.verbose < 2 and re.search(utils.setupEnvPrefix(), key):
                    continue            # these variables are an implementation detail

                cmd = "echo \"%s\"" % cmd

            cmds += [cmd]
        #
        # Extra environment variables that EUPS uses
        #
        if not fwd and productName == "eups":
            for k in ("EUPS_PATH", "EUPS_PKGROOT", "EUPS_SHELL",):
                if k in os.environ:
                    del os.environ[k]
        #
        # unset ones that have disappeared
        #
        for key in eupsenv.oldEnviron.keys():
            if productName != "eups":   # the world will break if we delete these
                if re.search(r"^EUPS_(DIR|PATH|PKGROOT|SHELL)$", key):
                    continue

            if os.environ.has_key(key):
                continue

            if eupsenv.shell == "sh" or eupsenv.shell == "zsh":
                cmd = "unset %s" % (key)
            elif eupsenv.shell == "csh":
                cmd = "unsetenv %s" % (key)

            if eupsenv.noaction:
                if eupsenv.verbose < 2 and re.search(utils.setupEnvPrefix(), key):
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
                value = re.sub(r'"?\$@"?', r"\!*", value)
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
                cmd = "unalias %s" % (key)

            if eupsenv.noaction:
                cmd = "echo \"%s\"" % cmd

            cmds += [cmd]
    elif fwd and version is None:
        print("Unable to find an acceptable version of", productName, file=utils.stderr)
        if eupsenv.verbose and os.path.exists(productName):
            print("(Did you mean setup -r %s?)" % productName, file=utils.stderr)
        cmds += ["false"]               # as in /bin/false
    else:
        if fwd:
            versionName = version

            if eupsenv.isLegalRelativeVersion(versionName):
                versionName = ""

            if versionName:
                versionName = " " + versionName
        
            print("Failed to setup %s%s: %s" % (productName, versionName, reason), file=utils.stderr)
        else:
            print("Failed to unsetup %s: %s" % (productName, reason), file=utils.stderr)

        cmds += ["false"]               # as in /bin/false

    return cmds

def unsetup(productName, version=None, eupsenv=None):
    """ 
    Return a set of shell commands which, when sourced, will unsetup a product.
    This is equivalent to setup(productName, version, fwd=False). 
    """
    return setup(productName, version, fwd=False)

def findProduct(productName, versionName=None, eupsenv=None):
    """
    return the specified product.  None is returned if no matching product can be found
    @param productName   the name of the product of interest
    @param version       the desired version (default: current).  This can in one of the 
    following forms:
    *  an explicit version 
    *  a version expression (e.g. ">=3.3")
    *  a Tag instance 
    *  None, in which case, the (most) preferred 
    version will be returned.
    @param eupsenv       The Eups instance to use to find the product.  If 
    not provided, a default will created.  
    """
    if not eupsenv:
        eupsenv = Eups()

    if versionName is None:
        versionName = Tag("current")

    return eupsenv.findProduct(productName, versionName)

def productDir(productName=None, versionName=Tag("setup"), eupsenv=None):
    """
    return the installation directory (PRODUCT_DIR) for the specified 
    product.  None is returned if no matching product can be found
    @param productName   the name of the product of interest; if None return a dictionary of all productDirs
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
    if productName and versionName == Tag("setup"): # we can take a shortcut
        return os.environ.get(utils.dirEnvNameFor(productName))

    if not eupsenv:
        eupsenv = Eups()

    if not productName:
        tags = None
        if versionName == Tag("setup"):
            tags = versionName
            versionName = ""
            
        productList = eupsenv.findProducts(productName, versionName, tags)
        productDirs = {}
        for prod in productList:
            pdir = prod.dir
            if pdir == "none":
                pdir = None
            productDirs[prod.name] = pdir

        return productDirs

    prod = eupsenv.findProduct(productName, versionName)
    if not prod:
        return None

    pdir = prod.dir
    if pdir == "none":
        pdir = None
        
    return pdir

def getSetupVersion(productName, eupsenv=None):
    """
    return the version name for the currently setup version of a given product.

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

def enableLocking(enableLocking=True):
    """Enable or disable the use of lock files"""
    from . import lock
    lock.disableLocking = not enableLocking
    

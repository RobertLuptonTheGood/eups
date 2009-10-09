"""
the Repositories class -- a set of distribution servers from which 
distribution packages can be received and installed.
"""
import sys, os, re, atexit, shutil

import eups.utils as utils
import server
from eups           import Eups, Tag, Tags, TagNotRecognized
from eups           import ProductNotFound, EupsException
from Repository     import Repository 
from eups.utils     import Flavor, Quiet
from Distrib        import findInstallableRoot
from DistribFactory import DistribFactory
from server         import ServerConf, Manifest, ServerError

class Repositories(object):
    """
    A set of repositories to be to look for products to install.

    This class evolved from DistributionSet in previous versions.
    """

    def __init__(self, pkgroots, options=None, eupsenv=None,
                 installFlavor=None, distribClasses=None, override=None, 
                 verbosity=None, log=sys.stderr):
                 
        """
        @param pkgroots   the base URLs for the distribution repositories.  This
                            can either be a list or a pipe-delimited ("|") 
                            string.  
        @param options    a dictionary of named options that are used to fine-
                            tune the behavior of the repositories.  These are
                            passed onto the constructors for the underlying 
                            Reposistory classes.
        @param eupsenv    an instance of a Eups class containing the Eups
                            environment to assume
        @param installFlavor   the desired flavor any install requests
        @param distribClasses  a dictionary by name of the Distrib classes 
                            to support.  This will augmented by those specified
                            by a server.  
        @param override   a dictionary of server configuration parameters that
                            should override the configuration received from 
                            each server.  
        @param verbosity  if > 0, print status messages; the higher the 
                            number, the more messages that are printed
                            (default is the value of eupsenv.verbose).
        @param log        the destination for status messages (default:
                            sys.stderr)
        """
        if isinstance(pkgroots, str):
            pkgroots = map(lambda p: p.strip(), pkgroots.split("|"))
        if len(pkgroots) == 0:
            raise EupsException("No package servers to query; set -r or $EUPS_PKGROOT")

        # the Eups environment
        self.eups = eupsenv
        if not self.eups:
            self.eups = Eups()

        self.verbose = verbosity
        if self.verbose is None:
            self.verbose = self.eups.verbose
        self.log = log

        if not distribClasses:
            distribClasses = {}

        # the list of repository base URLs
        self.pkgroots = []

        # a lookup of Repository instances by its base URL
        self.repos = {}

        # the preferred installation flavor
        self.flavor = installFlavor
        if not self.flavor:
            self.flavor = self.eups.flavor

        df = DistribFactory(self.eups)
        for name in distribClasses.keys():
            # note: this will override the server's recommendation
            # if we want change this, use:
            #   if not df.supportsName(name):
            #       df.register(distribClasses[name], name)
            # 
            df.register(distribClasses[name], name)

        for pkgroot in pkgroots:
#            if pkgroot == None:
#                ds = None
#            else:
#                ds = ServerConf.makeServer(pkgroot, eupsenv=eupsenv, 
#                                           override=override,
#                                           verbosity=self.eups.verbose)
#
            try:
                dist = Repository(self.eups, pkgroot, options=options, 
                                  flavor=installFlavor, distFactory=df, 
                                  verbosity=self.eups.verbose)

                self.pkgroots += [pkgroot]
                self.repos[pkgroot] = dist

            except ImportError, e:
                if self.verbose >= 0:
                    print >> self.log, "Unable to use server:", pkgroot
                    print >> self.log, \
                        "  %s; Are you missing a plug-in for this server?" % e

        if len(self.pkgroots) == 0 and self.verbose >= 0:
            print >> self.log, "No usable package repositories loaded"

        # a cache of the union of tag names supported by the repositories
        self._supportedTags = None

        # used by install() to control repeated error messages
        self._msgs = {}

    def listPackages(self, productName=None, versionName=None, flavor=None):
        """Return a list of tuples (pkgroot, package-list)"""

        out = []
        for pkgroot in self.pkgroots:
            # Note: each repository may have a cached list
            repos = self.repos[pkgroot]
            try:
                pkgs = repos.listPackages(productName, versionName, flavor)
            except ServerError, e:
                if self.quiet <= 0:
                    print >> self.log, "Warning: Trouble contacting", pkgroot
                    print >> self.log, str(e)
                pkgs = []

            out.append( (pkgroot, pkgs) )

        return out

    def getTagNames(self):
        """
        return a unique list of tag names supported collectively from all 
        of the repositories.
        """
        if self._supportedTags is None:
           found = {}
           for pkgroot in self.repos.keys():
               tags = self.repos[pkgroot].getSupportedTags()
               for tag in tags:
                   found[tag] = 1
           self._supportedTags = found.keys()
           self._supportedTags.sort()

        return self._supportedTags

    def getRepos(self, pkgroot):
        """
        return the Repository for a given base URL.  A KeyError is raised
        if pkgroot is not among those passed to this Repositories constructor.
        """
        return self.respos[pkgroot]

    def findWritableRepos(self):
        """
        return the first repository in the set that new packages may be 
        deployed to.  None is returned if one is not found in EUPS_PKGROOT
        """
        # search in order
        for pkgroot in self.pkgroots:
            if self.repos[pkgroot].isWritable():
                return self.repos[pkgroot]

        return None

    def findPackage(self, product, version=None, prefFlavors=None):
        """
        return a tuple (product, version, flavor, pkgroot) reflecting an 
        exact version and source of a desired product.
        @param product     the name of the product
        @param version     the desired version.  This can either be a version
                             string or an instance of Tag.  If None, 
                             the tags preferred by the Eups environment will
                             be searched.  
        @param prefFlavors the preferred platform flavors in an ordered list.  
                             A single flavor may be given as a string.  If None, 
                             flavors preferred by the Eups environment will
                             be searched.  
        """
        if prefFlavors is None:
            prefFlavors = Flavor().getFallbackFlavors(self.flavor, True)
        elif not isinstance(prefFlavors, list):
            prefFlavors = [prefFlavors]
            
        versions = [version]
        if version and isinstance(version, Tag):
            if not version.isGlobal():
                raise TagNotRecognized(tag.name, "global", 
                                       msg="Non-global tag %s requested." % 
                                           version.name)
        if not version:
            versions = map(lambda t: Tag(t), self.eups.getPreferredTags())

        newest = None

        for vers in versions:
            for flav in prefFlavors:
                for pkgroot in self.pkgroots:
                    out = self.repos[pkgroot].findPackage(product, vers, flav)
                    if out:  
                        # Question: if tag is "newest", should it return the 
                        # newest from across all repositories, or just the 
                        # newest from the first one that has the right 
                        # product/flavor.  If the later, change "True" below
                        # to "False".  
                        if True and \
                           isinstance(vers, Tag) and vers.name == "newest" \
                           and (not newest or 
                                self.eups.version_cmp(newest[1], out[1]) > 0):
                            newest = (out[0], out[1], out[2], pkgroot) 
                        else:
                            return (out[0], out[1], out[2], pkgroot)

            if newest:
                # if we were searching for the newest and found at least one
                # acceptable version, don't bother looking for other tags
                break

        return newest

    def findReposFor(self, product, version=None, prefFlavors=None):
        """
        return a Repository that can provide a requested package.  None is
        return if the package is not found
        @param product     the name of the package providing a product
        @param version     the desired version of the product.  This can 
                             either be  a version string or an instance of 
                             Tag.  If None, the most preferred tagged version 
                             will be found.
        @param prefFlavors the ordered list of preferred flavors to choose 
                             from.  If None, the set is drawn from the eups 
                             environment.
        """
        pkg = self.findPackage(product, version, prefFlavors)
        if not pkg:
            return None

        return self.repos[pkg[3]]

    def findDistribFor(self, product, version=None, prefFlavors=None):
        """
        return a Repository that can provide a requested package.  None is
        return if the package is not found
        @param product     the name of the package providing a product
        @param version     the desired version of the product.  This can 
                             either be  a version string or an instance of 
                             Tag.  If None, the most preferred tagged version 
                             will be found.
        @param prefFlavors the ordered list of preferred flavors to choose 
                             from.  If None, the set is drawn from the eups 
                             environment.
        """
        pkg = self.findPackage(product, version, prefFlavors)
        if not pkg:
            return None

        return None

    def install(self, product, version=None, updateTags=True, alsoTag=None,
                nodepend=False, noclean=False, noeups=False, options=None, 
                manifest=None, searchDep=None):
        """
        Install a product and all its dependencies.
        @param product     the name of the product to install
        @param version     the desired version of the product.  This can either 
                            be a version string or an instance of Tag.  If 
                            not provided (or None) the most preferred version 
                            will be installed.  
        @param updateTags  when True (default), server-assigned tags will 
                            be updated for this product and all its dependcies
                            to match those recommended on the server (even if
                            a product is already installed); if False, tags 
                            will not be changed.
        @param alsoTag     A list of tags to assign to all installed products
                            (in addition to server tags).  This can either be
                            a space-delimited list, a list of string names,
                            a Tag instance, or a list of Tag instances.
        @param nodepend    if True, the product dependencies will not be 
                            installed
        @param noclean     If False (default), the build directory will get
                            cleaned up after a successful install.  A True
                            value prevents this.
        @param noeups      if False (default), needed products that are already
                            installed will be skipped over.  If True, an 
                            attempt is made to install them anyway.  This 
                            allows a product to be installed in the target
                            install stack even if it is available in another
                            stack managed by EUPS.  Note, however, that if a
                            needed product is already installed into the target
                            stack, the installation may fail.  Use with caution.
        @param options     a dictionary of named options that are used to fine-
                            tune the behavior of this Distrib class.  See 
                            discussion above for a description of the options
                            supported by this implementation; sub-classes may
                            support different ones.
        @param manifest    use this manifest (a local file) as the manifest for 
                            the requested product instead of downloading manifest
                            from the server.
        @param searchDep   if False, install will be prevented from recursively
                            looking for dependencies of dependencies listed in
                            manifests.  In this case, it is assumed that a 
                            manifest contains all necessary dependencies.  If 
                            True, the distribution identifiers in the manifest
                            file are ignored and the dependencies will always
                            be recursively searched for.  If None,
                            the choice to recurse is left up to the server 
                            where the manifest comes from (which usually 
                            defaults to False).
        """
        if alsoTag is not None:
            if isinstance(alsoTag, str):
                alsoTag = map(lambda t: Tag(t, Tags.user), alsoTag.split())
            elif isinstance(alsoTag, Tag):
                alsoTag = [alsoTag]

        pkg = self.findPackage(product, version)
        if not pkg:
            raise ProductNotFound(product, version,
                    msg="Product %s %s not found in any package repository" % 
                        (product, version))

        (product, version, flavor, pkgroot) = pkg
#        opts = self._mergeOptions(options)
#        productRoot = utils.findWritableDb(self.eups.path)
        productRoot = self.getInstallRoot()
        if productRoot is None:
            raise EupsException("Unable to find writable place to install in EUPS_PATH")

        if manifest is not None:
            if not manifest or os.path.exists(manifest):
                raise EupsException("%s: user-provided manifest not found" %
                                    manifest)
            man = Manifest.fromFile(manifest, self.eups, 
                                    verbosity=self.eups.verbose-1)
        else:
            man = self.repos[pkgroot].getManifest(product, version, flavor)

        self._msgs = {}
        self._recursiveInstall(0, man, product, version, flavor, pkgroot, 
                               productRoot, updateTags, alsoTag, options, 
                               nodepend, noclean, noeups)
        
    def _recursiveInstall(self, recursionLevel, manifest, product, version, 
                          flavor, pkgroot, productRoot, updateTags=False, 
                          alsoTag=None, opts=None, nodepend=False, 
                          noclean=False, noeups=False, searchDep=None, 
                          setups=None, installed=None, tag=None, ances=None):
                          
        if installed is None:
            installed = []
        if ances is None:
            ances = []
        if setups is None:
            setups = []
        instflavor = flavor
        if instflavor == "generic":
            instflavor = self.eups.flavor

        if alsoTag is None:
            alsoTag = []

        # a function for creating an id string for a product
        prodid = lambda p, v, f: " %s %s for %s" % (p, v, f)
        
        idstring = prodid(manifest.product, manifest.version, flavor)

        if nodepend and self.verbose > 0:
            print >> self.log, \
                "Skipping dependencies for %s %s" % (product, version)

        products = manifest.getProducts()
        if self.verbose >= 0 and len(products) == 0:
            print >> self.log, "Warning: no installable packages associated", \
                "with", idstring

        for prod in products:
            pver = prodid(prod.product, prod.version, instflavor)

            # check for circular dependencies:
            if pver in ances:
                if self.verbose >= 0:
                    print >> self.log, "Detected circular dependencies", \
                        "within manifest for %s; short-circuiting." %  \
                        idstring 
                    if self.verbose > 2:
                        print >> self.log, "Package installation already",\
                            "in progress:"
                        for a in ances:
                            print >> self.log, "\t", a
                    continue
            ances.append(pver)

            if nodepend and prod.product != product and prod.version != version:
                continue

            if pver in installed:
                # we've installed this via the current install() call
                continue

            thisinstalled = None
            if not noeups:
                thisinstalled = self.eups.findProduct(prod.product, 
                                                      prod.version, 
                                                      flavor=instflavor)
            if thisinstalled:
                if self.verbose >= 0:
                    print >> self.log, \
                        "Required product %s %s is already installed" % \
                        (prod.product, prod.version)

            else:

                recurse = searchDep
                if recurse is None:  
                    recurse = not prod.distId or prod.shouldRecurse
                if recurse and \
                   prod.product != product and prod.version != version:

                    # This is not the top-level product for the current manifest.
                    # We are ignoring the distrib ID; instead we will search 
                    # for the required dependency in the repositories
                    pkg = self.findPackage(prod.product, prod.version, 
                                           prod.flavor)
                    if pkg:
                        dman = self.repos[pkg[3]].getManifest(pkg[0], pkg[1], 
                                                              pkg[2])

                        thisinstalled = \
                            self._recursiveInstall(recursionLevel+1, dman, 
                                                   prod.product, prod.version, 
                                                   prod.flavor, pkg[3], 
                                                   productRoot, updateTags, 
                                                   alsoTag, opts, norecurse, 
                                                   noclean, noeups, setups, 
                                                   installed, tag, ances)
                        if not thisinstalled and self.verbose > 0:
                            print >> self.log, \
                                "Warning: recursive install failed for", \
                                prod.product, prod.version

                    elif not prod.distId:
                        raise ServerError("Can't find a package for %s %s (%s)"
                                    % (prod.product, prod.version, prod.flavor))

                if not thisinstalled:
                    self._doInstall(pkgroot, prod, productRoot, 
                                    instflavor, opts, noclean, setups, tag)

            # Whether or not we just installed the product, we need to...
            # ...add the product to the setups 
            setups.append("setup --keep %s %s" % (prod.product, prod.version))

            # ...update the tags
            if updateTags:
                self._updateServerTags(pkgroot, prod, productRoot)
            if alsoTag:
                for tag in alsoTag:
                    try:
                        self.eups.assignTag(tag, prod.product, prod.version,
                                            productRoot)
                    except Exception, e:
                        msg = str(e)
                        if not self._msgs.has_key(msg):
                            print >> self.log, msg
                        self._msgs[msg] = 1

            # ...note that this package is now installed
            installed.append(pver)

        return True

    def _doInstall(self, pkgroot, prod, productRoot, instflavor, opts, 
                   noclean, setups, tag):

        if prod.instDir:
            installdir = prod.instDir
            if not os.path.isabs(installdir):
                installdir = os.path.join(productRoot, installdir)
            if os.path.exists(installdir):
                print >> self.log, \
                    "WARNING: Target installation directory exists:", installdir
                print >> self.log, "        Was --noeups used?  If so and", \
                    "the installation fails,"
                print >> self.log, \
                    '         try "eups distrib clean', prod.product, \
                    prod.version, '" before retrying installation."' 

        builddir = self.makeBuildDirFor(productRoot, prod.product,
                                        prod.version, opts, instflavor)

        # write the distID to the build directory to aid 
        # clean-up if it fails
        self._recordDistID(prod.distId, builddir, pkgroot)

        distrib = self.repos[pkgroot].getDistribFor(prod.distId, opts, 
                                                    instflavor, tag)

        if self.verbose > 1 and 'NAME' in dir(distrib):
            print >> self.log, "Using Distrib type:", distrib.NAME

        try:
            distrib.installPackage(distrib.parseDistID(prod.distId), 
                                   prod.product, prod.version,
                                   productRoot, prod.instDir, setups,
                                   builddir)
        except server.RemoteFileNotFound, e:
            if self.verbose >= 0:
                print >> self.log, "Failed to install %s %s: %s" % \
                    (prod.product, prod.version, str(e))
            raise e
        except RuntimeError, e:
            raise e

        if self.verbose >= 0:
            print >> self.log, \
                "Package %s %s installed successfully" % \
                (prod.product, prod.version)

        # declare the newly installed package, if necessary
        root = os.path.join(productRoot, instflavor, prod.instDir)

        try:
            self._ensureDeclare(pkgroot, prod, instflavor, root, productRoot)
                                
        except RuntimeError, e:
            print >> sys.stderr, e
            return
        
        # write the distID to the installdir/ups directory to aid 
        # clean-up
        self._recordDistID(prod.distId, root, pkgroot)

        # clean up the build directory
        if noclean:
            if self.verbose:
                print >> sys.stderr, "Not removing the build directory %s; you can cleanup manually with \"eups distrib clean\"" % (self.getBuildDirFor(self.getInstallRoot(), prod.product, prod.version, opts))
        else:
            self.clean(prod.product, prod.version, options=opts)

    def _updateServerTags(self, pkgroot, prod, productRoot):

        tags = self.repos[pkgroot].getTagNamesFor(prod.product, prod.version,
                                                  prod.flavor)
        self.eups.supportServerTags(tags, pkgroot)
        for tag in tags:
            try:
                self.eups.assignTag(tag, prod.product, prod.version, productRoot)
            except TagNotRecognized, e:
                msg = str(e)
                if not self._msgs.has_key(msg):
                    print >> self.log, msg
                self._msgs[msg] = 1

    def _recordDistID(self, pkgroot, distId, installDir):
        ups = os.path.join(installDir, "ups")
        file = os.path.join(ups, "distID.txt")
        if os.path.isdir(ups):
            try:
                fd = open(file, 'w')
                try:
                    print >> fd, distId
                    print >> fd, pkgroot
                finally:
                    fd.close()
            except:
                if self.verbose >= 0:
                    print >> self.log, "Warning: Failed to write distID to %s: %s" (file, traceback.format_exc(0))

    def _readDistIDFile(self, file):
        distId = None
        pkgroot = None
        idf = open(file)
        try:
          try:
            while line in idf:
                line = line.strip()
                if len(line) > 0:
                    if not distId:
                        distId = line
                    elif not pkgroot:
                        pkgroot = line
                    else:
                        break
          finally:
            idf.close()
        except Exception, e:
            if self.verbose >= 0:
                print >> self.log, "Warning: trouble reading %s, skipping" % file

        return (distId, pkgroot)
            
    def _ensureDeclare(self, pkgroot, mprod, flavor, rootdir, productRoot):
        
        flavor = self.eups.flavor

        prod = self.eups.findProduct(mprod.product, mprod.version, flavor=flavor)
        if prod:
            return

        repos = self.repos[pkgroot]

        if rootdir and not os.path.exists(rootdir):
            msg = "%s %s installation not found at %s" % \
                (mprod.product, mprod.version, rootdir)
            raise RuntimeError(msg)

        # make sure we have a table file if we need it
        upsdir = os.path.join(rootdir, "ups")
        tablefile = os.path.join(upsdir, "%s.table" % mprod.product)

        if not os.path.exists(tablefile):
            if mprod.tablefile == "none":
                tablefile = None
            else:
                # retrieve the table file and install it
                if rootdir == "/dev/null":
                    tablefile = \
                        repos.distServer.getFileForProduct(mprod.tablefile, 
                                                           mprod.product, 
                                                           mprod.version, 
                                                           flavor)
                    tablefile = open(tablefile, "r")
                else:
                    if not os.path.exists(upsdir):
                        os.makedirs(upsdir)
                    repos.distServer.getFileForProduct(tablefile, product, 
                                                       version, flavor,
                                                       filename=tablefile)
                if not os.path.exists(tablefile):
                    raise EupsException("Failed to find table file %s" % tablefile)

        self.eups.declare(mprod.product, mprod.version, rootdir, 
                          eupsPathDir=productRoot, tablefile=tablefile)

    def getInstallRoot(self):
        """return the first directory in the eups path that the user can install 
        stuff into
        """
        return findInstallableRoot(self.eups)

    def getBuildDirFor(self, productRoot, product, version, options=None, 
                       flavor=None):
        """return a recommended directory to use to build a given product.
        In this implementation, the returned path will usually be of the form
        <productRoot>/<buildDir>/<flavor>/<product>-<root> where buildDir is, 
        by default, "EupsBuildDir".  buildDir can be overridden at construction
        time by passing a "buildDir" option.  If the value of this option
        is an absolute path, then the returned path will be of the form
        <buildDir>/<flavor>/<product>-<root>.

        @param productRoot    the root directory where products are installed
        @param product        the name of the product being built
        @param version        the product's version 
        @param flavor         the product flavor.  If None, assume the current 
                                default flavor
        """
        buildRoot = "EupsBuildDir"
        if options and options.has_key('buildDir'):  
            buildRoot = self.options['buildDir']
        if not flavor:  flavor = self.eups.flavor

        pdir = "%s-%s" % (product, version)
        if os.path.isabs(buildRoot):
            return os.path.join(buildRoot, flavor, pdir)
        return os.path.join(productRoot, buildRoot, flavor, pdir)

    def makeBuildDirFor(self, productRoot, product, version, options=None, 
                        flavor=None):
        """create a directory for building the given product.  This calls
        getBuildDirFor(), ensures that the directory exists, and returns 
        the path.  
        @param productRoot    the root directory where products are installed
        @param product        the name of the product being built
        @param version        the product's version 
        @param flavor         the product flavor.  If None, assume the current 
                                default flavor
        @exception OSError  if the directory creation fails
        """
        dir = self.getBuildDirFor(productRoot, product, version, options, flavor)
        if not os.path.exists(dir):
            os.makedirs(dir)
        return dir

    def cleanBuildDirFor(self, productRoot, product, version, options=None,
                         force=False, flavor=None):
        """Clean out the build directory used to build a product.  This 
        implementation calls getBuildDirFor() to get the full path of the 
        directory used; then, if it exists, the directory is removed.  As 
        precaution, this implementation will only remove the directory if
        it appears to be below the product root, unless force=True.

        @param productRoot    the root directory where products are installed
        @param product        the name of the built product
        @param version        the product's version 
        @param force          override the removal restrictions
        @param flavor         the product flavor.  If None, assume the current 
                                default flavor
        """
        dir = self.getBuildDirFor(productRoot, product, version, options, flavor)
        if os.path.exists(dir):
            if force or (len(productRoot) > 0 and dir.startswith(productRoot) 
                         and len(dir) > len(productRoot)+1):
                if self.verbose > 1: 
                    print >> self.log, "removing", dir
                server.system("rm -rf " + dir,
                                  verbosity=self.verbose-1, log=self.log)
            elif self.verbose > 0:
                print >> self.log, "%s: not under root (%s); won't delete unless forced (use --force)" % (dir, productRoot)


    def clean(self, product, version, flavor=None, options=None, 
              installDir=None, uninstall=False):
        """clean up the remaining remants of the failed installation of 
        a distribution.  
        @param product      the name of the product to clean up after
        @param version      the version of the product
        @param flavor       the flavor for the product to assume.  This affects
                               where we look for partially installed packages.
                               None (the default) means the default flavor.
        @param options      extra options for fine-tuning the distrib-specific
                               cleaning as a dictionary
        @param installDir   the directory where the product should be installed
                               If None, a default location based on the above
                               parameters will be assumed.
        @parma uninstall    if True, run the equivalent of "eups remove" for 
                               this package. default: False.
        """
        handlePartialInstalls = True
        productRoot = self.getInstallRoot()
        if not flavor:  flavor = self.eups.flavor

        # check the build directory
        buildDir = self.getBuildDirFor(productRoot, product, version, 
                                       options, flavor)
        if self.verbose > 0:
            print >> self.log, "Looking for build directory:", buildDir

        if os.path.exists(buildDir):
            distidfile = os.path.join(buildDir, "distID.txt")
            if os.path.isfile(distidfile):
                (distId, pkgroot) = self._readDistIDFile(distidfile)
                if distId and pkgroot:
                    if self.verbose > 1:
                        print >> self.log, "Attempting distClean for", \
                            "build directory via ", distId
                    self.distribClean(product, version, pkgroot, distId, flavor)

            self.cleanBuildDirFor(productRoot, product, version, options, 
                                  flavor=flavor)

        # now look for a partially installed (but not yet eups-declared) package
        if handlePartialInstalls:
            if not installDir:
                installDir = os.path.join(productRoot, flavor, product, version)

            if self.verbose > 1:
                print >> self.log, "Looking for a partially installed package:",\
                    product, version

            if os.path.isdir(installDir):
                distidfile = os.path.join(installDir, "ups", "distID.txt")
                if os.path.isfile(distidfile):
                    (pkgroot, distId) = self._readDistIDFile(distidfile)
                    if distId:
                        if self.verbose > 1:
                            print >> self.log, "Attempting distClean for", \
                                "installation directory via ", distId
                        self.distribClean(product,version,pkgroot,distId,flavor)
                
                # make sure this directory is not declared for any product
                installDirs = map(lambda x: x.dir, self.eups.findProducts())
                if installDir not in installDirs:
                  if not installDir.startswith(productRoot) and \
                     not self.eups.force:
                      if self.verbose >= 0:
                          print >> self.log, "Too scared to delete product dir",\
                              "that's not under the product root:", installDir

                  else:
                    if self.verbose > 0:
                        print >> self.log, "Removing installation dir:", \
                            installDir[0]
                    server.system("/bin/rm -rf %s" % installDir)
                        
        # now see what's been installed
        if uninstall and flavor == self.eups.flavor:
            info = None
            distidfile = None
            info = self.eups.findProduct(product, version)
            if info:
                # clean up anything associated with the successfully 
                # installed package
                distidfile = os.path.join(info.dir, "ups", "distID.txt")
                if os.path.isfile(distidfile):
                    distId = self._readDistIDFile(distidfile)
                    if distId:
                        self.distribClean(product,version,pkgroot,distId,flavor)

                # now remove the package
                if self.verbose >= 0:
                    print >> self.log, "Uninstalling", product, version
                self.eups.remove(product, version, False)


    def distribClean(self, product, version, pkgroot, distId, flavor=None, 
                     options=None):
        """attempt to do a distrib-specific clean-up based on a distribID.
        @param product      the name of the product to clean up after
        @param version      the version of the product
        @param flavor       the flavor for the product to assume.  This affects
                               where we look for partially installed packages.
                               None (the default) means the default flavor.
        @param distId       the distribution ID used to install the package.
        @param options      extra options for fine-tuning the distrib-specific
                               cleaning as a dictionary
        """
        repos = self.repos[pkgroot]
        distrib = repos.createDistribFor(distId, options, flavor)
        location = distrib.parseDistID(distId)
        productRoot = self.getInstallRoot()
        return distrib.cleanPackage(product, version, productRoot, location)


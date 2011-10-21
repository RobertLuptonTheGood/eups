#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import sys, os, re, atexit, shutil
import eups
import server
from server import RemoteFileNotFound, Manifest, TaggedProductList
from eups.VersionParser import VersionParser

class Distrib(object):
    """A class to encapsulate product distribution

    This class is an abstract base class with some default implementation.
    Subclasses will provide an implementation for specific ways to install
    packages or create distributable packages that can be installed by others.  
    A DistribServer instance, passed in via the constructor, controls how a 
    user pulls packages and related information from a distribution server.  
    A Distrib class understands how to unpack and/or build a package and 
    install into the user's software stack; this may include assumptions of 
    conventions of where to put things (though usually that information is 
    brought down from the server).  A Distrib class also understands how to 
    create a server that provides these packages to users: it understands not
    only how to create the necessary files but also how to organize them on 
    the server.  

    An instance of implemented Distrib class is usually accomplished via a 
    DistribFactory, using either createDistrib() (when installing a package) 
    or createDistribByName() (when creating a package).  During package 
    installation, the Distrib class pulls down distribution files from a 
    (usually remote) server using a DistribServer instance (provided when 
    creating the DistribFactory instance).  With package creation, the 
    Distrib class creates the distribution files based on a locally installed 
    version and deploys them into a *local* server directory tree.  Thus a 
    Distrib class can (in principle) be used to replicate an entire server 
    locally.  By using different Distrib class on installation and creation, 
    one can convert a server from one convention to another.  Similarly, one
    can create a distribution of server with a mix of distribution types to,
    for example, provide both generic, build-from-source packages and 
    flavor-spcific, binary alternatives.

    Sub-class implementations must override the value of the static string 
    variable, NAME, which is used as its default name (for look-ups via 
    DistribFactory.createDistribByName()).  They should also provide 
    implementations (at a minimum) for the following unimplemented functions:
       createPackage()
       packageCreated()
       getDistIdForPackage()
       installPackage()
       getTaggedRelease()
       writeTaggedRelease()
       createDependencies()
       updateDependencies()
       writeManifest()

    The DefaultDistrib subclass provides default implementations for the 
    last four functions.

    OPTIONS:
    The behavior of a Distrib class is fine-tuned via options (a dictionary
    of named values) that are passed in at construction time.  This base
    implementation supports a core set; sub-classes usually support them as 
    well but are not required to.  A sub-class may support additional options
    as well.  The core set supported here are:
       noeups           do not use the local EUPS database for information  
                          while creating packages.       
       obeyGroups       If true, then any newly written directory or files 
                          will be set to groupWritable.
       groupowner       when obeyGroups is true, change the group owner of 
                          to this value
       buildDir         a directory that may be used to build a package 
                          during install.  If this is a relative path, it 
                          the full path (by default) will be relative to 
                          the product root for the installation.  (See
                          getBuildDirFor()).
       useFlavor        Create a flavor-specific installation (i.e. not "generic")
    """

    NAME = None                         # sub-classes should provide a string value
    PRUNE = False                       # True if manifests are complete, and there's no need for recursion
                                        # to find all the needed products

    def __init__(self, Eups, distServ, flavor=None, tag="current", options=None,
                 verbosity=0, log=sys.stderr):
        """create a Distrib instance.  
        
        A DistribServer instance (provided as distServ) is usually created
        by calling 'eups.server.ServerConf.makeServer(packageBase)' where 
        packageBase the base URL for the server.

        @param Eups       the Eups controller instance to use
        @param distServ   the DistribServer object associated with the server
        @param flavor     the default platform type to assume when necessary.
                             If None, it will be set to Eups.flavor
        @param tag        the logical name of the release of packages to assume
                            (default: "current")
        @param options    a dictionary of named options that are used to fine-
                            tune the behavior of this Distrib class.  See 
                            discussion above for a description of the options
                            supported by this implementation; sub-classes may
                            support different ones.
        """
        self.distServer = distServ
        self.Eups = Eups
        self.flavor = flavor
        self.tag = tag
        self.verbose = verbosity
        self.log = log

        if not self.flavor:
            self.flavor = self.Eups.flavor

        if options is None:  options = {}
        self.options = options
        if not isinstance(self.options, dict):
            raise RuntimeError("Non-dictionary passed to options parameter: " +
                               repr(self.options))

        self.noeups = self.getOption("noeups", False)
        if self.noeups in (False, "False", "false"):
            self.noeups = False
        elif self.noeups in (True, "True", "true"):
            self.noeups = True
        else:
            raise RuntimeError("Unrecognised value of noeups: %s" % self.noeups)

        self.buildDir = self.getOption('buildDir', 'EupsBuildDir')

    # @staticmethod   # requires python 2.4
    def parseDistID(distID):
        """Return a valid package location if and only we recognize the 
        given distribution identifier

        This implementation always returns None
        """
        return None

    parseDistID = staticmethod(parseDistID)  # should work as of python 2.2

    def checkInit(self, forserver=True):
        """Check that self is properly initialised; this matters for subclasses 
        with special needs"""
        return True

    def initServerTree(self, serverDir):
        """initialize the given directory to serve as a package distribution
        tree.
        @param serverDir    the directory to initialize
        """
        if not os.path.exists(serverDir):
            os.makedirs(serverDir)

    def createPackage(self, serverDir, product, version, flavor=None, overwrite=False,
                      letterVersion=None):
        """Write a package distribution into server directory tree and 
        return the distribution ID.  If a package is made up of several files,
        all of them (except for the manifest) should be deployed by this 
        function.  This includes the table file if it is not incorporated
        another file.  
        @param serverDir      a local directory representing the root of the 
                                  package distribution tree
        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation.  None means
                                that a non-flavor-specific package is preferred, 
                                if supported.
        @param overwrite      if True, this package will overwrite any 
                                previously existing distribution files even if Eups.force is false
        @param letterVersion The name for the desired "letter version"; a rebuild
                                 with following an ABI change in a dependency
        """
        self.unimplemented("createPackage");

    def getDistIdForPackage(self, product, version, flavor=None):
        """return the distribution ID that for a package distribution created
        by this Distrib class (via createPackage())
        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation.  None means
                                that a non-flavor-specific ID is preferred, 
                                if supported.
        """
        self.unimplemented("getDistIdForPackage");

    def packageCreated(self, serverDir, product, version, flavor=None):
        """return True if a distribution package for a given product has 
        apparently been deployed into the given server directory.  
        @param serverDir      a local directory representing the root of the 
                                  package distribution tree
        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation.  None means
                                that the status of a non-flavor-specific package
                                is of interest, if supported.
        """
        self.unimplemented("packageCreated")

    def installPackage(self, location, product, version, productRoot, 
                       installDir=None, setups=None, buildDir=None):
        """Install a package with a given server location into a given
        product directory tree.
        @param location     the location of the package on the server.  This 
                               value is a distribution ID (distID) that has
                               been stripped of its build type prefix.
        @param product      the name of the product installed by the package.
                               An implementation may ignore this parameter,
                               allowing the package to completely control
                               what is being installed.  
        @param version      the name of the product version.  Like the product
                               parameter, an implementatoin may ignore this 
                               parameter.
        @param productRoot  the product directory tree under which the 
                               product should be installed
        @param installDir   the preferred sub-directory under the productRoot
                               to install the directory.  This value, which 
                               should be a relative path name, may be
                               ignored or over-ridden by the implementation.
                               Implementations should be prepared that this 
                               might be set to None or "none".
        @param setups       a list of EUPS setup commands that should be run
                               to properly build this package.  This may be
                               ignored by the package.  
        @param buildDir     a directory to use as a temporary building space.
                               An implementation should attempt to create this
                               directory if it needs to.  Upon successful 
                               completion, it may clean up the contents of 
                               this directory, but it should not remove it.  
                               If None (default), use the value of the 
                               'buildDir' option.
        """
        self.unimplemented("installPackage");

    def cleanPackage(self, product, version, productRoot, location):
        """remove any distribution-specific remnants of a package installation.
        Some distrib mechanisms (namely, Pacman) maintain some of their own 
        state about installed package that may need to get cleaned up if the 
        installation fails.  Note, however, it is assumed okay to clean a 
        package once it has been declared to the EUPS system.  

        This implementation does nothing but return False.  Subclasses should 
        override method if additional state is maintained.  If an error 
        occurs, the appropriate exception should be raised.  

        @param product      the name of the product to clean up after
        @param version      the version of the product
        @param productRoot  the product directory tree under which the 
                               product is assumed to be installed
        @param location      the distribution location used to install the
                               package.  The implementation may ignore this.
        @returns bool    True, if any state was cleaned up or False if nothing
                             needed to be done.  Note that False is not an 
                             error.  
        """
        return False
        

    def createTaggedRelease(self, top_product, top_version, flavor=None,
                            tag=None):
        """create a list of products to include in a tagged release based on 
        what is considered current (or more precisely, what is associated with
        the given tag name) in the local EUPS database and return it as a 
        TaggedProductList instance.  

        In this implementation, a list of dependencies for a top product is 
        generated; then each product dependency is recursively analyzed for 
        its dependencies.  
        @param  top_product    the product that determines via its dependencies
                                 which products are included.
        @param  top_version    the version of the top product.
        @param  flavor         the target platform for the release (default: 
                                 "generic")
        """
        release = TaggedProductList(tag, flavor, self.verbose-1, sys.log)
        self._recurseProdDeps(release, top_product, top_version, flavor)


    def _recurseProdDeps(self, release, product, version, flavor):
                         
        dependencies = self.createDependencies(product, version, flavor)
                                               
        for dep in dependencies:
            prevVer = release.getProductVersion()
            if prevVer is None or \
                    VersionParser("%s < %s" % (prevVer, dep.version)).eval():
                release.addProduct(dep.product, dep.version, flavor)

                self._recurseProdDeps(release, dep.product, dep.version, flavor)

    def getTaggedRelease(self, serverDir, tag, flavor=None):
        """get the collection of products that make up a tagged release and 
        return it as a TaggedProductList instance.  If such a release has not
        yet been created/written, return None.  This is used for creating a 
        server (i.e. it does not contact a remote host for this info).
        @param tag        the name of the tagged release of interest
        @param flavor         the target flavor for this release.  An 
                                  implementation may ignore this variable.  
        """
        self.unimplemented("getTaggedReleasePath")

    def writeTaggedRelease(self, serverDir, tag, products, flavor=None, 
                           force=False):
        """write a given tagged release into a server distribution tree
        @param serverDir      a local directory representing the root of the 
                                  package distribution tree
        @param tag            the name to give to the release
        @param products       a TaggedProductList instance containing the list
                                  of products in the release
        @param flavor         the target flavor for this release.  An 
                                  implementation may ignore this variable.  
        @param force          if False, don't over-write file if it already
                                  exists
        """
        self.unimplemented("writeTaggedReleasePath")

    def createDependencies(self, product, version, flavor=None, tag=None, 
                           recursive=False):
        """create a list of product dependencies based on what is known from 
        the system.

        This implementation will look up the product in the EUPS database and 
        analyze its table file.  

        A typical full implementation of this function in a sub-class would 
        call _createDeps() to get the initial list of dependencies, but then 
        iterate through the products, adding the name of the table file and
        the distId.

        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation
        @param tag            where a dependency is loose, prefer the version
                                that is part of this tagged release.  This 
                                may be ignored by the implementation
        @param recursive      if False, this list will only contain the direct
                                dependencies of this product; otherwise, it 
                                will include the dependencies of the dependencies
                                recursively.  Default: False
        """
        self.unimplemented("createDependencies")

    def updateDependencies(self, productList, flavor=None):
        """fill in information in the list of product dependencies based
        on what is known from the system

        A typical full implementation of this function in a sub-class would
        iterate through the products, adding the name of the table file and
        the distId.

        @param productList     list of products (output from createDependencies)
        @param flavor          the flavor of the target platform; this may 
                                 be ignored by the implentation
        """
        self.unimplemented("updateDependencies")        

    def _createDeps(self, productName, versionName, flavor=None, tag=None, 
                    recursive=False, exact=False, letterVersions={}):
        """return a list of product dependencies for a given project.  This 
        function returns a proto-dependency list providing only as much 
        generic information as is possible without knowing the details of 
        how the data is organized on the server.  Thus, the dependency list
        will not include 
        """
        if flavor is None:  flavor = self.flavor
        if tag is None:  tag = self.tag
        #
        # We may need a letter version of this product;  let's check
        #
        versionName, letterVersion, repoVersionName = \
                     letterVersions.get(productName, (versionName, versionName, versionName))
        productList = Manifest(productName, letterVersion, self.Eups, self.verbose-1,
                               letterVersion=letterVersion, log=self.log)

        # add a record for the top product
        productList.addDependency(productName, versionName, flavor, None, None, None, False,
                                  letterVersion=letterVersion)

        dependencies = None
        ptablefile = None
        if self.noeups:
            if recursive and self.verbose > 0:
                print >> self.log, "Warning dependencies are not guaranteed", \
                    "to be recursive when using noeups option"

            # use the server as source of package information
            ptablefile = self.findTableFile(productName, versionName, self.flavor)
            if not ptablefile and self.distServer:
                try:
                    ptablefile = self.distServer.getTableFile(productName, versionName, self.flavor)
                except RemoteFileNotFound, e:
                    pass

            if ptablefile:
                dependencies = self.Eups.dependencies_from_table(ptablefile)
            else:
                if self.verbose > 0:
                    print >> self.log, "Failed to find %s's table file; trying eups" % productName

        if ptablefile is None:
            # consult the EUPS database
            try:
                productDictionary = {}
                product = self.Eups.getProduct(productName, versionName)
                dependencies = self.Eups.getDependentProducts(product, productDictionary=productDictionary,
                                                              topological=True)
            except (eups.ProductNotFound, eups.TableFileNotFound), e:
                if self.noeups:
                    if self.noeups and self.verbose > 0:
                        print >> self.log, e
                    dependencies = []
                else:
                    raise
        #
        # Still no luck? If noeups we'll proceed without a tablefile
        #
        if self.noeups and dependencies is None:
            if self.verbose > 0:
                print >> self.log, "Unable to find a table file for %s; assuming no dependencies" % productName

            dependencies = self.Eups.dependencies_from_table("none")
        #
        # We have our dependencies; proceed
        #
        # The first thing to do is to ensure that more deeply nested products are listed first as we need to
        # build them first when installing
        #
        def byDepth(a, b):
            """Sort by recursion depth"""
            return cmp(b[2], a[2])
        dependencies.sort(byDepth)

        for (dprod, dopt, recursionDepth) in dependencies:
            dproductName = dprod.name
            dversionName = dprod.version

            product, vroReason = self.Eups.findProductFromVRO(dproductName, dversionName)

            if product:
                versionName = product.version
            else:
                if dopt:
                    continue
                raise eups.ProductNotFound(dproductName, dversionName)

            versionName, letterVersion, repoVersionName = \
                         letterVersions.get(dproductName, (versionName, versionName, versionName))

            productList.addDependency(dproductName, versionName, flavor, None, None, None, dopt,
                                      letterVersion=letterVersion, repoVersion=repoVersionName)

        #
        # We need to install those products in the correct order
        #
        productList.roll()              # we put the top-level product at the start of the list

        # now let's go back and fill in the product directory
        for dprod in productList.getProducts():
            if self.noeups and productName == dprod.product:
                basedir, dprod.instDir = None, "/dev/null"
            else:
                (basedir, instDir) = self.getProductInstDir(dprod.product, dprod.version, dprod.flavor)

            if dprod.version != dprod.letterVersion:
                dprod.instDir = instDir.replace(dprod.version, dprod.letterVersion)

        return productList

    def getProductInstDir(self, product, version, flavor):
        """return the directory where a product is installed split into 
        its base directory and its product directory (name/version).
        """
        productDir = "/dev/null"
        baseDir = ""
        try:
            pinfo = self.Eups.getProduct(product, version)
            if not pinfo.dir: 
                pinfo.dir = "none"   # the product directory
        except eups.ProductNotFound, e:
            if not self.noeups or self.Eups.verbose:
                print >> self.log, \
                      "WARNING: Failed to lookup directory for product %s %s (%s): %s" % \
                      (product, version, flavor, e)
            return (baseDir, product)

        if pinfo.version != version:
            print >> self.log, \
                "Warning: Something's wrong with %s; %s != %s" % \
                (product, version, pinfo.version)

        if pinfo.dir == "none":
            productDir = "none"
        else:
            try:
                (baseDir, productDir) = re.search(r"^(\S+)/(%s/\S*)$" % (product), pinfo.dir).groups()
            except:
                if self.verbose > 1:
                    print >> self.log, \
                        "Split of \"%s\" at \"%s\" failed; proceeding" \
                        % (pinfo.dir, product)
                if False:
                    pass
                else:
                    try:
                        (baseDir, productDir) = re.search(r"^(\S+)/([^/]+/[^/]+)$", pinfo.dir).groups()
                        if self.verbose > 1:
                            print >> self.log, \
                                "Guessing \"%s\" has productdir \"%s\"" \
                                % (pinfo.dir, productDir)
                    except:
                        if self.verbose:
                            print >> self.log, \
                                "Again failed to split \"%s\" into baseDir and productdir" \
                                % (pinfo.dir)
                        productDir = pinfo.dir

        return (baseDir, productDir)
                

    def writeManifest(self, serverDir, productDeps, product, version,
                      flavor=None, force=False):
        """write out a manifest file for a given product with the given
        dependencies.
        @param serverDir      a local directory representing the root of the 
                                  package distribution tree
        @param productDeps    the list of product dependencies.  Each item in
                                  the list is a Dependency instance
        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation
        @param force          if True, this package will overwrite any 
                                previously existing distribution files
        """
        self.unimplemented("writeManifest")
        

    def getDependenciesFor(self, product, version):
        """read the manifest from the remote server for the given product 
        and return a list of products it depends on.  Each element in the 
        returned list is a Dependency instance.  
        """
        manifest = self.distServer.getManifest(product, version, self.flavor)
        return manifest.getProducts()

    def getTaggedProductVersion(self, product, tag):
        """return the version of the given product that is part of a
        tagged release.
        @param product     the name of the desired product
        @param tag         the collection release name
        """
        if tag is None:  tag = self.tag
        return self.distServer.getTaggedProductInfo(product, self.flavor, tag)

    def getOption(self, name, defval=None):
        if self.options.has_key(name):
            return self.options[name]
        return defval

    def setGroupPerms(self, file, descend=False):
        if self.getOption("obeygroups", False):
            if self.verbose > 1:
                print >> self.log, "Setting group access for", file
            group = self.Option("groupowner")
            recurse = ''
            if descend:  recurse = "-R "
            change = ""
            if os.path.isdir(file):  change = "x"
                
            if group is not None:
                try:
                    server.system("chgrp %s%s %s" % (recurse, group, dir), 
                                  self.Eups.noaction, self.verbose-2, 
                                  self.log)
                except OSError:  pass
            try:
                system("chmod %sg+rws%s %s" % (recurse, change, dir), 
                       self.Eups.noaction, self.verbose-2, self.log)
            except OSError:  pass

    def unimplemented(self, name):
        raise Exception("%s: unimplemented (abstract) method" % name)


class DefaultDistrib(Distrib):
    """This partial implementation encodes some common assumptions for 
    where to place tagged release files, manifests, and table files when 
    creating distributions.  The following still need implementations:
       createPackage()
       getDistIdForPackage()
       installPackage()
       parseDistId()

    This class implements the following conventions:
       o  Manifests are written in the format supported by eups.server.Manifest.
       o  Manifests are deployed into a subdirectory of the server directory 
            called "manifests".  If the flavor is specified (and is not set 
            to "generic"), the manifest will be put in a subdirectory below 
            "manifests" named after the flavor; otherwise, it will be put 
            directly under "manifests".  The form of the filename is 
            "<product>-<version>.list".  This convention is captured in the 
            function getManifestPath() (which subclasses may override).
       o  Tagged releases are written in the format supported by 
            eups.server.TaggedProductList.  
       o  Tagged releases are written into files directly below the server
            directory.  The form of the filename is "<tag>.list".  This 
            convention is captured in the function getTaggedReleasePath()
            (which subclasses may override).
       o  Table files have the form "<product>.table"
    """

    def initServerTree(self, serverDir):
        """initialize the given directory to serve as a package distribution
        tree.
        @param serverDir    the directory to initialize
        """
        Distrib.initServerTree(self, serverDir)

        for dir in "manifests tables".split():
            dir = os.path.join(serverDir, dir)
            if not os.path.exists(dir):
                os.makedirs(dir)

                # set group owner ship and permissions, if desired
                self.setGroupPerms(dir)

    def getTaggedRelease(self, serverDir, tag, flavor=None):
        """get the collection of products that make up a tagged release and 
        return it as a TaggedProductList instance.  If such a release has not
        yet been created/written, return None.
        @param serverDir      a local directory representing the root of the 
                                  package distribution tree
        @param tag            the name of the tagged release of interest
        @param flavor         the target flavor for this release.  An 
                                  implementation may ignore this variable.  
        """
        file = os.path.join(serverDir, self.getTaggedReleasePath(tag, flavor))
        if not os.path.exists(file):
            if self.verbose > 1:
                msg = "Release is not yet available: " + tag
                if flavor is not None:
                    msg += " (%s)" % flavor
                print >> self.log,  msg
            return None

        return TaggedProductList.fromFile(file, tag)

    def getTaggedReleasePath(self, tag, flavor=None):
        """get the file path relative to a server root that will be used 
        store the product list that makes up a tagged release.
        @param tag        the name of the tagged release of interest
        @param flavor         the target flavor for this release.  An 
                                  implementation may ignore this variable.  
        """
        return "%s.list" % tag

    def writeTaggedRelease(self, serverDir, tag, products, flavor=None, 
                           force=False):
        """write a given tagged release into a server distribution tree
        @param serverDir      a local directory representing the root of the 
                                  package distribution tree
        @param tag            the name to give to the release
        @param products       a TaggedProductList instance containing the list
                                  of products in the release
        @param flavor         the target flavor for this release.  An 
                                  implementation may ignore this variable.  
        @param force          if False, don't over-write file if it already
                                  exists
        """
        self.initServerTree(serverDir)
        out = os.path.join(serverDir, self.getTaggedReleasePath(tag, flavor))

        exists = os.path.exists(out)
        if exists and not force:
            raise RuntimeError("Unable to overwrite release file, %s, unless forced" % out)

        if self.verbose > 0:
            verb = "Creating"
            if exists:
                verb = "Updating"
            print >> self.log, verb, "tagged release,", tag, "to", out

        products.write(out, flavor, self.Eups.noaction)

    def getManifestPath(self, serverDir, product, version, flavor=None):
        """return the path where the manifest for a particular product will
        be deployed on the server.  In this implementation, all manifest 
        files are deployed into a subdirectory of serverDir called "manifests". 
        if the flavor is specified (and is not set to "generic"), the manifest 
        will be put in a subdirectory below "manifests" named after the flavor;
        otherwise, it will be put directly under "manifests".  The form of the 
        filename is "<product>-<version>.list".  

        Subclasses may override this behavior according to the type of 
        distributions it creates.  For example, a Distrib subclass that 
        produces platform-generic packages (e.g. because it will build the 
        product from source) may choose to ignore the flavor parameter.

        @param serverDir      the local directory representing the root of 
                                 the package distribution tree.  In this 
                                 implementation, the returned path will 
                                 start with this directory.
        @param product        the name of the product that the manifest is 
                                for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform for the 
                                manifest.  In this implementation, a value
                                of None will default to "generic".  
        """
        file = "%s-%s.manifest" % (product, version)
        if not flavor or flavor == "generic":
            return os.path.join(serverDir, "manifests", file)
        else:
            return os.path.join(serverDir, "manifests", flavor, file)

    def writeManifest(self, serverDir, productDeps, product, version,
                      flavor=None, force=False):
        """write out a manifest file for a given product with the given
        dependencies.  See getManifestPath() for an explanation of where
        manifests are deployed.  

        @param serverDir      a local directory representing the root of the 
                                  package distribution tree
        @param productDeps    the list of product dependencies.  Each item in
                                  the list is a Dependency instance
        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation
        """
        self.initServerTree(serverDir)
        out = None
        mandir = os.path.join(serverDir, "manifests")
        if flavor is not None and flavor != "generic":
            mandir = os.path.join(mandir, flavor)
        if not os.path.exists(mandir):
            os.makedirs(mandir)

        out = os.path.join(mandir, "%s-%s.manifest" % (product, version))
        
        man = Manifest(product, version, self.Eups, 
                       verbosity=self.verbose-1, log=self.log)
        for dep in productDeps:
            man.addDepInst(dep)
        #
        # Go through that manifest copying table files into the distribution tree
        #
        for dep in productDeps:
            if not dep.tablefile:
                dep.tablefile = "none"
            if dep.tablefile == "none":
                continue

            fulltablename = dep.tablefile
            tabledir = os.path.join(serverDir, "tables")
            dep.tablefile = "%s-%s.table" % (dep.product, dep.version)
            tablefile_for_distrib = os.path.join(tabledir, dep.tablefile)

            if os.access(tablefile_for_distrib, os.R_OK) and not force:
                if self.Eups.verbose > 1:
                    print >> sys.stderr, "Not recreating", tablefile_for_distrib
            elif not os.path.exists(fulltablename):
                print >> sys.stderr, "Tablefile %s doesn't exist; omitting" % (fulltablename)
            else:
                if self.Eups.verbose > 1:
                    print >> sys.stderr, "Copying %s to %s" % (fulltablename, tablefile_for_distrib)
                server.copyfile(fulltablename, tablefile_for_distrib)
        #
        # Finally write the manifest file itself
        #
        man.write(out, flavor=flavor, noOptional=False)
        self.setGroupPerms(out)
        
    def createDependencies(self, product, version, flavor=None, tag=None, 
                           recursive=False, exact=False, letterVersions={}):
        """create a list of product dependencies based on what is known from 
        the system.

        This implementation will look up the product in the EUPS database and 
        analyze its table file.  

        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation
        @param tag            the target package collection release; this may 
                                be ignored by the implentation
        @param recursive      if False, this list will only contain the direct
                                dependencies of this product; otherwise, it 
                                will include the dependencies of the dependencies
                                recursively.  Default: False
        @param exact          Generate the complete list of dependencies that eups list -D --exact would return
        @param letterVersions  A dictionary mapping products to the "letter version" that we need (i.e. the same code, but a different build as an ABI changed)
        """
        deps = self._createDeps(product, version, flavor, tag, recursive, exact,
                                letterVersions=letterVersions)
        for prod in deps.getProducts():
            prod.tablefile = None

        self.updateDependencies(deps.getProducts(), flavor=flavor)

        return deps

    def updateDependencies(self, productList, flavor=None):
        """fill in information in the list of product dependencies based
        on what is known from the system

        This implementation will iterate through the products, adding the
        name of the table file and the distId.

        @param productList     list of products (output from createDependencies)
        @param flavor          the flavor of the target platform; this may 
                                 be ignored by the implentation
        """
        for prod in productList:
            if prod.flavor is None:
                prod.flavor = flavor
            if prod.distId is None:
                prod.distId = self.getDistIdForPackage(prod.product, prod.letterVersion, prod.flavor)
            #
            # Find product's table file
            #
            if prod.tablefile is None:
                try:
                    prod.tablefile = self.Eups.getProduct(prod.product, prod.version).tablefile
                except KeyboardInterrupt:
                    raise RuntimeError, ("You hit ^C while looking for %s %s's table file" %
                                         (prod.product, prod.version))
                except eups.ProductNotFound, e:
                    prod.tablefile = self.findTableFile(prod.product, prod.version, prod.flavor)
                except Exception, e:
                    pass

            if prod.tablefile == None:
                if not self.noeups or self.Eups.verbose:
                    print >> sys.stderr, "WARNING: Failed to lookup tablefile for %s %s: %s" % \
                          (prod.product, prod.version, e)
                prod.tablefile = "none"


    def findTableFile(self, product, version, flavor):
        """Give the distrib a chance to produce a table file"""
        return None

def findInstallableRoot(Eups):
    """return the first directory in the eups path that the user can install 
    stuff into
    """
    for ep in Eups.path:
        if os.access(ep, os.W_OK):
            return ep

    return None

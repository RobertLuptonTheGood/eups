#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package: : a specialization for binary tar-balls
#
from __future__ import absolute_import, print_function
import sys, os, re
from . import Distrib as eupsDistrib
from . import server as eupsServer

class Distrib(eupsDistrib.DefaultDistrib):
    """A class to encapsulate tarball-based product distribution

    OPTIONS:
    The behavior of a Distrib class is fine-tuned via options (a dictionary
    of named values) that are passed in at construction time.  The options 
    supported are:
       noeups           do not use the local EUPS database for information  
                          while creating packages.       
       obeyGroups       when creating files (other on the user side or the 
                          server side), set group ownership and make group
                          writable
       groupowner       when obeyGroups is true, change the group owner of 
                          to this value
       buildDir         a directory to use to build a package during install.
                          If this is a relative path, the full path will be
                          relative to the product root for the installation.
    """

    NAME = "tarball"

    def __init__(self, Eups, distServ, flavor, tag="current", options=None,
                 verbosity=0, log=sys.stderr):
        eupsDistrib.Distrib.__init__(self, Eups, distServ, flavor, tag, options,
                                     verbosity, log)


    # @staticmethod   # requires python 2.4
    def parseDistID(distID):
        """Return a valid package location if and only if we recognize the 
        given distribution identifier

        This implementation return a location if it ends with ".tar.gz"
        """
        if distID:
            suffix = ".tar.gz"
            distID = distID.strip()
            if distID.endswith(suffix):
                return distID

        return None

    parseDistID = staticmethod(parseDistID)  # should work as of python 2.2

    def initServerTree(self, serverDir):
        """initialize the given directory to serve as a package distribution
        tree.
        @param serverDir    the directory to initialize
        """
        eupsDistrib.DefaultDistrib.initServerTree(self, serverDir)

        config = os.path.join(serverDir, eupsServer.serverConfigFilename)
        if not os.path.exists(config):
            configcontents = """# Configuration for a tarball-based server
MANIFEST_FILE_RE = ^(?P<product>[^-]+)-(?P<version>[^@]+)@(?P<flavor>.*)\.manifest$
MANIFEST_URL = %(base)s/manifests/%(product)s-%(version)s@%(flavor)s.manifest
TARBALL_URL = %(base)s/%(path)s
DIST_URL = %(base)s/%(path)s
"""
            cf = open(config, 'a')
            try:
                cf.write(configcontents)
            finally:
                cf.close()

    def createPackage(self, serverDir, product, version, flavor=None, 
                      overwrite=False):
        """Write a package distribution into server directory tree and 
        return the distribution ID 
        @param serverDir      a local directory representing the root of the 
                                  package distribution tree
        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation
        @param overwrite      if True, this package will overwrite any 
                                previously existing distribution files even if Eups.force is false
        """
        if flavor is None:  flavor = self.Eups.flavor
        tarball = self.getDistIdForPackage(product, version, flavor)
        (baseDir, productDir) = self.getProductInstDir(product, version, flavor)
        if not baseDir:
            if productDir != "none":
                raise RuntimeError("Please complain to RHL about %s %s (baseDir = '', productDir = '%s')" %
                                   (product, version, productDir))

            msg = "I don't know how to write a tarball for %s %s as it has no directory" % (product, version)
            if self.verbose > 1:
                print(msg, file=self.log)
            return None

        if os.access("%s/%s" % (serverDir, tarball), os.R_OK) and not (self.Eups.force or overwrite):
            if self.verbose > 0:
                print("Not recreating", tarball, file=self.log)
            return tarball

        if self.verbose > 0:
            print("Writing", tarball, file=self.log)
        #
        # Record where the binary distro was installed originally (and presumably tested...)
        #
        pwdFile = os.path.join(baseDir, productDir, ".pwd")
        fd = None
        try:                            # "try ... except ... finally" and "with" are too new-fangled to use
            fd = open(pwdFile, "w")
            print(os.path.join(baseDir, productDir), file=fd)
            del fd
        except Exception as e:
            if self.verbose > 0:
                print("Unable to write %s; installation will be unable to check paths: %s" % (pwdFile, e), file=self.log)

        fullTarball = os.path.join(serverDir, tarball)
        try:
            eupsServer.system('(cd "%s" && tar -cf - "%s") | gzip > "%s"' %
                              (baseDir, productDir, fullTarball),
                              self.Eups.noaction, self.verbose-1, self.log)
        except Exception as e:
            try:
                os.unlink(pwdFile)
            except:
                pass

            try:
                os.unlink(fullTarball)
            except:
                pass

            raise OSError("Failed to write '%s': %s" % (tarball, str(e)))

        try:
            os.unlink(pwdFile)
        except:
            pass
        
        self.setGroupPerms(os.path.join(serverDir, tarball))

        return tarball

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
        location = self.parseDistID(self.getDistIdForPackage(product, version, flavor))
        return os.path.exists(os.path.join(serverDir, location))

    def installPackage(self, location, product, version, productRoot, 
                       installDir=None, setups=None, buildDir=None):
        """Install a package with a given server location into a given
        product directory tree.
        @param location     the location of the package on the server.  This 
                               value is a distribution ID (distID) that has
                               been stripped of its build type prefix.
        @param product      the name of the product installed by the package.
        @param version      the name of the product version.  
        @param productRoot  the product directory tree under which the 
                               product should be installed
        @param installDir   the preferred sub-directory under the productRoot
                               to install the directory.  This value, which 
                               should be a relative path name, may be
                               ignored or over-ridden by the pacman scripts
        @param setups       a list of EUPS setup commands that should be run
                               to properly build this package.  This is usually
                               ignored by the pacman scripts.
        """
        tarball = location
        if not tarball:
            raise RuntimeError("Expected a tarball name; saw \"%s\"" % location)

        if not buildDir:
            buildDir = self.getOption('buildDir', 'EupsBuildDir')
        if self.verbose > 0:
            print("Building in", buildDir, file=self.log)

        # we will download the tarball to the build directory
        tfile = "%s/%s" % (buildDir, tarball)

        if not self.Eups.noaction:
            tfile = self.distServer.getFileForProduct(location, product, 
                                                      version, self.Eups.flavor,
                                                      ftype="dist",
                                                      filename=tfile)
            if not os.access(tfile, os.R_OK):
                raise RuntimeError("Unable to read %s" % (tfile))

        unpackDir = os.path.join(productRoot, self.Eups.flavor)
        if installDir and installDir != "none":
            try:
                (baseDir, pdir, vdir) = re.search(r"^(\S+)/([^/]+)/([^/]+)$", 
                                                  installDir).groups()
                unpackDir = os.path.join(unpackDir,baseDir)
            except AttributeError as e:
                pass
                    
        if not os.path.exists(unpackDir):
            os.makedirs(unpackDir)

        if self.verbose > 0:
            print("installing %s into %s" % (tarball, unpackDir), file=self.log)

        try:
            eupsServer.system('cd "%s" && tar -zxmf "%s"' % (unpackDir, tfile),
                              self.Eups.noaction, verbosity=self.verbose-1)
        except Exception as e:
            raise RuntimeError("Failed to read '%s': %s" % (tfile, e))

        if installDir and installDir == "none":
            installDir = None

        if installDir:
            installDir = os.path.join(productRoot, self.Eups.flavor, installDir)
        else:
            installDir = os.path.join(unpackDir, product, version)            

        if installDir and os.path.exists(installDir):
            self.setGroupPerms(installDir)
        #
        # Try to check for potential problems with non-relocatable binaries
        #
        pwdFile = os.path.join(installDir, ".pwd")
        if installDir and os.path.exists(pwdFile):
            try:                        # "try ... except ... finally" and "with" are too new-fangled to use
                fd = open(pwdFile)
                originalDir = fd.readline().strip()
            except:
                originalDir = None

            if originalDir and installDir != originalDir:
                if self.verbose > 0:
                    print("Installing binary product %s %s into %s (was built for %s)" % (
                        product, version, installDir, originalDir), file=self.log)

    def getDistIdForPackage(self, product, version, flavor=None):
        """return the distribution ID that for a package distribution created
        by this Distrib class (via createPackage())
        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; this may 
                                be ignored by the implentation
        @param tag            the target package collection release; this may 
                                be ignored by the implentation
        """
        if not flavor:  flavor = self.flavor
        return "%s-%s@%s.tar.gz" % (product, version, flavor)

    def writeManifest(self, *args, **kwargs):
        """We want to write flavor-specific manifest files, but without a flavor subdirectory,
        so as to make it easier to deduce the flavor"""
        kwargs["flavor"] = None
        return eupsDistrib.DefaultDistrib.writeManifest(self, *args, **kwargs)
        
    def getManifestPath(self, serverDir, product, version, flavor=None):
        """return the path where the manifest for a particular product will
        be deployed on the server.  In this implementation, all manifest 
        files are deployed into a subdirectory of serverDir called "manifests"
        with the filename form of "<product>-<version>.manifest".  Since 
        this implementation produces generic distributions, the flavor 
        parameter is ignored.

        @param serverDir      the local directory representing the root of 
                                 the package distribution tree.  In this 
                                 implementation, the returned path will 
                                 start with this directory.
        @param product        the name of the product that the manifest is 
                                for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform for the 
                                manifest.  This implementation ignores
                                this parameter.
        """
        return os.path.join(serverDir, "%s-%s@%s.manifest" % (product, version, flavor))

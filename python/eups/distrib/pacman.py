#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package: a specialization for Pacman
#
from __future__ import print_function
import sys, os
from . import Distrib as eupsDistrib
from . import server as eupsServer
from eups import utils

class Distrib(eupsDistrib.DefaultDistrib):
    """A class to encapsulate Pacman-based product distribution

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
       pacmanCache      the value of the pacman cache (used when creating 
                          packages); default: the server's package base 
                          URL + "/pm"
       pacmanDBRoot     the root directory containing the pacman database 
                          (o..pacman..o); default: the root directory for 
                          product installation
    """

    NAME = "pacman"

    def __init__(self, Eups, distServ, flavor, tag="current", options=None,
                 verbosity=0, log=sys.stderr):
        eupsDistrib.Distrib.__init__(self, Eups, distServ, flavor, tag, options,
                                     verbosity, log)

        if 'pacmanCache' not in self.options and \
                self.distServer is not None:
            self.options['pacmanCache'] = self.distServer.base + "/pm"

    # @staticmethod   # requires python 2.4
    def parseDistID(distID):
        """Return a valid package location if and only we recognize the 
        given distribution identifier

        This implementation return a location if it starts with "pacman:"
        """
        if distID:
            prefix = "pacman:"
            distID = distID.strip()
            if distID.startswith(prefix):
                return distID[len(prefix):]

        return None

    parseDistID = staticmethod(parseDistID)  # should work as of python 2.2

    def checkInit(self, forserver=True):
        """Check that self is properly initialised; this matters for subclasses 
        with special needs"""
        if not eupsDistrib.Distrib.checkInit(self, forserver):
            return False

        if forserver:
            if 'pacmanCache' not in self.options:
                print("Option 'pacmanCache' not set", file=self.log)
                return False

            msg = "Illegal value for Option 'pacmanCache': "
            if not utils.is_string(self.options['pacmanCache']):
                print(msg + self.options['pacmanCache'], file=self.log)
                return False

            self.options['pacmanCache'] = self.options['pacmanCache'].strip()
            if len(self.options['pacmanCache']) == 0:
                print(msg + self.options['pacmanCache'], file=self.log)
                return False

        return True

    def getManifestPath(self, serverDir, product, version, flavor=None):
        """return the path where the manifest for a particular product will
        be deployed on the server.  In this implementation, all manifest 
        files are deployed into a subdirectory of serverDir called "manifests"
        with the filename form of "<product>-<version>.manifest".  It is 
        assumed that pacman distributions are platform-generic, so the 
        flavor parameter is ignored.

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
        return os.path.join(serverDir, "manifests", 
                            "%s-%s.manifest" % (product, version))

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
        # we don't have a way of creating pacman files.  
        return self.getDistIdForPackage(product, version, flavor)

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
        location = self.parseDistID(self.getDistIdForPackage(product, version, 
                                                             flavor))
        return os.path.exists(os.path.join(serverDir, location))

    def getDistIdForPackage(self, product, version, flavor=None):
        """return the distribution ID that for a package distribution created
        by this Distrib class (via createPackage())
        @param product        the name of the product to create the package 
                                distribution for
        @param version        the name of the product version
        @param flavor         the flavor of the target platform; None means
                                assume a generic flavor.
        """
        if flavor is None or flavor == "generic":
            return "pacman:%s:%s-%s" % \
                (self.options['pacmanCache'], product, version)
        else:
            return "pacman:%s:%s/%s-%s" % \
                (self.options['pacmanCache'], flavor, product, version)

    def installPackage(self, location, product, version, productRoot, 
                       installDir, setups=None, buildDir=None):
        """Install a package with a given server location into a given
        product directory tree.
        @param location     the location of the package on the server.  This 
                               value is a distribution ID (distID) that has
                               been stripped of its build type prefix.
        @param product      the name of the product to install
        @param version      the version of the product
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
        pacmanDir = productRoot
        if 'pacmanDBRoot' in self.options:
            pacmanDir = os.join.path(pacmanDir, self.options['pacmanDBRoot'])

        self.createPacmanDir(pacmanDir)

        self.installPacmanPackage(location, productRoot, installDir, 
                                  pacmanDir, setups)
        self.cleanPackage(product, version, pacmanDir, location)
        self.setGroupPerms(installDir, descend=True)


    def installPacmanPackage(self, location, productRoot, installDir, pacmanDir,
                             setups=None):
        if not os.path.exists(os.path.join(pacmanDir, "o..pacman..o")) and \
                self.verbose >= 0:
            print("Warning: Pacman database directory,", \
                "o..pacman..o, not found in", pacmanDir, file=self.log)

        try:
            eupsServer.system("""cd %s && pacman -allow urllib2 -install "%s" """ % \
                                  (pacmanDir, location), 
                              self.Eups.noaction, self.verbose, self.log)
        except OSError:
            raise RuntimeError("Pacman failed to install " + location)

    def createPacmanDir(self, pacmanDir):
        """Create a directory to be used by pacman.

        N.b. May be subclassed to initialise pacman; e.g. LSST requires
           pacman -install http://dev.lsstcorp.org/pkgs/pm:LSSTinit
        """
        if not os.path.isdir(pacmanDir):
            os.mkdir(pacmanDir)
        
    def cleanPackage(self, product, version, productRoot, location):
        """remove any distribution-specific remnants of a package installation.
        This gets run automatically after a successful installation; however,
        it should be run explicitly after a failed installation.

        This implementation does a "pacman remove" to purge the record of the
        package from the local pacman database.

        @param product      the name of the product to clean up after
        @param version      the version of the product
        @param productRoot  the product directory tree under which the 
                               product is assumed to be installed
        @param location     the distribution location used to install the
                               package.  The implementation may ignore this.
        @returns bool    True, if any state was cleaned up or False if nothing
                             needed to be done.  Note that False is not an 
                             error.  
        """
        pacmanDir = self.getOption('pacmanDBRoot', productRoot)
        if os.path.exists(os.path.join(pacmanDir,'o..pacman..o')):
            cmd = 'cd %s && pacman -allow urllib2 -remove "%s" '
            eupsServer.system(cmd % (pacmanDir, location), 
                              self.Eups.noaction, self.verbose, self.log)
        else:
            if self.verbose >= 0:
                print("Warning: pacman database not found under", pacmanDir, file=self.log)
            return False
        
        return True

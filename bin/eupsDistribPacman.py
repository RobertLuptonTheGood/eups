#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import os, re, sys
import pdb
import eups
import eupsDistrib

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Distrib(eupsDistrib.Distrib):
    """Handle distribution using pacman"""
    
    implementation = "pacman"     # which implementation is provided?

    def checkInit(self):
        """Check that self is properly initialised; this matters for subclasses with special needs"""

        try:
            type(self.pacmanCache)
        except AttributeError, e:
            self.pacmanCache = None
            print >> sys.stderr, "Incorrectly initialised eupsDistribPacman: %s" % e

    def createPackage(self, productName, versionName, baseDir=None, productDir=None):
        """Create a package distribution and return a distribution ID (a pacman cache ID)"""

        return "pacman:%s:%s/%s-%s" % (self.pacmanCache, self.installFlavor, productName, versionName)

    def parseDistID(self, distID):
        """Return a valid identifier (e.g. a pacman cacheID) iff we understand this sort of distID"""

        try:
            return re.search(r"^pacman:(([^:]+):(.*))", distID).groups()
        except AttributeError:
            pass

        return None

    parseDistID = classmethod(parseDistID)

    def createPacmanDir(self, pacmanDir):
        """Create a directory to be used by pacman.

        N.b. May be subclassed to initialise pacman; e.g. LSST requires
           pacman -install http://dev.lsstcorp.org/pkgs/pm:LSSTinit
        """
 
        if not os.path.isdir(pacmanDir):
            os.mkdir(pacmanDir)
        
    def installPackage(self, distID, productsRoot, *args):
        """Install a package using pacman"""

        try:
            cacheID, cacheName, cacheDir = Distrib.parseDistID(distID)
            if not cacheID:
                raise RuntimeError, ("Expected distribution ID of form pacman:*:*; saw \"%s\"" % distID)
        except:
            raise
        
        pacmanDir = productsRoot
        try:
            self.createPacmanDir(pacmanDir)
        except:
            raise RuntimeError, ("Pacman failed to create %s" % (pacmanDir))

        if self.Eups.verbose > 0:
            print >> sys.stderr, "installing pacman cache %s into %s" % (cacheID, pacmanDir)

        try:
            eupsDistrib.system("""cd %s && pacman -install "%s" """ % (pacmanDir, cacheID), self.Eups.noaction)
        except OSError, e:
            raise RuntimeError, ("Pacman failed to install %s" % (cacheID))

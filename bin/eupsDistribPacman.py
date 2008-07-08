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

        return "pacman:%s:%s|version('%s')" % (pacman_cache, productName, versionName)

    def parseDistID(self, distID):
        """Return a valid identifier (e.g. a pacman cacheID) iff we understand this sort of distID"""

        try:
            return re.search(r"^pacman:(([^:]+):(.*))", distID).groups()
        except AttributeError:
            pass

        return None

    parseDistID = classmethod(parseDistID)

    def installPackage(self, distID, productsRoot, *args):
        """Install a package using pacman"""

        try:
            cacheID, cacheName, cacheDir = Distrib.parseDistID(distID)
            if not cacheID:
                raise RuntimeError, ("Expected distribution ID of form pacman:*:*; saw \"%s\"" % distID)
        except:
            raise
        
        pacmanDir = productsRoot
        if not os.path.isdir(pacmanDir):
            try:
                os.mkdir(pacmanDir)
            except:
                raise RuntimeError, ("Pacman failed to create %s" % (pacmanDir))
        #
        # Pacman installs tend to assume the existence of a flavor subdirectory, so make it now
        #
        # We won't actually't make it, as pacman needs to be initialised in this directory
        # to recognise cache names; e.g.
        #   pacman -install http://dev.lsstcorp.org/pkgs/pm:LSSTinit
        # As this is cache specific, I won't hard code it here.  In general, this
        # could be handled as a further subclass of eupsDistribPacman
        #
        if False:
            if os.path.split(pacmanDir)[1] == self.Eups.flavor:
                extra_dir = os.path.join(pacmanDir, self.Eups.flavor)
                if not os.path.isdir(extra_dir):
                    os.makedirs(extra_dir)

        if self.Eups.verbose > 0:
            print >> sys.stderr, "installing pacman cache %s into %s" % (cacheID, pacmanDir)

        try:
            eupsDistrib.system("""cd %s && pacman -install "%s" """ % (pacmanDir, cacheID), self.Eups.noaction)
        except OSError, e:
            raise RuntimeError, ("Pacman failed to install %s" % (cacheID))

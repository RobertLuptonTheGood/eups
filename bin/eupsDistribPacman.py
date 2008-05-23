#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import os, re, sys
import pdb
import neups as eups
import eupsDistrib

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Distrib(eupsDistrib.Distrib):
    """Handle distribution using pacman"""
    
    def createPackage(self, productName, versionName, baseDir=None, productDir=None):
        """Create a package distribution and return a distribution ID (a pacman cache ID)"""

        return "pacman:%s:%s|version('%s')" % (pacman_cache, productName, versionName)

    def installPackage(self, distID, productsRoot, *args):
        """Install a package using pacman"""

        if not re.search(r"^pacman:", distID):
            raise RuntimeError, ("Expected distribution ID of form pacman:*; saw \"%s\"" % distID)

        cacheID = distID

        pacmanDir = "%s" % (productsRoot)
        if not os.path.isdir(pacmanDir):
            try:
                os.mkdir(pacmanDir)
            except:
                raise RuntimeError, ("Pacman failed to create %s" % (pacmanDir))

        if verbose > 0:
            print >> sys.stderr, "installing pacman cache %s into %s" % (cacheID, pacmanDir)

        try:
            eups.system("""cd %s && pacman -install "%s" """ % (pacmanDir, cacheID), self.Eups.noaction)
        except:
            raise RuntimeError, ("Pacman failed to install %s" % (cacheID))

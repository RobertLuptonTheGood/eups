#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import os
import sys
import pdb
import neups as eups
import eupsDistrib

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Distrib(eupsDistrib.Distrib):
    """Handle distribution using pacman"""
    
    def getDistID(self, productName, versionName, basedir=None, productDir=None):
        """Return a distribution ID (a pacman cache ID)"""

        return "pacman:%s:%s|version('%s')" % (pacman_cache, productName, versionName)

    def doInstall(self, distID, products_root, *args):
        """Install a package using pacman"""

        cacheID = distID

        pacmanDir = "%s" % (products_root)
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

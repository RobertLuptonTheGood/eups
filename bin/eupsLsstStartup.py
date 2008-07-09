"""Define and register a subclass of eupsDistribPacman that can initialise the
pacman installation for LSST"""

import os, re, sys
import pdb
import eupsDistrib
import eupsDistribPacman

class lsstDistrib(eupsDistribPacman.Distrib):
    """Handle distribution using LSST's pacman cache"""

    implementation = "pacman:LSST"     # which implementation is provided?

    def parseDistID(self, distID):
        """Return a valid identifier (e.g. a pacman cacheID) iff we understand this sort of distID"""

        try:
            return re.search(r"^pacman:((LSST):(.*))", distID).groups()
        except AttributeError:
            pass

        return None

    parseDistID = classmethod(parseDistID)

    def createPacmanDir(self, pacmanDir):
        """Create and initialise a directory to be used by LSST's pacman."""

        if not os.path.isdir(pacmanDir):
            os.mkdir(pacmanDir)

        oPacmanDiro = os.path.join(pacmanDir, "o..pacman...o")
        if not os.path.isdir(opacmanDiro):
            eupsDistrib.system("cd %s && pacman -install http://dev.lsstcorp.org/pkgs/pm:LSSTinit" % (pacmanDir))

eupsDistribFactory.registerFactory(lsstDistrib)

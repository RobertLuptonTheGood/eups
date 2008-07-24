"""Define and register a subclass of eupsDistribPacman that can initialise the
pacman installation for LSST"""

import os, re, sys
import pdb
import eupsDistrib
import eupsDistribPacman
import eupsDistribFactory
#
# Subclass eupsDistribPacman to allow us to initialise caches
#
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
        if not os.path.isdir(oPacmanDiro):
            eupsDistrib.system("cd %s && pacman -install http://dev.lsstcorp.org/pkgs/pm:LSSTinit" % (pacmanDir))

eupsDistribFactory.registerFactory(lsstDistrib, first=True)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Define a distribution type "preferred"
#
eups.defineValidTags("preferred")

if False:
    eups.defineValidSetupTypes("build") # this one's defined already

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Allow "eups fetch" as an alias for "eups distrib install"
#
def eupsCmdHook(cmd, argv):
    """Called by eups to allow users to customize behaviour by defining it in EUPS_STARTUP

    The arguments are the command (e.g. "admin" if you type "eups admin")
    and sys.argv, which you may modify;  cmd == argv[1] if len(argv) > 1 else None
    """

    if cmd == "fetch":
        argv[1:2] = ["distrib", "install"]

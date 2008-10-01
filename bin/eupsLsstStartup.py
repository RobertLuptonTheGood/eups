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

    NAME = "pacman:LSST"     # which implementation is provided?
    prefix = NAME + ":"
    pacmanBaseURL = "http://dev.lsstcorp.org/pkgs/pm:"

    # @staticmethod   # requires python 2.4
    def parseDistID(distID):
        """Return a valid package location (e.g. a pacman cacheID) iff we understand this sort of distID"""

        if distID.startswith(prefix):
            return pacmanBaseURL + distID[len(prefix):]

        return None

    parseDistID = staticmethod(parseDistID)

    def createPacmanDir(self, pacmanDir):
        """Create and initialise a directory to be used by LSST's pacman."""

        if not os.path.isdir(pacmanDir):
            os.mkdir(pacmanDir)

        oPacmanDiro = os.path.join(pacmanDir, "o..pacman..o")
        if not os.path.isdir(opacmanDiro):
            eupsDistrib.system("cd %s && pacman -install http://dev.lsstcorp.org/pkgs/pm:LSSTinit" % (pacmanDir))

distribClasses['pacman'] = lsstDistrib

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

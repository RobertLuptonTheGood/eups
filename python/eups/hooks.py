"""
Module that enables user configuration and hooks.  
"""
import os, sys
import utils
from VersionCompare import VersionCompare

# the function to use to compare two version.  The user may reset this 
# to provide a different algorithm.
version_cmp = VersionCompare()

# a function for setting fallback flavors.  This function is callable by 
# the user.  
setFallbackFlavors = utils.Flavor().setFallbackFlavors

# various configuration properties settable by the user
config = utils.ConfigProperty("Eups".split())
config.Eups = utils.ConfigProperty("verbose userTags setupTypes".split(), "Eups")
config.Eups.verbose = 0
config.Eups.userTags = ""
config.Eups.setupTypes = "build"

def loadCustomization(customDir):
    """
    load all site or user customizations.
    """
    pass

_validSetupTypes = {}   # in lieu of a set

def defineValidSetupTypes(*types):
    """Define a permissible type of setup (e.g. build)"""

    for tp in types:
        _validSetupTypes[tp] = 1

def getValidSetupTypes():
    """Return (a copy of) all valid types of setup (e.g. build)"""
    out = _validSetupTypes.keys()
    out.sort()
    return out



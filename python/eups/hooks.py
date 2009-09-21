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
config.Eups = utils.ConfigProperty("verbose userTags".split(), "Eups")
config.Eups.verbose = 0
config.Eups.userTags = ""



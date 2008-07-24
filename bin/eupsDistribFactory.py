#!/usr/bin/env python
#
# The main eups programme
#
import sys
import eupsDistrib

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

_distribClasses = []                          # list of possible builders

def registerFactory(obj, first=False):
    """Register object (a module or class) as a type of eupsDistrib

    E.g.  import eupsDistribBuilder;  registerFactory(eupsDistribBuilder)"""

    global _distribClasses

    if isinstance(obj, type(sys)):      # isinstance(obj, module) doesn't work; why?
        obj = obj.Distrib

    if first:
        _distribClasses = [obj] + _distribClasses
    else:
        _distribClasses += [obj]

import eupsDistribBuilder; registerFactory(eupsDistribBuilder)
import eupsDistribPacman;  registerFactory(eupsDistribPacman)
import eupsDistribTarball; registerFactory(eupsDistribTarball)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def _chooseCtor(implementation):
    """Return the proper constructor for the implementation"""
    
    for dc in _distribClasses:          # find which version provides the desired implementation
        if dc.handles(implementation):
            return dc

    return eupsDistrib.Distrib

def Distrib(implementation, Eups, packageBasePath=None, installFlavor=None, preferFlavor=False,
            tag=None, no_dependencies=False, obeyGroups=False, allowIncomplete=False,
            noeups=False, **kwargs):
    """A factory function to return a Distrib that provides the desired implementation

    If Eups is an eupsDistrib object, then all other arguments are ignored and we'll return a copy
    (but with the requested implementation)"""

    if isinstance(Eups, eupsDistrib.Distrib):
        oldDistrib = Eups
        return copyDistrib(implementation, oldDistrib)
    #
    # We're not being asked for a copy
    #
    assert packageBasePath
    #
    # Make our Distrib object
    #
    Distrib = _chooseCtor(implementation)

    distrib = Distrib(Eups, packageBasePath, obeyGroups=obeyGroups, installFlavor=installFlavor,
                      tag=tag, preferFlavor=preferFlavor, no_dependencies=no_dependencies,
                      allowIncomplete=allowIncomplete, noeups=noeups)
    #
    # Set optional arguments;  not all may be needed by this particular eupsDistrib
    #
    distrib.kwargs = kwargs.copy()
    
    for k in kwargs.keys():
        distrib.__dict__[k] = kwargs[k]

    distrib.checkInit()   # check that all required fields are present

    return distrib

def copyDistrib(implementation, oldDistrib):
    """Copy a Distrib, returning the proper subclass for the specified implementation"""
    Distrib = _chooseCtor(implementation)

    od = oldDistrib                     # just for brevity
    distrib = Distrib(od.Eups, od.packageBasePath, obeyGroups=od.obeyGroups,
                      tag=od.tag, preferFlavor=od.preferFlavor, no_dependencies=od.no_dependencies,
                      noeups=od.noeups)

    distrib._msgs = od._msgs
    #
    # Set other parameters that are specific to distribution mechanisms
    #
    distrib.kwargs = od.kwargs.copy()
    
    for k in distrib.kwargs.keys():
        distrib.__dict__[k] = distrib.kwargs[k]

    distrib.checkInit()   # check that all required fields are present

    return distrib

def getImplementation(distID):
    """Return the proper implementation given a distID"""
    
    for dc in _distribClasses:
        if dc.parseDistID(distID):
            return dc.implementation

    return eupsDistrib.Distrib.implementation

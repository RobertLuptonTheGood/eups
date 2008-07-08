#!/usr/bin/env python
#
# The main eups programme
#
import sys
import eupsDistrib

_distribClasses = []                          # list of possible builders
import eupsDistribBuilder; _distribClasses += [eupsDistribBuilder]
import eupsDistribPacman;  _distribClasses += [eupsDistribPacman]
import eupsDistribTarball; _distribClasses += [eupsDistribTarball]

def _chooseCtor(implementation):
    """Return the proper constructor for the implementation"""
    
    for dc in _distribClasses:          # find which version provides the desired implementation
        if dc.Distrib.handles(implementation):
            return dc.Distrib

    return eupsDistrib.Distrib

def Distrib(implementation, Eups, packageBasePath=None, installFlavor=None, preferFlavor=False,
            current=False, tag=None, no_dependencies=False, obeyGroups=False, noeups=False, **kwargs):
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

    distrib = Distrib(Eups, packageBasePath, current=current, obeyGroups=obeyGroups, installFlavor=installFlavor,
                      tag=tag, preferFlavor=preferFlavor, no_dependencies=no_dependencies,
                      noeups=noeups)
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
    distrib = Distrib(od.Eups, od.packageBasePath, current=od.current, obeyGroups=od.obeyGroups,
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
        if dc.Distrib.parseDistID(distID):
            return dc.Distrib.implementation

    return eupsDistrib.Distrib.implementation

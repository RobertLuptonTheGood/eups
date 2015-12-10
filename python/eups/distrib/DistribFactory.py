#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package: a specialization for Pacman
#
import sys, os, re, copy
import eups
from . import server as eupsServer

from .Distrib import Distrib
from . import tarball
from . import pacman
from . import builder
from . import eupspkg

class DistribFactory:
    """a factory class for creating Distrib instances

    This default implementation will automatically register three default 
    Distrib class implementations:  "tarball", "pacman", and "builder".  
    (These are loaded via _registerDefaultDistribs().)  It will also consult 
    the DistribServer object provided at construction time for the 
    configuration property, "DISTRIB_CLASS" (via 
    DistribServer.getConfigPropertyList()).  Each value the form,

        [name: ]module_class_name

    where module_class_name is full module-qualified name of the Distrib 
    sub-class and the optional name is the logical name to associate with this
    class (for look-ups by name via createDistribByName()).  Example values 
    include:

        mymodule.myDistribClass
        tarball: mymodule.mySpecialDistribTarballClass

    In the second example, the class would over-ride the default DistribTarball
    class when looked up via createDistribByName().  

    (Note that these custom classes can be encoded into the server configuration
    file by putting each classname in a separate entry for DISTRIB_CLASS:

       DISTRIB_CLASS = mymodule.myDistribClass
       DISTRIB_CLASS = tarball: mymodule.mySpecialDistribTarballClass

    .)

    When a Distrib class is chosen via createDistrib(), the custom classes 
    will be searched first before the defaults.  More precisely, the classes
    are search in the reverse order that were registered so that latter 
    registered classes override the previous ones.  
    """

    def __init__(self, Eups, distServ=None):
        """create a factory
        @param Eups       the eups controller instance in use
        @param distServ   the DistribServer object to use to configure 
                            this factory.  If None, it will be necessary
                            to add one later via resetDistribServer() 
                            before creating Distribs.
        """
        self.classes = []
        self.lookup = {}
        self.distServer = distServ
        self.Eups = Eups

        self._registerDefaultDistribs()
        self._registerCustomDistribs()

    def clone(self):
        """
        create a copy of this factory.  The clone will share this instance's
        copy of the DistribServer and Eups objects.
        """
        out = copy.copy(self)
        out.classes = self.classes[:]
        out.lookup = self.lookup.copy()

    def supportsName(self, name): 
        """
        return True if a class is available by the given name
        """
        return self.lookup.has_key(name)

    def register(self, distribClass, name=None):
        """register a Distrib class.  An attempt to register an object that 
        is not a subclass of Distrib results in a TypeError exception.
        Classes registered later will override previous registrations when
        they support the same type of distribID or use the same name.  
        @param distribClass   the class object that is a sub-class of Distrib
        @param name           the look-up name to associate with the class.  
                                 this name should be used when creating a 
                                 Distrib instance via createDistribByName().
                                 If None, the internal default name for the 
                                 class will be used as the look-up name.
        """
        if not issubclass(distribClass, Distrib):
            raise TypeError("registrant not a subclass of eups.distrib.Distrib")

        if name is None:  name = distribClass.NAME
        self.lookup[name] = distribClass
        self.classes.append(distribClass)

    def resetDistribServer(self, distServer):
        """
        reassigne the DistribServer that will be passed to the Distrib
        classes created by this factory.
        """
        self.distServer = distServer
        self._registerCustomDistribs()

    def _registerDefaultDistribs(self):
        self.register(NoneDistrib)
        self.register(tarball.Distrib)
        self.register(pacman.Distrib)
        self.register(builder.Distrib)
        self.register(eupspkg.Distrib)

    def _registerCustomDistribs(self):
        if self.distServer:
            self.registerServerDistribs(self.distServer)

    def registerServerDistribs(self, distServer):
        self.distServer = distServer
        if self.distServer is None:
            return
        sep = re.compile(r'\s*:\s*')

        classnames = self.distServer.getConfigPropertyList("DISTRIB_CLASS")
        for cls in classnames:
            nameclass = sep.split(cls, 1)
            if len(nameclass) < 2:  
                nameclass = [ None, nameclass[0] ]
            self.register(self.importDistribClass(nameclass[1]), nameclass[0])

    def importDistribClass(self, classname):
        """import and return the constructor for the given Distrib class name
        @param classname   the module classname to import
        """
        return eupsServer.importClass(classname)

    def createDistrib(self, distId, flavor=None, tag=None, 
                      options=None, verbosity=0, log=sys.stderr):
        """create a Distrib instance for a given distribution identifier
        @param distId    a distribution identifier (as received via a manifest)
        @param flavor     the platform type to assume.  The default is the 
                            flavor associated with our Eups instance.
        @param tag        the logical name of the release of packages to assume
                            (default: "current")
        @param options    a dictionary of named options that are used to fine-
                            tune the behavior of this Distrib class.  See 
                            discussion above for a description of the options
                            supported by this implementation; sub-classes may
                            support different ones.
        @param verbosity  if > 0, print status messages; the higher the 
                            number, the more messages that are printed
                            (default=0).
        @param log        the destination for status messages (default:
                            sys.stderr)
        """
        if not self.distServer:
            raise RuntimeError("No DistribServer set; use DistribFactory.resetDistribServer()")
        if flavor is None:  flavor = self.Eups.flavor
        use = self.classes[:]
        use.reverse()
        for cls in use:
            if cls.parseDistID(distId):
                return cls(self.Eups, self.distServer, 
                           flavor, tag, options, verbosity, log)

        raise RuntimeError("I don't know how to install distId %s" % distId)

    def createDistribByName(self, name, flavor=None, tag=None, 
                            options=None, verbosity=0, log=sys.stderr):
        """create a Distrib instance for a given distribution identifier
        @param distId    a distribution identifier (as received via a manifest)
        @param verbosity     if > 0, print status messages; the higher the 
                               number, the more messages that are printed
                               (default=0).
        @param flavor     the platform type to assume.  The default is the 
                               flavor associated with our Eups instance.
        @param tag        the logical name of the release of packages to assume
                            (default: "current")
        @param log        the destination for status messages (default:
                               sys.stderr)
        @param options    a dictionary of named options that are used to fine-
                            tune the behavior of this Distrib class.  See 
                            discussion above for a description of the options
                            supported by this implementation; sub-classes may
                            support different ones.
        """
        if not self.distServer:
            raise RuntimeError("No DistribServer set; use DistribFactory.resetDistribServer()")
        if flavor is None:  flavor = self.Eups.flavor
        cls = self.lookup[name]
        return cls(self.Eups, self.distServer, flavor, tag, options, 
                   verbosity, log)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class NoneDistrib(Distrib):
    """A class to handle packages that don't need installing, but should be declared

E.g. python, if declared as "eups declare -r none ... python X.Y"
    """

    NAME = "none"

    def __init__(self, *args, **kwargs):
        Distrib.__init__(self,  *args, **kwargs)

    # @staticmethod   # requires python 2.4
    def parseDistID(distID):
        """Return a valid package location if and only if we recognize the given distribution identifier"""
        if distID == 'None':
            return distID

        return None

    parseDistID = staticmethod(parseDistID)  # should work as of python 2.2

    def installPackage(self, *args, **kwargs):
        """Install a package with a given server location into a given product directory tree.
        """
        pass

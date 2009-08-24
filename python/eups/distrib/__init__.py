"""
This module is responsible for downloading and installing products from 
a distribution server as well as for maintaining packages on that server.  
All remote interactions with a server is done via the eups.server module.

The important classes are:
  Distribution     This provides the EUPS application level interface to 
                     server-related functions
  Distrib          This provides an abstract API for different techniques
                     for installing products.
  DistribFactory   A factory class for creating Distrib instances that 
                     can operate on a given product distribution (i.e. 
                     a package) handle. 

The following Distrib implementations are supported:
  tarball          For products that can be installed by simply un-tarring 
                     a tar-ball file from the server; no compiling or other 
                     "building" required.
  pacman           For Pacman distributions (see 
                     http://atlas.bu.edu/~youssef/pacman/.
  builder          Products are built via a download-able Bourne scripts 
                     with particular conventions.

The DefaultDistrib class provides is a partial implementation of the Distrib
abstract class that encodes certain assumptions about the location of 
information on the distribution server, accessed via HTTP.  All of the 
above concrete implementations use these assumptions and thus inherit from 
DefaultDistrib.
"""
from Distribution import Distribution
from Distrib import Distrib, DefaultDistrib
from DistribFactory import DistribFactory

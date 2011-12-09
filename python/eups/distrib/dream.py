#!/usr/bin/env python

import re
import os.path
import eups
import eups.hooks
from eups.table import Table
from server import DistribServer, Manifest
from builder import expandBuildFile

class DreamServer(DistribServer):
    """Package server that allows one to turn dreams into reality.
    We dream about the existence of a product+version, and it appears.

    We get the build and table files from some archive, and use those
    with the usual "builder" Distrib to create a product with a known
    version.  Obviously, this cannot handle products that have
    dependencies on packages that don't yet exist (because it would
    need to know the desired version for those packages).
    """

    NOCACHE = True
    def __init__(self, *args, **kwargs):
        super(DreamServer, self).__init__(*args, **kwargs)
        self.Eups = eups.Eups()
        # Working with real files from here on out
        assert self.base.startswith("dream:")
        self.base = self.base[len("dream:"):]
        
    def getFileForProduct(self, path, product, version, flavor, 
                          ftype=None, filename=None, noaction=False):
        if ftype is not None and ftype.lower() == "manifest":
            return self.getManifest(product, version, flavor, noaction=noaction)

        if path is None or len(path) == 0:
            path = "%s.%s" % (product, ftype)
        elif version is not None:
            pv = "%s-%s" % (product, version)
            path = re.sub(pv, product, path)
        
        if ftype is not None and ftype == "build":
            if version is None:
                raise RuntimeError("Unspecified version for %s" % product)
            inBuild = open(os.path.join(self.base, path))
            if filename is None: filename = self.makeTempFile("dream_")
            outBuild = open(filename, "w")
            builderVars = eups.hooks.config.distrib["builder"]["variables"]
            expandBuildFile(outBuild, inBuild, product, version, self.verbose, builderVars)
            inBuild.close()
            outBuild.close()
            return filename

        return self.getFile(path, flavor, ftype=ftype, filename=filename, noaction=noaction)
        
    def getManifest(self, product, version, flavor, noaction=False):
        if noaction:
            return Manifest()

        if version is None:
            raise RuntimeError("Unspecified version for %s" % product)

        tablefile = self.getTableFile(product, version, flavor)
        table = Table(tablefile)
        deps = table.dependencies(self.Eups, recursive=True)
        deps.reverse()

        manifest = Manifest(product, version)
        for p, optional, depth in deps:
            if not optional or self.Eups.findProduct(p.name, p.version):
                manifest.addDependency(p.name, p.version, p.flavor, None, None, None, optional)

        distId = "build:%s-%s.build" % (product, version)
        tableName = "%s.table" % product
        manifest.addDependency(product, version, flavor, tableName, os.path.join(product, version),
                               distId, False)

        return manifest

    def getTagNames(self, flavor=None, noaction=False):
        return list()

    def getTagNamesFor(self, product, version, flavor="generic", tags=None, noaction=False):
        return list(), list()

    def getTaggedProductList(self, tag="current", flavor=None, noaction=False):
        return list()

    def listAvailableProducts(self, product=None, version=None, flavor=None,
                              tag=None, noaction=False):
        products = list()
        if tag is None and product is not None and version is not None:
            path = os.path.join(self.base, product)
            if os.path.exists(path + ".table") and os.path.exists(path + ".build"):
                products.append((product, version, flavor))
        return products
      
    def listFiles(self, path, flavor=None, tag=None, noaction=False):
        return list()


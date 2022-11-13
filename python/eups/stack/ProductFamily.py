import os
from eups import utils
from eups.Product import Product
import eups.tags
from eups.exceptions import ProductNotFound, TableFileNotFound
from eups.table import Table

class ProductFamily(object):
    """
    a set of different versions of a named product.  When this refers to
    installed products, it is assumed that all versions are of the same flavor.
    """

    def __init__(self, name):
        """
        create a product family with a given product name
        """

        # the product name
        self.name = name

        # a lookup for version-specific information where the keys are the
        # version names and the values are tuples containing the installation
        # directory, the dependencies table, and a corresponding instance of
        # Table (which may be None).
        self.versions = {}

        # a lookup of tag assignments where each key is a tag name and its
        # value is the version name assigned to the tag.
        self.tags = {}

    def __repr__(self):
        nVersion = len(self.versions)
        return "ProductFamily: %s (%d version%s)" % (self.name, nVersion, ('' if nVersion == 1 else 's'))

    def getVersions(self):
        """
        return a list containing the verison names in this product family
        """
        return list(self.versions.keys())

    def getProduct(self, version, dbpath=None, flavor=None):
        """
        return the Product of the requested version or None if not found.
        This returned Product's db attribute will be set to None.

        @param version : the desired version
        @param dbpath    a database path to set on the returned product
        @param flavor    a platform flavor to set on the returned product
        @return    the product description as a Product instance
        """
        try:
            versdata = self.versions[version]
            tags = [item[0] for item in [x for x in self.tags.items() if x[1] == version]]
            out = Product(self.name, version, flavor,
                          versdata[0],    # the install directory
                          versdata[1],    # the table file
                          tags, dbpath)
            if versdata[2]:
                out._table = versdata[2]
            return out

        except KeyError:
            raise ProductNotFound(self.name, version)

    def getTags(self):
        """
        return a list of the tag names assigned to versions in this
        product family
        """
        return list(self.tags.keys())

    def isTagAssigned(self, tag):
        """
        return true if the give tag is currently assigned to a version
        of this product.
        """
        return tag in self.tags

    def getTaggedProduct(self, tag, dbpath=None, flavor=None):
        """
        return the Product with the assigned tag name of None if not found

        @param tag : the desired tag name
        @param dbpath    a database path to set on the returned product
        @param flavor    a platform flavor to set on the returned product
        @return Product
        """
        if isinstance(tag, eups.tags.Tag):
            tag = str(tag)

        if self.isTagAssigned(tag):
            return self.getProduct(self.tags[tag], dbpath, flavor)
        else:
            return None

    def export(self, dbpath=None, flavor=None):
        """
        return all Products as a dictionary suitable for persisting.  Each
        key is a version name and its value is a Product describing it.
        @param dbpath    a database path to set for each product exported
        @param flavor    a platform flavor to set for each product exported
        @return dictionary :
        """
        out = {}
        for vers in self.versions.keys():
            out[vers] = self.getProduct(vers, dbpath, flavor)
        return out

    def import_(self, versions):
        """
        import products into this family.
        This will ignore over any products whose name does not match the
        name of this family.  Matching products will overwrite previous
        versions having the same version name.
        @param dictionary versions : the information for versions to be add
                             to this family.  Each key is a version name and
                             its value is a Product instance.
        """
        for vers in versions.keys():
            prod = versions[vers]
            if prod.name == self.name:
                self.addVersion(prod.version, prod.dir, prod.tablefile,
                                prod._table)

    def addVersion(self, version, installdir, tablefile=None, table=None):
        """
        register an installed version.  If the version already exists, it
        will be overwritten.

        @param version :      the name of the version to add
        @param installdir :   the installation directory where the product
                                  is installed.
        @param tablefile :    the path to the dependency table for this
                                  version.  If None, no path is applicable
        @param table :        the dependency table as a Table instance.  If
                                  None, the loading of the Table instance is
                                  deferred.
        """
        if not version:
            msg = "Missing version name while registering new version " + \
                "for product %s: %s"
            raise RuntimeError(msg % (self.name, version))
        self.versions[version] = (installdir, tablefile, table)

    def hasVersion(self, version):
        """
        return true if this family has a requested version registered.

        @param string version : the name of version of interest
        @return bool :   true if the version is registered
        """
        return version in self.versions

    def removeVersion(self, version):
        """
        unregister a version, return false if the version is not found.

        @param string version : the name of the version to unregister
        @return bool :
        """
        if self.hasVersion(version):
            itsTags = [y[0] for y in [x for x in self.versions.items() if x[1] == version]]
            for tag in itsTags:
                self.unassignTag(tag)
            del self.versions[version]
            return True
        else:
            return False

    def assignTag(self, tag, version, file=None):
        """
        assign the given tag to a version of the product.

        @param tag :     the tag name being assigned
        @param version : the name of the version being assigned the tag
        @param file :    the file to record the tagging information to.
        If None, it will not get recorded.
        """
        if not self.hasVersion(version):
            raise ProductNotFound(self.name, version)

        tag = str(tag)
        self.tags[tag] = version

    def unassignTag(self, tag, file=None):
        """
        remove a given tag from this product.  Return false if the tag is
        not assigned to a version of this product.

        @param string tag : the tag to remove from this product
        @param string file : the tagging file to update (i.e. remove)
        @return bool :  false if the tag was not previously assigned
        """
        if tag in self.tags:
            del self.tags[tag]
            return True
        else:
            return False

    def loadTableFor(self, version, table=None):
        """
        cache the parsed contents of the table file.  If table is not None,
        it will be taken as the Table instance representing the already
        parsed contents; otherwise, the table will be loaded from the
        table file path.

        @param version   the version of the product to load
        @param table     an instance of Table to accept as the loaded
                            contents
        """
        try:
            verdata = self.versions[version]
            if not table:
                if not utils.isRealFilename(verdata[1]):
                    return
                if not os.path.exists(verdata[1]):
                    raise TableFileNotFound(verdata[1], self.name, version)
                prod = self.getProduct(version)
                table = Table(verdata[1]).expandEupsVariables(prod)
            self.versions[version] = (verdata[0], verdata[1], table)
        except KeyError:
            raise ProductNotFound(self.name, version)

    def loadTables(self):
        """
        ensure that the tables for all versions have be parsed and cached
        into memory.
        """
        for ver in self.getVersions():
            self.loadTableFor(ver)


from eups import Product
from eups.exceptions import ProductNotFound

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
        self.name = name;

        # a lookup for version-specific information where the keys are the 
        # version names and the values are tuples containing the installation 
        # directory and the dependencies table
        self.versions = {}

        # a lookup of tag assignments where each key is a tag name and its 
        # value is the version name assigned to the tag.
        self.tags = {}

    def getVersions(self):
        """
        return a list containing the verison names in this product family
        """
        return self.versions.keys()

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
            tags = map(lambda item: item[0], 
                       filter(lambda x: x[1]==version, self.tags.items()))
            return Product(self.name, version, flavor, 
                           versdata[0],    # the install directory
                           versdata[1],    # the table file
                           tags, dbpath)
                           
        except KeyError:
            raise ProductNotFound(self.name, version)

    def getTags(self):
        """
        return a list of the tag names assigned to versions in this 
        product family
        """
        return self.tags.keys()

    def isTagAssigned(self, tag):
        """
        return true if the give tag is currently assigned to a version
        of this product.
        """
        return self.tags.has_key(tag);

    def getTaggedProduct(self, tag, dbpath=None, flavor=None):
        """
        return the Product with the assigned tag name of None if not found

        @param tag : the desired tag name
        @param dbpath    a database path to set on the returned product
        @param flavor    a platform flavor to set on the returned product
        @return Product 
        """
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
                self.addVersion(prod.version, prod.dir, prod.table)

    def addVersion(self, version, installdir, table=None):
        """
        register an installed version.  If the version already exists, it 
        will be overwritten.

        @param version :      the name of the version to add
        @param installdir :   the installation directory where the product 
                                  is installed.
        @param table :        the dependency table for this version.  If None,
                                  no table is applicable
        """
        if not version:
            msg = "Missing version name while registering new version " + \
                "for product %s: %s"
            raise RuntimeError(msg % (self.name, version))
        self.versions[version] = (installdir, table)

    def hasVersion(self, version):
        """
        return true if this family has a requested version registered.

        @param string version : the name of version of interest
        @return bool :   true if the version is registered
        """
        return self.versions.has_key(version)

    def removeVersion(self, version):
        """
        unregister a version, return false if the version is not found.

        @param string version : the name of the version to unregister
        @return bool :
        """
        if self.hasVersion(version):
            itsTags = map(lambda y: y[0], 
                       filter(lambda x: x[1]==version, self.versions.items()))
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
            raise ProductNotFound(self.name, version);
        self.tags[tag] = version

    def unassignTag(self, tag, file=None):
        """
        remove a given tag from this product.  Return false if the tag is 
        not assigned to a version of this product.

        @param string tag : the tag to remove from this product
        @param string file : the tagging file to update (i.e. remove)
        @return bool :  false if the tag was not previously assigned
        """
        if self.tags.has_key(tag):
            del self.tags[tag]
            return True
        else:
            return False





# from Table import *
import os
import cPickle

class Product(object):
    """
    a description of a Product as stored in the stack database.

    It is intended that users access the data that describes the product
    via public attributes and even update it as necessary.  The ProductStack
    always returns a copy of this information, so users should not worry 
    about corrupting its internal data.  The public data attributes are:

    name       the product's name
    version    the version name
    dir        product's installation directory path
    table      the product's dependency table
    db         the path to its ups_db database.  If None, the value is not
                  known.  (A Product returned by a ProductStack will always
                  have this set.)  
    flavor     the platform flavor supported.  If None, the value is not 
                  known or is assumed by context.  (A Product returned by a 
                  ProductStack will always have this set.)  
    tags       a list containing the tag names attached to this product
    """

    def __init__(self, name, version, flavor=None, dir=None, table=None, 
                 tags=None, db=None):
        self.name = name
        self.version = version
        self.dir = dir
        self.table = table;
        if not self.table and dir and name:
            table = os.path.join(dir,"ups",name+".table");
            if os.path.exists(table):
                self.table = table
        if not tags:  
            self.tags = []
        else:
            self.tags = list(tags)   # make a copy
        self.db = db
        self.flavor = flavor

    def clone(self):
        """
        return a copy of this product
        """
        return Product(self.name, self.version, self.flavor, self.dir,
                       self.table, self.tags, self.db)

    def __repr__(self):
        return "Product: %s %s" % (self.name, self.version)

    def isTagged(self, tag):
        """
        return True if this product has been assigned a given tag.
        """
        return tag in self.tags

    def stackRoot(self):
        """
        return the implied root of the product stack where this product
        is registered, or None if it is not clear.
        """
        if self.db is None:
            return None
        if os.path.basename(self.db) == "ups_db":
            return os.path.dirname(self.db)
        return self.db

    def persist(self, fd):
        cPickle.dump(self, fd, protocol=2);

    # @staticmethod   # requires python 2.4
    def unpersist(fd):
        """return a Product instance restored from a file persistence"""
        return cPickle.load(fd);
    unpersist = staticmethod(unpersist)  # should work as of python 2.2

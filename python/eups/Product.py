# from Table import *
import os
import cPickle
import table as mod_table
import utils
from exceptions import TableFileNotFound

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
    tablefile  the path to the product's dependency table
    db         the path to its ups_db database.  If None, the value is not
                  known.  (A Product returned by a ProductStack will always
                  have this set.)  
    flavor     the platform flavor supported.  If None, the value is not 
                  known or is assumed by context.  (A Product returned by a 
                  ProductStack will always have this set.)  
    tags       a list containing the tag names attached to this product

    Two additional attributes should be accessed via functions:

    stackRoot()   the assumed path to the product stack that this product is
                     a part of.  It is derived from product.db.
    getTable()    the loaded Table instance for this product.  This will 
                     load the Table on the fly from the path given by the 
                     tablefile attribute (via tableFileName()).  

    Finally, the tableFileName() returns the assumed path to the table file.
    Normally, this is the value of the tablefile attribute; however, if the
    attribute is None, a default name is returned based on the dir attribute.
    """

    def __init__(self, name, version, flavor=None, dir=None, table=None, 
                 tags=None, db=None):
        self.name = name
        self.version = version
        self.dir = dir

        if not table and dir and name:
            tablefile = os.path.join(dir,"ups",name+".table");
            if os.path.exists(tablefile):
                table = tablefile
        self.tablefile = None
        self._table = None
        if isinstance(table, mod_table.Table):
            self._table = table
        else:
            self.tablefile = table
        

        if not tags:  
            self.tags = []
        else:
            self.tags = list(tags)   # make a copy
        self.db = db
        self.flavor = flavor

        # this is a reference to a ProductStack that will be set when
        # this instance is extracted from a ProductStack cache.  It is used
        # by getTable() to signal the cache to add a table instance for this
        # product.  
        self._prodStack = None

    def clone(self):
        """
        return a copy of this product
        """
        return Product(self.name, self.version, self.flavor, self.dir,
                       self.tablefile, self.tags, self.db)

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

    def tableFileName(self):
        """
        return the assumed path to the product's table file.  This is 
        self.tablefile unless it is null; in this case, a default path 
        based on self.dir (namely, {self.dir}/ups/{self.name}.table) is 
        returned.  None is returned if the product is known
        not to have an associated table file.
        """
        if self.tablefile is None:
            if utils.isRealFilename(self.dir) and self.name:
                return os.path.join(self.dir, "ups", "%s.table" % self.name)
        elif utils.isRealFilename(self.tablefile):
            return self.tablefile
        return None

    def getTable(self):
        """
        return an in-memory instance of the product table.  This will be
        loaded from the path returned by tableFileName() (and cached for 
        subsequent accesses) on-the-fly.  None is returned if this product
        is known not to have a table file.  A TableError is raised if the
        table file cannot be loaded:  if it cannot be found, a 
        TableFileNotFound is raised; if it contains unparsable errors, a 
        BadTableContent is raised.  
        """
        if not self._table:
            tablepath = self.tableFileName()
            if tablepath is None:
                return None

            if not os.path.exists(tablepath):
                raise TableFileNotFound(tablepath, self.name, self.version,
                                        self.flavor)
            self._table = mod_table.Table(tablepath)

            if self._prodStack and self.name and self.version and self.flavor:
                # pass the loaded table back to the cache
                try:
                    self._prodStack.loadTableFor(self.name, self.version, 
                                                 self.flavor, self._table)
                except ProductNotFound:
                    pass
                                        
        return self._table

    def persist(self, fd):
        cPickle.dump(self, fd, protocol=2);

    # @staticmethod   # requires python 2.4
    def unpersist(fd):
        """return a Product instance restored from a file persistence"""
        return cPickle.load(fd);
    unpersist = staticmethod(unpersist)  # should work as of python 2.2

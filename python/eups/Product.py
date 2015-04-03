# from Table import *
from __future__ import absolute_import, print_function
import os
import re
try:
    import cPickle as pickle
except ImportError:
    import pickle
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser
from . import table as mod_table
from . import utils
from .exceptions import ProductNotFound, TableFileNotFound

macrore = { "PROD_ROOT": re.compile(r"^\$PROD_ROOT\b"),
            "PROD_DIR":  re.compile(r"^\$PROD_DIR\b"),
            "FLAVOR":    re.compile(r"\$FLAVOR\b"),
            "UPS_DIR":   re.compile(r"^\$UPS_DIR\b"),
            "UPS_DB":    re.compile(r"^\$UPS_DB\b")     }

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

    LocalVersionPrefix = "LOCAL:"

    def __init__(self, name, version, flavor=None, dir=None, table=None, 
                 tags=None, db=None, noInit=None, ups_dir=None):
        if (name and not utils.is_string(name)) or isinstance(dir,bool) or noInit is not None:
            import inspect
            caller = (inspect.stack(context=2))[1]
            reason = "unknown"
            if name and not utils.is_string(name):
                reason = "name is '{0}' ({1}) and not str".format(name, type(name))
            elif isinstance(dir, bool):
                reason = "dir is bool"
            elif noInit is not None:
                reason = "noInit is not None"

            print("Note: detected use of deprecated API at {0}:{1} ({2}) (reason: {3});"
                  " use Eups.getProduct() instead.".format(caller[1], caller[2], caller[3], reason),
                  file=utils.stdwarn)
            name = version
            version = flavor
            if not version:
                version = "none"

        self.name = name
        self.version = version
        self.ups_dir = ups_dir

        if not dir:
            dir = self._decode_dir(self.version)
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

    def __hash__(self):                 # needed for set operations (such as toplogicalSort)
        return (hash(self.name) ^
                hash(self.version) ^
                hash(self.flavor))

    def __eq__(self, rhs):
        return rhs and (self.name == rhs.name and
                        self.version == rhs.version and
                        self.flavor == rhs.flavor)                

    def __ne__(self, rhs):
        return not (self == rhs)

    def __lt__(self, rhs):
        return (self.name, self.version, self.flavor) < (rhs.name, rhs.version, rhs.flavor)

    @classmethod
    def _decode_dir(self, version):
        if version is not None and version.startswith(self.LocalVersionPrefix):
            version = utils.decodePath(version)
            return version[len(self.LocalVersionPrefix):]
        else:
            return None

    @classmethod
    def _encode_dir(self, productDir):
        return self.LocalVersionPrefix + utils.encodePath(productDir)

    def resolvePaths(self, strict=False):
        """
        Update the internal data so that all paths in the product data
        are resolved to absolute paths.  This is desirable for caching
        this product in a ProductStack (ProductStack.addProduct() calls 
        this internally).  

        Path resolution is carried out according to the following rules:
      *  A value of "none" indicates that the path explicitly does not have
           a logical value.  For example, for table_file, the product does not
           have a table file to set up the product.  For productDir, the 
           product is not formally installed anywhere.
      *  A value of None indicates that the path can be reset to a normalized
           default when written out.
      *  Any path can be absolutely specified (though they may get normalized
           when written out).
      *  If productDir is relative, it is assumed to be relative to the base
           directory of the software stack (not known to this class).
      *  If the ups_dir is relative, it is assumed to be relative to the 
           product installation directory, productDir.
      *  If the table file is relative, it is assumed to be relative to the
           ups_dir directory.  If the ups_dir is "none" or None, then the 
           table file is relative to productDir.
      *  The path may include symbolic path "macro"--a path
           with a context-specific value.  These macros have the form $name,
           and most have restrictions on where in the value it can appear
           (i.e. all but $FLAVOR may only appear at the start of the path).
           Some restrictions also apply as to within which path a macro may 
           appear.
           The supported macros are:
              $PROD_ROOT -- the absolute path to the default root directory 
                            where products are installed by default--i.e. 
                            the value of the EUPS path directory where it 
                            is registered.  This can only appear at the 
                            start of the path.
              $FLAVOR    -- the value of the product's flavor.
              $PROD_DIR  -- the fully resolved value of productDir; this 
                            macro cannot appear in the productDir value.
                            This can only appear at the start of the path.
              $UPS_DIR   -- the fully resolved value of ups_dir.
                            This can only appear at the start of the path.
              $UPS_DB    -- the path to the EUPS database directory path 
                            (which typically ends with the name "ups_db").
                            This can only appear at the start of the path.

        @param strict    raise an exception if the non-none product 
                           directory or table file cannot be resolved.  
        """
        root = self.stackRoot()
        macrodata = { "FLAVOR":    self.flavor,
                      "PROD_ROOT": root,
                      "UPS_DB":    self.db          }

        if utils.isRealFilename(self.dir) and not os.path.isabs(self.dir):
            if not self.dir.startswith("$PROD_") and \
               not self.dir.startswith("$UPS_") and not root in (None, "none"):
                self.dir = os.path.join(root, self.dir)
            self.dir = self._resolve(self.dir, macrodata)
            if strict and not os.path.isabs(self.dir):
                raise ValueError("product dir unresolvable: " + self.dir)
            macrodata["PROD_DIR"] = self.dir

        if utils.isRealFilename(self.ups_dir) and not os.path.isabs(self.ups_dir):
            if not self.ups_dir.startswith("$PROD_") and \
               not self.ups_dir.startswith("$UPS_") and not self.dir in (None, "none"):
                self.ups_dir = os.path.join(self.dir, self.ups_dir)
            self.ups_dir = self._resolve(self.ups_dir, macrodata)
#            if strict and not os.path.isabs(self.dir):
#                raise ValueError("product ups dir unresolvable: "+self.ups_dir)
            macrodata["UPS_DIR"] = self.ups_dir
            
        if self.tablefile is None and self.name and \
           (utils.isRealFilename(self.dir) or \
            utils.isRealFilename(self.ups_dir)):
            self.tablefile = "%s.table" % self.name
        if utils.isRealFilename(self.tablefile) and not os.path.isabs(self.tablefile):
            if not self.tablefile.startswith("$PROD_") and \
               not self.tablefile.startswith("$UPS_"):

                if self.ups_dir is None and utils.isRealFilename(self.dir):
                    self.ups_dir = os.path.join(self.dir, "ups")

                if utils.isRealFilename(self.ups_dir):
                    ntable = os.path.join(self.ups_dir, self.tablefile)
                    #
                    # OK, be nice.  Look relative to eupsPathDir too.  This is needed due to
                    # malformed .version files (fixed in r10329)
                    #
                    if root:
                        n2table = os.path.join(root, self.tablefile)
                    
                    if os.path.exists(ntable):
                        self.tablefile = ntable
                    elif root and os.path.exists(n2table):
                        self.tablefile = n2table
                    else:
                        self.tablefile = ntable # Hack for now to make tests pass when table file doesn't exist

                elif utils.isRealFilename(self.dir):
                    if self.ups_dir is None:
                        self.tablefile = os.path.join(self.dir,"ups",
                                                      self.tablefile)
                    else:
                        self.tablefile = os.path.join(self.dir,
                                                      self.tablefile)

            self.tablefile = self._resolve(self.tablefile, macrodata)
            if strict and not os.path.isabs(self.tablefile):
                raise ValueError("product table file unresolvable: " + 
                                 self.tablefile)

        # one last try:
        if utils.isRealFilename(self.dir) and self.dir.find('$') >= 0:
            self.dir = self._resolve(self.dir, macrodata, skip="PROD_DIR")
            macrodata["PROD_DIR"] = self.dir
        if utils.isRealFilename(self.tablefile) and \
           self.tablefile.find('$') >= 0:
            self.tablefile = self._resolve(self.tablefile, macrodata)

        return self

    def _resolve(self, value, data, skip=None):
        if not value: return value

        dosub = list(data.keys())
        if skip:
            if utils.is_string(skip):
                skip = skip.split()
            dosub = [n for n in dosub if n not in skip]

        for name in dosub:
            if name in macrore and data[name]:
                value = macrore[name].sub(data[name], value)

        return value

    def canonicalizePaths(self):
        """
        convert any internal absolute paths to ones relative to a root 
        directories.  This is appropriate for storage into database version
        files: without absolute paths, the files can be moved to another place
        on a filesystem without invalidating internal data. 
        @param strict    raise an exception if an absolute path remains.
        """
        sl = os.path.sep
        root = self.stackRoot()
        if not utils.isRealFilename(root):
            return self

        if self.tablefile is None:
            if self.name:  
                self.tablefile = self.name+".table"
            if self.ups_dir is None and utils.isRealFilename(self.dir):
                self.ups_dir = os.path.join(self.dir, "ups")
            

        # transform tablefile
        if utils.isRealFilename(self.tablefile) and os.path.isabs(self.tablefile):
            if utils.isRealFilename(self.db) and \
                 self.tablefile.startswith(self.db):
                if self.ups_dir is None:
                    self.ups_dir = os.path.join("$UPS_DB", 
                               os.path.dirname(self.tablefile)[len(self.db)+1:])
                    self.tablefile = os.path.basename(self.tablefile)
                else:
                    self.tablefile = os.path.join("$UPS_DB", 
                                                  self.ups_dir[len(self.db)+1:])
            elif utils.isRealFilename(self.ups_dir):
                if self.tablefile.startswith(self.ups_dir+sl):
                    # a relative tablefile path is relative to ups_dir, 
                    # if set.
                    self.tablefile = self.tablefile[len(self.ups_dir)+1:]
            elif utils.isRealFilename(self.dir) and \
                 self.tablefile.startswith(self.dir+sl):
                # when ups_dir is not set, relative tablefile is relative to 
                # the product dir
                self.tablefile = self.tablefile[len(self.dir)+1:]

        # transform ups_dir
        if utils.isRealFilename(self.ups_dir) and os.path.isabs(self.ups_dir):
            if utils.isRealFilename(self.dir) and self.ups_dir.startswith(self.dir+sl):
                # relative ups_dir path is relative to product dir
                self.ups_dir = self.ups_dir[len(self.dir)+1:]
            elif utils.isRealFilename(self.dir) and self.ups_dir == self.dir:
                self.ups_dir = "none"
            elif utils.isRealFilename(self.db) and self.ups_dir.startswith(self.db+sl):
                self.ups_dir = os.path.join("$UPS_DB", 
                                            self.ups_dir[len(self.db)+1:])
            elif utils.isRealFilename(self.db) and self.ups_dir == self.db:
                self.ups_dir = "$UPS_DB"
                                                              
        # transform installation dir
        if utils.isRealFilename(self.dir) and self.dir.startswith(root+sl):
            # relative ups_dir path is relative to stack root
            self.dir = self.dir[len(root+sl):]

        return self

    def clone(self):
        """
        return a copy of this product
        """
        out = Product(self.name, self.version, self.flavor, self.dir,
                      self.tablefile, self.tags, self.db, ups_dir=self.ups_dir)
        if self._table:
            out._table = self._table
        return out

    def __repr__(self):
        return "Product: %s %s" % (self.name, self.version)

    def isTagged(self, tag):
        """
        return True if this product has been assigned a given tag.  

        Note that if the input tag is a string, then an exact string match to a
        string tag name listed in this product instance (in self.tags) is 
        required to return True.  If the input is a instance of Tag, then the 
        match is controlled by the Tag class's __eq__() function.  This currently 
        means that an unqualified tag name listed in this product.  
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
        returned).  None is returned if the product is known
        not to have an associated table file.
        """
        if self.tablefile is not None and \
           not utils.isRealFilename(self.tablefile):
            return None
        elif self.tablefile is None or not os.path.isabs(self.tablefile):
            clone = self.clone().resolvePaths()
            if utils.isRealFilename(clone.tablefile):
                return clone.tablefile
        return self.tablefile

    def getTable(self, addDefaultProduct=None, quiet=False, verbose=0):
        """
        return an in-memory instance of the product table.  This will be
        loaded from the path returned by tableFileName() (and cached for 
        subsequent accesses) on-the-fly.  None is returned if this product
        is known not to have a table file.  A TableError is raised if the
        table file cannot be loaded:  if it cannot be found, a 
        TableFileNotFound is raised; if it contains unparsable errors, a 
        BadTableContent is raised.  
        """
        if quiet:
            verbose -= 2

        if not self._table:
            tablepath = self.tableFileName()
            if tablepath is None:
                return None

            if not os.path.exists(tablepath):
                raise TableFileNotFound(tablepath, self.name, self.version,
                                        self.flavor)
            self._table = mod_table.Table(tablepath, self,
                                          addDefaultProduct=addDefaultProduct, verbose=verbose,
                                          ).expandEupsVariables(self, quiet)

            if self._prodStack and self.name and self.version and self.flavor:
                # pass the loaded table back to the cache
                try:
                    self._prodStack.loadTableFor(self.name, self.version, 
                                                 self.flavor, self._table)
                except ProductNotFound:
                    pass
                                        
        return self._table

    def getConfig(self, section="DEFAULT", option=None, getType=None):
        """Return the product's ConfigParser, which will be empty if the file doesn't exist"""
        
        cfgFile = os.path.join(self.dir, "ups", "%s.cfg" % self.name)
        config = ConfigParser({"filename" : cfgFile})
        config.read(cfgFile)            # cfgFile need not exist
        #
        # Add default values
        #
        for s, o, val in [("distrib", "binary", True),]:
            if not config.has_option(s, o):
                if not config.has_section(s):
                    config.add_section(s)
                config.set(s, o, str(val))

        if option:
            try:
                if getType == bool:
                    return config.getboolean(section, option)
                elif getType == float:
                    return config.getfloat(section, option)
                elif getType == int:
                    return config.getint(section, option)
                else:
                    return config.get(section, option)
            except Exception as e:
                raise RuntimeError("Processing %s: %s" % (cfgFile, e))

        return config

    # this replaces from initFromDirectory()
    # @staticmethod   # requires python 2.4
    def createLocal(productName, productDir, flavor=None, checkForTable=True, tablefile=None):
        localDir = Product._decode_dir(productDir)
        if localDir:
            productDir = localDir

        if not os.path.isdir(productDir):
            return None

        out = Product(productName, Product._encode_dir(productDir),
                      flavor, productDir)
        out.db = "(none)"
        out.tablefile = tablefile
        if checkForTable:
            out.tablefile = out.tableFileName()
            if not os.path.exists(out.tablefile):
                out.tablefile = "none"
        return out
    createLocal = staticmethod(createLocal)  # should work as of python 2.2


    def envarDirName(self):
        return utils.dirEnvNameFor(self.name)

    def envarSetupName(self):
        return utils.setupEnvNameFor(self.name)

    def extraProductDir(self):
        """Return the full path to the extra product_dir"""
        return os.path.join(self.db, utils.extraDirPath(self.flavor, self.name, self.version))

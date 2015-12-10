import os, sys, re
from .VersionFile import VersionFile
from .ChainFile import ChainFile
from eups.utils import isRealFilename, isDbWritable
import eups.tags
from eups.Product import Product
from eups.exceptions import UnderSpecifiedProduct, ProductNotFound
from eups.exceptions import TableError

versionFileExt = "version"
versionFileTmpl = "%s." + versionFileExt
versionFileRe = re.compile(r'^(\w.*)\.%s$' % versionFileExt)
tagFileExt = "chain"
tagFileTmpl = "%s." + tagFileExt
tagFileRe = re.compile(r'^(\w.*)\.%s$' % tagFileExt)

try:
    _databases
except NameError:
    _databases = {}                     # the actual Database objects, making Database(XXX) a singleton 

def Database(dbpath, userTagRoot=None, defStackRoot=None, owner=None):
    """Return the singleton _Database object identified by this function call's arguments
    
        @param dbpath        the full path to the directory (usually called 
                                "ups_db") containing a EUPS software database.
        @param userTagRoot   a full path to a user-writable directory where 
                                user tag assignment may be recorded.  The 
                                file/directory structure maintained will be 
                                the same assumed by dbpath, though only 
                                chain files will be consulted.  If None, 
                                user tags will not be accessible or assignable.
        @param defStackRoot  the default path for product stack root directory.
                                When product install directories are specified
                                with relative paths, they will be assumed to be
                                relative to this root directory.  If None, 
                                it defaults to the parent directory of dbpath.
                                Specify an empty string ("") is the default is 
                                a bad assumption.
        @param owner         the owner of the userTagRoot
        """

    if defStackRoot is None:
        defStackRoot = os.path.dirname(dbpath)

    key = (dbpath, defStackRoot)
    if key not in _databases:
        _databases[key] = _Database(dbpath, defStackRoot)

    if userTagRoot:
        _databases[key].addUserTagDb(userTagRoot, defStackRoot, userId=owner)

    return _databases[key]

class _Database(object):
    """
    An interface to the product database recorded on disk.  This interface will
    enforce restrictions on product names, flavors, and versions.

    A database is represented on disk as a collection of files with a known 
    directory structure.  (The root directory is typically called "ups_db"; 
    however, but its name does not matter to this implementation.)  The 
    root directory contains a subdirectory named after each declared product.

    Each product name subdirectory contains one or more "version files", each
    in turn containing the product data (excluding tag assignments) for a 
    particular declared version of the product.  The version file has a name
    composed of the version string appended by the ".version" extension.  The
    format is known to the VersionFile class.  The version file will define
    one or more flavors of its version of the product.  

    The product name subdirectory may also contain "chain files"; these 
    record the assignment of tags to versions of a product.  A chain file
    has a name composed of a tag name appended by the ".chain" extension.  
    The format of the chain file is known to the ChainFile class.  Note that
    tags are assigned to a version on a per-flavor basis; that is, a tag 
    may be assigned to one flavor of the version but not all.  The chain
    file, thus, indicates which flavors are assigned the tag.

    The Database class understands a notion of "user" tags defined from its
    perspective as tag assignments that are recorded under a separate 
    directory (provided by the constructor).  Methods that take a tag name as 
    input will recognize it as a user tag if the name has the "user:" prefix.
    The structure of the separate user tag directory is the same as the 
    main database directory with the assignments recorded as chain files.
    (Any version files there will be ignored.)

    @author Raymond Plante
    """

    def __init__(self, dbpath, defStackRoot):
        """
        create an instance of a database; see Database() for details"""

        # path to the database directory (ups_db)
        self.dbpath = dbpath
        self.defStackRoot = defStackRoot

        self.addUserTagDb(None, defStackRoot)

    def addUserTagDb(self, userTagRoot, upsdb, userId=None):
        """Add a user tag database for products in upsdb; userId == None means me"""

        try:
            self._userTagDbs
        except AttributeError:
            self._userTagDbs = {}

        if upsdb not in self._userTagDbs:
            self._userTagDbs[upsdb] = {}
            self._userTagDbs[upsdb]["__keys"] = [] # .keys() in the order they were inserted
            
        if userId not in self._userTagDbs[upsdb]:
            self._userTagDbs[upsdb]["__keys"].append(userId) # keep keys in order
        self._userTagDbs[upsdb][userId] = userTagRoot

    def _getUserTagDb(self, userId=None, upsdb=None, values=False):
        """Add a user tag database for products in pdir; userId == None means me"""
        if not upsdb:
            upsdb = self.defStackRoot

        if values:
            return [self._userTagDbs[upsdb][k] for k in self._userTagDbs[upsdb]["__keys"]]
        else:
            return self._userTagDbs[upsdb][userId]

    def _productDir(self, productName, dbdir=None):
        if not dbdir:  dbdir = self.dbpath
        return os.path.join(dbdir, productName)

    def _versionFile(self, productName, version):
        return self._versionFileInDir(self._productDir(productName), version)

    def _tagFile(self, productName, tag):
        return self._tagFileInDir(self._productDir(productName), tag)

    def _versionFileInDir(self, dir, version):
        return os.path.join(dir, versionFileTmpl % version)

    def _tagFileInDir(self, dir, tag):
        return os.path.join(dir, tagFileTmpl % tag)

    def _findVersionFile(self, productName, version):
        """
        find a product's version file or null product is not declared.
        """
        if version:
            out = self._versionFile(productName, version)
            if os.path.exists(out):
                return out

        return None

    def isWritable(self):
        """
        return true if the user has write permission for this database
        """
        return eups.utils.isDbWritable(self.dbpath)

    def findProduct(self, name, version, flavor):
        """
        find the fully specified declared product given its name, version, 
        and platform flavor, or None if product is not declared.

        @param name :     the name of the desired product
        @param version :  the desired version of the product
        @param flavor :   the desired platform flavor
        @return Product : the matched product or None if not found
        """
        vfile = self._findVersionFile(name, version)
        if vfile is None:
            return None

        verdata = VersionFile(vfile, name, version)
        product = None
        try:
            product = verdata.makeProduct(flavor, self.defStackRoot, 
                                          self.dbpath)
            product.tags = self.findTags(name, version, flavor)
        except ProductNotFound:
            return None

        return product
        
    def findTags(self, productName, version, flavor):
        """
        return a list of tags for a given product.  An empty list is 
        returned if no tags are assigned.  ProductNotFound is raised if 
        no version of the product is declared.
        @param productName : the name of the desired product
        @param version :     the desired version of the product
        @param flavor :      the desired platform flavor
        """
        pdir = self._productDir(productName)
        if not os.path.exists(pdir):
            raise ProductNotFound(productName, version, flavor, self.dbpath)

        tags = self._findTagsInDir(pdir, productName, version, flavor)
        if self._getUserTagDb():
            udir = self._productDir(productName, self._getUserTagDb())
            if os.path.isdir(udir):
                tags.extend(map(lambda t: "user:"+t, 
                                self._findTagsInDir(udir, productName, 
                                                    version, flavor)))

        return tags

    def _findTagsInDir(self, dir, productName, version, flavor):
        # look tag assignments via chain files in a given directory

        tagFiles = filter(lambda x: not x.startswith('.'), os.listdir(dir))
        
        tags = []
        for file in tagFiles:
            mat = tagFileRe.match(file)
            if not mat:
                continue

            tag = mat.group(1)
            cf = ChainFile(os.path.join(dir,file), productName, tag)
            if cf.getVersion(flavor) == version:
                tags.append(tag)

        return tags

    def findProductNames(self):
        """
        return a list of the names of all products declared in this database
        """
        dirs = filter(lambda z: os.path.isdir(os.path.join(self.dbpath,z)), 
                      os.listdir(self.dbpath))

        out = []
        for dir in dirs:
            for file in os.listdir(os.path.join(self.dbpath,dir)):
                if versionFileRe.match(file):
                    out.append(dir)
                    break
        return out
        

    def findVersions(self, productName):
        """
        return a list of the versions currently declared for a given product
        An empty list is returned if not products by this name are declared.

        @param string productName : the name of the product to find
        @return string[] :
        """
        versions = []
        pdir = self._productDir(productName)
        if not os.path.exists(pdir):
            return versions

        for file in os.listdir(pdir):
            mat = versionFileRe.match(file)
            if mat: versions.append(mat.group(1))

        return versions
        
    def findFlavors(self, productName, versions=None):
        """
        return a list of flavors supported for the given product.  An 
        empty list is returned if the product is not declared or the 
        given version is not declared.

        @param productName : the name of the product to fine
        @param versions :    the versions to search for.  If None, all 
                                  versions will be considered.
        @return string[] :
        """
        if versions is None:
            versions = self.findVersions(productName)

        if not isinstance(versions, list):
            versions = [versions]

        out = []
        for version in versions:
            vfile = self._versionFile(productName, version)
            vfile = VersionFile(vfile, productName, version)
            flavors = vfile.getFlavors()
            for f in flavors:
                if f not in out:  out.append(f)

        return out
            

    def findProducts(self, name, versions=None, flavors=None):
        """
        return a list of Products matching the given inputs

        @param name :     the name of the desired product
        @param versions : the desired versions.  If versions is None, 
                            return all declared versions of the product.
        @param flavors :  the desired flavors.  If None, return matching 
                            products of all declared flavors.
        @return Product[] : a list of the matching products
        """
        if versions is None:
            versions = self.findVersions(name)

        if not isinstance(versions, list):
            versions = [versions]

        if flavors is not None and not isinstance(flavors, list):
            flavors = [flavors]

        out = {}
        for vers in versions:
            vfile = self._versionFile(name, vers)
            if not os.path.exists(vfile):
                continue
            vfile = VersionFile(vfile, name, vers)
                                
            flavs = flavors
            declared = vfile.getFlavors()
            if flavs is None:  flavs = declared
            out[vers] = {}
            for f in flavs:
                if f in declared:
                    out[vers][f] = vfile.makeProduct(f, self.defStackRoot, 
                                                     self.dbpath)

        if len(out.keys()) == 0:
            return []

        pdir = self._productDir(name)
        if not os.path.exists(pdir):
          raise RuntimeError("programmer error: product directory disappeared")

        # add in the tags 
        for tag, vers, flavor in self.getTagAssignments(name):
            try: 
                out[vers][flavor].tags.append(tag)
            except KeyError:
                pass

#  not sure why this doesn't work:
#        out = reduce(lambda x,y: x.extend(y), 
#                     map(lambda z:  z.values(), out.values()))
#        out.sort(_cmp_by_verflav)
#
#  replaced with moral equivalent:
#                          
        v = map(lambda z:  z.values(), out.values())
        x = v[0]
        for y in v[1:]:  x.extend(y)
        x.sort(_cmp_by_verflav)
        return x

    def getTagAssignments(self, productName, glob=True, user=True):
        """
        return a list of tuples of the form (tag, version, flavor) listing
        all of the tags assigned to the product.
        @param productName     the name of the product
        @param glob            if true (default), include the global tags
        @param user            if true (default), include the user tags
        """
        out = []
        loc = [None, None]
        if glob:  loc[0] = self._productDir(productName) 
        if user and self._getUserTagDb():
            loc[1] = self._productDir(productName, self._getUserTagDb())

        tgroup = ""
        for i in xrange(len(loc)):
            if not loc[i]: continue
            if i > 0:  
                tgroup = "user:"
                if not os.path.exists(loc[i]):
                    continue

            for file in os.listdir(loc[i]):
                mat = tagFileRe.match(file)
                if mat: 
                    tag = mat.group(1)
                    file = ChainFile(os.path.join(loc[i],file), productName,tag)
                    for flavor in file.getFlavors():
                        vers = file.getVersion(flavor)
                        out.append( (tgroup+tag, vers, flavor) )

        return out

    def isDeclared(self, productName, version=None, flavor=None):
        """
        return true if a product is declared.

        @param productName : the name of the product to search for
        @param version :     a specific version to look for.  If None, 
                               return true if any version of this product 
                               is available.  
        @param flavor :      a specific platform flavor to look for.  If 
                               None, return true if any flavor is supported 
                               by the product.  
        """
        pdir = self._productDir(productName)
        if not os.path.exists(pdir):
            return False

        if version is None:
            if flavor is None:  
                return True

            vfiles = os.listdir(pdir)
            for file in vfiles:
                if (versionFileRe.match(file)):
                    file = VersionFile(os.path.join(pdir,file))
                    vers = file.version
                    if file.hasFlavor(flavor):
                        return True

            return False
        else:
            file = self._versionFileInDir(pdir, version)
            if not os.path.exists(file):
                return False
            if flavor is None:
                return True
            file = VersionFile(file)
            return file.hasFlavor(flavor)
            

    def declare(self, product):
        """
        declare the given product.  If a table file is not specified, a 
        default one will be searched for (in the ups subdirectory of the 
        install directory).

        @param product : the Product instance to register
        @throws UnderSpecifiedProduct if the name, version, and flavor are
                   not all set
        """
        if not isinstance(product, Product):
            raise RuntimeError("Database.declare(): argument not a Product:" +
                               product)
        if not product.name or not product.version or not product.flavor:
            raise UnderSpecifiedProduct(
              msg="Product not fully specified: %s %s %s" 
                   % (str(product.name), str(product.version),
                      str(product.flavor))
            )

        prod = product.clone().canonicalizePaths()

        tablefile = prod.tablefile
        if not tablefile:
            tablefile = prod.tableFileName()
            if not tablefile or not os.path.exists(tablefile):
                raise TableFileNotFound(prod.name, prod.version, prod.flavor, 
                                        msg="Unable to located a table file in default location: " + tablefile)

        # set the basic product information
        pdir = self._productDir(prod.name)
        vfile = self._versionFileInDir(pdir, prod.version)
        versionFile = VersionFile(vfile, prod.name, prod.version)
        versionFile.addFlavor(prod.flavor, prod.dir, tablefile, prod.ups_dir)

        # seal the deal
        if not os.path.exists(pdir):
            os.mkdir(pdir)

        if prod.dir:
            trimDir = prod.stackRoot()
            if trimDir and not os.path.exists(trimDir):
                trimDir = None
                
        versionFile.write(trimDir)

        # now assign any tags
        for tag in prod.tags:
            self.assignTag(tag, prod.name, prod.version, prod.flavor)

    def undeclare(self, product):
        """
        undeclare the given Product.  Only the name, version, and flavor 
        will be paid attention to.  False is returned if the product was 
        not found in the database.

        @param product : the Product instance to undeclare.
        @return bool : False if nothing was undeclared
        @throws UnderSpecifiedProduct if the name, version, and flavor are
                   not all set
        """
        if not isinstance(product, Product):
            raise RuntimeError("Database.declare(): argument not a Product: " +
                               product)
        if not product.name or not product.version or not product.flavor:
            raise UnderSpecifiedProduct(
                msg="Product not fully specified: %s %s %s" 
                    % (str(product.name), str(product.version),
                       str(product.flavor))
            )

        pdir = self._productDir(product.name)
        vfile = self._versionFileInDir(pdir, product.version)
        if not os.path.exists(vfile):
            return False

        versionFile = VersionFile(vfile)
        if versionFile.hasFlavor(product.flavor):
            # unassign tags associated with this product
            tags = self.findTags(product.name, product.version, product.flavor)
            for tag in tags:
                self.unassignTag(tag, product.name, product.flavor)

        changed = versionFile.removeFlavor(product.flavor)
        if changed:  versionFile.write()

        # do a little clean up: if we got rid of the version file, try 
        # deleting the directory
        if not os.path.exists(vfile):
            try:
                os.rmdir(pdir)
            except:
                pass

        return changed

    def getChainFile(self, tag, productName, searchUserDB=False):
        """
        return the ChainFile for the version name of the product that has the given tag assigned
        to it.  None is return if the tag is not assigned to any version.
        ProductNotFound is raised if no version of the product is declared.
        @param tag          the string name for the tag.  A user tag must be
                              prepended by a "user:" label to be found
        @param productName  the name of the product
        """
        pdir = self._productDir(productName)
        if not os.path.exists(pdir):
            raise ProductNotFound(productName, stack=self.dbpath);

        if isinstance(tag, str):
            tag = eups.tags.Tag(tag)

        pdirs = []
        if searchUserDB and tag.isUser():
            for d in self._getUserTagDb(values=True):
                if d:
                    pdirs.append(self._productDir(productName, d))
        else:
            pdirs.append(pdir)

        for pdir in pdirs:
            tfile = self._tagFileInDir(pdir, tag.name)
            if os.path.exists(tfile):
                return ChainFile(tfile)

        return None
        
    def getTaggedVersion(self, tag, productName, flavor, searchUserDB=True):
        """
        return the version name of the product that has the given tag assigned
        to it.  None is returned if the tag is not assigned to any version.
        ProductNotFound is raised if no version of the product is declared.
        @param tag          the string name for the tag.  A user tag must be
                              prepended by a "user:" label to be found
        @param productName  the name of the product
        @param flavor       the flavor for the product
        """

        tf = self.getChainFile(tag, productName, searchUserDB=searchUserDB)
        if tf:
            return tf.getVersion(flavor)
        else:
            return None

    def assignTag(self, tag, productName, version, flavors=None):
        """
        assign a tag to a given product.

        @param tag :         the name of the tag to assign.  If the name is 
                               prepended with the "user:" label, the assignment
                               will be recorded in the user tag area.
        @param productName : the name of the product getting the tag
        @param version :     the version to tag 
        @param flavors :     the flavors of the product to be tagged.  
                                If None, tag all available flavors.  
        """

        if isinstance(tag, str):
            tag = eups.tags.Tag(tag)

        vf = VersionFile(self._versionFile(productName, version))
        declaredFlavors = vf.getFlavors()
        if len(declaredFlavors) == 0:
            raise ProductNotFound(productName, version)

        if flavors is None:
            flavors = list(declaredFlavors)
        elif not isinstance(flavors, list):
            flavors = [flavors]
        else:
            flavors = list(flavors)  # make a copy; we're gonna mess with it
        if len(flavors) == 0:
            flavors = list(declaredFlavors)

        # reduce the list of flavors to ones actually declared
        for i in xrange(len(flavors)):
            flavor = flavors.pop(0)
            if flavor in declaredFlavors and flavor not in flavors:
                flavors.append(flavor)
        if len(flavors) == 0:
            raise ProductNotFound(productName, version, 
                               msg="Requested flavors not declared for %s %s"
                                   % (productName, version))

        if tag.isUser():
            if not self._getUserTagDb():
                raise RuntimeError("Unable to assign user tags (user db not available)")

            pdir = self._productDir(productName, self._getUserTagDb())
            if not os.path.exists(pdir):
                os.makedirs(pdir)
        else:
            pdir = self._productDir(productName)
        
        tfile = self._tagFileInDir(pdir, tag.name)
        tagFile = ChainFile(tfile, productName, tag.name)

        tagFile.setVersion(version, flavors)
        tagFile.write()
            

    def unassignTag(self, tag, productNames, flavors=None):
        """
        unassign a tag from a product

        @param tag :          the tag to unassign
        @param productNames : the names of the products to deassign the 
                                 tag for.  This can be given as a single 
                                 string (for a single product) or as a list
                                 of product names.  If None, the tag will 
                                 be deassigned from all products.  
        @param flavors :      the flavors of the product to deassign tag for.  
                                 If None, deassign the tag for all available 
                                 flavors.
        @return bool : False if tag was not assigned to any of the products.
        """
        dbroot = self.dbpath
        if tag.startswith("user:"):
            dbroot = self._getUserTagDb(upsdb=self.defStackRoot)
            if not dbroot:
                return False
            tag = tag[len("user:"):]

        if not productNames:
            raise RuntimeError("No products names given: " + str(productNames))
        if not isinstance(productNames, list):
            productNames = [productNames]
        if flavors is not None and not isinstance(flavors, list):
            flavors = [flavors]

        unassigned = False
        for prod in productNames:
            tfile = self._tagFileInDir(self._productDir(prod,dbroot), tag)
            if not os.path.exists(tfile):
                continue

            if flavors is None:
                # remove all flavors
                os.remove(tfile)
                unassigned = True
                continue

            tf = ChainFile(tfile)
            changed = False
            for flavor in flavors:
                if tf.removeVersion(flavor):
                    changed = True

            if changed:
                tf.write()
                unassigned = True

        return unassigned

    def isNewerThan(self, timestamp, dbrootdir=None):
        """
        return true if the state of this database is newer than a given time
        NOTE: file timestamps only have a resolution of 1 second!
        @param timestamp    the epoch time, as given by os.stat()
        @param dbrootdir    directory where to look for file times.  If None,
                               defaults to database root.  
        """
        # HACK: If the user is _certain_ that the caches are up-to-date,
        #       allow them to say so. This is a hack to speed up builds
        #       on systems with thousands of products installed
        if os.environ.get("_EUPS_ASSUME_CACHES_UP_TO_DATE", "0") == "1":
            return False

        if not dbrootdir:
            dbrootdir = self.dbpath
        proddirs = map(lambda d: os.path.join(self.dbpath, d), self.findProductNames())

        for prod in proddirs:
            # check the directory mod-time: this will catch recent removal
            # of files from the directory
            if os.stat(prod).st_mtime > timestamp:
                return True

            # We need to do this even if we've checked the parent directory as contents may have changed
            for file in os.listdir(prod):
                mat = versionFileRe.match(file)
                if not mat:  mat = tagFileRe.match(file)
                if not mat:  continue
                file = os.path.join(prod, file)
                if os.stat(file).st_mtime > timestamp:
                    return True

        return False
        
def _cmp_by_verflav(a, b):
    c = _cmp_str(a.version,b.version)
    if c == 0:
        return _cmp_str(a.flavor, b.version)
    return c
    
def _cmp_str(a, b):
    if a < b:  return -1
    if a > b:  return 1
    return 0

    

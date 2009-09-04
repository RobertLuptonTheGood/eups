import os, sys, re
from VersionFile import VersionFile
from ChainFile import ChainFile
from eups.utils import isRealFilename
from eups.Product import Product
from eups.exceptions import UnderSpecifiedProduct, ProductNotFound
from eups.exceptions import TablefileNotFound

versionFileExt = "version"
versionFileTmpl = "%s." + versionFileExt
versionFileRe = re.compile(r'^(\w.*)\.%s$' % versionFileExt)
tagFileExt = "chain"
tagFileTmpl = "%s." + tagFileExt
tagFileRe = re.compile(r'^(\w.*)\.%s$' % tagFileExt)

class Database(object):

    """
    An interface to the product database recorded on disk.  This interface will
    enforce restrictions on product names, flavors, and versions.

    @author Raymond Plante
    """

    def __init__(self, dbpath):
        """
        create an instance of a database.
        @param dbpath    the full path to the directory (usually called 
                            "ups_db") containing a EUPS software database.
        """

        # path to the database directory (ups_db)
        self.dbpath = dbpath

    def _productDir(self, productName):
        return os.path.join(self.dbpath, productName)

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
        out = self._versionFile(productName, version)
        if not os.path.exists(out):
            return None
        return out

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
            product = verdata.makeProduct(flavor)
            product.db = self.dbpath
            product.tags = self.findTags(name, version, flavor)
        except ProductNotFound:
            return None

        return product
        
    def findTags(self, productName, version, flavor):
        """
        return a list of tags for a given product.  An empty list is 
        returned if no tags are assigned.  ProductNotFound is raised if 
        no version of the product is not currently declared.
        """
        pdir = self._productDir(productName)
        if not os.path.exists(pdir):
            raise ProductNotFound(productName, version, flavor, self.dbpath)

        tagFiles = filter(lambda x: not x.startswith('.'), os.listdir(pdir))
        
        tags = []
        for file in tagFiles:
            mat = tagFileRe.match(file)
            if not mat:
                continue

            tag = mat.group(1)
            cf = ChainFile(os.path.join(pdir,file), productName, tag)
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
        @author
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
            vfile = VersionFile(self._versionFile(name, vers),
                                name, vers)
            flavs = flavors
            declared = vfile.getFlavors()
            if flavs is None:  flavs = declared
            out[vers] = {}
            for f in flavs:
                if f in declared:
                    out[vers][f] = vfile.makeProduct(f)

        if len(out.keys()) == 0:
            return []

        pdir = self._productDir(name)
        if not os.path.exists(pdir):
          raise RuntimeError("programmer error: product directory disappeared")

        # add in the tags 
        for file in os.listdir(pdir):
            mat = tagFileRe.match(file)
            if mat: 
                tag = mat.group(1)
                file = ChainFile(os.path.join(pdir,file), name, tag)
                for flavor in file.getFlavors():
                    vers = file.getVersion(flavor)
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

        tablefile = product.table
        if not tablefile:
            tablefile = os.path.join("ups", "%s.table" % product.name)
            if not product.dir or not isRealFilename(product.dir) or \
               not os.path.exists(os.path.join(product.dir,tablefile)):
                raise TableFileNotFound(msg="Unable to located a table file " +
                                        "in default location: " + tablefile)

        # set the basic product information
        pdir = self._productDir(product.name)
        vfile = self._versionFileInDir(pdir, product.version)
        versionFile = VersionFile(vfile, product.name, product.version)
        versionFile.addFlavor(product.flavor, product.dir, tablefile)

        # seal the deal
        if not os.path.exists(pdir):
            os.mkdir(pdir)
        versionFile.write()

        # now assign any tags
        for tag in product.tags:
            self.assignTag(tag, product.name, product.version, product.flavor)

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

    def getTaggedVersion(self, tag, productName, flavor):
        """
        return the version name of the product that has the given tag assigned
        to it.  None is return if the tag is not assigned to any version.
        ProductNotFound is raised if no version of the product is declared.
        """
        pdir = self._productDir(productName)
        if not os.path.exists(pdir):
            raise ProductNotFound(productName, stack=self.dbpath);

        tfile = self._tagFileInDir(pdir, tag)
        if not os.path.exists(tfile):
            return None

        tf = ChainFile(tfile)
        return tf.getVersion(flavor)
        

    def assignTag(self, tag, productName, version, flavors=None):
        """
        assign a tag to a given product.

        @param tag :         the name of the tag to assign
        @param productName : the name of the product getting the tag
        @param version :     the version to tag 
        @param flavors :     the flavors of the product to be tagged.  
                                If None, tag all available flavors.  
        """
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
        
        tfile = self._tagFile(productName, tag)
        tagFile = ChainFile(tfile, productName, tag)

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
        if not productNames:
            raise RuntimeError("No products names given: " + str(productNames))
        if not isinstance(productNames, list):
            productNames = [productNames]
        if flavors is not None and not isinstance(flavors, list):
            flavors = [flavors]

        unassigned = False
        for prod in productNames:
            tfile = self._tagFile(prod, tag)
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
                if (tf.removeVersion(flavor)):
                    changed = True

            if changed:
                tf.write()
                unassigned = True

        return unassigned

    def isNewerThan(self, timestamp):
        """
        return true if the state of this database is newer than a given time
        NOTE: file timestamps only have a resolution of 1 second!
        @param timestamp    the epoch time, as given by os.stat()
        """
        proddirs = map(lambda d: os.path.join(self.dbpath, d), 
                       self.findProductNames())
        for prod in proddirs:
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

    

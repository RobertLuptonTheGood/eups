#!/usr/bin/env python
import os
import sys
try:
    import sqlite3 as sqlite
except ImportError:
    sqlite = None

#from exceptions import ProductNotFound, EupsException, TableFileNotFound
from exceptions import TableError
import cmd as eupsCmd
import utils

try:
    _eupsDatabaseFile
except NameError:
    _eupsDatabaseFile = None

class ProductInfo(object):
    def __init__(self, name, version, productTagNames, missing, depth=None):
        self.name = name
        self.version = version
        self.productTagNames = productTagNames
        self.depth = depth
        self.missing = missing

    def format(self):
        """Format a line describing a product"""
        pstr = "%-30s %-16s" % (("%s%s" % (self.depth*" ", self.name)), self.version)

        if self.missing is not None:
            pstr += " %11s" % ("(not found)" if self.missing else "")

        if self.productTagNames:
            pstr += " "
            pstr += ", ".join(productTagNames)

        return pstr

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def setDatabaseFile(fileName):
    global _eupsDatabaseFile
    _eupsDatabaseFile = fileName

class Connection(object):
    def __init__(self, connection=None):
        if connection:
            self._connection = connection
            self._mustClose = False
        else:
            if not _eupsDatabaseFile:
                raise RuntimeError("Please specify a database filename with setDatabaseFile()")
            self._connection = sqlite.connect(_eupsDatabaseFile)
            self._mustClose = True

    def __enter__(self):
        return self._connection

    def __exit__(self, type, value, tb):
        if self._mustClose:
            self._connection.close()

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def createEups():
    return eupsCmd.EupsCmd([]).createEups()

def create(fileName, force=False, populate=True):
    """Create the sqlite database, inserting the contents of the current eups DB if populate is True"""
    if not sqlite:
        raise NotImplementedError("sqlite is not available")
    
    if os.path.exists(fileName):
        if force:
            os.unlink(fileName)
        else:
            return
    
    setDatabaseFile(fileName)

    with Connection() as conn:
        cmd = """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT,
                version TEXT,
                directory TEXT,
                missing BOOLEAN
            )
        """

        conn.execute(cmd)
        conn.commit()

        cmd = """
            CREATE TABLE dependencies (
                id INTEGER,
                dependency INTEGER,
                optional BOOLEAN,
                FOREIGN KEY(id)         REFERENCES products(id),
                FOREIGN KEY(dependency) REFERENCES products(id)
            )
        """
        conn.execute(cmd)
        conn.commit()

        cmd = """
            CREATE TABLE tagNames (
                tid INTEGER PRIMARY KEY,
                name TEXT,
                fullname TEXT,
                isGlobal BOOLEAN,
                owner TEXT
            )
        """
        conn.execute(cmd)
        conn.commit()

        cmd = """
            CREATE TABLE tags (
                id INTEGER,
                tid INTEGER,
                FOREIGN KEY(id)    REFERENCES products(id),
                FOREIGN KEY(tid)   REFERENCES tagNames(tid)
            )
        """
        conn.execute(cmd)
        conn.commit()

        if populate:
            Eups = createEups()
            flavors = None
            #
            # Fill tagNames table first as we'll fill the join table "tags" as we process the products
            #
            insertTags(flavors=flavors, Eups=Eups, conn=conn)
            
            for epd in Eups.path:
                insertProducts(epd, flavors=flavors, Eups=Eups, conn=conn)

def insertTags(flavors=None, Eups=None, conn=None):
    """Insert a set of tags into the DB"""

    with Connection(conn) as conn:
        if not Eups:
            Eups = createEups()

        if flavors is None:
            flavors = utils.Flavor().getFallbackFlavors(Eups.flavor, True)
        #
        # Fill tagNames table first as we'll fill the join table "tags" as we process the products
        #
        cursor = conn.cursor()

        for t in Eups.tags.getTags():
            if t.isPseudo():
                continue
            cursor.execute("INSERT INTO tagNames VALUES (NULL, ?, ?, ?, ?)",
                           (t.name, str(t), t.isGlobal(), ""))
        conn.commit()

def insertProducts(eupsPathDir, flavors=None, Eups=None, conn=None):
    """Insert a set of products into the DB"""

    with Connection(conn) as conn:
        if not Eups:
            Eups = createEups()

        if flavors is None:
            flavors = utils.Flavor().getFallbackFlavors(Eups.flavor, True)
        #
        # Fill tagNames table first as we'll fill the join table "tags" as we process the products
        #
        cursor = conn.cursor()

        for t in Eups.tags.getTags():
            if t.isPseudo():
                continue
            cursor.execute("INSERT INTO tagNames VALUES (NULL, ?, ?, ?, ?)", (t.name, str(t), t.isGlobal(), ""))
        conn.commit()
    #
    # Iterate through each stack path
    #
    productList = []

    if not Eups.versions.has_key(eupsPathDir):
        return productList

    stack = Eups.versions[eupsPathDir]
    stack.ensureInSync(verbose=Eups.verbose)

    # iterate through the flavors of interest
    haveflavors = stack.getFlavors()
    for flavor in flavors:
        if flavor not in haveflavors:
            continue

        # match the product name
        for pname in stack.getProductNames(flavor):
            for ver in stack.getVersions(pname, flavor):
                productList.append(stack.getProduct(pname, ver, flavor))

    if not productList:
        return []

    defaultProduct, defaultProductList = findDefaultProducts(Eups, productList)[1:]

    dependencies = {}
    for pi in productList:          # for every known product
        if pi == defaultProduct:
            continue

        insertProduct(pi, newProduct=False) # we'll add the dependencies later

        try:
            dependentProducts = Eups.getDependentProducts(pi)
        except TableError, e:
            if not Eups.quiet:
                print >> utils.stdwarn, ("Warning: %s" % (e))
            continue

        dependencies[pi] = [(dp.name, dp.version, optional) for dp, optional, depth in dependentProducts if
                            dp not in defaultProductList]

    defaultProductName = defaultProduct.name if defaultProduct else None
    for pi, deps in dependencies.items():
        if pi.name == defaultProductName:
            continue

        insertProduct(pi, deps, newProduct=False, defaultProductName=defaultProductName)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def insertProduct(product, dependencies={}, newProduct=True, defaultProductName=None):
    """If newProduct is True, the product must not be already declared"""
    
    def insert_product(cursor, name, version, directory, missing=False):
        cursor.execute("INSERT INTO products VALUES (NULL, ?, ?, ?, ?)", (name, version,
                                                                          directory, missing))
        return cursor.lastrowid

    with Connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM products WHERE name = ? AND version = ?",
                       (product.name, product.version))
        result = cursor.fetchone()
        if result:
            if newProduct:
                raise RuntimeError("%s %s is already declared" % (product.name, product.version))
            else:
                pid1 = result[0]
        else:
            pid1 = insert_product(cursor, product.name, product.version, product.dir)
            for t in product.tags:
                cursor.execute("SELECT tid FROM tagNames WHERE fullname = ?", (t,))
                try:
                    tid = cursor.fetchone()[0]
                except TypeError:
                    print >> utils.stdwarn, \
                        "Unable to find tag %s for %s:%s" % (t, product.name, product.version)
                    continue

                cursor.execute("INSERT INTO tags VALUES (?, ?)", (pid1, tid))

        for p, v, optional in dependencies:
            cursor.execute("SELECT id FROM products WHERE name = ? AND version = ?", (p, v))
            try:
                pid2 = cursor.fetchone()[0]
            except TypeError:
                if p != defaultProductName:
                    print >> utils.stdwarn, \
                        "Unable to find dependency %s:%s of %s:%s" % (p, v, product.name, product.version)

                pid2 = insert_product(cursor, p, v, None, missing=True)

            #optional = False
            cursor.execute("INSERT INTO dependencies VALUES (?, ?, ?)", (pid1, pid2, optional))
        conn.commit()

def getTags(conn, pid):
    cursor = conn.cursor()

    query = """
SELECT tagNames.name
FROM products JOIN tags     ON products.id  = tags.id
              JOIN tagNames ON tagNames.tid = tags.tid
WHERE
   products.id = ?
"""
    tagNames = []
    for line in cursor.execute(query, (pid,)):
        tagNames.append(line[0])

    return tagNames

def queryForProducts(conn, name=None, version=None, tag=None):
    query = "SELECT products.id, products.name, products.version, products.missing FROM products"

    where = []
    if name:
        where.append("products.name = :name")
    if tag:
        query += """ JOIN tags     ON products.id  = tags.id
                     JOIN tagNames ON tagNames.tid = tags.tid"""

        where.append("tagNames.name = :tag")
    if version:
        where.append("products.version = :version")

    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY products.name"

    cursor = conn.cursor()
    cursor.execute(query, dict(name=name, version=version, tag=tag))

    return cursor.fetchall()

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def listProducts(productName=None, versionName=None, tagName=None,
                 flavor=None, outFile=None,
                 showDependencies=False, showTags=False, showMissing=False
                 ):
    if showDependencies:                # check that only one version is requested
        with Connection() as conn:
            try:
                queryForOneProduct(conn, productName, versionName, tagName)
            except RuntimeError as e:
                print >> sys.stderr, e
                return

    if outFile is None:
        fd = sys.stderr
    else:
        fd = open(outFile, "w")

    try:
        for pinfo in _listProducts(productName, versionName, tagName, flavor,
                                   showDependencies, showTags, showMissing):
            if pinfo.missing and not showMissing:
                continue
            
            print >> fd, pinfo.format()
    finally:
        del fd

def _listProducts(productName=None, versionName=None, tagName=None,
                  flavor=None, showDependencies=False, showTags=False, showMissing=False
                 ):
    """Worker routine for listProducts"""
    
    Eups = createEups()
    defaultProductName = findDefaultProducts(Eups)[0]

    def my_version_cmp(a, b):           # comparison function for list returned by queryForProducts
        na = a[1]; nb = b[1]            # product name
        compar = cmp(na, nb)
        if compar != 0:
            return compar
        else:
            va = a[2]; vb = b[2]        # product version
            return Eups.version_cmp(va, vb)

    res = []
    with Connection() as conn:
        productList = sorted(queryForProducts(conn, productName, versionName, tagName), my_version_cmp)
            
        for pid, n, v, missing in productList:
            if missing and not showMissing:
                continue

            productTagNames = getTags(conn, pid) if showTags else None

            depth = 0
            res.append(ProductInfo(n, v, productTagNames, missing, depth=depth))

            if not showDependencies:
                continue
            
            for dpid, n, v, depth, missing in _getDependencies(conn, pid, depth, {defaultProductName : 1},
                                                               flavor, tagName):
                productTagNames = getTags(conn, dpid) if showTags else None
                res.append(ProductInfo(n, v, productTagNames, missing, depth=depth))

    return res                           

def _getDependencies(conn, pid, depth, listedProducts, flavor, tag=None):

    depth += 1

    depCursor = conn.cursor()

    query = """
SELECT
   products.id, products.name, version, missing
FROM
   products JOIN dependencies ON dependency = products.id
WHERE
   dependencies.id = :pid
"""

    deps = []
    for dpid, p, v, missing in depCursor.execute(query, dict(pid=pid, tag=tag)):
        if listedProducts.get(p):
            continue
        if missing:
            print >> utils.stdwarn, "Unable to find %s %s for flavor %s" % (p, v, flavor)
            continue

        deps.append((dpid, p, v, depth, missing))
        listedProducts[p] = v
        deps += _getDependencies(conn, dpid, depth, listedProducts, flavor, tag)

    return deps
    
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def uses(name, version=None, tag=None, flavor=None):
    """Tell me who uses this product"""

    for consumer, versions in _uses(name, version, tag, flavor):
        print "%-30s %s" % (consumer, ", ".join(versions))

def _uses(name, version=None, tag=None, flavor=None):
    """Worker routine for uses"""

    with Connection() as conn:
        pid, name, version, missing = queryForOneProduct(conn, name, version, tag)

        Eups = createEups()
        defaultProductName = findDefaultProducts(Eups)[0]

        listedProducts = {}
        _getConsumers(conn, pid, listedProducts, flavor)
        res = []
        for n in sorted(listedProducts.keys()):
            res.append([n, sorted(listedProducts[n], Eups.version_cmp)])

    return res

def _getConsumers(conn, pid, listedProducts, flavor):
    """Insert all products that depend on product with id pid into dict listedProducts; the values
    are the set of versions
    """

    query = """
SELECT
   products.id, products.name, version
FROM
   products JOIN dependencies ON dependencies.id = products.id
WHERE
   dependencies.dependency = :pid
"""

    depCursor = conn.cursor()
    for dpid, p, v in depCursor.execute(query, dict(pid=pid)):
        if not listedProducts.has_key(p):
            listedProducts[p] = set()
            
        if v in listedProducts[p]:
            continue

        listedProducts[p].add(v)
        _getConsumers(conn, dpid, listedProducts, flavor)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def listTags():
    """List all known tags"""

    for name in _listTags():
        print "%-10s" % (name)

def _listTags():
    """List all known tags"""
    with Connection() as conn:
        cursor = conn.cursor()

        res = []
        for line in cursor.execute("SELECT name, isGlobal, owner FROM tagNames"):
            name, isGlobal, owner = line

            res.append(name)

    return res
    
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def findDefaultProducts(Eups=None, productList=None):
    """Find the default product"""

    if Eups is None:
        Eups = createEups()
    
    import hooks

    defaultProductName = hooks.config.Eups.defaultProduct["name"]
    defaultProduct = None
    defaultProductList = []
    if productList:
        defaultProduct = [_ for _ in productList if _.name == defaultProductName]
        if defaultProduct:
            defaultProduct = defaultProduct[0]
            defaultProductList = [_ for _ in productList if _ in
                                  [x[0] for x in Eups.getDependentProducts(defaultProduct)]]

    return defaultProductName, defaultProduct, defaultProductList

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def undeclareProduct(name, version, checkUsers=False):
    """Undeclare a version, including any tags

    If checkUsers is True check if any products depend on (name, version), and raise RuntimeError
    it if there are any
    """

    if checkUsers:
        users = _uses(name, version, tag=None, flavor=None)
        if users:
            raise RuntimeError("%s %s is used by %d products (see eups.sql.uses() to list them)" %
                               (name, version, len(users)))


    with Connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM products WHERE name = ? AND version = ?",
                       (name, version))
        result = cursor.fetchone()
        if not result:
            raise RuntimeError("Unable to find %s %s" % (name, version))
        pid = result[0]

        cursor.execute("DELETE FROM products WHERE id = ?", (pid,))
        cursor.execute("DELETE FROM dependencies WHERE id = ?", (pid,))
        cursor.execute("DELETE FROM tags WHERE id = ?", (pid,))

        #cursor.execute("SELECT tid FROM tagNames WHERE fullname = ?", (t,))

        conn.commit()

def test():
    create("eups.sql", force=True)

    insertProduct("A", "10.1")
    insertProduct("B", "10.2")
    insertProduct("C", "10.2", [("B", "10.2"),])
    insertProduct("X", "1.1", [("A", "10.1"),])
    insertProduct("X", "1.2")

    insertProduct("Y", "1.1", [("C", "10.2"),])
    insertProduct("Z", "1.1", [("X", "1.1"), ("Y", "1.1"),])
    
    listProducts()

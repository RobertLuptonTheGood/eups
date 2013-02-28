#!/usr/bin/env python
import os
import sys
try:
    import sqlite3 as sqlite
except ImportError:
    sqlite = None

#from exceptions import ProductNotFound, EupsException, TableError, TableFileNotFound
import cmd as eupsCmd
import utils

try:
    _eupsDatabaseFile
except NameError:
    _eupsDatabaseFile = None

def setDatabaseFile(fileName):
    global _eupsDatabaseFile
    _eupsDatabaseFile = fileName

def getConnection():
    if not _eupsDatabaseFile:
        raise RuntimeError("Please specify a database filename with setDatabaseFile()")

    return sqlite.connect(_eupsDatabaseFile)

def create(fileName, force=False):
    if not sqlite:
        raise NotImplementedError("sqlite is not available")
    
    if os.path.exists(fileName):
        if force:
            os.unlink(fileName)
        else:
            return
    
    setDatabaseFile(fileName)

    conn = getConnection()

    cmd = """
CREATE TABLE products (
   id INTEGER PRIMARY KEY,
   name TEXT,
   version TEXT,
   directory TEXT,
   missing BOOLEAN
)
"""
    try:
        conn.execute(cmd)
        conn.commit()
    except:
        conn.close()
        raise

    cmd = """
CREATE TABLE dependencies (
   id INTEGER,
   dependency INTEGER,
   optional BOOLEAN,
   FOREIGN KEY(id)         REFERENCES products(id),
   FOREIGN KEY(dependency) REFERENCES products(id)
)
"""
    try:
        conn.execute(cmd)
        conn.commit()
    except:
        conn.close()
        raise

    cmd = """
CREATE TABLE tagNames (
   tid INTEGER PRIMARY KEY,
   name TEXT,
   fullname TEXT,
   isGlobal BOOLEAN,
   owner TEXT
)
"""
    try:
        conn.execute(cmd)
        conn.commit()
    except:
        conn.close()
        raise

    cmd = """
CREATE TABLE tags (
   id INTEGER,
   tid INTEGER,
   FOREIGN KEY(id)    REFERENCES products(id),
   FOREIGN KEY(tid)   REFERENCES tagNames(tid)
)
"""
    try:
        conn.execute(cmd)
        conn.commit()
    finally:
        conn.close()

    Eups = eupsCmd.EupsCmd().createEups()
    for epd in Eups.path:
        insertProducts(epd, Eups=Eups)

def insertProducts(eupsPathDirs, flavors=None, Eups=None):
    """Insert a set of products into the DB"""

    if not Eups:
        Eups = eupsCmd.EupsCmd().createEups()

    if not isinstance(eupsPathDirs, list):
        eupsPathDirs = [eupsPathDirs]

    if flavors is None:
        flavors = utils.Flavor().getFallbackFlavors(Eups.flavor, True)
    #
    # Fill tagNames table first as we'll fill the join table "tags" as we process the products
    #
    conn = getConnection()
    cursor = conn.cursor()

    for t in Eups.tags.getTags():
        if t.isPseudo():
            continue
        cursor.execute("INSERT INTO tagNames VALUES (NULL, ?, ?, ?, ?)", (t.name, str(t), t.isGlobal(), ""))
    conn.commit()
    conn.close()
    #
    # Iterate through each stack path
    #
    productList = []
    for d in eupsPathDirs:
        if not Eups.versions.has_key(d):
            continue
        stack = Eups.versions[d]
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

        insertProduct(pi)               # we'll add the dependencies later

        try:
            dependentProducts = Eups.getDependentProducts(pi)
        except TableError, e:
            if not Eups.quiet:
                print >> utils.stdwarn, ("Warning: %s" % (e))
            continue

        dependencies[pi] = [(dp.name, dp.version) for dp, optional, depth in dependentProducts if
                            dp not in defaultProductList]

    defaultProductName = defaultProduct.name if defaultProduct else None
    for pi, deps in dependencies.items():
        assert pi.name != defaultProductName
        if pi.name == defaultProductName:
            continue

        insertProduct(pi, deps, newProduct=False, defaultProductName=defaultProductName)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def insertProduct(product, dependencies={}, newProduct=True, defaultProductName=None):
    """If newProduct is True, the product may not already be declared"""
    
    def insert_product(cursor, name, version, directory, missing=False):
        cursor.execute("INSERT INTO products VALUES (NULL, ?, ?, ?, ?)", (name, version,
                                                                          directory, missing))
        return cursor.lastrowid

    conn = getConnection()

    cursor = conn.cursor()
    try:
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

        for p, v in dependencies:
            cursor.execute("SELECT id FROM products WHERE name = ? AND version = ?", (p, v))
            try:
                pid2 = cursor.fetchone()[0]
            except TypeError:
                if p != defaultProductName:
                    print >> utils.stdwarn, \
                        "Unable to find dependency %s:%s of %s:%s" % (p, v, product.name, product.version)

                pid2 = insert_product(cursor, p, v, None, missing=True)

            optional = False
            cursor.execute("INSERT INTO dependencies VALUES (?, ?, ?)", (pid1, pid2, optional))
        conn.commit()
    except RuntimeError, e:
        print >> sys.stderr, "Error loading DB: %s" % e
    finally:
        conn.close()

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

def formatProduct(name, version, productTagNames, depth, missing=None):
    """Format a line describing a product"""
    pstr = "%-30s %-16s" % (("%s%s" % (depth*" ", name)), version)

    if missing is not None:
        pstr += " %11s" % ("(not found)" if missing else "")

    if productTagNames:
        pstr += " "
        pstr += ", ".join(productTagNames)

    return pstr

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

def listProducts(name=None, version=None, tag=None,
                 flavor=None, outFile=None,
                 showDependencies=False, showTags=False, showMissing=False
                 ):
    if outFile is None:
        fd = sys.stderr
    else:
        fd = open(outFile, "w")

    defaultProductName = findDefaultProducts()[0]

    conn = getConnection()
    try:
        for line in queryForProducts(conn, name, version, tag):
            pid, n, v, missing = line
            if missing and not showMissing:
                continue

            productTagNames = getTags(conn, pid) if showTags else None

            depth = 0
            print >> fd, formatProduct(n, v, productTagNames, depth, missing if showMissing else None)

            if not showDependencies:
                continue
            
            for dpid, n, v, depth in _getDependencies(conn, pid, depth, {defaultProductName : 1},
                                                      flavor, tag):
                productTagNames = getTags(conn, dpid) if showTags else None
                print >> fd, formatProduct(n, v, productTagNames, depth)
    except Exception, e:
        print e
        import pdb; pdb.set_trace() 
    finally:
        del fd
        conn.close()

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

        deps.append((dpid, p, v, depth))
        listedProducts[p] = v
        deps += _getDependencies(conn, dpid, depth, listedProducts, flavor, tag)

    return deps
    
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def uses(name, version=None, tag=None, flavor=None):
    """Tell me who uses this product"""

    conn = getConnection()
    products = queryForProducts(conn, name, version, tag)

    idStr = ["%s" % name]
    if version:
        idStr.append("version %s" % version)
    if tag:
        idStr.append("tag %s" % tag)
    idStr = " ".join(idStr)

    if len(products) == 0:
        raise RuntimeError("Unable to find %s" % (idStr))
    elif len(products) > 1:
        raise RuntimeError("Requested product \"%s\" is not unique. Found versions: %s" %
                           (idStr, ", ".join([_[2] for _ in products])))

    pid, name, version, missing = products[0]

    Eups = eupsCmd.EupsCmd().createEups()
    defaultProductName = findDefaultProducts(Eups)[0]

    listedProducts = {}
    _getConsumers(conn, pid, listedProducts, flavor)
    for n in sorted(listedProducts.keys()):
        print "%-20s %s" % (n, ", ".join(sorted(listedProducts[n], Eups.version_cmp)))

    conn.close()

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
    conn = getConnection()

    cursor = conn.cursor()

    for line in cursor.execute("SELECT name, isGlobal, owner FROM tagNames"):
        name, isGlobal, owner = line

        print "%-10s" % (name)

    conn.close()
    
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def findDefaultProducts(Eups=None, productList=None):
    """Find the default product"""

    if Eups is None:
        Eups = eupsCmd.EupsCmd().createEups()
    
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

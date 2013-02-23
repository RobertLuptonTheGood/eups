#!/usr/bin/env python
import os
import sys
try:
    import sqlite3 as sqlite
except ImportError:
    sqlite = None

from exceptions import ProductNotFound, EupsException, TableError, TableFileNotFound
import hooks
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
CREATE TABLE tags (
   id INTEGER PRIMARY KEY,
   name TEXT
)
"""
    try:
        conn.execute(cmd)
        conn.commit()
    finally:
        conn.close()

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

        for p, v in dependencies:
            cursor.execute("SELECT id FROM products WHERE name = ? AND version = ?", (p, v))
            try:
                pid2 = cursor.fetchone()[0]
            except TypeError:
                if p != defaultProductName:
                    print >> utils.stdwarn, \
                        "Unable to find dependency %s:%s of %s:%s" % (p, v, product.name, product.version)

                pid2 = insert_product(cursor, p, v, None, missing=True)

            cursor.execute("INSERT INTO dependencies VALUES (?, ?)", (pid1, pid2))
        conn.commit()
    except RuntimeError, e:
        import pdb; pdb.set_trace() 
    finally:
        conn.close()

    
def listProducts(name=None, version=None, dependencies=False, flavor=None, outFile=None):
    conn = getConnection()

    query = "SELECT id, name, version FROM products"

    if name or version:
        where = []
        if name:
            where.append("name = :name")
        if version:
            where.append("version = :version")
        query += " WHERE " + " AND ".join(where)

    if outFile is None:
        fd = sys.stderr
    else:
        fd = open(outFile, "w")

    import eups.cmd
    Eups = eups.cmd.EupsCmd().createEups()
    defaultProductName = findDefaultProducts(Eups)[0]

    try:
        cursor = conn.cursor()
        for line in cursor.execute(query, dict(name=name, version=version)):
            pid, p, v = line
            print >> fd, p, v

            if not dependencies:
                continue
            
            depth = 0
            for p, v, depth in _getDependencies(conn, pid, depth, {defaultProductName : 1}, flavor):
                print >> fd, "%-30s %s" % (("%s%s" % (depth*" ", p)), v)

    except Exception, e:
        print e
        import pdb; pdb.set_trace() 
    finally:
        del fd
        conn.close()

def _getDependencies(conn, pid, depth, listedProducts, flavor):

    depth += 1

    depCursor = conn.cursor()

    query = """
SELECT
   products.id, name, version, missing
FROM
   products JOIN dependencies ON dependency = products.id
WHERE
   dependencies.id = ?
"""

    deps = []
    for dpid, p, v, missing in depCursor.execute(query, (pid,)):
        if listedProducts.get(p):
            continue
        if missing:
            print >> utils.stdwarn, "Unable to find %s %s for flavor %s" % (p, v, flavor)
            continue

        deps.append((p, v, depth))
        listedProducts[p] = v
        deps += _getDependencies(conn, dpid, depth, listedProducts, flavor)

    return deps
    
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def build(eupsPathDirs=None, flavors=None):
    import eups.cmd
    Eups = eups.cmd.EupsCmd().createEups()

    if eupsPathDirs is None:
        eupsPathDirs = Eups.path
    if not isinstance(eupsPathDirs, list):
        eupsPathDirs = [eupsPathDirs]

    if flavors is None:
        flavors = utils.Flavor().getFallbackFlavors(Eups.flavor, True)

    # Iterate through each stack path
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

        try:
            dependentProducts = Eups.getDependentProducts(pi)
        except TableError, e:
            if not Eups.quiet:
                print >> utils.stdwarn, ("Warning: %s" % (e))
            continue

        insertProduct(pi)                     # we'll add the dependencies later

        dependencies[pi] = [(dp.name, dp.version) for dp, optional, depth in dependentProducts if
                            dp not in defaultProductList]

    defaultProductName = defaultProduct.name
    for pi, deps in dependencies.items():
        if pi.name == defaultProductName:
            continue

        insertProduct(pi, deps, newProduct=False, defaultProductName=defaultProductName)

def findDefaultProducts(Eups, productList=None):
    """Find the default product"""

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

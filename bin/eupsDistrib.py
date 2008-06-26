#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import atexit
import os, stat
import re, sys
import pdb
import tempfile
import shutil
import urllib, urllib2
import eups

author = "Robert Lupton (rhl@astro.princeton.edu)"
eups_distrib_version = "1.0"

if False:
    import warnings
    warnings.filterwarnings('ignore', "tmpnam ", RuntimeWarning, "", 0) # ignore tmpnam warnings

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

URL, SCP, LOCAL = "URL", "SCP", "LOCAL"

class Distrib(object):
    """A class to encapsulate product distribution"""

    def __init__(self, Eups, packageBasePath, transport, buildFilePath=None, installFlavor=None, preferFlavor=False,
                 current=False, tag=None, no_dependencies=False, obeyGroups=False,
                 noeups=False):
        self.Eups = Eups
        
        self.packageBasePath = packageBasePath # list of possible packageBases
        self.packageBase = None
        self.transport = transport
        self.buildFilePath = buildFilePath
        if not installFlavor:
            installFlavor = Eups.flavor
        self.installFlavor = installFlavor
        self.preferFlavor = preferFlavor
        self.current = current
        self.tag = tag
        self.no_dependencies = no_dependencies
        self.obeyGroups = obeyGroups
        self.noeups = noeups
    #
    # This is really an abstract base class, but provide dummies to help the user
    #
    def createPackage(self, productName, versionName, baseDir=None, productDir=None):
        """Create a package and return the distribution ID """

        eups.debug("createPackage", productName, versionName)

    def installPackage(self, distID, productsRoot, setups):
        """Install the package identified by distID into productsRoot;
        Setups is a list of setup commands needed to build this product"""

        eups.debug("installPackage", cacheId, productsRoot)

    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

    def currentFile(self):
        """Return the name of a current-versions file"""

        return "current.list"

    def manifestFile(self, productName, versionName):
        """Return the name of a manifest file"""

        return "%s-%s.manifest" % (productName, versionName)

    def get_tabledir(self):
        """Return the tablefile directory"""
        
        tabledir = "%s/tables" % (self.packageBase)
        if self.transport == LOCAL and not os.path.isdir(tabledir):
            print >> sys.stdout, "Creating %s" % (tabledir)
            os.mkdir(tabledir)

        return tabledir

    def find_file(self, filename, packagePath=None):
        """Lookup a filename given a (possibly incomplete) packageBase and filename

        N.B. Modifies the self.packageBase if needs be"""

        if not self.packageBase:        # we haven't yet chosen an element of packageBasePath
            for d in self.packageBasePath:
                self.packageBase = d
                try:
                    return self.find_file(filename, packagePath)
                except RuntimeError:
                    self.packageBase = None

            raise RuntimeError, \
                  ("Unable to find %s anywhere in %s" % (filename, " ".join(self.packageBasePath)))

        locs = self.createLocationList(filename, packagePath)

        subDirs = [""]
        if re.search('\.build$', filename):
            subDirs += ['builds']
        elif re.search('\.manifest$', filename):
            subDirs += ['manifests']
        elif re.search('\.table$', filename):
            subDirs += ['tables']

        if self.Eups.verbose > 1:
            print >> sys.stderr, "Looking for %s in subdirectories [%s] of:" % \
                  (filename, str.join(", ", map(lambda sd: "\"%s\"" % sd, subDirs))), \
                  str.join("", map(lambda str: "\n   %s" % os.path.join(self.packageBase, str), locs))

        if self.transport != LOCAL:
            tfile = None
            for loc in locs:
                for sd in subDirs:
                    try:
                        extendedPackageBase = os.path.join(self.packageBase, loc)
                        (tfile, msg) = file_retrieve(os.path.join(extendedPackageBase, sd, filename),
                                                     self.transport, self.Eups.noaction)
                        self.packageBase = extendedPackageBase
                        if self.Eups.verbose > 0:
                            print >> sys.stderr, "Found %s in %s" % (filename, self.packageBase)
                        break
                    except RuntimeError:
                        pass
                if tfile:
                    break
            if tfile:
                filename = tfile
            else:
                raise RuntimeError, ("Failed to find and retrieve filename %s from %s" % (filename, self.packageBase))
        else:
            if False and not self.packageBase:
                self.packageBase = "%s/packages/%s" % (db, installFlavor)

            tfile = None
            for loc in locs:
                for sd in subDirs:
                    guess = os.path.join(self.packageBase, loc, sd, filename)
                    if os.path.isfile(guess) or os.path.isdir(guess):
                        tfile = guess
                        break
                if tfile:
                    break

            if tfile is None:
                raise RuntimeError, ("File %s doesn't exist in %s" % (filename, self.packageBase))

            filename = tfile

        if self.Eups.verbose > 1:
            print >> sys.stderr, "Found %s" % (filename)

        return filename

    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

    def lookup_current_version(self, productName, from_eups=True):
        """Attempt to lookup a package's current version, as declared using eups distrib"""

        if from_eups:
            try:
                return self.Eups.findCurrentVersion(productName)[1]
            except RuntimeError:
                return ""
        else:
            try:
                for p in Current().read():
                    (name, version) = p
                    if name == productName:
                        return version
            except:
                pass

        return ""

    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

    def createLocationList(self, filename, packagePath):
        """Create a list of places to look"""

        locs = []
        if self.preferFlavor:
            locs.extend(['%s' % self.installFlavor, ''])
        else:
            locs.extend(['', '%s' % self.installFlavor])

        if packagePath is not None:
            if self.preferFlavor:
                if self.tag is not None:
                    locs.extend(['%s/%s/%s' % (packagePath, self.installFlavor, self.tag),
                                 '%s/%s' % (packagePath, self.installFlavor),
                                 '%s/%s' % (packagePath, self.tag),
                                 '%s' % (packagePath)])
                else:
                    locs.extend(['%s/%s' % (packagePath, self.installFlavor),
                                 '%s' % (packagePath)])
            else:
                if self.tag is not None:
                    locs.extend(['%s/%s' % (packagePath, self.tag),
                                 '%s/%s/%s' % (packagePath, self.installFlavor, self.tag),
                                 '%s' % (packagePath),
                                 '%s/%s' % (packagePath, self.installFlavor)])
                else:
                    locs.extend(['%s' % (packagePath),
                                 '%s/%s' % (packagePath, self.installFlavor)])

        return locs

    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

    def read_manifest(self, top_product, top_version, manifest):
        """Read a manifest and return the product and version, and productsRoot, top_version, and a list of products"""

        productsRoot = self.Eups.path[0]
        flavor_dir = "%s/%s" % (productsRoot, self.Eups.flavor)    # where to install
        if True or os.path.isdir(flavor_dir): # Always use the flavor_dir as productsRoot
            productsRoot = flavor_dir

        if manifest:
            raw_manifest = manifest
        else:
            if not top_version:
                top_version = self.lookup_current_version(top_product, from_eups = False)

                if top_version == "":
                    raise RuntimeError, (("No version of %s is declared current to eups distrib\n" + \
                                          "Please specify a version or a manifest file with -m") % (top_product))

                print >> sys.stderr, "Installing %s of %s" % (top_version, top_product)

            raw_manifest = self.manifestFile(top_product, top_version)
            manifest = self.find_file(raw_manifest)

            if self.transport == LOCAL:
                mat = re.search(r"^(.*)/([^/]+)$", manifest)
                if mat:
                    pb = mat.groups()[0]
                    if self.packageBase and self.packageBase != os.path.commonprefix([self.packageBase, pb]):
                        print >> sys.stderr, "Manifest file %s has different base from -r %s" % \
                              (manifest, self.packageBase)
                        self.packageBase = pb
        #
        # OK, we've found the manifest (phew)
        #
        if self.Eups.verbose > 1:
            if manifest == raw_manifest:
                print >> sys.stderr, "Manifest is", manifest
            else:
                print >> sys.stderr, "Manifest is", raw_manifest, "(%s)" % manifest
        if self.Eups.verbose > 2:
            try:
                fd = open(manifest, "r")
                print "Manifest file:\n\t", "\t".join(fd.readlines()),
                del fd
            except:
                pass

        try:
            fd = open(manifest, "r")
        except:
            raise IOError, ("Failed to open", manifest)

        line = fd.readline()
        mat = re.search(r"^EUPS distribution manifest for (\S+) \((\S+)\). Version (\S+)\s*$", line)
        if not mat:
            raise RuntimeError, ("First line of file %s is corrupted:\n\t%s" % (manifest, line))
        manifest_product, manifest_product_version, version = mat.groups()

        version = mat.groups()[2]
        if version != eups_distrib_version:
            print >> sys.stderr, "WARNING. Saw version %s; expected %s" % (version, eups_distrib_version)

        products = []
        for line in fd:
            line = line.split("\n")[0]
            if re.search(r"^\s*#", line):
                continue

            try:
                products += [re.findall(r"\S+", line)[0:6]]
            except:
                raise RuntimeError, ("Failed to parse line:", line)

        return manifest_product, manifest_product_version, productsRoot, top_version, products

    def find_file_on_path(self, file, auxDir = None):
        """Look for a file on the :-separated buildFilePath, looking in auxDir if
        an element of path is empty"""

        for bd in self.buildFilePath.split(":"):
            bd = os.path.expanduser(bd)
            
            if bd == "":
                if auxDir:
                    bd = auxDir
                else:
                    continue
            full_file = os.path.join(bd, file)

            if os.path.exists(full_file):
                if self.Eups.verbose:
                    print "Found %s (%s)" % (file, full_file)
                return full_file

        return None

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def system(cmd, noaction=False):
    """Run a command, throwing an OSError exception if a non-zero exit code is returned
    Obeys noaction"""

    if noaction:
        print cmd
    else:
        errno = os.system(cmd)
        if errno != 0:
            raise OSError, ("\n\t".join(("Command:\n" + cmd).split("\n")) + ("\nexited with code %d" % (errno >> 8)))

def issamefile(file1, file2):
    """Are two files identical?"""

    try:
        return os.path.samefile(file1, file2)
    except OSError:
        pass

    return False

def copyfile(file1, file2):
    """Like shutil.copy2, but don't fail copying a file onto itself"""

    if issamefile(file1, file2):
        return

    try:
        os.unlink(file2)
    except OSError:
        pass

    shutil.copy2(file1, file2)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def file_retrieve(file, transport, noaction):
    """Retrieve a file given a specified transport method"""

    if transport == LOCAL:
        return (file, None)
    elif transport == SCP:
        (tfile, msg) = scpretrieve(file, noaction)
    elif transport == URL:
        (tfile, msg) = urlretrieve(file, noaction)
    else:
        raise RuntimeError, "Unknown transport method: %s" % transport

    if os.path.isdir(tfile):
        atexit.register(lambda dir: shutil.rmtree(dir, ignore_errors=True), tfile)       # clean up
    else:
        atexit.register(os.unlink, tfile)   # clean up

    return (tfile, msg)

def scpretrieve(file, noaction=False):
    """Retrieve a file using scp"""

    # Maybe it's a simple file
    fd, tfile = tempfile.mkstemp(prefix="eupsDistrib")
    os.close(fd)

    try:
        system("scp %s %s 2>/dev/null" % (file, tfile), noaction)
        return tfile, None
    except OSError:
        os.unlink(tfile)
    #
    # Maybe it's a directory
    #
    tfile = tempfile.mkdtemp(prefix="eupsDistrib")
    atexit.register(lambda dir: shutil.rmtree(dir, ignore_errors=True), tfile)       # clean up

    try:
        system("scp -r %s %s 2>/dev/null" % (file, tfile), noaction)
    except OSError:
        raise RuntimeError, ("Failed to retrieve %s" % file)

    return os.path.join(tfile, os.path.basename(file)), None

def urlretrieve(file, noaction=False):
    """Like urllib's urlretrieve, except use urllib2 to detect 404 errors"""

    try:
        fd = urllib2.urlopen(file); del fd
    except urllib2.HTTPError:
        raise RuntimeError, ("Failed to open URL %s" % file)
    return urllib.urlretrieve(file)

HTTPError = urllib2.HTTPError

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def listdir(Distrib, url):
    """Return a list of the files specified by a directory URL"""

    if Distrib.transport == LOCAL:
        return os.listdir(url)
    elif Distrib.transport == SCP:
        return os.listdir(url)
    elif Distrib.transport == URL:
        """Read a URL, looking for the hrefs that apache uses in directory listings"""
        import HTMLParser, urlparse
        class LinksParser(HTMLParser.HTMLParser):
            """Based on code in Martelli's "Python in a Nutshell" """
            def __init__(self):

                HTMLParser.HTMLParser.__init__(self)
                self.nrow = 0
                self.seen = set()
                self.files = [] # files listed in table
                self.is_attribute = False # next data is value of <attribute>
                self.is_apache = False # are we reading data from apache?

            def handle_starttag(self, tag, attributes):
                if tag == "tr": # count rows in table
                    self.nrow += 1

                if tag == "address":
                    self.is_attribute = True

                if self.nrow <= 1 or tag != "a":
                    return

                for name, value in attributes:
                    if name != "href":
                        continue
                    if re.search(r"/$", value): # a directory
                        continue

                    self.files += [value]

            def handle_data(self, data):
                if self.is_attribute:
                    self.is_apache = re.search(r"^Apache", data)
                    self.is_attribute = False

        p = LinksParser()
        for line in open(url, "r").readlines():
            p.feed(line)

        if not p.is_apache:
            print >> sys.stderr, \
                  "I'm assuming that the manifest directory listing comes from an Apache server"

        return p.files
    else:
        raise AssertionError, ("I don't know how to handle transport == %s" % Distrib.transport)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def create(Distrib, top_productName, top_version, manifest):
    """Create a distribution"""

    if not Distrib.packageBase:         # use first element of path
        Distrib.packageBase = Distrib.packageBasePath[0]

    if not os.path.isdir(Distrib.packageBase):
        if Distrib.Eups.verbose > 0:
            print >> sys.stderr, "Creating", Distrib.packageBase
        try:
            os.makedirs(Distrib.packageBase)
        except:
            raise RuntimeError, ("Failed to create %s" % Distrib.packageBase)

    if not top_version:
        top_version = Distrib.lookup_current_version(top_productName, True)

    if Distrib.noeups:
        productName = top_productName

        ptablefile = Distrib.find_file_on_path("%s.table" % productName)
        if not ptablefile:
            if Distrib.Eups.verbose > 0:
                print >> sys.stderr, "Unable to find a table file for %s; assuming no dependencies" % productName
            if os.path.exists(os.path.join("ups", "%s.table" % productName)):
                print >> sys.stderr, \
                      "N.b. found %s.table in ./ups; consider adding ./ups to --build path" % (productName)
                
            ptablefile = "none"

        productList = [(productName, top_version, False)]
        dependencies = Distrib.Eups.dependencies_from_table(ptablefile)
        if dependencies:
            for (productName, version, optional) in dependencies:
                if not version:
                    version = Distrib.Eups.findCurrentVersion(productName)[1]
                productList += [(productName, version, optional)]
    else:
        top_product = Distrib.Eups.Product(top_productName, top_version)
        productList = []
        for (product, optionalInTable, currentRequested) in top_product.dependencies():
            productList += [(product.name, product.version, optionalInTable)]

    products = []
    for (productName, version, optional) in productList:
        if Distrib.Eups.verbose > 1:
            print "Product:", productName, "  Flavor:", Distrib.installFlavor, "  Version:", version

        if productName == top_productName and Distrib.noeups:
            baseDir, pdb, pdir = None, None, None
            productDir = "/dev/null"
        else:
            try:
                (pname, pversion, pdb, pdir, pcurrent, psetup) = Distrib.Eups.listProducts(productName, version)[0]
            except KeyboardInterrupt:
                sys.exit(1)
            except Exception, e:
                print >> sys.stderr, "WARNING: Failed to lookup directory for", \
                      "product:", productName, "  Flavor:", Distrib.installFlavor, "  Version:", version
                continue

            try:
                ptablefile = Distrib.Eups.Product(productName, version).table.file
                if ptablefile == "":
                    ptablefile = " "
            except KeyboardInterrupt:
                sys.exit(1)                    
            except Exception, e:
                print >> sys.stderr, "WARNING: Failed to lookup tablefile for", \
                      "product:", productName, "  Flavor:", Distrib.installFlavor, "  Version:", version
                continue

            if pversion != version:
                print >> sys.stderr, "Something's wrong with %s; %s != %s" % (productName, version, pversion)
            #
            # We have the product's directory, and which DB it's registered in
            #
            if pdir == "none":
                baseDir = ""; productDir = pdir
            else:
                try:
                    (baseDir, productDir) = re.search(r"^(\S+)/(%s/\S*)$" % (productName), pdir).groups()
                except:
                    if Distrib.Eups.verbose > 1:
                        print >> sys.stderr, "Split of \"%s\" at \"%s\" failed; proceeding" \
                              % (pdir, productName)
                    if False:
                        print >> sys.stderr, "WARNING: not creating package for %s" % (productName)
                        continue
                    else:
                        try:
                            (baseDir, productDir) = re.search(r"^(\S+)/([^/]+/[^/]+)$", pdir).groups()
                            if Distrib.Eups.verbose > 1:
                                print >> sys.stderr, "Guessing \"%s\" has productdir \"%s\"" \
                              % (pdir, productDir)
                        except:
                            if Distrib.Eups.verbose:
                                print >> sys.stderr, "Again failed to split \"%s\" into baseDir and productdir" \
                                      % (pdir)

                            baseDir = ""; productDir = pdir

        distID = Distrib.createPackage(productName=productName, versionName=version,
                                       baseDir=baseDir, productDir=productDir)

        if optional and not distID:
            if Distrib.Eups.verbose > -1:
                print >> sys.stderr, "Skipping optional product %s" % (productName)
            continue

        if ptablefile != "none":
            fulltablename = ptablefile
            ptablefile = os.path.basename(ptablefile)
            tabledir = Distrib.get_tabledir()

            if productName == top_productName and Distrib.noeups: # the file's called productName.table as if it were
                # in a product's repository, but it still needs to be installed
                tablefile_for_distrib = os.path.join(tabledir,
                                                     "%s-%s.table" % (top_productName, top_version))
                ptablefile = "%s.table" % top_version
            elif ("%s.table" % (productName)) == ptablefile:
                # we want the version with expanded dependencies
                tablefile_for_distrib = os.path.join(tabledir, "%s-%s.table" % (productName, version))
                ptablefile = "%s.table" % version
            else:
                tablefile_for_distrib = os.path.join(tabledir, "%s-%s" % (productName, ptablefile))

            if tablefile_for_distrib:
                if Distrib.Eups.verbose > 1:
                    print >> sys.stderr, "Copying %s to %s" % (fulltablename, tablefile_for_distrib)
                copyfile(fulltablename, tablefile_for_distrib)

        products += [[productName, Distrib.installFlavor, version, pdb, pdir, ptablefile, productDir, distID]]

        if Distrib.no_dependencies:
            if Distrib.Eups.force:
                break
            else:
                print >> sys.stderr, "Not writing manifest as you omitted dependencies; use --force to write it anyway"
    #
    # Time to write enough information to declare the products
    #
    manifestDir = os.path.join(Distrib.packageBase, "manifests")
    if not os.path.isdir(manifestDir):
        try:
            os.mkdir(manifestDir)
        except:
            raise OSError, "I failed to create %s" % (manifestDir)
    
    if not manifest:
        manifest = os.path.join(manifestDir, Distrib.manifestFile(top_productName, top_version))
        
    if Distrib.Eups.verbose > 0:
        print >> sys.stderr, "Writing", manifest

    try:
        if not Distrib.Eups.noaction:
            ofd = open(manifest, "w")
    except OSError, e:
        raise RuntimeError, ("Failed to open %s: %s" % manifest, e)

    if not Distrib.Eups.noaction:
        print >> ofd, "EUPS distribution manifest for %s (%s). Version %s" % \
              (top_productName, top_version, eups_distrib_version)
        
    rproducts = products[:]; rproducts.reverse() # reverse the products list
    for p in rproducts:
        (productName, Distrib.installFlavor, version, pdb, pdir, ptablefile, productDir, distID) = p
        if not Distrib.installFlavor:
            installFlavor = eups.flavor()
        if not Distrib.Eups.noaction:
            print >> ofd, "%-15s %-12s %-10s %-25s %-25s %s" % \
                  (productName, Distrib.installFlavor, version, ptablefile, productDir, distID)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Current(object):
    def __init__(self, Distrib):
        self.Distrib = Distrib
        self.file = self.Distrib.find_file(Distrib.currentFile())

    def read(self):
        """Read a list of current products from current file"""

        fd = open(self.file, "r")

        line = fd.readline()
        mat = re.search(r"^EUPS distribution current version list. Version (\S+)\s*$", line)
        if not mat:
            raise RuntimeError, ("First line of file %s is corrupted:\n\t%s" % (self.file, line),)
        version = mat.groups()[0]
        if version != eups_distrib_version:
            print >> sys.stderr, "WARNING. Saw version %s; expected %s", version, eups_distrib_version

        products = []
        for line in fd:
            line = line.split("\n")[0]
            if re.search(r"^\s*#", line):
                continue

            try:
                (product, flavor, version) = re.findall(r"\S+", line)[0:3]
            except:
                raise RuntimeError, ("Failed to parse line:", line)

            products += [(product, version)]

        return products

    def write(self, products):
        """Write a list of current products to file current"""

        if not self.Distrib.Eups.noaction:
            ofd = open(self.file, "w")

        if self.Distrib.Eups.verbose > 1:
            print >> sys.stderr, "Writing current product list to", self.file

        if not self.Distrib.Eups.noaction:
            print >> ofd, "EUPS distribution current version list. Version %s" % (eups_distrib_version)

        for p in products:
            (productName, versionName) = p[0:2]
            if not self.Distrib.Eups.noaction:
                print >> ofd, str.join("\t", [productName, self.Distrib.installFlavor, versionName])

def createCurrent(Distrib, top_product, top_version):
    """Create a list of packages that are declared current to eups distrib"""

    #
    # Extract the up-to-date information about current versions,
    # and add it to the previously existing list [if any]
    #
    if top_version:
        dp = [(top_product, top_version)]
        if not  Distrib.Eups.listProducts(top_product, top_version):
            print >> sys.stderr, "WARNING: failed to find a version \"%s\" of product %s" % \
                  (top_version, top_product)
    else:
        dp = [(top_product, Distrib.Eups.findCurrentVersion(top_product)[1])]

    if top_product and Distrib.Eups.verbose:
        (productName, versionName) = dp[0]
        assert (productName == top_product)
        print >> sys.stderr, "Declaring version %s of %s current to eups distrib" % (versionName, productName)
    #
    # Now lookup list of current versions
    #
    lock = Distrib.Eups.lockDB(Distrib.packageBase, upsDB=False)

    current = Current(Distrib)

    if top_product == "":               # update entire current list
        products = []
    else:
        try:
            products = current.read()
        except:
            products = []

        nproducts = []
        for p in products:
            if p[0] != top_product:
                nproducts += [p]
        products = nproducts

    products += dp 
    #
    # Now write the file containing current version info.
    #
    current.write(products)

def install(Distrib, top_product, top_version, manifest):
    """Install a set of packages"""

    manifest_product, manifest_product_version, productsRoot, top_version, products = \
                      Distrib.read_manifest(top_product, top_version, manifest)
    if os.path.isdir(productsRoot):
        if Distrib.Eups.verbose > 0:
            print >> sys.stderr, "Installing products into", productsRoot

    setups = []                         # setups that we've acquired while processing products
    for (productName, mflavor, versionName, tablefile, productDir, distID) in products:
        if (Distrib.no_dependencies and 
            (productName != top_product or versionName != top_version)):
            continue
        
        info = []
        if not Distrib.noeups:
            try:
                info = Distrib.Eups.listProducts(productName, versionName)[0]
            except IndexError:
                pass

        if info and len(info) > 0 and not re.search("^LOCAL:", info[1]):
            if productName != top_product:
                setups += ["setup %s %s &&" % (productName, versionName)]
            
            print >> sys.stderr, "Product %s (version %s, flavor %s) is already declared" % \
                  (productName, versionName, Distrib.Eups.flavor)
            if Distrib.Eups.force:
                print >> sys.stderr, "Reinstalling %s anyway" % (productName)
                Distrib.Eups.undeclare(productName, versionName, undeclare_current=Distrib.current)
            else:
                continue
        #
        # We need to install and declare this product
        #
        dodeclare = True

        if distID == "None":              # we don't know how to install this product
            if Distrib.Eups.verbose:
                print >> sys.stderr, "Manifest for %s doesn't have install instructions for %s; trying eups distrib --install %s" % \
                      (top_product, productName, productName)
            try:
                install(Distrib, productName, versionName, None)
                continue
            except RuntimeError, e:
                if not Distrib.Eups.force or Distrib.Eups.verbose > 0:
                    print >> sys.stderr, "I don't know how to install %s: %s" % (productName, e)
                if not Distrib.Eups.force:
                    print >> sys.stderr, "Specify force to proceed"
                    sys.exit(1)
                dodeclare = False
        else:
            Distrib.installPackage(distID, productsRoot, setups)

        setups += ["setup %s %s &&" % (productName, versionName)]
        #
        # We may be done
        #
        if Distrib.noeups:
            return
        #
        # we need to see if someone (e.g. the build/pacman script) declared the package for us
        #
        declared = Distrib.Eups.listProducts(productName, versionName)
        try:
            if re.search(r"^LOCAL:", declared[0][1]):
                dodeclare = False
        except Exception, e:
            pass
        #
        # Deal with table files if not in product root (i.e. -M files)
        #
        # If the table in the manifest file is not "<productName>.table" in the manifest file
        # the table file should be installed by eups_distrib and declared via eups declare -M
        #
        if dodeclare:
            if tablefile != "none":
                if ("%s.table" % (productName)) != tablefile: # tablefile should be saved in upsDB
                    tablefile = "%s-%s" % (productName, tablefile)
                    tablefile = Distrib.find_file(tablefile, "%s/%s" % (productName, versionName))

                    tablefile = open(tablefile)
            #
            # Look for productsRoot on eups path
            #
            eupsPathDir = None
            for pdir in Distrib.Eups.path:
                if pdir == os.path.commonprefix([productsRoot, pdir]):
                    eupsPathDir = pdir
                    break                

            if not re.search(r"^/", productDir):
                productDir = os.path.join(productsRoot, productDir)

            Distrib.Eups.declare(productName, versionName, productDir, tablefile=tablefile,
                                 eupsPathDir=eupsPathDir, declare_current=Distrib.current)
        else:                           # we may still need to declare it current
            if Distrib.current:
                Distrib.Eups.declareCurrent(productName, versionName, eupsPathDir=productsRoot)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def listProducts(Distrib, top_product, top_version, current, manifest):
    """List available packages"""

    available = []                      # available products
    if current:
        fd = open(Distrib.find_file(Distrib.currentFile()), "r")
        fd.readline()                   # skip header

        for line in fd.readlines():
            line = line[:-1]            # remove newline
            available += [line.split("\t")]
    else:
        #
        # That would have been easy. We need to read the list of manifests
        #
        manifestDir = Distrib.find_file("manifests")
        for file in listdir(Distrib, manifestDir):
            manifest = Distrib.find_file(file)
            manifest_product, manifest_product_version = Distrib.read_manifest(None, None, manifest)[0:2]

            available += [[manifest_product, None, manifest_product_version]]

    productList = []
    for a in available:
        manifest_product, manifest_flavor, manifest_product_version = a

        if manifest_flavor and manifest_flavor != Distrib.installFlavor:
            continue
        if top_product and top_product != manifest_product:
            continue
        if top_version and top_version != manifest_product_version:
            continue

        productList += [(manifest_product, manifest_product_version)]
    #
    # Be nice and sort the products
    #
    def pvsort(a,b):
        """Sort by product then version"""

        if a[0] == b[0]:
            return cmp(a[1], b[1])
        else:
            return cmp(a[0], b[0])

    productList.sort(pvsort)

    return productList

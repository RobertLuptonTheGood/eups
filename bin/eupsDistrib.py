#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import atexit
import fnmatch
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

    def __init__(self, Eups, packageBasePath, installFlavor=None, preferFlavor=False,
                 tag=None, no_dependencies=False, allowIncomplete=False, obeyGroups=False,
                 noeups=False):
        self.Eups = Eups
        
        self.packageBasePath = packageBasePath # list of possible packageBases
        self.packageBase = None
        self.transport = None

        if not installFlavor:
            installFlavor = Eups.flavor
        self.installFlavor = installFlavor
        self.preferFlavor = preferFlavor
        if tag and not eups.isValidTag(tag):
            raise RuntimeError, ("Unknown tag %s; expected one of \"%s\"" % (tag, "\" \"".join(eups.getValidTags())))
        self.tag = tag
        self.preferredTag = None        # old Ray usage; to be removed??
        self.no_dependencies = no_dependencies
        self.allowIncomplete = allowIncomplete
        self.obeyGroups = obeyGroups
        self.noeups = noeups

        self._msgs = {}
    #
    # Here are the hooks to allow the distribFactory to create the correct sort of Distrib
    #
    def handles(self, impl):
        """Return True iff we understand this sort of implementation"""

        return self.implementation == impl

    handles = classmethod(handles)

    def parseDistID(self, distID):
        """Return a valid identifier (e.g. a pacman cacheID) iff we understand this sort of distID"""

        return None

    parseDistID = classmethod(parseDistID)
    #
    # This is really an abstract base class, but provide dummies to help the user
    #
    implementation = None           # which implementation is provided?

    def checkInit(self):
        """Check that self is properly initialised; this matters for subclasses with special needs"""
        pass

    def createPackage(self, productName, versionName, baseDir=None, productDir=None):
        """Create a package and return the distribution ID """

        raise RuntimeError, ("Not implemented: createPackage %s %s" % (productName, versionName))

    def installPackage(self, distID, productsRoot, setups):
        """Install the package identified by distID into productsRoot;
        Setups is a list of setup commands for this product's dependencies"""

        raise RuntimeError, ("Not implemented: installPackage %s %s" % (distID, productsRoot))

    def find_file_on_path(self, file, auxDir = None):
        """Return the name of a file somewhere on a :-separated path, looking in auxDir if
        an element of path is empty"""

        eups.debug("find_file_on_path", file, auxDir)

        return None
    
    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

    def taggedVersionFile(self):
        """Return the name of a current-versions file"""

        if self.tag:
            return "%s.list" % self.tag
        else:
            raise RuntimeError, "I'm unable to generate a tag filename as tag is None"

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

    def remove_packageBase(self, transport, packageBase):
        """Remove packageBase from packageBasePath, taking into
        account transport mechanisms and flavor directories"""

        pb = packageBase           # A convenient abbreviation

        if not pb:
            return

        pb0, pb1 = os.path.split(pb)
        if pb1 == self.Eups.flavor:
            pb = pb0

        for pb in (pb, "%s:%s" % (transport.lower(), pb)):
            newPBP = filter(lambda d: d != pb, self.packageBasePath)

            if self.packageBasePath != newPBP:
                self.packageBasePath = newPBP
                return

    def get_transport(self, packageBaseURL):
        """Return (transport, packageBase) given a URL"""

        transport = LOCAL
        packageBase = packageBaseURL

        if packageBaseURL is not None:
            if re.search(r"^http://", packageBaseURL):
                transport = URL
            elif re.search(r"^scp:", packageBaseURL):
                transport = SCP
                packageBase = re.sub(r"^scp:", "", packageBaseURL)

        return (transport, packageBase)

    def find_file(self, filename, packagePath=None, create=False):
        """Lookup a filename given a (possibly incomplete) packageBase and filename

        N.B. Modifies the self.packageBase if needs be"""

        if not self.packageBase:        # we haven't yet chosen an element of packageBasePath
            for url in self.packageBasePath:
                self.transport, self.packageBase = self.get_transport(url)
                try:
                    return self.find_file(filename, packagePath)
                except RuntimeError:
                    self.transport, self.packageBase = None, None

            raise RuntimeError, \
                  ("Unable to find %s anywhere in %s" % (filename, " ".join(self.packageBasePath)))

        locs = self.createLocationList(filename, packagePath)

        subDirs = [""]
        for sd in ["", self.Eups.flavor]:
            if re.search('\.build$', filename):
                subDirs += [os.path.join('builds', sd)]
            elif re.search('\.manifest$', filename):
                subDirs += [os.path.join('manifests', sd)]
            elif re.search('\.table$', filename):
                subDirs += [os.path.join('tables', sd)]

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
                    except RuntimeError, e:
                        if self.Eups.verbose > 1:
                            print >> sys.stderr, e
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
                if create:
                    return os.path.join(self.packageBase, locs[0], subDirs[0], filename)

                raise RuntimeError, ("File %s doesn't exist in %s" % (filename, self.packageBase))

            filename = tfile

        if self.Eups.verbose > 1:
            print >> sys.stderr, "Found %s" % (filename)

        return filename

    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

    def lookup_tagged_version(self, productName):
        """Attempt to lookup a package's version with the specified tag, as declared using eups distrib"""

        try:
            for p in TaggedVersion(self).read():
                (name, flavor, version) = p
                if name == productName and flavor == self.Eups.flavor:
                    return version
        except:
            pass

        return ""

    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

    def createLocationList(self, filename, packagePath):
        """Create a list of places to look"""

        locs = []
        if self.preferFlavor:
            locs.extend([self.installFlavor, ''])
        else:
            locs.extend(['', self.installFlavor])

        if packagePath is not None:
            if self.preferFlavor:
                if self.preferredTag is not None:
                    locs.extend([os.path.join(packagePath, self.installFlavor, self.preferredTag),
                                 os.path.join(packagePath, self.installFlavor),
                                 os.path.join(packagePath, self.preferredTag),
                                 os.path.join(packagePath)])
                else:
                    locs.extend([os.path.join(packagePath, self.installFlavor),
                                 os.path.join(packagePath)])
            else:
                if self.preferredTag is not None:
                    locs.extend([os.path.join(packagePath, self.preferredTag),
                                 os.path.join(packagePath, self.installFlavor, self.preferredTag),
                                 os.path.join(packagePath),
                                 os.path.join(packagePath, self.installFlavor)])
                else:
                    locs.extend([os.path.join(packagePath),
                                 os.path.join(packagePath, self.installFlavor)])

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
                top_version = self.lookup_tagged_version(top_product)

                if top_version == "":
                    if self.tag:
                        msg = ("No version of %s is declared %s to eups distrib\n" +
                               "Please specify a version or a manifest file") % (top_product, self.tag)
                    else:
                        msg = ("I don't know which version of %s you want\n" +
                               "Please specify a version, a tag, or a manifest file") % (top_product)

                    raise RuntimeError, msg
                
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
            if re.search(r"^\s*(#.*)?$", line):
                continue

            try:
                products += [re.findall(r"\S+", line)[0:6]]
            except:
                raise RuntimeError, ("Failed to parse line:", line)

        return manifest_product, manifest_product_version, productsRoot, top_version, products

    def write_manifest(self, manifest, top_productName, top_version, products):
        """Write a manifest file"""
        
        manifestDir = os.path.join(self.packageBase, "manifests")
        if not os.path.isdir(manifestDir):
            try:
                os.mkdir(manifestDir)
            except:
                raise OSError, "I failed to create %s" % (manifestDir)

        if not manifest:
            manifest = os.path.join(manifestDir, self.manifestFile(top_productName, top_version))

        if os.access(manifest, os.R_OK) and not self.Eups.force:
            if self.Eups.verbose:
                print >> sys.stderr, "Not recreating", manifest
            return

        try:
            if not self.Eups.noaction:
                ofd = open(manifest, "w")
        except OSError, e:
            raise RuntimeError, ("Failed to open %s: %s" % manifest, e)

        if not self.Eups.noaction:
            print >> ofd, """\
EUPS distribution manifest for %s (%s). Version %s
#
# Creator:      %s
# Time:         %s
# Eups version: %s
#
# pkg           flavor       version    tablefile                 installation_directory    installID
#----------------------------------------------------------------------------------------------------""" % \
                  (top_productName, top_version, eups_distrib_version, self.Eups.who, eups.ctimeTZ(), eups.version())

        rproducts = products[:]; rproducts.reverse() # reverse the products list
        for p in rproducts:
            (productName, flavor, version, pDB, pdir, ptablefile, productDir, distID) = p

            if not flavor:
                if self.installFlavor:
                    flavor = self.installFlavor
                else:
                    flavor = eups.flavor()
                
            if not self.Eups.noaction:
                print >> ofd, "%-15s %-12s %-10s %-25s %-25s %s" % \
                      (productName, flavor, version, ptablefile, productDir, distID)

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
    fd, tfile = tempfile.mkstemp("", dir=eups.eupsTmpdir("distrib"))

    os.close(fd)

    try:
        system("scp -q %s %s 2>/dev/null" % (file, tfile), noaction)
        return tfile, None
    except OSError:
        os.unlink(tfile)
    #
    # Maybe it's a directory
    #
    tfile = tempfile.mkdtemp(dir=eups.eupsTmpdir("distrib"))
    atexit.register(lambda dir: shutil.rmtree(dir, ignore_errors=True), tfile)       # clean up

    try:
        system("scp -q -r %s %s 2>/dev/null" % (file, tfile), noaction)
    except OSError:
        raise RuntimeError, ("Failed to retrieve %s" % file)

    return os.path.join(tfile, os.path.basename(file)), None

def urlretrieve(file, noaction=False):
    """Like urllib's urlretrieve, except use urllib2 to detect 404 errors"""

    try:
        fd = urllib2.urlopen(file); del fd
    except urllib2.HTTPError:
        raise RuntimeError, ("Failed to open URL %s" % file)
    except urllib2.URLError:
        raise RuntimeError, ("Failed to contact URL %s" % file)
    return urllib.urlretrieve(file)

HTTPError = urllib2.HTTPError
URLError = urllib2.URLError

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def listdir(Distrib, url):
    """Return a list of the files specified by a directory URL"""

    if Distrib.transport == LOCAL:
        files = os.listdir(url)
    elif Distrib.transport == SCP:
        files = os.listdir(url)
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

        files = p.files
    else:
        raise AssertionError, ("I don't know how to handle transport == %s" % Distrib.transport)

    return filter(lambda f: not re.search(r"~$", f) and not re.search(r"^#.*#$", f), files)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def create(Distrib, top_productName, top_version, manifest=None):
    """Create a distribution"""

    if not Distrib.packageBase:         # use first element of path
        pb0 = Distrib.packageBasePath[0]
        Distrib.transport, Distrib.packageBase = Distrib.get_transport(pb0)

        if Distrib.transport != LOCAL:
            raise RuntimeError, ("I can only create packages locally, so %s is invalid" % pb0)

    if not os.path.isdir(Distrib.packageBase):
        if Distrib.Eups.verbose > 0:
            print >> sys.stderr, "Creating", Distrib.packageBase

        try:
            os.makedirs(Distrib.packageBase)
        except:
            raise RuntimeError, ("Failed to create %s" % Distrib.packageBase)

    if not top_version:
        top_version = Distrib.Eups.findCurrentVersion(top_productName)[1]

    if Distrib.noeups:
        productName = top_productName

        ptablefile = Distrib.find_file_on_path("%s.table" % productName)
        if not ptablefile:
            if Distrib.Eups.verbose > 0:
                print >> sys.stderr, "Unable to find a table file for %s; assuming no dependencies" % productName
                
            ptablefile = "none"

        productList = [(productName, top_version, False)]
        dependencies = Distrib.Eups.dependencies_from_table(ptablefile)
        if dependencies:
            for (product, optionalInTable, currentRequested) in dependencies:
                productName = product.name
                version = product.version
                if not version:
                    version = Distrib.Eups.findCurrentVersion(productName)[1]
                productList += [(productName, version, optionalInTable)]
    else:
        top_product = Distrib.Eups.Product(top_productName, top_version)
        productList = []
        for (product, optionalInTable, currentRequested) in top_product.dependencies(setupType="build"):
            productList += [(product.name, product.version, optionalInTable)]

    products = []
    for (productName, version, optional) in productList:
        if Distrib.Eups.verbose > 1:
            print "Product:", productName, "  Flavor:", Distrib.installFlavor, "  Version:", version

        if productName == top_productName and Distrib.noeups:
            baseDir, pDB, pdir = None, None, None
            productDir = "/dev/null"
        else:
            try:
                (pname, pversion, pDB, pdir, pcurrent, psetup) = Distrib.Eups.listProducts(productName, version)[0]
                if not pdir:
                    pdir = "none"
            except KeyboardInterrupt:
                sys.exit(1)
            except Exception, e:
                print >> sys.stderr, "WARNING: Failed to lookup directory for", \
                      "product:", productName, "  Flavor:", Distrib.installFlavor, "  Version:", version
                if productName == top_productName:
                    continue

            try:
                ptablefile = Distrib.Eups.Product(productName, version).table.file
                if False:               # when is this needed?
                    if ptablefile == "":
                        ptablefile = " "
            except KeyboardInterrupt:
                sys.exit(1)                    
            except Exception, e:
                print >> sys.stderr, "WARNING: Failed to lookup tablefile for", \
                      "product:", productName, "  Flavor:", Distrib.installFlavor, "  Version:", version
                if productName == top_productName:
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

        if productName == top_productName:
            if not distID:
                raise RuntimeError, "I don't know how to install %s %s; giving up" % (productName, version)
        else:
            # don't write explicit distIDs for dependent products --
            # that'd stop eups installing them recursively
            distID = None

        if not distID:
            pdir, ptablefile, productDir = "none", "none", "None"
        elif ptablefile != "none":
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
                if os.access(tablefile_for_distrib, os.R_OK) and not Distrib.Eups.force:
                    if Distrib.Eups.verbose > 1:
                        print >> sys.stderr, "Not recreating", tablefile_for_distrib
                else:
                    if Distrib.Eups.verbose > 1:
                        print >> sys.stderr, "Copying %s to %s" % (fulltablename, tablefile_for_distrib)
                    copyfile(fulltablename, tablefile_for_distrib)

        products += [[productName, Distrib.installFlavor, version, pDB, pdir, ptablefile, productDir, distID]]

        if Distrib.no_dependencies:
            if Distrib.Eups.force:
                break
            else:
                print >> sys.stderr, "Not writing manifest as you omitted dependencies; use --force to write it anyway"
    #
    # Time to write enough information to declare the products
    #
    Distrib.write_manifest(manifest, top_productName, top_version, products)
    #
    # We need to do this recursively
    #
    for (productName, flavor, version, pDB, pdir, ptablefile, productDir, distID) in products:
        if productName == top_productName:
            continue
        
        create(Distrib, productName, version)
    #
    # Maybe declare this version as satisfying Distrib.tag (if set)
    #
    createTaggedVersion(Distrib, top_productName, top_version)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class TaggedVersion(object):
    def __init__(self, Distrib):
        self.Distrib = Distrib
        self.tag = Distrib.tag

        self.file = self.Distrib.find_file(Distrib.taggedVersionFile(), create=True)

    def read(self):
        """Read a list of products from a tagged file (e.g. current.list)"""

        fd = open(self.file, "r")

        line = fd.readline()
        mat = re.search(r"^EUPS distribution %s version list. Version (\S+)\s*$" % self.tag, line)
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

            products += [(product, flavor, version)]

        return products

    def write(self, products):
        """Write a list of current products to file current"""

        if not self.Distrib.Eups.noaction:
            ofd = open(self.file, "w")

        if self.Distrib.Eups.verbose > 1:
            print >> sys.stderr, "Writing %s product list to %s" % (self.tag, self.file)

        if not self.Distrib.Eups.noaction:
            print >> ofd, """\
EUPS distribution %s version list. Version %s
#product             flavor     version
#--------------------------------------\
""" % (self.tag, eups_distrib_version)

        #
        # Be nice and sort the products
        #
        def pfsort(a,b):
            """Sort by product, then flavor"""

            if a[0] == b[0]:
                return cmp(a[1], b[1])
            else:
                return cmp(a[0], b[0])

        products = products[:]
        products.sort(pfsort)

        for p in products:
            if not self.Distrib.Eups.noaction:
                print >> ofd, "%-20s %-10s %s" % p

def createTaggedVersion(Distrib, top_productName, top_version):
    """Create a list of packages that are declared as having property Distrib.tag (e.g. current)"""

    if not Distrib.tag:
        return
    #
    # Extract the up-to-date information about current versions,
    # and add it to the previously existing list [if any]
    #
    assert top_version
    dp = [(top_productName, Distrib.installFlavor, top_version)]
    if not  Distrib.Eups.listProducts(top_productName, top_version):
        print >> sys.stderr, "WARNING: failed to find a version \"%s\" of product %s" % \
              (top_version, top_productName)

    if Distrib.Eups.verbose:
        print >> sys.stderr, "Declaring version %s %s to eups distrib as \"%s\"" % \
              (top_productName, top_version, Distrib.tag)
    #
    # Now lookup list of current versions
    #
    lock = Distrib.Eups.lockDB(Distrib.packageBase, upsDB=False)

    taggedVersion = TaggedVersion(Distrib)

    try:
        products = taggedVersion.read()
    except Exception, e:
        eups.debug(e)
        products = []

    nproducts = []
    for p, f, v in products:
        if p == top_productName and f == Distrib.Eups.flavor:
            continue

        nproducts += [(p, f, v)]

    products = nproducts

    products += dp
    #
    # Now write the file containing taggedVersion version info.
    #
    taggedVersion.write(products)

def install(Distrib, top_product, top_version, manifest):
    """Install a set of packages"""

    #
    # N.b. this is a circular dependency (as eupsDistribFactory imports this file),
    # so don't try to move this import up to the top of the file
    #
    import eupsDistribFactory

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
        
        if productDir != "none" and not re.search(r"^/", productDir):
            productDir = os.path.join(productsRoot, productDir)

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
                Distrib.Eups.undeclare(productName, versionName, undeclare_current=(Distrib.tag=="current"))
            else:
                continue
        #
        # If we're asking for a tagged distribution, ignore the distID as it specifies an
        # explicit version.  We don't do this for the toplevel product as we don't enjoy infinite recursion 
        #
        if Distrib.tag and productName != top_product:
            if Distrib.Eups.verbose > 1:
                print >> sys.stderr, "Ignoring distID %s as you specified tag %s" % (distID, Distrib.tag)
            distID = "None"
        #
        # We need to install and declare this product
        #
        dodeclare = True

        if distID == "None": # we weren't told how to install this product; maybe they don't know,
            # or maybe they want us to call distrib recursively
            if productName == top_product:
                raise RuntimeError, ("Manifest for %s %s doesn't have install instructions for itself; giving up" % \
                                     (productName, versionName))
            
            if Distrib.Eups.verbose > 2:
                print >> sys.stderr, "Manifest for %s doesn't have install instructions for %s; trying eups distrib --install %s %s" % \
                      (top_product, productName, productName, versionName)
            try:
                subDistrib = eupsDistribFactory.copyDistrib(None, Distrib)

                if False:
                    # remove the path we've already tried
                    subDistrib.remove_packageBase(Distrib.transport, Distrib.packageBase)

                if not subDistrib.packageBasePath:
                    raise RuntimeError, ("I have nowhere else to look for %s %s" % (productName, versionName))

                if Distrib.tag:            # use tagged version, ignoring the version name
                    if Distrib.Eups.verbose:
                        print >> sys.stderr, "Using tag %s not %s for %s" % (Distrib.tag, versionName, productName)
                    versionName = None
                    
                install(subDistrib, productName, versionName, None)
                continue
            except RuntimeError, e:
                if not Distrib.Eups.force or Distrib.Eups.verbose > 0:
                    print >> sys.stderr, "Detected problem installing %s: %s" % (productName, e)
                if not Distrib.Eups.force:
                    print >> sys.stderr, "Specify force to proceed"
                    sys.exit(1)
                dodeclare = False
        else:
            #
            # Choose the correct sort of eupsDistrib
            #
            impl = eupsDistribFactory.getImplementation(distID)
            eupsDistribFactory.Distrib(impl, Distrib).installPackage(distID, productsRoot, setups)

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
        # If no versions of this product are declared current, we need to make this one
        # current to allow products to set it up without an explicit version
        #
        declare_current = (Distrib.tag == "current")

        if not declare_current and len(Distrib.Eups.listProducts(productName, current=True)) == 0:
            declare_current = True
        #
        # Declare our product.  We need to deal with table files which are
        # not in product root (i.e. -M files)
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

            Distrib.Eups.declare(productName, versionName, productDir, tablefile=tablefile,
                                 eupsPathDir=eupsPathDir, declare_current=declare_current)
        else:                           # we may still need to declare it current
            if declare_current:
                Distrib.Eups.declareCurrent(productName, versionName, eupsPathDir=productsRoot)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def listProducts(Distrib, top_product, top_version, manifest):
    """List available packages; if Distrib.tag=="current" list versions declared current to eupsDistrib.
    Matching for product and version is a la shell globbing (i.e. using fnmatch)"""    


    available = []                      # available products
    if Distrib.tag:
        if False:
            fd = open(Distrib.find_file(Distrib.taggedVersionFile()), "r")
            fd.readline()                   # skip header

            for line in fd.readlines():
                if re.search(r"^\s*(#.*)?$", line):
                    continue

                line = line[:-1]            # remove newline
                available += [line.split(r"\s*")]
        else:
            taggedVersion = TaggedVersion(Distrib)
            available = taggedVersion.read()            
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
        if top_product and not fnmatch.fnmatchcase(manifest_product, top_product):
            continue
        if top_version and not fnmatch.fnmatchcase(manifest_product_version, top_version):
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

#!/usr/bin/env python
# -*- python -*-
"""
classes for communicating with a remote package server
"""
import sys, os, re, atexit, shutil
import fnmatch
import tempfile
import urllib2
import eups
import eups.hooks as hooks
import eups.utils as utils

from eups.exceptions import EupsException

serverConfigFilename = "config.txt"
BASH = "/bin/bash"    # see end of this module where we look for bash

class DistribServer(object):
    """a class that encapsulates the communication with a package server.

    This class allows the mechanisms (e.g. the URLs) used to retrieve 
    information from a server to be specialized to that server. 

    This class is intended  primarily as a base class for customizations.
    Typically the following files are would be over-ridden for a particular
    type of server:
        getFileForProduct()
        getFile()
        listFiles()
    The default implementations of the other functions pull their information 
    (e.g. manifests, product tag assignments) via the ones above; however, the 
    other functions may be overridden as well for finer control.  See function 
    documentation for more details.  See also ConfigurableDistribServer
    for an example of specializing.

    This base implementation assumes a simple set of URLs for retrieving files
    from a server with no special support for flavors or tags.  
    """

    def __init__(self, packageBase, config=None, verbosity=0, log=sys.stderr):
        """create a server communicator
        @param packageBase   the base URL for the server
        @param config        a dictionary of parameters for configuring the 
                               the behavior of this DistribServer.  Normally,
                               these are 
        @param verbosity     if > 0, print status messages; the higher the 
                               number, the more messages that are printed
                               (default=0).
        @param log           the destination for status messages (default:
                               sys.stderr)
        """
        # the root (URL) of the distribution server
        self.base = packageBase

        # a numeric measure of how chatty this instance should be
        self.verbose = verbosity

        # a file object to send messages to
        self.log = log

        # a cache of tag assignment lists.  The lookup is by tag name and then
        # product name.  
        self.tagged = {}

        # configuration data
        if config is None:  config = {}
        self.config = config
        self._initConfig_()

    def _initConfig_(self):
        pass

    def getManifest(self, product, version, flavor, noaction=False):
        """request the manifest for a particular product and return it as 
        a Manifest instance.

        This implementation calls getFileForProduct() to retrieve the manifest
        file and then reads via the Manifest class.  It is not necessary to 
        override this unless you want to use a different Manifest implementation.

        @param product     the desired product name
        @param version     the desired version of the product
        @param flavor      the flavor of the target platform
        """
        if noaction:
            return Manifest()
        else:
            try:
                file = self.getFileForProduct("", product, version, flavor, 
                                              "manifest", noaction=noaction)
                return Manifest.fromFile(file, self.getConfigProperty("RECURSE_OVER_MANIFEST"),
                                         verbosity=self.verbose)
            except RuntimeError, e:
                raise RuntimeError("Trouble reading manifest for %s %s (%s): %s"
                                   % (product, version, flavor, e))
            except RemoteFileNotFound, e:
                msg = "Product %s %s for %s not found on server" % \
                    (product, version, flavor)
                raise RemoteFileNotFound(msg, e)

    def getTagNames(self, flavor=None, noaction=False):
        """
        return the names of the tags supported by this server as a list.

        This implementation will discover what files of the form *.list 
        are available on the server, where * is a tag name.  The flavor 
        parameter is ignored.
        """
        return map(lambda x: x[:-5], 
                   filter(lambda f: f.endswith(".list"), 
                          self.listFiles("", noaction)))

    def getTagNamesFor(self, product, version, flavor="generic", tags=None, noaction=False):
        """
        return as a list of strings all of the tag names assigned to 
        the given product by the server, followed by a list of strings of all tags known to the server
        @param product     the name of the product
        @param version     the product's version
        @param flavor      the platform flavor (default: generic)
        @param tags        if set, the returned list will be the intersection
                             of the tags assigned by the server with this list.
                             By providing this, one can remove the need to 
                             query the server for its list of supported tags.  
        """
        if tags is None:
            tags = self.getTagNames()
        if isinstance(tags, str):
            tags = tags.split()

        out = []
        for tag in tags:
            info = self.getTaggedProductInfo(product, flavor, tag)
            if info[2] == version:
                out.append(tag)
        return out, tags

    def getTaggedProductList(self, tag="current", flavor=None, noaction=False):
        """request the product list for a particular tag name (default: 
        "current") and return it as TaggedProductList instance.

        This implementation downloads a single product list file on a per-tag
        basis (the flavor parameter is ignored), and the results are parsed 
        into a TaggedProductList instance and cached internally for subsequent
        calls to this function.  It is not necessary to override this unless 
        you want to use a different TaggedProductList implementation.

        @param tag         a logical name assigned to versions of products
        @param flavor      the flavor of the platform of interest.  If None
                             (default) or "generic", then a platform-generic
                             list is desired.  An implementation may choose
                             to ignore this value (e.g. if all lists are 
                             generic).
        @param filename    the recommended name of the file to write to; the
                             actual name may be different (if, say, a local 
                             copy is already cached).  If None, a name will
                             be generated.
        @param noaction    if True, simulate the retrieval
        """
        if self.tagged.has_key(tag) and self.tagged[tag]:
            return self.tagged[tag]

        if noaction:
            if flavor is None:  flavor = "generic"
            return TaggedProductList(tag, flavor, self.verbose-1, self.log)
        else:
            try:
                file = self.getFile("", flavor, tag, "list", noaction=noaction)
                self.tagged[tag] = \
                    TaggedProductList.fromFile(file, tag, 
                                               verbosity=self.verbose-1,
                                               log=self.log)
                return self.tagged[tag]

            except RemoteFileNotFound, e:
                if flavor is None:
                    flavor = "a generic platform"
                
                msg = 'Product tag "%s" for %s not found on server' % (tag, flavor)
                raise RemoteFileNotFound(msg, e)

    def getTaggedProductInfo(self, product, flavor, tag=None):
        """
        return a list with the current info for the given product.  This 
        list will contain at least 3 elements where the first three elements
        are the product name, flavor, and version.  

        This implementation calls getTaggedProductList() and looks up the 
        information.  This can be overridden if there is a different way to 
        get product information from the server for a single product. 
        """
        if tag is None:
            tag = "current"
        pl = self.getTaggedProductList(tag, flavor)
        out = [product]
        out.extend(pl.getProductInfo(product))
        return out

    def getTableFile(self, product, version, flavor, filename=None, 
                     noaction=False):
        """return the name of a local file containing a copy of the EUPS table
        file for a desired product retrieved from the server.

        This method encapsulates the mechanism for retrieving a table file 
        from the server; sub-classes may over-ride this to specialize for a 
        particular type of server.  This implementation ignores the flavor 
        and tag input parameters.

        @param product     the desired product name
        @param version     the desired version of the product
        @param flavor      the flavor of the target platform
        @param tag         an optional name for a variant of the product
        @param filename    the recommended name of the file to write to; the
                             actual name may be different (if, say, a local 
                             copy is already cached).  If None, a name will
                             be generated.
        @param noaction    if True, simulate the retrieval
        """
        return self.getFileForProduct("", product, version, flavor, "table",
                                      filename=filename, noaction=noaction)

    def listAvailableProducts(self, product=None, version=None, flavor=None,
                              tag=None, noaction=False):
        """return a list of available products on the server.  Each item 
        in the list is a list of the form, (product, version, flavor).
        The optional inputs will restrict the list to those matching the 
        values.  

        The following calls may return equivalent results:
           distribServer.listAvailableProducts(flavor=flavor, tag=tag)
           distribServer.getTaggedProductList(tag, flavor)
        If they differ, it will be in that the getTaggedProductList() results
        contains additional information for one or more products.  

        This implementation will end up reading every manifest file available
        on the server.  Sub-classes should do something more efficient.

        @param product     the desired product name
        @param version     the desired version of the product
        @param flavor      the flavor of the target platform
        @param tag         an optional name for a tag assigned to the product
        """

        out = []
        if flavor is not None and tag is not None:
            try:
                for val in self.getTaggedProductList(tag, flavor).getProducts():
                    if product and product != val[0]:
                        continue
                    if flavor == val[1]:
                        out += [(val[0], val[2], val[1])]
            except ServerNotResponding, e:
                print >> self.log, e
        else:
            files = self.listFiles("manifests", flavor, tag)
            for file in files:
                # each file is a manifest; check its product/version/flavor
                # by reading the manifest's header
                file = self.getFile("manifests/"+file, flavor, tag)
                man = Manifest.fromFile(file);

                if product and not fnmatch.fnmatchcase(man.product, product):
                    continue
                if version and not fnmatch.fnmatchcase(man.version, version):
                    continue
                if flavor and man.flavor != flavor:
                    continue

                out.append([man.product, man.version, man.flavor])

        return out

    def getFile(self, path, flavor=None, tag=None, ftype=None, 
                filename=None, noaction=False):
        """return a copy of a file with a given path on the server.  The 
        actual path used to retrieve the file may be different depending on
        the values of the other inputs.  

        This implementation simply looks for the path directly below the 
        base URL.  The flavor paramter is ignored.  

        @param path        the path on the remote server to the desired file
        @param flavor      the flavor of the target platform
        @param tag         an optional name for a variant of the file; the 
                             implementation may ignore this parameter
        @param ftype       a type of file to assume; if not provided, the 
                              extension will be used to determine the type
        @param filename    the recommended name of the file to write to; the
                             actual name may be different (if, say, a local 
                             copy is already cached).  If None, a name will
                             be generated.
        @param noaction    if True, simulate the retrieval
        """
        if ftype == "list" and path=="":
            src = "%s/%s.list" % (self.base, self.tag)
        else:
            src = "%s/%s" % (self.base, self.path)

        if filename is None:  filename = self.makeTempFile("path_")
        return self.cacheFile(filename, src, noaction);

    def getFileForProduct(self, path, product, version, flavor, 
                          ftype=None, filename=None, noaction=False):
        """return a copy of a file with a given path on the server associated
        with a given product.

        This implementation simply calls getFile(), ignoring the product name
        and version inputs.  

        @param path        the path on the remote server to the desired file
        @param product     the desired product name
        @param version     the desired version of the product
        @param flavor      the flavor of the target platform
        @param ftype       a type of file to assume; if not provided, the 
                              extension will be used to determine the type
        @param filename    the recommended name of the file to write to; the
                             actual name may be different (if, say, a local 
                             copy is already cached).  If None, a name will
                             be generated.
        @param noaction    if True, simulate the retrieval
        """
        return getFile(path, flavor, ftype=ftype, filename=filename, 
                       noaction=noaction)
#        src = "%s/%s/%s" % (self.base, product, version)
#        if flavor is not None and flavor != "generic":
#            src = "%s/%s" % (src, flavor)
#        src = "%s/%s" % (src, path)

#        if filename is None:  filename = self.makeTempFile(product + "_path_")
#        return self.cacheFile(filename, src, noaction)

    def listFiles(self, path, flavor=None, tag=None, noaction=False):
        """return a list of filenames under a server directory referred to 
        by path.  The actual directory on the server may be different, depending
        on flavor and tag.  

        In this implementation, the flavor and tag values are ignored.

        @param path        the path on the remote server to the desired file
        @param flavor      the flavor of the target platform
        @param tag         an optional name for a variant of the file; the 
                             implementation may ignore this parameter
        """
        source = "%s/%s" % (self.base, path)
        trx = makeTransporter(source, self.verbose-1, self.log)
        return trx.listDir(noaction=noaction)

    def makeTempFile(self, prefix):
        return makeTempFile(prefix)

    def cacheFile(self, filename, source, noaction=False):
        """cache a copy of a file to a file with the given name
        @param filename    the name of the file to write to
        @param source      the name of the remote file to obtain a copy of 
        @param noaction    if True, simulate the retrieval
        """
        trx = makeTransporter(source, self.verbose-1, self.log)

        # make sure we can write to destination
        parent = os.path.dirname(filename)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)

        trx.cacheToFile(filename, noaction=noaction)
        return filename

    def getConfigFile(self, filename=None, noaction=False):
        """return a file that is a copy of the Distrib configuration retrieved
        from the server.
        @param filename    the recommended name of the file to write to; the
                             actual name may be different (if, say, a local 
                             copy is already cached).  If None, a name will
                             be generated.
        @param noaction    if True, simulate the retrieval
        """
        src = "%s/%s" % (self.base, serverConfigFilename)
        if filename is None:  filename = self.makeTempFile("config_")
        return self.cacheFile(filename, src, noaction)

    def getConfigProperty(self, name, defval=None):
        """return a the value of a named configuration property.  If 
        multiple values are stored by this name, return the last one
        saved.  (If all values are desired, use getConfigPropertyList()).
        @param name   the name of the parameter
        @param deval  a default value to return if a value is not current
                        for this property name.
        """
        if not self.config.has_key(name):
            return defval
        out = self.config[name]
        if not isinstance(out, list):
            return out
        if len(out) == 0 or out[-1] is None:
            return defval
        return out[-1]

    def getConfigPropertyList(self, name, defval=None, minlen=0):
        """return all values of a configuration property stored with the 
        given name as a list.  This is guaranteed to always return a list.
        (See also getConfigPropertyList()).
        @param name     the name of the parameter
        @param defval   a default value to return if a value is not current
                          for this property name.  If this value is a list,
                          the whole list serves as the default value.  If 
                          it is not a list, it will be interpreted as the 
                          default value for each missing value up to the 
                          value of minlen.  In this case, the defval will 
                          only be used when minlen > 0 and when the stored
                          value has fewer than minlen elements.
        @param minlen   the minimum number of element the returned list must
                          have.  Any missing values with an index below this 
                          number will be provided as the value of defval.
        """
        if not self.config.has_key(name):
            if not isinstance(defval, list):
                defval = [defval] * minlen
            return defval
        out = self.config[name]
        if not isinstance(out, list):
            out = [out]
        if len(out) < minlen:
            if not isinstance(defval, list):
                defval = [defval] * minlen
            out.extend(defval[len(out):])
        return out

    def setConfigProperty(self, name, value):
        """update the value associated with the configuration property name.
        if the value is not a list, then it is just appended to the list of 
        current values.  If it is a list, then all previous values are 
        replaced with the list.  
        """
        if isinstance(value, list):
            self.config[name] = value
        else:
            if not self.config.has_key(name):
                self.config[name] = []
            self.config[name].append(value)

    def popConfigProperty(self, name):
        """remove the most recently set value associated with the given 
        configuration property name, revealing the previously set value.
        The removed value is returned.
        """
        if not self.config.has_key(name):
            return None

        out = self.config[name].pop(-1)
        if len(self.config[name]) == 0:
            del self.config[name]
        return out

    def clearConfigCache(self, eupsenv=None, verbosity=None):
        """
        clear the local server configuration cache for this server.
        @param eupsenv     the Eups instance to use to locate the cache.  If 
                             None, a default one will be created.
        @param verbosity   the level of verbosity.  If None, the default
                             verbosity set for this instance will be assumed.
        """
        if eupsenv is None:  eupsenv = eups.Eups()
        if verbosity is None: verbosity = self.verbose
        ServerConf.clearConfigCache(eupsenv, [self.base], verbosity, self.log)


class ConfigurableDistribServer(DistribServer):
    """
    a distribution server that forms locations based on templated strings.
    """

    def _initConfig_(self):
        DistribServer._initConfig_(self)

        # allowed keys in config files
        validKeys = ["DISTRIB_CLASS", "DISTRIB_SERVER_CLASS", "AVAILABLE_PRODUCTS_URL", "MANIFEST_DIR",
                     "BUILD_URL",
                     "MANIFEST_URL", "TABLE_URL", "LIST_URL", "PRODUCT_FILE_URL", "FILE_URL", "DIST_URL",
                     "MANIFEST_DIR_URL", "MANIFEST_FILE_RE", "PREFER_GENERIC", ]

        for k in self.config.keys():
            if not (k in validKeys):
                print >> self.log, "Invalid config parameter %s ignored" % k

        if not self.config.has_key('MANIFEST_URL'):
            self.config['MANIFEST_URL'] = \
                "%(base)s/manifests/%(product)s-%(version)s.manifest";
        if not self.config.has_key('TABLE_URL'):
            self.config['TABLE_URL'] = \
                "%(base)s/tables/%(product)s-%(version)s.table";
        if not self.config.has_key('LIST_URL'):
            self.config['LIST_URL'] = "%(base)s/%(tag)s.list";
        if not self.config.has_key('PRODUCT_FILE_URL'):
            self.config['PRODUCT_FILE_URL'] = \
                "%(base)s/%(product)s/%(version)s/%(path)s";
        if not self.config.has_key('FILE_URL'):
            self.config['FILE_URL'] = "%(base)s/%(path)s";
        if not self.config.has_key('DIST_URL'):
            self.config['DIST_URL'] = "%(base)s/%(path)s";
        if not self.config.has_key('MANIFEST_DIR_URL'):
            self.config['MANIFEST_DIR_URL'] = "%(base)s/manifests";
        if not self.config.has_key('MANIFEST_FILE_RE'):
            self.config['MANIFEST_FILE_RE'] = \
                r"^(?P<product>[^\-\s]+)(-(?P<version>\S+))?" + \
                r"(@(?P<flavor>[^\-\s]+))?.manifest$"

        if self.getConfigProperty('PREFER_GENERIC', '').upper() == 'FALSE':
            self.popConfigProperty('PREFER_GENERIC')
            self.setConfigProperty('PREFER_GENERIC', False)

    def getFile(self, path, flavor=None, tag=None, ftype=None, 
                filename=None, noaction=False):
        """return a copy of a file with a given path on the server.  
        @param path        the path on the remote server to the desired file
        @param flavor      the flavor of the target platform
        @param tag         an optional name for a variant of the file; the 
                             implementation may ignore this parameter
        @param ftype       a type of file to assume; if not provided, the 
                              extension will be used to determine the type
        @param filename    the recommended name of the file to write to; the
                             actual name may be different (if, say, a local 
                             copy is already cached).  If None, a name will
                             be generated.
        @param noaction    if True, simulate the retrieval
        """
        values = { "path": path,
                   "flavor": flavor,
                   "tag": tag,
                   "base": self.base }
        if flavor is None:  values["flavor"] = "generic"
        if filename is None:  filename = self.makeTempFile("file_")

        # determine the extension to determine the type of file we are 
        # retrieving; this may affect the ultimate URL
        if ftype is None:
            ftype = os.path.splitext(path)[1]
            if ftype.startswith("."):  ftype = ftype[1:]

        if self._fileViaTmpl8s(ftype, values, filename, noaction):
            return filename

        if ftype != "FILE":
            return self.getFile(path, flavor, tag, "FILE", filename, noaction)

        # this shouldn't happen
        return DistribServer.getFile(self, path, flavor, tag, None, 
                                     filename, noaction)
        

    def getFileForProduct(self, path, product, version, flavor, 
                          ftype=None, filename=None, noaction=False):
        """return a copy of a file with a given path on the server associated
        with a given product.

        @param path        the path on the remote server to the desired file
        @param product     the desired product name
        @param version     the desired version of the product
        @param flavor      the flavor of the target platform
        @param ftype       a type of file to assume; if not provided, the 
                              extension will be used to determine the type
        @param filename    the recommended name of the file to write to; the
                             actual name may be different (if, say, a local 
                             copy is already cached).  If None, a name will
                             be generated.
        @param noaction    if True, simulate the retrieval
        """
        values = { "path": path,
                   "product": product,
                   "version": version,
                   "flavor": flavor,
                   "base": self.base }
        if filename is None:  filename = self.makeTempFile(product + "_")

        # determine the extension to determine the type of file we are 
        # retrieving; this may affect the ultimate URL
        if ftype is None:
            ftype = os.path.splitext(path)[1]
            if ftype.startswith("."):  ftype = ftype[1:]

        if self._fileViaTmpl8s(ftype, values, filename, noaction):
            return filename

        if ftype != 'PRODUCT_FILE':
            return self.getFileForProduct(path, product, version, flavor, 
                                          'PRODUCT_FILE', filename, noaction)

        # this shouldn't happen
        return DistribServer.getFileForProduct(self, path, product, version, 
                                               flavor, None, filename, 
                                               noaction)

    def _fileViaTmpl8s(self, ftype, data, filename, noaction=False):
        ftype = ftype.upper()
        if len(ftype) == 0 or not self.getConfigProperty("%s_URL" % ftype):
            return False

        locations = ("TAGGED", "FLAVOR", "")
        if self.getConfigProperty('PREFER_GENERIC', ''):
            locations = ("TAGGED", "", "FLAVOR")

        for i in range(len(locations)):
            if locations[i] == "":
                param = "%s_URL" % ftype
            else:
                param = "%s_%s_URL" % (ftype, locations[i])
            tmpl = self.getConfigProperty(param, None)

            if tmpl is None:
                if self.verbose > 2:
                    print >> self.log, \
                        "Config parameter, %s, not set; skipping" % param
                continue

            if locations[i] == "TAGGED" and \
                    (not data.has_key('tag') or data['tag'] is None):
                if self.verbose > 1:
                    print >> self.log, \
                        "tag not specified; skipping", param, "location"
                continue
            if locations[i] == "FLAVOR" and \
                    (not data.has_key('flavor') or data['flavor'] is None):
                if self.verbose > 1:
                    print >> self.log, \
                        "flavor not specified; skipping", param, "location"
                continue

            if self.verbose > 2:
                print >> self.log, "Trying retrieve using", param, "to", filename
            try:
                src = tmpl % data
            except KeyError, e:
                msg = 'Server configuration error: bad template, %s: Key, %s, not available for %s' % (param, str(e), tmpl)
                raise RuntimeError(msg)

            if self.verbose > 0:
                print >> self.log, "Looking on server for", src
            if i == len(locations)-1:
                return self.cacheFile(filename, src, noaction)
            else: 
                try:
                    return self.cacheFile(filename, src, noaction)
                except RemoteFileNotFound, e:
                    if self.verbose > 1:
                        print >> self.log, "Not found; checking next alternative"
                except Exception, e:
                    if self.verbose >= 0:
                        print >> self.log, "Warning: trouble retrieving", \
                            "%s: %s" % (os.path.basename(src), str(e))
                        print >> self.log, "   (Trying alternate location)"

        # shouldn't happen
        src = self.getConfigProperty("%s_URL" % ftype) % data
        if self.verbose > 0:
            print >> self.log, "Failed to find %s in %s; looking on server" % (src, locations)
        return self.cacheFile(filename, src, noaction)

    def getTagNames(self, flavor=None, noaction=False):
        """
        return the names of the tags supported by this server as a list.

        This implementation three possible ways of retrieving this 
        information; each is tried in order until success:
          1) if the configuration parameter AVAILABLE_TAGS is set, it
               is assumed to contain a space-delimited list of tag names.
          2) if the AVAILABLE_TAGS_URL config parameter is set, it will 
               be used as a template to create a URL that returns a plain
               text file (MIME type: text/plain) in which each line gives
               a space-delimited list of available tag names.  
          3) if the TAGLIST_DIR config parameter is set, it will be used
               as a template to create a path to a directory on the 
               server containing all tag list files.  A file listing is 
               obtained by calling self.listFiles(path, None, None).  
               Each returned filename parsed according to the regular 
               expression provided in the TAGLIST_FILE_RE config parameter 
               (default: r"(?P<tag>[^\.]+)\.list$") to extract a tag name 
               (bylooking for a named group, "tag").  
        """
        out = self.getConfigProperty("AVAILABLE_TAGS")
        if out is not None:
            return out.split()

        out = []
        data = { "base":    self.base,
                 "flavor":  flavor     }
        tmpl = self.getConfigProperty("AVAILABLE_TAGS_URL")
        if tmpl is not None:
            src = tmpl % data
            file = self.makeTempFile("tagnames_")
            commre = re.compile(r'\s*#')
            try:
                file = self.cacheFile(file, src, noaction)
                fd = open(file)
                try:
                    for line in fd:
                        line = commre.split(line)[0].strip()
                        out.extend(line.split())
                finally:
                    fd.close()
                return out

            except TransporterError:
                pass

        filere = self.getConfigProperty("TAGLIST_FILE_RE", 
                                        r"^(?P<tag>[^\.]+)\.list$")
        filere = re.compile(filere)
        src = self.getConfigProperty("TAGLIST_DIR", "") % data

        try:
            files = self.listFiles(src, None, None, noaction)
        except RemoteFileNotFound, e:
            print >> self.log, e
            files = []
        except ServerNotResponding, e:
            print >> self.log, e
            files = []

        for file in files:
            m = filere.search(file)
            if m is None: continue
            m = m.groupdict()
            if m.has_key("tag") and m["tag"]:
                out.append(m["tag"])

        return out

    def listAvailableProducts(self, product=None, version=None, flavor=None,
                              tag=None, noaction=False):
        """return a list of available products on the server.  Each item 
        in the list is a list of the form, (product, version, flavor).
        The optional inputs will restrict the list to those matching the 
        values.  

        The following calls may return equivalent results:
           distribServer.listAvailableProducts(flavor=flavor, tag=tag)
           distribServer.getTaggedProductList(tag, flavor)
        If they differ, it will be in that the getTaggedProductList() results
        contains additional information for one or more records.  

        This implementation has three possible ways of retrieving this 
        information; each is tried in order until success:
          1) if both flavor and tag are specified, this function will 
               call getTaggedProductInfo()
          2) if the AVAILABLE_PRODUCTS_URL config paramter is set, it will 
               be used as a template to create a URL that returns a plain 
               text file (MIME type: text/plain) in which line gives an 
               available product's name, version, and flavor (delimited by
               spaces).  This is parsed and returned.
          3) if the MANIFEST_DIR config parameter is set, it will be 
               be used as a template to create a path to a directory on 
               the server containing all manifest files.  A file listing
               is obtained by calling self.listFiles(path, None, None).
               Each returned filename is parsed according to the regular 
               expression provided in the MANIFEST_FILE_RE config 
               parameter to extract the product data.  This expression
               uses named groups to extract parameters named "product",
               "version", and "flavor".

        @param product     the desired product name
        @param version     the desired version of the product
        @param flavor      the flavor of the target platform
        @param tag         an optional name for a tag assigned to the product
        @param noaction    if True, simulate the retrieval
        """
        if flavor and tag:
            return DistribServer.listAvailableProducts(self, product, version, flavor, tag, noaction)

        data = { "base":   self.base, 
                 "flavor": flavor,
                 "tag":    tag        }
        tmpl = self.getConfigProperty("AVAILABLE_PRODUCTS_URL")
        if tmpl is not None:
            src = tmpl % data
            file = self.makeTempFile("prods_")
            commre = re.compile(r'\s*#')
            try:
                file = self.cacheFile(file, src, noaction)

                out = []
                fd = open(file)
                try:
                    for line in fd:
                        line = commre.split(line)[0].strip()
                        if len(line) == 0:
                            continue
                        info = line.split()
                        if len(info) > 3:
                            info = info[:3]
                        out.append(info)
                finally:
                    fd.close()

                return out
                    
            except TransporterError:
                pass

        filere = self.getConfigProperty("MANIFEST_FILE_RE")
        if filere is not None:
            filere = re.compile(filere)
            src = self.getConfigProperty("MANIFEST_DIR", "manifests") % data

            try:
                files = self.listFiles(src, flavor, tag, noaction)
            except RemoteFileNotFound, e:
                print >> self.log, e
                files = []
            except ServerNotResponding, e:
                print >> self.log, e
                files = []

            out = []
            for file in files:
                m = filere.search(file)
                if m is None: continue
                m = m.groupdict()
                if not m["product"] or  \
                   (product and not fnmatch.fnmatchcase(m["product"], product)) or \
                   (version and not fnmatch.fnmatchcase(m["version"], version)):
                    continue

                info = [m["product"], "unknown", "generic"]
                if m["version"]:  info[1] = m["version"]
                if m["flavor"]:  info[2] = m["flavor"]
                out.append(info)

            return out
                
        # this shouldn't happen
        return DistribServer.listAvailableProducts(product, version, flavor, tag,
                                                   noaction)



class ServerError(EupsException):
    """an exception representing a problem communicating with a server"""
    def __init__(self, message, exc=None):
        """create a server error exception
        @param message    the reason for the error
        @param exc        a caught exception representing underlying symptom
        """
        EupsException.__init__(self, message)
        self.exc = exc
    def __str__(self):
        out = self.msg
        if self.exc is not None:
            out += " (%s)" % str(self.exc)
        return out

class TransporterError(ServerError):
    """a general error transporting data/information from the server"""
    def __init__(self, message, exc=None):
        """create a server error exception
        @param message    the reason for the error
        @param exc        a caught exception representing underlying symptom
        """
        ServerError.__init__(self, message, exc)
class RemoteFileNotFound(TransporterError):
    """an error indicating that a requested file was not found on the server"""
    def __init__(self, message, exc=None):
        """create a server error exception
        @param message    the reason for the error
        @param exc        a caught exception representing underlying symptom
        """
        TransporterError.__init__(self, message, exc)
    def __str__(self):
        return self.msg
class ServerNotResponding(TransporterError):
    """an error indicating a problem connecting to the server"""
    def __init__(self, message, exc=None):
        """create a server error exception
        @param message    the reason for the error
        @param exc        a caught exception representing underlying symptom
        """
        TransporterError.__init__(self, message, exc)
            
class Transporter(object):
    """a class that understands how to operate a particular transport 
    mechanism.

    This is an abstract class with an implementation that raises exeptions
    """
    # @staticmethod   # requires python 2.4
    def canHandle(source):
        """return True if this source location is recognized as one that 
        can be handled by this Transporter class"""
        return False;

    canHandle = staticmethod(canHandle)  # should work as of python 2.2

    def __init__(self, source, verbosity=0, log=sys.stderr):
        """create the transporter.
        @param source    the location of the source file 
        @param verbosity     if > 0, print status messages; the higher the 
                               number, the more messages that are printed
                               (default=0).
        @param log           the destination for status messages (default:
                               sys.stderr)
        """
        self.loc = source
        self.verbose = verbosity
        self.log = log

    def cacheToFile(self, filename, noaction=False):
        """cache the source to a local file
        @param filename      the name of the file to cache to
        @param noaction      if True, simulate the result (default: False)
        """
        self.unimplemented("cacheToFile");

    def listDir(self, noaction=False):
        """interpret the source as a directory and return a list of files
        it contains
        @param noaction      if True, simulate the result (default: False)
        """
        self.unimplemented("listDir")

    def unimplemented(self, name):
        raise Exception("%s: unimplemented (abstract) method" % name)

class WebTransporter(Transporter):
    """a class that can return files via an HTTP or FTP URL"""

    # @staticmethod   # requires python 2.4
    def canHandle(source):
        """return True if this source location is recognized as one that 
        can be handled by this Transporter class"""
        return bool(re.search(r'^http://', source)) or \
               bool(re.search(r'^ftp://', source)) 

    canHandle = staticmethod(canHandle)  # should work as of python 2.2

    def cacheToFile(self, filename, noaction=False):
        """cache the source to a local file
        @param filename      the name of the file to cache to
        @param noaction      if True, simulate the result (default: False)
        """
        if filename is None:
            raise RuntimeError("filename is None")

        if noaction:
            if self.verbose > 0:
                system("touch " + filename)
                print >> self.log, "Simulated web retrieval from", self.loc
        else:
            url = None
            out = None
            try:
                try:                               # for python 2.4 compat
                    url = urllib2.urlopen(self.loc)
                    out = open(filename, 'w')
                    out.write(url.read())
                except urllib2.HTTPError:
                    raise RemoteFileNotFound("Failed to open URL %s" % self.loc)
                except urllib2.URLError:
                    raise ServerNotResponding("Failed to contact URL %s" % self.loc)
                except KeyboardInterrupt:
                    raise EupsException("^C")
            finally: 
                if url is not None: url.close()
                if out is not None: out.close()

    def listDir(self, noaction=False):
        """interpret the source as a directory and return a list of files
        it contains
        @param noaction      if True, simulate the result (default: False)
        """
        url = None
        if noaction:
            return []

        import HTMLParser, urlparse
        class LinksParser(HTMLParser.HTMLParser):
            """Based on code in Martelli's "Python in a Nutshell" """
            def __init__(self):

                HTMLParser.HTMLParser.__init__(self)
                self.nrow = -1
                # self.seen = set()
                self.files = [] # files listed in table
                self.is_attribute = False # next data is value of <attribute>
                self.is_apache = False # are we reading data from apache?

            def handle_starttag(self, tag, attributes):
                if tag == "pre":  # now in file listing portion (Apache)
                    self.nrow = 0

                if tag == "tr": # count rows in table
                    if self.nrow < 0:  self.nrow = 0
                    self.nrow += 1

                if tag == "img" and self.nrow >= 0:
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
        try:
          try:                               # for python 2.4 compat
            url = urllib2.urlopen(self.loc)
            for line in url:
                p.feed(line)

            url.close()
            if not p.is_apache and self.verbose >= 0:
                print >> self.log, \
                    "Warning: URL does not look like a directory listing from an Apache web server"

            return p.files

          except urllib2.HTTPError:
            raise RemoteFileNotFound("Failed to open URL %s" % self.loc)
          except urllib2.URLError:
            raise ServerNotResponding("Failed to contact URL %s" % self.loc)
          except KeyboardInterrupt:
            raise EupsException("^C")
        finally: 
            if url is not None: url.close()

        p = LinksParser()
        for line in open(url, "r").readlines():
            p.feed(line)

        return p.files
        
        

class SshTransporter(Transporter):

    def __init__(self, source, verbosity=0, log=sys.stderr):
        Transporter.__init__(self, source, verbosity, log);
        self.remfile = re.sub(r'^scp:', '', self.loc)

    # @staticmethod   # requires python 2.4
    def canHandle(source):
        """return True if this source location is recognized as one that 
        can be handled by this Transporter class"""
        return bool(re.search(r'^scp:', source))

    canHandle = staticmethod(canHandle)  # should work as of python 2.2

    def cacheToFile(self, filename, noaction=False):
        """cache the source to a local file
        @param filename      the name of the file to cache to
        @param noaction      if True, simulate the result (default: False)
        """
        if re.search(r'[;,&\|"\']', self.remfile):
            raise OSError("remote file has dangerous location name: " + self.loc)

        try:
            system("scp -q %s %s 2>/dev/null" % (self.remfile, filename), 
                   noaction, self.verbose)
        except IOError, e:
            if e.errno == 2:
                raise RemoteFileNotFound("%s: file not found" % self.loc)
            else:
                raise TransporterError("Failed to copy %s: %s" % 
                                       (self.loc, str(e)))
        except OSError, e:
            raise TransporterError("Failed to retrieve %s" % self.loc)

        if noaction:
            system("touch %s" % filename)

        if self.verbose > 0:
            if noaction:
                print >> self.log, "Simulated scp from", self.remfile
            else:
                print >> self.log, "scp from", self.remfile

    def listDir(self, noaction=False):
        """interpret the source as a directory and return a list of files
        it contains
        @param noaction      if True, simulate the result (default: False)
        """
        if re.search(r'[;,&\|"\']', self.remfile):
            raise OSError("remote file has dangerous location name: " + self.loc)

        (remmach, file) = self.remfile.split(':', 1)
        cmd = """ssh %s python -c "'import os; print filter(lambda x: not x.startswith("'"."'"), filter(lambda f: os.path.isfile(os.path.join("'"%s"'",f)), os.listdir("'"%s"'")))'" """ % (remmach, file, file)

        if self.verbose > 0:
            if noaction:
                print >> self.log, "simulated ssh listing of", self.loc
            print >> self.log, cmd

        if noaction:
            return []
        else:
            pd = None
            try: 
                pd = os.popen(cmd)
                pylist = pd.readline().strip()
            finally:
                stat = pd.close()
            if stat is not None:
                stat = stat >> 8
                if stat > 0:
                  raise OSError("ssh command failed with exit status %d" % stat)

            exec "out=" + pylist
            return out



class LocalTransporter(Transporter):

    def __init__(self, source, verbosity=0, log=sys.stderr):
        Transporter.__init__(self, source, verbosity, log);

    # @staticmethod   # requires python 2.4
    def canHandle(source):
        """return True if this source location is recognized as one that 
        can be handled by this Transporter class"""
        return os.path.isabs(source) or os.path.exists(source) or \
               not re.match(r'^\w\w+:', source) 

    canHandle = staticmethod(canHandle)  # should work as of python 2.2

    def cacheToFile(self, filename, noaction=False):
        """cache the source to a local file
        @param filename      the name of the file to cache to
        @param noaction      if True, simulate the result (default: False)
        """
        if noaction:
            system("touch %s" % filename)
            if self.verbose > 0:
                print >> self.log, "Simulated cp from", self.loc
        else:
            if not os.path.exists(self.loc):
                raise RemoteFileNotFound("%s: file not found" % self.loc)

            try:
                copyfile(self.loc, filename)
                if self.verbose > 0:
                    print >> self.log, "cp from", self.loc
            except IOError, e:
                if e.errno == 2:
                    dir = os.path.dirname(filename)
                    if dir and not os.path.exists(dir):
                        raise RemoteFileNotFound("%s: destination directory not found" % dir)
                raise TransporterError("Failed to copy %s: %s" % 
                                       (self.loc, str(e)))
            except OSError, e:
                raise TransporterError("Failed to retrieve %s: %s" % 
                                       (self.loc, str(e)))

    def listDir(self, noaction=False):
        """interpret the source as a directory and return a list of files
        it contains
        @param noaction      if True, simulate the result (default: False)
        """
        if noaction:
            if self.verbose > 0:
                print >> self.log, "simulated listing of", self.loc
            return []
        else:
            if os.path.isdir(self.loc):
                return filter(lambda f: os.path.isfile(os.path.join(self.loc,f)), 
                              os.listdir(self.loc))
            else:
                if self.verbose > 0:
                    print >> self.log, "%s does not exist" % self.loc
                return []


class TransporterFactory(object):

    def __init__(self):
        self.classes = []

    def register(self, trxclass):
        """register a Transporter class
        @param trxclass    the class object that implements the Transporter 
                               interface
        """
        self.classes.append(trxclass)

    def createTransporter(self, source, verbosity=0, log=sys.stderr):
        """create a Transporter instance for a given source.  
        If the source is not recognized, an exception is raised.
        @param source        the location of the desired file
        @param verbosity     if > 0, print status messages; the higher the 
                               number, the more messages that are printed
                               (default=0).
        @param log           the destination for status messages (default:
                               sys.stderr)
        """
        use = self.classes[:]
        use.reverse()
        for cls in use:
            if cls.canHandle(source):
                return cls(source, verbosity, log)

        raise TransporterError("Transport for file not recognized: " + source)

defaultTransporterFactory = TransporterFactory();
defaultTransporterFactory.register(LocalTransporter)
defaultTransporterFactory.register(SshTransporter)
defaultTransporterFactory.register(WebTransporter)

def defaultMakeTransporter(source, verbosity, log):
    """create a Transporter instance for a given source.  
    If the source is not recognized, an exception is raised.
    @param source        the location of the desired file
    @param verbosity     if > 0, print status messages; the higher the 
                           number, the more messages that are printed
                           (default=0).
    @param log           the destination for status messages (default:
                           sys.stderr)
    """
    return defaultTransporterFactory.createTransporter(source, verbosity, log);

makeTransporter = defaultMakeTransporter


class TaggedProductList(object):
    """
    a listing of all versions of products that has been assigned a particular
    tag.  
    """

    def __init__(self, tag, defFlavor="generic", verbosity=0, log=sys.stderr):
        """create an empty collection of products with a given name
        @param tag         the logical name for this collection of product
        @param defFlavor   the flavor to assume when a product flavor is 
                              not specified (default: "generic")
        @param verbosity     if > 0, print status messages; the higher the 
                               number, the more messages that are printed
                               (default=0).
        @param log           the destination for status messages (default:
                               sys.stderr)
        """
        self.tag = tag
        self.flavor = defFlavor
        self.products = []
        self.info = {}
        self.verbose = verbosity
        self.log = log
        self.fmtversion = "1.0"

    def addProduct(self, product, version, flavor=None, info=None):
        """add a product to this tagged set of products"""
        if flavor is None:
            flavor = self.flavor

        prodinfo = [flavor, version]
        if info is not None:
            prodinfo.extend(info)

        self.info[product] = prodinfo
        if product not in self.products:
            self.products.append(product)

    def mergeProductList(self, products):
        """add/update the project information from a give list into this one
        @param products   a TaggedProductList instance whose content should 
                            be merged.
        """
        for p in products.getProducts():
            addProduct(p[0], p[2], p[1], p[3:])

    def read(self, filename):
        """read the products from a given file and add it to our list.  
        Any previously registered products may get updated."""
        fd = open(filename, "r")

        line = fd.readline()
        mat = re.search(r"^EUPS distribution %s version list. Version (\S+)\s*$" % self.tag, line)
        if not mat:
            raise RuntimeError("First line of %s version file %s is corrupted:\n\t%s" % 
                               (self.tag, filename, line))
        version = mat.groups()[0]
        if version != self.fmtversion:
           print >> self.log, \
              "WARNING. Saw version %s; expected %s" % (version, self.fmtversion)

        commre = re.compile(r"^\s*#")
        wordsre = re.compile(r"\S+")
        try:
            for line in fd:
                line = commre.split(line)[0].strip()
                if len(line) == 0:
                    continue

                try:
                    info = wordsre.findall(line)
                except:
                    raise RuntimeError("Failed to parse line:" + line)

                self.addProduct(info[0], info[2], info[1], info[3:])
        finally:
            fd.close()

    def write(self, filename, flavor=None, noaction=False):
        """write the collection of products out to a file
        @param filename    the filename to write manifest to
        @param flavor      if not None, set the platform flavor to this 
                              value
        """
        ofd = None
        if not noaction:
            ofd = open(filename, "w")

        if self.verbose > 0:
            print >> self.log, "Writing %s product list to %s" % \
                (self.tag, filename)

        if not noaction:
            print >> ofd, """\
EUPS distribution %s version list. Version %s
#product             flavor     version
#--------------------------------------\
""" % (self.tag, self.fmtversion)

        try:
            for product in sorted(self.products):
                info = self.info[product]
                flav = info[0]
                if flavor is not None:
                    flav = flavor
                if not noaction:
                    ofd.write("%-20s %-10s %s" % (product, flav, info[1]))

                if len(info) > 2:
                    for i in info[2:]:
                        if not noaction:
                            ofd.write("  %s" % i)
                if not noaction:
                    print >> ofd

        finally:
            if ofd is not None:
                ofd.close()

    def getProductInfo(self, product):
        """return the known information about the product as a list.
        The first item in the list will be the flavor and the second will be
        the version.  If the product is not recognized, a two-element list 
        will be return with both values set to None.
        """
        if self.info.has_key(product):
            return self.info[product]
        else:
            return [None, None]

    def getProductVersion(self, product):
        """return the version associated with the product or None if not known"""
        return self.getProductInfo(product)[1]

    def deleteProduct(self, product):
        """remove the given product from the list"""
        while product in self.products:
            del self.products[self.products.index(product)]
        if self.info.has_key(product):
            del self.info[product]

    def getProducts(self, sort=False):
        """return the product info for all known products as a list of lists"""
        products = self.products
        if sort:
            products.sort()

        out = []
        for p in products:
            info = [p]
            info.extend(self.getProductInfo(p))
            out.append(info)

        return out

    # @staticmethod   # requires python 2.4
    def fromFile(filename, tag="current", verbosity=0, log=sys.stderr):
        """create a TaggedProductList from the contents of a product list file
        @param filename   the file to read
        @param tag        the tag name to associate with this list 
                            (default: 'current')
        """
        out = TaggedProductList(tag, verbosity=verbosity, log=log)
        out.read(filename)
        return out

    fromFile = staticmethod(fromFile)  # should work as of python 2.2

class Dependency(object):
    """a container for information about a product required by another product.
    Users should use the attribute data directly.
    """

    def __init__(self, product, version, flavor, tablefile, instDir, distId,
                 isOptional=False, shouldRecurse=False, extra=None):
        self.product = product
        if not isinstance(version, str):
            if isinstance(version, type):
                version = version()
            else:
                version = version.__str__()
        self.version = version
        self.flavor = flavor
        self.tablefile = tablefile
        self.instDir = instDir
        if distId == "None":
            distId == None
        self.distId = distId
        self.isOpt = isOptional
        self.shouldRecurse = shouldRecurse
        self.extra = extra
        if self.extra is None:  self.extra = []

    def copy(self):
        return Dependency(self.product, self.version, self.flavor, 
                          self.tablefile, self.instDir, self.distId, 
                          self.extra[:])

    def __repr__(self):
        out = [self.product, self.version, self.flavor, 
               self.tablefile, self.instDir, self.distId]
        out.extend(self.extra)
        return repr(out)

class Manifest(object):
    """a list of product dependencies that must be installed in order to 
    install a particular product."""

    def __init__(self, product=None, version=None, eupsenv=None, 
                 verbosity=0, log=sys.stderr):
        self.products = []
        self.verbose = verbosity
        self.log = log
        self.fmtversion = "1.0"
        self.eups = eupsenv
        if self.eups is None:
            self.eups = eups.Eups()

        self.product = product
        self.version = version
        self.shouldRecurse = False

    def __str__(self):
        return "Manifest: %s %s" % (self.product, self.version)

    def getDependency(self, product, version=None, flavor=None, which=-1):
        """Return the last product dependency in this manifest that matches
        the given product info.  Typically only one version of a product will
        appear in a manifest, so usually only a product name is sufficient 
        to select a specific product dependency.  However, nothing disallows 
        the product from being listed multiple times, so the other inputs 
        make it possible to disambiguate the matches.
        @param product     the name of the desired product
        @param version     the version of the desired product
        @param flavor      the preferred flavor of the desired product
        @param which       if provided, return the which-th occurance of the 
                              matching products.  Default is the last matching
                              product.
        """
        out = filter(lambda x: x.product == product, self.products)
        if version is not None:
            out = filter(lambda x: x.version == version, out)
        if flavor is not None:
            out = filter(lambda x: x.flavor == flavor, out)
        if len(out) == 0 or which >= len(out) or which < -len(out):
            return None
        return out[which]

    def addDependency(self, product, version, flavor, tablefile,
                      instDir, distId, isOptional=False, shouldRecurse=False, 
                      extra=None):
        self.addDepInst(Dependency(product, version, flavor, tablefile, instDir, 
                                   distId, isOptional, shouldRecurse, extra))

    def addDepInst(self, dep):
        """add a dependency in the form of a dependency object"""
        if not isinstance(dep, Dependency):
            raise TypeError("not a Dependency instance: " + str(dep))

        self.products.append(dep)

    def getProducts(self):
        return self.products

    def reverse(self):
        """reverse the order of the dependency list.  It is common to load
        product dependencies in the order opposite from the order one needs
        to install them"""
        self.products.reverse()

    def roll(self, n=1):
        """Roll the list of products by n (n=1: [a, b, c, d] -> [b, c, d, a]"""
        if len(self.products) == 0:
            return

        if n < 0:
            n = -n
            for i in range(n):
                self.products.insert(0, self.products.pop())
        else:
            for i in range(n):
                self.products.append(self.products.pop(0))

    def read(self, file, setproduct=True, shouldRecurse=None):
        """load the dependencies listed in a file"""

        if shouldRecurse is None:
            shouldRecurse = False

        fd = open(file)
    
        line = fd.readline()
        mat = re.search(r"^EUPS distribution manifest for (\S+) \((\S+)\). Version (\S+)\s*$", line)
        if not mat:
            raise RuntimeError, ("First line of manifest file %s is corrupted:\n\t%s" % (file, line))
        manifest_product, manifest_product_version, version = mat.groups()

        version = mat.groups()[2]
        if version != self.fmtversion and self.verbose >= 0:
            print >> self.log, "WARNING. Saw version %s; expected %s" % \
                (version, self.fmtversion)

        if setproduct or self.product is None:
            self.product = manifest_product
        if setproduct or self.version is None:
            self.version = manifest_product_version

        FALSE = "FALSE"
        TRUE = "TRUE"
        REQ = "REQUIRED"
        OPT = "OPTIONAL"
        for line in fd:
            line = line.split("\n")[0]
            if re.search(r"^\s*(#.*)?$", line):
                continue

            try:
                info = re.findall(r"\S+", line)

                # make sure we have at least 5 elements
                info[4]

                # set a default for the distrib ID
                if len(info) < 6:
                    info.append(None)
                elif info[5] == "search":
                    info[5] = None

                # set a whether this is optional or required
                if len(info) < 7:
                    info.append(False)
                elif OPT.startswith(info[6]):
                    info[6] = True
                else:
                    info[6] = False

                if len(info) < 8:
                    info.append(shouldRecurse)
                elif TRUE.startswith(info[7]):
                    info[7] = True
                elif FALSE.startswith(info[7]):
                    info[7] = False
                else:
                    info[7] = shouldRecurse

                self.addDependency(info[0], info[2], info[1], info[3], 
                                   info[4], info[5], info[6], info[7], info[8:])
            except Exception, e:
                raise RuntimeError("Failed to parse line: (%s): %s" % 
                                   (str(e), line))


    def write(self, filename, noOptional=True, flavor=None, noaction=False):
        """write out the dependencies to a file
        @param filename    the filename to write manifest to
        @param flavor      if not None, set the platform flavor to this 
                              value
        """
        product = self.product
        if product is None:
            product = "UNKNOWN_PRODUCT"
        version = self.version
        if version is None:
            version = "generic"

        ofd = None
        if not noaction:
            ofd = open(filename, 'w')
        try:
            if not noaction:
                print >> ofd, """\
EUPS distribution manifest for %s (%s). Version %s
#
# Creator:      %s
# Time:         %s
# Eups version: %s
#
# pkg           flavor       version    tablefile                 installation_directory         installID
#---------------------------------------------------------------------------------------------------------""" % \
                    (product, version, self.fmtversion, self.eups.who,
                     utils.ctimeTZ(), utils.version())

            for p in self.products:
                if p.isOpt and noOptional:
                    continue

                p = p.copy()
                if not flavor:
                    p.flavor = flavor
                if not p.flavor:
                    p.flavor = self.eups.flavor()
                if not p.instDir:
                    p.instDir = "none"
                if not p.tablefile:
                    p.tablefile = "none"

                if not noaction:
                    print >> ofd, "%-15s %-12s %-10s %-25s %-30s %s" % \
                        (p.product, p.flavor, p.version, p.tablefile, 
                         p.instDir, p.distId)
        finally:
            if not noaction:
                ofd.close()

    # @staticmethod   # requires python 2.4
    def fromFile(filename, eupsenv=None, shouldRecurse=None, 
                 verbosity=0, log=sys.stderr):
        """
        create a Manifest instance from the given manifest file
        @param filename       the file to read the manifest from
        @param eupsenv        the eups environment to assume
        @param shouldRecurse  if True, it is recommended by that the installer
                                 recursively look for the dependencies for 
                                 each of the products in the manifest.  If
                                 False, the manifest should be assumed to be
                                 complete; no recursive searches are necessary.
                                 If None (default), the default value will be
                                 retained (usually False).
        """
        out = Manifest(eupsenv=eupsenv, verbosity=verbosity)
        out.read(filename, setproduct=True, shouldRecurse=shouldRecurse)
        out.remapEntries()
        return out

    fromFile = staticmethod(fromFile)  # should work as of python 2.2

    def remapEntries(self):
        """Allow the user to modify entries in the Manifest

The mapping is defined by the file userDataDir/manifest.remap, which consists of up to three columns:
productName[:version-in-manifest]    [[outProductName:]desired-version]    [flavor]

Comments (starting with #) are skipped
If version-in-manifest is "Any" the desired-version is used for all products
If oproductName is present, productName is replaced by outProductName
If desired-version is "None" or omitted, the product is deleted from the Manifest.
If flavor is supplied, the mapping is only applied for that flavor

E.g.
   doxygen:1.5.9                1.6.3
   python:Any                   2.6.2
   tcltk                        None
   tcltk:Any                    dummy:1.0               DarwinX86

Means that instead of installing doxygen 1.5.9 version 1.6.3 should be used; that any version of python should
be replaced by version 2.6.2; that on any platform other than DarwinX86 tcltk should be ignored; and that on
DarwinX86 machines any version of tcltk should be replace by product dummy, version 1.0
"""

        mapping = {}
        for dirname in hooks.customisationDirs:
            self._readRemapFile(dirname, mapping)
        #
        # Retrieve the correct flavor
        #
        mapping2 = {}
        if mapping.has_key("generic"):
            mapping2 = mapping["generic"]

        if mapping.has_key(eups.flavor()):
            for p, iMap in mapping[eups.flavor()].items():
                for iv, val in iMap.items():
                    mapping2[p][iv] = val

        mapping = mapping2
        #
        # Remap the incoming manifest
        #
        products = []
        for p in self.products:
            if mapping.has_key(p.product):
                if not len(mapping[p.product]):
                    if self.verbose > 0:
                        print >> self.log, "Deleting [%s, %s] from manifest" % (p.product, p.version)

                    p.version = None
                else:
                    for versName in (p.version, "any"):
                        if mapping[p.product].has_key(versName):
                            productName, versionName = mapping[p.product][versName]

                            if (productName, versionName) == (p.product, p.version): # identity map
                                break

                            if self.verbose > 0:
                                print >> self.log, "Mapping manifest's [%s, %s] to [%s, %s]" % \
                                      (p.product, versName, productName, versionName)

                            p = Dependency(productName, versionName, None, None, None, None)
                            break

            if p.version:
                products.append(p)

        self.products = products

    def _readRemapFile(self, dirname, mapping={}, filename="manifest.remap"):
        """Read a product mapping from dirname/filename"""
        
        if not dirname:
            return mapping
        
        mapFile = os.path.join(dirname, filename)
        if not os.path.exists(mapFile):
            return mapping
        
        lineNo = 0
        for line in open(mapFile, "r").readlines():
            lineNo += 1

            line = line.strip()
            line = re.sub(r"\s*#.*$", "", line) # strip comments

            if not line:
                continue

            vals = line.split()

            product, inversion, outproduct, outversion, flavor = 5*[None]
            if len(vals) > 0:
                mat = re.search(r"^([^:]+)(?::(.*))?", vals[0])
                product, inversion = mat.groups()
                                
                if inversion in (None, "any", "Any"):
                    inversion = "any"

            if len(vals) > 1:
                mat = re.search(r"^([^:]+)(?::(.*))?", vals[1])
                outproduct, outversion = mat.groups()
                if not outversion:
                    outversion = outproduct
                    outproduct = product

                if outversion in ("any", "none", "None"):
                    outversion = None

            if len(vals) > 2:
                flavor = vals[2]
                
            if len(vals) > 3:
                print >> sys.stderr, "Expected 3 fields in \"%s\" (%s:%d)" % (line, mapFile, lineNo)
                
            if not flavor:
                flavor = "generic"

            if not mapping.has_key(flavor):
                mapping[flavor] = {}

            if not mapping[flavor].has_key(product):
                mapping[flavor][product] = {}

            if outversion:
                mapping[flavor][product][inversion] = (outproduct, outversion)
            else:
                if mapping[flavor][product].has_key(inversion):
                    del mapping[flavor][product][inversion]

        return mapping


class ServerConf(object):
    """a factory class for creating DistribServer classes based on the 
    servers configuration data
    """

    def __init__(self, packageBase, save=False, configFile=None, 
                 override=None, eupsenv=None, verbosity=0, log=sys.stderr):
        """
        create the factory based on the server's configuration.  
        @param packageBase    the base URL of the server
        @param save           if True, the configuration will be cached on 
                                local disk.
        @param configFile     the server configuration file for the server
        @param override       a dictionary of configuration parameters that
                                should override those in the configuration 
                                file
        @param eupsenv        an Eups instance representing the Eups environment
        @param verbosity      an integer measure the number of messages 
                                that should be printed.
        @param log            a file descriptor where messages are written.
        """
        self.base = packageBase
        self.data = {}
        self.verbose = verbosity
        self.log = log

        if eupsenv is None:
            eupsenv = eups.Eups()
        self.eups = eupsenv

        if configFile and not os.path.exists(configFile):
            raise RuntimeError("config file not found: " + configFile)

        # cached is the location of the cached configuration file under ups_db
        if not self.base:
            if self.verbose > 0:
                print >> self.log, "Warning: no pkgroot is available"
            cached = None
        else:
            cached = self.cachedConfigFile(self.base);
            if not cached:
                save = False

            if save:
                # make sure the cache directory exists
                pdir = os.path.dirname(cached)
                if not os.path.exists(pdir):
                    os.makedirs(pdir)
                if self.verbose > 0 and self.base != "/dev/null" and not os.path.exists(cached):
                    print >> self.log, "Caching configuration for", self.base
                    if self.verbose > 1:
                        print >> self.log, "...as", cached

        if configFile is None:
            # we were not provided with a config file, so we'll try to get it from 
            # the server and (maybe) cache it.
            configFile = cached
        elif save:
            # we were provided a file, and we want to cache it in upd_db
            copyfile(configFile, cached)

        try:
            if not configFile:
                msg = "Unable to read configuration for server %s" % packageBase
                if self.eups.force:
                    print >> self.log, msg + "; continuing"
                    self.data = {}
                else:
                    raise RuntimeError(msg)
            else:
                if not os.path.exists(configFile):
                    # if we're going to the server but not saving it, we'll use 
                    # a temp file (which will happen if configFile is None).
                    if not save:  configFile = None

                    if self.base != "/dev/null" and self.verbose > 0:
                        print >> self.log, \
                            "Pulling configuration for %s from server" % self.base

                    ds = DistribServer(packageBase, 
                                       verbosity=self.verbose, log=self.log);
                    try:
                        configFile = ds.getConfigFile(configFile)
                    except RuntimeError:    # may not exist if this is a new installation
                        pass

                if not os.path.exists(configFile):
                    raise RuntimeError("Failed to find or cache config file: " +
                                       configFile)

                self.data = self.readConfFile(configFile);

        except RemoteFileNotFound, e:
            if self.base != "/dev/null" and self.verbose > 0:
                print >> self.log, \
                    "Warning: No configuration available from server;", \
                    'assuming "vanilla" server'
        except TransporterError:
            # including failed to recognize transport type
            raise
                
        if override is not None:
            for key in override.keys():
                self.data[key] = override[key]

    def cachedConfigFile(self, packageBase):
        """return the name of the file that contains the configuration data
        for the server accessed via the given package base URL.

        In this implementation, the configuration is assumed to be stored 
        under a directory called "_servers_" below the ups_db directory with
        a name that matches the packageBase.  
        """
        defaultConfigFile = None

        configFileRelPath = packageBase
        if os.path.isabs(configFileRelPath):
            configFileRelPath = configFileRelPath[1:]

        for stack in self.eups.path:
            configFile = os.path.join(self.eups.getUpsDB(stack), "_servers_",
                                      configFileRelPath, serverConfigFilename)

            if not defaultConfigFile:
                configDir = os.path.dirname(configFile)
                try:
                    if not os.path.exists(configDir):
                        os.makedirs(configDir)
                    if os.access(configDir, os.W_OK):
                        defaultConfigFile = configFile # we can create it if we need to
                except OSError:
                    continue

            if os.path.exists(configFile):
                return configFile

        return defaultConfigFile

    def readConfFile(self, file):
        """"read the configuration file and return the data as a dictionary"""
        paramre = re.compile("\s*=\s*")
        commre = re.compile("\s*#");
        out = {}

        try:
            fd = open(file);
        except IOError, e:
            raise RuntimeError("%s: %s" % (file, str(e)))
        if self.verbose > 1:
            print >> self.log, "Reading configuration data from", file

        try:
          try:                               # for python 2.4 compat
            lineno = 0
            for line in fd:
                lineno += 1
                line = commre.split(line)[0].strip()
                if len(line) == 0:  continue

                (name, value) = paramre.split(line, 1);
                if not out.has_key(name):
                    out[name] = []
                out[name].append(value.strip())

          except ValueError, e:
            raise RuntimeError("format error in config file (%s:%d): %s" %
                               (file, lineno, line))
        finally:
            fd.close()

        # check syntax of *CLASS
        for k in ["DISTRIB_CLASS", "DISTRIB_SERVER_CLASS",]:
            if out.has_key(k):
                if len(out[k][-1].split(".")) < 2:
                    print >> self.log, "Invalid config parameter %s: %s (expected module.class)" % (k, out[k][-1])

        return out;

    def writeConfFile(self, file):
        """write out the configuration paramters to a file"""
        fd = open(file, 'w')
        if self.verbose > 1:
            print >> self.log, "Writing configuration to", file

        try:
            for key in self.data.keys():
                for value in self.data[key]:
                    print >> fd, key, "=", self.data[key]
        finally:
            fd.close()

    # @staticmethod   # requires python 2.4
    def clearConfigCache(eups, servers=None, verbosity=0, log=sys.stderr):
        """clear the cached configuration data for each of the server URLs
        provided, or all of them if none are provided
        """
        # FIXME: this is not clearing caches in the user's .eups dir.

        for stack in eups.path:
            cache = os.path.join(eups.getUpsDB(stack), "_servers_")
            if not os.path.exists(cache):
                continue
            if not os.access(stack, os.W_OK) or not os.access(cache, os.W_OK):
                if verbosity > 0:
                    print >> log, "Insufficient permissions to clear", \
                        "cache in %s; skipping" % stack

            if servers is None:
                if verbosity > 0:
                    print >> log, "Clearing all server config data in", \
                        stack
                try:
                    system("rm -rf " + cache, 
                           verbosity=verbosity-1, log=log)
                except OSError, e:
                    if verbosity >= 0:
                        print >> log, "Warning: failed to clear cache in", \
                            "%s: %s" % (stack, str(e))
                    pass

            else:
                for pkgroot in servers:
                    if os.path.isabs(pkgroot):
                        pkgroot = pkgroot[1:]
                    file = os.path.join(cache, pkgroot, serverConfigFilename)
                    if os.path.exists(file):
                        if verbosity > 0:
                            print >> log, "Clearing all server config", \
                                "data for", pkgroot, "in", stack
                        try:
                            os.unlink(file)
                        except OSError, e:
                            if verbosity >= 0:
                                print >> log, \
                                    "Warning: failed to clear cache for", \
                                    pkgroot, "in %s: %s" % (stack, str(e))
                            pass

    clearConfigCache = staticmethod(clearConfigCache)


    def createDistribServer(self, verbosity=0, log=sys.stderr):
        """
        create a DistribServer instance based on this configuration
        @param verbosity      if > 0, print status messages; the higher the 
                                number, the more messages that are printed
                                (default=0).
        @param log            the destination for status messages (default:
                                sys.stderr)
        """
        serverClass = None
        if self.data.has_key('DISTRIB_SERVER_CLASS'):
            serverClass = self.data['DISTRIB_SERVER_CLASS']
        if isinstance(serverClass, list):
            serverClass = serverClass[-1]

        if serverClass is None:
            return ConfigurableDistribServer(self.base, self.data, verbosity,log)
        else:
            constructor = self.importServerClass(serverClass)
            return constructor(self.base, self.data, verbosity, log)

    def importServerClass(self, classname):
        """import and return the constructor for the given class name.
        @param classname    the full module classname to import
        """
        return importClass(classname)

    # @staticmethod   # requires python 2.4
    def makeServer(packageBase, save=True, eupsenv=None, override=None,
                   verbosity=0, log=sys.stderr):
        """create a DistribServer class for a give package base
        @param packageBase    the base URL for the server
        @param save           if True (default), save the server configuration
                                 into the local EUPS database
        @param eups           the eups control instance
        @param override       a dictionary of configuration parameters that 
                                 should override the parameters that are 
                                 received from the server
        @param verbosity      if > 0, print status messages; the higher the 
                                number, the more messages that are printed
                                (default=0).
        @param log            the destination for status messages (default:
                                sys.stderr)
        """
        conf = ServerConf(packageBase, save, eupsenv=eupsenv, override=override,
                          verbosity=verbosity, log=log)
        return conf.createDistribServer(verbosity=verbosity, log=log)

    makeServer = staticmethod(makeServer)  # should work as of python 2.2

def makeTempFile(prefix):
    (fd, filename) = tempfile.mkstemp("", prefix, utils.createTempDir("distrib"))
    os.close(fd);
    atexit.register(os.unlink, filename)
    return filename

def importClass(classname):
    """import and return the constructor for the given class name.
    @param classname    the full module classname to import
    """
    parts = classname.split(".")
    modname = ".".join(parts[:-1])
    clsnm = parts[-1]

    mod = __import__(modname, globals(), locals(), [clsnm])
    return getattr(mod, clsnm)

def system(cmd, noaction=False, verbosity=0, log=sys.stderr):
    """Run BASH shell commands in a EUPS-aware environment.  This will make
    sure the EUPS environment is properly setup before running the commands.
    The currently environment is passed in except:
      o  the SHELL environment is set to /bin/bash
      o  the BASH_ENV environment is set to setup EUPS
      o  the setting up of EUPS will tweak EUPS_PATH & PYTHONPATH (in good ways).

    @param cmd           the shell commands to run stored in a single string.
    @param noaction      if True, just print the command
    @param verbosity     the amount of status messages to print.  If > 0,
                             the requested command will be printed.
    @param log           a file object to send the messages to.
    @exception OSError   if a non-zero exit code is returned by the shell
    """
    if not os.environ.has_key('EUPS_DIR'):
        raise RuntimeError("EUPS_DIR is not set; is EUPS setup?")
    if noaction or verbosity > 0:
        print >> log, cmd
    if not noaction:

        # we don't use system() `cause we need to update the environment
        # to ensure that EUPS works properly.
        environ = os.environ.copy()
        environ['SHELL'] = BASH
        environ['BASH_ENV'] = os.path.join(environ['EUPS_DIR'],"bin","setups.sh")

        if environ.has_key("EUPS_PATH"): # keep current path
            cmd = ("export EUPS_PATH=%s\n" % (environ["EUPS_PATH"])) + cmd

        errno = os.spawnle(os.P_WAIT, BASH, BASH, "-c", cmd, environ)

        if errno != 0:
            raise OSError("\n\t".join(("Command:\n" + cmd).split("\n")) + ("\nexited with code %d" % (errno)))

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

def findInPath(file, path):
    """return the full path to a file with a given name in by searching 
    a list of directories given in a path.  The path returned will correspond 
    to the first directory found to contain the file.  None is returned if 
    the file is not found.
    @param file    a file name to find.  If this file is an absolute path,
                     it will be returned without change.  If it is a relative
                     path (or a simple basename), a file with this path will 
                     be looked for under each directory in path.
    @param path    the list of directories to search.  This can either be a 
                     python list of directory paths, or a string containing
                     a a colon (:) -separated list of directories (like the 
                     shell environment variable, PATH), a combination of the 
                     two.
    """
    if os.path.isabs(file):
        return file

    if not isinstance(path, list):
        path = [path]

    for dirs in path:
        dirs = map(lambda x: x.strip(), dirs.split(":"))
        for dir in dirs:
            filepath = os.path.join(dir, file)
            if os.path.exists(filepath):
                return os.path.abspath(filepath)

    return None

# make sure we can find bash
if not os.path.exists(BASH):
    if not os.environ.has_key('PATH'):
      raise RuntimeError("Can't find bash and PATH environement is not set!")
    BASH = findInPath("bash", os.environ['PATH'])
    if not BASH:
      raise RuntimeError("Can't find bash in PATH environement!")

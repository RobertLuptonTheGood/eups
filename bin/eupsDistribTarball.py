#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import os
import re, sys
import pdb
import eups
import eupsDistrib

class Distrib(eupsDistrib.Distrib):
    """Handle distribution via tarballs"""

    def createPackage(self, productName, versionName, baseDir, productDir):
        """Create a tarball and return a distribution ID which happens to be its name"""

        tarball = "%s-%s.tar.gz" % (productName, versionName)

        if os.access("%s/%s" % (self.packageBase, tarball), os.R_OK) and not force:
            if self.Eups.verbose > 0:
                print >> sys.stderr, "Not recreating", tarball
            return tarball

        if self.Eups.verbose > 0:
            print >> sys.stderr, "Writing", tarball

        try:
            eupsDistrib.system("cd %s && tar -cf - %s | gzip > %s/%s" % \
                               (baseDir, productDir, self.packageBase, tarball),
                               self.Eups.noaction)
        except Exception, e:
            try:
                os.unlink("%s/%s" % (self.packageBase, tarball))
            except:
                pass
            raise OSError, "Failed to write %s/%s" % (self.packageBase, tarball)

        return tarball

    def installPackage(self, distID, productsRoot, *args):
        """Retrieve and unpack a tarball"""

        if not re.search(r"tar\.gz$", distID):
            raise RuntimeError, ("Expected a tarball name; saw \"%s\"" % distID)

        tarball = distID

        tfile = "%s/%s" % (self.packageBase, tarball)

        if self.transport != eupsDistrib.LOCAL and not self.Eups.noaction:
            (tfile, msg) = file_retrieve(tfile, self.transport)

        if not self.Eups.noaction and not os.access(tfile, os.R_OK):
            raise RuntimeError, ("Unable to read %s" % (tfile))

        if self.Eups.verbose > 0:
            print >> sys.stderr, "installing %s into %s" % (tarball, productsRoot)

        try:
            eupsDistrib.system("cd %s && tar -zxf %s" % (productsRoot, tfile), self.Eups.noaction)
        except Exception, e:
            raise RuntimeError, ("Failed to read %s: %s" % (tfile, e))

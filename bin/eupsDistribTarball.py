#!/usr/bin/env python
# -*- python -*-
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import os
import re, sys
import pdb
import neups as eups
import eupsDistrib

class Distrib(eupsDistrib.Distrib):
    """Handle distribution via tarballs"""

    def getDistID(self, productName, versionName, basedir, productDir):
        """Create a tarball and return its name"""

        tarball = "%s-%s.tar.gz" % (productName, versionName)

        if os.access("%s/%s" % (self.packageBase, tarball), os.R_OK) and not force:
            if self.Eups.verbose > 0:
                print >> sys.stderr, "Not recreating", tarball
            return tarball

        if self.Eups.verbose > 0:
            print >> sys.stderr, "Writing", tarball

        try:
            eups.system("cd %s && tar -cf - %s | gzip > %s/%s" % (basedir, productDir, self.packageBase, tarball),
                         Distrib.Eups.noaction)
        except Exception, param:
            os.unlink("%s/%s" % (self.packageBase, tarball))
            raise OSError, "Failed to write %s/%s" % (self.packageBase, tarball)

        return tarball

    def doInstall(self, distID, products_root, *args):
        """Retrieve and unpack a tarball"""

        tarball = distID

        tfile = "%s/%s" % (self.packageBase, tarball)

        if transport != LOCAL and not noaction:
            (tfile, msg) = file_retrieve(tfile, transport)

        if not noaction and not os.access(tfile, os.R_OK):
            raise IOError, ("Unable to read %s" % (tfile))

        if self.Eups.verbose > 0:
            print >> sys.stderr, "installing %s into %s" % (tarball, products_root)

        try:
            eups.system("cd %s && cat %s | gunzip -c | tar -xf -" % (products_root, tfile), Distrib.Eups.noaction)
        except:
            raise IOError, ("Failed to read %s" % (tfile))

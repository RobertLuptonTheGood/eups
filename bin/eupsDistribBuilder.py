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

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

class Distrib(eupsDistrib.Distrib):
    """Handle distribution via curl/cvs/svn and explicit build files"""

    def createPackage(self, productName, versionName, baseDir, productDir):
        """Create a package (which basically means locating a
        buildfile which contains information about its CVS/SVN root,
        Then write a small file to the manifest directory allowing us to
        bootstrap the build.  The build file is looked for in
        buildFilePath, a : separated set of directories ("" -> the installed
        product's ups directory).  Then return a distribution ID
        """

        builder = "%s-%s.build" % (productName, versionName)
        buildFile = self.find_file_on_path("%s.build" % productName, os.path.join(baseDir, productDir, "ups"))

        if not buildFile:
            print >> sys.stderr, \
                  "I can't find a build file %s.build anywhere on \"%s\"" % (productName, self.buildFilePath)
            if os.path.exists(os.path.join("ups", "%s.build" % productName)):
                print >> sys.stderr, \
                      "N.b. found %s.build in ./ups; consider adding ./ups to --build path" % (productName)
            if self.Eups.force:
                return None

            raise RuntimeError, "I'm giving up. Use --force if you want to proceed with a partial distribution"

        builderDir = os.path.join(self.packageBase, "builds")
        if not os.path.isdir(builderDir):
            try:
                os.mkdir(builderDir)
            except:
                raise RuntimeError, ("Failed to create %s" % (builderDir))

        full_builder = os.path.join(builderDir, builder)
        if os.access(full_builder, os.R_OK) and not self.Eups.force:
            if self.Eups.verbose > 0:
                print >> sys.stderr, "Not recreating", full_builder
            return "build:" + builder

        if self.Eups.verbose > 0:
            print >> sys.stderr, "Writing", full_builder

        try:
            if not self.Eups.noaction:
                if False:
                    copyfile(buildFile, full_builder)
                else:
                    try:
                        ifd = open(buildFile)
                    except IOError, e:
                        raise RuntimeError, ("Failed to open file \"%s\" for read" % buildFile)
                    try:
                        ofd = open(full_builder, "w")
                    except IOError, e:
                        raise RuntimeError, ("Failed to open file \"%s\" for write" % full_builder)

                    try:
                        eups.expandBuildFile(ofd, ifd, productName, versionName, self.Eups.verbose)
                    except RuntimeError, e:
                        raise RuntimeError, ("Failed to expand build file \"%s\": %s" % (full_builder, e))

                    del ifd; del ofd
        except IOError, param:
            try:
                os.unlink(full_builder)
            except OSError:
                pass                        # probably didn't exist
            raise RuntimeError ("Failed to write %s: %s" % (full_builder, param))

        return "build:" + builder

    def installPackage(self, distID, products_root, setups):
        """Setups is a list of setup commands needed to build this product"""

        try:
            builder = re.search(r"build:(.*)", distID).group(1)
        except AttributeError:
            raise RuntimeError, ("Expected distribution ID of form build:*; saw \"%s\"" % distID)

        tfile = self.find_file(builder)

        if False:
            if not self.Eups.noaction and not os.access(tfile, os.R_OK):
                raise RuntimeError, ("Unable to read %s" % (tfile))

        if not self.buildDir:
            self.buildDir = os.path.join(products_root, "EupsBuildDir")

        if not os.path.isdir(self.buildDir):
            if not self.Eups.noaction:
                try:
                    os.makedirs(self.buildDir)
                except OSError, e:
                    print >> sys.stderr, "Failed to create %s: %s" % (self.buildDir, e)

        if self.Eups.verbose > 0:
            print >> sys.stderr, "Building %s in %s" % (builder, self.buildDir)
        #
        # Does this build file look OK?  In particular, does it contain a valid
        # CVS/SVN location or curl/wget command?
        #
        (cvsroot, svnroot, url, other) = get_root_from_buildfile(tfile)
        if not (cvsroot or svnroot or url or other):
            if force:
                action = "continuing"
            else:
                action = "aborting"
            msg = "Warning: unable to find a {cvs,svn}root or wget/curl command in %s; %s" % (tfile, action)
            if force:
                print >> sys.stderr, msg
            else:
                raise RuntimeError, msg
        #
        # Prepare to actually do some work
        #
        cmd = ["cd %s" % (self.buildDir)]
        cmd += setups

        if self.Eups.verbose > 2:
            cmd += ["set -vx"]
        #
        # Rewrite build file to replace any setup commands by "setup -j" as
        # we're not necessarily declaring products current, so we're setting
        # things up explicitly and a straight setup in the build file file
        # undo our hard work
        #
        try:
            fd = open(tfile)
        except IOError, e:
            raise RuntimeError, ("Failed to open %s: %s" % (tfile, e))

        for line in fd:
            line = re.sub(r"\n$", "", line) # strip newline

            if re.search("^#!/bin/(ba|k)?sh", line):      # a #!/bin/sh line; not needed
                continue

            line =  re.sub(r"^(\s*)#(.*)",
                           r"\1:\2", line) # make comments executable statements that can be chained with &&

            line = re.sub(r"^\s*setup\s", "setup -j ", line)
            cmd += [line]

        del fd
        #
        # Did they ask to have group permissions honoured?
        #
        if self.obeyGroups:
            if self.Eups.verbose > 2:
                print "Giving group %s r/w access" % group

            cmd += ["chgrp -R %s %s*" % (group, os.path.splitext(builder)[0])]
            cmd += ["chmod -R g+rwX %s*" % (group, os.path.splitext(builder)[0])]

        #
        # Write modified (== as run) build file to self.buildDir
        #
        bfile = os.path.join(self.buildDir, builder)
        if eupsDistrib.issamefile(bfile, tfile):
            print >> sys.stderr, "%s and %s are the same; not adding setups to installed build file" % \
                  (bfile, tfile)
        else:
            try:
                bfd = open(bfile, "w")
                for line in cmd:
                    print >> bfd, line
                del bfd
            except Exception, e:
                os.unlink(bfile)
                raise RuntimeError, ("Failed to write %s" % bfile)

        if self.Eups.verbose:
            print "Issuing commands:"
            print "\t", str.join("\n\t", cmd)

        eupsDistrib.system(str.join("\n", cmd), self.Eups.noaction)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def get_root_from_buildfile(buildFile):
    """Given the name of a buildfile, return (cvsroot, svnroot, url);
    presumably only one will be valid"""

    cvsroot = None; svnroot = None; url = None
    other = None                  # this build file is Other, but valid

    fd = open(buildFile)

    for line in fd:
        if re.search(r"^\s*[:#].*\bBuild\s+File\b", line, re.IGNORECASE):
            other = True

        mat = re.search(r"^\s*export\s+(CVS|SVN)ROOT\s*=\s*(\S*)", line)
        if mat:
            type = mat.group(1); val = re.sub("\"", "", mat.group(2))

            if type == "CVS":
                cvsroot = val
            elif type == "SVN":
                svnroot = val
            else:
                if verbose:
                    print >> sys.stderr, "Unknown root type:", line,

            continue

        mat = re.search(r"^\s*(cvs|svn)\s+(co|checkout)\s+(\S)", line)
        if mat:
            type = mat.group(1); val = re.sub("\"", "", mat.group(3))
            
            if type == "cvs":
                cvsroot = val
            elif type == "svn":
                svnroot = val
            else:
                if verbose:
                    print >> sys.stderr, "Unknown src manager type:", line,

            continue

        mat = re.search(r"^\s*(wget|curl)\s+(--?\S+\s+)*\s*(\S*)", line)
        if mat:
            url = mat.group(3)

    return (cvsroot, svnroot, url, other)

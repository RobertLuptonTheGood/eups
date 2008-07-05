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
                        expandBuildFile(ofd, ifd, productName, versionName, self.Eups.verbose)
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
            print >> sys.stderr, "Executing %s in %s" % (builder, self.buildDir)
        #
        # Does this build file look OK?  In particular, does it contain a valid
        # CVS/SVN location or curl/wget command?
        #
        (cvsroot, svnroot, url, other) = get_root_from_buildfile(tfile)
        if not (cvsroot or svnroot or url or other):
            print >> sys.stderr, \
                  "Unable to find a {cvs,svn}root or wget/curl command in %s; continuing" % (tfile)
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

        lines = []                      # processed command lines from build file
        for line in fd:
            line = re.sub(r"\n$", "", line) # strip newline

            if re.search("^#!/bin/(ba|k)?sh", line):      # a #!/bin/sh line; not needed
                continue

            if re.search(r"#", line): # make comments executable statements that can be chained with &&
                line =  re.sub(r"^(\s*)#(.*)", r"\1: \2", line)
                line = re.sub(r"([^\\])([|<>'\"\\])", r"\1\\\2", line) # We need to quote quotes and \|<> in
                                       #: comments as : is an executable command

            line = re.sub(r"^\s*setup\s", "setup -j ", line)
            if not re.search(r"^\s*$", line): # don't confuse the test for an empty build file ("not lines")
                lines += [line]
        del fd

        if not lines:
            lines += [":"]              # we need at least one command as cmd may end &&
        cmd += lines
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
        if re.search(r"^\s*[:#].*\bBuild\s*File\b", line, re.IGNORECASE):
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

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Expand a build file
#
def expandBuildFile(ofd, ifd, productName, versionName, verbose=False, svnroot=None, cvsroot=None):
    """Expand a build file, reading from ifd and writing to ofd"""
    #
    # A couple of functions to set/guess the values that we'll be substituting
    # into the build file
    #
    # Guess the value of CVSROOT
    #
    def guess_cvsroot(cvsroot):
        if cvsroot:
            pass
        elif os.environ.has_key("CVSROOT"):
            cvsroot = os.environ["CVSROOT"]
        elif os.path.isdir("CVS"):
            try:
                rfd = open("CVS/Root")
                cvsroot = re.sub(r"\n$", "", rfd.readline())
                del rfd
            except IOError, e:
                print >> sys.stderr, "Tried to read \"CVS/Root\" but failed: %s" % e

        return cvsroot    
    #
    # Guess the value of SVNROOT
    #
    def guess_svnroot(svnroot):
        if svnroot:
            pass
        elif os.environ.has_key("SVNROOT"):
            svnroot = os.environ["SVNROOT"]
        elif os.path.isdir(".svn"):
            try:
                rfd = os.popen("svn info .svn")
                for line in rfd:
                    mat = re.search(r"^Repository Root: (\S+)", line)
                    if mat:
                        svnroot = mat.group(1)
                        break

                if not svnroot:         # Repository Root is absent in svn 1.1
                    rfd = os.popen("svn info .svn")
                    for line in rfd:
                        mat = re.search(r"^URL: ([^/]+//[^/]+)", line)
                        if mat:
                            svnroot = mat.group(1)
                            break

                del rfd
            except IOError, e:
                print >> sys.stderr, "Tried to read \".svn\" but failed: %s" % e

        return svnroot
    #
    # Here's the function to do the substitutions
    #
    subs = {}                               # dictionary of substitutions
    subs["CVSROOT"] = guess_cvsroot(cvsroot)
    subs["SVNROOT"] = guess_svnroot(svnroot)
    subs["PRODUCT"] = productName
    subs["VERSION"] = versionName

    def subVar(name):
        var = name.group(1).upper()
        if subs.has_key(var):
            if not subs[var]:
                raise RuntimeError, "I can't guess a %s for you -- please set $%s" % (var, var)
            return subs[var]

        return "XXX"
    #
    # Actually do the work
    #
    for line in ifd:
        # Attempt substitutions
        line = re.sub(r"@([^@]+)@", subVar, line)
        line = re.sub(r"/tags/svn", "/trunk -r ", line);

        print >> ofd, line,

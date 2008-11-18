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

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Expand a table file
#
def expandTableFile(Eups, ofd, ifd, productList, versionRegexp=None):
    """Expand a table file, reading from ifd and writing to ofd"""
    #
    # Here's the function to do the substitutions
    #
    subs = {}                               # dictionary of substitutions

    def subSetup(match):
        cmd = match.group(1)
        args = match.group(2).split()

        original = match.group(0)

        flags = []; words = []

        i = -1
        while True:
            i += 1
            if i == len(args):
                break
            
            a = args[i]

            if re.search(r"^-[fgHmMqrUz]", a):
                i += 1

                if i == len(args):
                    raise RuntimeError, ("Flag %s expected an argument" % a)

                flags += ["%s %s" % (a, args[i])]
            elif re.search(r"^-[cdejknoPsvtV0-3]", a):
                flags += [a]
            elif re.search(r"^-[BO]", a):
                print >> sys.stderr, "I don't know how to process %s" % a
            elif re.search(r"^-", a):
                print >> sys.stderr, "Unknown setup flag %s" % a
            else:                       # split [expr] into separate words for later convenience
                mat = re.search(r"^\[\s*(.*)\s*\]?$", a)
                if mat:
                    words += ["["]
                    a = mat.group(1)

                mat = re.search(r"^(.*)\s*\]$", a)
                if mat:
                    words += [mat.group(1), "]"]
                else:
                    words += [a]
        try:
            productName = words.pop(0)
        except IndexError:
            print >> sys.stderr, "I cannot find a product in %s; passing through unchanged" % original
            return original

        try:
            version = words.pop(0)
        except IndexError:
            version = None
        # 
        #
        # Is version actually a logical expression?  If so, we'll want to save it
        # as well as the exact version being installed
        #
        logical = None;
        #
        # Is there already a logical expression [in square brackets]? If so, we want to keep it
        #
        if "[" in words and "]" in words:
            left, right = words.index("["), words.index("]")
            logical = " ".join(words[left + 1 : right])
            del words[left : right + 1]

        if version and Eups.versionIsRelative(version):
            if logical:                 # how did this happen? Version is logical and also a [logical]
                print >> sys.stderr, "Two logical expressions are present in %s; using first" % original
                
            logical = " ".join([version] + words)
            version = None

        version = productList.get(productName, version) # accept the explicit version if provided

        if not version:
            try:
                product = Eups.Product(productName, noInit=True).initFromSetupVersion()
                version = product.version
            except RuntimeError, e:
                print >> sys.stderr, e

        if logical:
            if not Eups.version_match(version, logical):
                print >> sys.stderr, "Warning: %s %s failed to match condition \"%s\"" % (productName, version, logical)
        else:
            if version: 
                logical = ">= %s" % version

        args = flags + [productName]
        if version:
            args += [version]
            if versionRegexp and not re.search(versionRegexp, version):
                print >> sys.stderr, "Suspicious version for %s: %s" % (productName, version)
        #
        # Here's where we record the logical expression, if provided
        #
        if logical:
            args += ["[%s]" % logical]

        rewrite = "%s(%s)" % (cmd, " ".join(args))

        return rewrite
    #
    # Actually do the work
    #
    
    for line in ifd:
        if re.search(r"^\s*#", line):
            print >> ofd, line,
            continue
            
        # Attempt substitutions
        line = re.sub(r'(setupRequired|setupOptional)\("?([^"]*)"?\)', subSetup, line)

        print >> ofd, line,

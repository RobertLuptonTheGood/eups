#!/usr/bin/env python

# Routines that talk to eups; all currently use popen on eups shell commands,
# but you're not supposed to know that

import os
import re
import sys

def current(product="", dbz="", flavor = ""):
    """Return the current version of a product; if product is omitted,
    return a list of (pruduct, version) for all current products"""

    opts = ""
    if dbz:
        opts += " --select-db %s" % (dbz)
    if flavor:
        opts += " --flavor %s" % (flavor)

    products = []
    for line in os.popen("eups list --current %s %s 2>&1" % (opts, product)).readlines():
        if re.search(r"^ERROR", line):
            raise RuntimeError, line
        elif re.search(r"^WARNING", line):
            continue

        match = re.findall(r"\S+", line)
        if product:
            return match[0]

        products += [match[0:2]]

    return products

def declare(flavor, dbz, tablefile, products_root, product_dir, product, version, declare_current = False,
            noaction = False):
    """Declare a product"""

    opts = ""
    if declare_current:
        opts += " -c"
    if dbz:
        opts += " -z %s" % dbz

    tableopt = "-m"
    if tablefile != "none":
        if ("%s.table" % (product)) != tablefile:
            tableopt = "-M"

    try:
        cmd = "eups_declare --flavor %s%s %s %s --root %s/%s %s %s" % \
              (flavor, opts, tableopt, tablefile, products_root, product_dir, product, version)
        if noaction:
            print cmd
        else:
            if os.system(cmd) != 0:
                raise RuntimeError, cmd
    except KeyboardInterrupt:
        raise
    except:
        print >> sys.stderr, "Failed to declare product %s (version %s, flavor %s)" % \
              (product, version, flavor)

def dependencies(product, version, dbz="", flavor=""):
    """Return a product's dependencies in the form of a list of tuples
    (product, version, flavor)
"""

    opts = ""
    if dbz:
        opts += " --select-db %s" % (dbz)
    if flavor:
        opts += " --flavor %s" % (flavor)

    productList = os.popen("eups_setup setup %s -n --verbose %s %s 2>&1 1> /dev/null" % \
                    (opts, product, version)).readlines()

    dep_products = {}
    deps = []
    for line in productList:
        if re.search("^FATAL ERROR:", line):
            raise RuntimeError, ("Fatal error setting up %s:" % (product), "\t".join(["\n"] + productList))

        mat = re.search(r"^Setting up:\s+(\S+)\s+Flavor:\s+(\S+)\s+Version:\s+(\S+)", line)
        if not mat:
            continue
        
        (oneProduct, oneFlavor, oneVersion) = mat.groups()
        oneDep = (oneProduct, oneVersion, oneFlavor) # note the change in order

        # prune repeats of identical product version/flavor
        versionHash = "%s:%s" % (oneVersion, oneFlavor)
        if dep_products.has_key(oneProduct) and dep_products[oneProduct] == versionHash:
            continue
        dep_products[oneProduct] = versionHash

        deps += [oneDep]

    return deps

def flavor():
    """Return the current flavor"""
    
    if os.environ.has_key("EUPS_FLAVOR"):
        return os.environ["EUPS_FLAVOR"]
    return str.split(os.popen('eups_flavor').readline(), "\n")[0]

def list(product, version = "", dbz = "", flavor = ""):
    """Return a list of declared versions of a product; if the
    version is specified, just return the properties of that version.

    The return value for each product is a list:
       (version, database, directory, isCurrent, isSetup)
    """

    opts = ""
    if dbz:
        opts += " --select-db %s" % (dbz)
    if flavor:
        opts += " --flavor %s" % (flavor)

    result = []
    for info in os.popen("eups list %s --verbose %s %s" % (opts, product, version)).readlines():
        oneResult = re.findall(r"\S+", info)

        if len(oneResult) == 3:
            oneResult += [False]
        else:
            assert (oneResult[3] == "Current")
            oneResult[3] = True

        if len(oneResult) == 4:
            oneResult += [False]
        else:
            assert (oneResult[4] == "Setup")
            oneResult[4] = True
        assert len(oneResult) == 5

        result += [oneResult]

        if version:
            return oneResult
        
    return result

def table(product, version, flavor = ""):
    """Return the full path of a product's tablefile"""
    if flavor:
        flavor = "--flavor %s" % (flavor)
        
    info = os.popen("eups list %s --table %s %s" % \
                    (flavor, product, version)).readlines()[0].split("\n")
    for i in info:
        if re.search("^WARNING", i):
            print >> sys.stderr, i
        else:
            return re.findall(r"\S+", i)[0]

    return None

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def version():
    """Return eups' current cvs version"""

    version = '$Name: not supported by cvs2svn $'                 # version from cvs
    
    mat = re.search(r"^\$[N]ame:\s*(\S+)\s*\$$", version)
    if mat:
        version = mat.groups()[0]
    else:
        version = "(NOCVS)"
        
    return version

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

# Like getopt.getopt, but supports a dictionary options of recognised
# options, supports long option names, allows aliases, allows options
# to follow arguments, and sets the values of flag options to the
# number of occurrences of the flag

class Getopt:
    def __init__(self, options, argv = sys.argv, aliases = dict(), msg = None):
        """A class to represent the processed command line arguments.

options is a dictionary whose keys are is the short name of the option
(and the one that it'll be indexed as), and the value is a tuple; the
first element is a boolean specifying if the option takes a value; the
second (if not None) is a long alias for the option, and the third is
a help string.  E.g.
    ["-i", (False, "--install", "Extract and install the specified package")],

aliases is another dictionary, with values that specify additional long versions
of options; e.g.
    ["-i", ["--extract"]],

Options may be accessed as Getopt.options[], and non-option arguments as Getopt.argv[]

msg is the help message associated with the command
        
"""
        if msg:
            self.msg = msg
        else:
            self.msg = "Command [options] arguments"
        #
        # Provide a -h/--help option if -h is omitted
        #
        if not options.has_key('-h'):
            options["-h"] = (False, "--help", "Print this help message")        
        #
        # Build the options string for getopt() and a hash of the long options
        #
        optstr = ""
        longopts = {}
        for opt in options.keys():
            optstr += opt[1]
            if options[opt][0]:
                optstr += ":"

            if options[opt][1]:
                longopts[options[opt][1]] = opt

        for opt in aliases.keys():
            longopts[aliases[opt][0]] = opt
        #
        # Massage the arguments
        #
        nargv = []
        opts = {}
        verbose = 0
        i = 0
        while i < len(argv) - 1:
            i = i + 1
            a = argv[i]

            if re.search(r"^[^-]", a):
                nargv += [a]
                continue

            mat = re.search(r"^([^=]+)=(.*)$", a)
            if mat:
                (a, val) = mat.groups()
            else:
                val = None            

            if longopts.has_key(a):
                a = longopts[a]

            if options.has_key(a):
                if options[a][0]:
                    if val:
                        opts[a] = val
                    else:
                        try:
                            opts[a] = argv[i + 1]; i += 1
                        except IndexError:
                            raise RuntimeError, ("Option %s expects a value" % a)
                else:
                    if opts.has_key(a):
                        opts[a] += 1
                    else:
                        opts[a] = 1
            else:
                raise RuntimeError, ("Unrecognised option %s" % a)
        #
        # Save state
        #
        self.cmd_options = options  # possible options
        self.cmd_aliases = aliases  # possible aliases
        self.options = opts         # the options provided
        self.argv = nargv           # the surviving arguments

    def has_option(self, opt):
        """Whas the option "opt" provided"""
        return self.options.has_key(opt)

    def usage(self):
        """Print a usage message based on the options list"""

        print >> sys.stderr, """\
Usage:
    %s
Options:""" % self.msg

        def asort(a,b):
            """Sort alphabetically, so C and c appear together"""
            if a.upper() != b.upper():
                a = a.upper(); b = b.upper()

            if a < b:
                return -1
            elif a == b:
                return 0
            else:
                return 1

        for opt in sorted(self.cmd_options.keys(), cmp = asort):
            optstr = "%2s%1s %-12s %s" % \
                     (opt,
                      (not self.cmd_options[opt][1] and [""] or [","])[0],
                      self.cmd_options[opt][1] or "",
                      (not self.cmd_options[opt][0] and [""] or ["arg"])[0])
            
            print >> sys.stderr, "   %-21s %s" % \
                  (optstr, ("\n%25s"%"").join(self.cmd_options[opt][2].split("\n")))
            if self.cmd_aliases.has_key(opt):
                print >> sys.stderr, "                         Alias%s:" % \
                      (len(self.cmd_aliases[opt]) == 1 and [""] or ["es"])[0], " ".join(self.cmd_aliases[opt])


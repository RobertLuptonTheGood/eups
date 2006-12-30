#!/usr/bin/env python
#
# Export a product and its dependencies as a package, or install a
# product from a package
#
import os
import re
import sys

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Routines that talk to eups; all currently use popen on eups shell commands.
#
def current(product, dbz = "", flavor = ""):
    """Return current versions of products"""

    opts = ""
    if dbz:
        opts += " --select-db %s" % (dbz)
    if flavor:
        opts += " --flavor %s" % (flavor)

    lp = os.popen("eups list --current %s %s" % (opts, product)).readlines()
    if re.search(r"^ERROR", lp[0]):
        raise RuntimeError, lp[0]

    if product:
        products = [(product, re.findall(r"\S+", lp[0])[0])]
    else:
        products = []
        for p in lp:
            products += [re.findall(r"\S+", p)]

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

def dependencies(product, version, dbz="", no_dependencies=False, flavor=""):
    """Return a product's dependencies"""

    opts = ""
    if dbz:
        opts += " --select-db %s" % (dbz)
    if flavor:
        opts += " --flavor %s" % (flavor)

    deps = os.popen("eups_setup setup %s -n --verbose %s %s 2>&1 1> /dev/null" % \
                    (opts, product, version)).readlines()
    if no_dependencies:
        return deps[0:1]
    else:
        return deps

def flavor():
    """Return the current flavor"""
    
    if os.environ.has_key("EUPS_FLAVOR"):
        return os.environ["EUPS_FLAVOR"]
    return str.split(os.popen('eups_flavor').readline(), "\n")[0]

def list(product, version, dbz = "", flavor = ""):
    """Return the properties of a product"""

    opts = ""
    if dbz:
        opts += " --select-db %s" % (dbz)
    if flavor:
        opts += " --flavor %s" % (flavor)

    info = os.popen("eups list %s --verbose %s %s" % \
                    (opts, product, version)).readlines()[0].split("\n")[0]
    return re.findall(r"\S+", info)

def table(product, version, flavor = ""):
    """Return the name of a product's tablefile"""
    if flavor:
        flavor = "--flavor %s" % (flavor)
        
    info = os.popen("eups list %s --table %s %s" % \
                    (flavor, product, version)).readlines()[0].split("\n")
    for i in info:
        if re.search("^WARNING", i):
            print >> sys.stderr, i
        else:
            return re.findall(r"\S+", i)

    return None

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def version():
    """Return current cvs version"""

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
        self.options = options
        self.aliases = aliases
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
                            raise RuntimeError, "Option %s expects a value" % a
                else:
                    if opts.has_key(a):
                        opts[a] += 1
                    else:
                        opts[a] = 1
            else:
                raise RuntimeError, "Unrecognised option %s" % a

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

        for opt in sorted(self.options.keys(), cmp = asort):
            optstr = "%2s%1s %-12s %s" % \
                     (opt,
                      (not self.options[opt][1] and [""] or [","])[0],
                      self.options[opt][1] or "",
                      (not self.options[opt][0] and [""] or ["arg"])[0])
            
            print >> sys.stderr, "   %-21s %s" % \
                  (optstr, ("\n%25s"%"").join(self.options[opt][2].split("\n")))
            if self.aliases.has_key(opt):
                print >> sys.stderr, "                         Alias%s:" % \
                      (len(self.aliases[opt]) == 1 and [""] or ["es"])[0], " ".join(self.aliases[opt])


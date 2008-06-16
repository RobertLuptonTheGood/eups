import re, sys

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

# Like getopt.getopt, but supports a dictionary options of recognised
# options, supports long option names, allows aliases, allows options
# to follow arguments, and sets the values of flag options to the
# number of occurrences of the flag

class Getopt:
    def __init__(self, options, argv = sys.argv, aliases = {}, msg = None, checkArgs=True, extras=None):
        """A class to represent the processed command line arguments.

options is a dictionary whose keys are is the short name of the option
(and the one that it'll be indexed as), and the value is a tuple; the
first element is a boolean specifying if the option takes a value; the
second (if not None) is a long alias for the option, and the third is
a help string.  E.g.
    ["-i", (False, "--install", "Extract and install the specified package")],
Values may be provided as a separate argument (-o XXX) or with = (-o=XXX).

If you specify the same option more than once, the values will be concatenated
(separated by :) if the option takes a value, and incremented if it doesn't; i.e.
   -a -b XXX -a -a -b=YYY
sets options["-a"] to 3, and options["-b"] to "XXX:YYY"

aliases is another dictionary, with values that specify additional long versions
of options; e.g.
    ["-i", ["--extract"]],

Options may be accessed as Getopt.options[], and non-option arguments as Getopt.argv[]

msg is the help message associated with the command;  if checkArgs is False, non-recognised
options are returned in self.argv
        
If extras is not None, it's taken to be a string specifying further arguments; if they
are not recognised they are silently ignored
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
            if isinstance(aliases[opt], str):
                aliases[opt] = [aliases[opt]]

            for a in aliases[opt]:
                longopts[a] = opt
        #
        # Handle extras, if present
        #
        if extras:
            if isinstance(extras, str):
                extras = extras.split(" ")

            argv += [None]
            argv += extras
        #
        # Massage the arguments
        #
        nargv = []
        opts = {}
        verbose = 0
        i = 0
        processingExtras = False        # we aren't yet; signalled by a None argument
        while i < len(argv) - 1:
            i = i + 1
            a = argv[i]

            if a == None:               # marker for extras
                processingExtras = True
                continue

            if a == "" or re.search(r"^[^-]", a):
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
                    if opts.has_key(a):
                        opts[a] += ":"
                    else:
                        opts[a] = ""

                    if not val:
                        try:
                            val = argv[i + 1]; i += 1
                        except IndexError:
                            raise RuntimeError, ("Option %s expects a value" % a)

                    opts[a] += val
                else:
                    if opts.has_key(a):
                        opts[a] += 1
                    else:
                        opts[a] = 1
            elif re.search(r"-\d*$", a): # a negative integer or "-"
                nargv += [a]
            elif processingExtras:
                continue
            elif not checkArgs:
                nargv += [a]
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

    def get(self, opt, value=None):
        """Return the value of option "opt" if provided, else the value (default: None)"""
        return self.options.get(opt, value)

    def usage(self):
        """Print a usage message based on the options list"""

        print >> sys.stderr, """\
Usage:
    %s
Options:""" % self.msg

        def asort(A, B):
            """Sort alphabetically, so -C, --cvs, and -c appear together"""

            a = self.cmd_options[A][1]
            if not a:
                a = A

            b = self.cmd_options[B][1]
            if not b:
                b = B

            a = re.sub(r"^-*", "", a)       # strip leading -
            b = re.sub(r"^-*", "", b)       # strip leading -

            if a.upper() != b.upper():
                a = a.upper(); b = b.upper()

            if a < b:
                return -1
            elif a == b:
                return 0
            else:
                return 1

        skeys = self.cmd_options.keys(); skeys.sort(asort) # python <= 2.3 doesn't support "sorted"
        for opt in skeys:
            popt = opt
            if ord(popt[1]) < ord(' '): # not printable; only long option matters
                popt = ""
            optstr = "%2s%1s %s" % \
                     (popt,
                      ((not popt or not self.cmd_options[opt][1]) and [""] or [","])[0],
                      self.cmd_options[opt][1] or "")
            optstr = "%-16s %s" % \
                     (optstr, (not self.cmd_options[opt][0] and [""] or ["arg"])[0])
            
            print >> sys.stderr, "   %-23s %s" % \
                  (optstr, ("\n%27s"%"").join(self.cmd_options[opt][2].split("\n")))
            if self.cmd_aliases.has_key(opt):
                print >> sys.stderr, "                           Alias%s:" % \
                      (len(self.cmd_aliases[opt]) == 1 and [""] or ["es"])[0], " ".join(self.cmd_aliases[opt])

def declareArgs(helpStr, required=None, optional=None):
    """Return an augmented helpStr and (nmin, nmax) given lists of required and optional arguments;
    if only a single argument is specified, a string may be passed instead of a list
    """

    if not required:
        required = []
    if not optional:
        optional = []

    if isinstance(required, str):
        required = [required]
    if isinstance(optional, str):
        optional = [optional]

    if required:
        helpStr += " " + " ".join(required)
    if optional:
        helpStr += " [" + "] [".join(optional) + "]"

    narg = (len(required), len(required) + len(optional))

    return helpStr, narg

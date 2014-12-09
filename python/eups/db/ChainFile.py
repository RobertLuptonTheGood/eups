import os, re, sys, pwd
from eups.utils import ctimeTZ, isRealFilename, stdwarn, stderr, getUserName

who = getUserName(full=True)

class ChainFile(object):
    """
    a representation of the data contained in a product tag chain file.  
    This file records which version of a product a particular tag is 
    assigned to.

    @author: Raymond Plante
    """

    # Per-flavor metadata fields in file, in order of appearance.  
    # Values are stored in self.info
    _fields = [      
      "DECLARER",
      "DECLARED",
      "MODIFIER",
      "MODIFIED",
    ]

    def __init__(self, file, productName=None, tag=None, verbosity=0, 
                 readFile=True):

        # the file containing the tag information
        self.file = file

        # the name of the product.
        self.name = productName

        # the name of the tag being described
        self.tag = tag

        # tag assignment attributes as a dictionary.  Each key is a flavor 
        # name and its value is a properties set of named metadata.
        self.info = {}

        if readFile and os.path.exists(self.file):
            self._read(self.file, verbosity)


    def getFlavors(self):
        """
        return the flavors described by this chain.

        @return string[] :  the supported flavor names
        """
        return self.info.keys()

    def hasFlavor(self, flavor):
        """
        return true if the product is declared for a given flavor 
        """
        return self.info.has_key(flavor)

    def getVersion(self, flavor):
        """
        return the version that has been assigned this tag or None if the 
        tag is not assigned to the flavor.

        @param flavor : the name of the flavor to get the tagged versions for. 
        @return string : the version tag is assigned to
        """
        if not self.info.has_key(flavor) or \
           not self.info[flavor].has_key("version"):
            return None
        return self.info[flavor]["version"]

    def setVersion(self, version, flavors=None):
        """
        assign this tag to a version.

        @param version : the version to assign this tag to
        @param flavors : the flavors to update tags for as a list or a single
                           string (for a single flavor).  If None, tag all 
                           previously tagged flavors will be retagged.
        """
        if flavors is None:
            return self.setVersion(self.getFlavors())
        if not isinstance(flavors, list):
            flavors = [flavors]

        for flavor in flavors:
            if self.info.has_key(flavor):
                info = self.info[flavor].copy()
                info["modifier"] = who
                info["modified"] = ctimeTZ()
            else:
                info = { "declarer": who, "declared": ctimeTZ() } 

            info["version"] = version
            self.info[flavor] = info

    def removeVersion(self, flavors=None):
        """
        remove the version tagging for the given flavors.  Return false 
        if the tag was not previously assigned for any of the flavors.

        @param flavors : the flavors to remove the tag for.  If None, the 
                            tag for all available flavors will be removed.  
        @return bool : False if tag was not assigned for the given flavors.
        """
        if flavors is None:
            return self.removeVersion(self.getFlavors())
        if not isinstance(flavors, list):
            flavors = [flavors]

        updated = False
        for flavor in flavors:
            if self.info.has_key(flavor):
                del self.info[flavor]
                updated = True

        return updated

    def hasNoAssignments(self):
        """
        return true if there are no currently set  assignments of this tag.
        """
        return (len(self.info.keys()) == 0)

    def write(self, file=None):
        """
        write the tag assingment data out to a file.  Note that if the tag
        is not currently assigned to any flavor, the file will be removed 
        from disk.

        @param file : the file to write the data to.  If None, the 
                       configured file will be used.  
        """

        if not file:
            file = self.file
        if self.hasNoAssignments():
            if os.path.exists(file):  os.remove(file)
            return

        fd = open(file, "w")

        # Should really be "FILE = chain", but eups checks for version.  I've changed it to allow 
 	# chain, but let's not break backward compatibility with old eups versions 
        print >> fd, """FILE = version
PRODUCT = %s
CHAIN = %s
#***************************************\
""" % (self.name, self.tag)

        for fq in self.info.keys():
            mat = re.search(r"^([^:]+)(:?:(.*)$)?", fq)
            flavor = mat.group(1)
            qualifier = mat.group(3)
            if not qualifier:
                qualifier = ""

            print >> fd, """
#Group:
   FLAVOR = %s
   VERSION = %s
   QUALIFIERS = "%s"\
""" % (flavor, self.info[fq]["version"], qualifier)

            for field in self._fields:
                k = field.lower()

                if self.info[fq].has_key(k):
                    value = self.info[fq][k]
                    if not value:
                        continue

                    print >> fd, "   %s = %s" % (field.upper(), value)

            print >> fd, "#End:"

        fd.close()

    def _read(self, file=None, verbosity=0):
        """
        read in data from a file, possibly overwring previously tagged products

        @param file : the file to read
        """
        if not file:
            file = self.file
        fd = open(file)

        flavor = None
        lineNo = 0           # line number in input file, for diagnostics
        for line in fd.readlines():
            lineNo += 1
            line = line.strip()
            line = re.sub(r"#.*$", "", line)
            if not line:
                continue

            #
            # Get key = value
            #
            mat = re.search(r"^(\w+)\s*=\s*(.*)", line, re.IGNORECASE)
            if mat:
                key = mat.group(1).lower()
                value = re.sub(r"^\"|\"$", "", mat.group(2))

            #
            # Ignore Group: and End:
            #
            elif re.search(r"^(End|Group)\s*:", line):
                continue
            else:
                raise RuntimeError, \
                      ("Unexpected line \"%s\" at %s:%d" % \
                         (line, self.file, lineNo))

            #
            # Check for information about product
            #
            if key == "file":
                if value.lower() not in ["chain", "version"]:
                    raise RuntimeError, \
                          ("Expected \"File = Version\"; saw \"%s\" at %s:%d" \
                             % (line, self.file, lineNo))

            elif key == "product":
                if not self.name:
                    self.name = value
                elif self.name != value:
                  if verbosity >= 0:
                    print >> stdwarn, \
                        "Warning: Unexpected product name, %s, in chain file; expected %s,\n  file=%s" % \
                        (value, self.name, file)

            elif key == "chain":
                if not self.tag:
                    self.tag = value
                elif self.tag != value:
                  if verbosity >= 0:
                    print >> stdwarn, \
                        "Warning: Unexpected tag/chain name, %s, in chain file; expected %s,\n  file=%s" % \
                        (value, self.tag, file)

            elif key == "flavor": # Now look for flavor-specific blocks
                flavor = value
                self.info[flavor] = {}
            else:
                value = re.sub(r"^\"(.*)\"$", r"\1", mat.group(2)) # strip ""

                if key == "qualifiers":
                    if value:           # flavor becomes e.g. Linux:build
                        newflavor = "%s:%s" % (flavor, value)
                        self.info[newflavor] = self.info[flavor]
                        del self.info[flavor]
                        flavor = newflavor
                else:
                    self.info[flavor][key] = value

        fd.close()




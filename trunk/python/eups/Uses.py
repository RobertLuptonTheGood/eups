"""
the Uses class -- a class for tracking product dependencies (used by the remove() 
function).  
"""
import re

#
# Cache for the Uses tree
#
class Uses(object):
    """
    a class for tracking product dependencies.  Typically an instance of 
    this class is created via a call to Eups.uses().  This class is used 
    by Eups.remove() to figure out what to remove.  
    """
    def __init__(self):
        self._depends_on = {} # info about products that depend on key
        self._setup_by = {}       # info about products that setup key, directly or indirectly

    def _getKey(self, p, v):
        return "%s:%s" % (p, v)

    def _remember(self, p, v, info):
        key = self._getKey(p, v)

        if not self._depends_on.has_key(key):
            self._depends_on[key] = []

        self._depends_on[key] += [info]

    def _do_invert(self, productName, versionName, k, depth, optional=False):
        """Workhorse for _invert"""
        if depth <= 0 or not self._depends_on.has_key(k):
            return
        
        for p, v, o in self._depends_on[k]:
            o = o or optional

            key = self._getKey(p, v)
            if not self._setup_by.has_key(key):
                self._setup_by[key] = []

            self._setup_by[key] += [(productName, versionName, (v, o, depth))]

            self._do_invert(productName, versionName, self._getKey(p, v), depth - 1, o)

    def _invert(self, depth):
        """ Invert the dependencies to tell us who uses what, not who depends on what"""

        pattern = re.compile(r"^(?P<product>[\w]+):(?P<version>[\w.+\-]+)")

        self._setup_by = {}
        for k in self._depends_on.keys():
            mat = pattern.match(k)
            assert mat

            productName = mat.group("product")
            versionName = mat.group("version")

            self._do_invert(productName, versionName, k, depth)

        if False:
            for k in self._depends_on.keys():
                print "%-30s" % k, self._depends_on[k]
        if False:
            print; print "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"; print
        if False:
            for k in self._setup_by.keys():
                print "XX %-20s" % k, self._setup_by[k]
        #
        # Find the minimum depth for each product
        #
        for k in self._setup_by.keys():
            vmin = {}
            dmin = {}
            for val in self._setup_by[k]:
                p, pv, requestedInfo = val
                d = requestedInfo[-1]    # depth is the last item

                key = "%s-%s" % (p, pv)
                if not dmin.has_key(key) or d < dmin[key]:
                    dmin[key] = d
                    vmin[key] = val

            self._setup_by[k] = []
            for key in vmin.keys():
                self._setup_by[k] += [vmin[key]]
        #
        # Make values in _setup_by unique
        #
        for k in self._setup_by.keys():
            self._setup_by[k] = list(set(self._setup_by[k]))

    def users(self, productName, versionName=None):
        """Return a list of the users of productName/productVersion; each element of the list is:
        (user, userVersion, (productVersion, optional)"""
        if versionName:
            versionName = re.escape(versionName)
        else:
            versionName = r"[\w.+\-]+"
            
        versionName = r"(?P<version>%s)" % versionName

        pattern = re.compile(r"^%s$" % self._getKey(productName, versionName))
        consumerList = []
        for k in self._setup_by.keys():
            mat = pattern.match(k)
            if mat:
                consumerList += (self._setup_by[k])
        #
        # Be nice; sort list
        #
        def pvsort(a,b):
            """Sort by product then version then information"""

            if a[0] == b[0]:
                if a[1] == b[1]:
                    return cmp(a[2], b[2])
                else:
                    return cmp(a[1], b[1])
            else:
                return cmp(a[0], b[0])

        consumerList.sort(pvsort)
        
        return consumerList
        

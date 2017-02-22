"""
the Uses class -- a class for tracking product dependencies (used by the remove()
function).
"""
import re
from .utils import cmp_or_key, cmp

#
# Cache for the Uses tree
#
class Props(object):
    def __init__(self, version, optional, depth):
        self.version = version
        self.optional = optional
        self.depth = depth

class Uses(object):
    """
    a class for tracking product dependencies.  Typically an instance of
    this class is created via a call to Eups.uses().  This class is used
    by Eups.remove() to figure out what to remove.
    """

    def __init__(self):
        self._depends_on = {}           # info about products that depend on key
        self._setup_by = {}             # info about products that setup key, directly or indirectly

    def _getKey(self, p, v):
        return "%s:%s" % (p, v)

    def _splitKey(self, k):
        return k.split(":", 1)

    def remember(self, p, v, info):
        key = self._getKey(p, v)

        if key not in self._depends_on:
            self._depends_on[key] = []

        self._depends_on[key] += [info]

    def invert(self, depth):
        """ Invert the dependencies to tell us who uses what, not who depends on what"""

        self._setup_by = {}
        for k in self._depends_on.keys():
            productName, versionName = self._splitKey(k)
            for dname, dver, doptional, ddepth in self._depends_on[k]:
                key = self._getKey(dname, dver)
                if key not in self._setup_by:
                    self._setup_by[key] = []

                self._setup_by[key].append((productName, versionName, Props(dver, doptional, ddepth)))

        #
        # Find the minimum depth for each product, and make sure that if a product is labelled required
        # if it is required at any depth
        #
        for k in self._setup_by.keys():
            vmin = {}
            dmin = {}
            for val in self._setup_by[k]:
                p, pv, props = val

                key = "%s-%s" % (p, pv)
                if key not in dmin or props.depth < dmin[key]:
                    dmin[key] = props.depth
                    vmin[key] = val

            self._setup_by[k] = list(set(vmin.values())) # Use set() to make values unique

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

        consumerList.sort(**cmp_or_key(pvsort))

        return consumerList


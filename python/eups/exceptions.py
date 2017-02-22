"""
exceptions raised by EUPS.  This includes EupsException, the base exception
for EUPS related failures.
"""
class EupsException(Exception):
    """
    an exception indicating a failure during an EUPS operation.
    """

    def __init__(self, message):
        """
        create the exception
        @param message  the message describing the failure.
        """
        self.msg = message

    def __str__(self):
        """
        return the exception message
        """
        return self.getMessage()

    def getMessage(self):
        """
        return the exception message
        """
        return self.msg


class ProductNotFound(EupsException):
    """
    an exception indicating that the requested product was not found in
    a stack database.

    An instance has the following public attributes:
        name     the product name
        version  the version.  A None value (default) means no product of
                     any version was found.
        flavors  the platform flavors of interest.  A None value (default)
                     means that the flavor is unknown, though typically can
                     be assumed to mean any of the supportable platforms.
        stack    the path to the EUPS-managed software stack or to the
                     database directory (ups_db).  A None value (default)
                     means that the flavor is unknown, though typically can
                     be assumed to mean any of the stacks in scope.
    """

    def __init__(self, name, version=None, flavors=None, stack=None, msg=None):
        """
        create the exception
        @param name     the product name
        @param version  the version.  Use None (default) if no product of
                            any version was found.
        @param flavors   the platform flavors of interest.  default: None
        @param stack    the path to the EUPS-managed software stack or to the
                           database directory (ups_db)
        @param msg      the descriptive message.  A default will be generated
                           from the product name.
        """
        message = msg
        if message is None:
            message = "Product " + str(name)
            if version is not None:
                message += " %s" % str(version)
            if flavors:
                message += " for %s" % str(flavors)
            message += " not found"
            if stack is not None:
                message += " in %s" % str(stack)
        EupsException.__init__(self, message)
        self.name = name
        self.version = version
        if not isinstance(flavors, list):
            flavors = [flavors]
        self.flavors = flavors
        self.stack = stack

class UnderSpecifiedProduct(EupsException):
    """
    An exception indicating that not enough information about a product
    was provided to carry out a requested operation.

    This exception includes the following public parameters, any of which
    may be None (because they were either not provided by the user or not
    relevent):
       name     the product name
       version  the version name
       flavor   the platform flavor
    """
    def __init__(self, productName=None, version=None, flavor=None, msg=None):
        """
        @param productName     the product name
        @param version  the version.
        @param flavor   the platform flavor of interest.
        @param msg      the descriptive message.  If None, A default will be
                       generated from the product name
        """
        message = msg
        if message is None:
            message = "Under-specified product: " + str(productName)
            if version is not None:
                message += " ver: %s" % str(version)
            if flavor is not None:
                message += " flavor: %s" % str(flavor)

        EupsException.__init__(self, message)

        self.name = productName
        self.version = version
        self.flavor = flavor

class TableError(EupsException):
    """
    A parent exception for problems accessing a product's table.

    This exception includes the following public parameters, any of which
    may be None:
       tablefile  the path to the missing tablefile
       name       the product name
       version    the version name
       flavor     the platform flavor
    """

    def __init__(self, tablefile=None, productName=None, version=None,
                 flavor=None, problem=None, msg=None):
        """
        @param productName  the product name
        @param version      the version.
        @param flavor       the platform flavor of interest.
        @param problem      a terse description of the problem.  What gets
                               printed will combine this with the product
                               information (unless msg is given).
        @param msg          the full descriptive message.  If None, A default
                               based on problem and citing the product
                               information will be generated.
        """
        if problem is None:
            if msg:
                problem = msg
            else:
                problem = "Unspecified table problem"

        self.tablefile = tablefile
        self.name = productName
        self.version = version
        self.flavor = flavor
        self.problem = problem

        EupsException.__init__(self, self._makeDefaultMessage(msg))

    def _makeDefaultMessage(self, msg):
        out = msg
        if out is None:
            out = self.problem
            if self.name is not None:
                out += " for %s" % str(self.name)
            if self.version is not None:
                out += " %s" % str(self.version)
            if self.flavor is not None:
                out += " (%s)" % str(self.flavor)
            if self.tablefile is not None:
                out += ": %s" % str(self.tablefile)
        return out


class TableFileNotFound(TableError):
    """
    a TableError indicating that a table file could not be found on disk.

    This exception includes the following public parameters, any of which
    may be None:
       tablefile  the path to the missing tablefile
       name       the product name
       version    the version name
       flavor     the platform flavor
    """

    def __init__(self, tablefile=None, productName=None, version=None,
                 flavor=None, msg=None):
        """
        @param productName  the product name
        @param version      the version.
        @param flavor       the platform flavor of interest.
        @param msg          the descriptive message.  If None, A default will
                               be generated.
        """
        TableError.__init__(self, tablefile, productName, version, flavor,
                            "Table file not found", msg)

class BadTableContent(TableError):
    """
    a TableError indicating an error occurred while parsing a table file.

    This exception includes the following public parameters, any of which
    may be None:
       tablefile  the path to the missing tablefile
       name       the product name
       version    the version name
       flavor     the platform flavor
    """

    def __init__(self, tablefile=None, productName=None, version=None,
                 flavor=None, msg=None):
        """
        @param productName  the product name
        @param version      the version.
        @param flavor       the platform flavor of interest.
        @param msg          the descriptive message.  If None, A default will
                               be generated.
        """
        TableError.__init__(self, tablefile, productName, version, flavor,
                            "Table parsing error", msg)

class CustomizationError(EupsException):
    """
    an error occurred while running a user's customization code
    """

    def __init__(self, msg=None):
        """
        @param msg          the descriptive message.  If None, A default will
                               be generated.
        """
        if not msg:
            msg = "Unknown user customization error"
        EupsException.__init__(self, msg)

class TagNameConflict(EupsException):
    """
    an exception indicating that there was a tagname conflict
    a stack database.

    An instance has the following public attributes:
        name     the product name
        version  the version.  A None value (default) means no product of
                     any version was found.
        flavors  the platform flavors of interest.  A None value (default)
                     means that the flavor is unknown, though typically can
                     be assumed to mean any of the supportable platforms.
        stack    the path to the EUPS-managed software stack or to the
                     database directory (ups_db).  A None value (default)
                     means that the flavor is unknown, though typically can
                     be assumed to mean any of the stacks in scope.
    """

    def __init__(self, name, version=None, flavors=None, stack=None, msg=None):
        """
        create the exception
        @param name     the product name
        @param version  the version.  Use None (default) if no product of
                            any version was found.
        @param flavors   the platform flavors of interest.  default: None
        @param stack    the path to the EUPS-managed software stack or to the
                           database directory (ups_db)
        @param msg      the descriptive message.  A default will be generated
                           from the product name.
        """
        message = msg
        if message is None:
            message = "Product " + str(name)
            if version is not None:
                message += " %s" % str(version)
            if flavors:
                message += " for %s" % str(flavors)
            message += " not found"
            if stack is not None:
                message += " in %s" % str(stack)
        EupsException.__init__(self, message)
        self.name = name
        self.version = version
        if not isinstance(flavors, list):
            flavors = [flavors]
        self.flavors = flavors
        self.stack = stack


class OperationForbidden(EupsException):
    """
    an exception indicating that someone tried to do something illegal

    An instance has the following public attributes:

        message
    """

    def __init__(self, message):
        """
        create the exception
        @param message  the message describing the failure.
        """
        EupsException.__init__(self, message)


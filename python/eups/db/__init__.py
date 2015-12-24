"""
a module for querying metadata for products declared into a single EUPS 
database.  A database is comprised of a set of special files in single 
directory, usually called "ups_db".  

The main classes in this module are:
   Database     an interface into the data stored in the database files.  
                 Users can lookup information about declared products, 
                 declare new products, or assign tags.  
   VersionFile  an interface into the data about a specific version of a 
                 product which is stored in a single file in the database.
   ChainFile    an interface into the data about the assignment of a 
                 specific tag to a product, which is stored in a single 
                 file in the database.
"""
from .VersionFile import VersionFile 
from .ChainFile import ChainFile
from .Database import Database


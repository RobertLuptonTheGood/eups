#!/usr/bin/perl
# Parser for eups table files
# Nikhil Padmanabhan, Princeton
#
#
# Jan 22, 2002
#EUPS : A Unix Versioning System
#Copyright (C) 2003 Nikhil Padmanabhan

#    This program is free software; you can redistribute it and/or
#modify it under the terms of the GNU General Public License
#    as published by the Free Software Foundation; either version 2
#of the License, or (at your option) any later version.

#This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

############################

package eups_setup;
require Exporter;

our @ISA = qw(Exporter);
our @EXPORT = qw(eups_unsetup eups_setup eups_find_products eups_parse_argv eups_show_options);
our $VERSION = 1.1;

#Subroutines follow

sub fix_special {
# This is essential since some of the flavors have special characters in 
# them.
    my $arg = $_[0];
    $arg =~ s/\\/\\\\/g;
    $arg =~ s/\./\\\./g;
    $arg =~ s/\+/\\\+/g;
    $arg =~ s/\(/\\\(/g;
    $arg =~ s/\)/\\\)/g;
    $arg =~ s/\{/\\\{/g;
    $arg =~ s/\}/\\\}/g;
    $arg =~ s/\^/\\\^/g;
    $arg =~ s/\*/\\\*/g;
    $arg =~ s/\?/\\\?/g;
    $arg =~ s/\[/\\\[/g;
    $arg =~ s/\|/\\\|/g;
    return $arg;
}

sub envInterpolate {
# Interpolates in values of environment variables
    my $in = $_[0];
    my @env_var = $in =~ m/\$\{(.+?)\}/g;
    for (my $i = 0; $i < @env_var; $i++) {
	my $val = $ENV{$env_var[$i]};
	$in =~ s/\$\{.+?\}/$val/g;
    }
    return $in;
}

sub cleanArg {
# Cleans out quotes and leading spaces
    my $pval = $_[0];
# $pval might have leading spaces - remove these
    my ($val) = $pval =~ m/ *([^ ].*)/;
# Maybe $val is quoted
    if ($val =~ m/".*"/) {
        ($pval) = $val =~ m/"(.*)"/;
        $val = $pval;
    }
    return $val;
}

sub addAlias {
    use File::Basename;
    our $outfile;
    my $shell = basename($ENV{"SHELL"});
    $shell = "sh" if ($shell eq "bash");
    $shell = "csh" if ($shell eq "tcsh");
    my $name = $_[0];
    my $value = $_[1];
    if ($shell eq "csh") { 
	print $outfile "alias $name \"$value\"\n";
    }
    if ($shell eq "sh") {
	print $outfile "function $name \{ $value \; \} \n";
    }
}

sub unAlias {
    use File::Basename;
    our $outfile;
    my $shell = basename($ENV{"SHELL"});
    $shell = "sh" if ($shell eq "bash");
    $shell = "csh" if ($shell eq "tcsh");
    my $name = $_[0];
    if ($shell eq "csh") {
        print $outfile "unalias $name\n";
    }
    if ($shell eq "sh") {
        print $outfile "unfunction $name\n";
    }
}


sub envAppend {
    our $outfile;
    my $var = $_[0];
    my $val = cleanArg($_[1]);
    my $delim = cleanArg($_[2]);
    $delim = ":" if ($delim eq "");

    $curval = $ENV{$var};
    if ($curval) {
       $curval .= $delim;
    }
    $curval .= "$val";

    $ENV{$var} = envInterpolate($curval);
}

sub envPrepend {
    our $outfile;
    my $var = $_[0];
    my $val = cleanArg($_[1]);
    my $delim = cleanArg($_[2]);
    $delim = ":" if ($delim eq "");

    $curval = "$val";
    if ($curval) {
       $curval .= $delim;
    }
    $curval .= $ENV{$var};

    $ENV{$var} = envInterpolate($curval);
}

sub envSet {
    my $var = $_[0];
    my $val = cleanArg($_[1]);

    $ENV{$var} = envInterpolate($val);
}

sub envRemove {
    my $var = $_[0];
    my $pval = $_[1];
    $pval = envInterpolate($pval);
    my $val = cleanArg($_[1]);
    my $delim = cleanArg($_[2]);
    my $sval = fix_special($val);
    $delim = ":" if ($delim eq "");
    my $sdelim = fix_special($delim);
    $curval = $ENV{$var};
    $curval =~ s/$sval//;
    $curval =~ s/$sdelim$sdelim/$sdelim/;
    $curval =~ s/^$sdelim//;
    $curval =~ s/$sdelim$//;
    $ENV{$var} = $curval;
}

sub envUnset {
    our $outfile;
    my $var = $_[0];
    delete $ENV{$var};
}

sub extract_table_commands {

    my $data = $_[0];
    my $flavor = $_[1];
    my $flavor = fix_special($flavor);
    my $pattern = "FLAVOR\\s*=\\s*$flavor(\\s|\n)";
    my $pattern2 = "FLAVOR\\s*=\\s*ANY(\\s|\n)";
    my $pattern3 = "FLAVOR\\s*=\\s*NULL(\\s|\n)";

# Extract the groups - first see if old style table file
    my @group = ($data =~ m/group:(.+?end:)/gsi);
    if (scalar(@group) == 0) {
# If minimal table file
	$data = "$data\n";
	my @lines = split  "\n", $data;
	my $record = 1;
	my $inblock = 1;
	my $block = "";
	for ($i=0; $i < @lines; $i++) {
	    my $this = "$lines[$i]\n"; 
	    if ($lines[$i] =~ m/flavor\s*=/gsi) {
		$record = 0 if ($inblock == 1);
		$record = 1 if ($this =~ m/$pattern/gsi);
		$record = 1 if ($this =~ m/$pattern2/gsi);
		$record = 1 if ($this =~ m/$pattern3/gsi);
		$inblock = 0;
		next;
	    }
	    $block = "$block$this" if ($record == 1);
	    $inblock = 1;
	}
	@group = ($block);
    } else {
# If old style table file
	for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
	    $pos = $i if ($group[$i] =~ m/$pattern/gsi);
	    $pos = $i if ($group[$i] =~ m/$pattern2/gsi);
	    $pos = $i if ($group[$i] =~ m/$pattern3/gsi);
	}
	if ($pos == -1) {           # no flavor was specified
	    warn "FATAL ERROR: no match for flavor \"$flavor\" in table file\n";
	    return -1;
	} else {
	    @group = ($group[$pos] =~ m/Common:(.+?)End:/gsi);
	}
    }


    return $group[0];

}


sub parse_table {
    my $fn = $_[0];
    my $proddir = $_[1];
    my $upsdir = $_[2];
    my $prod = $_[3];
    my $vers = $_[4];
    my $flavor = $_[5];
    my $db = $_[6];
    my $fwd = $_[7];
    our $outfile = $_[8];
    my $quiet = $_[9];
    my $data = 0;

# Define the return value
    my $retval = 0;

# Define the command hashes

%switchback = (
addalias => \&unAlias,
envappend => \&envRemove,
envprepend => \&envRemove,
envremove => \&envAppend,
envset => \&envUnset,
envunset => \&envSet,
pathappend => \&envRemove,
pathprepend => \&envRemove,
pathremove => \&envAppend,
proddir => \&envUnset,
setupenv => \&envUnset,
	       );

%switchfwd = (
addalias => \&addAlias,
envappend => \&envAppend,
envprepend => \&envPrepend,
envremove => \&envRemove,
envset => \&envSet,
envunset => \&envUnset,
pathappend => \&envAppend,
pathprepend => \&envPrepend,
pathremove => \&envRemove,
proddir => \&envSet,
setupenv => \&envSet,
               );

# Some local variables
    my $pos; my $i;
    my $comm; my $arg; my $qaz;


# Read in the table file
    if ($fn eq "none") {
       $data = "";
    } else {
       my @size = stat($fn);
       open FILE, "<$fn";
       read FILE, $data, $size[7];
       close FILE;
       $data =~ s/\#.*?\n//g;	# strip comments
    }

# Extract the commands from the table file
    $group = extract_table_commands($data, $flavor);
    if ($group==-1) {
	$retval = -1;
	return $retval;
    }

# Replace certain variables
    $group =~ s/\$\{PRODUCTS\}/$db/g;
    $group =~ s/\$\{UPS_PROD_DIR\}/$proddir/g;
    $group =~ s/\$\{UPS_PROD_FLAVOR\}/$flavor/g;
    $group =~ s/\$\{UPS_PROD_NAME\}/$prod/g;
    $group =~ s/\$\{UPS_PROD_VERSION\}/$vers/g;
    $group =~ s/\$\{UPS_UPS_DIR\}/$upsdir/g;
    
# Execute the proddir and setupenv commands directly
    $comm = "setupenv";
    $qaz = $prod;
    $qaz =~ tr/[a-z]/[A-Z]/;
    $arg[0] = "SETUP_$qaz";
    #$arg[1] = "$prod $vers -f $flavor -z $db";
    $arg[1] = "$prod $vers -f $flavor -Z $ENV{PROD_DIR_PREFIX}";
    if ($fwd == 0) {
	$switchback{$comm}->(@arg);
    } else {
	$switchfwd{$comm}->(@arg);
    }
    $arg[0] = "$qaz\_DIR";
    $arg[1] = "$proddir";
    $comm = "proddir";
    if ($fwd == 0) {
	$switchback{$comm}->(@arg);
    }
    else {
	$switchfwd{$comm}->(@arg);
    }

# Now loop over the remaining commands
    my @lines = split "\n",$group;
    for ($i = 0;$i<@lines;$i++) {
	next if (!($lines[$i] =~ m/[a-z]+\(.*\)/i));
	($comm,$arg)=$lines[$i] =~ m/([a-z]+)\((.*)\)/i;
	my @arg = split ",",$arg;
	$comm =~ tr/[A-Z]/[a-z]/;
	if ($comm eq "setupenv") {
	    print STDERR "WARNING : Deprecated command $comm\n" if ($debug > 1);
            next;
	}
	if ($comm eq "proddir") {
            print STDERR "WARNING : Deprecated command $comm\n" if ($debug > 1);
            next;
	}
	if (($comm eq "setuprequired")&&($fwd==0)) {
            ($qaz) = $arg =~ m/ *"(.*)"/;
            $foo = eups_unsetup($qaz,$outfile,$debug,$quiet);
	    $retval =+ $foo;
	    print STDERR "ERROR: REQUIRED UNSETUP $qaz failed \n" if ($foo < 0);
	    next;
	}
        if (($comm eq "setupoptional")&&($fwd==0)) {
	    ($qaz) = $arg =~ m/ *"(.*)"/;
	    eups_unsetup($qaz,$outfile,$debug,$quiet);
	    next;
        }
        if (($comm eq "setuprequired")&&($fwd==1)) {
	    ($qaz) = $arg =~ m/ *"(.*)"/;
            $foo = eups_setup($qaz,$outfile,$debug,$quiet);
	    $retval =+ $foo;
            print STDERR "ERROR: REQUIRED SETUP $qaz failed \n" if ($foo < 0);
	    next;
        }
        if (($comm eq "setupoptional")&&($fwd==1)) {
            ($qaz) = $arg =~ m/ *"(.*)"/;
            eups_setup($qaz,$outfile,$debug,$quiet);
	    next;
        }
	if ($fwd == 0) {
	    if ($switchback{$comm}) {
		$switchback{$comm}->(@arg)}
	    else 
	    {
		print STDERR "Unknown command $comm in $fn\n";
	    }
	} 
	else {
            if ($switchfwd{$comm}) {
                $switchfwd{$comm}->(@arg)}
            else
            {
                print STDERR "Unknown command $comm in $fn\n";
            }
        } 

    }   

    return $retval;
}



sub eups_unsetup {

use File::Spec::Functions;
use File::Basename;

my $eups_dir = $ENV{"EUPS_DIR"};
# We don't need error checking here since that 
# is already done in eups_setup

local $indent = $indent + 1;

#Some more environment variables
$prodprefix = $ENV{"PROD_DIR_PREFIX"};
if ($prodprefix eq "") {
    print STDERR  "ERROR: PROD_DIR_PREFIX not specified\n";
    return -1;
}


# Need to extract the parameters carefully
local ($args,$outfile,$debug,$quiet) = @_;
$args =~ s/\-[a-zA-Z]  *[^ ]+//g;
@args = split " ",$args;
my($prod) = $args[0];
if ($prod eq "") {
    print STDERR  "ERROR: Product not specified\nSyntax : eups_setup unsetup <product>\n";
    return -1;
}

# Now get the information from eups_flavor
$comm = "eups_flavor -a $prod";
$comm = catfile($eups_dir,"bin",$comm);
chomp($out = `$comm`);
if ($out eq "") {
   print STDERR "ERROR running eups_flavor : $comm\n" if ($debug >= 1);
   return -1;
}
# Parse the output for the flavor and version file
my($vers,$flavor,$db) = split ":",$out;

if (($debug >= 1 && !$quiet) || $debug > 1) {
   show_product_version("Unsetting up", $indent, $prod, $vers, $flavor);
}

my $capprod = uc($prod) . "_DIR";
$prod_dir = $ENV{$capprod};
if ($prod_dir eq "") {
    print STDERR "ERROR: Environment variable $prod $capprod not set\n" if ($debug >= 1);
    return -1;
}
$ups_dir = catfile($prod_dir,"ups");

# Now construct the version file's name, then read and parse it
if ($vers eq "") {		# unknown version, so look in $ups_dir
   $table_file = catfile($ups_dir, "$prod.version");
   if (! -e $table_file) {
      $table_file = "none";
   }
} else {
   $fn = catfile($db,$prod,"$vers.version");
   if (read_version_file($fn, $prod, $flavor) < 0) {
      return -1;
   }
}

if ($table_file !~ /^none$/i && (!(-e $table_file))) {
  print STDERR "ERROR: Missing table file \"$table_file\"\n" if ($debug >= 1);
  return -1;
}

#Call the table parser here 
#The arguments are the full table path, the direction (reversed or not)
#prod_dir,ups_dir,verbosity

$fwd = 0;
return parse_table($table_file,$prod_dir,$ups_dir,$prod,$vers,$flavor,$db,$fwd,$outfile,$quiet);
}



sub eups_setup {

use File::Spec::Functions;
use File::Basename;

local $indent = $indent + 1;

#Some more environment variables
$prodprefix = $ENV{"PROD_DIR_PREFIX"};
if ($prodprefix eq "") {
    print STDERR  "ERROR: PROD_DIR_PREFIX not specified\n";
    return -1;
}

# Need to extract the parameters carefully
local ($args,$outfile,$debug,$quiet) = @_;

my $qaz = $args;
$args =~ s/\-[a-zA-Z]  *[^ ]+//g;
@args = split " ",$args;
$prod = $args[0];
# Extract version info if any
$vers = $args[1]; 
if ($prod eq "") {
    print STDERR  "ERROR: Product not specified\n";
    print STDERR "Syntax : eups_setup setup <product> [version] [-f <flavor>] [-z <database>]\n";
    return -1;
}

# Attempt an unsetup

my($SETUP_PROD) = "SETUP_".uc($prod);
if (defined($ENV{$SETUP_PROD})) {
   eups_unsetup($qaz, $outfile, $debug, 1);
}

#Determine flavor - first see if specified on command line
#else get it from the environment EUPS_FLAVOR
#We want this to propagate to subproducts
($flavor) = $qaz =~ m/\-f  *([^ ]+)/;
$flavor = $ENV{"EUPS_FLAVOR"} if ($flavor eq ""); 
if ($flavor eq "") {
    print STDERR "ERROR: No flavor specified, Use -f or set EUPS_FLAVOR\n";
    return -1;
}
$ENV{"EUPS_FLAVOR"} = $flavor; 	# propagate to sub-products

#Determine database - or get it from environment PRODUCTS
#We want this to propagate to subproducts
my $db = "";
my $db_old = "";
($db) = $qaz =~ m/\-z  *([^ ]+)/;
if ($db eq "") {
    $db = eups_find_products();
} else {
    $db_old = eups_find_products();
    $ENV{"PRODUCTS"} = $db;
}
    
if ($db eq "") {
    print STDERR "ERROR: No database specified, Use -z, -Z, or set PROD_DIR_PREFIX or PRODUCTS\n";
    return -1;
}

# Now check to see if the table file and product directory are 
# specified. If so, extract these and immediately start, else 
# complain 
$table_file = "";
$prod_dir = "";
$ups_dir = "";
($prod_dir) = $qaz =~ m/\-r  *([^ ]+)/;

if ($prod_dir eq "") {
   #Determine version - check to see if already defined, otherwise
   #determine it from current.chain
   #Also construct the full version file and check if it exists.
   if ($vers eq "") {
      $fn = catfile($db,$prod,"current.chain");
      if (-e $fn) {
	 $vers = read_chain_file($fn, $flavor);
	 
	 if ($vers eq "") {
	    print STDERR "ERROR: No version found in chain file $fn\n" if ($debug >= 1);
	    return -1;
	 }
      } else {
	 print STDERR "ERROR: chain file $fn does not exist\n" if ($debug >= 1);
	 print STDERR "FATAL ERROR: Product $prod doesn't seem to have been declared\n";
	 return -1;
      }
   }
   
   # Now construct the version file\'s name, then read and parse it
   $fn = catfile($db,$prod,"$vers.version");
   if (read_version_file($fn, $prod, $flavor) < 0) {
      return -1;
   }
} else {
    if (! -d $prod_dir) {
       warn "FATAL ERROR: directory $prod_dir doesn't exist\n";
       return -1;
    }

    $table_file = "$prod.table";
    $table_file = catfile("ups",$table_file);
    if (!($prod_dir =~ m"^/")) {
	$prod_dir = catfile($prodprefix,$prod_dir);
    }
    if (!($table_file =~ m"^/")) {
	$table_file = catfile($prod_dir,$table_file);
    }

    if ($table_file ne "" && $debug >= 1) {
       print STDERR "WARNING : Using table file $table_file\n";
    }
} 
   
if (($debug >= 1 && !$quiet) || $debug > 1) {
   show_product_version("Setting up", $indent, $prod, $vers, $flavor);
}

if ($table_file !~ /^none$/i && !(-e $table_file)) {
   print STDERR "ERROR: Missing table file $table_file\n" if ($debug >= 1);
   return -1;
}
   
#Call the table parser here 
   
$fwd = 1;
return parse_table($table_file,$prod_dir,$ups_dir,$prod,$vers,$flavor,$db,$fwd,$outfile,$quiet);
}

###############################################################################
#
# Read and parse current.chain file
#
sub read_chain_file
{
   my($fn, $flavor) = @_;

   if (!(-e $fn)) {
      print STDERR "ERROR: No version or current.chain\n" if ($debug >= 1);
      return "";
   }
   my $versinfo;
   my @size = stat($fn);
   open FILE, "<$fn";
   read FILE, $versinfo, $size[7];
   close FILE;
# Now strip out all comments
   $versinfo =~ s/\#.*\n//g;
   $versinfo =~ s/flavor/##FLAVOR/gsi;
   my @groups2 = $versinfo =~ m/#(flavor.+?)#/gsi;
# Match the last flavor
   my @groups3 = $versinfo =~ m/.*(flavor.+\Z)/gsi;
   my @group = (@groups2,@groups3);
#Now find the appropriate group
   $flavor = fix_special($flavor);
   my $pattern = "FLAVOR *= *$flavor( |\n)";
   my $pattern2 = "FLAVOR *= *ANY( |\n)";
   my $pattern3 = "FLAVOR *= *NULL( |\n)";

   my $pos = -1;
   for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
      $pos = $i if ($group[$i] =~ m/$pattern/gsi);
      $pos = $i if ($group[$i] =~ m/$pattern2/gsi);
      $pos = $i if ($group[$i] =~ m/$pattern3/gsi);
   }
   if ($pos == -1) {
      print STDERR "ERROR: Flavor $flavor not found in chain file $fn\n" if ($debug >= 1);
      return "";
   }
   ($vers) = $group[$pos] =~ m/VERSION *= *(.+?) *\n/i;

   return $vers;
}

###############################################################################
# read in the version file and start to parse it
#
sub read_version_file
{
   my($fn, $prod, $flavor) = @_;

   if (!(open FILE,"<$fn")) {
      print STDERR "ERROR: Cannot open version file $fn\n" if ($debug >= 1);
      return -1;
   }
   my @size = stat($fn);
   my $versinfo;
   
   read FILE,$versinfo,$size[7];
   close FILE;
   # Now strip out all comments
   $versinfo =~ s/\#.*\n//g;
   # Extract the groups - either defined by group-end or between two flavors
   my(@groups) = $versinfo =~ m/group:(.+?)end:/gsi;
   $versinfo =~ s/group:(.+?)end://gsi;
   $versinfo =~ s/flavor/##FLAVOR/gsi;
   @groups2 = $versinfo =~ m/#(flavor.+?)#/gsi;
   # Match the last flavor
   @groups3 = $versinfo =~ m/.*(flavor.+\Z)/gsi;
   @group = (@groups,@groups2,@groups3);

   #Now find the appropriate group
   $pos = -1;
   $flavor = fix_special($flavor);
   $pattern = "FLAVOR *= *$flavor( |\n)";
   my $pattern2 = "FLAVOR *= *ANY( |\n)";
   my $pattern3 = "FLAVOR *= *NULL( |\n)";
   for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
      $pos = $i if ($group[$i] =~ m/$pattern/gsi);
      $pos = $i if ($group[$i] =~ m/$pattern2/gsi);
      $pos = $i if ($group[$i] =~ m/$pattern3/gsi);
   }
   if ($pos == -1) {
      print STDERR "ERROR: Flavor $flavor not found in version file $fn\n" if ($debug >= 1);
      return -1;
   }

   # Now extract the prod_dir and table_file
   my($ups_dir) = "ups";
   my($table_dir) = "ups";
   ($prod_dir)  = $group[$pos] =~ m/PROD_DIR *= *(.+?) *\n/i;
   ($table_file) = $group[$pos] =~ m/TABLE_FILE *= *(.+?) *\n/i;

   if ($table_file ne "$prod.table" && $table_file !~ /^none$/i) {
      my $otable_file = $table_file;
      $table_file = "$prod.table";

      if ($debug > 1) {
	 warn "WARNING: table file name $otable_file is invalid; using $table_file\n";
      }
   }

   # Does the product directory have an environment variable set in it?
   @env = $prod_dir =~ m/\$\{(.+?)\}/g;
   for ($i = 0; $i < @env; $i++) {
      $val = $ENV{"$env[$i]"};
      $prod_dir =~ s/\$\{$env[$i]\}/$val/g;
   }
   
   if (!($prod_dir =~ m"^/")) {
      $prod_dir = catfile($prodprefix,$prod_dir);
   }
   
   if (!($ups_dir =~ m"^/")) {
      $ups_dir = catfile($prod_dir,$ups_dir);
   }
   
   if ($table_file !~ /^none$/i) {
      $table_file = catfile($ups_dir,$table_file);
   }
}

###############################################################################
#
# Try to find the PRODUCTS directory
#
sub eups_find_products {
   if (defined($ENV{"PRODUCTS"})) {
      return $ENV{"PRODUCTS"};
   } elsif (defined($ENV{PROD_DIR_PREFIX}) && -d $ENV{PROD_DIR_PREFIX} . "/ups_db") {
      return $ENV{PROD_DIR_PREFIX} . "/ups_db";
   } else {
      return "";
   }
}

###############################################################################

sub show_product_version
{
   my($str, $indent, $prod, $vers, $flavor) = @_;
   printf STDERR "%-14s %-20s  Flavor: %-10s Version: %s\n",
   sprintf("%s:", $str), sprintf("%*s%s", $indent, "", $prod) ,$flavor,
   ($vers eq "" ? "LOCAL" : $vers);
}

###############################################################################
#
# Parse arguments. Many are actually interpreted by eups_setup.pm
#
%longopts = (
	     '--database',	'-Z',
	     '--flavor',	'-f',
	     '--help',		'-h',
	     '--root',		'-r',
	     '--version',	'-V',
	     '--verbose',	'-v',
	     );

sub eups_parse_argv
{
   my($opts, $args, $words) = @_;
   
   while ($ARGV[0]) {
      if ($ARGV[0] !~ /^-/) {	# not an option
	 push(@$words, $ARGV[0]); shift @ARGV;
	 next;
      }
      
      $ropt = $opt = $ARGV[0]; shift @ARGV;
      
      if (defined($longopts{$opt})) {
	 $opt = $longopts{$opt};
      }
      
      if ($opt eq "-h") {
	 return "-h";
      } elsif (grep(/^$opt$/, keys(%$opts))) {
	 if ($$opts{$opt}) {	# require an argument
	    if (!defined($ARGV[0])) {
	       warn "You must specify a value with $ropt\n";
	       return -1;
	    }
	    $val = $ARGV[0]; shift @ARGV;
	 }
	 
	 if ($opt eq "-v") {
	    $ENV{"EUPS_DEBUG"}++;
	 } elsif ($opt eq "-n") {
	    $opts{$opt} = 1;
	 } elsif ($opt eq "-V") {
	    my($version) = &get_version();
	    warn "Version: $version\n";
	    return -1;
	 } elsif ($opt eq "-Z") {
	    $ENV{"PROD_DIR_PREFIX"} = $val;
	    if (!defined($ENV{PRODUCTS})) {
	       $ENV{"PRODUCTS"} = $ENV{"PROD_DIR_PREFIX"} . "/ups_db";
	    }
	 } else {
	    push(@$args, $opt);

	    if ($$opts{$opt}) {	# push argument too
	       push(@$args, $val);
	       $opts{$opt} = $val;
	    } else {
	       $opts{$opt} = 1;
	    }
	 }
      } else {			# unknown argument
	 warn "Unknown option: $ropt\n";
	 return -1;
      }
   }

   return \%opts;
}

###############################################################################
#
# Get version number from cvs
#
sub
get_version()
{
   my($version) = '\$Name: not supported by cvs2svn $';	# version from cvs

   if ($version =~ /^\\\$[N]ame:\s*(\S+)\s*\$$/) {
      $version = $1;
   } else {
      $version = "(NOCVS)";
   }

   return $version;
}

###############################################################################

sub eups_show_options
{
   my($opts) = @_;

   my $strings = {
       -h => "Print this help message",
       -c => "Declare this product current",
       -C => "Make this version current",
       -f => "Use this flavor (default: \$EUPS_FLAVOR)",
       -n => "Don't actually do anything",
       -m => "Use this table file (may be \"none\") (default: product.table)",
       -r => "Location of product being declared",
       -v => "Be chattier (repeat for even more chat)",
       -V => "Print version number and exit",
       -z => "Use this products database (default: \$PRODUCTS)",
       -Z => "Use this products prefix (default: \$PROD_DIR_PREFIX)",
    };

   foreach $key (keys %longopts) { # inverse of longopts table
      $rlongopts{$longopts{$key}} = $key;
   }

   warn "Options:\n";

   foreach $opt ("-h", sort {lc($a) cmp lc($b)} keys %$opts) {
      printf STDERR "\t$opt";
      if (defined($rlongopts{$opt})) {
	 printf STDERR ", %-10s", $rlongopts{$opt};
      } else {
	 printf STDERR "  %-10s", "";
      }
      printf STDERR "\t$$strings{$opt}\n";
   }
}

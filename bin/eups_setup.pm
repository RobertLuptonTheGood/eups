#!/usr/local/bin/perl
# Parser for evilups table files
# Nikhil Padmanabhan, Princeton
#
#
# Jan 22, 2002
############################

package eups_setup;
require Exporter;

our @ISA = qw(Exporter);
our @EXPORT = qw(eups_unsetup eups_setup);
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
    my $pval = $_[1];

# $pval might have leading spaces - remove these
    my ($val) = $pval =~ m/ *([^ ].*)/;
# Maybe $val is quoted
    if ($val =~ m/".*"/) {
        ($pval) = $val =~ m/"(.*)"/;
        $val = $pval;
    }

    my $delim = $_[2];
    $delim = ":" if ($delim eq "");
    $curval = $ENV{$var};
    $curval = "$curval$delim$val";
    $ENV{$var} = $curval;
}

sub envPrepend {
    our $outfile;
    my $var = $_[0];
    my $pval = $_[1];

# $pval might have leading spaces - remove these
    my ($val) = $pval =~ m/ *([^ ].*)/;
# Maybe $val is quoted
    if ($val =~ m/".*"/) {
        ($pval) = $val =~ m/"(.*)"/;
        $val = $pval;
    }

    my $delim = $_[2];
    $delim = ":" if ($delim eq "");
    $curval = $ENV{$var};
    $curval = "$val$delim$curval";
    $ENV{$val} = $curval;
}

sub envSet {
    my $var = $_[0];
    my $pval = $_[1];

# $pval might have leading spaces - remove these
    my ($val) = $pval =~ m/ *([^ ].*)/;
# Maybe $val is quoted
    if ($val =~ m/".*"/) {
        ($pval) = $val =~ m/"(.*)"/;
        $val = $pval;
    }

    $ENV{$var} = $val;
}

sub envRemove {
    my $var = $_[0];
    my $pval = $_[1];

# $pval might have leading spaces - remove these
    my ($val) = $pval =~ m/ *([^ ].*)/;
# Maybe $val is quoted
    if ($val =~ m/".*"/) {
	($pval) = $val =~ m/"(.*)"/;
	$val = $pval;
    }

    my $sval = fix_special($val);
    my $delim = $_[2];
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
pathprepend => \&envRemove,
pathremove => \&envRemove,
proddir => \&envSet,
setupenv => \&envSet,
               );

# Some local variables
    my $pos; my $i;
    my $comm; my $arg; my $qaz;


# Read in the table file
    open FILE, "<$fn";
    read FILE, $data, 1000000;
    close FILE;

    my @group = $data =~ m/group:(.+?end:)/gsi;
    $pos = -1;
    my $flavour = fix_special($flavor);
    my $pattern = "FLAVOR *= *$flavour( |\n)";
    my $pattern2 = "FLAVOR *= *ANY( |\n)";
    for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
	$pos = $i if ($group[$i] =~ m/$pattern/gsi);
	$pos = $i if ($group[$i] =~ m/$pattern2/gsi);
    }
    @group = $group[$pos] =~ m/Common:(.+?)End:/gsi;
    my $group = $group[0];
# Replace certain variables
    $group =~ s/\$\{PRODUCTS\}/$db/g;
    $group =~ s/\$\{UPS_PROD_DIR\}/$proddir/g;
    $group =~ s/\$\{UPS_PROD_FLAVOR\}/$flavor/g;
    $group =~ s/\$\{UPS_PROD_NAME\}/$prod/g;
    $group =~ s/\$\{UPS_PROD_VERSION\}/$vers/g;
    $group =~ s/\$\{UPS_UPS_DIR\}/$upsdir/g;
    
    my @lines = split "\n",$group;
    for ($i = 0;$i<@lines;$i++) {
	next if (!($lines[$i] =~ m/[a-z]+\(.*\)/i));
	($comm,$arg)=$lines[$i] =~ m/([a-z]+)\((.*)\)/i;
	my @arg = split ",",$arg;
	$comm =~ tr/[A-Z]/[a-z]/;
	if ($comm eq "setupenv") {
	    $qaz = $prod;
	    $qaz =~ tr/[a-z]/[A-Z]/;
	    $arg[0] = "SETUP_$qaz";
	    $arg[1] = "$prod $vers -f $flavor -z $db"; 
	}
	if ($comm eq "proddir") {
	    $qaz = $prod;
            $qaz =~ tr/[a-z]/[A-Z]/;
            $arg[0] = "$qaz\_DIR";
            $arg[1] = "$proddir";
	}
	if (($comm eq "setuprequired")&&($fwd==0)) {
            ($qaz) = $arg =~ m/ *"(.*)"/;
            $retval = eups_unsetup($qaz,$outfile);
	    print STDERR "ERROR : REQUIRED UNSETUP $qaz failed \n" if ($retval == -1);
	    next;
	}
        if (($comm eq "setupoptional")&&($fwd==0)) {
	    ($qaz) = $arg =~ m/ *"(.*)"/;
	    eups_unsetup($qaz,$outfile);
	    next;
        }
        if (($comm eq "setuprequired")&&($fwd==1)) {
	    ($qaz) = $arg =~ m/ *"(.*)"/;
            $retval = eups_setup($qaz,$outfile);
            print STDERR "ERROR : REQUIRED UNSETUP $qaz failed \n" if ($retval == -1);
	    next;
        }
        if (($comm eq "setupoptional")&&($fwd==1)) {
            ($qaz) = $arg =~ m/ *"(.*)"/;
            eups_setup($qaz,$outfile);
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

print STDERR "Evilups (eups_unsetup) --- by Nikhil Padmanabhan\n" if ($debug == 1);

my $eups_dir = $ENV{"EUPS_DIR"};
# We don't need error checking here since that 
# is already done in evilsetup

my $retval = 0;

$debug = $ENV{"EUPS_DEBUG"};
$debug = 0 if ($debug != 1);

#Some more environment variables
$prodprefix = $ENV{"PROD_DIR_PREFIX"};
if ($prodprefix eq "") {
    print STDERR  "ERROR : PROD_DIR_PREFIX not specified\n";
    $retval = -1;
    goto END;
}


# Need to extract the parameters carefully
my ($args,$outfile) = @_;
$args =~ s/\-[a-zA-Z] *[^ ]+//g;
@args = split " ",$args;
$prod = $args[0];
if ($prod eq "") {
    print STDERR  "ERROR : Product not specified\nSyntax : evilsetup unsetup <product>\n";
    $retval = -1;
    goto END;
}

print STDERR "Unsetting up : $prod\n";

# Now get the information from eups_flavor
$comm = "eups_flavor -a $prod";
$comm = catfile($eups_dir,"bin",$comm);
$out = `$comm`;
if ($out eq "") {
   print STDERR "ERROR running eups_flavor : $comm\n";
   $retval = -1;
   goto END;
}
# Parse the output for the flavor and version file
($vers,$flavor,$fn,$db,$temp) = split " ",$out;
print STDERR "Version: $fn\nFlavor: $flavor\n" if ($debug == 1);

# Now read in the version file and start to parse it
open FILE,"<$fn";
read FILE,$versinfo,1000000;
close FILE;
# Now strip out all comments
$versinfo =~ s/\#.*\n//g;
# Extract the groups - either defined by group-end or between two flavours
@groups = $versinfo =~ m/group:(.+?)end:/gsi;
$versinfo =~ s/group:(.+?)end://gsi;
$versinfo =~ s/flavor/##FLAVOR/gsi;
@groups2 = $versinfo =~ m/#(flavor.+?)#/gsi;
# Match the last flavor
@groups3 = $versinfo =~ m/.*(flavor.+\Z)/gsi;
@group = (@groups,@groups2,@groups3);

#Now find the appropriate group
$pos = -1;
$flavour = fix_special($flavor);
$pattern = "FLAVOR *= *$flavour( |\n)";
print STDERR "Matching pattern : $pattern\n" if ($debug==1);
for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
  $pos = $i if ($group[$i] =~ m/$pattern/gsi); 
}
if ($pos == -1) {
    print STDERR "ERROR: Flavor $flavor not found in version file $fn\n";
    $retval = -1;
    goto END;
}
print STDERR "FLAVOR:$flavor\n$group[$pos]\n" if ($debug==1);

# Now extract the prod_dir, ups_dir, table_dir and table_file
($prod_dir)  = $group[$pos] =~ m/PROD_DIR *= *(.+?) *\n/i;
($ups_dir) = $group[$pos] =~ m/UPS_DIR *= *(.+?) *\n/i;
($table_dir) = $group[$pos] =~ m/TABLE_DIR *= *({^ ,.}+?) *\n/i;
($table_file) = $group[$pos] =~ m/TABLE_FILE *= *(.+?) *\n/i;
# Check for a few things 
$table_file = "$vers.table" if ($table_file eq "");
$table_dir = dirname($fn) if ($table_dir eq "");
$table_file = catfile($table_dir,$table_file);
# Does the product directory have an environment variable set in it
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
#If the table file is not in the directory, search in new directory...
if (!(-e $table_file)) {
    $table_file = basename($table_file);
    $table_file = catfile($ups_dir,$table_file);
}
if (!(-e $table_file)) {
  print STDERR "ERROR: Missing table file $table_file\n";
  $retval=-1;
  goto END;
}

print STDERR "PROD_DIR:$prod_dir\n" if ($debug==1);
print STDERR "UPS_DIR:$ups_dir\n" if ($debug==1);
print STDERR "TABLE_DIR:$table_dir\n" if ($debug==1);
print STDERR "TABLE_FILE:$table_file\n" if ($debug==1);

#Call the table parser here 
#The arguments are the full table path, the direction (reversed or not)
#prod_dir,ups_dir,verbosity

$fwd = 0;
$retval = parse_table($table_file,$prod_dir,$ups_dir,$prod,$vers,$flavor,$db,$fwd,$outfile);

print STDERR "(eups_unsetup) exiting......\n" if ($debug == 1);

END:

return $retval;
}



sub eups_setup {

use File::Spec::Functions;
use File::Basename;

print STDERR "Evilups (eups_setup) --- by Nikhil Padmanabhan\n" if ($debug == 1);

my $retval = 0;

$debug = $ENV{"EUPS_DEBUG"};
$debug = 0 if ($debug != 1);

#Some more environment variables
$prodprefix = $ENV{"PROD_DIR_PREFIX"};
if ($prodprefix eq "") {
    print STDERR  "ERROR : PROD_DIR_PREFIX not specified\n";
    $retval = -1;
    goto END;
}


# Need to extract the parameters carefully
my ($args,$outfile) = @_;
my $qaz = $args;
$args =~ s/\-[a-zA-Z] *[^ ]+//g;
@args = split " ",$args;
$prod = $args[0];
# Extract version info if any
$vers = $args[1]; 
if ($prod eq "") {
    print STDERR  "ERROR : Product not specified\n";
    print STDERR "Syntax : evilsetup setup <product> [version] [-f <flavor>] [-z <database>]\n";
    $retval = -1;
    goto END;
}

print STDERR "Setting up : $prod\n";

#Determine flavour - first see if specified on command line
#else get it from the environment EUPS_FLAVOR
($flavor) = $qaz =~ m/\-f *([^ ]+)/;
$flavor = $ENV{"EUPS_FLAVOR"} if ($flavor eq ""); 
if ($flavor eq "") {
    print STDERR "ERROR : No flavor specified, Use -f or set EUPS_FLAVOR\n";
    $retval = -1;
    goto END;
}

#Determine database - or get it from environment PRODUCTS
($db) = $qaz =~ m/\-z *([^ ]+)/;
$db = $ENV{"PRODUCTS"} if ($db eq "");
if ($db eq "") {
    print STDERR "ERROR : No database specified, Use -z or set PRODUCTS\n";
    $retval = -1;
    goto END;
}

#Determine version - check to see if already defined, otherwise
#determine it from current.chain
#Also construct the full version file and check if it exists.
if ($vers eq "") {
    $fn = catfile($db,$prod,"current.chain");
    if (!(-e $fn)) {
	print STDERR "ERROR : No version or current.chain\n";
	$retval = -1;
	goto END;
    }
    open FILE, "<$fn";
    read FILE, $versinfo, 1000000;
    close FILE;
# Now strip out all comments
    $versinfo =~ s/\#.*\n//g;
    $versinfo =~ s/flavor/##FLAVOR/gsi;
    @groups2 = $versinfo =~ m/#(flavor.+?)#/gsi;
# Match the last flavor
    @groups3 = $versinfo =~ m/.*(flavor.+\Z)/gsi;
    @group = (@groups2,@groups3);
#Now find the appropriate group
    $pos = -1;
    $flavour = fix_special($flavor);
    $pattern = "FLAVOR *= *$flavour( |\n)";
    print STDERR "Matching pattern : $pattern\n" if ($debug==1);
    for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
	$pos = $i if ($group[$i] =~ m/$pattern/gsi);
    }
    if ($pos == -1) {
	print STDERR "ERROR: Flavor $flavor not found in chain file $fn\n";
	$retval = -1;
	goto END;
    }
    ($vers) = $group[$pos] =~ m/VERSION *= *(.+?) *\n/i;
    if ($vers eq "") {
        print STDERR "ERROR: No version found in chain file $fn\n";
        $retval = -1;
        goto END;
    }
}
# Now construct the filename
$fn = catfile($db,$prod,"$vers.version");
print STDERR "Version: $fn\nFlavor: $flavor\n" if ($debug == 1);

# Now read in the version file and start to parse it
if (!(open FILE,"<$fn")) {
    print STDERR "ERROR: Cannot open version file $fn\n";
    $retval = -1;
    goto END;
}
read FILE,$versinfo,1000000;
close FILE;
# Now strip out all comments
$versinfo =~ s/\#.*\n//g;
# Extract the groups - either defined by group-end or between two flavours
@groups = $versinfo =~ m/group:(.+?)end:/gsi;
$versinfo =~ s/group:(.+?)end://gsi;
$versinfo =~ s/flavor/##FLAVOR/gsi;
@groups2 = $versinfo =~ m/#(flavor.+?)#/gsi;
# Match the last flavor
@groups3 = $versinfo =~ m/.*(flavor.+\Z)/gsi;
@group = (@groups,@groups2,@groups3);

#Now find the appropriate group
$pos = -1;
$flavour = fix_special($flavor);
$pattern = "FLAVOR *= *$flavour( |\n)";
print STDERR "Matching pattern : $pattern\n" if ($debug==1);
for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
  $pos = $i if ($group[$i] =~ m/$pattern/gsi); 
}
if ($pos == -1) {
    print STDERR "ERROR: Flavor $flavor not found in version file $fn\n";
    $retval = -1;
    goto END;
}
print STDERR "FLAVOR:$flavor\n$group[$pos]\n" if ($debug==1);

# Now extract the prod_dir, ups_dir, table_dir and table_file
($prod_dir)  = $group[$pos] =~ m/PROD_DIR *= *(.+?) *\n/i;
($ups_dir) = $group[$pos] =~ m/UPS_DIR *= *(.+?) *\n/i;
($table_dir) = $group[$pos] =~ m/TABLE_DIR *= *({^ ,.}+?) *\n/i;
($table_file) = $group[$pos] =~ m/TABLE_FILE *= *(.+?) *\n/i;
# Check for a few things 
$table_file = "$vers.table" if ($table_file eq "");
$table_dir = dirname($fn) if ($table_dir eq "");
$table_file = catfile($table_dir,$table_file);
# Does the product directory have an environment variable set in it
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
#If the table file is not in the directory, search in new directory...
if (!(-e $table_file)) {
    $table_file = basename($table_file);
    $table_file = catfile($ups_dir,$table_file);
}
if (!(-e $table_file)) {
  print STDERR "ERROR: Missing table file $table_file\n";
  $retval=-1;
  goto END;
}

print STDERR "PROD_DIR:$prod_dir\n" if ($debug==1);
print STDERR "UPS_DIR:$ups_dir\n" if ($debug==1);
print STDERR "TABLE_DIR:$table_dir\n" if ($debug==1);
print STDERR "TABLE_FILE:$table_file\n" if ($debug==1);

#Call the table parser here 
#The arguments are the full table path, the direction (reversed or not)
#prod_dir,ups_dir,verbosity

$fwd = 1;
$retval = parse_table($table_file,$prod_dir,$ups_dir,$prod,$vers,$flavor,$db,$fwd,$outfile);

print STDERR "(eups_setup) exiting......\n" if ($debug == 1);

END:

return $retval;
}





#!/usr/bin/perl

use strict;

while (<STDIN>) {
    chomp;
    my ($registry, $cc, $type, $start, $value, undef, $status) = split(/\|/);

    unless ($type eq 'ipv4' && ($status eq 'allocated' || $status eq 'assigned')) { next; }
    #unless ($cc eq 'JP') { next; }

    my $SubnetMaskBin = sprintf('%b', scalar($value));
    if ($SubnetMaskBin !~ /^1(0+)$/) {
        next;
    }
    my $prefix = 32 - length($1);

    my $num;
    $num = ($num << 8) + $_ foreach (split(/\./, $start));

    if (($num % $value) != 0) {
        next;
    }
    print $start.'/'.$prefix."\t".$cc."\n";
}

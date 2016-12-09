#!/bin/bash
##############################################################################################################
# Takes either an item or the name of a file on command line then outputs the test data for a sortmatrix emulation
# January 13, 2016
# Andrew Nisbet
##############################################################################################################
if [ $1 ]
then
	if [ -s "$1" ]
	then
		cat "$1" |  selitem -iB -oNBlyt 2>/dev/null | selcallnum -iN -oSA 2>/dev/null
	else
		echo "$1" |  selitem -iB -oNBlyt 2>/dev/null | selcallnum -iN -oSA 2>/dev/null
	fi
else
	printf "usage: $0 [file|item_id]\n"
	exit 1
fi

#!/usr/bin/env python
####################################################
#
# Python source for project sorteremu_py
#
# tests and emulates 3M sort matrices.
#    Copyright (C) 2015  Andrew Nisbet
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.
#
# Author:  Andrew Nisbet, Edmonton Public Library
# Created: Fri Dec 18 10:23:18 MST 2015
# Rev:
#          1.0.01 - Fix to report items that fall into exception bin (eg no match).
#          0.0 - Dev.
#
####################################################
import sys
import getopt
import os
import re
from itertools import product # Produces product of vector of rules for analysis

version = '1.0.01'

# A rule is a object that encapsulates a single AND operation, so represents data from a single column within
# a configuration file. If a rule is provided as a string it is assumed to be either a single rule or a rule set
# Where different values are permitted if separated by a ',' and optional space. In either case the rule is stored
# and query-able.
# Accepts either a string with optional ',', or a list.
class Rule:
    def __init__(self, rules):
        # parse the rules depending on the type of input. String or list.
        self.rule = []
        assert isinstance(rules, list)
        for rule in rules:
            print rule


# Rule engine reads and stores rules, then tests can be run against arbitrary items.
# Input must have the following structure: 'item_id|home_location|destination_library|item_type|call_number (range)|'
# produced with echo 31221115689585 | selitem -iB -oNBlyt | selcallnum -iN -oSA
# Produces: '31221115689585  |PBKMYS|EPLSTR|BOOK|870.44|'
#  0 - Sort Route
#  1 - Alert
#  2 - AlertType
#  3 - Magnetic Media
#  4 - Media Type
#  5 - Permanent Location
#  6 - Destination Location
#  7 - Collection Code
#  8 - Call Number
#  9 - Sort Bin	Branch ID
# 10 - Library ID
# 11 - Check-in Result
# 12 - Custom Tag Data
# 13 - Detection Source
# R5	*	*	*	*	NONFICTION, REFERENCE	*	BOOK, JBOOK, PBK, PAPERBACK	7*,8*,9*	*	*	*	*
# This script is based on the common rules I have seen on our sorters. That is we don't use position 1,2,3, or 4
# but commonly use 5, 7, and 8. If you add additional rules in 1,2,3,4 or after 8, you can and they will be checked
# but the script will fail if you don't add positional matching data in your input.
#
# Rule engine can read configs specified from text files that have raw screen scraping from the configuration web page.
# TODO: add a switch to specify a URL so the app can scrape the config itself.
class RuleEngine:
    def __init__(self):
        self.MIN_COLS = 9
        self.rule_table = []
        self.rule_column_names = [ 'SortRoute', 'Alert', 'AlertType', 'MagneticMedia', 'MediaType',
                              'PermanentLocation', 'DestinationLocation', 'CollectionCode',
                              'CallNumber', 'SortBin', 'BranchID', 'LibraryID', 'CheckinResult',
                              'CustomTagData', 'DetectionSource' ]

    # Tests for duplicate rule entries.
    def test_duplicates(self, explain=False):
        # Create a hash map into which we put keys made of the strings
        # of all combinations of rules on a given line,  and-ed together.
        # Once done, if the key appears twice it is has an identical twin.
        count = 0
        master_rule_map = {}
        # for item_entry in self.rule_table:
        for line in self.rule_table:
            my_item_list = []
            rule_name = line.pop(0)
            for item_entry in line:
                if item_entry[0] == '*':
                    continue
                elif item_entry.find(','):
                    my_item_list.append(item_entry.split(','))
                else:
                    my_item_list.append(item_entry)
            # Now create a string for each rule that is a concatenation of all the and'ed rules for this line.
            for item_entry in list(product(*my_item_list)):
                rule_string = ''
                for item in item_entry:
                    rule_string += item + '.'
                count += 1
                # Chop off the trailing '.' for cleaner display
                rule_string = rule_string[:-1]
                if explain:
                    sys.stdout.write("{0}) {1}::".format(count, rule_name))
                    sys.stdout.write("{0}\n".format(rule_string))
                # Add each new name as a key into a hashmap with the rule name as the value.
                if master_rule_map.has_key(rule_string):
                    sys.stdout.write("** Warning duplicate rule detected in rule {0} and {1}->{2}\n".format(master_rule_map[rule_string], rule_name, rule_string.split('.')))
                else:
                    master_rule_map[rule_string] = rule_name
            # Put the route name back on the list for reference later during item check.
            line.insert(0, rule_name)

    # Loads a rule from the config file, adjusting to 2 different types of formatting. The config file can be created
    # by hand separating the columns with pipes, but that got boring so the method can also parse values that are cut
    # and paste from the sorter's configuration web page. No extra editing required. See parse_screen_scrape_config().
    def load_rule(self, rule_line):
        this_line_list = rule_line.split('|')
        # No pipes means the input is probably screen-scraped from the configuration web page.
        if len(this_line_list) == 1:
            this_line_list = self.parse_screen_scrape_config(rule_line)
        this_line_list[-1] = str.strip(this_line_list[-1])
        if this_line_list[-1] == '':
            this_line_list[-1] = '*'
        for i in range(len(this_line_list), len(self.rule_column_names)): # pad remaining fields with stars
            this_line_list.insert(i, '*')
        # sys.stdout.write("padded rule::{0}\n".format(this_line_list))
        if len(this_line_list) >= self.MIN_COLS:
            new_list = []
            for col in this_line_list:
                if col != '\n': # Sometimes Symphony users will include a trailing '|' which will cause and empty field.
                    new_list.append(col)
            self.rule_table.append(new_list)
            # sys.stdout.write("****{0}\n".format(new_list))
        else:
            sys.stderr.write('** "{0}" not enough rules, ignoring.'.format(rule_line))
            sys.stderr.write('** expected {0}, but got {1}.'.format(self.MIN_COLS, len(this_line)))

    # Sometimes you want to set up a config file based on what the settings are on the target machine.
    # If you go into the sorter configuration you can copy and paste the contents of the config HTML page
    # into a text file. This script will clean it up and add the rules.
    # REJECT	Y	01	*	*	*	*	*	*	*	*	*	*	*	*
    # Submit	 	Submit	Submit	REJECT	Y	02	*	*	*	*	*	*	*	*	*	*	*	*
    # Submit	 	Submit	Submit	REJECT	Y	03	*	*	*	*	*	*	*	*	*	*	*	*
    # Submit	 	Submit	Submit	R2	*	*	*	*	*	*	CD, DVD*, JCD, VIDGAME, BLU-RAY*	*	*	*	*	*	*	*
    # Submit	 	Submit	Submit	R5	*	*	*	*	*	EPLCLV	PERIODICAL	*	*	*	*	*	*	*
    # Submit	 	Submit	Submit	R6	*	*	*	*	*	EPLCLV	JPERIODICL	*	*	*	*	*	*	*
    # Submit	 	Submit	Submit	R1	*	*	*	*	TEENFIC, TEENGRAPHC, TPBK, TPBKSER, EASYENGL	*	JBOOK, JPBK, BOOK	*	*	*	*	*	*	*
    # Submit	 	Submit	Submit	R4	*	*	*	*	ABORIGINAL, JUVPIC, JPBK, JUVNONF, JUVOTHLANG, NONFICTION, YRCA	*	JPBK, JPAPERBACK, JBOOK, JOTHLANGBK	*	*	*	*	*	*	*
    # Submit	 	Submit	Submit	R6	*	*	*	*	EMOVIE, JUV*, COMICBOOK	*	JBOOK, JDVD*, JBLU-RAY*, JPBK, COMIC	*	*	*	*	*	*	*
    # Submit	 	Submit	Submit	R1	*	*	*	*	*	*	OTHLANGBK	*	*	*	*	*	*	*
    # Submit	 	Submit	Submit	R3	*	*	*	*	GENERAL, FIC*, PBK*, LARGE*	*	BOOK, LARGEPRINT, PBK, PAPERBACK	*	*	*	*	*	*	*
    # Submit	 	Submit	Submit	R5	*	*	*	*	*	*	BOOK, MUSICSCORE, PAPERBACK	*	*	*	*	*	*	*
    def parse_screen_scrape_config(self, line_of_rules):
        new_line = str.replace(line_of_rules, 'Submit', '')
        new_line = str.strip(new_line)
        new_line = str.replace(new_line, ', ', ',')
        # Sometimes people put extra space between the rule and comma.
        new_line = str.replace(new_line, ' ,', ',')
        new_line = re.sub(r'\s+', '|', new_line)
        new_line_list = new_line.split('|')
        # now remove the space after commas
        # sys.stdout.write('Here is my cols:"{0}"\n'.format(new_line_list))
        return new_line_list

    # Displays all the rules in order.
    def show_rules(self):
        for rule in self.rule_table:
            sys.stdout.write("{0}".format(rule))

    # Tests that longer rules appear before shorter rules, since longer rules require stricter adherence, there is
    # more chance that more lax rules will fire before them, generally speaking.
    # param:  optional boolean value explain.
    # return: True if the rules are ordered longest to shortest and False otherwise.
    def is_check_rule_order(self, explain=True):
        # Go through each rule and count how many have more than just a '*'. The higher the count the more complex
        # the rule, the further up the matrix it goes. The one exception is ruels that fire alerts should come first.
        is_ordered = True
        line_no = 0
        current_rank = 15
        for line in self.rule_table:
            rank = -1 # The rule name will trigger a rank of '0'.
            line_no += 1
            # Holds for ILL, this or that library should come first.
            if line[1] != '*':
                rank = len(self.rule_column_names) # set to maximum so they should appear first.
            else:
                for column in line:
                    if len(column) > 1:
                        rank += 1
            if rank > current_rank:
                is_ordered = False
                sys.stdout.write('** Warning line #{0}:({1}) has {2} comparisons and should move above lines with {3}.\n'.format(line_no, line[0], rank, rank -1))
            else:
                current_rank = rank
        return is_ordered

    # Checks the rules for errors and possible optimizations.
    # Each rule has a number of qualifiers that must match for the rule to fire. If a rule has fewer qualifiers
    # but appears first, it will fire before a rule with more details, negating the need for the additional complexity.
    # If we arrange each rule in a tree so that every combination of rule is computed we can find mis-ordered rules
    # (redundant) and conflicting rules (repeated).
    # Redundant example:
    # BOOK|*|*|
    # BOOK|*|9*| - never fires because simpler rule takes precedence.
    # Conflicting example:
    # CD,DVD*|*|*|
    # DVD21,JCD,JDVD|*|*| - DVD21 never fires because DVD* matches first.
    # If we put these rules into lists like so:
    # [BOOK]
    # [BOOK, 9]
    # we can see that the simpler rule will fire first since there are more matches that must be met within the.
    # In the second case we search similar rules by cherry picking the '*' candidates and determine if there are rules
    # that follow the current rule that are more refined.
    # grep DVD* in [DVD21,JCD,JDVD]
    def test_rules(self, explain=False):
        # now we want to expand all the lists within a line so that each member creates a new list.
        sys.stdout.write('testing bins.\n')
        self.check_bins(explain)
        sys.stdout.write('done.\n')
        sys.stdout.write('testing for redundant rules.\n')
        self.test_duplicates(explain)
        sys.stdout.write('done.\n')
        sys.stdout.write('rule order: \n')
        if self.is_check_rule_order(explain):
            sys.stdout.write('pass.\n')

    # Checks if all the bins are utilized.
    def check_bins(self, explain=False):
        bins = []
        for i in range(0, len(self.rule_table)):
            # Snag the bin number and put in an array then sort.
            my_bin_name = self.rule_table[i][0]
            if my_bin_name == 'REJECT' or my_bin_name == 'reject':
                sys.stdout.write('* WARNING: sort route #{0} is set up to reject materials.\n'.format(i + 1))
            bins.append(my_bin_name)
        # now produce a histogram of rules for each bin.
        bin_dict = {}
        for bin in bins:
            try:
                bin_dict[bin] += 1
            except KeyError:
                bin_dict[bin] = 1
        sys.stdout.write('found {0} bins with routing rules.\n'.format(len(bin_dict.keys())))
        bin_key_list = bin_dict.keys()
        bin_key_list.sort()
        for name in bin_key_list:
            sys.stdout.write('bin #{0} has {1} rules.\n'.format(name, bin_dict[name]))

    # Tests an items data from the ILS and returns a list of the [ item_id, is_match, rule# ]
    # param:  single rule line from the matrix.
    # param:  item data read from the item file.
    # pamam:  boolean value True will show where the rule fails, False returns quietly.
    # return: list of the [ 31221012345678, True, R6 ]
    def is_rule_match(self, rule, item_line, show_fail=True):
        line_items = item_line.split('|')
        # sys.stdout.write('>>>>item cols:{0}\n>>>>rule cols:{1}.\n'.format(line_items, rule))
        if len(line_items) != len(rule):
            sys.stdout.write('columns don\'t match item cols:{0}, rule cols:{1}.\n'.format(len(line_items), len(rule)))
            sys.exit(1)
        # Since we do a side by side comparison of config columns to item columns
        # we need to ensure that the item_line has the same number of columns.
        # The data arrives from
        # columns of input must match rule columns, and each value
        # within the data column must match at least one rule specified
        # in the rule columns for the test to succeed.
        # the bin number and in the input its the item id.
        match_count = 1 # the first col of a rule and of the item don't have to match.
        matched_rules = []
        for index in range(1, len(line_items)):
            regexes = rule[index].split(',') # regexes can look like BOOK,PBK*
            test_col = line_items[index]
            no_match_count = 0
            for reg in regexes:
                regex = str.strip(reg)
                regex = str.replace(regex,'*','')
                if show_fail:
                    sys.stdout.write('"{0}" <=> "{1}", '.format(reg, test_col))
                # If the regex is empty, it matches anything.
                # It can be empty because we remove the '*' because of python 'bug'.
                if len(regex) == 0: # That was a star so everything automatically matches.
                    if show_fail:
                        sys.stdout.write(' Auto-MATCH.\n')
                    break
                elif test_col == '*': # and len(regex) > 0 because previous if failed.
                    if show_fail:
                        sys.stdout.write(' NO-MATCH.\n')
                    break # It doesn't matter what the rule wants we don't have enough information to test.
                elif test_col.startswith(regex):
                    if show_fail:
                        sys.stdout.write(' MATCHES\n'.format(test_col, regex))
                    matched_rules.append(regex)
                    break
                no_match_count += 1
                # if we got here none of the listed rules in this column matched our items data.
                if no_match_count == len(regexes):
                    return [line_items[0], False, rule[0], matched_rules]
                if show_fail:
                    sys.stdout.write(" skip...\n")
            index += 1
        # line_items.insert(0, item_id)
        return [line_items[0], len(matched_rules) > 0, rule[0], matched_rules]

    # Tests an item against the matrix, reports which bin it gets sent to and why.
    # Input must have the following structure: 'item_id|home_location|destination_library|item_type|call_number (range)|'
    # produced with echo 31221115689585 | selitem -iB -oNBlyt | selcallnum -iN -oSA
    # 31221115689585  |PBKMYS|EPLLHL|PBK|MYSTERY B TRADEPBK|
    # Which gets expanded to include extra '*' characters standing in for config settings we don't normally use.
    # '31221115689585  |PBKMYS|EPLSTR|BOOK|870.44|'
    def test_item(self, item, explain=True):
        # the rules must match top down
        my_item = str.strip(item)
        if my_item.endswith('|'):
            my_item = my_item[:-1]
        item_columns = my_item.split('|')
        # The script just works on the general case of assuming there are no holds for these items, to see where
        # they would theoretically fall into.
        # sys.stdout.write('item_array:{0}\n'.format(item_columns))
        for i in range(1, len(self.rule_column_names)): # instead of sort route we have an item id.
            if i < 5: # put stars in the following positions to match rule columns.
                item_columns.insert(i, '*')
            if i > 8:
                item_columns.append('*')
        # Convert back to string
        item_string = '|'.join(item_columns)
        # Test print item with complete columns.
        if explain:
            sys.stdout.write('item_string:{0}\n'.format(item_string))
        rule_index = 1
        rule_match = False
        for rule in self.rule_table:
            # TODO: fix so we can optionally handle material with holds.
            # This skips the first three special rules for handling materials with holds. Just look at the general case
            # for a given item.
            if rule[1] == 'Y' or rule[1] == 'N':
                rule_index += 1
                continue
            result = self.is_rule_match(rule, item_string, explain)
            # result = self.is_rule_match(rule, item_string)
            if result[1]:
                sys.stdout.write("{0}->bin {3} ({2}, line {1}) matches on {4}".format(item_columns[0], rule_index, result[2], result[2][1:], result[3]))
                if explain:
                    sys.stdout.write(", matched on rule '{0}'.\n".format(result[3]))
                else:
                    sys.stdout.write("\n")
                rule_match = True
                break
            rule_index += 1
        if not rule_match:
            sys.stdout.write("line --: {0}->bin E (R-) no rule matches.\n".format(item_columns[0]))


def usage():
    sys.stdout.write('usage: python sortemu.py [-i<items>] -c[config.file] -e.\n')
    sys.stdout.write('  Written by Andrew Nisbet for Edmonton Public Library (c) (2016).\n')
    sys.stdout.write('  See the source header for licensing restrictions.\n')
    sys.stdout.write('  Version: {0}\n'.format(version))


# Take valid command line arguments -b'n', -o, -i, -d, and -h -s.
def main(argv):
    config_file = ''
    items_file = ''
    explain = False
    try:
        opts, args = getopt.getopt(argv, "c:ei:", ["config=", "items="])
    except getopt.GetoptError:
        usage()
        sys.exit()
    for opt, arg in opts:
        if opt in ("-c", "--config"):
            assert isinstance(arg, str)
            config_file = arg
        elif opt in ("-i", "--items"):
            assert isinstance(arg, str)
            items_file = arg
        elif opt in "-e":
            explain = True

    sys.stdout.write('configuration file is "{0}"\n'.format(config_file))
    sys.stdout.write('running file "{0}"\n'.format(items_file))
    if not os.path.isfile(config_file):
        sys.stderr.write("** error: configuration file {0} does not exist.\n".format(config_file))
        sys.exit()
    if items_file and not os.path.isfile(items_file):
        sys.stderr.write("** error: item(s) file {0} does not exist.\n".format(items_file))
        sys.exit()
    rule_engine = RuleEngine()
    c_file = open(config_file, 'r')
    for line in c_file:
        rule_engine.load_rule(line)
    c_file.close()
    # Now you can check rules if you like
    # rule_engine.check_rules(explain)
    rule_engine.test_rules(explain)
    if items_file:
        i_file = open(items_file, 'r')
        for item in i_file:
            rule_engine.test_item(item, explain)
        i_file.close()

    sys.exit(0)

if __name__ == "__main__":
    # import doctest
    # doctest.testmod()
    main(sys.argv[1:])
    # EOF

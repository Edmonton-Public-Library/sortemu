#!/usr/bin/env python

#######################################################################################################################
# Compile a sort matrix.
# Requires all ILS locations and iTypes combinations with counts.
#
# selitem -olt | pipe.pl -dc0,c1 -A -P -TCSV_UTF-8:"Count,Loc,iTyp"
#
# With this staff can order the list by counts and add their preferred bin
# number to the 'Bin #' column. Rare loc/itype combinations can be ignored
# and will end up in the exception bin.
#
# The way to do this by hand is to filter on bin number then order by either
# location or iType. Take the locations for a specific bin, dedup the list
# and prune unwanted locations like DISCARD and ON-ORDER.
#
# Look for commonly prefixed names like FICGENERAL, FICSCIENCE,FICMYSTERY
# and replace them with FIC*.
#
# Repeat for iTypes, and once done order by most specific or comprehensive
# rule, followed by most general rules.
#
# Staff may choose to identify materials to go to the exception bin, but
# these can be ignored.
#
# TODO: 2 Add a default rule before any single column rule for DAMAGE,MISSING,DISCARD,*ORDER,BINDERY,UNKNOWN,NOF.
#  better yet read these from a different sheet along with ILL and hold rules.
# TODO: Add optional default sort routes for holds for other libraries.
# TODO: Compile rules into optimized format.
# TODO: Export 3CS file as XML
#  and allow user to write proposed matrix back to the spread sheet.
#######################################################################################################################
import xlrd
import sys
import argparse
import re
import os
import declxml as xml

# Reads in a standard XSLS spreadsheet and displays the entire contents in JSON.
from typing import Dict


# ConfigGenerator builds an optimized configuration file based on staff recommendations provided in a simple
# MicroSoft spread sheet. The first sheet should contain four columns. The second and third column must contain
# a location and item type for a group for an arbitrary but specific group of items. For example a common item
# in any public library catalog would be comic books, which may have a location of TEENFIC and
# item type of COMICBOOK. In this case column 2 would have an entry of TEENFIC and column 3, COMICBOOK. The forth
# column would contain the bin number to sort into.
# The first column should contain the count of items in this category of the catalog. This gives a clue about where
# staff can focus attention when defining sortation rules. The application produces a summary report that outlines
# how much material can be expected to end up unsorted, and so adjustments can be made.
#
# Example:
#  Count | Location | Item Type | Bin
#  1250  | TEENFIC  | COMICBOOK | 2
#  ...
#
#  The above can be created on a Symphony system with API as follows.
#  <pre>selitem -olt | pipe.pl -dc0,c1 -A -P | pipe.pl -TCSV_UTF-8:"count,loc,iType,bin >staff.csv</pre>
#  then the csv file opened and saved in MS office, Open Office or what have you. The XLS file should be saved as
#  Excel 2007 XSLS file type.
class ConfigGenerator:

    # The constructor requires a file name (with path) to the XSLS file.
    # The XSLS configuration file must include a header row. The names read there are the index to the dictionaries.
    # param:  sheet_index the zero-based index to the sheet to read. Default: 0.
    # param:  debug - output additional information. Default: False.
    def __init__(self, file, index=0):
        # The fewest number of bins permissible on any sorter real or fictional.
        self.MIN_BINS = 3
        self.COL_NAME: Dict[str, int] = {'count': 0, 'location': 1, 'type': 2, 'callnum': 3, 'bin': 4}
        # TODO: Check the alert types are correct.
        self.HOLD_TYPE: Dict[str, int] = {'ill': 3, 'branch': 2, 'hold': 1}
        # You may want to add or change this list.
        self.BAD_LOCATIONS = ["DISCARD", "MISSING", "STOLEN", "ON-ORDER", "NOF", "BINDERY", "UNKNOWN"]
        self.BAD_TYPES = []
        # Keep count of the number of items in BAD_LOCATIONS so we can make a rule to catch them by default.
        self.rejected_item_count = 0
        # The master matrix as an array (or List) of named rules. Their order matters. The smaller the index of
        # the rule, the sooner the rule is used for testing materials.
        self.matrix = []
        self.header_row = []  # The row where we stock the name of the column
        self.all_count_locn_type_cnum_binnum = []
        self.handled_by_rule_count = 0
        self.unhandled_rule = []
        self.unhandled_items_count = 0
        self.bins = {}
        # These are computed to ensure all rules are accounted for and well-formed.
        self.highest_identified_bin = 0
        self.exception_bin = 0
        self.last_bin = 0
        self.malformed_rule_name_row = {}
        self.malformed_rule_item_count = 0

        # Ignore what the columns are called and use the names defined in self.col_name.
        workbook = xlrd.open_workbook(file)
        worksheet = workbook.sheet_by_index(index)
        for column_name, col_index in self.COL_NAME.items():
            self.header_row.append(column_name)
        # transform the staff_selection_workbook to a list of dictionies, building them up from the spread sheet
        # row-by-row.
        for row in range(1, worksheet.nrows):
            count_loc_typ_callnum_bin = {}
            item_count: int = 0
            for column_name, col_index in self.COL_NAME.items():
                count_loc_typ_callnum_bin[self.header_row[col_index]] = worksheet.cell_value(row, col_index)
            # See if the location is one of the BAD_LOCATIONS keep a count and don't add it to any rule
            # Count the number of rules specified for each bin. We'll use this for reporting and for computing
            # which bin is the exception bin if one isn't specifically added in the column.
            # But check if staff put text in the 'Bin #' column instead of an actual bin number. Sheesh.
            # If the number format hasn't been set to integer in the spreadsheet coerce it now.
            item_count = self._get_integer_(count_loc_typ_callnum_bin['count'])
            if count_loc_typ_callnum_bin['type'] in self.BAD_TYPES:
                # TODO: Add switch so users can specify bad types, and code to add a bad item type rule.
                self.rejected_item_count += item_count
                # Carry on to the next line in the spread sheet without further processing. Stops bad types
                # ending up in the matrix. They are added explicitly later.
                continue
            if count_loc_typ_callnum_bin['location'] in self.BAD_LOCATIONS:
                self.rejected_item_count += item_count
                # Carry on to the next line in the spread sheet without further processing. Stops bad locations
                # ending up in the matrix. They are added explicitly later.
                continue
            # If staff didn't identify a bin for this combo ignore it.
            if count_loc_typ_callnum_bin['bin'] != '':
                try:
                    my_bin_key: int = round(count_loc_typ_callnum_bin['bin'], None)
                except ValueError:
                    # Since we couldn't make the entry an integer, issue a warning to staff to fix it.
                    if count_loc_typ_callnum_bin['bin'].upper() == "REJECT":
                        # TODO: We don't know what the reject bin is at this point but should handle these somehow later.
                        pass
                    else:
                        if debug:  # These get reported in the report.
                            sys.stdout.write(" **WARN: invalid bin assignment '{}' on spread sheet row {}.\n".format(
                                count_loc_typ_callnum_bin['bin'], row + 1))
                        self.malformed_rule_name_row[count_loc_typ_callnum_bin['bin']] = row + 1
                        self.malformed_rule_item_count += item_count
                        continue
                if my_bin_key in self.bins:
                    self.bins[my_bin_key] += 1
                else:
                    self.bins[my_bin_key] = 1
                self.all_count_locn_type_cnum_binnum.append(count_loc_typ_callnum_bin)
                # Add the count of items from the first column to the total.
                self.handled_by_rule_count += item_count
            else:# The bin isn't specified so they these items are inferred to be going to exception.
                # Do these rules have any use? Is it just the counts we need?
                self.unhandled_rule.append(count_loc_typ_callnum_bin)
                self.unhandled_items_count += item_count
        if self._is_well_formed_(self.bins):
            self._compile_rules_(self.all_count_locn_type_cnum_binnum)
            # Add the default rule for unknown items to the new matrix, it will ensure there is at least one rule
            # on the matrix when we loop through for comparison. If you remove it, you will have to check if the
            # new_matrix has any items or the loop below will fail the first test and nothing will be added.
            if self.rejected_item_count > 0:
                bad_locn_rule = {"R{}".format(self.exception_bin): dict(location=self.BAD_LOCATIONS, type=['*'],
                                                                        callnum=['*'],
                                                                        affected=self.rejected_item_count)}
                self.matrix.append(bad_locn_rule)
            self._order_rules_()
            self._compress_rules_()
            self._tidy_()
        else:
            sys.stdout.write("There are errors in the spread sheet. Please fix them and re-run the application.\n")
            sys.exit(2)
        # Print out all the rules as JSON.
        if debug:
            sys.stdout.write(">>> JSON sorter rules:\n{0}\n\n".format(self.all_count_locn_type_cnum_binnum))

    # Gets the item count if the column contains a number but populate default rules if it contains 'hold*'
    # in any case. In that case create default rules.
    # param:  The count as a string.
    # return: count of items in the catalog with this combination of location and item type, or 0 if the column
    # contains hold rules.
    def _get_integer_(self, count_str):
        # Default to 0 so hold rules don't artificially inflate numbers of items affected by rules.
        item_count = 0
        try:
            item_count: int = round(count_str, None)
        except TypeError:
            # There was no mention of hold in the parameter count_str.
            sys.stderr.write("**error: invalid value found. Expected an integer but got '{}'.\n".format(count_str))
        return item_count

    # Helper function to find a named dictionary in the List of rules.
    # param:  name of the dictionary.
    # return: the dictionary, if there is one, and None none were found with that name.
    def __search__(self, name):
        rule: dict
        for rule in self.matrix:
            if name in rule:
                return rule
        return None

    # Rules begin compilation by creating one rule for each bin and adding all the locations and item types that
    # need to match for that rule to fire. One rule which should covers the largest number of items in the catalog
    # Can contain just item types and will be ordered below the more complex rules that contain locations and item
    # types.
    # param:  ss_rule_dict -  a array of dictionaries of rules taken from the spread sheet.
    def _compile_rules_(self, ss_rule_array):
        # The input array looks like this:
        # [{'count': 2184.0, 'location': 'AUDIOBOOK', 'type': 'JAUDBK', 'bin': 5.0}, {'count': 2809.0, ... }]
        # Create a matrix like so:
        # [{'R1': {'location': ['DAISY', ',FLICKTUNE'], 'type': ['DAISYTB', ',JFLICKTOGO'], 'affected': 4657}}, ... ]
        for ss_item in ss_rule_array:
            affected_count: int = round(ss_item['count'], None)
            this_bin_num: int = round(ss_item['bin'], None)
            r_name = "R{}".format(this_bin_num)
            existing_rule = self.__search__(r_name)
            if existing_rule:
                rule_content = existing_rule[r_name]
                new_location: str = ss_item['location']
                # Append this location onto the existing locations
                rule_content['location'].append("{}".format(new_location))
                new_item_type: str = ss_item['type']
                rule_content['type'].append("{}".format(new_item_type))
                rule_content['affected'] = rule_content['affected'] + affected_count
            else:
                # Add the data to this rule.
                rule_content = {'location': [ss_item['location']], 'type': [ss_item['type']],
                                'affected': affected_count}
                new_rule = {r_name: rule_content}
                self.matrix.append(new_rule)

    '''
    Helper (static) function that finds and replaces multiple instances of rules that can be shortened by
    replacing them with name globbing. For example 'they, them, these' can be replaced with 'the*' in the case
    of sorter rule definitions.
    param:  the_list List of words to compress by glob-ing and or deduplication of the list.
    param:  length integer minimum number of initial characters that must match before the rule can be reduced.
      Any value less than 1 will deduplicate the list, while values larger than the longest string will have no effect.
      The default compression is 3 which makes most shortened words readable in the sort matrix.
    >>> juv = ['JUV', 'JUV', 'JUV', 'JUViDVD', 'JUV_COMIC', 'JUV']
    >>> print("=> {}\n".format(glob(juv, 0)))
    ['JUV_COMIC', 'JUV', 'JUViDVD']
    >>> juv = ['JUV', 'JUV_LIT', 'JUV_FIC', 'JUViDVD', 'JUV_COMIC', 'JUV_COMICBOOK']
    >>> print("=> {}\n".format(glob(juv, 1)))
    ['J*']
    >>> juv = ['JUV', 'JUV_LIT', 'JUV_FIC', 'JUViDVD', 'JUV_COMIC', 'JUV_COMICBOOK']
    >>> print("=> {}\n".format(glob(juv, 2)))
    ['JU*']
    >>> juv = ['JUV', 'JUV_LIT', 'JUV_FIC', 'JUViDVD', 'JUV_COMIC', 'JUV_COMICBOOK']
    >>> print("=> {}\n".format(glob(juv, 3)))
    ['JUV*']
    >>> juv = ['JUV', 'JUV_LIT', 'JUV_FIC', 'JUViDVD', 'JUV_COMIC', 'JUV_COMICBOOK']
    >>> print("=> {}\n".format(glob(juv, 4)))
    ['JUV', 'JUViDVD', 'JUV_*']
    '''
    def __compress__(self, word_list, minimum_length=3):
        word_list: list
        # if the user wants fewer than length characters, assume they just want the list de-duplicated.
        if minimum_length < 1:
            return list(set(word_list))
        # Sorting the list makes sure that the most similar words appear together.
        word_list.sort()
        for i in range(1, len(word_list)):
            if word_list[i - 1][0:minimum_length] == word_list[i][0:minimum_length]:
                word_list[i] = word_list[i - 1] = word_list[i][0:minimum_length] + '*'
        # Remove all the repeated glob-ed words.
        return list(set(word_list))

    # Rules with similar prefixes can be reduced to one rule. For example, TEENFIC, TEENGEN, TEEMCOMIC
    # can be reduced to TEEN*. This method does that. This method only looks at suffixes and the prefix
    # must have at least 3 characters in length.
    def _compress_rules_(self):
        for rule in self.matrix:
            rule: dict
            for key, value in rule.items():
                value['location'] = self.__compress__(value['location'], compression)
                value['type'] = self.__compress__(value['type'], compression)

    # Orders the matrix so testing flows from most specific rule matching to most general.
    # Other facets of the algorithm include ordering specific exception item types before
    # more general rules.
    # A general rule of thumb is if items have to match on both location and type they must precede
    # other rules that don't. The more columns in a spread sheet are needed to determine where the
    # item goes, the higher in the list it goes. The exception is reject rules; holds for other
    # libraries or ILL.
    def _order_rules_(self):
        # Rule ordering rules:
        # 1) REJECT rules for holds fire first since any material with a hold should be handled as quickly as possible.
        # 2) The more complex the rule are those that have values in both the locations and types (and  possibly more)
        #    dictionaries. Place complex rules above simple (single) rules (where 0 is the highest position).
        #    Rules where one or more dictionaries have no entries are less complex.
        # 3) Place default rule for BAD_LOCATIONS above other single rules.
        # 4) Rules that have only types should be listed higher than rules with just locations. This is because the
        #    selection of a specific type is more uncommon than its location which could change, but a type is a
        #    type, and is a finer filter so less likely to match than anything that just happens to be in a given
        #    location.
        # 5) Prefer rules that affect smaller number of items above others. If the rules are well formed
        #    and well maintained this suggestion has no effect. However if someone adjusts the rules unskillfully and
        #    inadvertently introduces a duplicate rule, their fly swatter fix has a chance of firing before the
        #    bazooka rules that (may) come later.
        # 6) The most general rule with the most affected items will appear at the bottom and can have its item
        #    types removed.
        # TODO: First order the reject rules, then order by most dicitionaries ordering them from least affected to
        #  to most affected.
        # * Reject rules are those marked with names: 'REJECT' as opposed to reject rules for BAD_LOCATIONS which are
        # named with the name of the exception bin specifically.
        new_matrix = []
        hierarchy_score: int = 0
        # Order the rules by high and low order, and sort.
        #
        # v is a dict: {"location": ['*'], "type": ['*'], "affected": 0, "alert": 3}
        # Add another attribute called 'score' which will be used to order the rules based on an algorithm described
        # below. However add the 'REJECT' rules first since they would score quite low in the algorithm but need to
        # appear before all others.
        for rule in self.matrix:
            rule: dict
            for key, value in rule.items():
                if key == "REJECT":
                    value['score'] = round(value['alert'], 2) * 100.0
                    continue
                # Count how many rules and compute 'score' where higher scores put rules higher in the matrix.
                hierarchy_score = 0
                for k, v in value.items():
                    # the rule that has item rules will get double points.
                    if k == 'type':
                        hierarchy_score += round(len(v) * 2, 2)
                    elif k == 'location':
                        # The complexity of the location rules counts one-for-one.
                        hierarchy_score += round(len(v), 2)
                    elif k == 'affected':
                        # The more items are affected, the lower in the matrix they go so less gregarious rules have
                        # a chance to fire before the really big gregarious rules.
                        try:
                            hierarchy_score += round((1.0 / v) * 100.0, 2)
                        except ZeroDivisionError:
                            # "REJECT" rules have an effect on 0 known items.
                            hierarchy_score += round(100.0, 2)
                value['score'] = hierarchy_score

        # * Order dictionaries by score.
        for rule in self.matrix:
            rule: dict
            for key, value in rule.items():
                for i in range(len(new_matrix)):
                    for k, v in new_matrix[i].items():
                        if v['score'] <= value['score']:
                            new_matrix.insert(i, rule)
                            break
                    else:
                        continue
                    break
                else:
                    continue
                break
            else:
                new_matrix.append(rule)
        # Add rules to reject materials for other branches or ILL holds.
        hold_rule = dict(REJECT={
            "location": ['*'], "type": ['*'], "callnum": ['*'], "affected": 0, "alert": self.HOLD_TYPE['ill']})
        new_matrix.insert(0, hold_rule)
        hold_rule = dict(REJECT={
            "location": ['*'], "type": ['*'], "callnum": ['*'], "affected": 0, "alert": self.HOLD_TYPE['branch']})
        new_matrix.insert(0, hold_rule)
        hold_rule = dict(REJECT={
            "location": ['*'], "type": ['*'], "callnum": ['*'], "affected": 0, "alert": self.HOLD_TYPE['hold']})
        new_matrix.insert(0, hold_rule)
        # And display the results.
        for rule in new_matrix:
            rule: dict
            for key, value in rule.items():
                print("{} ==> {}".format(key, value))
        self.matrix = new_matrix

    # Writes the proposed matrix to the spread sheet. A new sheet is created at the end fo the
    # document with the proposed rules written in columns.
    def write_matrix_to_ss(self, named_sheet):
        # TODO: Finish me
        pass

    # This method is used to create the XML version of the 3SC file used to upload to each of the induction
    # units on the sorter.
    def write_config_file(self, file_name):
        # TODO: Finish me
        pass

    # Staff have the option of either specifying that certain location/iType combinations should go to the exception
    # bin, but it is not required. If not specified the highest even bin number is taken to be the second last sorter
    # bin on the machine. The last bin is always the exception bin, which may or may not be used in the spread sheet's
    # 'Bin #' column. Items identified to go to the exception bin will have rules generated and will be included in
    # the matrix rules, but anything that is not identified as going into one bin or another will automatically go
    # to the exception bin.
    # param:  bins - a dictionary with ordered as follows. {'1': 84, '2': 76, '3': 13, '4': 5}
    # return: True if the staff have provided enough information to compute a matrix and false otherwise.
    def _is_well_formed_(self, bins):
        if len(bins.items()) < self.MIN_BINS:
            # Why do you have a sorter if you only have 2 or fewer bins.
            sys.stderr.write("**error: staff have only identified {} bins for sortation.\n"
                             .format(len(self.bins.items())))
            return False
        for my_bin, count in sorted(bins.items()):
            if my_bin > self.highest_identified_bin:
                self.highest_identified_bin = my_bin
            if debug:
                sys.stdout.write("Bin: {0} was identified {1} times\n".format(my_bin, count))
        # If highest_bin is even then the exception bin is highest_bin +1.
        if self.highest_identified_bin % 2 == 0:
            # No items were identified specifically as going into the exception bin.
            self.exception_bin = self.highest_identified_bin + 1
            self.last_bin = self.highest_identified_bin
        else:
            self.exception_bin = self.highest_identified_bin
            self.last_bin = self.highest_identified_bin - 1
        # Test for missing bins.
        # Given: {'1': 84, '2': 76, '3': 13, '4': 5}
        rule_count = 1
        missing_rules = []
        # See: https://stackoverflow.com/questions/16819222/how-to-return-dictionary-keys-as-a-list-in-python
        for key in sorted([*bins]):
            if int(key) != rule_count:
                missing_rules.append(rule_count)
                sys.stdout.write(" **WARN: there are no rules defined for bin {}\n\n".format(rule_count))
                # The rule count is now out of sync with bins defined. To stop the remaining bins from being reported
                # set the rule_count to the current key and let it increment to compare with the next expected bin.
                rule_count = int(key)
            rule_count += 1
        return True

    # Cleans adds '*' fields to empty arrays.
    def _tidy_(self):
        for rule in self.matrix:
            rule: dict
            for key, value in rule.items():
                if isinstance(value, list):
                    if len(value) < 1:
                        value.append('*')

    # Prints out useful information about how well staff covered the majority of items from the spreadsheet.
    def report(self):
        if debug:
            sys.stdout.write("Highest bin: {0}, last bin: {1}, and exception bin is {2}.\n"
                             .format(self.highest_identified_bin, self.last_bin, self.exception_bin))
        # Report rule coverage.
        sys.stdout.write("Rule coverage:\n")
        total_items = self.handled_by_rule_count + self.unhandled_items_count
        percent_sort: float = round((self.handled_by_rule_count / total_items) * 100.0, 1)
        percent_ignored: float = round(100.0 - percent_sort, 1)
        sys.stdout.write(
            f"Staff ID'd {len(self.all_count_locn_type_cnum_binnum):0.0f} location / item pairs cover "
            f"{self.handled_by_rule_count:0.0f} items, or {percent_sort:0.1f}% of the catalog.\n")
        if percent_ignored > 0.0:
            sys.stdout.write(
                "{:0.0f} rule(s) weren\'t addressed leaving {:0.0f} items or {:0.1f}% of items to fall into "
                "exception bin.\n".format(len(self.unhandled_rule), self.unhandled_items_count, percent_ignored))
        # Now report the errors in the spread sheet.
        if self.malformed_rule_item_count > 0:
            sys.stdout.write("\n**WARN: {} items will fail sortation because their bin assignment(s) in the "
                             "spread sheet are invalid. See below.\n".format(self.malformed_rule_item_count))
            for bad_bin, ss_row in self.malformed_rule_name_row.items():
                sys.stdout.write("  Invalid bin assignment '{}' on row {}.\n".format(bad_bin, ss_row))
        for view_item in self.matrix:
            # TODO: Fix this for better reporting.
            sys.stdout.write("RULE -->: {}\n".format(view_item))


# Staff should be given a spreadsheet whose first sheet includes the header 'Count, Locations, iTypes, Bin #".

if __name__ == "__main__":
    unset_sheet_name: str = "__UNSET__"
    parser = argparse.ArgumentParser(description="Generates optimized sorter config from a Microsoft XSLS file.")
    parser.add_argument("-c", "--compression", default=3, action="store", type=int, required=False,
                        help="Sets the compression level when wildcard-ing locations and item types. For example, "
                             "'JUVFIC' and 'JUVCOMIC' will be wildcard-ed to 'JUV*' with compression of 3, and "
                             "'JU*' if 2 is selected. If 0 is selected only duplicate locations and item types, "
                             "will be removed, and no wildcards will be used.")
    parser.add_argument("-d", "--debug", default="False", action="store", type=str, required=False,
                        help="Turns on diagnostic debug information about the compilation process.")
    # Required input for the name of the XSLS file.
    parser.add_argument("-i", "--in_file", action="store", type=str, required=True,
                        help="The path and name of the XSLS file to read staff selections from.")
    parser.add_argument("-l", "--library_code", action="store", type=str, required=False,
                        help="Specifies code of the library code where the sorter operates. "
                             "For example EPLIDY for Idylwylde branch. If not used no branch specific "
                             "rules will be added.")
    parser.add_argument("-o", "--out_file", action="store", type=str, required=False,
                        help="Specifies the name (and path) of the .3SC file that can be uploaded to each of "
                             "the induction units on the sorter.")
    # The sheet number where the data to compile is located. Sheets are zero-indexed. The default sheet index is '0'.
    parser.add_argument("-s", "--sheet_index", default=0, action="store", type=int, required=False,
                        help="The zero-based index of the staff-selection sheet within the XSLS file. "
                             "Default 0, or the first sheet in the spreadsheet.")
    parser.add_argument("-w", "--write_spread_sheet", default=unset_sheet_name, action="store", type=str,
                        required=False,
                        help="The zero-based index of the staff-selection sheet within the XSLS file. "
                             "Default 0, or the first sheet in the spreadsheet.")
    args = parser.parse_args()
    # The path/spread_sheet.xsls
    input_file = args.in_file
    compression = 3
    if args.compression:
        compression = args.compression
    # The index of the sheet which has the rules staff specified.
    # The first sheet (default) is the '0' or zero-th sheet.
    if args.sheet_index:
        sheet_index = args.sheet_index
    else:
        sheet_index = 0
    # The optional name of the branch where the sorter is situated. This is the library code for that branch.
    # See help for more details.
    branch = ""
    if args.library_code:
        branch = args.library_code.uc()
    # Turn on debugging
    debug = False
    if args.debug == "True":
        debug = True
    # Logic starts here.
    if debug:
        sys.stdout.write("input_file: {0}\n".format(input_file))
        sys.stdout.write("sheet_index: {0}\n".format(sheet_index))

    sorter_configurator = ConfigGenerator(input_file, sheet_index)

    if args.out_file:
        xml_config = args.out_file
        # TODO: Test and report if directory and or file exist and report or exit.
        sorter_configurator.write_config_file(xml_config)
    if args.write_spread_sheet != unset_sheet_name:
        ss_sheet_name = args.write_spread_sheet
        # TODO: Test and report if the sheet already exists and add a new suffix to it to
        #  make the sheet name unique.
        sorter_configurator.write_matrix_to_ss(ss_sheet_name)
    sorter_configurator.report()

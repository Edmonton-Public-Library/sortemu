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
# TODO: Add optional default sort routes for holds for other libraries.
# TODO: Compile rules into optimized format.
# TODO: Export 3CS file as XML.
#######################################################################################################################
import xlrd
import sys
import argparse
import os
import declxml as xml

# Reads in a standard XSLS spreadsheet and displays the entire contents in JSON.
from typing import Dict


class ConfigGenerator:

    # The constructor requires a file name (with path) to the XSLS file.
    # The XSLS configuration file must include a header row. The names read there are the index to the dictionaries.
    # param:  sheet_index the zero-based index to the sheet to read. Default: 0.
    # param:  debug - output additional information. Default: False.
    def __init__(self, file, index=0, info=True):
        # The fewest number of bins permissible on any sorter real or fictional.
        self.MIN_BINS = 3
        self.col_name: Dict[str, int] = {'count': 0, 'location': 1, 'type': 2, 'bin': 3}
        self.debug = info
        self.matrix = []
        workbook = xlrd.open_workbook(file)
        worksheet = workbook.sheet_by_index(index)
        self.header_row = []  # The row where we stock the name of the column
        # Ignore what the columns are called and use the names defined in self.col_name.
        for column_name, col_index in self.col_name.items():
            self.header_row.append(column_name)
        # transform the staff_selection_workbook to a list of dictionary
        self.all_num_loc_typ_bin = []
        self.handled_rule_count = 0
        self.unhandled_rule = []
        self.unhandled_rule_count = 0
        self.bins = {}
        # These are computed to ensure all rules are accounted for and well-formed.
        self.highest_bin = 0
        self.exception_bin = 0
        self.last_bin = 0
        self.malformed_rule_name_row = {}
        self.malformed_rule_item_count = 0
        for row in range(1, worksheet.nrows):
            num_loc_typ_bin = {}
            for column_name, col_index in self.col_name.items():
                num_loc_typ_bin[self.header_row[col_index]] = worksheet.cell_value(row, col_index)
            # If staff didn't identify a bin for this combo ignore it. It's probably a comment somewhere in the empty
            # part of the spread sheet.
            if num_loc_typ_bin['bin'] != '':
                # Count the number of rules specified for each bin. We'll use this for reporting and for computing
                # which bin is the exception bin if one isn't specifically added in the column.
                # But check if staff put text in the 'Bin #' column instead of an actual bin number. Sheesh.
                # If the number format hasn't been set to integer in the spreadsheet coerce it now.
                item_count: int = round(num_loc_typ_bin['count'], None)
                try:
                    my_bin_key: int = int(num_loc_typ_bin['bin'])
                except ValueError:
                    # Since we couldn't make the entry an integer, issue a warning to staff to fix it.
                    if self.debug:  # These get reported in the report.
                        sys.stdout.write(" **WARN: invalid bin assignment '{}' on spread sheet row {}.\n".format(
                            num_loc_typ_bin['bin'], row + 1))
                    self.malformed_rule_name_row[num_loc_typ_bin['bin']] = row + 1
                    self.malformed_rule_item_count += item_count
                    continue
                if my_bin_key in self.bins:
                    self.bins[my_bin_key] += 1
                else:
                    self.bins[my_bin_key] = 1
                self.all_num_loc_typ_bin.append(num_loc_typ_bin)
                # Add the count of items from the first column to the total.
                self.handled_rule_count += item_count
            else:  # The bin isn't specified so they these items are inferred to be going to exception.
                # Do these rules have any use? Is it just the counts we need?
                self.unhandled_rule.append(num_loc_typ_bin)
                self.unhandled_rule_count += item_count
        if self._is_well_formed_(self.bins):
            self._compile_rules_(self.all_num_loc_typ_bin)
        else:
            sys.stdout.write("There are errors in the spread sheet. Please fix them and re-run the application.\n")
            sys.exit(2)
        # Print out all the rules as JSON.
        if self.debug:
            sys.stdout.write(">>> JSON sorter rules:\n{0}\n\n".format(self.all_num_loc_typ_bin))

    # Rules begin compilation by creating one rule for each bin and adding all the locations and item types that
    # need to match for that rule to fire. One rule which should covers the largest number of items in the catalog
    # Can contain just item types and will be ordered below the more complex rules that contain locations and item
    # types.
    # param:  ss_rule_dict -  a array of dictionaries of rules taken from the spread sheet.
    def _compile_rules_(self, ss_rule_array):
        # [{'Count': 2184.0, 'Location': 'AUDIOBOOK', 'Item Type': 'JAUDBK', 'Bin #': 5.0}, {'Count': 2809.0, ...
        # TODO: finish me.
        # Create a matrix like so:
        # [{'R2': {'location': 'AUDIOBOOK,TEENFIC,DAISY', 'type': 'JAUDBK,COMICBOOK,DAISYTB'}}, ... ]
        # for item in ss_rule_array:
        #     if self.matrix
        pass

    # Adds default rules like reject items on hold for other branches or ILL customers.
    def _add_default_rules_(self):
        pass

    # Orders the matrix so testing flows from most specific rule matching to most general.
    # Other facets of the algorithm include ordering specific exception item types before
    # more general rules.
    def _order_rules_(self):
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
            if my_bin > self.highest_bin:
                self.highest_bin = my_bin
            if self.debug:
                sys.stdout.write("Bin: {0} was identified {1} times\n".format(my_bin, count))
        # If highest_bin is even then the exception bin is highest_bin +1.
        if self.highest_bin % 2 == 0:
            # No items were identified specifically as going into the exception bin.
            self.exception_bin = self.highest_bin + 1
            self.last_bin = self.highest_bin
        else:
            self.exception_bin = self.highest_bin
            self.last_bin = self.highest_bin - 1
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

    # Prints out useful information about how well staff covered the majority of items from the spreadsheet.
    def report(self):
        if self.debug:
            sys.stdout.write("Highest bin: {0}, last bin: {1}, and exception bin is {2}.\n"
                         .format(self.highest_bin, self.last_bin, self.exception_bin))
        # Report rule coverage.
        sys.stdout.write("Rule coverage:\n")
        total_items = self.handled_rule_count + self.unhandled_rule_count
        percent_sort: float = round((self.handled_rule_count / total_items) * 100.0, 1)
        percent_ignored: float = round(100.0 - percent_sort, 1)
        sys.stdout.write(
            f"{len(self.all_num_loc_typ_bin):0.0f} rules cover {self.handled_rule_count:0.0f} location/items pairs or "
            f"{percent_sort:0.1f}% of the catalog.\n")
        sys.stdout.write('{:0.0f} rules weren\'t addressed leaving {:0.0f} items or {:0.1f}% of items to fall into '
                         'exception bin.\n'
                         .format(len(self.unhandled_rule), self.unhandled_rule_count, percent_ignored))
        # Now report the errors in the spread sheet.
        if self.malformed_rule_item_count > 0:
            sys.stdout.write('\n**WARN: {} items will fail sortation because their bin assignments in the '
                             'spread sheet are invalid.\n'.format(self.malformed_rule_item_count))
            for bad_bin, ss_row in self.malformed_rule_name_row.items():
                sys.stdout.write("  bin assignment '{}' on row {}.\n".format(bad_bin, ss_row))


# Staff should be given a spreadsheet whose first sheet includes the header 'Count, Locations, iTypes, Bin #".

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generates optimized sorter config from a Microsoft XSLS file.")
    # Required input for the name of the XSLS file.
    parser.add_argument("-i", "--in_file", action="store", type=str, required=True,
                        help="the path and name of the XSLS file to read staff selections from.")
    # The sheet number where the data to compile is located. Sheets are zero-indexed. The default sheet index is '0'.
    parser.add_argument("-s", "--sheet_index", default=0, action="store", type=int, required=False,
                        help="the zero-based index of the staff-selection sheet within the XSLS file. "
                             "Default 0, or the first sheet in the spreadsheet.")
    parser.add_argument("-d", "--debug", default="False", action="store", type=str, required=False,
                        help="Turns on diagnostic debug information about the compilation process.")
    parser.add_argument("-l", "--library", action="store", type=str, required=False,
                        help="Specifies code of the library code where the sorter operates. "
                             "For example EPLIDY for Idylwylde branch. If not used no branch specific "
                             "rules will be added.")
    args = parser.parse_args()
    input_file = args.in_file
    branch = ""
    if args.library:
        branch = args.library.uc()
    debug = False
    if args.debug == "True":
        debug = True
    if args.sheet_index:
        sheet_index = args.sheet_index
    else:
        sheet_index = 0
    if debug:
        sys.stdout.write("input_file: {0}\n".format(input_file))
        sys.stdout.write("sheet_index: {0}\n".format(sheet_index))
    sorter_configurator = ConfigGenerator(input_file, sheet_index, debug)
    sorter_configurator.report()

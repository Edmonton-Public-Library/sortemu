#!/usr/bin/env python

############################################################################
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
# TODO: 1 Add a non-optional 'Bin count' flag the command line, otherwise
# TODO: the highest even numbered bin is the last.
# TODO: 2 Add a default rule before any single column rule for DAMAGE,
# TODO: MISSING,DISCARD,*ORDER,BINDERY,UNKNOWN,NOF
# TODO: Export 3CS file as XML.
# TODO: Add optional default sort routes for holds for other libraries.
############################################################################
import xlrd
import sys
import argparse
import os
import declxml as xml

DEBUG = True


# Reads in a standard XSLS spreadsheet and displays the entire contents in JSON.


class ConfigGenerator:
    # The constructor requires a file name (with path) to the XSLS file.
    # The XSLS configuration file must include a header row. The names read there are the index to the dictionaries.
    # param:  sheet_index the zero-based index to the sheet to read. Default: 0.
    # param:  debug - output additional information. Default: False.
    def __init__(self, file, index=0, debug=False):
        self.MIN_BINS = 3
        self.debug = debug
        workbook = xlrd.open_workbook(file)
        worksheet = workbook.sheet_by_index(index)
        # TODO: Check header has format of 'count,locations,iTypes,bin #' ignoring case.
        self.header_row = []  # The row where we stock the name of the column
        for col in range(worksheet.ncols):
            self.header_row.append(worksheet.cell_value(0, col))
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
        for row in range(1, worksheet.nrows):
            num_loc_typ_bin = {}
            for col in range(worksheet.ncols):
                # If the column head is empty it means the cell contains random
                # notes and can be ignored. These will show up as cells with content
                # but no text in the column head.
                if self.header_row[col] != '':
                    num_loc_typ_bin[self.header_row[col]] = worksheet.cell_value(row, col)
            # If staff didn't identify a bin for this combo ignore it. It's probably a comment somewhere in the empty
            # part of the spread sheet.
            # TODO: Make it so the actual column names don't matter.
            if num_loc_typ_bin['Bin #'] != '':
                # Count the number of rules specified for each bin. We'll use this for reporting and for computing
                # which bin is the exception bin if one isn't specifically added in the column.
                # But check if staff put text in the 'Bin #' column instead of an actual bin number. Sheesh.
                try:
                    my_bin_key = int(num_loc_typ_bin['Bin #'])
                except ValueError:
                    continue
                if my_bin_key in self.bins:
                    self.bins[my_bin_key] += 1
                else:
                    self.bins[my_bin_key] = 1
                self.all_num_loc_typ_bin.append(num_loc_typ_bin)
                # Add the count of items from the first column to the total.
                self.handled_rule_count += num_loc_typ_bin[self.header_row[0]]
            else:
                # Do these rules have any use? Is it just the counts we need?
                self.unhandled_rule.append(num_loc_typ_bin)
                self.unhandled_rule_count += num_loc_typ_bin[self.header_row[0]]
        self._compute_bin_number_()
        # Print out all the rules as JSON.
        if self.debug:
            sys.stdout.write(">>> JSON sorter rules:\n{0}\n\n".format(self.all_num_loc_typ_bin))

    # Staff have the option of either specifying that certain location/iType combinations should go to the exception
    # bin, but it is not required. If not specified the highest even bin number is taken to be the second last sorter
    # bin on the machine. The last bin is always the exception bin, which may or may not be used in the spread sheet's
    # 'Bin #' column. Items identified to go to the exception bin will have rules generated and will be included in
    # the matrix rules, but anything that is not identified as going into one bin or another will automatically go
    # to the exception bin.
    # param:  none
    # return: message of the number of bins.
    def _compute_bin_number_(self):
        # TODO: test for the following.
        # TODO: * There are at least 1 bin identified in the 'Bin #' column.
        # TODO: * Find the highest even number and the highest odd number. The even is the last sort bin, the odd the
        # TODO:   exception bin.
        # TODO: * Test that there are no missing bins in the 'Bin #' column, that is, no gaps in bin count.
        # TODO: make sure there are at least three bins defined. That is logically the smallest sorter possible.
        # TODO: Make it so the actual column names don't matter.
        if len(self.bins.items()) < self.MIN_BINS:
            # Why do you have a sorter if you only have 2 or fewer bins.
            sys.stderr.write("**error: staff have only identified {} bins for sortation.\n"
                             .format(len(self.bins.items())))
        for my_bin, count in self.bins.items():
            if my_bin > self.highest_bin:
                self.highest_bin = my_bin
            sys.stdout.write("Bin: {0} was identified {1} times\n".format(my_bin, count))
        # If highest_bin is even then the exception bin is highest_bin +1.
        if self.highest_bin % 2 == 0:
            # No items were identified specifically as going into the exception bin.
            self.exception_bin = self.highest_bin + 1
            self.last_bin = self.highest_bin
        else:
            self.exception_bin = self.highest_bin
            self.last_bin = self.highest_bin - 1

    # Prints out useful information about how well staff covered the majority of items from the spreadsheet.
    def report(self):
        sys.stdout.write("Highest bin: {0}, last bin: {1}, and exception bin is {2}.\n"
                         .format(self.highest_bin, self.last_bin, self.exception_bin))
        # Report rule coverage.
        sys.stdout.write("Location and iType rules\n")
        total_items = self.handled_rule_count + self.unhandled_rule_count
        percent_sort: float = round((self.handled_rule_count / total_items) * 100.0, 1)
        percent_ignored: float = round(100.0 - percent_sort, 1)
        sys.stdout.write("defined: {:0.0f} covering {:0.0f} items or {:0.1f}% of the catalog.\n".format(
            len(self.all_num_loc_typ_bin), self.handled_rule_count, percent_sort))
        sys.stdout.write(
            "ignored: {:0.0f} leaving {:0.0f} items or {:0.1f}% of items to fall into exception bin.\n".format(
                len(self.unhandled_rule), self.unhandled_rule_count, percent_ignored))


# Staff should be given a spreadsheet whose first sheet includes the header 'Count, Locations, iTypes, Bin #".
# The sheet should have
if __name__ == "__main__":
    # TODO: add a flag to specify the index of the sheet that contains the staff selections in the xsls file.
    parser = argparse.ArgumentParser(description="Generates optimized sorter config from a Microsoft XSLS file.")
    parser.add_argument("--in_file", action="store", type=str, required=True,
                        help="the path and name of the XSLS file to read staff selections from.")
    parser.add_argument("--sheet_index", action="store", type=int, required=False,
                        help="the zero-based index of the staff-selection sheet within the XSLS file. "
                             "Default 0, or the first sheet in the spreadsheet.")
    parser.add_argument("--bin_count", action="store", type=int, required=False,
                        help="the number of bins the sorter has. If not specified the app will infer the number of "
                             "bins is the highest even bin number specified by staff in the XSLS file. The last "
                             "odd bin number will be taken to be the exceptions bin. This allows staff to not waste "
                             "time defining exception items.")
    args = parser.parse_args()
    input_file = args.in_file
    if args.sheet_index:
        sheet_index = args.sheet_index
    else:
        sheet_index = 0
    if DEBUG:
        sys.stdout.write("input_file: {0}\n".format(input_file))
        sys.stdout.write("sheet_index: {0}\n".format(sheet_index))
    sorter_configurator = ConfigGenerator(input_file, sheet_index, True)
    sorter_configurator.report()

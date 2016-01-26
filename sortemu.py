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
#          1.2.01 - Added more header HTTP output with -e.
#          1.2.00 - Screen scrape configuration web page of sorter.
#          1.1.02 - Formatting, output changes.
#          1.1.01 - Fix greedy matching on rules.
#          1.1.00 - Add checks for correct item type and location names.
#          1.0.01 - Fix to report items that fall into exception bin (eg no match).
#          0.0 - Dev.
#
####################################################
import sys
import getopt
import os
import re
from itertools import product # Produces product of vector of rules for analysis
import urllib2

version = '1.2.01'

# Manages the retrieval of the sorter's configuration. The class screen-scrapes the configuration
# from a given sorter's web interface, logging in as required.
# param:  password string of the password for the sorter you want to grab the config for.
# param:  machine name like 'assams1.epl.ca'
class ConfigFetcher:
    def __init__(self, password, machine_name):
        assert isinstance(password, str)
        self.password = password
        assert isinstance(machine_name, str)
        self.machine = machine_name
        self.rules = []

    # Parses the raw HTML for sort matrix rules. Writes the configuration to a file called sorter.cfg
    # in the working directory.
    # param:  explain boolean True to see the rules and False to be quiet.
    # return: True if the content parsed and False otherwise.
    def parse_sort_matrix_HTML(self, page, explain):
        lines = page.split('\r\n')
        config = open('sorter.cfg', 'w')
        for line in lines:
            # Just grab the lines that start with space and table data, then clean it up and write it to file.
            if re.match('\s+</td><td>[R|r]', line):
                line = line.replace('</td><td>', '\t')
                line = line.strip()
                line = line.replace('</td>', '\n')
                # Sometimes there are pesky extra spaces in between rules.
                line = line.replace(' ', '')
                if explain:
                    sys.stdout.write('SS:"{0}"\n'.format(line))
                self.rules.append(line)
                config.write(line)
        config.close()
        return (len(self.rules) > 0)

    # Manages logging into the sorter's web page. Not meant to be called outside of the class.
    # param:  explain boolean, True if you want to see the returned page's HTML and False to remain silent.
    # return: the array of all the lines of html form the settings page.
    def __login__(self, explain):
        url_login = 'http://' + self.machine + '/IntelligentReturn/pages/Index.aspx?password=' + self.password
        if explain:
            sys.stdout.write('SS.login: "{0}"\n'.format(url_login))
            sys.stdout.write('POST: /IntelligentReturn/pages/Index.aspx HTTP/1.1\n')
            sys.stdout.write('Content-Type: x-www-form-urlencoded\n')
            sys.stdout.write('Origin: http://{0}\n'.format(self.machine))
            sys.stdout.write('Referer: {0}\n'.format(url_login))
        req = urllib2.Request(url_login)
        req.add_header('POST', '/IntelligentReturn/pages/Index.aspx HTTP/1.1')
        req.add_header('Content-Type', 'x-www-form-urlencoded')
        req.add_header('Origin', 'http://' + self.machine)
        req.add_header('Referer', url_login)
        # This is nasty
        # TODO: tidy this up. We are just lucky 3M is lazy about authentication.
        req.add_header('Cookie', '_ga=GA1.2.1092116257.1449677921; ASP.NET_SessionId=kvethq55okpydy452fi2srnk')
        try:
            page = urllib2.urlopen(req).read()
            if explain:
                print str(page)
        except urllib2.URLError:
            sys.stderr.write('** error URLError while reading url:\n{0}.\n'.format(url_login))
            return False
        if len(page) == 0:
            return False
        return True

    # Manages opening the sorter matrix configuration settings web page. Not meant to be called outside of the class.
    # param:  explain boolean, True if you want to see the returned page's HTML and False to remain silent.
    # return: the array of all the lines of html form the settings page.
    def __scrape_settings__(self, explain):
        url_string = 'http://' + self.machine + '/IntelligentReturn/pages/SortMatrixItems.aspx'
        if explain:
            sys.stdout.write('GET: /IntelligentReturn/pages/SortMatrixItems.aspx HTTP/1.1')
            sys.stdout.write('Referer', 'http://{0}/IntelligentReturn/pages/Workflow.aspx'.format(self.machine))
        req = urllib2.Request(url_string)
        req.add_header('GET', '/IntelligentReturn/pages/SortMatrixItems.aspx HTTP/1.1')
        req.add_header('Referer', 'http://' + self.machine + '/IntelligentReturn/pages/Workflow.aspx')
        req.add_header('Cookie', '_ga=GA1.2.1092116257.1449677921; ASP.NET_SessionId=kvethq55okpydy452fi2srnk')
        page = urllib2.urlopen(req).read()
        if not self.parse_sort_matrix_HTML(page, explain):
            sys.stderr.write('** error failed to parse HTML from :\n{0}.\n'.format(url_string))
            return False
        return True

    # Fetches the rules from the sorter's web sorter configuration interface.
    # param:  explain boolean, True if you want to see the page that was retrieved and False otherwise.
    # return: returns the array of rules read from the web interface.
    def fetch_rules(self, explain=False):
        if self.__login__(explain):
            if self.__scrape_settings__(explain):
                return self.rules
            else:
                sys.stderr.write('** error scraping sorter settings for {0}.\n'.format(self.machine))
                sys.exit(-2)
        else:
            sys.stderr.write('** error logging into sorter {0}.\n'.format(self.machine))
            sys.exit(-3)


# Allows testing of item locations from the ILS.
# TODO: update with live information from the ILS.
class Location:
    def __init__(self):
        self.locations = {
            "STACKS" :1, "CHECKEDOUT" :2, "HOLDS": 3, "ON-ORDER":4, "UNKNOWN":5, "REFERENCE" :6, "MISSING":7, "LOST": 8,
            "BINDERY" :9, "INPROCESS" :10, "DISCARD":11, "INTRANSIT" :12, "ILL": 13, "RESERVES":14, "CATALOGING" :15,
            "LOST-PAID" :16, "REPAIR": 17, "RESHELVING" :18, "ADULTCOLL" :19, "4ALLAGES":20, "ALTALEG":21,
            "ALTALIT" :22, "ANNUALREPT" :23, "ATLAS": 24, "ATLASREF":25, "AVCOLL": 26, "AVREF": 27, "AVSEASONAL" :28,
            "BUSINESREF" :29, "LONGOVRDUE" :30, "BUSINESS":31, "BUSREF01":32, "BUSREF10":33, "BUSREF11":34,
            "BUSREF12" :35, "BUSREF13":36, "GOVMAG": 37, "BUSREF15":38, "BUSREF16":39, "BUSREF17":40, "BUSREF18":41,
            "BUSREF19" :42, "BUSREF02":43, "BUSREF20":44, "GOVFWORKS" :45, "BUSREF22":46, "BUSREF23":47, "BUSREF24":48,
            "BUSREF25" :49, "BUSREF26":50, "BUSREF27":51, "BUSREF28":52, "BUSREF29":53, "BUSREF03":54, "GOVFLAW":55,
            "GOVFDIREC" :56, "GOVFECONO" :57, "GOVFDEMOG" :58, "GOVFSTATS" :59, "BUSREF35":60, "BUSREF36":61,
            "BUSREF37" :62, "BUSREF38":63, "BUSREF39":64, "BUSREF04":65, "BUSREF40":66, "BUSREF41":67, "BUSREF42":68,
            "BUSREF05" :69, "BUSREF06":70, "BUSREF07":71, "BUSREF08":72, "BUSREF09":73, "CANC_ORDER" :74,
            "CAREER" :75, "CAREERREF" :76, "CENSUS": 77, "CHILDINFO" :78, "CITYDIR":79, "CITYDIRREF" :80, "COMMNITY":81,
            "COMMNTYREF" :82, "COMMONS":83, "CONSUMER":84, "CONSUMREF" :85, "DESKINFO":86, "DESKMAGS":87, "DESKREAD":88,
            "DESKTELINF" :89, "DISPLAY":90, "DIVISION1" :91, "EDMCOUN":92, "ENCYCLOP":93, "EPLACQ": 94, "EPLBINDERY" :95,
            "EPLCATALOG" :96, "EPLILL": 97, "ESL": 98, "COMICBOOK" :99, "FAIRYTALE" :100, "FICCLASSIC" :101,
            "FICFANTASY" :102, "FICHISTOR" :103, "FICMYSTERY" :104, "FICROMANCE" :105, "FICSCIENCE" :106,
            "FICWESTERN" :107, "FRENCH": 108, "GENERAL":109, "GOVPUB": 110, "HALLOWEEN" :111, "EASTER": 112,
            "CHRISTMAS" :113, "VALENTINE" :114, "THANKSGIVI" :115, "FLICKTUNE" :116, "HERITGNOVR" :117,
            "HERITOVRSZ" :118, "HEALTHREF" :119, "JUVOTHLANG" :120, "STATSCAN":121, "JUVFRENCH" :122, "JUVGRAPHIC" :123,
            "TEENGRAPHC" :124, "LARGEPRMYS" :125, "LARGEPRROM" :126, "LARGEPRWES" :127, "STUDYGUIDE" :128,
            "HERITAGE" :129, "HERITATLAS" :130, "HERITCITYD" :131, "HERITGNLGY" :132, "HERITINDEX" :133, "HOMEWORK":134,
            "INCOMPLETE" :135, "INDEX": 136, "INTERNET":137, "JANESCOLL" :138, "JUVCOLL":139, "JUVCONCEPT" :140,
            "JUVICANRD" :141, "JUVPOETRY" :142, "JUVREF": 143, "JUVSEASONL" :144, "LADCOLL":145, "LADDESK":146,
            "LARGEPRINT" :147, "LAW": 148, "LITERACY":149, "MAGAZINES" :150, "MUSICMAG":151, "NONFICTION" :152,
            "OFFICE" :153, "OTHERLANG" :154, "OVERSIZE":155, "PAMPHLET":156, "PARENTS":157, "SEASONAL":158,
            "SENATE" :159, "SHORTSTORY" :160, "SPOKENBUSI" :161, "SPOKENHLTH" :162, "SPOKENINTP" :163, "SPOKENLANG" :164,
            "SPOKENMUSI" :165, "STANDARDS" :166, "STORAGE":167, "STORAGEHER" :168, "STORAGEREF" :169, "STORYTIME" :170,
            "TEENCOLL" :171, "TREATIES":172, "YRCA": 173, "BUSREF44":174, "BUSREF47":175, "DAMAGE": 176, "FICGRAPHIC" :177,
            "BARCGRAVE" :178, "NON-ORDER" :179, "SENIORS":180, "LOST-ASSUM" :181, "LOST-CLAIM" :182, "JUVCLASSIC" :183,
            "ABORIGINAL" :184, "PROGRAM":185, "BESTSELLER" :186, "REF-ORDER" :187, "JBESTSELLR" :188, "STORAGEGOV" :189,
            "TEENWORLDL" :190, "AVAIL_SOON" :191, "INSHIPPING" :192, "FICGENERAL" :193, "JPBK": 194, "PBK": 195,
            "TPBK" :196, "PBKNF": 197, "JUVVIDGAME" :198, "TEENVIDGME" :199, "MUSIC": 200, "REFMAG": 201,
            "AUDIOBOOK" :202, "CHRISMUSIC" :203, "STOLEN": 204, "JUVPIC": 205, "JUVFIC": 206, "JUVNONF":207,
            "CUSTSERVIC" :208, "INVSTLTR":209, "VIDGAMES":210, "NOF": 211, "MAKER": 212, "EPL2GO": 213, "FICOVER":214,
            "PBKCLA" :215, "PBKFAN": 216, "PBKHIR": 217, "PBKHOR": 218, "PBKINS": 219, "PBKMYS": 220, "PBKROM": 221,
            "PBKSCIFI" :222, "PBKTHR": 223, "PBKWES": 224, "TEENFIC":225, "TPBKSER":226, "NEWS": 227, "JUVBOARD":228,
            "JUVLPR" :229, "EASYENGL":230, "JUVOVRNF":231, "JUVOVRFIC" :232, "NFOVER": 233, "BRAILLE":234, "DAISY": 235,
            "LARGEPRFAN" :236, "LARGEPRNF" :237, "TEENFOVR":238, "JUVMAG": 239, "JUVCDBK":240, "JPBKSER":241,
            "JPBKBCH" :242, "JPBKBCHSER" :243, "JUVFAMLNG" :244, "JUVMOVIE":245, "EMOVIE": 246, "JUVFILMNF" :247,
            "JUVFILMWL" :248, "JUVMUSIC":249, "JUVSPOKEN" :250, "MOVIES": 251, "FILMWL": 252, "JMOVIESOVR" :253,
            "LARGEPRSCI" :254, "LARGEPRHI" :255, "MOVIESOVR" :256, "MUSICOVR":257, "JMUSICOVR" :258, "AUDBKOVR":259,
            "JSPOKENOVR" :260, "EPL2GO2":261, "WLAUDIOBKS" :262
        }

    # Reports if the argument string is a valid location name in the ILS.
    # param:  none.
    # return: True if there is a location in the ILS that matches the argument and False otherwise.
    def has_location(self, location_name):
        if not self.locations.has_key(location_name):
            # May be a star
            if location_name == '*':
                return True
            # could be a location wild card like FIC*
            if location_name[-1] == '*':
                for location in self.locations.keys():
                    if location.startswith(location_name[:-1]):
                        return True
            else: # not a star, no match on valid name
                return False
        else:
            return True

# Allows testing of item types from the ILS.
# TODO: update with live information from the ILS.
class Itype:
    def __init__(self):
        self.types = {
            "UNKNOWN" :1, "ILL-BOOK":2, "AV": 3, "AV-EQUIP":4, "BOOK": 5, "MAGAZINE":6, "MICROFORM" :7, "NEWSPAPER" :8,
            "NEW-BOOK" :9, "REF-BOOK":10, "BRAILLE":11, "CASSETTE":12, "CD": 13, "DVD21": 14, "DVD7": 15, "EQUIPMENT" :16,
            "E-RESOURCE" :17, "JBOOK": 18, "JBRAILLE":19, "JCASSETTE" :20, "JCD": 21, "JDVD21": 22, "JDVD7": 23,
            "JLARGEPRNT" :24, "JMUSICSCOR" :25, "JPAPERBACK" :26, "JPERIODICL" :27, "JREFBOOK":28, "JTALKBKMED" :29,
            "JTALKINGBK" :30, "JVIDEO21":31, "JVIDEO7":32, "LARGEPRINT" :33, "MUSICSCORE" :34, "PAMPHLET":35,
            "PAPERBACK" :36, "PERIODICAL" :37, "TALKBKMED" :38, "TALKINGBK" :39, "VIDEO21":40, "VIDEO7": 41,
            "DAISYRD" :42, "BESTSELLER" :43, "COMIC": 44, "JBESTSELLR" :45, "FLICKTUNE" :46, "JFLICKTUNE" :47,
            "OTHLANGBK" :48, "JOTHLANGBK" :49, "RFIDSCANNR" :50, "BKCLUBKIT" :51, "JKIT": 52, "FLICKSTOGO" :53,
            "TUNESTOGO" :54, "JFLICKTOGO" :55, "JTUNESTOGO" :56, "PROGRAMKIT" :57, "DAISYTB":58, "JDAISYTB":59,
            "JPBK" :60, "PBK": 61, "JVIDGAME":62, "REFPERDCL" :63, "GOVERNMENT" :64, "LAPTOP": 65, "BLU-RAY":66,
            "BLU-RAY21" :67, "JBLU-RAY":68, "JBLU-RAY21" :69, "EREADER":70, "PROGRAM6WK" :71, "LEASEDBK":72,
            "JLEASEDBK" :73, "TABLET": 74, "VIDGAME":75, "PEDOMETER" :76, "MAKERKIT":77, "SBKCLUBKIT" :78
        }

    # Reports if the argument string is a valid item type in the ILS.
    # param:  none.
    # return: True if there is a item type in the ILS that matches the argument and False otherwise.
    def has_type(self, itype):
        if not self.types.has_key(itype):
            # May be a star
            if itype == '*':
                return True
            # could be a location wild card like BLUE-RAY*
            if itype[-1] == '*':
                for location in self.types.keys():
                    if location.startswith(itype[:-1]):
                        return True
            else: # not a star, no match on valid name
                return False
        else:
            return True


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
        """

        :rtype: object
        """
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

    # Tests if the locations entered in the permanent location column are all valid locations at the library.
    # param:  none
    # return: True if all locations entered are valid and false otherwise.
    def test_valid_location(self):
        location_lookup = Location()
        result = True
        line_no = 1
        for line in self.rule_table:
            # locations are in field 5 (0 indexed).
            locations = line[5].split(',')
            for location in locations:
                if not location_lookup.has_location(location):
                    sys.stdout.write('Invalid location on line #{0}: "{1}"\n'.format(line_no, location))
                    result = False
            line_no += 1
        if result:
            sys.stdout.write('pass.\n')
        else:
            sys.stdout.write('fail.\n')

    # Tests if the locations entered in the permanent location column are all valid locations at the library.
    # param:  none
    # return: True if all locations entered are valid and false otherwise.
    def test_valid_itypes(self):
        type_lookup = Itype()
        result = True
        line_no = 1
        for line in self.rule_table:
            # locations are in field 5 (0 indexed).
            itypes = line[7].split(',')
            for my_type in itypes:
                if not type_lookup.has_type(my_type):
                    sys.stdout.write('Invalid item type on line #{0}: "{1}"\n'.format(line_no, my_type))
                    result = False
            line_no += 1
        if result:
            sys.stdout.write('pass.\n')
        else:
            sys.stdout.write('fail.\n')

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
        sys.stdout.write('valid locations: \n')
        self.test_valid_location()
        sys.stdout.write('valid item types: \n')
        self.test_valid_itypes()

    # Checks if all the bins are utilized.
    def check_bins(self, explain=False):
        bins = []
        for i in range(0, len(self.rule_table)):
            # Snag the bin number and put in an array then sort.
            my_bin_name = self.rule_table[i][0]
            if my_bin_name == 'REJECT' or my_bin_name == 'reject':
                sys.stdout.write('Sort route #{0} is set up to reject materials.\n'.format(i + 1))
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
    def is_rule_match(self, rule, item_line, explain=True):
        line_items = item_line.split('|')
        # sys.stdout.write('>>>>item cols:{0}\n>>>>rule cols:{1}.\n'.format(line_items, rule))
        if len(line_items) != len(rule):
            sys.stdout.write('columns don\'t match item cols:{0}, rule cols:{1}, do the items have enough data?\n'.format(len(line_items), len(rule)))
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
            if explain:
                sys.stdout.write('\n=== new test sequence ===\n')
            for reg in regexes:
                regex = str.strip(reg)
                if explain:
                    sys.stdout.write('"{0}" <=> "{1}", '.format(reg, test_col))
                if regex == '*': # That was a star so everything automatically matches.
                    if explain:
                        sys.stdout.write(' Auto-MATCH.\n')
                    break
                elif test_col == '*' and regex != '*': # Item has starred field but rule requires a match.
                    if explain:
                        sys.stdout.write(' NO-MATCH.\n')
                    break
                elif regex[-1] == '*': # The rule ends with '*' so now do relaxed testing.
                    if test_col.startswith(regex[:-1]):
                        if explain:
                            sys.stdout.write(' MATCHES\n'.format(test_col, regex))
                        matched_rules.append(regex)
                        break
                if test_col == regex:
                    if explain:
                        sys.stdout.write(' MATCHES\n'.format(test_col, regex))
                    matched_rules.append(regex)
                    break

                no_match_count += 1
                # if we got here none of the listed rules in this column matched our items data.
                if no_match_count == len(regexes):
                    return [line_items[0], False, rule[0], matched_rules]
                if explain:
                    sys.stdout.write(" skip...\n")
            index += 1
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
    machine = ''
    password = ''
    explain = False
    try:
        opts, args = getopt.getopt(argv, "c:ei:m:p:", ["config=", "items=", "machine="])
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
        elif opt in ("-m", "--machine"):
            assert isinstance(arg, str)
            this_arg = arg.replace("'", '')
            this_arg = this_arg.replace('"', '')
            machine = this_arg
        elif opt in ("-p", "--password"):
            assert isinstance(arg, str)
            this_arg = arg.replace("'", '')
            this_arg = this_arg.replace('"', '')
            password = this_arg
        elif opt in "-e":
            explain = True

    rule_engine = RuleEngine()
    if config_file:
        sys.stdout.write('configuration file is "{0}"\n'.format(config_file))
        if not os.path.isfile(config_file):
            sys.stderr.write("** error: configuration file {0} does not exist.\n".format(config_file))
            sys.exit(-1)
        c_file = open(config_file, 'r')
        for line in c_file:
            rule_engine.load_rule(line)
        c_file.close()
    else: # Screen scrape it.
        if len(machine) > 0:
            if len(password) > 0:
                # This object may call sys.exit() if it has problem reading the web form.
                config_fetcher = ConfigFetcher(password, machine)
                for line in config_fetcher.fetch_rules(explain):
                    rule_engine.load_rule(line)
            else:
                sys.stderr.write("** error: password not specified.\n")
                sys.exit(-1)
        else:
            sys.stderr.write("** error: machine to screen scrape not specified.\n")
            sys.exit(-1)
    # Now you can check rules if you like
    # rule_engine.check_rules(explain)
    rule_engine.test_rules(explain)

    # Test the items file if user wants to check files.
    if items_file:
        sys.stdout.write('running file "{0}"\n'.format(items_file))
        if items_file and not os.path.isfile(items_file):
            sys.stderr.write("** error: item(s) file {0} does not exist.\n".format(items_file))
            sys.exit()
        i_file = open(items_file, 'r')
        for item in i_file:
            rule_engine.test_item(item, explain)
        i_file.close()
    # Done.
    sys.exit(0)

if __name__ == "__main__":
    # import doctest
    # doctest.testmod()
    main(sys.argv[1:])
    # EOF

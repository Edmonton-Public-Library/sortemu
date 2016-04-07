Project Notes
-------------
Initialized: Wed Nov 18 09:55:09 MST 2015.

Sorter basic description:
-----------------------
An item received on an induction slot will be compared to the rules defined in a configuration file. The rules are read
starting from the top, line-by-line until a rule fires and the item is shunted into the bin associated with the rule.
The rule functions to define a sort route which just means bin number. If no rule matches the item travels through the
sorter and ends up in the exception bin.

Each sorter can have many bins. EPL has sorters ranging from 3 to 11 bins.
```
+---+---+---+---+---+---+
|   | 10| 8 | 6 | 4 | 2 |
| 11|---+---+---+---+---+   <- item travel direction
|   | 9 | 7 | 5 | 3 | 1 |
+---+---+---+---+---+---+
```
Organization of a 11 bin sorter. In this case bin 11 is the exception bin.

Sorter configuration (the sort matrix):
---------------------------------------
Sort matrices on the 3M sorters is complicated, but logical. The sorters have a configuration file that is made up of rules, one per line.
A complete list of configurable facets for a rule are:
```
  0 - Sort Route
  1 - Alert
  2 - AlertType
  3 - Magnetic Media
  4 - Media Type
  5 - Permanent Location
  6 - Destination Location
  7 - Collection Code
  8 - Call Number
  9 - Sort Bin	Branch ID
 10 - Library ID
 11 - Check-in Result
 12 - Custom Tag Data
 13 - Detection Source
```
We only use Alert, Alert Type, Permanent Location (Home location), Destination Location (Item Library), Collection code (iType),
and call number. Below is a typical entry.
```
Sort Route	Alert	AlertType	Magnetic Media	Media Type	Permanent Location	Destination Location	Collection Code	Call Number	Sort Bin	Branch ID	Library ID	Check-in Result	Custom Tag Data	Detection Source
R5	*	*	*	*	NONFICTION, REFERENCE	*	BOOK, JBOOK, PBK, PAPERBACK	7*,8*,9*	*	*	*	*
```

The above mentioned rules are defined within a web interface on each induction unit.
The configuration can be exported, then imported to another sorter induction unit. The exported configuration file is
called '3M SelfCheck System Configuration.cfg' by default and is binary encoded.

Sorters may have many induction slots; places where materials are fed into the machine, but all induction slots fall into 2 categories:
Staff side or Patron side. Each induction unit needs to be configured independently, and it is generally better to work on the configuration
for the staff side because it is much easier to test and see what happens. Once testing is complete, the configuration can be exported, then
uploaded to the patron side(s). This will eliminate confusion where patron side sorting differs from staff side.
In addition to the staff and patron induction units there is a central control unit that starts and maintains sorter machinery operations.

The emulator:
-------------

In this emulator we will be concerned with the bin, Permanent location, Destination Location, Collection Code, and Call number.
The bin is the final destination of the items, the other 4 values will be supplied in pipe delimited form or specified from a file.
The configuration file, for the emulator, will just consist of the 4 key criteria specified as they are shown in the web interface.
That is 
 - '*' means match anything in this criterial, or everything matches.
 - Permanent location must contain full or partial home locations such as NONFICTION, or in the case of a partial specification PBK*, which
will match any home location that starts with 'PBK'
 - Similarly, collection code must match fully qualified item types like JBOOK or partial item types such as BLU-RAY* which will match 
BLU-RAY21, and BLU-RAY14.
 - Call numbers are similar and work as follows 700,800,900 specifies exactly 7, 8, and 900 call numbers. To match ranges use 02* for any
range in '02X' range, and 9* to match any call number in the 900 range. 

Once the config file is read in it is parsed for errors, then sorteremu starts reading in the items also one per line, pipe separated on
STDIN. There must always be 4 pipes per line but call number or destination location may be empty if there are no rules to match. Once a 
rule is entered that specifies a condition the line must include values or it will sort to the exception bin, read fail on all lines and 
end up in the default bin. 

Instructions for creating a configuration file:
-----------------------------------------------
There are 2 ways to create configuration files for input. The first is to select all the lines from the sorter's web interface
copy, and paste in a new text document. The extension of the file does not matter. Once created the emulator will parse
the rules from the file and test them for redundant rules and under utilized bins. An example is shown below.
```
R9	Y	03	*	*	*	*	*	*	*	*	*	*	*	*
Submit	 	Submit	Submit	R9	Y	02	*	*	*	*	*	*	*	*	*	*	*	*
Submit	 	Submit	Submit	R9	Y	01	*	*	*	*	*	*	*	*	*	*	*	*
Submit	 	Submit	Submit	R11	*	*	*	*	*	*	BESTSELLER, FLICKSTOGO, JBESTSELLR, JFLICKTOGO, JFLICKTUNE, TUNESTOGO	*	*	*	*	*	*	*
Submit	 	Submit	Submit	R7	*	*	*	*	NONFICTION, REFERENCE	*	BOOK, JBOOK, PBK, PAPERBACK	00*,01*,02*,03*,04*,05*,06*,07*,08*,09,1*,2*,3*,4*,5*,6*	*	*	*	*	*	*
...
```
These rules are taken directly from a 3M sorter matrix web page (version 3.50.050.0).

The second way is to craft a rule file by hand. here is an example of 2 basic rule definitions created by hand.
```
R4|*|*|*|*|*|PBK*|*|*|
R5|*|*|*|*|*|BOOK|900|*
```

Notes on 3M SelfCheck System S-Series Manager
---------------------------------------------
This is a separate sort matrix system that we have. It has fewer columns and looks like this:
```
1	*	*	*	*	LOST-ASSUM, LOST-CLAIM, BINDERY	*	*	*	*
Delete	Edit	Move Up	Move Down	1	Y	01	*	*	*	*	*	*	*
Delete	Edit	Move Up	Move Down	1	Y	02	*	*	*	*	*	*	*
Delete	Edit	Move Up	Move Down	1	Y	03	*	*	*	*	*	*	*
Delete	Edit	Move Up	Move Down	8	*	*	*	*	TEENCOLL, TPBK, TPBKSER	*	JPERIODICL, JPBK	*	*
Delete	Edit	Move Up	Move Down	2	*	*	*	*	*	EPLLON	JPERIODICL, PERIODICAL	*	*
```

The comparison of columns; first the new columns, below it the columns from our standard sort matrix.
```
Bin#	Alert	AlertType	Magnetic Media	Media Type	Permanent Location Destination Location	Collection Code	Call Number	Sort Bin
Sort Route	Alert	AlertType	Magnetic Media	Media Type	Permanent Location	Destination Location	Collection Code	Call Number	Sort Bin	Branch ID	Library ID
```
They match except for the last 2 columns which were added, and the names have been altered somewhat.

Use the -p and -m switches to scrape the sort matrix from a given sorter on the network.


Instructions for creating input item data:
------------------------------------------

The emulator will test items to determine which route rules (bin) will fire. You can create an input file for the -i
switch with
```
echo 31221106625838 | selitem -iB -oNBlyt | selcallnum -iN -oSA
31221106625838  |DAISY|EPLCLV|JDAISYTB|DAISY J 364.1523  DON HEN|
```
The emulator takes these fields and pads missing columns so they are the same number of columns as the rule, then performs
a comparison, reporting which rule fires and why.

Once the rules and input data are aligned the emulator will test each item and make a report of the success of each item.
Here is an example. For the input of:
```
31221106625838  |DAISY|EPLCLV|JDAISYTB|DAISY J 364.1523  DON HEN|
```
The output generated is as follows.
```
python sortemu.py -imna.lst -cmna.cfg
configuration file is "mna.cfg"
running file "mna.lst"
testing bins.
found 11 bins with routing rules.
bin #R1 has 1 rules.
bin #R10 has 2 rules.
bin #R11 has 2 rules.
bin #R2 has 1 rules.
bin #R3 has 3 rules.
bin #R4 has 2 rules.
bin #R5 has 3 rules.
bin #R6 has 1 rules.
bin #R7 has 3 rules.
bin #R8 has 3 rules.
bin #R9 has 3 rules.
done.
testing for redundant rules.
done.
rule order:
** Warning line #5:(R7) has 3 comparisons and should move above lines with 2.
valid locations:
pass.
valid item types:
Invalid item type on line #19: "JTALKBK"
Invalid item type on line #19: "JLARGEPRINT"
fail.
line --: 31221106625838  ->bin E (R-) no rule matches.
```
If the match was successful on then the output looks like this:
```
python sortemu.py -iclv.lst -cclv.cfg
...
31221115754736  ->bin 4 (R4, line 8) matches on ['JPBK*', 'JPBK']
31221108590774  ->bin 4 (R5, line 4) matches on ['JUVMOVIE', 'JDVD21']
```

Instructions for Running:
-------------------------
python sortemu.py [-i'items.lst'] [-c'matrix.cfg'| -p'password' -m'sorter.epl.ca'] [-e]

Product Description:
--------------------
Perl script written by Andrew Nisbet for Edmonton Public Library, distributable by the enclosed license.

Repository Information:
-----------------------
This product is under version control using Git.
[Visit GitHub](https://github.com/Edmonton-Public-Library)

Dependencies:
-------------
None

Known Issues:
-------------
The emulator does not currently take the current hold state of test items into account during processing, that is,
what would happen to these items if holds were not taken into account?
TODO: Allow for items with holds.

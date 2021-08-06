# sazparser
A simple parser for Session Archive Zip (SAZ) files

Written based on https://web.archive.org/web/20180730023102/http://fiddler.wikidot.com:80/saz-files

The purpose is to analysis the result of fiddler (http://www.telerik.com/fiddler) with script.

Current implementation is very basic, but can already extract the most useful data for further analysis.

## Usage
1. install dependancies

   $ pip install -r requirements.txt
   
2. extract information from a saz file

   $ python sazparser.py test.saz

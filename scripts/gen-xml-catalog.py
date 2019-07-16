#!/usr/bin/env python

from AnalysisUtils.diracutils import gen_xml_catalog_from_file
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('lfnsfile', help = 'Options file containing the LFNs.')
parser.add_argument('--xmlfile', default = None, help = 'Name of the xml file to save the catalog to.')
parser.add_argument('--rootvar', default = None, help = 'Environment variable to use as the root of the xml file path')
parser.add_argument('--nfiles', default = 0, help = 'Number of files to generate the catalog for.')
args = parser.parse_args()

gen_xml_catalog_from_file(args.lfnsfile, xmlfile = args.xmlfile, rootvar = args.rootvar,
                          nfiles = int(args.nfiles))

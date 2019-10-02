#!/usr/bin/env python

from AnalysisUtils.diracutils import gen_xml_catalog_from_file, get_lfns_from_path, get_data_settings
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('bkpath', help = 'Bookkeeping path.')
parser.add_argument('lfnsfile', help = 'Options file to save the LFNs to.')
parser.add_argument('--genxml', '-x', action = 'store_true', help = 'Flag to save the xml catalog.')
parser.add_argument('--xmlfile', default = None, help = 'Name of the xml file to save the catalog to.')
parser.add_argument('--rootvar', default = None, help = 'Environment variable to use as the root of the xml file path')
parser.add_argument('--nfiles', default = 0, help = 'Number of files to generate the catalog for.')
parser.add_argument('--settings', '-s', action = 'store_true', help = 'Flag to save the data settings.')

args = parser.parse_args()

get_lfns_from_path(path = args.bkpath, outputfile = args.lfnsfile)
if args.genxml :
    gen_xml_catalog_from_file(args.lfnsfile, xmlfile = args.xmlfile, rootvar = args.rootvar,
                              nfiles = int(args.nfiles))
if args.settings :
    get_data_settings(args.lfnsfile)

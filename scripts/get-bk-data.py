#!/usr/bin/env python

from AnalysisUtils.diracutils import get_bk_data
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('bkpath', help = 'Bookkeeping path.')
parser.add_argument('lfnsfile', help = 'Options file to save the LFNs to.')
parser.add_argument('--dataquality', default = 'OK', help = 'Data quality flags to use (default OK)')
parser.add_argument('--nostats', action = 'store_true', help = 'Don\'t save the stats for the BK path to the output file.')
parser.add_argument('--genxml', '-x', action = 'store_true', help = 'Flag to save the xml catalog.')
parser.add_argument('--xmlfile', default = None, help = 'Name of the xml file to save the catalog to.')
parser.add_argument('--rootvar', default = None, help = 'Environment variable to use as the root of the xml file path')
parser.add_argument('--nfiles', default = 0, help = 'Number of files to generate the catalog for.')
parser.add_argument('--settings', '-s', action = 'store_true', help = 'Flag to save the data settings.')
parser.add_argument('--ignore', action = 'store_true', help = 'Whether to ignore inaccessible files'
                    ' when generating the xml catalog.')
parser.add_argument('--originaltags', action = 'store_true', help = 'Use original tags for real data (default - latest tags).')

args = parser.parse_args()

get_bk_data(path = args.bkpath, outputfile = args.lfnsfile, stats = not args.nostats,
            dataQuality = args.dataquality,
            genxml = args.genxml, xmlfile = args.xmlfile, rootvar = args.rootvar, 
            nfiles = int(args.nfiles), ignore = args.ignore,
            settings = args.settings, latestTagsForRealData = (not args.originaltags))

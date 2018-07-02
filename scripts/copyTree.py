#!/bin/env python

from argparse import ArgumentParser
from AnalysisUtils.treeutils import copy_tree

optParse = ArgumentParser()
optParse.add_argument("--inFiles", nargs = '+', help = 'Name of the input file(s), can be a list.')
optParse.add_argument("--inTree", help = 'Name of the input TTree')
optParse.add_argument("--outFile", help = 'Name of the output file')
optParse.add_argument("--nEntries", type = int, default=-1, help = 'Number of entries to copy (default all).')
optParse.add_argument("--selection", default = '', help = 'Selection to apply (default none).')
optParse.add_argument('--keepBranches', nargs = '*', help = 'List of regexes to be matched to branches to be kept.')
optParse.add_argument('--removeBranches', nargs = '*', help = 'List of regexes to be matched to branches to be removed.')

args = optParse.parse_args()

from ROOT import TTree, TFile

inFile = TFile(options.inFile)
inTree = TTree()
inFile.GetObject(options.inTree, inTree)

outFile = TFile(options.outFile, "recreate")
copy_tree(inTree, selection = args.selection, nentries = args.nEntries, keepbranches = args.keepBranches,
          removebranches = args.removeBranches)
outTree.Write()
outFile.Close()

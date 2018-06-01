#!/bin/env python

from optparse import OptionParser
import sys

optParse = OptionParser()
optParse.add_option("--inFile", type="string", dest="inFile")
optParse.add_option("--inTree", type="string", dest="inTree")
optParse.add_option("--outFile", type="string", dest="outFile")
optParse.add_option("--nEntries", type="int", dest="nEntries", default=1e9)
optParse.add_option("--selection", type="string", dest="selection", default="")

(options,args) = optParse.parse_args()

if options.inFile == None or options.inTree == None or options.outFile == None :
    print "Usage:"
    print "copyTree.py --inFile <input file name> --inTree <input TTree name> --outFile <output file name> [--nEntries <n. entries to copy> --selection <selection to apply>]"
    sys.exit(0)

from ROOT import TTree, TFile

inFile = TFile(options.inFile)
inTree = TTree()
inFile.GetObject(options.inTree, inTree)

outFile = TFile(options.outFile, "recreate")
outTree = inTree.CopyTree(options.selection, "",int(options.nEntries))
outTree.Write()
outFile.Close()

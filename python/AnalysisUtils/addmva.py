from xml.etree import ElementTree
from argparse import ArgumentParser
import ROOT, os
from array import array
from AnalysisUtils.treeutils import TreeFormula, is_tfile_ok

class MVACalc(object) :
    '''Class to calculate MVA variables from an xml file output by TMVA.'''

    def __init__(self, inputtree, weightsfile, weightsvar) :
        '''Takes the TTree on which to calculate the MVA, the xml file output by the TMVA
        training, and the name of the MVA variable.'''

        self.inputtree = inputtree
        self.weightsfile = weightsfile
        self.weightsvar = weightsvar

        weightstree = ElementTree.parse(self.weightsfile)
        weightsroot = weightstree.getroot()

        self.reader = ROOT.TMVA.Reader('Silent')
        self.treevars = {}
        self.tmvavararrays = {}

        weightvars = weightsroot.findall('Variables')[0].findall('Variable')
        for v in weightvars :
            form = v.get('Expression')
            vtype = v.get('Type')

            self.tmvavararrays[form] = array(vtype.lower(), [0])
            self.reader.AddVariable(form, self.tmvavararrays[form])
            self.treevars[form] = TreeFormula(form, form, inputtree)

        spectatorvars = weightsroot.findall('Spectators')[0].findall('Spectator')
        for v in spectatorvars :
            form = v.get('Expression')
            vtype = v.get('Type')
            self.tmvavararrays[form] = array(vtype.lower(), [0])
            self.reader.AddSpectator(form, self.tmvavararrays[form])
            self.treevars[form] = TreeFormula(form, form, inputtree)

        self.reader.BookMVA(self.weightsvar, self.weightsfile)

    def calc_mva(self, ientry) :
        '''Calculate the MVA variable for the given entry in the input tree.'''
        self.inputtree.LoadTree(ientry)
        for key, treeval in self.treevars.iteritems() :
            self.tmvavararrays[key][0] = treeval()
        return self.reader.EvaluateMVA(self.weightsvar)

def make_mva_tree(inputtree, weightsfile, weightsvar, outputtree, outputfile, maxentries = -1, branchname = None) :
    '''Make a TTree containing the MVA variable values for the given input tree.'''
    mvacalc = MVACalc(inputtree, weightsfile, weightsvar)

    if not branchname :
        branchname = weightsvar

    outputfile = ROOT.TFile.Open(outputfile, 'recreate')
    outputtree = ROOT.TTree(outputtree, outputtree)
    mvavar = array('f', [0])
    outputtree.Branch(branchname, mvavar, branchname + '/F')

    if maxentries == -1 :
        maxentries = inputtree.GetEntries()

    for i in xrange(min(maxentries, inputtree.GetEntries())) :
        mvavar[0] = mvacalc.calc_mva(i)
        outputtree.Fill()
    outputtree.Write()
    outputfile.Close()    

def add_mva_friend(datalib, dataname, weightsfile, weightsvar, outputname, perfile = True, overwrite = False):
    '''Add a friend TTree for the given dataset with the values of the given MVA. 'outputname' will
    be used as the output file name and the branch name. If perfile = True, one file will be written
    per input file. If overwrite = False, files with existing friends will be skipped.'''

    if perfile:
        datainfo = datalib.get_data_info(dataname)
        def trees():
            for i in xrange(len(datainfo['files'])):
                yield datalib.get_data(dataname, i)
    else:
        def trees():
            yield datalib.get_data(dataname)
    
    for i, tree in enumerate(trees()):
        fout = datalib.friend_file_name(dataname, outputname, outputname + '_tree', i, True)
        if not overwrite and os.path.exists(fout) and is_tfile_ok(fout):
            continue
        make_mva_tree(tree, weightsfile, weightsvar, outputname + '_tree', outputname, branchname = outputname)

def main() :
    ROOT.gROOT.SetBatch(True)
    argparser = ArgumentParser()
    argparser.add_argument('--inputfile')
    argparser.add_argument('--inputtree')
    argparser.add_argument('--outputfile')
    argparser.add_argument('--outputtree')
    argparser.add_argument('--weightsfile')
    argparser.add_argument('--weightsvar')
    argparser.add_argument('--maxentries', default = -1, type = int)

    args = argparser.parse_args()

    inputfile = ROOT.TFile.Open(args.inputfile)
    inputtree = inputfile.Get(args.inputtree)
    if not inputtree :
        raise Exception("File {0!r} doesn't contain a TTree called {1!r}!".format(args.inputfile, args.inputtree))

    make_mva_tree(inputtree, args.weightsfile, args.weightsvar, args.outputtree, args.outputfile, args.maxentries)

if __name__ == '__main__' :
    main()

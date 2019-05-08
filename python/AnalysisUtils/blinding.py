'''Tools for blinding datasets.'''

import ROOT
from AnalysisUtils.treeutils import TreeBranchAdder, search_branches, make_chain

class BlindingParameter(object) :

    __slots__ = ('__value',)
    
    def __init__(self, value) :
        self.__value = value

    def blind(self, val) :
        return val + self.__value

class GaussBlindingParameter(BlindingParameter) :

    def __init__(self, seed, mu, sigma, nsigmarange = 10., verbose = True,
                 maxattempts = 100) :
        '''Generate a blinding parameter from a Gaussian with the given mu and sigma. If
        a generated value is beyond nsigmarange * sigma from mu, then a new value is generated.
        The first generated value is printed as a cross check (if verbose = True), and the second
        returned.'''

        rndm = ROOT.TRandom3(seed)
        parmin = mu - sigma * nsigmarange
        parmax = mu + sigma * nsigmarange

        def gen() :
            v = rndm.Gaus(mu, sigma)
            i = 1
            while v < parmin or v > parmax :
                v = rndm.Gaus(mu, sigma)
                if i >= maxattempts :
                    raise ValueError('Failed to generate blinding parameter with seed '
                                     '{0!r}, mu = {1!r}, sigma = {2!r}, min = {3!r}, max = {4!r}, in {5} attempts!'\
                                         .format(seed, mu, sigma, parmin, parmax,
                                                 maxattempts))

                i += 1
            return v

        v1 = gen()
        if verbose :
            print 'Generating blinding parameter with seed '\
                '{0!r}, mu = {1!r}, sigma = {2!r}, min = {3!r}, max = {4!r}'\
                .format(seed, mu, sigma, parmin, parmax)
            print 'The first random value is {0!r}'.format(v1)
        v2 = gen()

        super(GaussBlindingParameter, self).__init__(v2)

class GaussScaleBlindingPar(GaussBlindingParameter) :

    __slots__ = ('__offset',)

    def __init__(self, seed, mu, sigma, offset = 0., nsigmarange = 10., verbose = True,
                 maxattempts = 100) :
        self.__offset = offset
        super(GaussScaleBlindingPar, self).__init__(seed, mu, sigma, nsigmarange, verbose, maxattempts)

    def blind(self, value) :
        return (value - self.__offset) * self._BlindingParameter__value + self.__offset

def blind_tree(blindingpar, fout, tree, branches, selection = None) :
    '''Blind branches in the given TTree with the given blinding scale and save the resulting TTree
    to fout.
    blindingpar: the BlindingParameter instance used to blind.
    fout: the name of the output file.
    tree: the TTree to be blinded.
    branches: a list of the names of branches to be blinded.'''

    fout = ROOT.TFile.Open(fout)
    for branch in branches :
        tree.SetBranchStatus(branch, False)
    treeout = tree.CopyTree()
    branchadders = []
    treebranches = []
    for branch in branches :
        tree.SetBranchStatus(branch, True)
        br = tree.GetBranch(branch)
        treebranches.append(br)
        leaf = tree.GetLeaf(branch)
        branchadder = BranchAdder\
    .copy_branch(tree, branch, treeout,
                 (lambda leaf : [leaf.GetValue(i)*blindingscale for i in xrange(leaf.GetLen())]),
                 filllength = False, args = (leaf,))
        branchadders.append(branchadder)
    
    for i in tree_loop(tree, selection) :
        for branch in treebranches :
            branch.GetEntry(i)
        for adder in branchadders :
            adder.set_value()
            adder.fill()
    treeout.Write()
    fout.Close()

def blind_tree_with_scale_main() :
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('--inputfile', nargs = '+', 
                        help = 'Name of the file(s) containing the TTree to be blinded.')
    parser.add_argument('--inputtree', help = 'Name of the TTree to be blinded.')
    parser.add_argument('--outputfile', help = 'Name of the output file.')
    parser.add_argument('--seed', help = 'Seed to generate the blinding scale.', type = long)
    parser.add_argument('--mu', help = 'Mean of the blinding scale.', type = float)
    parser.add_argument('--sigma', help = 'Width of the blinding scale.', type = float)
    parser.add_argument('--offset', default = 0., help = 'Offset to apply when blinding.', type = float)
    parser.add_argument('--nsigmarange', help = 'Max number of sigma the scale can be from mu.', default = 10.,
                        type = float)
    parser.add_argument('--maxattempts', help = 'Max number of attempts to generate a scale within range.',
                        default = 100, type = long)
    parser.add_argument('--branches', nargs = '*', help = 'Names of branches to blind with the scale.')
    parser.add_argument('--regexbranches', nargs = '*',
                        help = 'Regexes of branch names, matching branches will be blinded.')
    parser.add_argument('--quiet', action = 'store_true')
    parser.add_argument('--selection', help = 'Selection to apply when copying the TTree for blinding.')

    args = parser.parse_args()
    par = GaussScaleBlindingPar(args.seed, args.mu, args.sigma, args.offset, args.nsigmarange, not args.quiet,
                                args.maxattempts)

    intree = make_chain(args.inputtree, *args.inputfile)

    branches = args.branches
    if args.regexbranches :
        branches += search_branches(intree, *args.regexbranches)
    if not branches :
        raise ValueError('No branches were selected to blind!\n'
                         'Requested branches:' + str(args.branches) + '\n'
                         'Regex branches:' + str(args.regexbranches))

    blind_tree(par, args.outputfile, intree, branches, args.selection)

from AnalysisUtils.treeutils import TreePVector, get_unique_events, tree_loop
import ROOT
from array import array
from ROOT import TLorentzVector

def get_pvectors(tree, parts, **kwargs) :
    '''Get the momentum vectors of the given particles from the TTree as
    TLorentzVectors. The keyword 'selection' can be used to apply a selection.'''
    
    pforms = {part : TreePVector(tree, part) for part in parts}
    nparts = len(pforms)
    
    pvecs = {part : [] for part in parts}
    for i in tree_loop(tree, kwargs.get('selection', None)) :
        for part, form in pforms.items() :
            pvecs[part].append(form.vector())
    return pvecs

def offset_pvectors(pvecs, offset) :
    '''Get sets of pvectors from the given dict of lists of p vectors (from get_pvectors)
    from offset events. The pvectors are selected using indices (i+(offset+1)*j) % nevts
    where i = event index and j = particle index.'''
    nevts = len(pvecs.values()[0])
    for i in xrange(nevts) :
        _pvecs = {}
        for j, (part, plist) in enumerate(pvecs.items()) :
            _pvecs[part] = plist[(i+(offset+1)*j) % nevts]
        yield _pvecs
    
def total_mass(pvecs) :
    '''Get the total mass from the dict of p vectors.'''
    pvec = TLorentzVector()
    for vec in pvecs.values() :
        pvec += vec
    return pvec.M()

def wrong_event_masses(tree, outputfile, nbins, massvar, parts, **kwargs) :
    '''Calculate the mass of combinations of particles from different events. Unique
    events are selected using eventNumber and runNumber. Different branches can be used
    by passing a list with the 'checkbranches' keyword. Keyword 'selection' can be used
    to apply an additional selection besides selecting unique events. By default, one
    iteration is run with an offset between events of 0. The pvectors are selected using
    indices (i+(offset+1)*j) % nevts where i = event index and j = particle index.
    Additional iterations can be run by passing a list of offsets using the 'offsets'
    keyword.'''

    closefile = False
    if isinstance(outputfile, str) :
        outputfile = ROOT.TFile.Open(outputfile, kwargs.get('openopt', 'recreate'))
        closefile = True
    outputfile.cd()

    if 'selection' in kwargs :
        print 'Using selection', kwargs['selection']
    uniquelist = get_unique_events(tree, selection = kwargs.get('selection', None),
                                   checkbranches = kwargs.get('checkbranches', ('eventNumber', 'runNumber')))
    print 'Selected', uniquelist.GetN(), 'unique events from TTree', tree.GetName()
    pvecs = get_pvectors(tree, parts, selection = uniquelist)

    combinations = kwargs.get('combinations', {})
    if not 'totalmass' in combinations :
        combinations['totalmass'] = {'function' : total_mass}
    combinations['totalmass'].update({'xmin' : massvar['xmin'],
                                      'xmax' : massvar['xmax']})

    histos = {name : ROOT.TH1F(name, '', nbins, vals['xmin'], vals['xmax']) for name, vals in combinations.items()}

    requireall = kwargs.get('requireall', True)
    if requireall :
        select = lambda vals : all(combinations[name]['xmin'] <= v and v <= combinations[name]['xmax'] \
                                       for name, v in vals.items())
    else :
        select = lambda vals : any(combinations[name]['xmin'] <= v and v <= combinations[name]['xmax'] \
                                       for name, v in vals.items())

    outtree = ROOT.TTree(kwargs.get('treename', 'wrongmasstree'), kwargs.get('treename', 'wrongmasstree'))
    branches = {}
    for name in combinations :
        brancharr = array('f', [0.])
        branch = outtree.Branch(name, brancharr, name + '/F')
        branches[name] = brancharr
    offsetarr = array('i', [0])
    outtree.Branch('offset', offsetarr, 'offset/I')

    def run_offset(offset) :
        offsetarr[0] = offset
        for _pvecs in offset_pvectors(pvecs, offset) :
            combvals = {name : vals['function'](_pvecs) for name, vals in combinations.items()}
            if not select(combvals) :
                continue
            for name, v in combvals.items() :
                branches[name][0] = v
                histos[name].Fill(v)
            outtree.Fill()

    offsets = kwargs.get('offsets', range(1))
    if 'targetstats' in kwargs :
        run_offset(0)
        nper = histos['totalmass'].GetEntries()
        noff = int(kwargs['targetstats']/histos['totalmass'].GetEntries()) + 1
        offsets = range(1, noff)
        print 'Got', nper, 'entries from offset=0'
        print 'Will use', noff-1, 'more offsets to obtain', kwargs['targetstats'], 'entries'

    for offset in offsets :
        run_offset(offset)

    for obj in [outtree,] + list(histos.values()) :
        obj.Write()

    if closefile :
        for h in histos.values() :
            h.SetDirectory(None)
        outputfile.Close()

    if len(histos) == 1 :
        return histos['totalmass']
    return histos

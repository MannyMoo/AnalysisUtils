from PhysSelPython.Wrappers import Selection, SelectionSequence
from PhysConf.Selections import RebuildSelection
import StandardParticles
from Configurables import FilterDesktop, CombineParticles, CheckPV

mcbasicinputs = {'K+' : ['StdAllNoPIDsKaons'],
                 'pi+' : ['StdAllNoPIDsPions'],
                 'mu-' : ['StdAllNoPIDsMuons'],
                 'p+' : ['StdAllNoPIDsProtons'],
                 'e-' : ['StdAllNoPIDsElectrons'],
                 # RebuildSelection currently doesn't work with StdLooseResolvedPi0.
                 'pi0' : ['StdLooseMergedPi0',], #'StdLooseResolvedPi0']
                 }

selections = {}

def build_mc_unbiased_selection(decayDesc, arrow = '==>', refitpvs = True) :
    '''Make a selection for the given decay descriptor that has no cuts besides
    truth matching.'''

    preamble = [ "from LoKiPhysMC.decorators import *" , "from LoKiPhysMC.functions import mcMatch" ]
    decayDesc = decayDesc.copy()
    decayDesc.clear_aliases()
    decayDesc.set_carets(False)
    decayDescCC = decayDesc.copy()
    decayDescCC.cc = True
    algname = decayDesc.get_full_alias() + '_MCSel'
    algnameconj = decayDesc.conjugate().get_full_alias() + '_MCSel'
    if algname in selections :
        return selections[algname]
    elif algnameconj in selections :
        return selections[algnameconj]

    if not decayDesc.daughters :
        alg = FilterDesktop(algname + '_Filter')
        basicname = decayDesc.particle.name
        if not basicname in mcbasicinputs :
            basicname = decayDesc.conjugate().particle.name
        if basicname in mcbasicinputs :
            inputsels = [RebuildSelection(getattr(StandardParticles, basicinput)) for basicinput in mcbasicinputs[basicname]]
        else :
            raise ValueError("Can't find MC basic input for particle " + repr(decayDesc.particle.name))
        alg.Code = 'mcMatch({0!r})'.format(decayDescCC.to_string(arrow))
        alg.Preambulo = preamble
        sel = Selection(algname,
                        Algorithm = alg,
                        RequiredSelections = inputsels)
        selections[algname] = sel
        return sel
    inputs = set()
    daughtercuts = {}
    for daughter in decayDescCC.daughters :
        originaldaughtercc = daughter.cc
        daughter.cc = True
        sel = build_mc_unbiased_selection(daughter, arrow, refitpvs)
        daughter.cc = originaldaughtercc
        inputs.add(sel)
        #daughter.caret = True
        #daughtercuts[daughter.particle.name] = 'mcMatch({0!r})'.format(decayDescCC.to_string(arrow))
        #daughter.caret = False
    #comb = nCombiners[len(decayDesc.daughters)](algname + '_Comb')
    comb = CombineParticles(algname + '_Comb')
    # CombineParticles uses small cc, so set ishead = False
    comb.DecayDescriptors = [decayDesc.to_string(depth = 1).replace('CC', 'cc')]
    comb.MotherCut = 'mcMatch({0!r})'.format(decayDescCC.to_string(arrow))
    comb.Preambulo = preamble
    comb.DaughtersCuts = daughtercuts
    comb.ReFitPVs = refitpvs
    if refitpvs:
        comb.MotherCut += ' & BPVVALID()'
    sel = Selection(algname,
                    Algorithm = comb,
                    RequiredSelections = list(inputs))
    selections[algname] = sel
    return sel

def make_mc_unbiased_seq(desc, arrow = '==>', refitpvs = True) :
    '''Make a selection sequence for the given decay descriptor that has no cuts besides
    truth matching.'''
    desc = desc.copy()
    desc.clear_aliases()
    sel = build_mc_unbiased_selection(desc, arrow, refitpvs)
    selseq = SelectionSequence(desc.get_full_alias() + '_MCUnbiasedSeq',
                               TopSelection = sel)
    seq = selseq.sequence()
    seq.Members.insert(0, CheckPV())
    return seq, selseq

from DecayTreeTuple.Configuration import DecayTreeTuple
from Configurables import MCDecayTreeTuple
from AnalysisUtils.Selections.mcselections import build_mc_unbiased_selection

def _make_tuple(desc, suff, ToolList, TupleType) :
    dtt = TupleType(desc.get_full_alias() + suff)
    dtt.ToolList = list(ToolList)
    dtt.Decay = desc.to_string(carets = True)
    dtt.addBranches(desc.branches())
    return dtt

def make_tuple(desc, inputloc, 
               ToolList = ['TupleToolPrimaries',
                           'TupleToolGeometry',
                           'TupleToolPid',
                           'TupleToolANNPID',
                           'TupleToolRecoStats',
                           'TupleToolKinematic',
                           'TupleToolEventInfo',
                           'TupleToolTrackInfo'],
               suff = '_Tuple') :
    dtt = _make_tuple(desc, suff, ToolList, DecayTreeTuple)
    dtt.Inputs = [inputloc]
    return dtt

def make_mc_tuple(desc, ToolList = ['MCTupleToolKinematic', 'TupleToolEventInfo'],
                  suff = '_MCDecayTreeTuple') :
    return _make_tuple(desc, suff, ToolList, MCDecayTreeTuple)

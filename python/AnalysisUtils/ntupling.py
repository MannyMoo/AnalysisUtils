from DecayTreeTuple.Configuration import DecayTreeTuple

def make_tuple(desc, inputloc, suff = '_Tuple') :
    dtt = DecayTreeTuple(desc.get_full_alias() + suff)
    dtt.Decay = desc.to_string().replace('CC', 'cc')
    dtt.Inputs = [inputloc]
    dtt.setBranches(desc.branches())
    return dtt

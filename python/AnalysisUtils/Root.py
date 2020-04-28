'''ROOT hacks.'''

import ROOT, os, stat, string, random

def random_string(n = 6, chars = string.ascii_uppercase + string.ascii_lowercase) :
    '''Generate a random string of length n.'''
    return ''.join(random.choice(chars) for _ in xrange(n))

def getperm(fname):
    '''Get default permissions for a file created in the same directory as the given file name.'''
    try:
        fperm = os.path.join(os.path.dirname(fname), '___getperm_' + random_string() + '___')
        with open(fperm, 'w') as f:
            pass
        perms = stat.S_IMODE(os.lstat(fperm).st_mode)
        os.remove(fperm)
        return perms
    except IOError:
        return None

def __init__(self, name, option = '', ftitle = '', compress = 1):
    '''Open a ROOT file. For local files, the permissions will automatically be set to match
     the default for the directory in which the file is created.'''
    self._init(name, option, ftitle, compress)
    if self.IsZombie():
        return
    # Not a local file, or read mode.
    if ':/' in name or not option or option.lower() == 'read':
        return
    perm = getperm(name)
    if not perm:
        return
    os.chmod(name, perm)

def Open(name, option = '', ftitle = '', compress = 1, netopt = 0):
    '''Open a ROOT file. For local files, the permissions will automatically be set to match
    the default for the directory in which the file is created.'''
    # Not a local file.
    if ':/' in name:
        return ROOT.TFile._Open(name, option, ftitle, compress, netopt)
    return ROOT.TFile(name, option, ftitle, compress)

ROOT.TFile._init = ROOT.TFile.__init__
ROOT.TFile.__init__ = __init__
del __init__

ROOT.TFile._Open = ROOT.TFile.Open
ROOT.TFile.Open = staticmethod(Open)
del Open

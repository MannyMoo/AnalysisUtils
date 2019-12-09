#!/usr/bin/env python

import subprocess, sys, os

# Prepend directories to PYTHONPATH.
env = dict(os.environ)
if 'GANGAPYTHONPATH' in env:
    env['PYTHONPATH'] = env['GANGAPYTHONPATH'] + ':' + env['PYTHONPATH']

# Get ganga arguments.
argv = list(sys.argv[1:])
args = []
# Check if ganga version is specified, make sure that's the first argument
if '--ganga-version' in argv:
    iver = argv.index('--ganga-version')
    args += ['--ganga-version', argv[iver+1]]
    argv.pop(iver)
    argv.pop(iver)
args += argv

def get_args(envvar, opt, action = None):
    '''Get ganga configuration args from environment an environment variable.
    envvar: the name of the environment variable
    opt: the name of the configuration option.
    Eg:
    args = []
    args += get_args('GANGASTARTUP', '[Configuration]StartupGPI')
    '''
    if not envvar in os.environ:
        return []
    val = os.environ[envvar]
    if action:
        val = action(val)
    return ['-o', opt + '=' + val]

args += get_args('GANGASTARTUP', '[Configuration]StartupGPI')
args += get_args('GANGADIR', '[Configuration]gangadir',
                 action = (lambda x : os.path.join(x, os.environ['USER'])))

subprocess.call(['ganga'] + args, env = env)

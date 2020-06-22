#!/bin/bash

RUNDIR="$( cd "$( dirname "${BASH_SOURCE[0]}")/../../" && pwd )"
PROJECT=$(basename $RUNDIR)
# This is necessary to get pytools for ipython.
echo "alias run=\"$RUNDIR/run\""
# make install is needed to use lb-run.
echo "alias build=\"cd ${RUNDIR};(make >& stdout-make) && cat stdout-make || less stdout-make;cd -\""
echo "alias confbuild=\"cd ${RUNDIR};(make configure >& stdout-make && make >>& stdout-make) && cat stdout-make  || less stdout-make ;cd -\""
echo "alias install=\"cd ${RUNDIR};make install;cd -\""
echo "export ANALYSISUTILSROOT=$ANALYSISUTILSROOT"
GANGAPYTHONPATH="$ANALYSISUTILSROOT/ganga"
echo "export GANGAPYTHONPATH=$GANGAPYTHONPATH"
GANGASTARTUP="from AnalysisUtils.Ganga import *"
echo "export GANGASTARTUP=\"$GANGASTARTUP\""
echo "alias ganga.py=$(which ganga.py)"
echo "alias pyroot='run pyroot'"

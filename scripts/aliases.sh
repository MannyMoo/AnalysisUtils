#!/bin/bash

RUNDIR="$( cd "$( dirname "${BASH_SOURCE[0]}")/../../" && pwd )"
PROJECT=$(basename $RUNDIR)
# This is necessary to get pytools for ipython.
echo "alias run=\"$RUNDIR/run\""
# make install is needed to use lb-run.
echo "alias build=\"cd ${RUNDIR};make;cd -\""
echo "alias confbuild=\"cd ${RUNDIR};make configure && make;cd -\""
echo "alias install=\"cd ${RUNDIR};make install;cd -\""

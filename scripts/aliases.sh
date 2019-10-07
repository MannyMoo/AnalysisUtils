#!/bin/bash

RUNDIR="$( cd "$( dirname "${BASH_SOURCE[0]}")/../../" && pwd )"
PROJECT=$(basename $RUNDIR)
# This is necessary to get pytools for ipython.
echo "alias run=\"lb-run --ext pytools --user-area=${RUNDIR}/../ ${PROJECT/_//}\""
# make install is needed to use lb-run.
echo "alias build=\"cd ${RUNDIR};make && make install;cd -\""
echo "alias confbuild=\"cd ${RUNDIR};make configure && make && make install;cd -\""

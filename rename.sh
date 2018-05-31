#!/bin/bash

name=$1
nameupper=$(python -c "print '$name'.upper()")
for f in $(find . -path ./.git -prune -o -type f) ; do
    sed -i "s/AnalysisUtils/$name/g" $f
    sed -i "s/ANALYSISUTILS/$nameupper/g" $f
done
	
git mv python/AnalysisUtils python/$name

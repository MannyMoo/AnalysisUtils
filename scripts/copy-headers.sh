#!/bin/bash

# Copy header files from source directories into a shared directory.

dest=$1
dirs=${@:1}
for d in $dirs ; do
    find $d -name '*.h' -exec cp {} $dest \;
    find $d -name '*.hh' -exec cp {} $dest \;
done

cd $dest
for f in $(ls) ; do
    sed -i "s/<${f}>/\"${f}\"/" *
done
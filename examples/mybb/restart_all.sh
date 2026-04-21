#!/bin/bash

cmd=$(basename $0 | sed s/_all.sh//)

for a in badenpi downtownpi uptownpi sawmillpi
do
    ssh -l root $a systemctl $cmd dccexonsbc &
done

#!/bin/bash

# load current ops count (or default to 0)
if [[ "$(ctx type)" == 'relationship-instance' ]]
then
ops_counter=$(ctx source instance runtime_properties 'ops_counter')
else
ops_counter=$(ctx instance runtime_properties 'ops_counter')
fi
ops_counter=${ops_counter:-0}

# increment ops count
ops_counter=$(expr $ops_counter + 1)

# store updated count
if [[ "$(ctx type)" == 'relationship-instance' ]]
then
ctx source instance runtime_properties 'ops_counter' $ops_counter
else
ctx instance runtime_properties 'ops_counter' $ops_counter
fi
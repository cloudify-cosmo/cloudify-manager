#!/bin/bash

# load current ops count (or default to 0)
if [[ "$(ctx type)" == 'relationship-instance' ]]
then
source_ops_counter=$(ctx source instance runtime_properties 'source_ops_counter')
else
source_ops_counter=$(ctx instance runtime_properties 'source_ops_counter')
fi
source_ops_counter=${source_ops_counter:-0}

# increment ops count
source_ops_counter=$(expr $source_ops_counter + 1)

# store updated count
if [[ "$(ctx type)" == 'relationship-instance' ]]
then
ctx source instance runtime_properties 'source_ops_counter' $source_ops_counter
else
ctx instance runtime_properties 'source_ops_counter' $source_ops_counter
fi
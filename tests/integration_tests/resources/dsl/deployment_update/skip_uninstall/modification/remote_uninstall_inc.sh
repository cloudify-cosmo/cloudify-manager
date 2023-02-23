#!/bin/bash

# load current ops count (or default to 0)
if [[ "$(ctx type)" == 'relationship-instance' ]]
then
uninstall_op_counter=$(ctx target instance runtime_properties get 'uninstall_op_counter')
else
uninstall_op_counter=$(ctx instance runtime_properties get 'uninstall_op_counter')
fi
uninstall_op_counter=${uninstall_op_counter:-0}

# increment ops count
uninstall_op_counter=$(expr $uninstall_op_counter + 1)

# store updated count
if [[ "$(ctx type)" == 'relationship-instance' ]]
then
ctx target instance runtime_properties 'uninstall_op_counter' $uninstall_op_counter
else
ctx instance runtime_properties 'uninstall_op_counter' $uninstall_op_counter
fi
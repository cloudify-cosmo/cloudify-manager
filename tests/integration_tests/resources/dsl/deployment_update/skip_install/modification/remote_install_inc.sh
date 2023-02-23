#!/bin/bash

# load current ops count (or default to 0)
if [[ "$(ctx type)" == 'relationship-instance' ]]
then
install_op_counter=$(ctx target instance runtime_properties get 'install_op_counter')
else
install_op_counter=$(ctx instance runtime_properties get 'install_op_counter')
fi
install_op_counter=${install_op_counter:-0}

# increment ops count
install_op_counter=$(expr $install_op_counter + 1)

# store updated count
if [[ "$(ctx type)" == 'relationship-instance' ]]
then
ctx target instance runtime_properties 'install_op_counter' $install_op_counter
else
ctx instance runtime_properties 'install_op_counter' $install_op_counter
fi
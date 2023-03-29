#!/bin/bash

# load current ops count (or default to 0)

e_ops_counter=$(ctx instance runtime_properties get 'e_ops_counter')
e_ops_counter=${e_ops_counter:-0}
# increment ops count
e_ops_counter=$(expr $e_ops_counter + 1)

# store updated count
ctx instance runtime_properties 'e_ops_counter' $e_ops_counter

#!/bin/bash

# load current ops count (or default to 0)

f_ops_counter=$(ctx instance runtime_properties get 'f_ops_counter')
f_ops_counter=${f_ops_counter:-0}
# increment ops count
f_ops_counter=$(expr $f_ops_counter + 1)

# store updated count
ctx instance runtime_properties 'f_ops_counter' $f_ops_counter

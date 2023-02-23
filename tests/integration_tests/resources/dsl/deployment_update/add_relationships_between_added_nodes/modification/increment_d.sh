#!/bin/bash

# load current ops count (or default to 0)

d_ops_counter=$(ctx instance runtime_properties get 'd_ops_counter')
d_ops_counter=${d_ops_counter:-0}
# increment ops count
d_ops_counter=$(expr $d_ops_counter + 1)

# store updated count
ctx instance runtime_properties 'd_ops_counter' $d_ops_counter

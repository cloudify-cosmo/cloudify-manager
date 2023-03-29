#!/bin/bash

# load current ops count (or default to 0)

b_ops_counter=$(ctx instance runtime_properties get 'b_ops_counter')
b_ops_counter=${b_ops_counter:-0}
# increment ops count
b_ops_counter=$(expr $b_ops_counter + 1)

# store updated count
ctx instance runtime_properties 'b_ops_counter' $b_ops_counter

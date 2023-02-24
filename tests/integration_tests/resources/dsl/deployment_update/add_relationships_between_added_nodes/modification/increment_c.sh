#!/bin/bash

# load current ops count (or default to 0)

c_ops_counter=$(ctx instance runtime_properties get 'c_ops_counter')
c_ops_counter=${c_ops_counter:-0}
# increment ops count
c_ops_counter=$(expr $c_ops_counter + 1)

# store updated count
ctx instance runtime_properties 'c_ops_counter' $c_ops_counter

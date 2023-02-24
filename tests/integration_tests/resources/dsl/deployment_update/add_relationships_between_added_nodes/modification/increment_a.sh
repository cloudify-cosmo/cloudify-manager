#!/bin/bash

# load current ops count (or default to 0)
a_ops_counter=$(ctx instance runtime_properties get 'a_ops_counter')
a_ops_counter=${a_ops_counter:-0}
# increment ops count
a_ops_counter=$(expr $a_ops_counter + 1)

# store updated count
ctx instance runtime_properties 'a_ops_counter' $a_ops_counter

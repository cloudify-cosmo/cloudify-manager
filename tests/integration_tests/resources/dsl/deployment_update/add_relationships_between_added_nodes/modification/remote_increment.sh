#!/bin/bash

# load current ops count (or default to 0)
target_ops_counter=$(ctx target instance runtime_properties get 'target_ops_counter')
target_ops_counter=${target_ops_counter:-0}

# increment ops count
target_ops_counter=$(expr $target_ops_counter + 1)

# store updated count
ctx target instance runtime_properties 'target_ops_counter' $target_ops_counter

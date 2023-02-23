#!/bin/bash

# load current ops count (or default to 0)
source_ops_counter_d=$(ctx target instance runtime_properties get 'target_ops_counter_de')
source_ops_counter_d=${source_ops_counter_d:-0}

# increment ops count
source_ops_counter_d=$(expr $source_ops_counter_d + 1)

# store updated count
ctx source instance runtime_properties 'source_ops_counter_d' $source_ops_counter_d

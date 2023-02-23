#!/bin/bash

# load current ops count (or default to 0)
source_ops_counter_b=$(ctx source instance runtime_properties get 'source_ops_counter_b')
source_ops_counter_b=${source_ops_counter_b:-0}

# increment ops count
source_ops_counter_b=$(expr $source_ops_counter_b + 1)

# store updated count

ctx source instance runtime_properties 'source_ops_counter_b' $source_ops_counter_b

#!/bin/bash

net_file="networkFiles/M510_FTX_TrafficSignals_Simple.xodr"
sim_time=100
demands_file="demands_m510.txt"
output_dir="output_dbs/Batch_run_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$output_dir"

for seed in {1..2}
do
    python3 -c "from ModelExample import run_model; run_model('$net_file', run_time=int($sim_time), demands='$demands_file', seed=int($seed), output_dir='$output_dir')" 
done

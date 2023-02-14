#!/bin/bash

for i in {0..19}; do
  filename="peer_${i}.txt"
  dot "peer_graphs/${filename}" -Tpng -o "peer_graphs/${filename%.*}.png"
done
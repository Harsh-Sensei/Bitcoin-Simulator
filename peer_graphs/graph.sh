#!/bin/bash

for i in {0..19}; do
  filename="peer_${i}.txt"
  dot "${filename}" -Tpng -o "${filename%.*}.png"
done
#!/bin/bash

for i in {0..9}; do
  filename="peer_${i}.txt"
  dot "peer_graphs/${filename}" -Tpdf -o "peer_graphs/${filename%.*}.pdf"
done
#!/bin/sh
# Builds landing/img/*.webp (+ og/icons) from docs/screenshots (sample data + CC0 covers only).
set -e
S=docs/screenshots; O=landing/img
w() { ffmpeg -v error -y -i "$S/$1.png" -vf "scale=$3:-2" -c:v libwebp -quality 78 -compression_level 6 "$O/$2.webp"; }
for t in light dark; do
  w lista-cuadricula-$t-desktop hero-$t 1200
  w lista-cuadricula-$t-desktop hero-$t-720 720
  w detalle-$t-mobile hero-m-$t 260
  for v in detalle planificador compra filtros lista-una lista-info; do w $v-$t-desktop g-$v-$t 960; w $v-$t-desktop g-$v-$t-480 480; done
  for v in lista detalle compra; do w $v-$t-mobile m-$v-$t 300; done
done
ffmpeg -v error -y -i $S/lista-cuadricula-light-desktop.png -vf "crop=1440:756:0:0,scale=1200:630" -q:v 3 $O/og.jpg

export function worldToScreen(x, y, v) {
  return {x:v.width/2+(x-v.cx-(y-v.cy))*32*v.scale, y:v.height/2-(x-v.cx+y-v.cy)*16*v.scale};
}
export function screenToWorld(px, py, v) {
  const a=(px-v.width/2)/(32*v.scale), b=-(py-v.height/2)/(16*v.scale);
  return {x:Math.round(v.cx+(a+b)/2),y:Math.round(v.cy+(b-a)/2)};
}

export function tileFill(tile) {
  const terrain = tile?.terrain?.value;
  if (tile?.terrain?.status === 'conflict') return '#c99a65';
  if (tile?.village?.value) return '#a5b57d';
  if (terrain?.category === 'village' && terrain?.fields?.occupied === false) return '#cfe8ae';
  if (terrain?.category === 'oasis') return '#7da982';
  return terrain ? '#b1bf91' : '#c7ccaf';
}

export function oasisAppearance(terrain) {
  if (terrain?.status !== 'known' || terrain.value?.category !== 'oasis') return null;
  const resources = terrain.value.static?.resources;
  const types = [['Lumber', 'Forest'], ['Clay', 'Clay'], ['Iron', 'Hill'], ['Crop', 'Lake']];
  const selected = types.find(([key]) => typeof resources?.[key] === 'number' && Number.isFinite(resources[key]) && resources[key] > 0);
  const occupied = terrain.value.fields?.occupied;
  return {
    resource: selected?.[0] ?? null,
    landscape: selected?.[1] ?? null,
    occupied: typeof occupied === 'boolean' ? occupied : null,
  };
}

export function villageLevel(tile) {
  if (tile?.village?.status === 'conflict') return null;
  let population;
  if (tile?.village?.status === 'known') population = tile.village.value?.population;
  else if (tile?.terrain?.status === 'known' && tile.terrain.value?.category === 'village' && tile.terrain.value.fields?.occupied === true) population = tile.terrain.value.fields.village?.population;
  if (!Number.isInteger(population) || population < 0) return null;
  return population < 100 ? 1 : population < 400 ? 2 : population < 1000 ? 3 : 4;
}

export function overviewMarkerColor(items, x, y) {
  const markers = items.filter(item => item.type === 'marker' && item.x === x && item.y === y);
  return markers.length === 1 ? markers[0].color : '#555b57';
}

export function overviewTileColor(tile, markers, x, y) {
  if (tile.village?.status === 'conflict' || tile.terrain?.status === 'conflict') return '#c77e39';
  const terrain = tile.terrain?.value;
  if (tile.village?.status === 'known' || (terrain?.category === 'village' && terrain.fields?.occupied === true)) return overviewMarkerColor(markers, x, y);
  if (terrain?.category === 'village') return '#a5c990';
  if (terrain?.category === 'oasis') return '#508963';
  if (terrain?.category === 'landscape') return '#8c9978';
  return null;
}

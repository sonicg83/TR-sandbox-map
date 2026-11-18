export function splitViewport(bounds, maxTiles=40000) {
  const {min_x,max_x,min_y,max_y}=bounds;
  if (max_x<min_x || max_y<min_y) return [];
  const width=Math.min(maxTiles,max_x-min_x+1);
  const height=Math.max(1,Math.floor(maxTiles/width));
  const result=[];
  for (let x=min_x;x<=max_x;x+=width) for(let y=min_y;y<=max_y;y+=height) {
    result.push({min_x:x,max_x:Math.min(max_x,x+width-1),min_y:y,max_y:Math.min(max_y,y+height-1)});
  }
  return result;
}

export async function fetchViewport(bounds, fetchChunk, isCurrent) {
  try {
    const pieces=await Promise.all(splitViewport(bounds).map(fetchChunk));
    return isCurrent() ? pieces.flat() : null;
  } catch (error) {
    if (!isCurrent()) return null;
    throw error;
  }
}

export function createOverviewCache(fetchWorld) {
  const entries = new Map();
  return {
    get(worldId) {
      if (!entries.has(worldId)) {
        const request = Promise.resolve().then(() => fetchWorld(worldId));
        entries.set(worldId, request);
        request.catch(() => { if (entries.get(worldId) === request) entries.delete(worldId); });
      }
      return entries.get(worldId);
    },
    invalidate(worldId) { entries.delete(worldId); },
  };
}

export function createDetailLoader(fetchDetail, show, showError) {
  let latest = 0;
  const load = async key => {
    const id = ++latest;
    try {
      const result = await fetchDetail(key);
      if (id === latest) show(result, key);
    } catch (error) {
      if (id === latest) showError(error, key);
    }
  };
  load.cancel = () => { latest++; };
  return load;
}

import {nextZoom,zoomAt} from './zoom.mjs?v=1';
import {fetchViewport,createOverviewCache,createDetailLoader} from './viewport.mjs?v=3';
import {worldToScreen,screenToWorld,tileFill,oasisAppearance,villageLevel,overviewMarkerColor,overviewTileColor} from './map.mjs?v=6';
const $ = id => document.getElementById(id), canvas=$('map'), ctx=canvas.getContext('2d');
let worlds=[], world=null, tiles=[], plan=null, selected={x:0,y:0}, drawing=false, arrowStart=null, chosenItem=null;
let view={cx:0,cy:0,width:0,height:0,scale:1}, requestId=0;
const mapImages = {};
function loadMapImage(group, name) {
  const image = new Image();
  image.onload = () => {
    // Source PNGs contain transparent margins; crop them once for consistent placement.
    const scratch = document.createElement('canvas');
    scratch.width = image.naturalWidth; scratch.height = image.naturalHeight;
    const context = scratch.getContext('2d', {willReadFrequently:true});
    context.drawImage(image, 0, 0);
    const pixels = context.getImageData(0, 0, scratch.width, scratch.height).data;
    let left=scratch.width, top=scratch.height, right=-1, bottom=-1;
    for (let y=0; y<scratch.height; y++) for (let x=0; x<scratch.width; x++) {
      if (pixels[(y*scratch.width+x)*4+3] > 8) {
        left=Math.min(left,x); right=Math.max(right,x); top=Math.min(top,y); bottom=Math.max(bottom,y);
      }
    }
    if (right >= left) mapImages[`${group}/${name}`] = {image, left, top, width:right-left+1, height:bottom-top+1};
    render();
  };
  image.src = `/static/assets/${group}/${name}.png`;
}
for (const name of ['Lake','Forest','Clay','Hill','Vulcano']) loadMapImage('landscape', name);
for (const name of ['Lumber','Clay','Iron','Crop']) loadMapImage('oasis', name);
for (const name of ['level1','level2','level3','level4']) loadMapImage('village', name);
function paintImage(asset, x, y, width, height) {
  if (!asset) return false;
  ctx.drawImage(asset.image, asset.left, asset.top, asset.width, asset.height, x, y, width, height);
  return true;
}
function paintMapObjects(objects) {
  const scale=view.scale;
  // Paint all terrain before badges so adjacent tiles cannot cover a badge.
  for (const {p, tile, terrain, matches} of objects) {
    const appearance=terrain?.category==='oasis' ? oasisAppearance(tile.terrain) : null;
    const landscape=terrain?.category==='landscape' ? terrain.static?.landscape_type : appearance?.landscape;
    ctx.save();
    if (!matches) ctx.globalAlpha=.35;
    if (landscape) paintImage(mapImages[`landscape/${landscape}`], p.x-30*scale,p.y-18*scale,60*scale,36*scale);
    ctx.restore();
  }
  for (const {p, tile, terrain, village, scanVillage, matches, filter} of objects) {
    const appearance=terrain?.category==='oasis' ? oasisAppearance(tile.terrain) : null;
    ctx.save();
    if (!matches) ctx.globalAlpha=.35;
    if (appearance?.resource) {
      const x=p.x+16*scale, y=p.y-8*scale, radius=8*scale;
      ctx.beginPath(); ctx.arc(x,y,radius,0,Math.PI*2); ctx.fillStyle='#f5f2df'; ctx.fill();
      ctx.strokeStyle=appearance.occupied===true?'#ca4038':appearance.occupied===false?'#4b9a50':'#7d8078';
      ctx.lineWidth=2*scale; ctx.stroke();
      if (!paintImage(mapImages[`oasis/${appearance.resource}`],x-5.5*scale,y-5.5*scale,11*scale,11*scale)) {
        ctx.fillStyle='#514d42'; ctx.font=`bold ${10*scale}px sans-serif`; ctx.textAlign='center'; ctx.textBaseline='middle';
        ctx.fillText({Lumber:'L',Clay:'C',Iron:'I',Crop:'W'}[appearance.resource],x,y);
      }
    }
    if (village||scanVillage) {
      const level=villageLevel(tile);
      const drawn=level && paintImage(mapImages[`village/level${level}`],p.x-28*scale,p.y-22*scale,56*scale,40*scale);
      if (!drawn) {
      ctx.font=`${Math.max(9,13*scale)}px sans-serif`; ctx.textAlign='center';
      ctx.fillStyle=(!matches||(filter&&!(village?.alliance_name||'').toLowerCase().includes(filter)))?'#abb39a':'#6d5343';
      ctx.fillText('⌂',p.x,p.y+4*scale);
      }
    }
    ctx.restore();
  }
  for (const {p, selectedTile} of objects) {
    if (selectedTile) {
      ctx.beginPath(); ctx.moveTo(p.x,p.y-16*scale); ctx.lineTo(p.x+32*scale,p.y); ctx.lineTo(p.x,p.y+16*scale); ctx.lineTo(p.x-32*scale,p.y); ctx.closePath();
      ctx.strokeStyle='#e6a73a'; ctx.lineWidth=2; ctx.stroke();
    }
  }
}

async function api(url, options={}) { const r=await fetch(url,options); const d=await r.json(); if(!r.ok) throw new Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail)); return d; }
const overviewCache=createOverviewCache(id=>api(`/api/worlds/${id}/village-overview`));
const json=(method,data)=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
function toast(s){$('toast').textContent=s;$('toast').style.display='block';setTimeout(()=>$('toast').style.display='none',3500)}
async function refreshWorlds(){worlds=await api('/api/worlds');$('worlds').replaceChildren(...worlds.map(w=>{const o=document.createElement('option');o.value=w.id;o.textContent=`${w.name} · ${w.season}`;return o}));if(worlds.length) await selectWorld(Number($('worlds').value));else render()}
async function selectWorld(id){++requestId;detailLoader.cancel();tiles=[];world=worlds.find(w=>w.id===id);if(!world)return;view.cx=0;view.cy=0;selected={x:0,y:0};$('worldName').textContent=`${world.name} / ${world.season}`;await loadPlans();loadSelectedDetail();await loadTiles()}
function bounds(){const corners=[[0,0],[view.width,0],[0,view.height],[view.width,view.height]].map(p=>screenToWorld(...p,view));return {min_x:Math.max(world.min_x,Math.min(...corners.map(p=>p.x))-2),max_x:Math.min(world.max_x,Math.max(...corners.map(p=>p.x))+2),min_y:Math.max(world.min_y,Math.min(...corners.map(p=>p.y))-2),max_y:Math.min(world.max_y,Math.max(...corners.map(p=>p.y))+2)}}
async function loadTiles(){
  const id=++requestId;
  if(!world){tiles=[];render();return}
  const b=bounds(), worldId=world.id, overview=view.scale===.1;
  if(b.min_x>b.max_x||b.min_y>b.max_y){tiles=[];render();return}
  try {
    const result=overview ? await overviewCache.get(worldId) : await fetchViewport(b,part=>api(`/api/worlds/${worldId}/tiles?${new URLSearchParams({...part,render:'true'})}`),()=>id===requestId);
    if(id!==requestId || result===null)return;
    tiles=result;render();
  }catch(e){if(id===requestId)toast(e.message)}
}
const detailLoader=createDetailLoader(
  ({worldId,x,y})=>api(`/api/worlds/${worldId}/tiles?${new URLSearchParams({min_x:x,max_x:x,min_y:y,max_y:y})}`),
  result=>showDetail(result[0] ?? null),
  error=>{$('detail').textContent=`详情加载失败：${error.message}`}
);
function loadSelectedDetail(){
  if(!world)return;
  const {x,y}=selected;
  $('coord').textContent=`${x} / ${y}`;
  $('detail').textContent='正在加载地块详情…';
  detailLoader({worldId:world.id,x,y});
}
function resize(){const r=canvas.getBoundingClientRect();view.width=r.width;view.height=r.height;canvas.width=Math.round(r.width*devicePixelRatio);canvas.height=Math.round(r.height*devicePixelRatio);ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);loadTiles()}
function renderOverview() {
  const markers=new Map();
  for (const item of plan?.items||[]) if (item.type==='marker') {
    const key=`${item.x},${item.y}`;
    if (!markers.has(key)) markers.set(key,[]);
    markers.get(key).push(item);
  }
  const conflicts=new Set();
  for (const foreground of [false, true]) for (const tile of tiles) {
    const terrain=tile.terrain?.value;
    const conflict=tile.village?.status==='conflict' || tile.terrain?.status==='conflict';
    const village=tile.village?.status==='known' || (terrain?.category==='village' && terrain.fields?.occupied===true);
    if (!conflict && !village) continue;
    if ((conflict || village) !== foreground) continue;
    const color=overviewTileColor(tile,markers.get(`${tile.x},${tile.y}`)||[],tile.x,tile.y);
    if (!color) continue;
    if (conflict) conflicts.add(`${tile.x},${tile.y}`);
    const p=worldToScreen(tile.x,tile.y,view);
    if (p.x<0||p.x>view.width||p.y<0||p.y>view.height) continue;
    ctx.fillStyle=color;
    if (foreground) { ctx.beginPath(); ctx.arc(p.x,p.y,2.5,0,Math.PI*2); ctx.fill(); }
    else ctx.fillRect(p.x-1,p.y-1,2,2);
  }
  for (const [key, items] of markers) {
    if (conflicts.has(key)) continue;
    const item=items[0], p=worldToScreen(item.x,item.y,view);
    ctx.fillStyle=overviewMarkerColor(items,item.x,item.y); ctx.beginPath(); ctx.arc(p.x,p.y,2.5,0,Math.PI*2); ctx.fill();
  }
  for (const item of plan?.items||[]) if (item.type==='arrow') {
    const from=worldToScreen(item.from.x,item.from.y,view), to=worldToScreen(item.to.x,item.to.y,view);
    ctx.strokeStyle=item.color; ctx.lineWidth=1.5; ctx.beginPath(); ctx.moveTo(from.x,from.y); ctx.lineTo(to.x,to.y); ctx.stroke();
  }
  $('zoom').textContent='10%';
}
function render(){ctx.clearRect(0,0,view.width,view.height);ctx.fillStyle='#c3cba7';ctx.fillRect(0,0,view.width,view.height);if(!world)return;if(view.scale===.1){renderOverview();return}const b=bounds(), by=new Map(tiles.map(t=>[`${t.x},${t.y}`,t]));const filter=$('filter').value.trim().toLowerCase(), objects=[];for(let x=b.min_x;x<=b.max_x;x++)for(let y=b.min_y;y<=b.max_y;y++){const p=worldToScreen(x,y,view);if(p.x < -80 || p.x > view.width+80 || p.y < -50 || p.y > view.height+50)continue;const t=by.get(`${x},${y}`),terrain=t?.terrain?.value,village=t?.village?.value,scanVillage=terrain?.category==='village'&&terrain?.fields?.occupied===true;ctx.beginPath();ctx.moveTo(p.x,p.y-16*view.scale);ctx.lineTo(p.x+32*view.scale,p.y);ctx.lineTo(p.x,p.y+16*view.scale);ctx.lineTo(p.x-32*view.scale,p.y);ctx.closePath();ctx.fillStyle=tileFill(t);const kind=$('tileFilter').value;const matches=kind==='all'||(kind==='village'&&(!!village||scanVillage))||(kind==='available'&&terrain?.available===true)||(kind==='oasis'&&terrain?.category==='oasis')||(kind==='landscape'&&terrain?.category==='landscape');if(!matches)ctx.fillStyle='#d1d5c1';ctx.fill();ctx.strokeStyle='#87947688';ctx.lineWidth=.7;ctx.stroke();objects.push({p,tile:t,terrain,village,scanVillage,matches,filter,selectedTile:x===selected.x&&y===selected.y})}paintMapObjects(objects);for(const item of plan?.items||[]){const p=worldToScreen(item.type==='marker'?item.x:item.from.x,item.type==='marker'?item.y:item.from.y,view);ctx.strokeStyle=ctx.fillStyle=item.color;if(item.type==='arrow'){const end=worldToScreen(item.to.x,item.to.y,view),angle=Math.atan2(end.y-p.y,end.x-p.x);ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(end.x,end.y);ctx.lineTo(end.x-10*Math.cos(angle-.5),end.y-10*Math.sin(angle-.5));ctx.moveTo(end.x,end.y);ctx.lineTo(end.x-10*Math.cos(angle+.5),end.y-10*Math.sin(angle+.5));ctx.stroke()}else{ctx.beginPath();ctx.arc(p.x,p.y,6,0,Math.PI*2);ctx.fill();ctx.font='12px sans-serif';ctx.textAlign='left';ctx.fillText(item.label,p.x+8,p.y-6)}}$('zoom').textContent=`${Math.round(view.scale*100)}%`}
function showDetail(tile){ $('coord').textContent=`${selected.x} / ${selected.y}`;if(!tile){$('detail').textContent='未知地块：尚无可显示的观察。';return}const format=(label,value)=>{if(!value)return `${label}：未知`;if(value.status==='conflict')return `${label}：观察冲突\n${value.candidates.map(c=>JSON.stringify(c.value)+`\n观察时间：${c.observed_at||'未知'}`).join('\n')}`;return `${label}：${JSON.stringify(value.value,null,2)}\n来源：${value.source}\n观察时间：${value.observed_at||'未知'}\n导入时间：${value.imported_at}${value.observation ? '\n扫描观察：'+JSON.stringify(value.observation,null,2) : ''}`};$('detail').textContent=format('村庄',tile.village)+'\n\n'+format('地块',tile.terrain)}
async function loadPlans(){const plans=await api(`/api/worlds/${world.id}/plans`);$('plans').replaceChildren(...plans.map(p=>{const o=document.createElement('option');o.value=p.id;o.textContent=p.name;return o}));plan=plans.length?await api(`/api/plans/${plans[0].id}`):null;renderItems();render()}
function renderItems(){ $('items').replaceChildren(...(plan?.items||[]).map(item=>{const row=document.createElement('div');row.className='row';const edit=document.createElement('button');edit.textContent=`${item.type==='marker'?'标记':'路线'}：${item.label||'未命名'}`;edit.onclick=async()=>{const label=prompt('名称',item.label);if(label===null)return;const note=prompt('备注',item.note);if(note===null)return;const color=prompt('颜色（例如 #b1513e）',item.color);if(color===null)return;Object.assign(item,{label,note,color});await savePlan()};const del=document.createElement('button');del.textContent='删除';del.onclick=async()=>{plan.items=plan.items.filter(i=>i.id!==item.id);await savePlan()};row.append(edit,del);return row}));}
async function savePlan(){if(!plan){toast('请先新建方案');return false}await api(`/api/plans/${plan.id}`,json('PUT',{name:plan.name,items:plan.items}));$('planStatus').textContent='方案已保存';renderItems();render();return true}
canvas.addEventListener('pointerdown',e=>{canvas.setPointerCapture(e.pointerId);drawing={x:e.clientX,y:e.clientY,cx:view.cx,cy:view.cy,moved:false}});
canvas.addEventListener('pointermove',e=>{if(!drawing)return;const dx=e.clientX-drawing.x,dy=e.clientY-drawing.y;if(Math.abs(dx)+Math.abs(dy)>3&&!drawing.moved){drawing.moved=true;++requestId;}const a=dx/(32*view.scale),b=-dy/(16*view.scale);view.cx=drawing.cx-(a+b)/2;view.cy=drawing.cy-(b-a)/2;render()});
canvas.addEventListener('pointerup',async e=>{if(!drawing)return;const moved=drawing.moved;drawing=false;if(moved){loadTiles();return}const rect=canvas.getBoundingClientRect();const point=screenToWorld(e.clientX-rect.left,e.clientY-rect.top,view);if(!world||point.x<world.min_x||point.x>world.max_x||point.y<world.min_y||point.y>world.max_y)return;selected=point;loadSelectedDetail();chosenItem=plan?.items.find(i=>i.type==='marker'&&i.x===selected.x&&i.y===selected.y)?.id||null;if(arrowStart){const label=prompt('路线名称','路线');if(label!==null){plan.items.push({id:crypto.randomUUID(),type:'arrow',from:arrowStart,to:{...selected},label,color:'#b1513e',note:''});await savePlan()}arrowStart=null}$('x').value=selected.x;$('y').value=selected.y;render()});
function changeZoom(direction, point) {
  view=zoomAt(view,nextZoom(view.scale,direction),point);
  $('zoomIn').disabled=view.scale>=1;
  $('zoomOut').disabled=view.scale<=.1;
  render();
  loadTiles();
}
$('zoomIn').onclick=()=>changeZoom(1,{x:view.width/2,y:view.height/2});
$('zoomOut').onclick=()=>changeZoom(-1,{x:view.width/2,y:view.height/2});
$('centerOrigin').onclick=()=>{view.cx=0;view.cy=0;loadTiles()};
canvas.addEventListener('wheel',e=>{e.preventDefault();if (!e.deltaY) return;const rect=canvas.getBoundingClientRect();changeZoom(e.deltaY<0?1:-1,{x:e.clientX-rect.left,y:e.clientY-rect.top})},{passive:false});
$('worlds').onchange=()=>selectWorld(Number($('worlds').value));$('newWorld').onclick=async()=>{const name=prompt('服务器名称');if(!name)return;const season=prompt('世界或赛季标识');if(!season)return;const max=Number(prompt('地图坐标最大绝对值（例如 200）','200'));if(!Number.isInteger(max)||max<1)return;try{await api('/api/worlds',json('POST',{name,season,min_x:-max,max_x:max,min_y:-max,max_y:max,wrap:false}));await refreshWorlds();$('worlds').value=worlds.at(-1).id;await selectWorld(Number($('worlds').value))}catch(e){toast(e.message)}};
$('import').onclick=async()=>{if(!world||!$('file').files.length){toast('请选择服务器和文件');return}const f=new FormData();f.append('kind',$('kind').value);f.append('file',$('file').files[0]);if($('observed').value)f.append('observed_at',new Date($('observed').value).toISOString());$('importStatus').textContent='正在导入…';try{const r=await api(`/api/worlds/${world.id}/imports`,{method:'POST',body:f});overviewCache.invalidate(world.id);loadSelectedDetail();$('importStatus').textContent=`已导入 ${r.success} 条；服务器归属由用户确认。`;await loadTiles()}catch(e){$('importStatus').textContent=e.message}};
$('go').onclick=()=>{if(!world)return;const x=Number($('x').value),y=Number($('y').value);if(!Number.isInteger(x)||!Number.isInteger(y)||x<world.min_x||x>world.max_x||y<world.min_y||y>world.max_y){toast('坐标超出范围');return}selected={x,y};view.cx=x;view.cy=y;loadSelectedDetail();loadTiles()};$('filter').oninput=render;
$('search').onkeydown=async e=>{if(e.key!=='Enter'||!world)return;const matches=await api(`/api/worlds/${world.id}/search?${new URLSearchParams({q:e.target.value})}`);$('results').replaceChildren(...matches.map(m=>{const b=document.createElement('button');b.textContent=`${m.village_name} · ${m.player_name} (${m.x}|${m.y}) · ${m.conflict?'观察冲突':m.observed_at||'时间未知'}`;b.onclick=()=>{$('x').value=m.x;$('y').value=m.y;$('go').click()};return b}))};
$('newPlan').onclick=async()=>{if(!world)return;const name=prompt('方案名称');if(!name)return;try{const p=await api(`/api/worlds/${world.id}/plans`,json('POST',{name}));await loadPlans();$('plans').value=p.id;plan=await api(`/api/plans/${p.id}`);renderItems();render()}catch(e){toast(e.message)}};$('plans').onchange=async()=>{plan=await api(`/api/plans/${$('plans').value}`);renderItems();render()};$('mark').onclick=async()=>{if(!plan){toast('请先新建方案');return}const label=prompt('标记名称');if(label===null)return;const note=prompt('备注','')??'';plan.items.push({id:crypto.randomUUID(),type:'marker',...selected,label,color:'#b1513e',note});await savePlan()};$('arrow').onclick=()=>{if(!plan){toast('请先新建方案');return}arrowStart={...selected};toast('已选择起点，请点击终点')};$('tileFilter').onchange=render;
new ResizeObserver(resize).observe(canvas);refreshWorlds().catch(e=>toast(e.message));

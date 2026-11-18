import {test} from 'node:test';
import assert from 'node:assert/strict';
import {worldToScreen, screenToWorld} from '../trmap/static/map.mjs';

test('coordinates round trip after pan and zoom', () => {
  for (const scale of [0.5, 1, 2]) for (const [x,y] of [[0,0],[-2,4],[200,-200]]) {
    const view = {cx: 17, cy: -23, width: 1000, height: 700, scale};
    const p = worldToScreen(x,y,view);
    assert.deepEqual(screenToWorld(p.x,p.y,view), {x,y});
  }
});

test('only confirmed unoccupied villages use the light green fill', async () => {
  const {tileFill} = await import('../trmap/static/map.mjs');
  const empty = {terrain:{status:'known',value:{category:'village',fields:{occupied:false}}}};
  assert.equal(tileFill(empty), '#cfe8ae');
  assert.notEqual(tileFill({terrain:{status:'known',value:{category:'village',fields:{}}}}), '#cfe8ae');
  assert.notEqual(tileFill({terrain:{status:'known',value:{category:'oasis',fields:{occupied:false}}}}), '#cfe8ae');
  assert.notEqual(tileFill({...empty, village:{value:{}}}), '#cfe8ae');
  assert.notEqual(tileFill({terrain:{status:'conflict'}}), '#cfe8ae');
});

test('oasis appearance maps the first positive resource to its matching landscape', async () => {
  const {oasisAppearance} = await import('../trmap/static/map.mjs');
  const value = (resources, occupied) => ({status:'known', value:{category:'oasis', static:{resources}, fields:{occupied}}});
  for (const [resource, landscape] of [['Lumber','Forest'],['Clay','Clay'],['Iron','Hill'],['Crop','Lake']]) {
    assert.deepEqual(oasisAppearance(value({[resource]:25}, false)), {resource, landscape, occupied:false});
  }
  assert.deepEqual(oasisAppearance(value({Crop:25,Iron:25,Clay:25,Lumber:25}, true)), {resource:'Lumber', landscape:'Forest', occupied:true});
});

test('oasis appearance retains unknown resource and occupancy and excludes conflicts', async () => {
  const {oasisAppearance} = await import('../trmap/static/map.mjs');
  assert.deepEqual(oasisAppearance({status:'known',value:{category:'oasis',static:{resources:null},fields:{}}}), {resource:null,landscape:null,occupied:null});
  assert.deepEqual(oasisAppearance({status:'known',value:{category:'oasis',static:{resources:{Lumber:0,Clay:0,Iron:0,Crop:0}},fields:{occupied:'false'}}}), {resource:null,landscape:null,occupied:null});
  assert.equal(oasisAppearance({status:'conflict'}), null);
  assert.equal(oasisAppearance({status:'known',value:{category:'village'}}), null);
  assert.equal(oasisAppearance(null), null);
});

 test('overview shows observed terrain and retains conflict and village colors', async () => {
  const {overviewTileColor} = await import('../trmap/static/map.mjs');
  const tile = category => ({terrain:{status:'known', value:{category, fields:{occupied:false}}}});
  for (const category of ['village','oasis','landscape']) assert.ok(overviewTileColor(tile(category), [], 0, 0));
  assert.equal(overviewTileColor({terrain:{status:'conflict'}}, [], 0, 0), '#c77e39');
  assert.equal(overviewTileColor({village:{status:'known'}}, [], 0, 0), '#555b57');
  assert.equal(overviewTileColor({}, [], 0, 0), null);
});

import {test} from 'node:test';
import assert from 'node:assert/strict';
import * as map from '../trmap/static/map.mjs';

test('village level is based only on a known observed population', () => {
  for (const [population, expected] of [[0,1],[99,1],[100,2],[399,2],[400,3],[999,3],[1000,4]]) {
    assert.equal(map.villageLevel({village:{status:'known',value:{population}}}), expected);
  }
  assert.equal(map.villageLevel({village:{status:'known',value:{population:null}}}), null);
  assert.equal(map.villageLevel({village:{status:'conflict'}}), null);
  assert.equal(map.villageLevel({terrain:{status:'known',value:{category:'village',fields:{occupied:true,village:{population:120}}}}}), 2);
  assert.equal(map.villageLevel({terrain:{status:'known',value:{category:'village',fields:{occupied:false,village:{population:120}}}}}), null);
});

test('overview marker colors require exactly one matching marker', () => {
  assert.equal(map.overviewMarkerColor([{type:'marker',x:1,y:2,color:'#ff0000'}],1,2),'#ff0000');
  assert.equal(map.overviewMarkerColor([],1,2),'#555b57');
  assert.equal(map.overviewMarkerColor([{type:'marker',x:1,y:2,color:'#ff0000'},{type:'marker',x:1,y:2,color:'#00ff00'}],1,2),'#555b57');
});

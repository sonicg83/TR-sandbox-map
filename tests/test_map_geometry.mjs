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

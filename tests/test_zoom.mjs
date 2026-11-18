import {test} from 'node:test';
import assert from 'node:assert/strict';
import {nextZoom, zoomAt} from '../trmap/static/zoom.mjs';

test('zoom steps have 10%, 50% and 100% bounds', () => {
  assert.equal(nextZoom(1, -1), .5);
  assert.equal(nextZoom(.5, -1), .1);
  assert.equal(nextZoom(.1, -1), .1);
  assert.equal(nextZoom(.1, 1), .5);
  assert.equal(nextZoom(.5, 1), 1);
  assert.equal(nextZoom(1, 1), 1);
});

test('zoom anchors the same point of the world to the pointer', () => {
  const view = {cx: 8, cy: -2, width: 800, height: 600, scale: 1};
  const point = {x: 520, y: 240};
  const coords = (v) => {
    const a = (point.x-v.width/2)/(32*v.scale), b = -(point.y-v.height/2)/(16*v.scale);
    return [v.cx+(a+b)/2, v.cy+(b-a)/2];
  };
  const after = zoomAt(view, .5, point);
  assert.deepEqual(coords(after), coords(view));
  assert.deepEqual(zoomAt(view, .1, {x:400,y:300}), {...view,scale:.1});
});

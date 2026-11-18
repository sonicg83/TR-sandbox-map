import {test} from 'node:test';
import assert from 'node:assert/strict';
import {splitViewport, fetchViewport} from '../trmap/static/viewport.mjs';

test('partitions a large viewport without gaps, overlaps or oversized requests', () => {
  const bounds={min_x:-250,max_x:250,min_y:-200,max_y:200};
  const parts=splitViewport(bounds);
  const points=new Set();
  for (const p of parts) {
    assert.ok((p.max_x-p.min_x+1)*(p.max_y-p.min_y+1)<=40000);
    for(let x=p.min_x;x<=p.max_x;x++) for(let y=p.min_y;y<=p.max_y;y++) {
      const key=`${x},${y}`; assert.ok(!points.has(key)); points.add(key);
    }
  }
  assert.equal(points.size, 501*401);
  assert.ok(points.has('-250,-200')); assert.ok(points.has('250,200'));
});

test('merges chunks and discards obsolete viewport results', async () => {
  const bounds={min_x:0,max_x:400,max_y:100,min_y:0};
  let current=true;
  const resolvers=[];
  const pending=fetchViewport(bounds, part => new Promise(resolve => {resolvers.push(()=>resolve([part]));}),()=>current);
  current=false; resolvers.forEach(resolve=>resolve());
  assert.equal(await pending, null);
  const rows=await fetchViewport({min_x:0,max_x:400,max_y:100,min_y:0}, async part=>[part],()=>true);
  assert.equal(rows.length,2);
});

test('does not surface errors from an obsolete viewport', async () => {
  let current=true, rejectPending;
  const result=fetchViewport({min_x:0,max_x:0,min_y:0,max_y:0},()=>new Promise((_, reject)=>{rejectPending=reject}),()=>current);
  current=false; rejectPending(new Error('stale'));
  assert.equal(await result,null);
  await assert.rejects(fetchViewport({min_x:0,max_x:0,min_y:0,max_y:0},()=>Promise.reject(new Error('current')),()=>true), /current/);
});

 test('overview cache reuses requests and invalidation fetches fresh data', async () => {
  const {createOverviewCache} = await import('../trmap/static/viewport.mjs');
  let calls=0; const cache=createOverviewCache(async id => { calls++; return [id,calls]; });
  assert.deepEqual(await cache.get(1), [1,1]);
  assert.deepEqual(await cache.get(1), [1,1]);
  assert.deepEqual(await cache.get(2), [2,2]);
  cache.invalidate(1);
  assert.deepEqual(await cache.get(1), [1,3]);
});

 test('detail loader ignores stale results and stale failures', async () => {
  const {createDetailLoader} = await import('../trmap/static/viewport.mjs');
  const pending=[], shown=[], errors=[];
  const loader=createDetailLoader(key=>new Promise((resolve,reject)=>pending.push({resolve,reject})), value=>shown.push(value), error=>errors.push(error.message));
  const a=loader('a'), b=loader('b');
  pending[1].resolve('new'); await b; pending[0].resolve('old'); await a;
  assert.deepEqual(shown,['new']);
  const c=loader('c'), d=loader('d');
  pending[2].reject(new Error('stale')); await c; pending[3].resolve('current'); await d;
  assert.deepEqual(errors,[]); assert.deepEqual(shown,['new','current']);
});

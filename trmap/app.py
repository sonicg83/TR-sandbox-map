from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import sqlite3

from fastapi import FastAPI, HTTPException, UploadFile, Form, File, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, model_validator

from trmap.db import connect
from trmap.imports.sql import parse_map_sql
from trmap.imports.scan import parse_scan_json, normalize_time

mimetypes.add_type('text/javascript', '.mjs')


class World(BaseModel):
    name: str
    season: str
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    wrap: bool = False

    @model_validator(mode='after')
    def validate_world(self):
        if not self.name.strip() or not self.season.strip() or self.min_x > self.max_x or self.min_y > self.max_y:
            raise ValueError('invalid world')
        if self.wrap:
            raise ValueError('world wrap is not supported yet')
        return self


class Plan(BaseModel):
    name: str
    items: list[dict] = []


def create_app(database_path: Path) -> FastAPI:
    app = FastAPI()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
    app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)

    @app.middleware('http')
    async def same_origin(request: Request, call_next):
        origin = request.headers.get('origin')
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail':'Cross-origin request rejected'}, status_code=403)
        return await call_next(request)
    static_path = Path(__file__).parent / 'static'
    app.mount('/static', StaticFiles(directory=static_path), name='static')

    @app.get('/')
    def index():
        return FileResponse(static_path / 'index.html')
    with connect(database_path):
        pass

    @app.post('/api/worlds', status_code=201)
    def create_world(world: World):
        try:
            with connect(database_path) as db:
                cursor = db.execute('INSERT INTO worlds (name,season,min_x,max_x,min_y,max_y,wrap) VALUES (?,?,?,?,?,?,?)', tuple(world.model_dump().values()))
                return {'id': cursor.lastrowid}
        except sqlite3.IntegrityError:
            raise HTTPException(422, 'duplicate world')

    @app.get('/api/worlds')
    def worlds():
        with connect(database_path) as db:
            return [dict(row) for row in db.execute('SELECT * FROM worlds ORDER BY id')]

    @app.post('/api/worlds/{world_id}/imports', status_code=201)
    async def import_data(world_id: int, kind: str = Form(), file: UploadFile = File(), observed_at: str = Form(''), complete_snapshot: bool = Form(False)):
        if kind not in ('map_sql', 'scan_json'):
            raise HTTPException(422, 'Unsupported import type')
        try:
            timestamp = None
            if observed_at:
                dt = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    raise ValueError('Observation time needs timezone')
                timestamp = dt.astimezone(timezone.utc).isoformat()
            raw = await file.read(50_000_001)
            if len(raw) > 50_000_000:
                raise ValueError('File exceeds 50 MB')
            metadata = None
            if kind == 'scan_json':
                metadata, records = parse_scan_json(raw.decode('utf-8-sig'))
            else:
                records = parse_map_sql(raw.decode('utf-8-sig'))
            with connect(database_path) as db:
                world = db.execute('SELECT * FROM worlds WHERE id=?', (world_id,)).fetchone()
                if world is None:
                    raise HTTPException(404, 'World not found')
                if any(not (world['min_x'] <= r['x'] <= world['max_x'] and world['min_y'] <= r['y'] <= world['max_y']) for r in records):
                    raise ValueError('Coordinates outside world')
                digest = hashlib.sha256(raw).hexdigest()
                existing = db.execute('SELECT id FROM imports WHERE world_id=? AND kind=? AND sha256=? AND observed_at IS ?', (world_id,kind,digest,timestamp)).fetchone()
                if existing:
                    raise HTTPException(409, detail={'message':'Already imported','id':existing['id']})
                cursor = db.execute('INSERT INTO imports(world_id,kind,sha256,imported_at,observed_at,complete_snapshot,metadata) VALUES (?,?,?,?,?,?,?)', (world_id,kind,digest,datetime.now(timezone.utc).isoformat(),timestamp,complete_snapshot,json.dumps(metadata,ensure_ascii=False) if metadata is not None else None))
                db.executemany('INSERT INTO observations(import_id,x,y,payload) VALUES (?,?,?,?)', [(cursor.lastrowid,r['x'],r['y'],json.dumps(r,ensure_ascii=False)) for r in records])
                return {'id':cursor.lastrowid,'success':len(records),'skipped':0,'conflicts':0,'errors':0}
        except (ValueError, UnicodeError, sqlite3.IntegrityError) as exc:
            raise HTTPException(422, str(exc))

    @app.get('/api/worlds/{world_id}/imports')
    def list_imports(world_id: int):
        with connect(database_path) as db:
            return [{**dict(row), 'metadata': json.loads(row['metadata']) if row['metadata'] else None} for row in db.execute('SELECT * FROM imports WHERE world_id=? ORDER BY id DESC', (world_id,))]

    def read_tiles(world_id: int, min_x: int, max_x: int, min_y: int, max_y: int, overview: bool = False, selected_x: int | None = None, selected_y: int | None = None, village_only: bool = False, render: bool = False):
        if max_x < min_x or max_y < min_y or (not village_only and (max_x-min_x+1)*(max_y-min_y+1) > 40000):
            raise HTTPException(422, 'Invalid or oversized viewport')
        with connect(database_path) as db:
            if village_only:
                rows = db.execute('''WITH candidates AS (
                    SELECT DISTINCT o.x,o.y FROM observations o JOIN imports i ON i.id=o.import_id
                    WHERE i.world_id=? AND (i.kind='map_sql' OR (
                        json_extract(o.payload,'$.kind')='village' AND EXISTS (
                            SELECT 1 FROM json_each(o.payload,'$.observations') j
                            WHERE json_type(j.value,'$.fields.occupied')='true'))))
                    SELECT o.x,o.y,o.payload,i.id AS batch_id,i.kind,i.observed_at,i.imported_at
                    FROM candidates c JOIN observations o ON o.x=c.x AND o.y=c.y
                    JOIN imports i ON i.id=o.import_id WHERE i.world_id=?''', (world_id,world_id)).fetchall()
            else:
                rows = db.execute('''SELECT o.x,o.y,o.payload,i.id AS batch_id,i.kind,i.observed_at,i.imported_at
                    FROM observations o JOIN imports i ON i.id=o.import_id
                    WHERE i.world_id=? AND o.x BETWEEN ? AND ? AND o.y BETWEEN ? AND ?''', (world_id,min_x,max_x,min_y,max_y)).fetchall()
        grouped = {}
        for row in rows:
            tile = grouped.setdefault((row['x'], row['y']), {'x':row['x'], 'y':row['y'], 'village':None, 'terrain':None})
            field = 'village' if row['kind'] == 'map_sql' else 'terrain'
            payload = json.loads(row['payload'])
            if row['kind'] == 'scan_json':
                for obs in payload['observations'] or [None]:
                    fields = obs['fields'] if obs else {}
                    value = {'x': payload['x'], 'y': payload['y'], 'category': payload['kind'], 'static': payload['static'], 'fields': fields}
                    resources = payload['static'].get('resources')
                    if resources is not None:
                        value.update(resources)
                    if payload['kind'] == 'landscape':
                        value['type'] = payload['static']['landscape_type']
                    if type(fields.get('occupied')) is bool:
                        value['available'] = not fields['occupied']
                    tile.setdefault('_'+field, []).append({'value':value, 'observed_at':normalize_time(obs.get('observed_at')) if obs and obs.get('observed_at') else row['observed_at'], 'imported_at':row['imported_at'], 'batch_id':row['batch_id'], 'source':row['kind'], 'observation':obs})
            else:
                tile.setdefault('_'+field, []).append({'value':payload, 'observed_at':row['observed_at'], 'imported_at':row['imported_at'], 'batch_id':row['batch_id'], 'source':row['kind']})
        for tile in grouped.values():
            for field in ('village', 'terrain'):
                candidates = tile.pop('_'+field, [])
                if not candidates:
                    continue
                if len(candidates) == 1:
                    tile[field] = {**candidates[0], 'status':'known'}
                elif all(c['value'] == candidates[0]['value'] for c in candidates):
                    dated = [c for c in candidates if c['observed_at'] is not None]
                    best = max(dated, key=lambda c:c['observed_at']) if dated else candidates[0]
                    tile[field] = {**best, 'status':'known', 'candidates':candidates}
                elif any(c['observed_at'] is None for c in candidates):
                    tile[field] = {'status':'conflict', 'candidates':candidates}
                else:
                    newest = max(c['observed_at'] for c in candidates)
                    latest = [c for c in candidates if c['observed_at'] == newest]
                    tile[field] = {**latest[0], 'status':'known'} if all(c['value'] == latest[0]['value'] for c in latest) else {'status':'conflict','candidates':latest}
        if render:
            def render_tile(tile):
                result = {'x': tile['x'], 'y': tile['y'], 'village': None, 'terrain': None}
                for field in ('village', 'terrain'):
                    observation = tile[field]
                    if not observation:
                        continue
                    result[field] = {'status': observation['status']}
                    if observation['status'] != 'known':
                        continue
                    value = observation['value']
                    if field == 'village':
                        result[field]['value'] = {key: value.get(key) for key in ('population', 'alliance_name')}
                    else:
                        fields = value['fields']
                        village = fields.get('village')
                        render_fields = {'occupied': fields.get('occupied')}
                        if isinstance(village, dict):
                            render_fields['village'] = {'population': village.get('population')}
                        render_value = {'category': value['category'], 'fields': render_fields,
                                        'static': {key: value['static'].get(key) for key in ('resources', 'landscape_type')}}
                        if 'available' in value:
                            render_value['available'] = value['available']
                        result[field]['value'] = render_value
                return result
            return JSONResponse([render_tile(tile) for tile in grouped.values()])
        if overview:
            def compact(tile):
                if tile['x'] == selected_x and tile['y'] == selected_y:
                    return tile
                result = {'x': tile['x'], 'y': tile['y'], 'village': None, 'terrain': None}
                for field in ('village', 'terrain'):
                    observation = tile[field]
                    if observation:
                        result[field] = {'status': observation['status']}
                        if field == 'terrain' and observation['status'] == 'known':
                            value = observation['value']
                            result[field]['value'] = {'category': value['category'], 'fields': {'occupied': value['fields'].get('occupied')}}
                return result
            return JSONResponse([compact(tile) for tile in grouped.values()])
        return list(grouped.values())

    @app.get('/api/worlds/{world_id}/tiles')
    def tiles(world_id: int, min_x: int, max_x: int, min_y: int, max_y: int, overview: bool = False, selected_x: int | None = None, selected_y: int | None = None, render: bool = False):
        return read_tiles(world_id, min_x, max_x, min_y, max_y, overview, selected_x, selected_y, render=render)

    @app.get('/api/worlds/{world_id}/village-overview')
    def village_overview(world_id: int):
        with connect(database_path) as db:
            world = db.execute('SELECT min_x,max_x,min_y,max_y FROM worlds WHERE id=?', (world_id,)).fetchone()
        if world is None:
            raise HTTPException(404, 'World not found')
        return read_tiles(world_id, world['min_x'], world['max_x'], world['min_y'], world['max_y'], overview=True, village_only=True)

    @app.get('/api/worlds/{world_id}/search')
    def search(world_id: int, q: str):
        if not q.strip() or len(q)>100:
            return []
        with connect(database_path) as db:
            rows = db.execute('''SELECT o.x,o.y,o.payload,i.observed_at FROM observations o JOIN imports i ON i.id=o.import_id
                WHERE i.world_id=? AND i.kind='map_sql' ''', (world_id,)).fetchall()
        groups = {}
        for row in rows:
            groups.setdefault((row['x'],row['y']), []).append(row)
        result = []
        for candidates in groups.values():
            unknown = any(c['observed_at'] is None for c in candidates)
            latest = candidates if unknown else [c for c in candidates if c['observed_at'] == max(r['observed_at'] for r in candidates)]
            conflicting = len({c['payload'] for c in latest}) > 1
            for row in latest:
                data = json.loads(row['payload'])
                if any(q.casefold() in str(data.get(k) or '').casefold() for k in ('village_name','player_name','alliance_name')):
                    result.append({**data, 'observed_at':row['observed_at'], 'conflict':conflicting})
                    break
            if len(result) == 50:
                break
        return result

    @app.get('/api/worlds/{world_id}/plans')
    def list_plans(world_id: int):
        with connect(database_path) as db:
            return [dict(row) for row in db.execute('SELECT id,name FROM plans WHERE world_id=?', (world_id,))]

    @app.post('/api/worlds/{world_id}/plans', status_code=201)
    def create_plan(world_id: int, plan: Plan):
        if not plan.name.strip() or len(plan.name) > 100 or plan.items:
            raise HTTPException(422, 'Invalid plan')
        try:
            with connect(database_path) as db:
                cursor = db.execute('INSERT INTO plans(world_id,name) VALUES (?,?)', (world_id,plan.name))
                return {'id':cursor.lastrowid}
        except sqlite3.IntegrityError:
            raise HTTPException(404, 'World not found')

    @app.get('/api/plans/{plan_id}')
    def get_plan(plan_id: int):
        with connect(database_path) as db:
            row = db.execute('SELECT * FROM plans WHERE id=?', (plan_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Plan not found')
            return {**dict(row), 'items':json.loads(row['items'])}

    @app.put('/api/plans/{plan_id}')
    def save_plan(plan_id: int, plan: Plan):
        with connect(database_path) as db:
            world = db.execute('SELECT worlds.* FROM worlds JOIN plans ON plans.world_id=worlds.id WHERE plans.id=?', (plan_id,)).fetchone()
            if not world:
                raise HTTPException(404, 'Plan not found')
            if not plan.name.strip() or len(plan.name)>100 or len(plan.items)>5000:
                raise HTTPException(422, 'Invalid plan')
            ids = set()
            for item in plan.items:
                if not isinstance(item.get('id'), str) or item['id'] in ids or item.get('type') not in ('marker','arrow'):
                    raise HTTPException(422, 'Invalid item')
                ids.add(item['id'])
                if any(not isinstance(item.get(k), str) or len(item[k]) > 2000 for k in ('label','color','note')):
                    raise HTTPException(422, 'Invalid item text')
                points = [item] if item['type'] == 'marker' else [item.get('from'),item.get('to')]
                for point in points:
                    if not isinstance(point, dict) or type(point.get('x')) is not int or type(point.get('y')) is not int or not(world['min_x']<=point['x']<=world['max_x'] and world['min_y']<=point['y']<=world['max_y']):
                        raise HTTPException(422, 'Invalid coordinates')
            db.execute('UPDATE plans SET name=?,items=? WHERE id=?', (plan.name,json.dumps(plan.items,ensure_ascii=False),plan_id))
            return {'ok':True}

    return app


app = create_app(Path('data/trmap.sqlite3'))

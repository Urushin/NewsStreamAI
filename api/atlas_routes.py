"""Attributed, cache-bounded data adapters for the shared web/iOS Atlas.

Every returned observation is supplied by the named provider or omitted.
Unavailable credentials produce an explicit unavailable state, never demo data.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import math
import os
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from fastapi import APIRouter, HTTPException, Query

atlas_router = APIRouter(prefix="/api/atlas", tags=["atlas"])
_cache: dict[str, dict[str, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}
_root = Path(__file__).resolve().parent.parent


def _iso(value: Any, milliseconds: bool = False) -> str | None:
    try:
        number = float(value) / (1000 if milliseconds else 1)
        return datetime.fromtimestamp(number, timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return str(value) if isinstance(value, str) and value else None


def _point(lon: Any, lat: Any) -> bool:
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lon, lat)) and -180 <= lon <= 180 and -90 <= lat <= 90


def _result(layer: str, provider: str, status: str = "unavailable", note: str = "") -> dict[str, Any]:
    return {"id": layer, "provider": provider, "status": status, "events": [], "paths": [], "fetched_at": None, "note": note}


def _provider_name(name: str) -> str:
    return {"earthquakes":"USGS","nature":"NASA EONET","weather":"GDACS","fires":"NASA FIRMS","flights":"OpenSky Network","ships":"AISStream","society":"ACLED / World Monitor","military":"World Monitor","nuclear":"GeoJSON local","cables":"GeoJSON local","pipelines":"GeoJSON local"}.get(name, name)


async def _cached(name: str, ttl: int, loader: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
    now = time.monotonic(); cached = _cache.get(name)
    if cached and now - cached["attempted"] < ttl: return cached["result"]
    async with _locks.setdefault(name, asyncio.Lock()):
        cached = _cache.get(name)
        if cached and time.monotonic() - cached["attempted"] < ttl: return cached["result"]
        try: result = await loader()
        except Exception:
            stale = cached.get("last_good") if cached else None
            result = {**stale, "status":"stale", "note":"Source momentanément indisponible. Dernier relevé conservé."} if stale else _result(name, _provider_name(name), note="Source momentanément indisponible.")
        result["refresh_seconds"] = ttl
        last_good = result if result.get("status") in {"live","limited","static"} else cached.get("last_good") if cached else None
        _cache[name] = {"attempted":time.monotonic(), "result":result, "last_good":last_good}
        return result


async def _json_get(url: str, headers: dict[str, str] | None = None, timeout: float = 15) -> Any:
    base = {"User-Agent":"NewsStreamAI-Atlas/2.0", "Accept":"application/json"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers={**base, **(headers or {})}) as client:
        response = await client.get(url); response.raise_for_status(); return response.json()


async def _earthquakes() -> dict[str, Any]:
    data = await _json_get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"); events=[]
    for feature in data.get("features", [])[:1000]:
        props, coords = feature.get("properties") or {}, (feature.get("geometry") or {}).get("coordinates") or []
        if len(coords)<2 or not _point(coords[0],coords[1]): continue
        magnitude=props.get("mag")
        events.append({"id":f"usgs:{feature.get('id')}","layer":"earthquakes","title":props.get("title") or "Séisme","summary":f"Magnitude {magnitude} · profondeur {coords[2] if len(coords)>2 else '—'} km","latitude":coords[1],"longitude":coords[0],"magnitude":magnitude,"timestamp":_iso(props.get("time"),True),"location_name":props.get("place"),"source_name":"USGS","source_url":props.get("url")})
    return {**_result("earthquakes","USGS","live","Séismes M2,5+ des dernières 24 heures."),"events":events,"fetched_at":datetime.now(timezone.utc).isoformat()}


def _weather_subtype(text: str) -> str:
    value=text.lower()
    if any(w in value for w in ("cyclone","typhoon","hurricane","storm")): return "cyclone"
    if "flood" in value: return "flood"
    if any(w in value for w in ("wildfire","fire")): return "fire"
    if "volcano" in value: return "volcano"
    if any(w in value for w in ("heat","drought")): return "heat"
    if any(w in value for w in ("snow","winter","cold")): return "snow"
    return "weather"


def _eonet_events(data: dict[str, Any]) -> list[dict[str, Any]]:
    events=[]
    for item in data.get("events", [])[:300]:
        points=[g for g in item.get("geometry",[]) if g.get("type")=="Point"]
        if not points: continue
        point=max(points,key=lambda g:g.get("date") or ""); coords=point.get("coordinates") or []
        if len(coords)<2 or not _point(coords[0],coords[1]): continue
        categories=[c.get("title","") for c in item.get("categories",[])]; sources=item.get("sources") or []
        events.append({"id":f"eonet:{item.get('id')}","layer":"nature","title":item.get("title") or "Événement naturel","summary":item.get("description") or ", ".join(categories),"category":", ".join(categories),"subtype":_weather_subtype(" ".join(categories)),"latitude":coords[1],"longitude":coords[0],"timestamp":point.get("date"),"source_name":"NASA EONET","source_url":sources[0].get("url") if sources else item.get("link")})
    return events


async def _nature() -> dict[str, Any]:
    data=await _json_get("https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=14&limit=300")
    return {**_result("nature","NASA EONET","live","Événements naturels ouverts des 14 derniers jours."),"events":_eonet_events(data),"fetched_at":datetime.now(timezone.utc).isoformat()}


async def _weather() -> dict[str, Any]:
    data=await _json_get("https://www.gdacs.org/contentdata/xml/gdacsAPP_Home.geojson",headers={"Accept":"*/*"}); events=[]
    for feature in data.get("features",[])[:500]:
        props,geometry=feature.get("properties") or {},feature.get("geometry") or {}; coords=geometry.get("coordinates") or []
        if coords and isinstance(coords[0],list): coords=coords[0]
        if geometry.get("type")!="Point" or len(coords)<2 or not _point(coords[0],coords[1]) or str(props.get("eventtype") or "")=="EQ": continue
        event_type=str(props.get("eventtype") or "")
        links=props.get("url") or props.get("link"); source_url=links if isinstance(links,str) else next((entry.get("Value") for entry in (links or []) if entry.get("Key")=="web"),None)
        events.append({"id":f"gdacs:{event_type}:{props.get('eventid')}","layer":"weather","title":props.get("title") or props.get("name") or "Alerte naturelle","summary":props.get("description") or props.get("alertlevel") or "Alerte GDACS","subtype":{"TC":"cyclone","FL":"flood","WF":"fire","VO":"volcano","DR":"heat"}.get(event_type,"weather"),"severity":str(props.get("alertlevel") or "").lower(),"latitude":coords[1],"longitude":coords[0],"location_name":props.get("country"),"country_code":props.get("iso3"),"timestamp":props.get("todate") or props.get("fromdate"),"source_name":"GDACS","source_url":source_url})
    return {**_result("weather","GDACS","live","Alertes et catastrophes publiées par GDACS."),"events":events,"fetched_at":datetime.now(timezone.utc).isoformat()}


async def _fires() -> dict[str, Any]:
    key=os.getenv("NASA_FIRMS_MAP_KEY","").strip()
    if not key:
        data=await _json_get("https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=14&limit=300")
        events=[dict(event,id=event["id"].replace("eonet:","eonet-fire:"),layer="fires",subtype="fire") for event in _eonet_events(data) if "fire" in (event.get("category") or "").lower()]
        return {**_result("fires","NASA EONET","limited","Incendies déclarés par EONET. Ajoutez NASA_FIRMS_MAP_KEY pour les détections satellite FIRMS."),"events":events,"fetched_at":datetime.now(timezone.utc).isoformat()}
    url=f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_NOAA20_NRT/world/1"
    async with httpx.AsyncClient(timeout=30,follow_redirects=False,headers={"User-Agent":"NewsStreamAI-Atlas/2.0"}) as client:
        response=await client.get(url); response.raise_for_status()
    rows=list(csv.DictReader(io.StringIO(response.text))); stride=max(1,math.ceil(len(rows)/1200)); events=[]
    for index,row in enumerate(rows[::stride]):
        try: lat,lon=float(row["latitude"]),float(row["longitude"])
        except (KeyError,ValueError): continue
        if not _point(lon,lat): continue
        raw_time=str(row.get("acq_time","")).zfill(4); acquired=f"{row.get('acq_date','')}T{raw_time[:2]}:{raw_time[2:]}:00Z"
        events.append({"id":f"firms:{row.get('satellite')}:{row.get('acq_date')}:{row.get('acq_time')}:{index}","layer":"fires","title":"Feu détecté par satellite","summary":f"Confiance {row.get('confidence','—')} · puissance radiative {row.get('frp','—')} MW","subtype":"fire","latitude":lat,"longitude":lon,"timestamp":acquired,"source_name":"NASA FIRMS","source_url":"https://firms.modaps.eosdis.nasa.gov/"})
    return {**_result("fires","NASA FIRMS","live",f"{len(rows)} détections, échantillonnées à {len(events)} points."),"events":events,"fetched_at":datetime.now(timezone.utc).isoformat()}


async def _flights() -> dict[str, Any]:
    data=await _json_get("https://opensky-network.org/api/states/all"); observed=data.get("time") or time.time(); events=[]
    for state in data.get("states") or []:
        if not isinstance(state,list) or len(state)<11 or not _point(state[5],state[6]) or state[8] or not isinstance(state[3],(int,float)) or observed-state[3]>180: continue
        events.append({"id":f"opensky:{state[0]}","layer":"flights","title":(state[1] or state[0]).strip(),"summary":f"{state[2]} · {round(state[7]) if isinstance(state[7],(int,float)) else '—'} m","latitude":state[6],"longitude":state[5],"heading":state[10],"timestamp":_iso(state[3]),"source_name":"OpenSky Network","source_url":"https://opensky-network.org/"})
    events.sort(key=lambda item:item["id"]); stride=max(1,math.ceil(len(events)/700))
    return {**_result("flights","OpenSky Network","live","Échantillon de 700 positions ADS-B maximum."),"events":events[::stride],"fetched_at":datetime.now(timezone.utc).isoformat()}


async def _ships() -> dict[str, Any]:
    key=os.getenv("AISSTREAM_API_KEY","").strip()
    if not key:
        data=await _json_get("https://meri.digitraffic.fi/api/ais/v1/locations",headers={"Digitraffic-User":"NewsStreamAI/2.0"}); events=[]
        features=data.get("features") or []; stride=max(1,math.ceil(len(features)/700))
        for feature in features[::stride]:
            props,coords=feature.get("properties") or {},(feature.get("geometry") or {}).get("coordinates") or []
            if len(coords)<2 or not _point(coords[0],coords[1]): continue
            mmsi=str(feature.get("mmsi") or props.get("mmsi") or "")
            if not mmsi: continue
            events.append({"id":f"digitraffic:{mmsi}","layer":"ships","title":f"Navire {mmsi}","summary":f"AIS · {props.get('sog','—')} nœuds", "latitude":coords[1],"longitude":coords[0],"heading":props.get("heading") or props.get("cog"),"speed_knots":props.get("sog"),"timestamp":_iso(props.get("timestampExternal"),True) or data.get("dataUpdatedTime"),"source_name":"Fintraffic Digitraffic","source_url":"https://www.digitraffic.fi/en/marine-traffic/"})
        return {**_result("ships","Fintraffic Digitraffic","limited","Positions AIS en direct des eaux finlandaises. Ajoutez AISSTREAM_API_KEY pour une couverture terrestre mondiale."),"events":events,"fetched_at":data.get("dataUpdatedTime") or datetime.now(timezone.utc).isoformat()}
    import websockets
    events: dict[str,dict[str,Any]]={}
    async with websockets.connect("wss://stream.aisstream.io/v0/stream",open_timeout=10,close_timeout=2) as socket:
        await socket.send(json.dumps({"APIKey":key,"BoundingBoxes":[[[-90,-180],[90,180]]],"FilterMessageTypes":["PositionReport","StandardClassBPositionReport","ExtendedClassBPositionReport"]}))
        deadline=time.monotonic()+6
        while time.monotonic()<deadline and len(events)<500:
            try: envelope=json.loads(await asyncio.wait_for(socket.recv(),timeout=max(.1,deadline-time.monotonic())))
            except asyncio.TimeoutError: break
            metadata=envelope.get("MetaData") or {}; message=envelope.get("Message") or {}; report=next((v for v in message.values() if isinstance(v,dict) and "Latitude" in v),None)
            if not report: continue
            lat,lon=report.get("Latitude"),report.get("Longitude")
            if not _point(lon,lat): continue
            mmsi=str(metadata.get("MMSI") or report.get("UserID") or "")
            if not mmsi: continue
            events[mmsi]={"id":f"ais:{mmsi}","layer":"ships","title":metadata.get("ShipName") or f"Navire {mmsi}","summary":f"MMSI {mmsi}","latitude":lat,"longitude":lon,"heading":report.get("TrueHeading"),"speed_knots":report.get("Sog"),"timestamp":metadata.get("time_utc") or datetime.now(timezone.utc).isoformat(),"source_name":"AISStream","source_url":"https://aisstream.io/"}
    return {**_result("ships","AISStream","live","Instantané AIS collecté pendant 6 secondes ; couverture terrestre partielle."),"events":list(events.values()),"fetched_at":datetime.now(timezone.utc).isoformat()}


async def _society() -> dict[str, Any]:
    if os.getenv("WORLDMONITOR_API_KEY","").strip():
        return await _worldmonitor("society","/api/unrest/v1/list-unrest-events?page_size=100","events")
    async with httpx.AsyncClient(timeout=25,follow_redirects=True,headers={"User-Agent":"NewsStreamAI-Atlas/2.0"}) as client:
        index=await client.get("https://data.gdeltproject.org/gdeltv2/lastupdate.txt"); index.raise_for_status()
        export_url=next((line.split()[2] for line in index.text.splitlines() if len(line.split())>=3 and line.split()[2].endswith(".export.CSV.zip")),None)
        if not export_url: raise ValueError("Flux GDELT export introuvable")
        archive=await client.get(export_url.replace("http://","https://")); archive.raise_for_status()
    events=[]
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
        filename=next(name for name in zipped.namelist() if name.lower().endswith(".csv"))
        with zipped.open(filename) as raw:
            reader=csv.reader(io.TextIOWrapper(raw,encoding="utf-8",errors="replace"),delimiter="\t")
            for row in reader:
                if len(row)<61 or row[28]!="14": continue
                try: lat,lon=float(row[56]),float(row[57])
                except (ValueError,IndexError): continue
                if not _point(lon,lat): continue
                try: timestamp=datetime.strptime(row[59],"%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()
                except ValueError: timestamp=datetime.now(timezone.utc).isoformat()
                actors=" ↔ ".join(filter(None,(row[6],row[16])))
                location=row[52] or row[36] or row[43] or "Lieu identifié par GDELT"
                events.append({"id":f"gdelt-protest:{row[0]}","layer":"society","title":f"Manifestation · {location}","summary":f"Événement de protestation GDELT{f' · {actors}' if actors else ''}","latitude":lat,"longitude":lon,"location_name":location,"country_code":row[53] or None,"timestamp":timestamp,"source_name":"GDELT 2.0","source_url":row[60] or None})
                if len(events)>=300: break
    return {**_result("society","GDELT 2.0","live","Manifestations géolocalisées dans le dernier relevé mondial GDELT (15 minutes)."),"events":events,"fetched_at":datetime.now(timezone.utc).isoformat()}


async def _worldmonitor(layer: str, endpoint: str, collection: str) -> dict[str, Any]:
    key=os.getenv("WORLDMONITOR_API_KEY","").strip()
    if not key: return _result(layer,"World Monitor",note="Ajoutez WORLDMONITOR_API_KEY côté serveur pour activer cette couche.")
    data=await _json_get(f"https://api.worldmonitor.app{endpoint}",headers={"X-WorldMonitor-Key":key}); raw=data.get(collection) or []; events=[]
    for index,item in enumerate(raw):
        loc=item.get("location") or {}; lat=item.get("lat",item.get("latitude",loc.get("latitude"))); lon=item.get("lon",item.get("longitude",loc.get("longitude")))
        if not _point(lon,lat): continue
        events.append({"id":f"wm:{layer}:{item.get('id',index)}","layer":layer,"title":item.get("name") or item.get("title") or item.get("city") or layer,"summary":item.get("description") or item.get("eventType") or item.get("kind") or "","latitude":lat,"longitude":lon,"timestamp":_iso(item.get("detectedAt") or item.get("startAt") or item.get("updatedAt"),True),"country_code":item.get("country"),"source_name":"World Monitor","source_url":"https://worldmonitor.app/","operator":item.get("operator"),"kind":item.get("kind")})
    return {**_result(layer,"World Monitor","live",f"{len(events)} observations fournies par l’API World Monitor."),"events":events,"fetched_at":datetime.now(timezone.utc).isoformat()}


async def _local_geojson(layer: str) -> dict[str, Any]:
    path=_root/"data"/"atlas"/f"{layer}.geojson"
    if not path.exists(): return _result(layer,"GeoJSON local",note=f"Ajoutez data/atlas/{layer}.geojson pour activer cette couche.")
    data=json.loads(path.read_text(encoding="utf-8")); paths=[]; events=[]
    for index,feature in enumerate(data.get("features",[])):
        geometry,props=feature.get("geometry") or {},feature.get("properties") or {}; coords=geometry.get("coordinates")
        if geometry.get("type")=="Point" and coords and _point(coords[0],coords[1]):
            events.append({"id":f"local:{layer}:{index}","layer":layer,"title":props.get("name") or layer,"summary":props.get("description") or "","latitude":coords[1],"longitude":coords[0],"source_name":props.get("source") or "GeoJSON local","source_url":props.get("source_url")})
        elif geometry.get("type") in {"LineString","MultiLineString"}:
            lines=coords if geometry.get("type")=="MultiLineString" else [coords]
            for line_index,line in enumerate(lines or []):
                points=[[pt[1],pt[0]] for pt in line if len(pt)>=2 and _point(pt[0],pt[1])]
                if len(points)>1: paths.append({"id":f"local:{layer}:{index}:{line_index}","layer":layer,"name":props.get("name") or layer,"points":points})
    return {**_result(layer,"GeoJSON local","static",f"Données chargées depuis {path.name}."),"events":events,"paths":paths,"fetched_at":datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()}


_LOADERS: dict[str,tuple[int,Callable[[],Awaitable[dict[str,Any]]]]] = {
    "earthquakes":(300,_earthquakes),"nature":(600,_nature),"weather":(600,_weather),"fires":(600,_fires),"flights":(120,_flights),"ships":(120,_ships),
    "society":(600,_society),
    "military":(86400,lambda:_worldmonitor("military","/api/military/v1/list-military-bases?zoom=3","bases")),
    "nuclear":(86400,lambda:_local_geojson("nuclear")),"cables":(86400,lambda:_local_geojson("cables")),"pipelines":(86400,lambda:_local_geojson("pipelines")),
}


@atlas_router.get("/layers")
async def get_atlas_layers(include: str = Query("earthquakes,nature,weather")):
    selected=list(dict.fromkeys(name.strip() for name in include.split(",") if name.strip())); unknown=[name for name in selected if name not in _LOADERS]
    if unknown: raise HTTPException(400,f"Unknown layer(s): {', '.join(unknown)}")
    layers=await asyncio.gather(*(_cached(name,*_LOADERS[name]) for name in selected))
    return {"layers":layers,"generated_at":datetime.now(timezone.utc).isoformat()}

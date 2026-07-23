#!/usr/bin/env python3
"""Update the site's MRT/restaurant JSON using OpenStreetMap Overpass."""
from __future__ import annotations
import argparse, json, math, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINTS=["https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter"]
# OSM maps future stations early. Keep the public picker on operational MRT only.
# Review this set when LTA opens a new line or infill station.
NON_OPERATIONAL={
  "Aviation Park","Bahar Junction","Bedok South","Bukit Batok West","Bukit Brown",
  "Choa Chu Kang West","Corporation","Defu","Elias","Enterprise","Founders' Memorial",
  "Gek Poh","Hong Kah","Jurong Hill","Jurong Pier","Jurong Town Hall","Jurong West",
  "Loyang","Maju","Marina South","Mount Pleasant","Nanyang Crescent","Nanyang Gateway",
  "Pandan Reservoir","Pasir Ris East","Peng Kang Hill","Serangoon North","Sungei Bedok",
  "Tampines North","Tavistock","Tawas","Teck Ghee","Tengah","Tengah Park",
  "Tengah Plantation","Toh Guan","Tukang","Turf City","West Coast","Xilin"
}
NOT_MRT={"Riviera","Samudera","VivoCity","Woodlands Train Checkpoint"}
FOOD_COURT_MARKERS={
  "hawker","food court","foodcourt","food centre","food center","coffee shop",
  "coffeeshop","kopitiam","koufu","food republic","food junction","foodfare",
  "malaysia boleh","cantine","broadway","kimly","happy hawkers","food opera",
  "rasapura masters","fork & spoon","foodclique","food loft","makan place",
  "makanplace","al makan"
}
def fetch(q,endpoints):
  payload=urlencode({"data":q}).encode(); last=None
  for attempt in range(3):
    for endpoint in endpoints:
      try:
        with urlopen(Request(endpoint,data=payload,headers={"User-Agent":"MakanNextStop/1.0"}),timeout=180) as r:return json.load(r)
      except (HTTPError,URLError,TimeoutError) as e:last=e
    time.sleep(2**attempt)
  raise RuntimeError(f"Overpass request failed: {last}")
def pos(e):
  c=e.get("center",e); return float(c["lat"]),float(c["lon"])
def dist(a,b):
  a1,o1,a2,o2=map(math.radians,(*a,*b)); h=math.sin((a2-a1)/2)**2+math.cos(a1)*math.cos(a2)*math.sin((o2-o1)/2)**2
  return round(12742000*math.asin(math.sqrt(h)))
def eid(prefix,e):return f"{prefix}-{e['type']}-{e['id']}"
def is_food_court(tags,name):
  text=" ".join(str(tags.get(k,"")) for k in ("amenity","cuisine","brand","operator","description"))
  normalized=" ".join((name+" "+text).lower().replace("_"," ").replace("-"," ").split())
  return any(marker in normalized for marker in FOOD_COURT_MARKERS)
def main():
  p=argparse.ArgumentParser();p.add_argument("--radius",type=int,default=500);p.add_argument("--output",type=Path,default=Path("public/data/restaurants.json"));p.add_argument("--endpoint",action="append");p.add_argument("--min-restaurants",type=int,default=0);a=p.parse_args(); endpoints=a.endpoint or ENDPOINTS
  sq='''[out:json][timeout:120];area["ISO3166-1"="SG"][admin_level=2]->.sg;(nwr(area.sg)["railway"="station"]["station"="subway"];nwr(area.sg)["public_transport"="station"]["train"="yes"];);out center tags;'''
  rq='''[out:json][timeout:180];area["ISO3166-1"="SG"][admin_level=2]->.sg;nwr(area.sg)["amenity"="restaurant"]["name"];out center tags;'''
  print("Fetching MRT stations and restaurants…",file=sys.stderr); raw_s=fetch(sq,endpoints)["elements"]; raw_r=fetch(rq,endpoints)["elements"]
  station_map={}
  for e in raw_s:
    t=e.get("tags",{}); n=t.get("name:en") or t.get("name")
    clean=(n or "").replace(" MRT Station","")
    if n and "depot" not in n.lower() and clean not in NON_OPERATIONAL|NOT_MRT:station_map.setdefault(clean.lower().strip(),e)
  restaurants=[]; excluded=[]
  for e in raw_r:
    t=e.get("tags",{});n=t.get("name:en") or t.get("name")
    if not n:continue
    if is_food_court(t,n):excluded.append(n);continue
    try:lat,lon=pos(e)
    except KeyError:continue
    house=" ".join(filter(None,[t.get("addr:housenumber"),t.get("addr:street")]))
    restaurants.append(((lat,lon),{"id":eid("restaurant",e),"name":n,"nameZh":t.get("name:zh"),"address":t.get("addr:full") or ", ".join(filter(None,[house,t.get("addr:postcode"),"Singapore"])),"cuisine":(t.get("cuisine") or "").replace(";",", ").replace("_"," ").title(),"openingHours":t.get("opening_hours",""),"lat":lat,"lon":lon}))
  stations=[]
  for e in station_map.values():
    t=e.get("tags",{});lat,lon=pos(e);n=(t.get("name:en") or t.get("name")).replace(" MRT Station","");near=[]
    for rp,r in restaurants:
      m=dist((lat,lon),rp)
      if m<=a.radius:near.append({**r,"distanceM":m})
    near.sort(key=lambda x:(x["distanceM"],x["name"]))
    if len(near)>=a.min_restaurants:stations.append({"id":eid("station",e),"name":n,"nameZh":t.get("name:zh"),"lines":[],"lat":lat,"lon":lon,"restaurants":near})
  stations.sort(key=lambda x:x["name"]); result={"updatedAt":datetime.now(timezone.utc).isoformat(),"source":"© OpenStreetMap contributors / Overpass API","radiusM":a.radius,"stations":stations}
  a.output.parent.mkdir(parents=True,exist_ok=True);tmp=a.output.with_suffix(".tmp");tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");os.replace(tmp,a.output)
  print(f"Excluded {len(excluded)} food-court or hawker-centre records",file=sys.stderr)
  print(f"Wrote {len(stations)} stations / {sum(len(s['restaurants']) for s in stations)} matches to {a.output}",file=sys.stderr)
if __name__=="__main__":main()

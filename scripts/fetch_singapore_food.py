#!/usr/bin/env python3
"""Update the site's MRT/restaurant JSON using OpenStreetMap Overpass."""
from __future__ import annotations
import argparse, calendar, json, math, os, sys, time
from datetime import date, datetime, timezone
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
def is_permanently_closed(tags,name,today=None):
  today=today or date.today()
  closed_values={"yes","true","1","closed","permanently_closed","permanently closed","disused","abandoned","demolished"}
  for key in ("closed","disused","abandoned","demolished","operational_status","status"):
    if str(tags.get(key,"")).strip().lower() in closed_values:return True
  opening=" ".join(str(tags.get("opening_hours","")).lower().replace("_"," ").split())
  if opening in {"closed","off","permanently closed"}:return True
  normalized_name=" ".join(name.lower().replace("_"," ").replace("-"," ").split())
  if any(marker in normalized_name for marker in ("permanently closed","closed permanently","已永久关闭")):return True
  end_date=str(tags.get("end_date","")).strip()
  if end_date:
    try:
      parts=[int(part) for part in end_date.split("-")]
      month=parts[1] if len(parts)>1 else 12
      day=parts[2] if len(parts)>2 else calendar.monthrange(parts[0],month)[1]
      ended=date(parts[0],month,day)
      if ended<=today:return True
    except (ValueError,IndexError):pass
  return False
def normalize_name(name):
  return " ".join(name.casefold().replace("_"," ").replace("-"," ").split())
def load_closed_list(path):
  if not path.exists():return set(),set()
  data=json.loads(path.read_text(encoding="utf-8"))
  return set(data.get("osmIds",[])),{normalize_name(name) for name in data.get("names",[]) if name.strip()}
def main():
  p=argparse.ArgumentParser();p.add_argument("--radius",type=int,default=500);p.add_argument("--output",type=Path,default=Path("public/data/restaurants.json"));p.add_argument("--closed-list",type=Path,default=Path("data/closed-restaurants.json"));p.add_argument("--endpoint",action="append");p.add_argument("--min-restaurants",type=int,default=0);a=p.parse_args(); endpoints=a.endpoint or ENDPOINTS
  closed_ids,closed_names=load_closed_list(a.closed_list)
  sq='''[out:json][timeout:120];area["ISO3166-1"="SG"][admin_level=2]->.sg;(nwr(area.sg)["railway"="station"]["station"="subway"];nwr(area.sg)["public_transport"="station"]["train"="yes"];);out center tags;'''
  rq='''[out:json][timeout:180];area["ISO3166-1"="SG"][admin_level=2]->.sg;nwr(area.sg)["amenity"="restaurant"]["name"];out center tags;'''
  print("Fetching MRT stations and restaurants…",file=sys.stderr); raw_s=fetch(sq,endpoints)["elements"]; raw_r=fetch(rq,endpoints)["elements"]
  station_map={}
  for e in raw_s:
    t=e.get("tags",{}); n=t.get("name:en") or t.get("name")
    clean=(n or "").replace(" MRT Station","")
    if n and "depot" not in n.lower() and clean not in NON_OPERATIONAL|NOT_MRT:station_map.setdefault(clean.lower().strip(),e)
  restaurants=[]; excluded=[]; excluded_closed=[]; excluded_manually=[]
  for e in raw_r:
    t=e.get("tags",{});n=t.get("name:en") or t.get("name")
    if not n:continue
    if is_food_court(t,n):excluded.append(n);continue
    if is_permanently_closed(t,n):excluded_closed.append(n);continue
    restaurant_id=eid("restaurant",e)
    if restaurant_id in closed_ids or normalize_name(n) in closed_names:excluded_manually.append(n);continue
    try:lat,lon=pos(e)
    except KeyError:continue
    house=" ".join(filter(None,[t.get("addr:housenumber"),t.get("addr:street")]))
    restaurants.append(((lat,lon),{"id":restaurant_id,"name":n,"nameZh":t.get("name:zh"),"address":t.get("addr:full") or ", ".join(filter(None,[house,t.get("addr:postcode"),"Singapore"])),"cuisine":(t.get("cuisine") or "").replace(";",", ").replace("_"," ").title(),"openingHours":t.get("opening_hours",""),"lat":lat,"lon":lon}))
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
  print(f"Excluded {len(excluded_closed)} permanently closed restaurant records",file=sys.stderr)
  print(f"Excluded {len(excluded_manually)} restaurants from {a.closed_list}",file=sys.stderr)
  print(f"Wrote {len(stations)} stations / {sum(len(s['restaurants']) for s in stations)} matches to {a.output}",file=sys.stderr)
if __name__=="__main__":main()

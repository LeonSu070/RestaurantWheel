"use client";

import { useEffect, useRef, useState } from "react";

type Restaurant={id:string;name:string;nameZh?:string;address:string;cuisine:string;openingHours:string;lat:number;lon:number;distanceM:number};
type Station={id:string;name:string;nameZh?:string;lines:string[];lat:number;lon:number;restaurants:Restaurant[]};
type Dataset={updatedAt:string;source:string;radiusM:number;stations:Station[]};
type Phase="station-ready"|"station-spin"|"restaurant-ready"|"restaurant-spin"|"done";

const copy={
  en:{eyebrow:"Singapore food roulette",title1:"Your next meal.",title2:"One stop away.",sub:"Leave lunch to the MRT. Pick a station, then let the neighbourhood choose your table.",step:"Current journey",startStation:"Roll a station",stopStation:"Stop at this station",startFood:"Roll a restaurant",stopFood:"That's the one",again:"Start a new journey",placeholder:"Ready when you are",empty:"Your restaurant details will appear here.",address:"Address",hours:"Opening hours",cuisine:"Cuisine",map:"Open in Google Maps",updated:"Data updated",near:"nearby restaurants",station:"station",restaurant:"restaurant"},
  zh:{eyebrow:"新加坡美食轮盘",title1:"下一顿饭，",title2:"只差一站。",sub:"把午餐交给地铁。先抽一个地铁站，再让附近街区替你选餐厅。",step:"当前旅程",startStation:"抽一个地铁站",stopStation:"就选这个地铁站",startFood:"抽一家餐厅",stopFood:"就是这家",again:"重新开始",placeholder:"准备好就出发",empty:"选中餐厅后，详细信息会显示在这里。",address:"地址",hours:"营业时间",cuisine:"菜系",map:"在 Google 地图中打开",updated:"数据更新于",near:"家附近餐厅",station:"地铁站",restaurant:"餐厅"}
};

export default function Picker({data}:{data:Dataset}){
 const [lang,setLang]=useState<"en"|"zh">("en"),[phase,setPhase]=useState<Phase>("station-ready"),[station,setStation]=useState<Station|null>(null),[restaurant,setRestaurant]=useState<Restaurant|null>(null),[display,setDisplay]=useState("");
 const timer=useRef<ReturnType<typeof setInterval>|null>(null); const current=useRef<Station|Restaurant|null>(null); const t=copy[lang];
 useEffect(()=>()=>{if(timer.current)clearInterval(timer.current)},[]);
 const name=(x:{name:string;nameZh?:string})=>lang==="zh"&&x.nameZh?x.nameZh:x.name;
 function shuffled<T>(items:T[]){const result=[...items];for(let i=result.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[result[i],result[j]]=[result[j],result[i]]}return result}
 function spin(items:(Station|Restaurant)[]){
   let order=shuffled(items),index=0,last:Station|Restaurant|null=null;
   const show=(item:Station|Restaurant)=>{current.current=item;last=item;setDisplay(name(item))}; show(order[index]);
   timer.current=setInterval(()=>{index++;if(index>=order.length){order=shuffled(items);if(order.length>1&&order[0]===last)[order[0],order[1]]=[order[1],order[0]];index=0}show(order[index])},85)
 }
 function stop(kind:"station"|"restaurant"){if(timer.current)clearInterval(timer.current);timer.current=null;const picked=current.current;if(!picked)return;setDisplay(name(picked));if(kind==="station"){setStation(picked as Station);setPhase("restaurant-ready")}else{setRestaurant(picked as Restaurant);setPhase("done")}}
 function act(){if(phase==="station-ready"){setRestaurant(null);setStation(null);setPhase("station-spin");spin(data.stations)}else if(phase==="station-spin")stop("station");else if(phase==="restaurant-ready"&&station){setPhase("restaurant-spin");spin(station.restaurants)}else if(phase==="restaurant-spin"&&station)stop("restaurant");else{setPhase("station-ready");setStation(null);setRestaurant(null);current.current=null;setDisplay("")}}
 const label={"station-ready":t.startStation,"station-spin":t.stopStation,"restaurant-ready":t.startFood,"restaurant-spin":t.stopFood,done:t.again}[phase];
 const active=phase.includes("spin"); const shown=display||(station?name(station):t.placeholder);
 return <main className="shell"><header className="topbar"><div className="brand"><span className="brandmark">◎</span> MAKAN NEXT STOP</div><button className="lang" onClick={()=>setLang(lang==="en"?"zh":"en")} aria-label="Switch language">{lang==="en"?"中文":"EN"}</button></header><section className="main"><div className="eyebrow">{t.eyebrow}</div><h1>{t.title1}<br/><em>{t.title2}</em></h1><p className="sub">{t.sub}</p><div className="board"><section className="picker" aria-live="polite"><div className="step"><span>{t.step}</span><span>{phase.startsWith("station")?`01 — ${t.station}`:`02 — ${t.restaurant}`}</span></div><div className={`rolling ${active?"active":""}`}>{shown}</div><div><div className="lines" aria-hidden="true"><i className="line on"/><i className={`line ${station?"on":""}`}/><i className={`line ${restaurant?"on":""}`}/></div><button className="action" onClick={act}>{active?"■ ":"● "}{label}</button></div></section><aside className="details">{restaurant?<><span className="tag">{station&&name(station)} · {restaurant.distanceM}m</span><h2>{name(restaurant)}</h2><div className="info"><span>⌖</span><div><b>{t.address}</b>{restaurant.address}</div></div><div className="info"><span>◷</span><div><b>{t.hours}</b>{restaurant.openingHours||"—"}</div></div><div className="info"><span>♨</span><div><b>{t.cuisine}</b>{restaurant.cuisine||"—"}</div></div><div className="info"><span>↗</span><div><a className="map" target="_blank" rel="noreferrer" href={`https://www.google.com/maps/search/?api=1&query=${restaurant.lat},${restaurant.lon}`}>{t.map}</a></div></div></>:<div className="empty"><div className="empty-icon">⌖</div><b>{station?`${station.restaurants.length} ${t.near}`:t.placeholder}</b><p>{t.empty}</p></div>}</aside></div><footer className="foot"><span>{data.stations.length} MRT stops · {data.stations.reduce((n,s)=>n+s.restaurants.length,0)} restaurants</span><span>{t.updated} {new Date(data.updatedAt).toLocaleDateString(lang==="zh"?"zh-SG":"en-SG")}</span></footer></section></main>
}

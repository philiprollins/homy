export const $=id=>document.getElementById(id);
export const fmt=(v,u='')=>v==null?'Unavailable':Number(v).toFixed(2)+' '+u;
export const get=async url=>{const r=await fetch(url);if(!r.ok)throw Error('Request failed: '+r.status);return r.json()};
export const enc=encodeURIComponent;
export function cards(id,items){$(id).replaceChildren(...items.map(([label,value])=>{const d=document.createElement('div');d.className='card';const s=document.createElement('span');s.textContent=label;const b=document.createElement('strong');b.textContent=value;d.append(s,b);return d}))}
export function setStatus(text,stale=false){const s=$('status');if(!s)return;s.textContent=text;s.className=stale?'stale':''}

// Max gap between readings before a chart line breaks; refined from /api/system/health.
export let gap=30;
get('/api/system/health').then(h=>{gap=h.max_gap_seconds}).catch(()=>{});

// Wraps an async refresh so overlapping calls coalesce into one follow-up run.
export function serial(fn){let busy=false,pending=false;return async function run(){if(busy){pending=true;return}busy=true;try{await fn()}finally{busy=false;if(pending){pending=false;run()}}}}

// History range selector, persisted across views.
export const RANGES=[['1','Last hour'],['24','Last 24 hours'],['168','Last 7 days'],['720','Last 30 days']];
export const hours=()=>localStorage.getItem('homy.range')||'24';
export function rangeSelect(onchange){const s=document.createElement('select');s.setAttribute('aria-label','History range');for(const [v,t] of RANGES){const o=new Option(t,v);o.selected=v===hours();s.append(o)}s.onchange=()=>{localStorage.setItem('homy.range',s.value);onchange()};return s}

export function chart(title,rows,key,chartGap=gap,span_hours=Number(hours())){
 const div=document.createElement('div');div.className='chart';
 const label=document.createElement('p');label.textContent=title;div.append(label);
 const legend=document.createElement('div');legend.className='chart-legend';
 const swatch=document.createElement('span');swatch.className='chart-swatch';swatch.setAttribute('aria-hidden','true');
 legend.append(swatch,document.createTextNode(title+' · UTC'));div.append(legend);
 const values=rows.filter(r=>Number.isFinite(r[key])&&Number.isFinite(Date.parse(r.timestamp)));
 if(values.length<2){const empty=document.createElement('div');empty.className='chart-empty';empty.textContent=values.length?'Collecting history — the next reading starts your chart.':'History will appear as readings arrive.';div.append(empty);return div}
 let low=Infinity,high=-Infinity;for(const r of values){low=Math.min(low,r[key]);high=Math.max(high,r[key])}
 if(low===high){const padding=Math.max(Math.abs(low)*.02,.1);low-=padding;high+=padding}
 const last=Math.max(Date.now(),Date.parse(values.at(-1).timestamp)),first=Math.min(last-span_hours*3600000,Date.parse(values[0].timestamp)),span=last-first||1;
 const unit=title.match(/\(([^)]+)\)/)?.[1]||'';
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 560 220');
 svg.setAttribute('role','img');svg.setAttribute('aria-label',title+' over time, '+new Date(first).toISOString()+' to '+new Date(last).toISOString());
 function element(tag,attrs,text){const el=document.createElementNS(svg.namespaceURI,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;svg.append(el);return el}
 for(let i=0;i<=4;i++){
  const y=15+i*40,value=high-(high-low)*i/4;
  element('line',{x1:70,x2:545,y1:y,y2:y,stroke:'#343d49','stroke-dasharray':'3 5'});
  element('text',{x:62,y:y+4,'text-anchor':'end',class:'chart-axis',fill:'#e3eaf4'},value.toFixed(2)+' '+unit);
 }
 for(let i=0;i<=2;i++){
  const x=70+475*i/2,t=first+span*i/2,d=new Date(t);
  const stamp=(span>=86400000?d.toISOString().slice(5,10)+' ':'')+d.toISOString().slice(11,16);
  element('text',{x:x,y:202,'text-anchor':i===0?'start':i===2?'end':'middle',class:'chart-axis',fill:'#e3eaf4'},stamp);
 }
 let points=[];
 const flush=()=>{if(points.length===1)element('circle',{cx:points[0][0],cy:points[0][1],r:2.5,fill:'#8ba9d4'});else if(points.length>1)element('polyline',{points:points.map(p=>p.join(',')).join(' '),fill:'none',stroke:'#8ba9d4','stroke-width':2});points=[]};
 let prev=null;
 for(const r of rows){const t=Date.parse(r.timestamp),valid=Number.isFinite(r[key])&&Number.isFinite(t);if(!valid||(prev!==null&&t-prev>chartGap*1000))flush();if(valid){points.push([70+475*(t-first)/span,175-160*(r[key]-low)/(high-low)]);prev=t}else prev=null}flush();
 div.append(svg);return div
}

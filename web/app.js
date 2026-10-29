const $=id=>document.getElementById(id);
const fmt=(v,u='')=>v==null?'Unavailable':Number(v).toFixed(2)+' '+u;
const get=async url=>{const r=await fetch(url);if(!r.ok)throw Error('Request failed: '+r.status);return r.json()};
function cards(id,items){$(id).replaceChildren(...items.map(([label,value])=>{const d=document.createElement('div');d.className='card';const s=document.createElement('span');s.textContent=label;const b=document.createElement('strong');b.textContent=value;d.append(s,b);return d}))}
function chart(title,rows,key,chartGap=gap){
 const div=document.createElement('div');div.className='chart';const label=document.createElement('p');label.textContent=title;div.append(label);
 const values=rows.filter(r=>r[key]!=null);if(values.length<2){const empty=document.createElement('div');empty.style.cssText='height:180px;display:grid;place-content:center;text-align:center;color:#8792a3';empty.textContent=values.length?'Collecting history — the next reading starts your chart.':'History will appear as readings arrive.';div.append(empty);return div}
 let low=Infinity,high=-Infinity;for(const r of values){low=Math.min(low,r[key]);high=Math.max(high,r[key])}if(low===high){low-=1;high+=1}
 const first=Date.parse(rows[0].timestamp),last=Date.parse(rows.at(-1).timestamp);
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 500 180');
 for(let i=0;i<4;i++){const y=20+i*46;const grid=document.createElementNS(svg.namespaceURI,'line');for(const [k,v] of Object.entries({x1:10,x2:490,y1:y,y2:y,stroke:'#2c333e','stroke-dasharray':'3 5'}))grid.setAttribute(k,v);svg.append(grid)}
 let points=[];const flush=()=>{if(!points.length)return;const line=document.createElementNS(svg.namespaceURI,'polyline');line.setAttribute('points',points.join(' '));line.setAttribute('fill','none');line.setAttribute('stroke','#8ba9d4');line.setAttribute('stroke-width','2');svg.append(line);points=[]};
 let prev=null;for(const r of rows){const t=Date.parse(r.timestamp);if(r[key]==null||prev&&t-prev>chartGap*1000)flush();if(r[key]!=null)points.push((10+480*(t-first)/(last-first||1))+','+(160-140*(r[key]-low)/(high-low||1)));prev=t}flush();div.append(svg,document.createTextNode(fmt(low)+' – '+fmt(high)+' · '+new Date(first).toISOString().slice(11,16)+' — '+new Date(last).toISOString().slice(11,16)+' UTC'));return div
}
let statuses=[],gap=30,busy=false,pending=false;
async function refresh(){
 if(busy){pending=true;return}busy=true;
 try{
 await refreshInverter();
 statuses=await get('/api/status');
 const bank=await get('/api/bank/summary');
 $('bank-state').textContent=(bank.source==='mock'?'SIMULATED · ':'')+(bank.complete?'ALL PACKS LIVE':'PARTIAL COVERAGE');
 $('bank-state').className='pill'+(bank.complete?'':' warning');
 cards('bank-metrics',[
 ['Bank SOC'+(bank.soc_complete?'':' · partial'),fmt(bank.soc_percent,'%')],
 ['Charging input'+(bank.power_complete?'':' · partial'),fmt(bank.input_power_w,'W')],
 ['Discharging output'+(bank.power_complete?'':' · partial'),fmt(bank.output_power_w,'W')],
 ['Net power'+(bank.power_complete?'':' · partial'),fmt(bank.net_power_w,'W')],
 ['Batteries online',bank.reporting_count+' / '+bank.configured_count],
 ['Temperature range',bank.temperature_min_c==null?'Unavailable':fmt(bank.temperature_min_c,'°C')+' – '+fmt(bank.temperature_max_c,'°C')]
 ]);
 $('bank-notice').textContent=(bank.mixed_sources?'Mixed real and simulated sources: aggregation disabled. ':bank.complete?'Fresh individual-pack readings. ':'Partial figures only; missing or stale packs excluded: '+bank.excluded_battery_ids.join(', ')+'. ')+'SOC is weighted by pack capacity and nominal voltage. Temperature coverage: '+bank.temperature_reporting_count+'/'+bank.configured_count+' packs.';
 const alarmBox=$('bank-alarms');alarmBox.replaceChildren();
 if(bank.alarms.length){for(const alarm of bank.alarms){const row=document.createElement('p');row.className='alarm-row';row.textContent=alarm.battery_name+' · '+alarm.alarm;alarmBox.append(row)}}
 else{alarmBox.textContent=bank.alarm_coverage_complete?'✓ No protection alarms reported across all packs':'Protection status incomplete · no alarms reported by available packs'}
 alarmBox.className=bank.alarms.length?'has-alarms':'';

 if(!$('battery').options.length){for(const b of statuses){const o=document.createElement('option');o.value=b.id;o.textContent=b.name;$('battery').append(o)}}
 const id=$('battery').value,b=statuses.find(b=>b.id===id);if(!b)return;
 const packReadings=await Promise.all(statuses.map(pack=>get('/api/batteries/'+encodeURIComponent(pack.id)+'/latest')));
 $('packs').replaceChildren(...statuses.map((pack,i)=>{
 const reading=packReadings[i],button=document.createElement('button');
 button.className='pack-tile'+(pack.id===id?' selected':'');
 button.setAttribute('aria-pressed',String(pack.id===id));
 const label=document.createElement('span');label.textContent=pack.name;
 const soc=document.createElement('strong');soc.textContent=reading?.soc_percent==null?'—':Math.round(reading.soc_percent)+'%';
 const detail=document.createElement('small');detail.textContent=(pack.mock?'SIMULATED · ':'')+(pack.stale?'STALE':pack.state==='connected'?'LIVE':pack.state)+' · '+fmt(reading?.power_w,'W');
 button.append(label,soc,detail);button.onclick=()=>{$('battery').value=pack.id;refresh()};return button;
 }));
 const [r,h,e]=await Promise.all([get('/api/batteries/'+encodeURIComponent(id)+'/latest'),get('/api/batteries/'+encodeURIComponent(id)+'/history?hours='+$('range').value+'&limit=100000'),get('/api/energy/daily?battery_id='+encodeURIComponent(id))]);
 $('status').textContent=(b.mock?'SIMULATED DATA · ':'')+b.state+(b.stale?' · STALE':'')+' · Last reading: '+(b.last_reading||'none')+(b.error?' · '+b.error:'');
 $('status').className=b.stale?'stale':'';
 $('soc').textContent=r?.soc_percent==null?'—':Math.round(r.soc_percent);
 $('soc-fill').style.width=(r?.soc_percent??0)+'%';
 $('activity').textContent=b.stale?'STALE':r?.current_a==null?'UNKNOWN':r.current_a>0?'CHARGING':r.current_a<0?'DISCHARGING':'IDLE';
 $('hero-power').textContent=fmt(r?.power_w,'W');
 $('power-caption').textContent=b.stale?'Last recorded power · device is stale':r?.current_a==null?'Waiting for a valid reading':r.current_a<0?'Energy is flowing out of this pack':r.current_a>0?'Energy is flowing into this pack':'No current flowing';
 $('capacity').textContent=fmt(r?.remaining_capacity_ah,'Ah')+' / '+fmt(r?.full_capacity_ah,'Ah');
 $('scope').textContent=r?.scope==='pack'?'Individual pack':'Scope unknown';
 $('flow-label').textContent=r?.current_a>0?'Charging':'Discharging';
 cards('overview',[['Pack voltage',fmt(r?.voltage_v,'V')],['Current · + charging',fmt(r?.current_a,'A')],['Warmest sensor',r?.temperatures_c?.length?fmt(Math.max(...r.temperatures_c),'°C'):'Unavailable'],['Charge cycles',r?.cycles??'Unavailable']]);
 const today=new Date().toISOString().slice(0,10),month=today.slice(0,7),day=e.find(x=>x.period===today);
 const sum=k=>e.filter(x=>x.period.startsWith(month)).reduce((a,x)=>a+x[k],0);
 cards('energy',[['Charged today',fmt(day?.charged_kwh??0,'kWh')],['Discharged today',fmt(day?.discharged_kwh??0,'kWh')],['Charged this month',fmt(sum('charged_kwh'),'kWh')],['Discharged this month',fmt(sum('discharged_kwh'),'kWh')]]);
 $('health').textContent='Scope: '+(r?.scope||'unknown')+' · Cell min/max/difference: '+[r?.cell_min_mv,r?.cell_max_mv,r?.cell_delta_mv].map(v=>fmt(v,'mV')).join(' / ')+' · Alarms: '+(r?r.alarms.join(', ')||'None reported':'Unknown');
 cards('cells',(r?.cell_voltages_mv||[]).map((v,i)=>['Cell '+(i+1),fmt(v,'mV')]));
 $('history-note').textContent=h.truncated?'Range truncated; narrow the range.':'Times shown in UTC. Lines break at missing readings.';
 $('charts').replaceChildren(...[['SOC (%)','soc_percent'],['Voltage (V)','voltage_v'],['Current (A)','current_a'],['Power (W)','power_w']].map(([t,k])=>chart(t,h.readings,k)));
 const table=document.createElement('table');for(const row of [['UTC day','Charged kWh','Discharged kWh'],...e.map(x=>[x.period,fmt(x.charged_kwh),fmt(x.discharged_kwh)])]){const tr=document.createElement('tr');for(const v of row){const td=document.createElement('td');td.textContent=v;tr.append(td)}table.append(tr)}if(e.length)$('daily').replaceChildren(table);else{const empty=document.createElement('p');empty.style.padding='15px 22px';empty.textContent='Your daily ledger starts after two valid readings. Only measured intervals count.';$('daily').replaceChildren(empty)}
 }catch(e){$('status').textContent='Dashboard disconnected · '+e.message;$('status').className='stale'}finally{busy=false;if(pending){pending=false;refresh()}}
}
$('battery').onchange=refresh;$('range').onchange=refresh;
get('/api/system/health').then(h=>{gap=h.max_gap_seconds}).catch(()=>{});refresh();setInterval(refresh,10000);const stream=new EventSource('/api/events');stream.onmessage=refresh;stream.onerror=()=>{$('status').textContent='Live connection interrupted; reconnecting…'};

function clock(){ $('clock').textContent=new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) }clock();setInterval(clock,10000);

async function refreshInverter(){
 try{
 const snapshot=await get('/api/inverter');
 $('inverter-section').hidden=!snapshot.enabled;
 if(!snapshot.enabled)return;
 const r=snapshot.reading,live=snapshot.state==='connected'&&!snapshot.stale;
 $('inverter-name').textContent=snapshot.name;
 $('inverter-state').textContent=live?'LIVE · LOCAL':'STALE / '+snapshot.state.toUpperCase();
 $('inverter-state').className='pill'+(live?'':' warning');
 $('inverter-status').textContent='Last reading: '+(r?.timestamp??'none')+(snapshot.error?' · '+snapshot.error:'')+(r?' · '+r.inverter_serial:'');
 cards('inverter-metrics',[
 ['Solar input',fmt(r?.pv_total_power_w,'W')],
 ['AC load output',fmt(r?.load_total_power_w,'W')],
 ['Battery voltage · inverter',fmt(r?.battery_voltage_v,'V')],
 ['SOC · inverter estimate',fmt(r?.inverter_reported_soc_percent,'%')],
 ['PV1 / PV2',fmt(r?.pv1_power_w,'W')+' / '+fmt(r?.pv2_power_w,'W')],
 ['Load L1',fmt(r?.load_l1_power_w,'W')],
 ['Load L2',fmt(r?.load_l2_power_w,'W')],
 ['PV voltage · 1 / 2',fmt(r?.pv1_voltage_v,'V')+' / '+fmt(r?.pv2_voltage_v,'V')]
 ]);
 const history=await get('/api/inverter/history?hours='+$('range').value+'&limit=100000');
 $('inverter-charts').replaceChildren(...[['Solar input (W)','pv_total_power_w'],['AC loads (W)','load_total_power_w']].map(([title,key])=>chart(title,history.readings,key,snapshot.max_gap_seconds)));
 $('inverter-history-note').textContent=(history.truncated?'History truncated. ':'')+'History follows the time range selected below. UTC timestamps; gaps are excluded.';
 }catch(error){$('inverter-state').textContent='CONNECTION UNAVAILABLE';$('inverter-state').className='pill warning';$('inverter-status').textContent=error.message}
}

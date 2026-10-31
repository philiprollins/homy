import {$,fmt,get,enc,cards,chart,serial,setStatus,hours,rangeSelect} from '../lib.js';
import {live} from '../live.js';

export default {
 title:'Battery',
 render(root,{id}){
  root.innerHTML=`
<div class="page-heading"><div><div class="eyebrow">ENERGY / BATTERIES</div><h1 id="battery-name">Battery</h1><p>A live view of your battery, from the inside out.</p></div><div class="device-picker"><label for="battery">MONITORING</label><select id="battery"></select></div></div>
<div id="status" role="status">Connecting to your monitor…</div>
<section class="hero">
<div class="charge-panel"><div class="panel-top"><span class="eyebrow">STATE OF CHARGE</span><span id="activity" class="pill">Waiting</span></div><div class="charge-number"><span id="soc">—</span><span class="percent">%</span></div><div class="battery-track"><div id="soc-fill"></div></div><div class="charge-footer"><span id="capacity">Capacity unavailable</span><span id="scope">Pack scope unknown</span></div></div>
<div class="hero-summary"><div class="eyebrow">RIGHT NOW</div><div class="power-number" id="hero-power">— <small>W</small></div><p id="power-caption">Waiting for a valid battery reading</p><div class="flow"><span class="flow-icon">▤</span><span class="flow-line"></span><span id="flow-label">Battery</span><span class="flow-line"></span><span class="flow-icon">⌂</span></div><div class="hero-foot">Positive power charges the pack · Negative power discharges it</div></div>
</section>
<section id="overview" class="grid metrics"></section>
<div class="section-title"><div><span class="eyebrow">THE BIGGER PICTURE</span><h2>Energy, accounted for.</h2></div><span class="subtle">UTC totals · Observed intervals only</span></div><section id="energy" class="grid energy-grid"></section>
<div class="section-title" id="history-section"><div><span class="eyebrow">PATTERNS OVER TIME</span><h2>Your battery's rhythm.</h2></div><span id="range-slot"></span></div>
<p id="history-note" class="subtle"></p><section id="charts" class="charts"></section>
<div class="section-title" id="health-section"><div><span class="eyebrow">UNDER THE SURFACE</span><h2>Every cell tells a story.</h2></div><span class="pill">CELL HEALTH</span></div>
<section class="health-panel"><div id="health"></div><section id="cells" class="cell-grid"></section><div class="cell-legend"><i></i> Individual cell voltage · Millivolts</div></section>
<div class="section-title"><div><span class="eyebrow">THE DAILY LEDGER</span><h2>Energy in. Energy out.</h2></div><span class="subtle">kWh / day</span></div><div id="daily" class="ledger"></div>`;
  const refresh=serial(async()=>{
   try{
    const statuses=await get('/api/status');
    if(!root.isConnected)return;
    const picker=$('battery');
    if(!picker.options.length){for(const s of statuses)picker.append(new Option(s.name,s.id,false,s.id===id));picker.onchange=()=>window.homy.navigate('/batteries/'+enc(picker.value))}
    const b=statuses.find(s=>s.id===id);
    if(!b){setStatus('Unknown battery “'+id+'”.',true);return}
    $('battery-name').textContent=b.name;document.title='Homy · '+b.name;
    const [r,h,e]=await Promise.all([get('/api/batteries/'+enc(id)+'/latest'),get('/api/batteries/'+enc(id)+'/history?hours='+hours()+'&limit=100000'),get('/api/energy/daily?battery_id='+enc(id))]);
    if(!root.isConnected)return;
    setStatus((b.mock?'SIMULATED DATA · ':'')+b.state+(b.stale?' · STALE':'')+' · Last reading: '+(b.last_reading||'none')+(b.error?' · '+b.error:''),b.stale);
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
   }catch(e){setStatus('Dashboard disconnected · '+e.message,true)}
  });
  $('range-slot').replaceWith(rangeSelect(refresh));
  return live(refresh);
 }
};

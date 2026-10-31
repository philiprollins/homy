import {$,fmt,get,cards,chart,serial,hours,rangeSelect} from '../lib.js';
import {live} from '../live.js';

export default {
 title:'Solar',
 render(root){
  root.innerHTML=`
<div class="page-heading"><div><div class="eyebrow">ENERGY / SOLAR &amp; AC LOADS</div><h1 id="inverter-name">Inverter</h1><p>Solar production and household load, read locally from the inverter.</p></div><span id="inverter-state" class="pill">Waiting</span></div>
<div id="status" role="status">Connecting to your inverter…</div>
<section id="inverter-section">
<div id="inverter-metrics" class="grid energy-grid"></div>
<p class="subtle">Inverter-reported SOC is separate from battery BMS SOC. AC load current is the sum of the two output legs; grid input is not yet measured.</p>
<div class="section-title"><div><span class="eyebrow">PATTERNS OVER TIME</span><h2>Sun and load.</h2></div><span id="range-slot"></span></div>
<div id="inverter-charts" class="charts"></div><p id="inverter-history-note" class="subtle"></p>
</section>`;
  const amps=v=>v==null?null:v/10;
  const refresh=serial(async()=>{
   try{
    const snapshot=await get('/api/inverter');
    if(!root.isConnected)return;
    if(!snapshot.enabled){$('inverter-section').hidden=true;$('status').textContent='No inverter is configured. Enable the inverter section in config.yaml.';return}
    const r=snapshot.reading,ok=snapshot.state==='connected'&&!snapshot.stale,l1=r?.raw_registers?.l1_current?.[0],l2=r?.raw_registers?.l2_current?.[0];
    $('inverter-name').textContent=snapshot.name;
    $('inverter-state').textContent=ok?'LIVE · LOCAL':'STALE / '+snapshot.state.toUpperCase();
    $('inverter-state').className='pill'+(ok?'':' warning');
    $('status').textContent='Last reading: '+(r?.timestamp??'none')+(snapshot.error?' · '+snapshot.error:'')+(r?' · '+r.inverter_serial:'');
    $('status').className=ok?'':'stale';
    cards('inverter-metrics',[
     ['Solar input',fmt(r?.pv_total_power_w,'W')],
     ['AC load · L1 + L2',fmt(l1==null||l2==null?null:(l1+l2)/10,'A')],
     ['Battery voltage · inverter',fmt(r?.battery_voltage_v,'V')],
     ['SOC · inverter estimate',fmt(r?.inverter_reported_soc_percent,'%')],
     ['PV1 / PV2',fmt(r?.pv1_power_w,'W')+' / '+fmt(r?.pv2_power_w,'W')],
     ['Load L1 current',fmt(amps(l1),'A')],
     ['Load L2 current',fmt(amps(l2),'A')],
     ['PV voltage · 1 / 2',fmt(r?.pv1_voltage_v,'V')+' / '+fmt(r?.pv2_voltage_v,'V')]
    ]);
    const history=await get('/api/inverter/history?hours='+hours()+'&limit=100000');
    if(!root.isConnected)return;
    const rows=history.readings.map(row=>{const a=row.raw_registers?.l1_current?.[0],b=row.raw_registers?.l2_current?.[0];return {...row,load_total_current_a:a==null||b==null?null:(a+b)/10}});
    $('inverter-charts').replaceChildren(...[['Solar input (W)','pv_total_power_w'],['AC load L1 + L2 (A)','load_total_current_a']].map(([title,key])=>chart(title,rows,key,snapshot.max_gap_seconds)));
    $('inverter-history-note').textContent=(history.truncated?'History truncated. ':'')+'UTC timestamps; gaps are excluded.';
   }catch(error){$('inverter-state').textContent='CONNECTION UNAVAILABLE';$('inverter-state').className='pill warning';$('status').textContent=error.message;$('status').className='stale'}
  });
  $('range-slot').replaceWith(rangeSelect(refresh));
  return live(refresh);
 }
};

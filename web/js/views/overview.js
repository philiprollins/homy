import {$,fmt,get,enc,cards,chart,serial,setStatus,hours,rangeSelect} from '../lib.js';
import {live} from '../live.js';

const kw=w=>w==null||!Number.isFinite(w)?'—':Math.abs(w)>=1000?(w/1000).toFixed(2)+' kW':Math.round(w)+' W';
function node(id,eyebrow){return `<div class="flow-node" id="${id}"><span class="eyebrow">${eyebrow}</span><strong>—</strong><small>Waiting</small></div>`}
function setNode(id,value,detail,{state='',href}={}){const n=$(id);n.querySelector('strong').textContent=value;n.querySelector('small').textContent=detail;n.dataset.state=state;if(href){n.onclick=()=>window.homy.navigate(href);n.classList.add('linked')}}

export default {
 title:'Power overview',
 render(root){
  root.innerHTML=`
<div class="page-heading"><div><div class="eyebrow">ENERGY / POWER</div><h1>Where your power is going.</h1><p>Solar in, battery in and out, the house, and the car, right now.</p></div></div>
<div id="status" role="status">Connecting to your monitor…</div>
<section class="power-flow" aria-label="Live power flow">
 ${node('n-solar','SOLAR IN')}
 <div class="flow-arrow" id="a-solar" aria-hidden="true"></div>
 <div class="flow-center">${node('n-home','HOUSE LOAD')}<div class="flow-split"><div id="home-bar" class="split-bar"><i id="bar-car"></i><i id="bar-rest"></i></div><div class="split-legend"><span><i class="car"></i><b id="lg-car">Car —</b></span><span><i class="rest"></i><b id="lg-rest">Everything else —</b></span></div></div></div>
 <div class="flow-arrow" id="a-bank" aria-hidden="true"></div>
 ${node('n-bank','BATTERY BANK')}
</section>
<p id="balance" class="subtle"></p>
<section id="car-panel" class="car-panel" hidden>
 <div class="car-head"><div><span class="eyebrow">VEHICLE</span><h2 id="car-name">Tesla</h2></div><a class="pill" id="car-state" href="/vehicle">Waiting</a></div>
 <div class="car-body"><div><div class="charge-number small"><span id="car-soc">—</span><span class="percent">%</span></div><div class="battery-track"><div id="car-fill"></div><div id="car-limit" class="limit-mark"></div></div><div class="charge-footer"><span id="car-range">—</span><span id="car-limit-label">Limit —</span></div></div>
 <div id="car-metrics" class="grid car-metrics"></div></div>
 <p id="car-automation" class="subtle"></p>
</section>
<div class="section-title"><div><span class="eyebrow">PATTERNS OVER TIME</span><h2>Production and consumption.</h2></div><span id="range-slot"></span></div>
<section id="power-charts" class="charts"></section><p id="power-note" class="subtle"></p>
<div class="section-title"><div><span class="eyebrow">STORAGE</span><h2>Battery bank.</h2></div><span id="bank-state" class="pill">Waiting</span></div>
<div id="bank-metrics" class="bank-metrics"></div><p id="bank-notice" class="subtle"></p><div id="bank-alarms" role="status"></div>
<section id="packs" class="pack-list" aria-label="Monitored battery packs"></section>`;

  let historyAt=0;
  const refresh=serial(async()=>{
   try{
    const [statuses,bank,inv,t]=await Promise.all([get('/api/status'),get('/api/bank/summary'),get('/api/inverter').catch(()=>null),get('/api/tesla').catch(()=>null)]);
    if(!root.isConnected)return;
    const r=inv?.enabled?inv.reading:null,invOk=inv?.enabled&&inv.state==='connected'&&!inv.stale;
    const v=t?.enabled?t.vehicle||{}:null,charging=v?.charging_state==='Charging'&&!t.stale;
    // Charger volts × amps is finer-grained than the API's whole-kW charger_power figure.
    const carW=charging?(v.charger_voltage_v&&v.charger_actual_current_a?v.charger_voltage_v*v.charger_actual_current_a:(v.charger_power_kw??0)*1000):0;
    const solar=r?.pv_total_power_w,load=r?.load_total_power_w,net=bank.net_power_w;

    setNode('n-solar',inv?.enabled?kw(solar):'Not set up',inv?.enabled?(invOk?'PV1 '+kw(r?.pv1_power_w)+' · PV2 '+kw(r?.pv2_power_w):'Inverter '+(inv.stale?'stale':inv.state)):'No inverter configured',{state:invOk&&solar>20?'active':'',href:inv?.enabled?'/solar':undefined});
    setNode('n-home',kw(load),invOk?'L1 '+kw(r.load_l1_power_w)+' · L2 '+kw(r.load_l2_power_w):'Load unavailable',{state:invOk?'active':''});
    setNode('n-bank',net==null?'—':(net>0?'+':net<0?'−':'')+kw(Math.abs(net)),(net>5?'Charging':net<-5?'Discharging':'Idle')+' · '+fmt(bank.soc_percent,'%').replace(' %','%')+' SOC'+(bank.power_complete?'':' · partial'),{state:net>5?'charging':net<-5?'discharging':'',href:'/batteries'});
    $('a-solar').dataset.on=String(invOk&&solar>20);
    $('a-bank').className='flow-arrow '+(net<-5?'to-home':net>5?'to-bank':'');

    const carShare=load?Math.min(carW,load):0;
    $('bar-car').style.width=load?100*carShare/load+'%':'0';$('bar-rest').style.width=load?100*(load-carShare)/load+'%':'0';
    $('lg-car').textContent='Car '+(v?kw(carW):'—');$('lg-rest').textContent='Everything else '+(load==null?'—':kw(Math.max(load-carShare,0)));
    $('balance').textContent=invOk&&net!=null?'Solar + battery discharge covers about '+kw(Math.max((solar||0)+Math.max(-net,0)-Math.max(net,0),0))+' of '+kw(load)+' load; the rest comes from grid input, which is not measured yet. Car share is estimated from charger volts × amps.':'';

    $('car-panel').hidden=!t?.enabled;
    if(t?.enabled){
     $('car-name').textContent=v.name||'Tesla';
     $('car-state').textContent=t.error?'NO DATA':(t.stale?'STALE · ':'')+(charging?'CHARGING':(v.charging_state||t.state||'unknown').toUpperCase());
     $('car-state').className='pill'+(t.stale||t.error?' warning':charging?' active':'');
     $('car-soc').textContent=v.battery_level??'—';$('car-fill').style.width=(v.battery_level??0)+'%';
     $('car-limit').style.left=(v.charge_limit_soc??100)+'%';$('car-limit-label').textContent='Limit '+(v.charge_limit_soc??'—')+'%';
     $('car-range').textContent=v.battery_range_mi==null?'Range unavailable':Math.round(v.battery_range_mi)+' mi range';
     cards('car-metrics',[
      ['Charging power',charging?kw(carW):v.charging_state??'—'],
      ['Current · set / max',charging?(v.charger_actual_current_a??'—')+' A · '+(v.charge_current_request_a??'—')+' / '+(v.charge_current_request_max_a??'—')+' A':'—'],
      ['Added this session',fmt(v.charge_energy_added_kwh,'kWh')],
      ['Time to limit',charging&&v.minutes_to_full_charge!=null?Math.floor(v.minutes_to_full_charge/60)+'h '+v.minutes_to_full_charge%60+'m':'—']
     ]);
     const a=t.automation||{};
     $('car-automation').textContent=(t.error||'Snapshot '+(t.data_at??'never'))+(a.stop_at==null?'':' · Automation pauses charging at bank ≤ '+a.stop_at+'%'+(a.resume_at==null?'':', resumes at ≥ '+a.resume_at+'%')+(a.dry_run?' (dry run)':'')+(a.stopped_by_us?' · currently paused':''));
    }

    $('bank-state').textContent=(bank.source==='mock'?'SIMULATED · ':'')+(bank.complete?'ALL PACKS LIVE':'PARTIAL COVERAGE');
    $('bank-state').className='pill'+(bank.complete?'':' warning');
    cards('bank-metrics',[['Bank SOC',fmt(bank.soc_percent,'%')],['Charging input',kw(bank.input_power_w)],['Discharging output',kw(bank.output_power_w)],['Batteries online',bank.reporting_count+' / '+bank.configured_count],['Temperature range',bank.temperature_min_c==null?'Unavailable':fmt(bank.temperature_min_c,'°C')+' – '+fmt(bank.temperature_max_c,'°C')],['Protection alarms',String(bank.alarms.length)]]);
    $('bank-notice').textContent=bank.mixed_sources?'Mixed real and simulated sources: aggregation disabled.':bank.complete?'':'Partial figures; excluded: '+bank.excluded_battery_ids.join(', ');
    const alarmBox=$('bank-alarms');alarmBox.replaceChildren(...bank.alarms.map(al=>{const p=document.createElement('p');p.className='alarm-row';p.textContent=al.battery_name+' · '+al.alarm;return p}));alarmBox.className=bank.alarms.length?'has-alarms':'';
    const readings=await Promise.all(statuses.map(p=>get('/api/batteries/'+enc(p.id)+'/latest')));
    if(!root.isConnected)return;
    $('packs').replaceChildren(...statuses.map((pack,i)=>{const pr=readings[i],a=document.createElement('a');a.className='pack-tile';a.href='/batteries/'+enc(pack.id);
     const l=document.createElement('span');l.textContent=pack.name;const s=document.createElement('strong');s.textContent=pr?.soc_percent==null?'—':Math.round(pr.soc_percent)+'%';
     const d=document.createElement('small');d.textContent=(pack.mock?'SIMULATED · ':'')+(pack.stale?'STALE':pack.state==='connected'?'LIVE':pack.state)+' · '+kw(pr?.power_w);a.append(l,s,d);return a}));

    // History is heavier; refresh it at most once a minute (or on range change).
    if(inv?.enabled&&Date.now()-historyAt>60000){
     historyAt=Date.now();
     const h=await get('/api/inverter/history?hours='+hours()+'&limit=100000');
     if(!root.isConnected)return;
     $('power-charts').replaceChildren(...[['Solar input (W)','pv_total_power_w'],['House load (W)','load_total_power_w']].map(([title,key])=>chart(title,h.readings,key,inv.max_gap_seconds)));
     $('power-note').textContent=(h.truncated?'History truncated. ':'')+'UTC. Lines break at missing readings.';
    }else if(!inv?.enabled)$('power-note').textContent='Production and consumption charts need an inverter.';

    const stale=statuses.filter(s=>s.stale).length;
    setStatus((invOk?'Inverter live':'Inverter '+(inv?.enabled?'offline':'not configured'))+' · '+statuses.length+' batteries'+(stale?' · '+stale+' stale':'')+(t?.enabled?' · car '+(t.stale?'stale':'snapshot fresh'):''),stale>0||(inv?.enabled&&!invOk));
   }catch(e){setStatus('Dashboard disconnected · '+e.message,true)}
  });
  $('range-slot').replaceWith(rangeSelect(()=>{historyAt=0;refresh()}));
  return live(refresh);
 }
};

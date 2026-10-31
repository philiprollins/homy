import {$,fmt,get,cards,serial} from '../lib.js';
import {live} from '../live.js';

export default {
 title:'Vehicle',
 render(root){
  root.innerHTML=`
<div class="page-heading"><div><div class="eyebrow">ENERGY / VEHICLE</div><h1 id="tesla-name">Tesla</h1><p>Read from tesla_ctrl's snapshot; the car is never woken for the dashboard.</p></div><span id="tesla-state" class="pill">Waiting</span></div>
<div id="status" role="status">Loading vehicle snapshot…</div>
<div id="tesla-metrics" class="grid energy-grid"></div>
<p id="tesla-automation" class="subtle"></p>`;
  const refresh=serial(async()=>{
   try{
    const t=await get('/api/tesla');
    if(!root.isConnected)return;
    if(!t.enabled){$('status').textContent='No vehicle is configured. Enable the tesla section in config.yaml.';return}
    const v=t.vehicle||{},a=t.automation||{},yes=b=>b==null?'Unavailable':b?'Yes':'No';
    $('tesla-name').textContent=v.name||'Tesla';
    $('tesla-state').textContent=t.error?'NO DATA':(t.stale?'STALE · ':'')+(t.state||'unknown').toUpperCase()+(v.charging_state&&t.state==='online'?' · '+v.charging_state.toUpperCase():'');
    $('tesla-state').className='pill'+(t.stale||t.error?' warning':'');
    $('status').textContent=t.error||('Checked: '+(t.checked_at??'never')+' · Details from: '+(t.data_at??'never')+(t.state&&t.state!=='online'?' · Car is '+t.state+'; showing last known details':''));
    $('status').className=t.stale||t.error?'stale':'';
    const charging=v.charging_state==='Charging';
    cards('tesla-metrics',[
     ['Car SOC · limit '+(v.charge_limit_soc??'—')+'%',fmt(v.battery_level,'%')],
     ['Range',fmt(v.battery_range_mi,'mi')],
     ['Charging power',charging?fmt(v.charger_power_kw,'kW'):(v.charging_state??'Unavailable')],
     ['Current · actual / set / max',charging?[v.charger_actual_current_a,v.charge_current_request_a,v.charge_current_request_max_a].map(x=>x??'—').join(' / ')+' A':(v.charge_current_request_a==null?'Unavailable':'Set '+v.charge_current_request_a+' A')],
     ['Added this session',fmt(v.charge_energy_added_kwh,'kWh')],
     ['Time to full',charging&&v.minutes_to_full_charge!=null?Math.floor(v.minutes_to_full_charge/60)+'h '+v.minutes_to_full_charge%60+'m':'—'],
     ['Inside / outside',fmt(v.inside_temp_c,'°C')+' / '+fmt(v.outside_temp_c,'°C')],
     ['Locked · Sentry',yes(v.locked)+' · '+yes(v.sentry_mode)]
    ]);
    $('tesla-automation').textContent=a.stop_at==null?'':'Automation: stop car charging at bank ≤ '+a.stop_at+'%'+(a.resume_at==null?'':', resume at ≥ '+a.resume_at+'%')+(a.dry_run?' · DRY RUN (logging only)':'')+(a.stopped_by_us?' · Currently paused by automation':'')+(t.last_action?' · Last action '+t.last_action.at+': '+t.last_action.text:'')+' · Refreshes every '+Math.round((a.status_every_seconds||0)/60)+' min.';
   }catch(error){$('tesla-state').textContent='CONNECTION UNAVAILABLE';$('tesla-state').className='pill warning';$('status').textContent=error.message;$('status').className='stale'}
  });
  return live(refresh);
 }
};

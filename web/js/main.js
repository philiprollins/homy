import {get,enc} from './lib.js';
import {createRouter} from './router.js';

// Lazy-loaded so each view's code is fetched on first visit.
const routes=[
 ['/',()=>import('./views/overview.js')],
 ['/batteries',()=>({default:{title:'Batteries',render(){get('/api/status').then(s=>s.length&&router.navigate('/batteries/'+enc(s[0].id),{replace:true}))}}})],
 ['/batteries/:id',()=>import('./views/battery.js')],
 ['/solar',()=>import('./views/solar.js')],
 ['/vehicle',()=>import('./views/vehicle.js')],
 ['*',()=>import('./views/not-found.js')],
];
const crumbs={'/':'Power overview','/batteries/:id':'Batteries','/solar':'Solar','/vehicle':'Vehicle'};

const router=createRouter(routes,{root:document.getElementById('view'),onNavigate(path,pattern){
 for(const a of document.querySelectorAll('.sidebar .nav')){const on=a.dataset.match==='/'?path==='/':path.startsWith(a.dataset.match);a.classList.toggle('active',on);on?a.setAttribute('aria-current','page'):a.removeAttribute('aria-current')}
 document.getElementById('crumb').textContent=crumbs[pattern]||'Not found';
}});
window.homy={navigate:router.navigate};
router.start();

// Hide nav entries for features that are not configured.
get('/api/inverter').then(i=>{document.querySelector('[data-match="/solar"]').hidden=!i.enabled}).catch(()=>{});
get('/api/tesla').then(t=>{document.querySelector('[data-match="/vehicle"]').hidden=!t.enabled}).catch(()=>{});

const clock=()=>{document.getElementById('clock').textContent=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})};clock();setInterval(clock,10000);

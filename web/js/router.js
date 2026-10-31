// Minimal History API router. A route is [pattern, loader]; patterns use :name params.
// A view module exports {title, render(root, params)} where render returns an optional cleanup fn.
export function createRouter(routes,{root,onNavigate=()=>{}}){
 const compiled=routes.map(([pattern,load])=>({pattern,load,re:pattern==='*'?/(?!)/:new RegExp('^'+pattern.replace(/\/:(\w+)/g,'/(?<$1>[^/]+)')+'/?$')}));
 let cleanup=null,seq=0;
 async function resolve(){
  const path=location.pathname,id=++seq;
  let match=null,params={};
  for(const r of compiled){const m=path.match(r.re);if(m){match=r;params=Object.fromEntries(Object.entries(m.groups||{}).map(([k,v])=>[k,decodeURIComponent(v)]));break}}
  const view=(await (match||compiled.find(r=>r.pattern==='*')).load()).default;
  if(id!==seq)return; // a newer navigation won
  cleanup?.();cleanup=null;
  root.replaceChildren();
  document.title='Homy · '+(typeof view.title==='function'?view.title(params):view.title);
  onNavigate(path,match?.pattern);
  cleanup=view.render(root,params)||null;
  window.scrollTo(0,0);
 }
 function navigate(to,{replace=false}={}){if(to===location.pathname+location.search)return;history[replace?'replaceState':'pushState'](null,'',to);resolve()}
 document.addEventListener('click',e=>{
  const a=e.target.closest('a[href]');
  if(!a||e.defaultPrevented||e.button||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||a.target||a.origin!==location.origin||a.pathname.startsWith('/api/'))return;
  if(a.hash&&a.pathname===location.pathname)return; // in-page anchor
  e.preventDefault();navigate(a.pathname+a.search+a.hash);
 });
 window.addEventListener('popstate',resolve);
 return {navigate,start:resolve};
}

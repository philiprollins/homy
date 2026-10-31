// One shared live feed for all views: SSE pushes from the server plus a 10s fallback poll.
import {setStatus} from './lib.js';
const subscribers=new Set();
const notify=()=>{for(const fn of subscribers)fn()};
const stream=new EventSource('/api/events');
stream.onmessage=notify;
stream.onerror=()=>setStatus('Live connection interrupted; reconnecting…',true);
setInterval(notify,10000);

// Runs fn now and on every live tick; returns an unsubscribe function.
export function live(fn){subscribers.add(fn);fn();return ()=>subscribers.delete(fn)}

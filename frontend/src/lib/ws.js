export function connectWS(url, onEvent){
  let ws;
  function open(){
    ws = new WebSocket(url);
    ws.onopen = () => console.log("[WS] connected", url);
    ws.onmessage = (m)=> onEvent(JSON.parse(m.data));
    ws.onclose = ()=> setTimeout(open, 1000);
    ws.onerror = ()=> ws.close();
  }
  open();
  return ()=> ws && ws.close();
}
export function startMock(onEvent){
  const countries = [
    {cc:"US",lat:38,lon:-97},{cc:"CN",lat:36,lon:104},
    {cc:"IT",lat:42,lon:12},{cc:"DE",lat:51,lon:10},{cc:"BR",lat:-14,lon:-52}
  ];
  const vectors = ["SYN","UDP","HTTP2"];
  function fake(){
    const s = countries[Math.floor(Math.random()*countries.length)];
    let d = countries[Math.floor(Math.random()*countries.length)];
    if(d===s) d = countries[(countries.indexOf(s)+1)%countries.length];
    const pps = Math.floor(Math.exp( Math.random()*3 + 10 ));
    const bps = pps * (50+Math.random()*300);
    const score = Math.max(0, Math.min(1, 0.4 + Math.random()*0.6));
    onEvent({
      ts: Date.now(),
      src:{country:s.cc, lat:s.lat, lon:s.lon},
      dst:{country:d.cc, lat:d.lat, lon:d.lon},
      vector: vectors[Math.floor(Math.random()*vectors.length)],
      pps, bps, score
    });
  }
  const id = setInterval(fake, 200);
  return ()=> clearInterval(id);
}

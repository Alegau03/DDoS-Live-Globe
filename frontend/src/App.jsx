import { useEffect, useRef, useState } from "react";
import GlobeView from "./components/GlobeView";
import ControlPanel from "./components/ControlPanel";
import TopTables from "./components/TopTables";
import { connectWS, startMock } from "./lib/ws";
import "./styles.css";

const WS_URL = import.meta.env.VITE_WS_URL;
const MAX_EVENTS = 1500;

function colorByVector(v){
  return v==="UDP" ? "#f59e0b" : v==="SYN" ? "#3b82f6" : "#a855f7";
}
function colorByScore(s){
  if(s > 0.85) return "#ef4444";
  if(s > 0.65) return "#f59e0b";
  return "#60a5fa";
}

export default function App(){
  // UI / filtri
  const [paused, setPaused] = useState(false);
  const [scoreMin, setScoreMin] = useState(0.2); // default più permissivo
  const [vectors, setVectors] = useState({ SYN:true, UDP:true, HTTP2:true });
  const [countryFilter, setCountryFilter] = useState([]);
  const [colorMode, setColorMode] = useState("score"); // "score" | "vector"

  // KPI e dati per Globe
  const [kpi, setKpi] = useState({ eps:0, avgGbps:0, highScore:0 });
  const [arcs, setArcs] = useState([]);
  const [points, setPoints] = useState([]);

  // Aggregazioni
  const [topCountries, setTopCountries] = useState([]);
  const [topVectors, setTopVectors] = useState([]);

  // Buffer eventi
  const bufRef = useRef([]);
  const unsubRef = useRef(null);

  // Stream con fallback: WS → (3s) → mock se nessun evento arriva
  useEffect(()=>{
    const onEvent = (ev)=>{
      bufRef.current.push(ev);
      if(bufRef.current.length > MAX_EVENTS) bufRef.current = bufRef.current.slice(-MAX_EVENTS);
    };
    // prova WS se definito, altrimenti mock
    unsubRef.current = WS_URL ? connectWS(WS_URL, onEvent) : startMock(onEvent);

    // fallback a mock se entro 3s nessun evento
    const t = setTimeout(()=>{
      if (WS_URL && bufRef.current.length === 0) {
        // passa al mock
        unsubRef.current && unsubRef.current();
        unsubRef.current = startMock(onEvent);
        console.warn("[Stream] Nessun evento dal WS entro 3s → fallback a mock");
      }
    }, 3000);

    return ()=>{
      clearTimeout(t);
      unsubRef.current && unsubRef.current();
    };
  }, []);

  // Aggiornamento UI 5x/s
  useEffect(()=>{
    const id = setInterval(()=>{
      if(paused) return;
      const now = Date.now();
      const raw = bufRef.current;

      // KPI
      const last1s = raw.filter(e => (now - (e.ts*1000 || e.ts)) < 1000);
      const eps = last1s.length;
      const tail = raw.slice(-Math.min(100, raw.length));
      const avgGbps = tail.reduce((acc,e)=>acc + e.bps, 0) / Math.max(1, tail.length) / 1e9;
      const highScore = raw.slice(-200).reduce((m,e)=>Math.max(m, e.score), 0);
      setKpi({ eps, avgGbps, highScore });

      // Filtri
      const allowVector = new Set(Object.entries(vectors).filter(([,v])=>v).map(([k])=>k));
      const allowCountries = countryFilter.length ? new Set(countryFilter) : null;

      const filtered = [];
      const outPoints = [];
      for(let i=Math.max(0, raw.length-1000); i<raw.length; i++){
        const ev = raw[i];
        if(ev.score < scoreMin) continue;
        if(!allowVector.has(ev.vector)) continue;
        if(allowCountries && !allowCountries.has((ev.src.country||"").toUpperCase())) continue;

        const sev = ev.score;
        const color = colorMode==="score" ? colorByScore(sev) : colorByVector(ev.vector);
        const altitude = 0.12 + Math.min(0.35, (Math.log10(ev.bps + 1) / 10) + sev * 0.25);

        filtered.push({
          startLat: ev.src.lat, startLng: ev.src.lon,
          endLat: ev.dst.lat, endLng: ev.dst.lon,
          color,
          altitude,
          label: `${ev.src.country} → ${ev.dst.country}<br/>${ev.vector} • ${(ev.bps/1e9).toFixed(2)} Gbps • ${(sev*100|0)}%`
          });
        outPoints.push({
          lat: ev.dst.lat, lng: ev.dst.lon,
          size: Math.max(0.5, Math.log10(ev.pps+10)),
          color,
          label: `${ev.dst.country}<br/>pps≈${ev.pps} • Gbps≈${(ev.bps/1e9).toFixed(2)}`
        });
      }

      setArcs(filtered.slice(-900));
      setPoints(outPoints.slice(-600));

      // Aggregazioni sugli ultimi 500 (post-filtri)
      const recent = raw.slice(-500).filter(ev=>{
        if(ev.score < scoreMin) return false;
        if(!allowVector.has(ev.vector)) return false;
        if(allowCountries && !allowCountries.has((ev.src.country||"").toUpperCase())) return false;
        return true;
      });
      const byCountry = new Map();
      const byVector = new Map();
      for(const e of recent){
        const c = e.src.country || "??";
        const vc = byCountry.get(c) || {country:c, count:0, sumScore:0, sumGbps:0};
        vc.count++; vc.sumScore += e.score; vc.sumGbps += e.bps/1e9;
        byCountry.set(c, vc);

        const v = e.vector;
        const vv = byVector.get(v) || {vector:v, count:0, sumScore:0, sumGbps:0};
        vv.count++; vv.sumScore += e.score; vv.sumGbps += e.bps/1e9;
        byVector.set(v, vv);
      }
      const tc = Array.from(byCountry.values())
        .map(r=>({country:r.country, count:r.count, avgScore:r.sumScore/Math.max(1,r.count), gbps:r.sumGbps}))
        .sort((a,b)=> b.count - a.count).slice(0,5);
      const tv = Array.from(byVector.values())
        .map(r=>({vector:r.vector, count:r.count, avgScore:r.sumScore/Math.max(1,r.count), gbps:r.sumGbps}))
        .sort((a,b)=> b.count - a.count).slice(0,5);

      setTopCountries(tc);
      setTopVectors(tv);

    }, 200);
    return ()=> clearInterval(id);
  }, [paused, scoreMin, vectors, countryFilter, colorMode]);

  const onTogglePause = ()=> setPaused(p=>!p);
  const onClear = ()=>{
    bufRef.current = [];
    setArcs([]); setPoints([]);
  };

  return (
    <div className="w-screen h-screen relative">
      <GlobeView arcs={arcs} points={points} kpi={kpi} />
      <ControlPanel
        paused={paused} onTogglePause={onTogglePause} onClear={onClear}
        scoreMin={scoreMin} setScoreMin={setScoreMin}
        vectors={vectors} setVectors={setVectors}
        countryFilter={countryFilter} setCountryFilter={setCountryFilter}
        colorMode={colorMode} setColorMode={setColorMode}
      />
      <TopTables topCountries={topCountries} topVectors={topVectors} />
    </div>
  );
}

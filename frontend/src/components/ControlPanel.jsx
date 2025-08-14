import { useEffect, useState } from "react";

export default function ControlPanel({
  paused, onTogglePause, onClear,
  scoreMin, setScoreMin,
  vectors, setVectors,
  countryFilter, setCountryFilter,
  colorMode, setColorMode
}){
  const [countriesInput, setCountriesInput] = useState(countryFilter.join(","));

  useEffect(()=>{
    setCountriesInput(countryFilter.join(","));
  }, [countryFilter]);

  const onApplyCountries = ()=>{
    const list = countriesInput
      .split(",")
      .map(s => s.trim().toUpperCase())
      .filter(Boolean);
    setCountryFilter(list);
  };

  const toggleVector = (v)=> setVectors(prev => ({...prev, [v]: !prev[v]}));

  return (
    <div className="absolute top-4 right-4 w-80 max-w-[90vw] bg-black/60 text-white rounded-2xl p-4 backdrop-blur-md border border-white/10 shadow-xl">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">Controlli</h2>
        <div className="flex gap-2">
          <button
            onClick={onTogglePause}
            className={`px-3 py-1.5 rounded-lg text-sm ${paused ? "bg-emerald-600" : "bg-amber-600"} hover:opacity-90`}
            title="Pausa/Resume stream"
          >{paused ? "Riprendi" : "Pausa"}</button>
          <button
            onClick={onClear}
            className="px-3 py-1.5 rounded-lg text-sm bg-slate-700 hover:opacity-90"
            title="Svuota eventi dal globo"
          >Clear</button>
        </div>
      </div>

      <div className="mb-4">
        <label className="text-sm opacity-80">Soglia score minima: <span className="font-mono">{(scoreMin*100).toFixed(0)}%</span></label>
        <input
          type="range" min={0} max={1} step={0.01}
          value={scoreMin}
          onChange={e=>setScoreMin(parseFloat(e.target.value))}
          className="w-full"
        />
      </div>

      <div className="mb-4">
        <div className="text-sm opacity-80 mb-1">Vettori</div>
        <div className="flex flex-wrap gap-2">
          {["SYN","UDP","HTTP2"].map(v=>(
            <label key={v} className={`px-2 py-1 rounded-md cursor-pointer text-sm border ${vectors[v] ? "bg-white/10 border-white/30" : "bg-black/20 border-white/10"}`}>
              <input type="checkbox" className="mr-1" checked={!!vectors[v]} onChange={()=>toggleVector(v)} />
              {v}
            </label>
          ))}
        </div>
      </div>

      <div className="mb-4">
        <div className="text-sm opacity-80 mb-1">Filtro Paesi sorgente (ISO-2, es: CN,US) – vuoto = tutti</div>
        <div className="flex gap-2">
          <input
            value={countriesInput}
            onChange={e=>setCountriesInput(e.target.value)}
            placeholder="CN,US,IT"
            className="flex-1 bg-black/30 border border-white/10 rounded-md px-2 py-1 text-sm outline-none focus:border-white/30"
          />
          <button onClick={onApplyCountries} className="px-3 py-1.5 rounded-lg text-sm bg-slate-700 hover:opacity-90">Applica</button>
        </div>
      </div>

      <div className="mb-1 text-sm opacity-80">Colorazione archi</div>
      <div className="flex gap-2">
        <button
          onClick={()=>setColorMode("score")}
          className={`px-3 py-1.5 rounded-lg text-sm border ${colorMode==="score" ? "bg-white/10 border-white/30" : "bg-black/20 border-white/10"}`}
        >
          Per severità (score)
        </button>
        <button
          onClick={()=>setColorMode("vector")}
          className={`px-3 py-1.5 rounded-lg text-sm border ${colorMode==="vector" ? "bg-white/10 border-white/30" : "bg-black/20 border-white/10"}`}
        >
          Per vettore
        </button>
      </div>
    </div>
  );
}

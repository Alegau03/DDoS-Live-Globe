function Table({ title, cols, rows }){
  return (
    <div className="bg-black/60 text-white rounded-2xl p-4 backdrop-blur-md border border-white/10 shadow-xl">
      <div className="text-sm font-semibold mb-2">{title}</div>
      <div className="overflow-hidden rounded-lg border border-white/10">
        <table className="w-full text-sm">
          <thead className="bg-white/5">
            <tr>
              {cols.map((c,i)=>(<th key={i} className="text-left px-3 py-2 font-medium">{c}</th>))}
            </tr>
          </thead>
          <tbody>
            {rows.length===0 ? (
              <tr><td className="px-3 py-2 opacity-60" colSpan={cols.length}>—</td></tr>
            ) : rows.map((r,i)=>(
              <tr key={i} className="odd:bg-white/0 even:bg-white/5">
                {r.map((cell,j)=>(<td key={j} className="px-3 py-2">{cell}</td>))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function TopTables({ topCountries, topVectors }){
  return (
    <div className="absolute bottom-4 left-4 w-[36rem] max-w-[90vw] grid grid-cols-2 gap-4">
      <Table
        title="Top Paesi sorgente"
        cols={["Paese","Eventi","Avg Score","~Gbps"]}
        rows={topCountries.map(r=>[
          r.country, r.count, (r.avgScore*100).toFixed(0)+"%", r.gbps.toFixed(2)
        ])}
      />
      <Table
        title="Top Vettori"
        cols={["Vettore","Eventi","Avg Score","~Gbps"]}
        rows={topVectors.map(r=>[
          r.vector, r.count, (r.avgScore*100).toFixed(0)+"%", r.gbps.toFixed(2)
        ])}
      />
    </div>
  );
}

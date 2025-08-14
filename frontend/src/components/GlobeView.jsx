// src/components/GlobeView.jsx
import { useEffect, useRef } from "react";
import Globe from "react-globe.gl";
import * as THREE from "three";
import { useWindowSize } from "@react-hook/window-size";

const TEX_DAY   = "https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg";
const TEX_BUMP  = "https://unpkg.com/three-globe/example/img/earth-topology.png";
const TEX_CLOUD = "https://unpkg.com/three-globe/example/img/earth-clouds.png";

export default function GlobeView({ arcs, points, kpi }){
  const [w,h] = useWindowSize();
  const globeRef = useRef(null);
  const cloudsRef = useRef(null);

  useEffect(() => {
    if (!globeRef.current) return;

    // controlli: rotazione dolce
    const controls = globeRef.current.controls();
    if (controls) {
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.45;
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;
    }

    // materiale globo: bump per rilievi
    const mat = globeRef.current.globeMaterial?.();
    if (mat) {
      mat.bumpScale = 0.04;       // rilievo discreto
      mat.shininess = 0.9;        // riflesso leggero
      mat.specular = new THREE.Color(0x222222);
    }

    // layer nuvole: sfera leggermente più grande che ruota lentamente
    const scene = globeRef.current.scene?.();
    const R = globeRef.current.getGlobeRadius
      ? globeRef.current.getGlobeRadius()
      : 100; // fallback

    const loader = new THREE.TextureLoader();
    loader.load(TEX_CLOUD, (cloudTex) => {
      const cloudGeo = new THREE.SphereGeometry(R * 1.01, 75, 75);
      const cloudMat = new THREE.MeshPhongMaterial({
        map: cloudTex,
        transparent: true,
        opacity: 0.35,
        depthWrite: false
      });
      const cloudMesh = new THREE.Mesh(cloudGeo, cloudMat);
      cloudsRef.current = cloudMesh;
      scene && scene.add(cloudMesh);

      // animazione nuvole
      const animate = () => {
        if (cloudsRef.current) cloudsRef.current.rotation.y += 0.0005;
        requestAnimationFrame(animate);
      };
      animate();
    });

    // luci extra per realismo
    if (scene) {
      const amb = new THREE.AmbientLight(0xffffff, 0.65);
      const dir = new THREE.DirectionalLight(0xffffff, 0.75);
      dir.position.set(-2, 1, 1);
      scene.add(amb, dir);
    }

    return () => {
      // cleanup nuvole
      if (scene && cloudsRef.current) {
        scene.remove(cloudsRef.current);
        cloudsRef.current.geometry?.dispose?.();
        cloudsRef.current.material?.map?.dispose?.();
        cloudsRef.current.material?.dispose?.();
        cloudsRef.current = null;
      }
    };
  }, []);

  return (
    <div className="w-full h-full">
      <Globe
        ref={globeRef}
        width={w} height={h}

        // sfondo trasparente per lasciare il body (stelle/nero)
        backgroundColor="rgba(0,0,0,0)"

        // Terra realistica
        globeImageUrl={TEX_DAY}
        bumpImageUrl={TEX_BUMP}

        // atmosfera glow azzurra
        showAtmosphere={true}
        atmosphereColor="#3fa7ff"
        atmosphereAltitude={0.12}

        // archi (attacchi)
        arcsData={arcs}
        arcColor={"color"}
        arcAltitude={d => d.altitude ?? 0.18}
        arcStroke={1.2}
        arcDashLength={0.6}
        arcDashGap={0.2}
        arcDashAnimateTime={1400}
        arcLabel={d=>d.label}

        // marker sui target
        pointsData={points}
        pointColor={"color"}
        pointAltitude={d=>0.01 + Math.min(0.25, d.size/8)}
        pointRadius={d=>0.35 + d.size/6}
        pointLabel={d=>d.label}

        labelsData={[]}
      />

      {/* KPI overlay */}
      <div className="absolute top-4 left-4 bg-black/60 text-white rounded-xl px-4 py-3 backdrop-blur">
        <h1 className="font-semibold">DDoS Live Map</h1>
        <p className="text-sm opacity-80">Terra realistica · archi = attacchi</p>
        <div className="mt-2 text-sm grid grid-cols-3 gap-3">
          <div><div className="opacity-70">Eventi/s</div><div className="font-mono">{kpi.eps}</div></div>
          <div><div className="opacity-70">Media Gbps</div><div className="font-mono">{kpi.avgGbps.toFixed(2)}</div></div>
          <div><div className="opacity-70">Max score</div><div className="font-mono">{(kpi.highScore*100|0)}%</div></div>
        </div>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { BoxSelect, Crosshair, Eye, EyeOff, Grid3X3, Maximize2, MousePointer2, Ruler, RotateCcw, ScanSearch, SquareDashed, View } from "lucide-react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

import type { PreviewBoundingBox, RevisionPreview, SelectionState } from "../types/api";
import { formatLength, trimNumber, type Measurement } from "./previewTypes";

type CadViewerProps = {
  stlUrl: string | null;
  preview: RevisionPreview | null;
  selection: SelectionState;
  displayUnits: "mm" | "in";
  onSelectOperation: (operationId: string, source: SelectionState["source"]) => void;
};

type ViewerMode = "solid" | "wireframe" | "solid_edges";
type ViewName = "iso" | "top" | "bottom" | "front" | "back" | "left" | "right";

export function CadViewer({ stlUrl, preview, selection, displayUnits, onSelectOperation }: CadViewerProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const overlayGroupRef = useRef<THREE.Group | null>(null);
  const sketchGroupRef = useRef<THREE.Group | null>(null);
  const bboxRef = useRef<THREE.Box3Helper | null>(null);
  const measurementGroupRef = useRef<THREE.Group | null>(null);
  const gridRef = useRef<THREE.GridHelper | null>(null);
  const axesRef = useRef<THREE.AxesHelper | null>(null);
  const overlayMeshesRef = useRef<Map<string, THREE.Mesh>>(new Map());
  const pointerDownRef = useRef<{ x: number; y: number } | null>(null);
  const measurePointsRef = useRef<THREE.Vector3[]>([]);
  const [viewerMode, setViewerMode] = useState<ViewerMode>("solid");
  const [gridVisible, setGridVisible] = useState(true);
  const [axesVisible, setAxesVisible] = useState(true);
  const [bboxVisible, setBboxVisible] = useState(false);
  const [measureEnabled, setMeasureEnabled] = useState(false);
  const [measurement, setMeasurement] = useState<Measurement | null>(null);
  const [coordinate, setCoordinate] = useState<[number, number, number] | null>(null);
  const [hoverLabel, setHoverLabel] = useState<string | null>(null);
  const [viewerStatus, setViewerStatus] = useState("No model loaded");
  const selectedPreviewObject = useMemo(
    () => preview?.objects.find((object) => object.operation_id === selection.selectedOperationId) ?? null,
    [preview, selection.selectedOperationId]
  );

  useEffect(() => {
    if (!hostRef.current) {
      return undefined;
    }

    const host = hostRef.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111316);
    sceneRef.current = scene;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(host.clientWidth, host.clientHeight);
    host.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(45, host.clientWidth / host.clientHeight, 0.1, 5000);
    camera.position.set(130, 130, 100);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
    controlsRef.current = controls;

    scene.add(new THREE.HemisphereLight(0xeaf7ff, 0x111111, 1.8));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.8);
    keyLight.position.set(80, -120, 160);
    scene.add(keyLight);

    const grid = new THREE.GridHelper(220, 22, 0x2fbdd6, 0x30363d);
    gridRef.current = grid;
    scene.add(grid);
    const axes = new THREE.AxesHelper(70);
    axesRef.current = axes;
    scene.add(axes);

    const overlayGroup = new THREE.Group();
    overlayGroupRef.current = overlayGroup;
    scene.add(overlayGroup);

    const sketchGroup = new THREE.Group();
    sketchGroupRef.current = sketchGroup;
    scene.add(sketchGroup);

    const measurementGroup = new THREE.Group();
    measurementGroupRef.current = measurementGroup;
    scene.add(measurementGroup);

    const resizeObserver = new ResizeObserver(() => {
      const width = Math.max(host.clientWidth, 1);
      const height = Math.max(host.clientHeight, 1);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    });
    resizeObserver.observe(host);

    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      animationFrame = requestAnimationFrame(animate);
    };
    let animationFrame = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      controls.dispose();
      clearObject(meshRef.current);
      clearGroup(overlayGroup);
      clearGroup(sketchGroup);
      clearGroup(measurementGroup);
      renderer.dispose();
      host.removeChild(renderer.domElement);
      meshRef.current = null;
      sceneRef.current = null;
    };
  }, []);

  useEffect(() => {
    const scene = sceneRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!scene || !camera || !controls) {
      return undefined;
    }
    if (meshRef.current) {
      scene.remove(meshRef.current);
      clearObject(meshRef.current);
      meshRef.current = null;
    }
    if (!stlUrl) {
      setViewerStatus("No model loaded");
      return undefined;
    }

    let cancelled = false;
    setViewerStatus("Loading revision mesh");
    new STLLoader().load(
      stlUrl,
      (geometry) => {
        if (cancelled) {
          geometry.dispose();
          return;
        }
        geometry.computeVertexNormals();
        const mesh = new THREE.Mesh(
          geometry,
          new THREE.MeshStandardMaterial({
            color: 0xaebbc0,
            metalness: 0.24,
            roughness: 0.46,
            transparent: true,
            opacity: 0.92
          })
        );
        mesh.name = "final_revision_mesh";
        meshRef.current = mesh;
        scene.add(mesh);
        applyViewerMode(viewerMode);
        fitCameraToBox(camera, controls, new THREE.Box3().setFromObject(mesh));
        setViewerStatus("Semantic preview ready");
      },
      undefined,
      () => setViewerStatus("Preview unavailable")
    );
    return () => {
      cancelled = true;
    };
  }, [stlUrl]);

  useEffect(() => {
    const overlayGroup = overlayGroupRef.current;
    const sketchGroup = sketchGroupRef.current;
    if (!overlayGroup || !sketchGroup || !preview) {
      return undefined;
    }
    clearGroup(overlayGroup);
    clearGroup(sketchGroup);
    overlayMeshesRef.current.clear();

    let cancelled = false;
    const loader = new STLLoader();
    for (const object of preview.objects) {
      if (object.mesh_url) {
        loader.load(object.mesh_url, (geometry) => {
          if (cancelled) {
            geometry.dispose();
            return;
          }
          geometry.computeVertexNormals();
          const mesh = new THREE.Mesh(
            geometry,
            previewMaterial(object.object_type, object.operation_id === selection.selectedOperationId)
          );
          mesh.name = object.operation_id;
          mesh.userData.operationId = object.operation_id;
          mesh.userData.label = object.label;
          mesh.userData.objectType = object.object_type;
          overlayMeshesRef.current.set(object.operation_id, mesh);
          overlayGroup.add(mesh);
          updateHighlighting();
        });
      }
      if (object.sketch_entities.length > 0) {
        const sketchLines = createSketchOverlay(object);
        sketchLines.name = object.operation_id;
        sketchLines.userData.operationId = object.operation_id;
        sketchLines.visible = object.visible_by_default || object.operation_id === selection.selectedOperationId;
        sketchGroup.add(sketchLines);
      }
    }
    setViewerStatus(preview.objects.length ? "Semantic preview ready" : "STL preview");
    return () => {
      cancelled = true;
      clearGroup(overlayGroup);
      clearGroup(sketchGroup);
      overlayMeshesRef.current.clear();
    };
  }, [preview]);

  useEffect(() => {
    applyViewerMode(viewerMode);
  }, [viewerMode]);

  useEffect(() => {
    if (gridRef.current) gridRef.current.visible = gridVisible;
  }, [gridVisible]);

  useEffect(() => {
    if (axesRef.current) axesRef.current.visible = axesVisible;
  }, [axesVisible]);

  useEffect(() => {
    updateHighlighting();
    updateBoundingBox();
  }, [selection.selectedOperationId, bboxVisible, preview]);

  useEffect(() => {
    if (!measureEnabled) {
      measurePointsRef.current = [];
    }
  }, [measureEnabled]);

  function resetCamera() {
    if (cameraRef.current && controlsRef.current) {
      const box = activeModelBox(preview, null, meshRef.current);
      if (box) fitCameraToBox(cameraRef.current, controlsRef.current, box);
    }
  }

  function focusSelection() {
    if (cameraRef.current && controlsRef.current) {
      const box = activeModelBox(preview, selection.selectedOperationId, meshRef.current);
      if (box) fitCameraToBox(cameraRef.current, controlsRef.current, box);
    }
  }

  function setView(view: ViewName) {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;
    const box = activeModelBox(preview, selection.selectedOperationId, meshRef.current);
    if (!box) return;
    setCameraView(camera, controls, box, view);
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    pointerDownRef.current = { x: event.clientX, y: event.clientY };
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const hit = pick(event);
    if (hit?.point) {
      setCoordinate([hit.point.x, hit.point.y, hit.point.z]);
      setHoverLabel(hit.object.userData.label ?? null);
    } else {
      setCoordinate(null);
      setHoverLabel(null);
    }
  }

  function handlePointerUp(event: React.PointerEvent<HTMLDivElement>) {
    const down = pointerDownRef.current;
    pointerDownRef.current = null;
    if (!down || Math.hypot(event.clientX - down.x, event.clientY - down.y) > 4) {
      return;
    }
    const hit = pick(event);
    if (!hit) {
      return;
    }
    if (measureEnabled) {
      addMeasurementPoint(hit.point);
      return;
    }
    const operationId = hit.object.userData.operationId as string | undefined;
    if (operationId) {
      onSelectOperation(operationId, "viewer");
    } else if (preview?.objects.length === 1) {
      onSelectOperation(preview.objects[0].operation_id, "viewer");
    }
  }

  function addMeasurementPoint(point: THREE.Vector3) {
    const points = [...measurePointsRef.current, point.clone()].slice(-2);
    measurePointsRef.current = points;
    if (points.length === 2) {
      const distanceMm = points[0].distanceTo(points[1]);
      setMeasurement({
        start: [points[0].x, points[0].y, points[0].z],
        end: [points[1].x, points[1].y, points[1].z],
        distanceMm
      });
      drawMeasurement(points[0], points[1]);
      measurePointsRef.current = [];
    }
  }

  function clearMeasurement() {
    setMeasurement(null);
    measurePointsRef.current = [];
    if (measurementGroupRef.current) {
      clearGroup(measurementGroupRef.current);
    }
  }

  function pick(event: React.PointerEvent<HTMLDivElement>): THREE.Intersection | null {
    const host = hostRef.current;
    const camera = cameraRef.current;
    if (!host || !camera) return null;
    const rect = host.getBoundingClientRect();
    const pointer = new THREE.Vector2(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(pointer, camera);
    const selectable = [...overlayMeshesRef.current.values(), ...(meshRef.current ? [meshRef.current] : [])].filter((object) => object.visible);
    return raycaster.intersectObjects(selectable, false)[0] ?? null;
  }

  function updateHighlighting() {
    const selectedId = selection.selectedOperationId;
    overlayMeshesRef.current.forEach((mesh, operationId) => {
      const material = mesh.material;
      if (material instanceof THREE.MeshStandardMaterial) {
        const selected = operationId === selectedId;
        material.color.set(selected ? 0x8af0ff : mesh.userData.objectType === "subtractive_helper" ? 0x5fd7ff : 0xdfe8ec);
        material.opacity = selected ? 0.58 : mesh.userData.objectType === "subtractive_helper" ? 0.23 : 0.16;
        material.wireframe = viewerMode === "wireframe";
        material.needsUpdate = true;
      }
    });
    sketchGroupRef.current?.children.forEach((child) => {
      child.visible = child.userData.operationId === selectedId;
    });
  }

  function applyViewerMode(mode: ViewerMode) {
    const finalMaterial = meshRef.current?.material;
    if (finalMaterial instanceof THREE.MeshStandardMaterial) {
      finalMaterial.wireframe = mode === "wireframe";
      finalMaterial.opacity = mode === "wireframe" ? 0.54 : 0.92;
      finalMaterial.needsUpdate = true;
    }
    updateHighlighting();
  }

  function updateBoundingBox() {
    const scene = sceneRef.current;
    if (!scene) return;
    if (bboxRef.current) {
      scene.remove(bboxRef.current);
      bboxRef.current.geometry.dispose();
      bboxRef.current = null;
    }
    if (!bboxVisible) return;
    const box = activeModelBox(preview, selection.selectedOperationId, meshRef.current);
    if (!box) return;
    const helper = new THREE.Box3Helper(box, 0x8af0ff);
    bboxRef.current = helper;
    scene.add(helper);
  }

  function drawMeasurement(start: THREE.Vector3, end: THREE.Vector3) {
    const group = measurementGroupRef.current;
    if (!group) return;
    clearGroup(group);
    const lineGeometry = new THREE.BufferGeometry().setFromPoints([start, end]);
    group.add(new THREE.Line(lineGeometry, new THREE.LineBasicMaterial({ color: 0x8af0ff })));
    const markerMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff });
    for (const point of [start, end]) {
      const marker = new THREE.Mesh(new THREE.SphereGeometry(1.3, 16, 16), markerMaterial.clone());
      marker.position.copy(point);
      group.add(marker);
    }
  }

  const activeBox = selectedPreviewObject?.bounding_box ?? preview?.overall_bounding_box ?? null;

  return (
    <section className="viewer-shell">
      <div className="viewer-toolbar">
        <span>{viewerStatus}</span>
        <button type="button" className="tool-button compact" onClick={() => setViewerMode("solid")} title="Solid mode" aria-pressed={viewerMode === "solid"}>
          <View size={15} /> Solid
        </button>
        <button type="button" className="tool-button compact" onClick={() => setViewerMode("wireframe")} title="Wireframe mode" aria-pressed={viewerMode === "wireframe"}>
          <RotateCcw size={15} /> Wire
        </button>
        <button type="button" className="tool-button compact" onClick={() => setViewerMode("solid_edges")} title="Solid with semantic overlays" aria-pressed={viewerMode === "solid_edges"}>
          <SquareDashed size={15} /> Edges
        </button>
        <button type="button" className="icon-button" onClick={resetCamera} title="Fit model">
          <Maximize2 size={16} />
        </button>
        <button type="button" className="icon-button" onClick={focusSelection} title="Focus selection">
          <ScanSearch size={16} />
        </button>
        <button type="button" className="icon-button" onClick={() => setBboxVisible((value) => !value)} title="Bounding box" aria-pressed={bboxVisible}>
          <BoxSelect size={16} />
        </button>
        <button type="button" className="icon-button" onClick={() => setGridVisible((value) => !value)} title="Grid" aria-pressed={gridVisible}>
          <Grid3X3 size={16} />
        </button>
        <button type="button" className="icon-button" onClick={() => setAxesVisible((value) => !value)} title="Axes" aria-pressed={axesVisible}>
          {axesVisible ? <Eye size={16} /> : <EyeOff size={16} />}
        </button>
        <button type="button" className="icon-button" onClick={() => setMeasureEnabled((value) => !value)} title="Measure point to point" aria-pressed={measureEnabled}>
          <Ruler size={16} />
        </button>
      </div>
      <div
        className={measureEnabled ? "viewer-host measuring" : "viewer-host"}
        ref={hostRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        <div className="orientation-widget" aria-label="Orientation">
          <span className="axis-x">X</span>
          <span className="axis-y">Y</span>
          <span className="axis-z">Z</span>
        </div>
        <div className="view-shortcuts" aria-label="View shortcuts">
          {(["iso", "top", "bottom", "front", "back", "left", "right"] as ViewName[]).map((view) => (
            <button type="button" key={view} onClick={() => setView(view)} title={`${view} view`}>
              {view.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="viewer-readout">
          <MousePointer2 size={14} />
          {coordinate ? (
            <span>
              X {formatLength(coordinate[0], displayUnits)} · Y {formatLength(coordinate[1], displayUnits)} · Z {formatLength(coordinate[2], displayUnits)}
            </span>
          ) : (
            <span>No point under cursor</span>
          )}
        </div>
        {hoverLabel ? <div className="viewer-tooltip">{hoverLabel}</div> : null}
        {bboxVisible && activeBox ? (
          <div className="bbox-readout">
            BBOX {formatLength(activeBox.xlen, displayUnits)} × {formatLength(activeBox.ylen, displayUnits)} × {formatLength(activeBox.zlen, displayUnits)}
          </div>
        ) : null}
        {measureEnabled || measurement ? (
          <div className="measurement-readout">
            <span>{measurement ? `Preview distance: ${formatLength(measurement.distanceMm, displayUnits)}` : "Measure: click point A, then point B"}</span>
            <button type="button" onClick={clearMeasurement}>Clear</button>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function fitCameraToBox(camera: THREE.PerspectiveCamera, controls: OrbitControls, box: THREE.Box3) {
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);
  const maxDim = Math.max(size.x, size.y, size.z, 1);
  const fitDistance = maxDim / (2 * Math.tan((Math.PI * camera.fov) / 360));
  camera.position.set(center.x + fitDistance, center.y + fitDistance, center.z + fitDistance * 0.7);
  camera.near = Math.max(fitDistance / 100, 0.1);
  camera.far = fitDistance * 100;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

function setCameraView(camera: THREE.PerspectiveCamera, controls: OrbitControls, box: THREE.Box3, view: ViewName) {
  const center = new THREE.Vector3();
  const size = new THREE.Vector3();
  box.getCenter(center);
  box.getSize(size);
  const maxDim = Math.max(size.x, size.y, size.z, 1);
  const distance = maxDim * 2.15;
  const vectors: Record<ViewName, THREE.Vector3> = {
    iso: new THREE.Vector3(1, -1, 0.78),
    top: new THREE.Vector3(0, 0, 1),
    bottom: new THREE.Vector3(0, 0, -1),
    front: new THREE.Vector3(0, -1, 0),
    back: new THREE.Vector3(0, 1, 0),
    left: new THREE.Vector3(-1, 0, 0),
    right: new THREE.Vector3(1, 0, 0)
  };
  const direction = vectors[view].normalize();
  camera.position.copy(center.clone().add(direction.multiplyScalar(distance)));
  camera.up.set(0, 0, view === "top" || view === "bottom" ? -1 : 1);
  camera.near = Math.max(distance / 100, 0.1);
  camera.far = distance * 100;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

function activeModelBox(preview: RevisionPreview | null, operationId: string | null, mesh: THREE.Mesh | null): THREE.Box3 | null {
  const selected = operationId ? preview?.objects.find((object) => object.operation_id === operationId)?.bounding_box : null;
  const box = selected ?? preview?.overall_bounding_box ?? null;
  if (box) {
    return boxFromPreview(box);
  }
  return mesh ? new THREE.Box3().setFromObject(mesh) : null;
}

function boxFromPreview(box: PreviewBoundingBox): THREE.Box3 {
  return new THREE.Box3(new THREE.Vector3(box.xmin, box.ymin, box.zmin), new THREE.Vector3(box.xmax, box.ymax, box.zmax));
}

function previewMaterial(objectType: string, selected: boolean): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color: selected ? 0x8af0ff : objectType === "subtractive_helper" ? 0x5fd7ff : 0xdfe8ec,
    metalness: 0.05,
    roughness: 0.35,
    transparent: true,
    opacity: selected ? 0.58 : objectType === "subtractive_helper" ? 0.23 : 0.16,
    depthWrite: false
  });
}

function createSketchOverlay(object: { sketch_entities: Array<{ points: Array<[number, number, number]> }> }): THREE.Group {
  const group = new THREE.Group();
  for (const entity of object.sketch_entities) {
    const points = entity.points.map((point) => new THREE.Vector3(point[0], point[1], point[2]));
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    group.add(new THREE.Line(geometry, new THREE.LineBasicMaterial({ color: 0x8af0ff })));
  }
  return group;
}

function clearGroup(group: THREE.Group) {
  for (const child of [...group.children]) {
    group.remove(child);
    clearObject(child);
  }
}

function clearObject(object: THREE.Object3D | null) {
  if (!object) return;
  object.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();
    const material = mesh.material;
    if (Array.isArray(material)) {
      material.forEach((item) => item.dispose());
    } else if (material) {
      material.dispose();
    }
  });
}

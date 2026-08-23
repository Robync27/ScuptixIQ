/**
 * MeshForge 3D — Frontend Application Controller
 * ===============================================
 * Three.js WebGL rendering, orbit controls, Eel Python bridge,
 * multi-format 3D exports, sample loaders, and interactive HUD.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// ---------------------------------------------------------------------------
// DOM Element References
// ---------------------------------------------------------------------------
const dropZone = document.getElementById('dropZone');
const dropContent = document.getElementById('dropContent');
const previewImage = document.getElementById('previewImage');
const fileInput = document.getElementById('fileInput');
const btnBrowse = document.getElementById('btnBrowse');
const btnClearImage = document.getElementById('btnClearImage');
const btnGenerate = document.getElementById('btnGenerate');
const paddingSlider = document.getElementById('paddingSlider');
const paddingValue = document.getElementById('paddingValue');
const toggleRemoveBg = document.getElementById('toggleRemoveBg');
const resolutionGroup = document.getElementById('resolutionGroup');
const resolutionBadge = document.getElementById('resolutionBadge');
const textureGroup = document.getElementById('textureGroup');
const samplesCarousel = document.getElementById('samplesCarousel');

// Hardware & Header
const hardwareName = document.getElementById('hardwareName');
const deviceSelector = document.getElementById('deviceSelector');
const btnAbout = document.getElementById('btnAbout');
const aboutModal = document.getElementById('aboutModal');
const btnCloseAbout = document.getElementById('btnCloseAbout');
const btnModalCloseAction = document.getElementById('btnModalCloseAction');

// Diagnostics
const diagBackend = document.getElementById('diagBackend');
const diagGPU = document.getElementById('diagGPU');
const diagCPU = document.getElementById('diagCPU');
const diagPyTorch = document.getElementById('diagPyTorch');

// Viewport & HUD
const viewerCanvas = document.getElementById('viewerCanvas');
const viewerPlaceholder = document.getElementById('viewerPlaceholder');
const btnResetView = document.getElementById('btnResetView');
const toggleWireframe = document.getElementById('toggleWireframe');
const toggleAutoRotate = document.getElementById('toggleAutoRotate');
const toggleGrid = document.getElementById('toggleGrid');
const lightingSelect = document.getElementById('lightingSelect');

// Stats & Exports
const meshStatsHUD = document.getElementById('meshStatsHUD');
const statVerts = document.getElementById('statVerts');
const statFaces = document.getElementById('statFaces');
const statTime = document.getElementById('statTime');
const statDevice = document.getElementById('statDevice');
const exportBar = document.getElementById('exportBar');

// Progress Overlay
const progressOverlay = document.getElementById('progressOverlay');
const progressTitle = document.getElementById('progressTitle');
const progressSubtitle = document.getElementById('progressSubtitle');
const progressBarFill = document.getElementById('progressBarFill');
const progressPercent = document.getElementById('progressPercent');

// ---------------------------------------------------------------------------
// Application State
// ---------------------------------------------------------------------------
let selectedImageBase64 = null;
let currentLoadedMesh = null;
let currentModelId = null;
let currentResolution = 256;
let currentTextureMode = 'uv_atlas';
let currentBakeTexture = true;
let isWireframeActive = false;
let isGenerating = false;

// ---------------------------------------------------------------------------
// Three.js 3D Scene Initialization
// ---------------------------------------------------------------------------
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0d14);
scene.fog = new THREE.FogExp2(0x0a0d14, 0.08);

const camera = new THREE.PerspectiveCamera(
    45,
    (viewerCanvas.clientWidth || 800) / (viewerCanvas.clientHeight || 600),
    0.1,
    100
);
camera.position.set(2.5, 1.8, 3.2);

const renderer = new THREE.WebGLRenderer({
    canvas: viewerCanvas,
    antialias: true,
    alpha: false,
    powerPreference: "high-performance",
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.25;
renderer.outputColorSpace = THREE.SRGBColorSpace;

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.minDistance = 0.5;
controls.maxDistance = 15;
controls.target.set(0, 0, 0);
controls.autoRotate = true;
controls.autoRotateSpeed = 1.8;

// ---------------------------------------------------------------------------
// Lighting Setup & Environments
// ---------------------------------------------------------------------------
const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
scene.add(ambientLight);

const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.8);
dirLight1.position.set(4, 7, 5);
dirLight1.castShadow = true;
dirLight1.shadow.mapSize.width = 2048;
dirLight1.shadow.mapSize.height = 2048;
dirLight1.shadow.camera.near = 0.5;
dirLight1.shadow.camera.far = 25;
dirLight1.shadow.bias = -0.0001;
scene.add(dirLight1);

const dirLight2 = new THREE.DirectionalLight(0xddeeff, 1.2);
dirLight2.position.set(-5, 4, -4);
scene.add(dirLight2);

const dirLightFront = new THREE.DirectionalLight(0xffffff, 0.9);
dirLightFront.position.set(0, 2, 6);
scene.add(dirLightFront);

const rimLight = new THREE.DirectionalLight(0xffeedd, 0.8);
rimLight.position.set(0, -3, -4);
scene.add(rimLight);

function setLightingEnvironment(theme) {
    switch (theme) {
        case 'cyber':
            scene.background.setHex(0x060810);
            scene.fog.color.setHex(0x060810);
            ambientLight.color.setHex(0x381050);
            ambientLight.intensity = 1.0;
            dirLight1.color.setHex(0x00f0ff);
            dirLight1.intensity = 2.2;
            dirLight2.color.setHex(0xa855f7);
            dirLight2.intensity = 1.8;
            dirLightFront.color.setHex(0x00f0ff);
            dirLightFront.intensity = 1.2;
            rimLight.color.setHex(0xff007f);
            break;
        case 'sunset':
            scene.background.setHex(0x140a0e);
            scene.fog.color.setHex(0x140a0e);
            ambientLight.color.setHex(0x553020);
            ambientLight.intensity = 0.9;
            dirLight1.color.setHex(0xffaa55);
            dirLight1.intensity = 2.2;
            dirLight2.color.setHex(0xff4488);
            dirLight2.intensity = 1.4;
            dirLightFront.color.setHex(0xffcc88);
            dirLightFront.intensity = 1.2;
            rimLight.color.setHex(0xffaa66);
            break;
        case 'clay':
            scene.background.setHex(0x1c1c22);
            scene.fog.color.setHex(0x1c1c22);
            ambientLight.color.setHex(0xffffff);
            ambientLight.intensity = 1.2;
            dirLight1.color.setHex(0xffffff);
            dirLight1.intensity = 1.8;
            dirLight2.color.setHex(0xcccccc);
            dirLight2.intensity = 1.0;
            dirLightFront.color.setHex(0xffffff);
            dirLightFront.intensity = 1.0;
            rimLight.color.setHex(0xdddddd);
            break;
        case 'studio':
        default:
            scene.background.setHex(0x0a0d14);
            scene.fog.color.setHex(0x0a0d14);
            ambientLight.color.setHex(0xffffff);
            ambientLight.intensity = 0.9;
            dirLight1.color.setHex(0xffffff);
            dirLight1.intensity = 1.8;
            dirLight2.color.setHex(0xddeeff);
            dirLight2.intensity = 1.2;
            dirLightFront.color.setHex(0xffffff);
            dirLightFront.intensity = 0.9;
            rimLight.color.setHex(0xffeedd);
            break;
    }
}

// ---------------------------------------------------------------------------
// Studio Environment Map & PBR Reflections
// ---------------------------------------------------------------------------
function generateStudioEnvironment() {
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    pmremGenerator.compileEquirectangularShader();

    const envScene = new THREE.Scene();
    envScene.background = new THREE.Color(0x0a0d14);

    // Key Light Softbox (Top-Left-Front)
    const softbox1 = new THREE.Mesh(
        new THREE.PlaneGeometry(10, 10),
        new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide })
    );
    softbox1.position.set(6, 8, 6);
    softbox1.lookAt(0, 0, 0);
    envScene.add(softbox1);

    // Fill Light Softbox (Right)
    const softbox2 = new THREE.Mesh(
        new THREE.PlaneGeometry(8, 8),
        new THREE.MeshBasicMaterial({ color: 0x99ccff, side: THREE.DoubleSide })
    );
    softbox2.position.set(-6, 5, 5);
    softbox2.lookAt(0, 0, 0);
    envScene.add(softbox2);

    // Rim Light (Back-Top)
    const softbox3 = new THREE.Mesh(
        new THREE.PlaneGeometry(12, 4),
        new THREE.MeshBasicMaterial({ color: 0xffe0b2, side: THREE.DoubleSide })
    );
    softbox3.position.set(0, 7, -7);
    softbox3.lookAt(0, 0, 0);
    envScene.add(softbox3);

    const envMap = pmremGenerator.fromScene(envScene).texture;
    pmremGenerator.dispose();
    return envMap;
}

const studioEnvMap = generateStudioEnvironment();
scene.environment = studioEnvMap;

let currentMaterialFinish = 'glossy';

function applyMaterialFinish(finishType) {
    currentMaterialFinish = finishType;
    if (!currentLoadedMesh) return;

    let roughness = 0.18;
    let metalness = 0.05;
    let envMapIntensity = 1.5;

    switch (finishType) {
        case 'glossy':
            roughness = 0.18;
            metalness = 0.05;
            envMapIntensity = 1.5;
            break;
        case 'metallic':
            roughness = 0.15;
            metalness = 0.85;
            envMapIntensity = 1.8;
            break;
        case 'natural':
            roughness = 0.45;
            metalness = 0.02;
            envMapIntensity = 1.0;
            break;
        case 'matte':
            roughness = 0.90;
            metalness = 0.0;
            envMapIntensity = 0.3;
            break;
    }

    currentLoadedMesh.traverse((node) => {
        if (node.isMesh && node.material) {
            node.material.roughness = roughness;
            node.material.metalness = metalness;
            node.material.envMapIntensity = envMapIntensity;
            node.material.needsUpdate = true;
        }
    });
}

// ---------------------------------------------------------------------------
// Grid & Ground Shadow Plane
// ---------------------------------------------------------------------------
const gridHelper = new THREE.GridHelper(6, 24, 0x00f0ff, 0x1e293b);
gridHelper.position.y = -0.001;
scene.add(gridHelper);

const shadowPlaneGeo = new THREE.PlaneGeometry(20, 20);
const shadowPlaneMat = new THREE.ShadowMaterial({ opacity: 0.35 });
const shadowPlane = new THREE.Mesh(shadowPlaneGeo, shadowPlaneMat);
shadowPlane.rotation.x = -Math.PI / 2;
shadowPlane.position.y = 0;
shadowPlane.receiveShadow = true;
scene.add(shadowPlane);

// ---------------------------------------------------------------------------
// Resize & Render Loop
// ---------------------------------------------------------------------------
function handleResize() {
    const container = document.getElementById('viewerContainer');
    if (!container) return;
    const width = container.clientWidth;
    const height = container.clientHeight;
    if (width === 0 || height === 0) return;

    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
}
window.addEventListener('resize', handleResize);
setTimeout(handleResize, 100);

function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}
animate();

// ---------------------------------------------------------------------------
// 3D Model Loading & Normalization
// ---------------------------------------------------------------------------
const gltfLoader = new GLTFLoader();

function loadModelIntoScene(glbUrl) {
    if (currentLoadedMesh) {
        scene.remove(currentLoadedMesh);
        currentLoadedMesh = null;
    }

    viewerPlaceholder.style.display = 'none';

    gltfLoader.load(
        glbUrl,
        (gltf) => {
            const root = gltf.scene;

            // Center & normalize model size to fit nicely in 1.8m bounding cube
            const box = new THREE.Box3().setFromObject(root);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 1.8 / Math.max(maxDim, 0.001);

            root.scale.setScalar(scale);
            root.position.x = -center.x * scale;
            root.position.z = -center.z * scale;
            root.position.y = -box.min.y * scale;

            root.traverse((node) => {
                if (node.isMesh) {
                    node.castShadow = true;
                    node.receiveShadow = true;
                    if (node.material) {
                        node.material.wireframe = isWireframeActive;
                        node.material.side = THREE.DoubleSide;
                        node.material.roughness = 0.45;
                        node.material.metalness = 0.05;
                        if (node.material.color) {
                            node.material.color.setHex(0xffffff);
                        }
                        node.material.needsUpdate = true;
                    }
                }
            });

            scene.add(root);
            currentLoadedMesh = root;
            applyMaterialFinish(currentMaterialFinish);

            controls.target.set(0, (size.y * scale) / 2, 0);
            camera.position.set(2.2, 1.6, 2.8);
            controls.update();
        },
        (xhr) => {
            // Loading progress
        },
        (error) => {
            console.error('[Three.js] Error loading GLB model:', error);
        }
    );
}

// ---------------------------------------------------------------------------
// Viewport Camera Presets
// ---------------------------------------------------------------------------
function setCameraView(viewType) {
    const targetY = controls.target.y || 0.6;
    switch (viewType) {
        case 'front':
            camera.position.set(0, targetY, 3.2);
            break;
        case 'top':
            camera.position.set(0, targetY + 3.5, 0.001);
            break;
        case 'side':
            camera.position.set(3.2, targetY, 0);
            break;
        case 'iso':
        default:
            camera.position.set(2.2, targetY + 1.2, 2.8);
            break;
    }
    controls.update();
}

document.querySelectorAll('.view-preset').forEach(btn => {
    btn.addEventListener('click', () => setCameraView(btn.dataset.view));
});

btnResetView.addEventListener('click', () => setCameraView('iso'));

toggleWireframe.addEventListener('click', () => {
    isWireframeActive = !isWireframeActive;
    toggleWireframe.classList.toggle('active', isWireframeActive);
    if (currentLoadedMesh) {
        currentLoadedMesh.traverse((node) => {
            if (node.isMesh && node.material) {
                node.material.wireframe = isWireframeActive;
                node.material.needsUpdate = true;
            }
        });
    }
});

toggleAutoRotate.addEventListener('click', () => {
    controls.autoRotate = !controls.autoRotate;
    toggleAutoRotate.classList.toggle('active', controls.autoRotate);
});

toggleGrid.addEventListener('click', () => {
    gridHelper.visible = !gridHelper.visible;
    shadowPlane.visible = gridHelper.visible;
    toggleGrid.classList.toggle('active', gridHelper.visible);
});

lightingSelect.addEventListener('change', (e) => {
    setLightingEnvironment(e.target.value);
});

const materialFinishSelect = document.getElementById('materialFinishSelect');
if (materialFinishSelect) {
    materialFinishSelect.addEventListener('change', (e) => {
        applyMaterialFinish(e.target.value);
    });
}

// ---------------------------------------------------------------------------
// Image Input & Drag-and-Drop Handlers
// ---------------------------------------------------------------------------
function setImage(base64Data) {
    if (!base64Data) return;
    selectedImageBase64 = base64Data;
    previewImage.src = base64Data;
    previewImage.style.display = 'block';
    dropContent.style.display = 'none';
    btnClearImage.style.display = 'inline-block';
    btnGenerate.disabled = false;
}

function clearImage(e) {
    if (e) {
        e.stopPropagation();
    }
    selectedImageBase64 = null;
    previewImage.src = '';
    previewImage.style.display = 'none';
    dropContent.style.display = 'flex';
    btnClearImage.style.display = 'none';
    btnGenerate.disabled = true;
    fileInput.value = '';
}

btnClearImage.addEventListener('click', clearImage);

// Open file selector when clicking anywhere on drop zone
dropZone.addEventListener('click', () => {
    fileInput.click();
});

if (btnBrowse) {
    btnBrowse.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });
}

fileInput.addEventListener('change', (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (evt) => setImage(evt.target.result);
        reader.readAsDataURL(file);
    }
});

// Drag & Drop
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (evt) => setImage(evt.target.result);
        reader.readAsDataURL(file);
    }
});

// Clipboard Paste
window.addEventListener('paste', (e) => {
    const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items;
    if (!items) return;
    for (let item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
            const file = item.getAsFile();
            if (file) {
                const reader = new FileReader();
                reader.onload = (evt) => setImage(evt.target.result);
                reader.readAsDataURL(file);
                break;
            }
        }
    }
});

// ---------------------------------------------------------------------------
// Sample Carousel & 1-Click Loaders
// ---------------------------------------------------------------------------
function attachSampleButtonEvents() {
    document.querySelectorAll('.sample-btn').forEach((btn) => {
        btn.onclick = async (e) => {
            e.preventDefault();
            e.stopPropagation();
            const sampleFile = btn.dataset.sample;
            if (!sampleFile) return;
            try {
                const sampleUrl = `/samples/${sampleFile}`;
                const resp = await fetch(sampleUrl);
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const blob = await resp.blob();
                const reader = new FileReader();
                reader.onload = (evt) => setImage(evt.target.result);
                reader.readAsDataURL(blob);
            } catch (err) {
                console.error('Failed to load sample image:', err);
                alert(`Could not load sample: ${sampleFile}`);
            }
        };
    });
}
attachSampleButtonEvents();

async function loadSampleImages() {
    if (!window.eel) return;
    try {
        const samples = await eel.get_sample_images()();
        if (samples && samples.length > 0) {
            samplesCarousel.innerHTML = '';
            samples.forEach((sample) => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'sample-btn';
                btn.textContent = sample.name;
                btn.dataset.sample = sample.id;
                samplesCarousel.appendChild(btn);
            });
            attachSampleButtonEvents();
        }
    } catch (e) {
        console.warn('Failed to load dynamic sample images list:', e);
    }
}

// ---------------------------------------------------------------------------
// AI Text-to-Image Generator (Open-Source Prompt → Image → 3D)
// ---------------------------------------------------------------------------
const t2iHeader = document.getElementById('t2iHeader');
const t2iBody = document.getElementById('t2iBody');
const t2iChevron = document.getElementById('t2iChevron');
const t2iPromptInput = document.getElementById('t2iPrompt');
const t2iNegativePrompt = document.getElementById('t2iNegativePrompt');
const t2iModelSelect = document.getElementById('t2iModelSelect');
const t2iModelHint = document.getElementById('t2iModelHint');
const t2iStepsSlider = document.getElementById('t2iStepsSlider');
const t2iStepsValue = document.getElementById('t2iStepsValue');
const t2iCfgSlider = document.getElementById('t2iCfgSlider');
const t2iCfgValue = document.getElementById('t2iCfgValue');
const t2iOptimize3d = document.getElementById('t2iOptimize3d');
const btnT2IGenerate = document.getElementById('btnT2IGenerate');
const t2iGallery = document.getElementById('t2iGallery');

let t2iBusy = false;
let t2iInitialized = false;

if (t2iHeader) {
    const toggleT2I = () => {
        const open = t2iBody.style.display === 'none';
        t2iBody.style.display = open ? 'block' : 'none';
        t2iChevron.textContent = open ? '▴' : '▾';
        if (open && !t2iInitialized) initT2IModels();
    };
    t2iHeader.addEventListener('click', toggleT2I);
    t2iHeader.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleT2I(); }
    });
}

async function initT2IModels() {
    if (!window.eel) return;
    try {
        const info = await eel.get_t2i_models()();
        t2iInitialized = true;

        if (!info.diffusers_installed) {
            t2iModelHint.innerHTML = '⚠️ <code>pip install diffusers accelerate</code> required for the image generator.';
            btnT2IGenerate.disabled = true;
            return;
        }

        t2iModelSelect.innerHTML = '';
        (info.models || []).forEach((m) => {
            const opt = document.createElement('option');
            opt.value = m.key;
            opt.textContent = m.label;
            t2iModelSelect.appendChild(opt);
        });
        if (info.default) t2iModelSelect.value = info.default;
        updateT2IModelDefaults();

        // Warn on CPU-only machines about heavy models
        const hw = info.hardware || {};
        if (!hw.has_cuda) {
            t2iModelHint.textContent += ' · No CUDA GPU detected: generation will be slow on CPU.';
        }
    } catch (e) {
        console.warn('Failed to load text-to-image models:', e);
    }
}

function updateT2IModelDefaults() {
    const defaults = { 'sd15': [25, 7.5], 'dreamshaper': [25, 7], 'sd-turbo': [1, 0], 'sdxl-turbo': [1, 0] };
    const d = defaults[t2iModelSelect.value];
    if (d) {
        t2iStepsSlider.value = d[0];
        t2iCfgSlider.value = d[1];
        t2iStepsValue.textContent = d[0];
        t2iCfgValue.textContent = Number(d[1]).toFixed(1);
    }
}

if (t2iModelSelect) t2iModelSelect.addEventListener('change', updateT2IModelDefaults);
if (t2iStepsSlider) t2iStepsSlider.addEventListener('input', (e) => t2iStepsValue.textContent = e.target.value);
if (t2iCfgSlider) t2iCfgSlider.addEventListener('input', (e) => t2iCfgValue.textContent = Number(e.target.value).toFixed(1));

if (btnT2IGenerate) {
    btnT2IGenerate.addEventListener('click', async () => {
        const prompt = (t2iPromptInput.value || '').trim();
        if (!prompt) { alert('Please enter a prompt first.'); return; }
        if (t2iBusy) return;

        t2iBusy = true;
        btnT2IGenerate.disabled = true;
        btnT2IGenerate.textContent = '⏳ Generating...';
        progressOverlay.style.display = 'flex';

        const options = {
            model: t2iModelSelect.value,
            negative_prompt: t2iNegativePrompt ? t2iNegativePrompt.value : '',
            steps: parseInt(t2iStepsSlider.value),
            guidance_scale: parseFloat(t2iCfgSlider.value),
            seed: -1,
            optimize_for_3d: t2iOptimize3d.checked,
        };

        try {
            const res = await eel.generate_image_from_prompt(prompt, JSON.stringify(options))();
            if (res && res.success) {
                addT2IToGallery(res);
                setImage(res.image_data_url);   // feed straight into the 3D pipeline
            } else {
                alert(`Image generation failed: ${res?.error || 'Unknown error'}`);
            }
        } catch (err) {
            console.error('Text-to-image call failed:', err);
            alert(`Image generation failure: ${err.message || err}`);
        } finally {
            t2iBusy = false;
            btnT2IGenerate.disabled = false;
            btnT2IGenerate.textContent = '🎨 Generate Image';
            progressOverlay.style.display = 'none';
        }
    });
}

function addT2IToGallery(result) {
    if (!t2iGallery) return;
    const item = document.createElement('div');
    item.className = 't2i-gallery-item';

    const img = document.createElement('img');
    img.src = result.image_data_url;
    img.alt = result.prompt_used || 'Generated concept';
    img.title = `${result.model} · ${result.elapsed_s}s · seed ${result.seed}\nClick to use as source image`;

    const useBtn = document.createElement('button');
    useBtn.type = 'button';
    useBtn.className = 't2i-use-btn';
    useBtn.textContent = '→ Use for 3D';
    useBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        setImage(result.image_data_url);
    });

    item.appendChild(img);
    item.appendChild(useBtn);
    t2iGallery.prepend(item);

    while (t2iGallery.children.length > 6) {
        t2iGallery.removeChild(t2iGallery.lastChild);
    }
}

// ---------------------------------------------------------------------------
// Settings Controls
// ---------------------------------------------------------------------------
paddingSlider.addEventListener('input', (e) => {
    paddingValue.textContent = `${Math.round(e.target.value * 100)}%`;
});

resolutionGroup.querySelectorAll('.segment-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
        e.preventDefault();
        resolutionGroup.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentResolution = parseInt(btn.dataset.res);
        resolutionBadge.textContent = btn.textContent;
    });
});


const texResGroup = document.getElementById('texResGroup');
const texResGroupWrapper = document.getElementById('texResGroupWrapper');
const texResBadge = document.getElementById('texResBadge');
let currentTextureResolution = 2048;

textureGroup.querySelectorAll('.segment-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
        e.preventDefault();
        textureGroup.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentTextureMode = btn.dataset.mode || (btn.dataset.bake === 'true' ? 'uv_atlas' : 'vertex_colors');
        currentBakeTexture = (currentTextureMode === 'uv_atlas');
        if (texResGroupWrapper) {
            texResGroupWrapper.style.display = (currentTextureMode === 'uv_atlas') ? 'block' : 'none';
        }
    });
});

if (texResGroup) {
    texResGroup.querySelectorAll('.segment-btn').forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            texResGroup.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTextureResolution = parseInt(btn.dataset.texres);
            if (texResBadge) texResBadge.textContent = btn.textContent;
        });
    });
}

// ---------------------------------------------------------------------------
// 3D Generation Pipeline
// ---------------------------------------------------------------------------
btnGenerate.addEventListener('click', async (e) => {
    e.preventDefault();
    if (!selectedImageBase64 || isGenerating) return;

    isGenerating = true;
    btnGenerate.disabled = true;
    progressOverlay.style.display = 'flex';
    progressBarFill.style.width = '5%';
    progressPercent.textContent = '5%';
    progressTitle.textContent = 'Initializing Neural Pipeline...';
    progressSubtitle.textContent = 'Preparing image and compute device';

    const options = {
        resolution: currentResolution,
        texture_mode: currentTextureMode,
        bake_texture: (currentTextureMode === 'uv_atlas'),
        texture_resolution: currentTextureResolution,
        remove_bg: toggleRemoveBg.checked,
        foreground_ratio: parseFloat(paddingSlider.value),
        device: deviceSelector.value,
    };

    try {
        const result = await eel.generate_3d(selectedImageBase64, JSON.stringify(options))();

        if (result && result.success) {
            currentModelId = result.model_id;
            loadModelIntoScene(result.model_url);

            statVerts.textContent = (result.stats?.vertex_count || 0).toLocaleString();
            statFaces.textContent = (result.stats?.face_count || 0).toLocaleString();
            statTime.textContent = `${result.stats?.generation_time_s || 0}s`;
            statDevice.textContent = (result.stats?.device_used || 'CPU').toUpperCase();
            meshStatsHUD.style.display = 'flex';
            exportBar.style.display = 'flex';
        } else {
            alert(`Generation Error: ${result?.error || 'Unknown error'}`);
        }
    } catch (err) {
        console.error('Generation call failed:', err);
        alert(`Pipeline failure: ${err.message || err}`);
    } finally {
        isGenerating = false;
        btnGenerate.disabled = false;
        progressOverlay.style.display = 'none';
    }
});

// Shortcut: Ctrl + Enter
window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!btnGenerate.disabled) {
            btnGenerate.click();
        }
    }
});

// ---------------------------------------------------------------------------
// Progress Bridge from Python
// ---------------------------------------------------------------------------
if (window.eel) {
    window.eel.expose(updateProgress, 'updateProgress');
}
function updateProgress(phaseName, progressPct) {
    const pctInt = Math.round(progressPct * 100);
    progressBarFill.style.width = `${pctInt}%`;
    progressPercent.textContent = `${pctInt}%`;
    progressTitle.textContent = phaseName;
    progressSubtitle.textContent = `Progress: ${pctInt}% complete`;
}

// ---------------------------------------------------------------------------
// Multi-Format Export Handlers
// ---------------------------------------------------------------------------
document.querySelectorAll('.export-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
        e.preventDefault();
        if (!currentModelId) return;
        const fmt = btn.dataset.fmt;
        btn.textContent = '⏳ Exporting...';

        try {
            if (fmt === 'glb') {
                // GLB is already generated and cached on server
                const link = document.createElement('a');
                link.href = `/outputs/${currentModelId}.glb`;
                link.download = `${currentModelId}.glb`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            } else {
                const res = await eel.export_model_format(currentModelId, fmt)();
                if (res && res.success) {
                    const link = document.createElement('a');
                    link.href = res.download_url;
                    link.download = res.filename;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                } else {
                    alert(`Export failed: ${res?.error || 'Unknown error'}`);
                }
            }
        } catch (err) {
            console.warn('Direct export fallback:', err);
            const link = document.createElement('a');
            link.href = `/outputs/${currentModelId}.${fmt}`;
            link.download = `${currentModelId}.${fmt}`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } finally {
            switch (fmt) {
                case 'glb': btn.textContent = '📦 .GLB (glTF)'; break;
                case 'obj': btn.textContent = '📁 .OBJ (Mesh+Tex)'; break;
                case 'stl': btn.textContent = '🖨️ .STL (3D Print)'; break;
                case 'ply': btn.textContent = '📊 .PLY'; break;
            }
        }
    });
});

// ---------------------------------------------------------------------------
// Diagnostics & Hardware Initialization
// ---------------------------------------------------------------------------
async function initApp() {
    if (!window.eel) {
        console.warn('Eel bridge not detected.');
        return;
    }

    try {
        const info = await eel.get_system_info()();
        const hw = info.hardware;

        if (hw.has_cuda && hw.cuda_devices.length > 0) {
            hardwareName.textContent = `🟢 ${hw.cuda_devices[0].name}`;
            diagGPU.textContent = hw.cuda_devices[0].name;
            diagBackend.textContent = 'NVIDIA CUDA Acceleration';
        } else {
            hardwareName.textContent = `💻 ${hw.cpu_info}`;
            diagGPU.textContent = 'None (Multi-threaded CPU)';
            diagBackend.textContent = 'CPU Multi-threaded Engine';
        }

        diagCPU.textContent = hw.cpu_info;
        diagPyTorch.textContent = hw.torch_version;

        deviceSelector.addEventListener('change', async (e) => {
            const target = e.target.value;
            const res = await eel.set_device(target)();
            if (res.success) {
                hardwareName.textContent = (target === 'cpu') ? `💻 CPU Multi-thread` : `🟢 ${hw.cuda_devices[0]?.name || 'GPU'}`;
            }
        });

        loadSampleImages();

        // --- Free tier UI gating: pure mesh only (clay) — no colors, no textures
        try {
            const lic = await eel.get_license_status()();
            if (!lic.valid || lic.tier === 'free') {
                currentTextureMode = 'none';
                currentBakeTexture = false;
                const clayBtn = textureGroup.querySelector('[data-mode="none"]');
                if (clayBtn) {
                    textureGroup.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
                    clayBtn.classList.add('active');
                }
                textureGroup.querySelectorAll('.segment-btn').forEach(b => {
                    if (b.dataset.mode !== 'none') {
                        b.disabled = true;
                        b.style.opacity = '0.45';
                        b.style.cursor = 'not-allowed';
                        b.title = 'Pro feature — activate a license to unlock colors & textures';
                    }
                });
                if (texResGroupWrapper) texResGroupWrapper.style.display = 'none';
                console.info('Free tier active: mesh only (no colors/textures).');
            }
        } catch (licErr) {
            console.warn('License check failed:', licErr);
        }

    } catch (e) {
        console.warn('Failed to fetch system info:', e);
        hardwareName.textContent = '💻 Standard Engine';
    }
}

btnAbout.addEventListener('click', () => aboutModal.style.display = 'flex');
btnCloseAbout.addEventListener('click', () => aboutModal.style.display = 'none');
btnModalCloseAction.addEventListener('click', () => aboutModal.style.display = 'none');
aboutModal.addEventListener('click', (e) => {
    if (e.target === aboutModal) aboutModal.style.display = 'none';
});

// Initialize
initApp();
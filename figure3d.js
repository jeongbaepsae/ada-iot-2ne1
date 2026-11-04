// 블록 인체 모델 패널.
//
// 외부 모델 대신 관절 구조를 직접 세운다. 리그의 축 규약을 추측할 필요가 없어
// 팔 겨냥이 결정적으로 맞고, 비율·앉은 자세·색을 과제에 맞춰 고를 수 있다.
//
// 관절 규약: 모든 마디는 Group(관절 위치)에 Mesh 를 -Y 로 길이의 절반만큼 내려
// 매단다. 따라서 모든 마디의 쉼 자세 축은 (0,-1,0) 으로 같다.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const DOWN = V(0, -1, 0);

// 성인 기준 치수(m). 서 있을 때 키 약 1.70.
const D = {
  seat: 0.46,                       // 앉은 엉덩이 높이
  pelvis: [0.34, 0.16, 0.22],
  torso: [0.38, 0.50, 0.23],
  neck: 0.085,
  head: [0.23, 0.25, 0.23],
  upperArm: [0.105, 0.29, 0.105],
  foreArm: [0.095, 0.27, 0.095],
  hand: [0.095, 0.13, 0.065],
  thigh: [0.155, 0.42, 0.17],
  shin: [0.13, 0.42, 0.13],
  foot: [0.13, 0.09, 0.27],
  shoulderX: 0.175,
  hipX: 0.105,
};

function box(w, h, d, mat) {
  return new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 3, Math.min(w, h, d) * 0.18), mat);
}

/** 관절 그룹 하나. 길이 len 의 마디를 -Y 로 매단다. */
function limb(parent, at, size, mat) {
  const g = new THREE.Group();
  g.position.copy(at);
  parent.add(g);
  const m = box(size[0], size[1], size[2], mat);
  m.position.y = -size[1] / 2;
  g.add(m);
  g.userData.len = size[1];
  return g;
}

/** 관절을 월드 방향 dir 로 겨냥한다. 모든 마디의 쉼 자세 축은 -Y. */
function aim(group, dirWorld) {
  if (!group || !group.parent) return;
  const q = new THREE.Quaternion();
  group.parent.getWorldQuaternion(q).invert();
  const local = dirWorld.clone().normalize().applyQuaternion(q).normalize();
  group.quaternion.setFromUnitVectors(DOWN, local);
  group.updateMatrixWorld(true);
}

export class Figure {
  constructor(host) {
    this.host = host;
    this.ready = false;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(34, 1, 0.05, 50);
    this.camera.position.set(1.05, 1.45, 2.05);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    host.appendChild(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(0, 0.80, 0);
    this.controls.enableDamping = true;
    this.controls.minDistance = 0.9;
    this.controls.maxDistance = 5;
    this.controls.update();
  }

  _materials(dark) {
    const mk = (c, r = 0.75) => new THREE.MeshStandardMaterial({ color: c, roughness: r, metalness: 0 });
    return dark
      ? { skin: mk(0xc9a07c), shirt: mk(0x3f5a68), pants: mk(0x2b3b45),
          shoe: mk(0x1d272d), chair: mk(0x22303a, .9), limb: mk(0xe8884a, .6),
          eyeWhite: mk(0xf2efe9, .45), pupil: mk(0x1c2429, .35), brow: mk(0x4b3a2c),
          nose: mk(0xbe946f), mouth: mk(0x8d5a52) }
      : { skin: mk(0xd9b08c), shirt: mk(0x7d9aa8), pants: mk(0x5d7684),
          shoe: mk(0x3f5058), chair: mk(0xc3d0d6, .9), limb: mk(0xc0591f, .6),
          eyeWhite: mk(0xfbf9f5, .45), pupil: mk(0x2a3238, .35), brow: mk(0x6b513c),
          nose: mk(0xcc9f79), mouth: mk(0xa8655c) };
  }

  async load() {
    const dark = matchMedia('(prefers-color-scheme: dark)').matches &&
                 document.documentElement.getAttribute('data-theme') !== 'light';
    const M = this._materials(dark);
    this.M = M;

    this.scene.add(new THREE.HemisphereLight(0xffffff, dark ? 0x1a2429 : 0x9fb0b8, 2.0));
    const key = new THREE.DirectionalLight(0xffffff, 1.5);
    key.position.set(2.0, 3.0, 2.2);
    this.scene.add(key);

    const root = new THREE.Group();
    this.scene.add(root);
    this.root = root;

    // 의자
    const chair = new THREE.Group();
    const seat = box(0.44, 0.06, 0.42, M.chair); seat.position.set(0, D.seat - 0.11, 0.06);
    const back = box(0.44, 0.44, 0.05, M.chair); back.position.set(0, D.seat + 0.14, -0.16);
    chair.add(seat, back); root.add(chair);

    // 골반 -> 몸통 -> 머리
    const pelvis = new THREE.Group(); pelvis.position.y = D.seat; root.add(pelvis);
    pelvis.add(box(D.pelvis[0], D.pelvis[1], D.pelvis[2], M.pants));
    const torso = new THREE.Group(); torso.position.y = D.pelvis[1] / 2; pelvis.add(torso);
    const torsoMesh = box(D.torso[0], D.torso[1], D.torso[2], M.shirt);
    torsoMesh.position.y = D.torso[1] / 2; torso.add(torsoMesh);
    const neck = box(0.115, D.neck + 0.03, 0.115, M.skin);
    neck.position.y = D.torso[1] + D.neck / 2 - 0.01; torso.add(neck);
    const headG = new THREE.Group(); headG.position.y = D.torso[1] + D.neck; torso.add(headG);
    const head = box(D.head[0], D.head[1], D.head[2], M.skin);
    head.position.y = D.head[1] / 2; headG.add(head);
    this._face(headG, M);
    this.headG = headG;
    this.noseLocal = V(0, D.seat + D.pelvis[1] / 2 + D.torso[1] + D.neck + D.head[1] * 0.52,
                       D.head[2] / 2 + 0.02);

    // 팔: 어깨 -> 팔꿈치 -> 손
    this.arm = {};
    for (const side of ['L', 'R']) {
      const sx = (side === 'R' ? -1 : 1) * D.shoulderX;   // 화면 기준 오른팔 = -X
      const sh = limb(torso, V(sx, D.torso[1] - 0.045, 0), D.upperArm, M.shirt);
      const el = limb(sh, V(0, -D.upperArm[1], 0), D.foreArm, M.skin);
      const hd = limb(el, V(0, -D.foreArm[1], 0), D.hand, M.skin);
      this.arm[side] = { sh, el, hd };
    }
    // 다리: 고관절 -> 무릎 -> 발
    this.leg = {};
    for (const side of ['L', 'R']) {
      const hx = (side === 'R' ? -1 : 1) * D.hipX;
      const hip = limb(pelvis, V(hx, -D.pelvis[1] / 2 + 0.02, 0), D.thigh, M.pants);
      const knee = limb(hip, V(0, -D.thigh[1], 0), D.shin, M.pants);
      const foot = new THREE.Group(); foot.position.y = -D.shin[1]; knee.add(foot);
      const fm = box(D.foot[0], D.foot[1], D.foot[2], M.shoe);
      fm.position.set(0, -D.foot[1] / 2, D.foot[2] / 2 - 0.06); foot.add(fm);
      this.leg[side] = { hip, knee, foot };
    }
    root.updateMatrixWorld(true);
    this._sit();

    // 표식
    this.marks = new THREE.Group(); this.scene.add(this.marks);
    const dot = (r, c, op = 1) => new THREE.Mesh(new THREE.SphereGeometry(r, 20, 14),
      new THREE.MeshStandardMaterial({ color: c, roughness: .4, transparent: op < 1, opacity: op }));
    this.handDot = dot(0.032, 0xc0591f);
    this.halo = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 16),
      new THREE.MeshBasicMaterial({ color: 0xc0591f, transparent: true, opacity: .18 }));
    this.noseDot = dot(0.022, 0x8498a2, .95);
    this.restDot = dot(0.018, 0x8498a2, .6);
    const tg = new THREE.BufferGeometry();
    tg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(400 * 3), 3));
    tg.setDrawRange(0, 0);
    this.trail = new THREE.Line(tg, new THREE.LineBasicMaterial({ color: 0xc0591f }));
    this.marks.add(this.handDot, this.halo, this.noseDot, this.restDot, this.trail);
    this.cloud = null;

    this.ready = true;
    return this;
  }

  /** 눈·코·입. 얼굴 앞면(+Z)에 얕게 덧붙인다. */
  _face(headG, M) {
    const H = D.head[1], Z = D.head[2] / 2;
    const flat = (w, h, d, mat, x, y, z) => {
      const m = box(w, h, d, mat); m.position.set(x, y, z); headG.add(m); return m;
    };
    // 눈: 흰자 + 눈동자
    for (const sx of [-1, 1]) {
      flat(0.052, 0.042, 0.014, M.eyeWhite, sx * 0.055, H * 0.62, Z - 0.002);
      flat(0.024, 0.028, 0.012, M.pupil,    sx * 0.055, H * 0.615, Z + 0.006);
      flat(0.058, 0.013, 0.012, M.brow,     sx * 0.055, H * 0.745, Z - 0.001);
    }
    // 코: 과제 목표점이기도 하다
    flat(0.040, 0.062, 0.034, M.nose, 0, H * 0.52, Z + 0.008);
    // 입
    flat(0.082, 0.020, 0.014, M.mouth, 0, H * 0.325, Z - 0.001);
    // 귀
    for (const sx of [-1, 1])
      flat(0.020, 0.058, 0.050, M.skin, sx * (D.head[0] / 2), H * 0.57, 0);
  }

  _sit() {
    for (const side of ['L', 'R']) {
      aim(this.leg[side].hip, V(0, -0.10, 1));    // 넓적다리 앞으로
      aim(this.leg[side].knee, V(0, -1, 0.05));   // 정강이 아래로
      aim(this.leg[side].foot, V(0, -1, 0));
      aim(this.arm[side].sh, V(0, -1, 0.08));     // 팔은 기본적으로 내려둔다
      aim(this.arm[side].el, V(0, -1, 0.1));
    }
    this.root.updateMatrixWorld(true);
  }

  /** chain: 뷰어 좌표(x 좌우, y 앞뒤, z 위)의 어깨·팔꿈치·손 */
  pose(chain, opts = {}) {
    if (!this.ready) return;
    const side = chain.right ? 'R' : 'L';
    const A = this.arm[side];
    // 뷰어(x 좌우, y 앞뒤, z 위) -> three(x 좌우, y 위, z 앞뒤).
    // 이 모델은 오른쪽이 -X, 몸 앞쪽이 +Z 다.
    const toW = p => V(-p[0], p[2], p[1]);
    const shW = new THREE.Vector3(); A.sh.getWorldPosition(shW);
    const off = shW.clone().sub(toW(chain.sh));
    this._toWorld = p => toW(p).add(off);
    const elW = toW(chain.el).add(off), wrW = toW(chain.wr).add(off);

    aim(A.sh, elW.clone().sub(shW));
    const elNow = new THREE.Vector3(); A.el.getWorldPosition(elNow);
    aim(A.el, wrW.clone().sub(elNow));
    const hdNow = new THREE.Vector3(); A.hd.getWorldPosition(hdNow);
    aim(A.hd, wrW.clone().sub(hdNow).lengthSq() > 1e-6
      ? wrW.clone().sub(elNow) : V(0, -1, 0));

    // 반대 팔은 내려둔 상태 유지
    const other = this.arm[side === 'L' ? 'R' : 'L'];
    aim(other.sh, V(0, -1, 0.08)); aim(other.el, V(0, -1, 0.1));

    const handW = new THREE.Vector3(); A.hd.getWorldPosition(handW);
    handW.y -= D.hand[1] * 0.5;
    const col = opts.color ?? 0xc0591f;
    this.handDot.position.copy(handW);
    this.handDot.material.color.setHex(col);
    // 후광 반지름 = 실제 떨림 변위(화면 배율 반영). 장식이 아니라 크기 지표다.
    const rMM = (opts.dispMM || 0) * (opts.amp || 1);
    this.halo.position.copy(handW);
    this.halo.scale.setScalar(Math.max(rMM / 1000, 1e-4));
    this.halo.visible = rMM > 0.15;
    this.halo.material.color.setHex(col);
    this.trail.material.color.setHex(col);

    this.noseDot.visible = !!opts.nose;
    if (opts.nose) this.noseDot.position.copy(this.noseLocal);
    this.restDot.visible = !!opts.rest;
    if (opts.rest) this.restDot.position.copy(toW(opts.rest).add(off));

    if (opts.trail && opts.trail.length > 1) {
      const pos = this.trail.geometry.attributes.position;
      const n = Math.min(opts.trail.length, 400);
      for (let i = 0; i < n; i++) {
        const w = toW(opts.trail[opts.trail.length - n + i]).add(off);
        pos.setXYZ(i, w.x, w.y, w.z);
      }
      pos.needsUpdate = true;
      this.trail.geometry.setDrawRange(0, n);
      this.trail.visible = true;
    } else this.trail.visible = false;

    this._cloud(opts.cloud, handW, col);
  }

  _cloud(pts, origin, color) {
    if (this.cloud) { this.scene.remove(this.cloud); this.cloud.geometry.dispose(); this.cloud = null; }
    if (!pts || !pts.length) return;
    const a = new Float32Array(pts.length * 3);
    pts.forEach((p, i) => {
      a[i * 3] = origin.x - p[0]; a[i * 3 + 1] = origin.y + p[2]; a[i * 3 + 2] = origin.z + p[1];
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(a, 3));
    this.cloud = new THREE.Points(g, new THREE.PointsMaterial(
      { color, size: 0.007, transparent: true, opacity: .5 }));
    this.scene.add(this.cloud);
  }

  /** 손 주변을 바짝 당겨 본다. 떨림을 과장하지 않고 '확대'해서 보기 위한 것. */
  focusHand(on, dist = 0.26) {
    this._focus = on;
    this._anchor = null;
    if (!on) {
      this.camera.position.set(1.05, 1.45, 2.05);
      this.controls.target.set(0, 0.80, 0);
      this.controls.minDistance = 0.9;
    } else {
      this.controls.minDistance = 0.06;
      const h = this.handDot.position;
      this.controls.target.copy(h);
      this.camera.position.set(h.x + dist * 0.75, h.y + dist * 0.42, h.z + dist);
    }
    this.controls.update();
  }

  /** 확대 모드에서 카메라가 따라갈 기준점.
   *
   * 손 자체를 따라가면 손이 화면에 고정되고 대신 몸과 배경이 흔들려 보인다.
   * 그래서 **떨림을 뺀** 손 위치(도달 운동만 반영)를 기준으로 삼고, 그마저도
   * 완만하게 쫓아간다. 그래야 배경은 가만히 있고 손만 떤다.
   */
  followAnchor(steadyViewer) {
    if (!this._focus || !steadyViewer || !this._toWorld) return;
    const want = this._toWorld(steadyViewer);
    if (!this._anchor) this._anchor = want.clone();
    this._anchor.lerp(want, 0.10);                 // 저역통과: 남은 미세 변동도 걸러낸다
    const d = this.camera.position.clone().sub(this.controls.target);
    this.controls.target.copy(this._anchor);
    this.camera.position.copy(this._anchor).add(d);
  }

  resize() {
    const r = this.host.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    this.renderer.setSize(r.width, r.height, false);
    this.camera.aspect = r.width / r.height;
    this.camera.updateProjectionMatrix();
  }
  render() { this.controls.update(); this.renderer.render(this.scene, this.camera); }
  get focused() { return !!this._focus; }
}

import re
"""Build the 3D scene with two realistic MakeHuman/MPFB2 characters and render frames.

Run: blender -b -P build_scene.py -- --timeline t.json --out frames/ --start 1 --end 100 [--still 1]
"""
import bpy, sys, os, json, math
from mathutils import Vector, Quaternion
import addon_utils

argv = sys.argv[sys.argv.index("--") + 1:]
A = dict(zip(argv[::2], argv[1::2]))
TL = json.load(open(A["--timeline"]))
FPS = TL["fps"]
OUT = A["--out"]
HDRI = A.get("--hdri", "")
JAW_SIGN = float(A.get("--jaw", "1"))
ARM_SIDE = float(A.get("--armside", "1"))

# ---------- clean scene ----------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
addon_utils.enable("bl_ext.user_default.mpfb", default_set=True)
from bl_ext.user_default.mpfb.services.humanservice import HumanService

DATA = os.path.join(bpy.utils.extension_path_user("bl_ext.user_default.mpfb"), "data")
print("MPFB user data:", DATA, os.listdir(DATA) if os.path.isdir(DATA) else "MISSING")


def assets(sub, ext):
    res = []
    for d, _, fs in os.walk(os.path.join(DATA, sub)):
        for f in fs:
            if f.endswith(ext):
                res.append(os.path.basename(d) + "/" + f)
    return sorted(res)


def pick(sub, ext, *prefs):
    lst = assets(sub, ext)
    print(f"[{sub}] {len(lst)}:", ", ".join(x.split("/")[1] for x in lst))
    for p in prefs:
        words = p.split()
        for x in lst:
            toks = set(re.split(r"[_/.\-]+", x.lower()))
            if all(w in toks or (w.rstrip("0123456789") != w and any(t.startswith(w) for t in toks)) for w in words):
                return x
    return lst[0] if lst else ""


def human(name, pheno, skin_prefs, cloth_prefs, hair_prefs):
    info = HumanService._create_default_human_info_dict()
    info["name"] = name
    info["phenotype"].update(pheno)
    info["rig"] = "default"
    info["skin_mhmat"] = pick("skins", ".mhmat", *skin_prefs)
    info["skin_material_type"] = "ENHANCED_SSS"
    info["eyes"] = pick("eyes", ".mhclo", "high-poly", "")
    info["eyebrows"] = pick("eyebrows", ".mhclo", "eyebrow001", "")
    info["eyelashes"] = pick("eyelashes", ".mhclo", "eyelashes01", "")
    info["teeth"] = pick("teeth", ".mhclo", "teeth_base", "")
    info["tongue"] = pick("tongue", ".mhclo", "tongue01", "")
    info["hair"] = pick("hair", ".mhclo", *hair_prefs)
    clothes = []
    for group in cloth_prefs:
        c = pick("clothes", ".mhclo", *group)
        if c and c not in clothes:
            clothes.append(c)
    info["clothes"] = clothes
    print(name, "INFO", {k: info[k] for k in ["skin_mhmat", "hair", "clothes", "eyes"]})
    s = HumanService.get_default_deserialization_settings()
    s["subdiv_levels"] = 1
    body = HumanService.deserialize_from_dict(info, s)
    rig = body.parent
    return body, rig


AFR = {"african": 0.9, "caucasian": 0.05, "asian": 0.05}
rich_body, rich = human(
    "Kwame", {"gender": 1.0, "age": 0.62, "weight": 0.68, "muscle": 0.45, "height": 0.6, "race": AFR},
    ["middleage african male", "african male", "male"],
    [["male_elegantsuit01"], ["shoes01"]], ["short02", ""])
poor_body, poor = human(
    "Kofi", {"gender": 1.0, "age": 0.5, "weight": 0.4, "muscle": 0.62, "height": 0.55, "race": AFR},
    ["young african male", "african male", "male"],
    [["male_worksuit01"], ["shoes03"]], ["short01", ""])

rich.location = (-0.42, 0, 0)
rich.rotation_euler = (0, 0, math.radians(68))
poor.location = (0.42, 0, 0)
poor.rotation_euler = (0, 0, math.radians(-68))
bpy.context.view_layer.update()

# ---------- posing ----------
ARM_BONES = ["upperarm01", "upperarm02", "lowerarm01", "lowerarm02"]


def aim(rig, bone, direction):
    pb = rig.pose.bones[bone]
    cur = (pb.tail - pb.head).normalized()
    q = cur.rotation_difference(Vector(direction).normalized())
    m = pb.matrix.copy()
    loc = m.translation.copy()
    nm = q.to_matrix().to_4x4() @ m
    nm.translation = loc
    pb.matrix = nm
    bpy.context.view_layer.update()


def snapshot(rig, bones):
    return {b: rig.pose.bones[b].rotation_quaternion.copy() for b in bones}


def setup_rig(rig, gesture):
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
    # armature space: character faces -Y, left side is +X
    for side, sx in (("L", 1), ("R", -1)):
        aim(rig, f"upperarm01.{side}", (sx * 0.18 * ARM_SIDE, 0.02, -1))
        aim(rig, f"upperarm02.{side}", (sx * 0.18 * ARM_SIDE, 0.02, -1))
        aim(rig, f"lowerarm01.{side}", (sx * 0.12 * ARM_SIDE, -0.35, -1))
        aim(rig, f"lowerarm02.{side}", (sx * 0.12 * ARM_SIDE, -0.35, -1))
    bones = [f"{b}.{s}" for b in ARM_BONES for s in "LR"]
    base = snapshot(rig, bones)
    # gesture pose
    if gesture == "point":  # right arm points forward at the other person
        aim(rig, "upperarm01.R", (-0.25, -0.75, -0.45))
        aim(rig, "upperarm02.R", (-0.25, -0.75, -0.45))
        aim(rig, "lowerarm01.R", (-0.1, -1, -0.05))
        aim(rig, "lowerarm02.R", (-0.1, -1, -0.05))
    else:  # open palms: both forearms forward
        for side, sx in (("L", 1), ("R", -1)):
            aim(rig, f"lowerarm01.{side}", (sx * 0.3, -1, -0.15))
            aim(rig, f"lowerarm02.{side}", (sx * 0.3, -1, -0.15))
    gest = snapshot(rig, bones)
    for b, q in base.items():
        rig.pose.bones[b].rotation_quaternion = q
    return bones, base, gest


rich_bones, rich_base, rich_gest = setup_rig(rich, "point")
poor_bones, poor_base, poor_gest = setup_rig(poor, "open")


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def local(axis, ang):
    return Quaternion(axis, ang)


def animate(rig, who, bones, base, gest, phase):
    head = rig.pose.bones["head"]
    jaw = rig.pose.bones["jaw"]
    spine = rig.pose.bones["spine03"]
    neck = rig.pose.bones["neck02"]
    h0, j0, s0, n0 = head.rotation_quaternion.copy(), jaw.rotation_quaternion.copy(), spine.rotation_quaternion.copy(), neck.rotation_quaternion.copy()
    for f in range(1, TL["frames"] + 1):
        t = (f - 1) / FPS
        env, w = 0.0, 0.0
        for ln in TL["lines"]:
            if ln["who"] != who:
                continue
            if ln["start"] <= t < ln["end"]:
                k = int((t - ln["start"]) * FPS)
                env = ln["env"][min(k, len(ln["env"]) - 1)]
            if ln["gesture"] != "none":
                w = max(w, smooth((t - ln["start"] + 0.1) / 0.4) * (1 - smooth((t - ln["end"] + 0.1) / 0.5)))
        breathe = math.sin(t * 2 * math.pi / 3.8 + phase)
        spine.rotation_quaternion = s0 @ local((1, 0, 0), 0.015 * breathe)
        neck.rotation_quaternion = n0 @ local((0, 0, 1), 0.03 * math.sin(t * 0.7 + phase))
        nod = env * 0.07 + 0.02 * math.sin(t * 4.3 + phase) * (1 if env > 0.05 else 0.3)
        head.rotation_quaternion = h0 @ local((1, 0, 0), nod) @ local((0, 1, 0), 0.025 * math.sin(t * 1.1 + phase))
        jaw.rotation_quaternion = j0 @ local((1, 0, 0), JAW_SIGN * 0.28 * env)
        for b in bones:
            q = base[b].slerp(gest[b], w)
            rig.pose.bones[b].rotation_quaternion = q
        for pb in [head, jaw, spine, neck] + [rig.pose.bones[b] for b in bones]:
            pb.keyframe_insert("rotation_quaternion", frame=f)


animate(rich, "rich", rich_bones, rich_base, rich_gest, 0.0)
animate(poor, "poor", poor_bones, poor_base, poor_gest, 1.7)

# ---------- world, floor, lights ----------
scn = bpy.context.scene
world = bpy.data.worlds.new("W")
scn.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]
if HDRI and os.path.exists(HDRI):
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI)
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.8
else:
    bg.inputs["Color"].default_value = (0.05, 0.06, 0.08, 1)

bpy.ops.mesh.primitive_plane_add(size=40)
floor = bpy.context.object
fm = bpy.data.materials.new("floor")
fm.use_nodes = True
p = fm.node_tree.nodes["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.18, 0.17, 0.16, 1)
p.inputs["Roughness"].default_value = 0.55
floor.data.materials.append(fm)


def light(name, loc, energy, size, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.size, d.color = energy, size, color
    o = bpy.data.objects.new(name, d)
    scn.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector((0, 0, 1.4)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


light("key", (-1.6, -2.4, 2.6), 260, 1.8, (1, 0.93, 0.85))
light("fill", (2.0, -2.2, 1.8), 90, 2.5, (0.85, 0.9, 1))
light("rimL", (-1.5, 2.0, 2.2), 180, 1.0, (1, 0.8, 0.6))
light("rimR", (1.5, 2.0, 2.2), 180, 1.0, (0.7, 0.8, 1))

# ---------- cameras ----------
def head_pos(rig):
    return rig.matrix_world @ rig.pose.bones["head"].head


bpy.context.view_layer.update()
hr, hp = head_pos(rich) + Vector((0, 0, 0.06)), head_pos(poor) + Vector((0, 0, 0.06))


def camera(name, loc, target, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.dof.use_dof = True
    cd.dof.focus_distance = (Vector(target) - Vector(loc)).length
    cd.dof.aperture_fstop = 2.2
    o = bpy.data.objects.new(name, cd)
    scn.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


mid = (hr + hp) / 2
cam_wide = camera("wide", mid + Vector((0, -3.4, -0.1)), mid - Vector((0, 0, 0.35)), 35)
cam_rich = camera("on_rich", hr + Vector((0.95, -1.15, 0.0)), hr, 70)
cam_poor = camera("on_poor", hp + Vector((-0.95, -1.15, 0.0)), hp, 70)
# slow push-in on the wide camera
cam_wide.keyframe_insert("location", frame=1)
cam_wide.location += Vector((0, 0.6, 0.05))
cam_wide.keyframe_insert("location", frame=TL["frames"])

shots = {"rich": cam_rich, "poor": cam_poor, "narrator": cam_wide}
scn.timeline_markers.new("s0", frame=1).camera = cam_wide
for i, ln in enumerate(TL["lines"]):
    if i == 0:
        continue
    m = scn.timeline_markers.new(f"s{i}", frame=max(2, int((ln["start"] - 0.25) * FPS)))
    m.camera = shots[ln["who"]]
scn.camera = cam_wide

# ---------- render settings ----------
scn.render.engine = "CYCLES"
scn.cycles.device = "CPU"
scn.cycles.samples = int(A.get("--samples", "24"))
scn.cycles.use_denoising = True
scn.cycles.max_bounces = 4
scn.cycles.use_adaptive_sampling = True
scn.render.use_persistent_data = True
scn.render.resolution_x, scn.render.resolution_y = 720, 1280
scn.render.fps = FPS
scn.view_settings.view_transform = "AgX"
scn.view_settings.look = "AgX - Medium High Contrast"
scn.render.image_settings.file_format = "PNG"
scn.frame_start = 1
scn.frame_end = TL["frames"]

os.makedirs(OUT, exist_ok=True)
if "--still" in A:
    for i, ln in enumerate(TL["lines"][:4]):
        f = int(((ln["start"] + ln["end"]) / 2) * FPS)
        scn.frame_set(f)
        scn.render.filepath = os.path.join(OUT, f"still_{i}_{f:05d}.png")
        bpy.ops.render.render(write_still=True)
else:
    for f in range(int(A["--start"]), min(int(A["--end"]), TL["frames"]) + 1):
        scn.frame_set(f)
        scn.render.filepath = os.path.join(OUT, f"{f:05d}.png")
        bpy.ops.render.render(write_still=True)
        print("rendered", f, flush=True)

import bpy
from bpy.app.handlers import persistent
from . import utils
from . import bones


def simplify_modes(mode):
    if mode == 'EDIT':
        return mode
    else:
        return 'POSE'


@utils.event("update")
def event_update(context):
    bpy.ops.rigid_body_bones.update()


@utils.event("rigid_body")
@utils.if_armature_enabled
def event_rigid_body(context, armature, top):
    for bone in armature.data.bones:
        data = bone.rigid_body_bones

        if data.active:
            bones.update_rigid_body(data.active.rigid_body, data)

        elif data.passive:
            bones.update_rigid_body(data.passive.rigid_body, data)


@utils.event("rigid_body_constraint")
@utils.if_armature_enabled
def event_rigid_body_constraint(context, armature, top):
    for bone in armature.data.bones:
        data = bone.rigid_body_bones

        if data.constraint:
            bones.update_constraint(data.constraint.rigid_body_constraint, data)


@utils.event("align")
@utils.if_armature_enabled
def event_align(context, armature, top):
    for pose_bone in armature.pose.bones:
        bone = pose_bone.bone
        data = bone.rigid_body_bones

        if data.active:
            bones.align_hitbox(data.active, bone, data)

        elif data.passive:
            bones.align_hitbox(data.passive, bone, data)

        bones.update_pose_constraint(pose_bone)


@utils.event("collision_shape")
@utils.if_armature_enabled
def event_collision_shape(context, armature, top):
    for bone in armature.data.bones:
        data = bone.rigid_body_bones

        if data.active:
            bones.update_shape(data.active, type=data.collision_shape)

        elif data.passive:
            bones.update_shape(data.passive, type=data.collision_shape)


@utils.event("hide_hitboxes")
@utils.if_armature_enabled
def event_hide_hitboxes(context, armature, top):
    if top.actives:
        top.actives.hide_viewport = top.hide_hitboxes

    if top.passives:
        top.passives.hide_viewport = top.hide_hitboxes


@utils.event("hide_active_bones")
@utils.if_armature_enabled
def event_hide_active_bones(context, armature, top):
    for bone in armature.data.bones:
        data = bone.rigid_body_bones
        bones.hide_active_bone(bone, data, top.hide_active_bones)


def event_dirty(self, context):
    global dirty
    dirty = True


dirty = False
timer_delay = 0.1

def timer():
    global dirty

    if dirty:
        context = bpy.context

        armature = context.active_object

        if armature and armature.type == 'ARMATURE':
            dirty = False
            event_update(None, context)

    return timer_delay


def mode_switch():
    global dirty

    context = bpy.context

    armature = context.active_object

    if armature and armature.type == 'ARMATURE':
        top = armature.data.rigid_body_bones

        mode = simplify_modes(armature.mode)

        if top.mode != mode:
            top.mode = mode
            #dirty = True
            event_update(None, context)


owner = object()

def register_subscribers():
    bpy.msgbus.clear_by_owner(owner)

    bpy.msgbus.subscribe_rna(
        key=(bpy.types.Object, "mode"),
        owner=owner,
        args=(),
        notify=mode_switch,
        # TODO does this need PERSISTENT ?
        options={'PERSISTENT'}
    )

@persistent
def load_post(dummy):
    register_subscribers()


def register():
    utils.debug("REGISTER EVENTS")

    # This is needed in order to re-subscribe when the file changes
    bpy.app.handlers.load_post.append(load_post)

    register_subscribers()

    # This is used to run the event_update function asynchronously,
    # during the main event loop.
    bpy.app.timers.register(
        timer,
        first_interval=timer_delay,
        persistent=True,
    )


def unregister():
    utils.debug("UNREGISTER EVENTS")

    if bpy.app.timers.is_registered(timer):
        bpy.app.timers.unregister(timer)

    if load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_post)

    bpy.msgbus.clear_by_owner(owner)

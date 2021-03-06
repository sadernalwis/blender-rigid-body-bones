import bpy
from bpy.app.handlers import persistent
from . import utils
from . import bones


def simplify_modes(mode):
    if mode == 'EDIT':
        return mode
    else:
        return 'POSE'


def event_dirty(self, context):
    mark_dirty(context)


@utils.event("rigid_body")
@utils.if_armature_enabled
def event_rigid_body(context, armature, top):
    if not is_dirty(context.scene.rigid_body_bones, armature):
        for bone in armature.data.bones:
            data = bone.rigid_body_bones

            if data.active:
                bones.update_rigid_body(data.active.rigid_body, data)

            elif data.passive:
                bones.update_rigid_body(data.passive.rigid_body, data)


@utils.event("rigid_body_constraint")
@utils.if_armature_enabled
def event_rigid_body_constraint(context, armature, top):
    if not is_dirty(context.scene.rigid_body_bones, armature):
        for bone in armature.data.bones:
            data = bone.rigid_body_bones

            if data.constraint:
                bones.update_constraint(data.constraint.rigid_body_constraint, data)


@utils.event("align")
@utils.if_armature_enabled
def event_align(context, armature, top):
    if not is_dirty(context.scene.rigid_body_bones, armature):
        utils.reset_frame(context)

        for pose_bone in armature.pose.bones:
            bone = pose_bone.bone
            data = bone.rigid_body_bones

            if data.active:
                bones.align_hitbox(data.active, bone, data)

            elif data.passive:
                bones.align_hitbox(data.passive, bone, data)

            if data.origin_empty:
                bones.align_origin(data.origin_empty, bone, data)

            bones.update_pose_constraint(pose_bone)


@utils.event("hide_hitboxes")
@utils.if_armature_enabled
def event_hide_hitboxes(context, armature, top):
    if top.actives:
        top.actives.hide_viewport = top.hide_hitboxes

    if top.passives:
        top.passives.hide_viewport = top.hide_hitboxes

    if top.compounds:
        top.compounds.hide_viewport = top.hide_hitboxes

    if top.origins:
        top.origins.hide_viewport = top.hide_hitbox_origins


@utils.event("hide_active_bones")
@utils.if_armature_enabled
def event_hide_active_bones(context, armature, top):
    for bone in armature.data.bones:
        data = bone.rigid_body_bones
        bones.hide_active_bone(bone, data, top.hide_active_bones)


def is_dirty(scene, armature):
    for dirty in scene.dirties:
        if dirty.armature and dirty.armature.name == armature.name:
            return True

    return False


# This is used to run the update operator during the next
# main event tick.
#
# It also causes multiple update operations to be batched
# into one operation, which makes Alt updating work correctly.
def mark_dirty(context):
    assert utils.is_armature(context)

    armature = context.active_object
    scene = context.scene.rigid_body_bones

    # Don't add duplicate objects
    if not is_dirty(scene, armature):
        dirty = scene.dirties.add()
        dirty.armature = armature

    if len(scene.dirties) > 0:
        if not bpy.app.timers.is_registered(next_tick):
            bpy.app.timers.register(next_tick)


@utils.timed("update")
def next_tick():
    context = bpy.context
    scene = context.scene.rigid_body_bones

    with utils.Selected(context), utils.Selectable(context):
        for dirty in scene.dirties:
            if dirty.armature:
                utils.select_active(context, dirty.armature)
                assert context.active_object.name == dirty.armature.name
                bpy.ops.rigid_body_bones.update()

    scene.dirties.clear()


def mode_switch():
    context = bpy.context

    if utils.is_armature(context):
        armature = context.active_object
        top = armature.data.rigid_body_bones

        mode = simplify_modes(armature.mode)

        if top.mode != mode:
            top.mode = mode
            mark_dirty(context)


# This is needed to cleanup the rigid body objects when the armature is deleted
def cleanup_armatures():
    if bpy.ops.rigid_body_bones.cleanup_armatures.poll():
        bpy.ops.rigid_body_bones.cleanup_armatures()

    return 5.0


@persistent
def fix_undo(scene):
    context = bpy.context

    if utils.is_armature(context):
        mark_dirty(context)


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

    # This is needed in order to fix up problems caused by undo/redo
    #bpy.app.handlers.undo_post.append(fix_undo)
    #bpy.app.handlers.redo_post.append(fix_undo)

    bpy.app.timers.register(cleanup_armatures, persistent=True)

    register_subscribers()


def unregister():
    utils.debug("UNREGISTER EVENTS")

    if bpy.app.timers.is_registered(cleanup_armatures):
        bpy.app.timers.unregister(cleanup_armatures)

    if bpy.app.timers.is_registered(next_tick):
        bpy.app.timers.unregister(next_tick)

    if fix_undo in bpy.app.handlers.redo_post:
        bpy.app.handlers.redo_post.remove(fix_undo)

    if fix_undo in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(fix_undo)

    if load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_post)

    bpy.msgbus.clear_by_owner(owner)

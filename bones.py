import bpy
from math import radians
from mathutils import Vector, Euler
from . import armatures
from . import utils


def bone_to_object_space(vector):
    vector.rotate(Euler((radians(90.0), 0.0, 0.0)))

def hitbox_dimensions(bone):
    dimensions = bone.rigid_body_bones.scale * bone.length
    bone_to_object_space(dimensions)
    return dimensions


def init_hitbox(object):
    object.hide_render = True
    object.show_in_front = True
    object.display.show_shadows = False


def show_bounds(object, type):
    object.show_bounds = True
    object.display_type = 'BOUNDS'
    object.display_bounds_type = type


def update_shape(object, type):
    object.rigid_body.collision_shape = type

    if type == 'CONVEX_HULL' or type == 'MESH':
        object.show_bounds = False
        object.display_type = 'WIRE'
        object.display_bounds_type = 'BOX'

    else:
        show_bounds(object, type)


def update_rigid_body(rigid_body, data):
    rigid_body.mass = data.mass
    rigid_body.friction = data.friction
    rigid_body.restitution = data.restitution
    rigid_body.linear_damping = data.linear_damping
    rigid_body.angular_damping = data.angular_damping
    rigid_body.use_margin = data.use_margin
    rigid_body.collision_margin = data.collision_margin
    rigid_body.collision_collections = data.collision_collections
    rigid_body.use_deactivation = data.use_deactivation
    rigid_body.use_start_deactivated = data.use_start_deactivated
    rigid_body.deactivate_linear_velocity = data.deactivate_linear_velocity
    rigid_body.deactivate_angular_velocity = data.deactivate_angular_velocity


def make_empty_rigid_body(context, name, collection, parent):
    mesh = bpy.data.meshes.new(name=name)
    body = bpy.data.objects.new(name, mesh)
    collection.objects.link(body)

    body.parent = parent
    body.parent_type = 'OBJECT'

    with utils.Selected(context), utils.Selectable(armatures.root_collection(context)):
        utils.select(context, [body])
        bpy.ops.rigidbody.object_add(type='PASSIVE')

    body.rigid_body.kinematic = True
    body.rigid_body.collision_collections[0] = False
    body.hide_select = True
    body.hide_viewport = True
    init_hitbox(body)
    show_bounds(body, type='BOX')

    return body


def make_empty(context, name, collection, parent):
    empty = bpy.data.objects.new(name=name, object_data=None)
    collection.objects.link(empty)

    empty.parent = parent
    empty.parent_type = 'OBJECT'

    with utils.Selected(context), utils.Selectable(armatures.root_collection(context)):
        utils.select(context, [empty])
        bpy.ops.rigidbody.constraint_add(type='FIXED')

    empty.hide_select = True
    empty.hide_viewport = True
    #init_hitbox(empty)

    return empty


def create_constraint(context, armature, bone):
    data = bone.rigid_body_bones

    if not data.constraint:
        constraint = make_empty(
            context,
            name=bone.name + " [Head]",
            collection=armatures.constraints_collection(context, armature),
            parent=armature,
        )

        data.constraint = constraint


def constraint_location(bone):
    location = bone.rigid_body_bones.location.copy()
    bone_to_object_space(location)
    location += bone.center
    return location


def hitbox_location(bone, type):
    data = bone.rigid_body_bones

    length = bone.length
    origin = length * (data.origin - 0.5)

    location = Vector((0.0, -origin * data.scale.y, 0.0))
    location.rotate(data.rotation)

    location.y += origin - (length * 0.5)
    location += data.location

    if type == 'ACTIVE':
        bone_to_object_space(location)
        location += bone.tail

    return location


def hitbox_rotation(bone, type):
    if type == 'ACTIVE':
        rotation = bone.rigid_body_bones.rotation.copy()
        rotation.rotate(bone.matrix.to_euler())
        rotation.rotate_axis('X', radians(90.0))
        return rotation

    else:
        rotation = Euler((radians(90.0), 0.0, 0.0))
        rotation.rotate(bone.rigid_body_bones.rotation)
        return rotation


def make_active_hitbox(context, armature, bone):
    data = bone.rigid_body_bones

    hitbox = utils.make_cube(
        name=bone.name + " [Hitbox]",
        dimensions=hitbox_dimensions(bone),
        collection=armatures.hitboxes_collection(context, armature),
    )

    hitbox.parent = armature
    hitbox.parent_type = 'OBJECT'

    hitbox.rotation_euler = hitbox_rotation(bone, 'ACTIVE')
    hitbox.location = hitbox_location(bone, 'ACTIVE')

    with utils.Selected(context), utils.Selectable(armatures.root_collection(context)):
        utils.select(context, [hitbox])
        bpy.ops.rigidbody.object_add(type='ACTIVE')
        update_rigid_body(hitbox.rigid_body, data)
        init_hitbox(hitbox)
        update_shape(hitbox, type=data.collision_shape)

    return hitbox


def make_passive_hitbox(context, armature, bone):
    data = bone.rigid_body_bones

    hitbox = utils.make_cube(
        name=bone.name + " [Hitbox]",
        dimensions=hitbox_dimensions(bone),
        collection=armatures.hitboxes_collection(context, armature),
    )

    hitbox.parent = armature
    hitbox.parent_type = 'BONE'
    hitbox.parent_bone = bone.name

    hitbox.rotation_euler = hitbox_rotation(bone, 'PASSIVE')
    hitbox.location = hitbox_location(bone, 'PASSIVE')

    with utils.Selected(context), utils.Selectable(armatures.root_collection(context)):
        utils.select(context, [hitbox])
        bpy.ops.rigidbody.object_add(type='PASSIVE')
        hitbox.rigid_body.kinematic = True
        init_hitbox(hitbox)
        update_shape(hitbox, type=data.collision_shape)

    return hitbox


def create(context, armature, bone):
    data = bone.rigid_body_bones

    if not data.hitbox:
        if data.type == 'ACTIVE':
            data.hitbox = make_active_hitbox(context, armature, bone)

        else:
            data.hitbox = make_passive_hitbox(context, armature, bone)


def remove(context, armature, bone):
    data = bone.rigid_body_bones

    if data.hitbox:
        utils.remove_object(data.hitbox)
        data.hitbox = None

    if data.constraint:
        utils.remove_object(data.constraint)
        data.constraint = None


def initialize(context, armature, bone):
    data = bone.rigid_body_bones

    if data.enabled:
        create(context, armature, bone)


def is_active(bone):
    data = bone.rigid_body_bones
    return data.enabled and data.type == 'ACTIVE'


def align_hitbox(bone):
    data = bone.rigid_body_bones

    if data.hitbox:
        data.hitbox.location = hitbox_location(bone, data.type)
        data.hitbox.rotation_euler = hitbox_rotation(bone, data.type)
        utils.set_mesh_cube(data.hitbox.data, hitbox_dimensions(bone))


def remove_parent(bone):
    data = bone.rigid_body_bones

    if data.enabled and data.type == 'ACTIVE':
        assert data.is_property_set("parent")
        assert data.is_property_set("use_connect")
        bone.parent = None


def store_parent(bone, armature_enabled):
    data = bone.rigid_body_bones

    assert not data.is_property_set("parent")
    assert not data.is_property_set("use_connect")

    if data.enabled and data.type == 'ACTIVE':
        parent = bone.parent

        if parent:
            name = parent.name
            parent.rigid_body_bones.name = name
            data.parent = name

        else:
            data.parent = ""

        data.use_connect = bone.use_connect

        if armature_enabled:
            bone.parent = None


def restore_parent(bone, mapping, delete):
    data = bone.rigid_body_bones

    if data.is_property_set("parent"):
        assert data.is_property_set("use_connect")

        if data.parent == "":
            bone.parent = None

        else:
            parent = mapping.get(data.parent)

            #parent = None

            # TODO make this faster somehow
            #for x in armature.data.edit_bones:
                #if x.rigid_body_bones.name == data.parent:
                    #parent = x
                    #break

            if parent is None:
                utils.error("[{}] could not find parent \"{}\"".format(bone.name, data.parent))

            bone.parent = parent

        bone.use_connect = data.use_connect

        if delete:
            data.property_unset("use_connect")
            data.property_unset("parent")

    else:
        assert not data.is_property_set("use_connect")


@utils.bone_event("type")
def event_type(context, armature, bone, data):
    remove(context, armature, bone)
    initialize(context, armature, bone)


@utils.bone_event("collision_shape")
def event_collision_shape(context, armature, bone, data):
    if data.hitbox:
        update_shape(data.hitbox, data.collision_shape)


@utils.bone_event("location")
def event_location(context, armature, bone, data):
    if data.hitbox:
        data.hitbox.location = hitbox_location(bone, data.type)

@utils.bone_event("rotation")
def event_rotation(context, armature, bone, data):
    if data.hitbox:
        data.hitbox.rotation_euler = hitbox_rotation(bone, data.type)

@utils.bone_event("scale")
def event_scale(context, armature, bone, data):
    if data.hitbox:
        utils.set_mesh_cube(data.hitbox.data, hitbox_dimensions(bone))

@utils.bone_event("rigid_body")
def event_rigid_body(context, armature, bone, data):
    if data.hitbox:
        update_rigid_body(data.hitbox.rigid_body, data)


@utils.bone_event("enabled")
def event_enabled(context, armature, bone, data):
    if data.enabled:
        create(context, armature, bone)

    else:
        remove(context, armature, bone)
        armatures.safe_remove_collections(context, armature)

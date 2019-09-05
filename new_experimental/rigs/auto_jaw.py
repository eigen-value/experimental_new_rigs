#######################################################################################################################
# Automation jaw contruction rules:
# - make a main bone with a connected children. The tail of the connected children
# is the chin point its head is the jaw pivot
# - make 4 bones for the mouth. Parent them unconnected to the main bone
#######################################################################################################################

import bpy
from rna_prop_ui import rna_idprop_ui_prop_get

from rigify.utils import copy_bone, align_bone_z_axis, align_bone_y_axis
from rigify.utils import strip_org, make_mechanism_name
from rigify.utils import MetarigError
from rigify.utils import create_cube_widget
from rigify.rigs.widgets import create_jaw_widget
from .meshy_rig import MeshyRig
from .control_layers_generator import ControlLayersGenerator
from .utils import make_constraints_from_string
from mathutils import Vector

script = """
all_controls   = [%s]
jaw_ctrl_name  = '%s'

if is_selected(all_controls):
    layout.prop(pose_bones[jaw_ctrl_name],  '["%s"]', slider=True)
"""


class Rig(MeshyRig):

    def __init__(self, obj, bone_name, params):

        super().__init__(obj, bone_name, params)

        self.main_mch = self.get_jaw()
        self.lip_len = None
        self.mouth_bones = self.get_mouth()
        self.rotation_mode = params.rotation_mode

        self.layer_generator = ControlLayersGenerator(self)

    def get_jaw(self):
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        name = ""
        for child in edit_bones[self.bones['org'][0]].children:
            if child.use_connect:
                name = child.name

        return name

    def get_mouth(self):
        """
        Returns the mouth bones placeholders
        :return:
        """

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        lip_bones = []
        for child in edit_bones[self.bones['org'][0]].children:
            if not child.use_connect:
                lip_bones.append(child.name)

        # Rule check
        if len(lip_bones) != 4:
            raise MetarigError("Exactly 4 disconnected placeholder bones (lip angles) must be parented to main bone")

        mouth_bones_dict = {'top': [], 'corners': [], 'bottom': []}

        m_b_z_positions = [edit_bones[name].head.z for name in lip_bones]

        top_idx = m_b_z_positions.index(max(m_b_z_positions))
        mouth_bones_dict['top'].append(lip_bones[top_idx])

        bottom_idx = m_b_z_positions.index(min(m_b_z_positions))
        mouth_bones_dict['bottom'].append(lip_bones[bottom_idx])

        for i, b in enumerate(lip_bones):
            if i not in [top_idx, bottom_idx]:
                mouth_bones_dict['corners'].append(b)

        print(mouth_bones_dict)

        return mouth_bones_dict

    def orient_org_bones(self):

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        if self.rotation_mode == 'automatic':
            alignment_axis = edit_bones[self.main_mch].tail - edit_bones[self.base_bone].head
            align_bone_z_axis(self.obj, self.main_mch, alignment_axis)

    def create_mch(self):
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        main_bone_name = strip_org(self.bones['org'][0])
        mouth_lock_name = make_mechanism_name(main_bone_name + "_lock")
        mouth_lock = copy_bone(self.obj, self.main_mch, mouth_lock_name)

        self.bones['jaw_mch'] = dict()
        self.bones['jaw_mch']['mouth_lock'] = mouth_lock
        self.bones['jaw_mch']['jaw_masters'] = []

        jaw_masters_number = 3

        for i in range(0, jaw_masters_number):
            jaw_m_name = make_mechanism_name("jaw_master")
            jaw_m = copy_bone(self.obj, self.main_mch, jaw_m_name)
            div_len = (edit_bones[mouth_lock].length/(jaw_masters_number + 1))
            edit_bones[jaw_m].length = (jaw_masters_number - i) * div_len
            edit_bones[jaw_m].use_connect = False

            self.bones['jaw_mch']['jaw_masters'].append(jaw_m)

        # create remaining subchain mch-s
        super().create_mch()

    def create_def(self):
        # create remaining subchain def-s
        super().create_def()

    def create_controls(self):
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        self.bones['jaw_ctrl'] = dict()

        jaw_ctrl_name = "jaw_master"

        jaw_ctrl = copy_bone(self.obj, self.main_mch, jaw_ctrl_name)
        self.bones['jaw_ctrl']['jaw'] = jaw_ctrl
        edit_bones[jaw_ctrl].use_connect = False

        super().create_controls()

        ctrls = self.get_all_ctrls()

        for ctrl in ctrls:
            align_bone_y_axis(self.obj, ctrl, Vector((0, 0, 1)))

    def make_constraints(self):
        """
        Make constraints
        :return:
        """

        bpy.ops.object.mode_set(mode='OBJECT')
        pose_bones = self.obj.pose.bones

        owner = pose_bones[self.bones['jaw_mch']['mouth_lock']]
        subtarget = self.bones['jaw_ctrl']['jaw']
        make_constraints_from_string(owner, self.obj, subtarget, "CT0.2WW0.0")

        influence_div = 1/len(self.bones['jaw_mch']['jaw_masters'])
        for i, j_m in enumerate(self.bones['jaw_mch']['jaw_masters']):
            owner = pose_bones[j_m]
            subtarget = self.bones['jaw_ctrl']['jaw']
            influence = 1 - i * influence_div
            make_constraints_from_string(owner, self.obj, subtarget, "CT%sWW0.0" % influence)
            if j_m != self.bones['jaw_mch']['jaw_masters'][-1]:
                owner = pose_bones[j_m]
                subtarget = self.bones['jaw_mch']['mouth_lock']
                make_constraints_from_string(owner, self.obj, subtarget, "CT0.0WW0.0")
            # add limits on upper_lip jaw_master
            if j_m == self.bones['jaw_mch']['jaw_masters'][-2]:
                make_constraints_from_string(owner, self.obj, "", "LLmY0mZ0#LRmX0MX%f" % (3.14/2))

        # lip_bones = []
        # lip_bones.extend(self.mouth_bones['top'])
        # lip_bones.extend(self.mouth_bones['bottom'])
        #
        # for lip_bone in lip_bones:
        #     lip_bone = strip_org(lip_bone)
        #     total_len = 0
        #     influence_share = []
        #     for def_b in self.bones['def'][lip_bone]:
        #         total_len += pose_bones[def_b].length
        #         influence_share.append(total_len)
        #     influence_share = [val / total_len for val in influence_share]
        #     for i, ctrl in enumerate(self.bones['ctrl'][lip_bone][1:-1]):
        #         owner = pose_bones[self.bones['ctrl'][lip_bone][i+1]]
        #         subtarget = self.bones['ctrl'][lip_bone][-1]
        #         infl = influence_share[i]
        #         make_constraints_from_string(owner, self.obj, subtarget, "CL%sLLO0.0" % infl)
        #         subtarget = self.bones['ctrl'][lip_bone][0]
        #         infl = 1 - influence_share[i]
        #         make_constraints_from_string(owner, self.obj, subtarget, "CL%sLLO0.0" % infl)
        #         make_constraints_from_string(owner, self.obj, subtarget, "CR1.0LLO0.0")
        #         make_constraints_from_string(owner, self.obj, subtarget, "CS1.0LLO0.0")

        # make the standard bendy rig constraints
        super().make_constraints()

    def parent_bones(self):
        """
        Parent jaw bones
        :return:
        """

        bpy.ops.object.mode_set(mode='EDIT')
        edit_bones = self.obj.data.edit_bones

        # Parenting to jaw MCHs
        jaw_masters = self.bones['jaw_mch']['jaw_masters']
        top_main = self.get_ctrl_by_index(strip_org(self.mouth_bones['top'][0]), 0)
        corner_1 = self.get_ctrl_by_index(strip_org(self.mouth_bones['corners'][0]), 0)
        corner_2 = self.get_ctrl_by_index(strip_org(self.mouth_bones['corners'][1]), 0)
        bottom_main = self.get_ctrl_by_index(strip_org(self.mouth_bones['bottom'][0]), 0)

        edit_bones[top_main].parent = edit_bones[jaw_masters[0]]
        edit_bones[corner_1].parent = edit_bones[jaw_masters[1]]
        edit_bones[corner_2].parent = edit_bones[jaw_masters[1]]
        edit_bones[bottom_main].parent = edit_bones[jaw_masters[2]]

        # parenting what's connected to main jaw mch to jaw ctrl
        for child in edit_bones[self.main_mch].children:
            child.parent = edit_bones[self.bones['jaw_ctrl']['jaw']]

        super().parent_bones()

    def create_widgets(self):

        top_main = self.get_ctrl_by_index(strip_org(self.mouth_bones['top'][0]), 0)
        corner_1 = self.get_ctrl_by_index(strip_org(self.mouth_bones['corners'][0]), 0)
        corner_2 = self.get_ctrl_by_index(strip_org(self.mouth_bones['corners'][1]), 0)
        bottom_main = self.get_ctrl_by_index(strip_org(self.mouth_bones['bottom'][0]), 0)

        create_cube_widget(self.obj, top_main)
        create_cube_widget(self.obj, corner_1)
        create_cube_widget(self.obj, corner_2)
        create_cube_widget(self.obj, bottom_main)

        jaw_ctrl = self.bones['jaw_ctrl']['jaw']
        create_jaw_widget(self.obj, jaw_ctrl)

        super().create_widgets()

    def generate(self):
        return super().generate()


def create_sample(obj):
    # generated by rigify.utils.write_metarig
    bpy.ops.object.mode_set(mode='EDIT')
    arm = obj.data

    bones = {}

    bone = arm.edit_bones.new('mouth')
    bone.head[:] = 0.0000, -0.0300, 0.0562
    bone.tail[:] = 0.0000, -0.0295, 0.0962
    bone.roll = 0.0000
    bone.use_connect = False
    bones['mouth'] = bone.name
    bone = arm.edit_bones.new('mouth.001')
    bone.head[:] = 0.0000, -0.0295, 0.0962
    bone.tail[:] = 0.0000, -0.0923, 0.0044
    bone.roll = 0.0000
    bone.use_connect = True
    bone.parent = arm.edit_bones[bones['mouth']]
    bones['mouth.001'] = bone.name
    bone = arm.edit_bones.new('lip.T')
    bone.head[:] = 0.0000, -0.1022, 0.0563
    bone.tail[:] = 0.0000, -0.1022, 0.0629
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['mouth']]
    bones['lip.T'] = bone.name
    bone = arm.edit_bones.new('lip.L')
    bone.head[:] = 0.0236, -0.0877, 0.0519
    bone.tail[:] = 0.0236, -0.0877, 0.0585
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['mouth']]
    bones['lip.L'] = bone.name
    bone = arm.edit_bones.new('lip.B')
    bone.head[:] = 0.0000, -0.0993, 0.0455
    bone.tail[:] = 0.0000, -0.0993, 0.0521
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['mouth']]
    bones['lip.B'] = bone.name
    bone = arm.edit_bones.new('lip.R')
    bone.head[:] = -0.0236, -0.0877, 0.0519
    bone.tail[:] = -0.0236, -0.0877, 0.0585
    bone.roll = 0.0000
    bone.use_connect = False
    bone.parent = arm.edit_bones[bones['mouth']]
    bones['lip.R'] = bone.name

    bpy.ops.object.mode_set(mode='OBJECT')
    pbone = obj.pose.bones[bones['mouth']]
    pbone.rigify_type = 'auto_jaw'
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['mouth.001']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.T']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.L']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.B']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'
    pbone = obj.pose.bones[bones['lip.R']]
    pbone.rigify_type = ''
    pbone.lock_location = (False, False, False)
    pbone.lock_rotation = (False, False, False)
    pbone.lock_rotation_w = False
    pbone.lock_scale = (False, False, False)
    pbone.rotation_mode = 'QUATERNION'

    bpy.ops.object.mode_set(mode='EDIT')
    for bone in arm.edit_bones:
        bone.select = False
        bone.select_head = False
        bone.select_tail = False
    for b in bones:
        bone = arm.edit_bones[bones[b]]
        bone.select = True
        bone.select_head = True
        bone.select_tail = True
        arm.edit_bones.active = bone


def add_parameters(params):
    """ Add the parameters of this rig type to the
        RigifyParameters PropertyGroup
    """
    items = [
        ('manual', 'Manual', ''),
        ('automatic', 'Automatic', '')
    ]

    params.rotation_mode = bpy.props.EnumProperty(
        items=items,
        name="Rotation Mode",
        description="Auto will align z-axis of jaw ctrl along the plane defined by the main and jaw bones",
        default='automatic'
    )

    ControlLayersGenerator.add_layer_parameters(params)


def parameters_ui(layout, params):
    """ Create the ui for the rig parameters."""

    r = layout.row()
    r.prop(params, "rotation_mode")

    ControlLayersGenerator.add_layers_ui(layout, params)
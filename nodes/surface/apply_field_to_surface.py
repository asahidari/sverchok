
import numpy as np

import bpy
from bpy.props import FloatProperty, EnumProperty, BoolProperty, IntProperty

from sverchok.node_tree import SverchCustomTreeNode, throttled
from sverchok.data_structure import updateNode, zip_long_repeat
from sverchok.utils.surface.algorithms import SvDeformedByFieldSurface, PROJECT, COPROJECT

class SvApplyFieldToSurfaceNode(bpy.types.Node, SverchCustomTreeNode):
        """
        Triggers: Apply field to surface
        Tooltip: Apply vector field to surface
        """
        bl_idname = 'SvExApplyFieldToSurfaceNode'
        bl_label = 'Apply Field to Surface'
        sv_icon = 'SV_SURFACE_VFIELD'

        coefficient : FloatProperty(
                name = "Coefficient",
                default = 1.0,
                update=updateNode)

        modes = [
            ('NONE', "As Is", "Do not consider surface normal", 0),
            (PROJECT, "Along normal", "Displace surface along it's normal", 1),
            (COPROJECT, "Along tangent", "Displace surface along it's tangent plane", 2)
        ]

        by_normal : EnumProperty(
                name = "By normal",
                items = modes,
                default = 'NONE',
                update = updateNode)

        def draw_buttons(self, context, layout):
            layout.prop(self, 'by_normal', text='')

        def sv_init(self, context):
            self.inputs.new('SvVectorFieldSocket', "Field")
            self.inputs.new('SvSurfaceSocket', "Surface")
            self.inputs.new('SvStringsSocket', "Coefficient").prop_name = 'coefficient'
            self.outputs.new('SvSurfaceSocket', "Surface")

        def process(self):
            if not any(socket.is_linked for socket in self.outputs):
                return

            surface_s = self.inputs['Surface'].sv_get()
            field_s = self.inputs['Field'].sv_get()
            coeff_s = self.inputs['Coefficient'].sv_get()

            surface_out = []
            for surface, field, coeff in zip_long_repeat(surface_s, field_s, coeff_s):
                if isinstance(coeff, (list, tuple)):
                    coeff = coeff[0]

                new_surface = SvDeformedByFieldSurface(surface, field, coeff, by_normal = self.by_normal)
                surface_out.append(new_surface)

            self.outputs['Surface'].sv_set(surface_out)

def register():
    bpy.utils.register_class(SvApplyFieldToSurfaceNode)

def unregister():
    bpy.utils.unregister_class(SvApplyFieldToSurfaceNode)


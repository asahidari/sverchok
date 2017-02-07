# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
from bpy.props import IntProperty, FloatProperty, BoolProperty, EnumProperty

from math import sin, cos, pi, sqrt, radians
from mathutils import *
from random import random
import time

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode, match_long_repeat, SvSetSocketAnyType


def torus_verts(R, r, N1, N2, rPhase, sPhase, Separate):
    '''
        R      : major radius
        r      : minor radius
        N1     : number of revolution sections (around the torus center)
        N2     : number of spin sections (around the torus tube)
        rPhase : revolution phase
        sPhase : spin phase
    '''
    listVerts = []
    listNorms = []

    # angle increments (cached outside of the loop for performance)
    da1 = 2*pi/N1
    da2 = 2*pi/N2

    for n1 in range(N1):
        a1 = n1 * da1
        theta = a1 + rPhase  # revolution angle
        sin_theta = sin(theta) # caching
        cos_theta = cos(theta) # caching

        loopVerts = []
        for n2 in range(N2):
            a2 = n2 * da2
            phi = a2 + sPhase  # spin angle
            sin_phi = sin(phi) # caching
            cos_phi = cos(phi) # caching

            x = (R + r*cos_phi) * cos_theta
            y = (R + r*cos_phi) * sin_theta
            z = r*sin_phi

            # append vertex to loop
            loopVerts.append([x, y, z])

            # append normal
            cx = R * cos_theta # torus tube center
            cy = R * sin_theta # torus tube center
            norm = [x-cx, y-cy, z]
            listNorms.append(norm)

        if Separate:
            listVerts.append(loopVerts)
        else:
            listVerts.extend(loopVerts)

    return listVerts, listNorms


def torus_edges(N1, N2):
    '''
        N1     : number of revolution sections (around the torus center)
        N2     : number of spin sections (around the torus tube)
    '''
    listEdges = []

    # spin loop EDGES : around the torus tube
    for n1 in range(N1):
        for n2 in range(N2-1):
            listEdges.append([N2*n1 + n2, N2*n1 + n2+1])
        listEdges.append([N2*n1 + N2-1, N2*n1 + 0])

    # revolution loop EDGES : around the torus center
    for n1 in range(N1-1):
        for n2 in range(N2):
            listEdges.append([N2*n1 + n2, N2*(n1+1) + n2])
    for n2 in range(N2):
        listEdges.append([N2*(N1-1) + n2, N2*0 + n2])

    return listEdges


def torus_polygons(N1, N2):
    '''
        N1     : number of revolution sections (around the torus center)
        N2     : number of spin sections (around the torus tube)
    '''
    listPolys = []
    for n1 in range(N1-1):
        for n2 in range(N2-1):
            listPolys.append([N2*n1 + n2, N2*n1 + n2+1, N2*(n1+1) + n2+1, N2*(n1+1) + n2])
        listPolys.append([N2*n1 + N2-1, N2*n1 + 0, N2*(n1+1) + 0, N2*(n1+1) + N2-1])
    for n2 in range(N2-1):
        listPolys.append([N2*(N1-1) + n2, N2*(N1-1) + n2+1, N2*0 + n2+1, N2*0 + n2])
    listPolys.append([N2*(N1-1) + N2-1, N2*(N1-1) + 0, N2*0 + 0, N2*0 + N2-1])

    return listPolys


class SvTorusNode(bpy.types.Node, SverchCustomTreeNode):
    ''' Torus '''
    bl_idname = 'SvTorusNode'
    bl_label = 'Torus'
    bl_icon = 'MESH_TORUS'

    def update_mode(self, context):
        # switch radii input sockets (R,r) <=> (eR,iR)
        if self.mode == 'EXT_INT':
            self.inputs['R'].prop_name = "torus_eR"
            self.inputs['r'].prop_name = "torus_iR"
        else:
            self.inputs['R'].prop_name = "torus_R"
            self.inputs['r'].prop_name = "torus_r"

        updateNode(self, context)

    # keep the equivalent radii pair in sync (eR,iR) => (R,r)
    def external_internal_radii_changed(self, context):
        if self.mode == "EXT_INT":
            self.torus_R = (self.torus_eR + self.torus_iR)*0.5
            self.torus_r = (self.torus_eR - self.torus_iR)*0.5
            updateNode(self, context)

    # keep the equivalent radii pair in sync (R,r) => (eR,iR)
    def major_minor_radii_changed(self, context):
        if self.mode == "MAJOR_MINOR":
            self.torus_eR = self.torus_R + self.torus_r
            self.torus_iR = self.torus_R - self.torus_r
            updateNode(self, context)

    # TORUS DIMENSIONS options
    mode = EnumProperty(
            name="Torus Dimensions",
            items=(("MAJOR_MINOR", "Major/Minor",
                    "Use the Major/Minor radii for torus dimensions."),
                    ("EXT_INT", "Exterior/Interior",
                    "Use the Exterior/Interior radii for torus dimensions.")),
            update=update_mode)

    torus_R = FloatProperty(
            name="Major Radius",
            min=0.00, max=100.0,
            default=1.0,
            subtype='DISTANCE',
            unit='LENGTH',
            description="Radius from the torus origin to the center of the cross section",
            update=major_minor_radii_changed)

    torus_r = FloatProperty(
            name="Minor Radius",
            min=0.00, max=100.0,
            default=.25,
            subtype='DISTANCE',
            unit='LENGTH',
            description="Radius of the torus' cross section",
            update=major_minor_radii_changed)

    torus_iR = FloatProperty(
            name="Interior Radius",
            min=0.00, max=100.0,
            default=.75,
            subtype='DISTANCE',
            unit='LENGTH',
            description="Interior radius of the torus (closest to the torus center)",
            update=external_internal_radii_changed)

    torus_eR = FloatProperty(
            name="Exterior Radius",
            min=0.00, max=100.0,
            default=1.25,
            subtype='DISTANCE',
            unit='LENGTH',
            description="Exterior radius of the torus (farthest from the torus center)",
            update=external_internal_radii_changed)

    # TORUS RESOLUTION options
    torus_n1 = IntProperty(
            name="Revolution Sections",
            default=32,
            min=3, soft_min=3,
            description="Number of sections around the torus center",
            update=updateNode)

    torus_n2 = IntProperty(
            name="Spin Sections",
            default=16,
            min=3, soft_min=3,
            description="Number of sections around the torus tube",
            update=updateNode)

    # TORUS Phase Options
    torus_rP = FloatProperty(
            name="Revolution Phase",
            default=0.0,
            min=0.0, soft_min=0.0,
            description="Phase the revolution sections by this radian amount",
            update=updateNode)

    torus_sP = FloatProperty(
            name="Spin Phase",
            default=0.0,
            min=0.0, soft_min=0.0,
            description="Phase the spin sections by this radian amount",
            update=updateNode)

    # OTHER options
    Separate = BoolProperty(
            name='Separate',
            description='Separate UV coords',
            default=False,
            update=updateNode)


    def sv_init(self, context):
        self.inputs.new('StringsSocket', "R").prop_name = 'torus_R'
        self.inputs.new('StringsSocket', "r").prop_name = 'torus_r'
        self.inputs.new('StringsSocket', "n1").prop_name = 'torus_n1'
        self.inputs.new('StringsSocket', "n2").prop_name = 'torus_n2'
        self.inputs.new('StringsSocket', "rP").prop_name = 'torus_rP'
        self.inputs.new('StringsSocket', "sP").prop_name = 'torus_sP'

        self.outputs.new('VerticesSocket', "Vertices")
        self.outputs.new('StringsSocket',  "Edges")
        self.outputs.new('StringsSocket',  "Polygons")
        self.outputs.new('VerticesSocket', "Normals")


    def draw_buttons_ext(self, context, layout):
        layout.column().label(text="Phasing")
        box = layout.box()
        box.prop(self, "torus_rP")
        box.prop(self, "torus_sP")


    def draw_buttons(self, context, layout):
        layout.prop(self, "Separate", text="Separate")
        layout.prop(self, 'mode', expand=True)


    def process(self):
        # no need to process if no outputs are connected
        if not self.outputs['Vertices'].is_linked and \
           not self.outputs['Edges'].is_linked and \
           not self.outputs['Polygons'].is_linked and \
           not self.outputs['Normals'].is_linked:
           return

        # input values
        RR = self.inputs["R"].sv_get()[0][0]
        rr = self.inputs["r"].sv_get()[0][0]
        n1 = self.inputs["n1"].sv_get()[0][0]
        n2 = self.inputs["n2"].sv_get()[0][0]
        rP = self.inputs["rP"].sv_get()[0][0]
        sP = self.inputs["sP"].sv_get()[0][0]

        # convert input radii values to MAJOR/MINOR, based on selected mode
        if self.mode == 'EXT_INT':
            # convert radii from EXTERIOR/INTERIOR to MAJOR/MINOR
            R = (RR + rr)*0.5
            r = (RR - rr)*0.5
        else: # values already given as MAJOR/MINOR radii
            R = RR
            r = rr

        if self.outputs['Vertices'].is_linked:
            verts, norms = torus_verts(R,r,n1,n2,rP,sP,self.Separate)
            SvSetSocketAnyType(self, 'Vertices', [verts])
            SvSetSocketAnyType(self, 'Normals', [norms])

        if self.outputs['Edges'].is_linked:
            edges = torus_edges(n1, n2)
            SvSetSocketAnyType(self, 'Edges', [edges])

        if self.outputs['Polygons'].is_linked:
            polys = torus_polygons(n1, n2)
            SvSetSocketAnyType(self, 'Polygons', [polys])


def register():
    bpy.utils.register_class(SvTorusNode)


def unregister():
    bpy.utils.unregister_class(SvFTorusNode)

if __name__ == '__main__':
    register()

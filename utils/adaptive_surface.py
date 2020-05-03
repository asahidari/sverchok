# This file is part of project Sverchok. It's copyrighted by the contributors
# recorded in the version control history of the file, available from
# its original location https://github.com/nortikin/sverchok/commit/master
#  
# SPDX-License-Identifier: GPL3
# License-Filename: LICENSE

import numpy as np
import numpy.random
from math import ceil, isnan

from sverchok.utils.logging import info, exception
from sverchok.utils.surface import SvSurface
from sverchok.utils.geom_2d.merge_mesh import crop_mesh_delaunay
from sverchok.utils.voronoi import computeDelaunayTriangulation, Site

GAUSS = 'gauss'
MAXIMUM = 'max'
MEAN = 'mean'

class PopulationData(object):
    def __init__(self):
        self.surface = None
        self.u_min = self.u_max = None
        self.v_min = self.v_max = None
        self.new_us = self.new_vs = None
        self._points = None
        self.samples_u = self.samples_v = None

    @property
    def points(self):
        if self._points is None:
            self._points = self.surface.evaluate_array(self.us, self.vs).reshape((self.samples_u, self.samples_v, 3))
        return self._points

def populate_surface_uv(surface, samples_u, samples_v, by_curvature=True, curvature_type = MAXIMUM, by_area=True, min_ppf=1, max_ppf=5, seed=1):
    u_min, u_max = surface.get_u_min(), surface.get_u_max()
    v_min, v_max = surface.get_v_min(), surface.get_v_max()
    us_range = np.linspace(u_min, u_max, num=samples_u)
    vs_range = np.linspace(v_min, v_max, num=samples_v)
    us, vs = np.meshgrid(us_range, vs_range, indexing='ij')
    us = us.flatten()
    vs = vs.flatten()

    data = PopulationData()
    data.surface = surface
    data.us = us
    data.vs = vs
    data.u_min = u_min
    data.v_min = v_min
    data.u_max = u_max
    data.v_max = v_max
    data.samples_u = samples_u
    data.samples_v = samples_v

    if by_curvature:
        if curvature_type == GAUSS:
            curvatures = abs(surface.gauss_curvature_array(us, vs)).clip(0, 100)
        elif curvature_type == MAXIMUM:
            curvatures = abs(surface.principal_curvature_values_array(us, vs)[1])
        elif curvature_type == MEAN:
            curvatures = abs(surface.mean_curvature_array(us, vs))
        else:
            raise Exception("Unsupported curvature type:" + curvature_type)
        curvatures = curvatures.reshape((samples_u, samples_v))

        curvatures_0 = curvatures[:-1, :-1]
        curvatures_du = curvatures[1:, :-1]
        curvatures_dv = curvatures[:-1, 1:]
        curvatures_du_dv = curvatures[1:, 1:]

        max_curvatures = np.max([curvatures_0, curvatures_du, curvatures_dv, curvatures_du_dv], axis=0)
        max_curvature = max_curvatures.max()
        min_curvature = max_curvatures.min()
        curvatures_range = max_curvature - min_curvature
        info("Curvature range: %s - %s", min_curvature, max_curvature)
        if curvatures_range == 0:
            max_curvatures = np.zeros((samples_u-1, samples_v-1))
        else:
            max_curvatures = (max_curvatures - min_curvature) / curvatures_range
    else:
        max_curvatures = np.zeros((samples_u-1, samples_v-1))
        curvatures_range = 0

    if by_area:
        surface_points = surface.evaluate_array(us, vs)
        surface_points = surface_points.reshape((samples_u, samples_v, 3))
        data._points = surface_points

        points_0 = surface_points[:-1, :-1,:]
        points_du = surface_points[1:, :-1,:]
        points_dv = surface_points[:-1, 1:,:]
        points_du_dv = surface_points[1:, 1:,:]

        areas_1 = np.linalg.norm(np.cross(points_du_dv - points_0, points_du - points_0), axis=2)/6.0
        areas_2 = np.linalg.norm(np.cross(points_dv - points_0, points_du_dv - points_0), axis=2)/6.0
        areas = areas_1 + areas_2
        h_u = us_range[1] - us_range[0]
        h_v = vs_range[1] - vs_range[0]
        areas = areas / (h_u * h_v)
        min_area = areas.min()
        max_area = areas.max()
        areas_range = max_area - min_area
        info("Areas range: %s - %s", min_area, max_area)
        if areas_range == 0:
            areas = np.zeros((samples_u-1, samples_v-1))
        else:
            areas = (areas - min_area) / areas_range
    else:
        areas = np.zeros((samples_u-1, samples_v-1))
        areas_range = 0

    factors = max_curvatures + areas
    factor_range = areas_range + curvatures_range
    if by_area and by_curvature:
        factors = factors / 2.0
        factor_range = factor_range / 2.0
    max_factor = factors.max()
    if max_factor != 0:
        factors = factors / max_factor
    #info("Factors: %s - %s (%s)", factors.min(), factors.max(), factor_range)
    #info("Areas: %s - %s", areas.min(), areas.max())
    #info("Curvatures: %s - %s", max_curvatures.min(), max_curvatures.max())

    ppf_range = max_ppf - min_ppf

    if not seed:
        seed = 12345
    numpy.random.seed(seed)
    new_u = []
    new_v = []
    for i in range(samples_u-1):
        u1 = us_range[i]
        u2 = us_range[i+1]
        for j in range(samples_v-1):
            v1 = vs_range[j]
            v2 = vs_range[j+1]
            factor = factors[i,j]
            if factor_range == 0 or isnan(factor):
                ppf = (min_ppf + max_ppf)/2
            else:
                ppf = min_ppf + ppf_range * factor
            #ppf = int(round(ppf))
            ppf = ceil(ppf)
#             if ppf > 1:
#                 info("I %s, J %s, factor %s, PPF %s", i, j, factor, ppf)
#                 info("U %s - %s, V %s - %s", u1, u2, v1, v2)
            u_r = numpy.random.uniform(u1, u2, size=ppf).tolist()
            v_r = numpy.random.uniform(v1, v2, size=ppf).tolist()
            new_u.extend(u_r)
            new_v.extend(v_r)

    data.new_us = new_u
    data.new_vs = new_v
    return data

def adaptive_subdivide(surface, samples_u, samples_v, by_curvature=True, curvature_type = MAXIMUM, by_area=True, add_points=None, min_ppf=1, max_ppf=5, seed=1):
    data = populate_surface_uv(surface, samples_u, samples_v,
                            by_curvature = by_curvature,
                            curvature_type = curvature_type,
                            by_area = by_area,
                            min_ppf = min_ppf, max_ppf = max_ppf, seed =seed)
    us, vs, new_u, new_v = data.us, data.vs, data.new_us, data.new_vs
    us_list = list(us) + new_u
    vs_list = list(vs) + new_v
    if add_points and len(add_points[0]) > 0:
        us_list.extend([p[0] for p in add_points])
        vs_list.extend([p[1] for p in add_points])

    surface_points = data.points
    # Calculate lengths of:
    #   1) target_v_length = length of f(0, v) for v in v_range,
    #   2) target_v_length = length of f(u, 0) for u in u_range.
    # Obviously length of f(u1, v) for v in v_range for some other u1
    # can be very different from target_v_length; and the same goes for
    # target_u_length.
    # TODO: we could check all U/V iso-parametric lines length and select maximums.
    dvs = surface_points[0,1:] - surface_points[0,:-1]
    v_lengths = np.linalg.norm(dvs, axis=1)
    target_v_length = np.sum(v_lengths)
    dus = surface_points[1:,0] - surface_points[:-1,0]
    u_lengths = np.linalg.norm(dus, axis=1)
    target_u_length = np.sum(u_lengths)

    src_u_length = data.u_max - data.u_min
    src_v_length = data.v_max - data.v_min

    u_coeff = target_u_length / src_u_length
    v_coeff = target_v_length / src_v_length
    print(u_coeff, v_coeff)

    points_uv = [Site(u * u_coeff, v * v_coeff) for u, v in zip(us_list, vs_list)]
    faces = computeDelaunayTriangulation(points_uv)
    return np.array(us_list), np.array(vs_list), faces

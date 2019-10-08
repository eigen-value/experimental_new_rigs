from mathutils import Matrix, Vector
from math import pi, sin, cos
from rigify.rigs.widgets import create_widget


def create_widget_from_cluster(rig, bone_name, cluster, size=1.0, bone_transform_name=None):
    """

    :param rig:
    :param bone_name:
    :param cluster: point cloud
    :type cluster: list(Vector)
    :param size:
    :param direction:
    :param bone_transform_name:
    :return:
    """
    obj = create_widget(rig, bone_name, bone_transform_name)

    if obj is not None:
        ctrl_x = rig.pose.bones[bone_name].x_axis
        ctrl_y = rig.pose.bones[bone_name].y_axis

        cluster = get_cluster_projection(cluster, ctrl_x, ctrl_y)

        size = 1/rig.pose.bones[bone_name].length

        [verts, edges] = get_2d_border(cluster, size=size)

        mesh = obj.data
        mesh.from_pydata(verts, edges, [])
        mesh.validate()
        mesh.update()
        return obj
    else:
        return None


def get_cluster_projection(cluster, x_axis, y_axis):

    new_cluster = []
    cluster_sum = Vector((0, 0, 0))

    for point in cluster:
        cluster_sum += point

    cluster_center = cluster_sum / len(cluster)

    for point in cluster:
        _point = point - cluster_center
        new_point = Vector((_point.dot(x_axis), _point.dot(y_axis), 0))
        new_cluster.append(new_point)

    return new_cluster


def get_cluster_span(cluster):

    x_span = 0
    y_span = 0
    z_span = 0

    for point in cluster:
        x_span = max(x_span, abs(point.x))
        y_span = max(y_span, abs(point.y))
        z_span = max(z_span, abs(point.z))

    return [x_span, y_span, z_span]


def get_2d_border(cluster, max_points=None, size=1.0, double=True):

    if not max_points:
        max_points = 2 * len(cluster)

    angle_step = 2 * pi / max_points

    x_axis = Vector((1, 0))

    points = [(-1, 0)] * max_points

    for i, point in enumerate(cluster):
        angle = point.to_2d().angle_signed(x_axis)
        angle = angle if angle >= 0 else 2 * pi + angle
        index = int(round(angle / angle_step, 2)) % len(points)
        if point.magnitude > points[index][1]:
            points[index] = (i, point.magnitude)

    points = [p for p in points if p[0] >= 0]

    verts = []
    edges = []

    if len(points) == 1:
        return verts, edges

    if len(points) == 2:
        i0 = points[0][0]
        i1 = points[1][0]
        # displ = (cluster[i1] - cluster[i0]).magnitude * 0.05
        displ = 0.1 / size
        angle = cluster[i0].to_2d().angle(x_axis)
        displ_vect = displ * Vector((sin(angle), -cos(angle), 0))

        verts = [cluster[i0] + displ_vect, cluster[i1] + displ_vect, cluster[i0]
                 - displ_vect, cluster[i1] - displ_vect]
        verts = [size * v for v in verts]
        edges = [(0, 1), (2, 3)]
        return verts, edges

    j = 0
    for p in points:
        if p[0] >= 0:
            vert = size * cluster[p[0]]
            verts.append(vert.to_tuple())
            edges.append(((j + 1) % len(points), j))
            j += 1

    if double:
        for p in points:
            if p[0] >= 0:
                vert = size * 1.1 * cluster[p[0]]
                verts.append(vert.to_tuple())
                edges.append(((j + 1) % len(points) + len(points), j))
                j += 1

    return verts, edges


def adjust_widget(mesh, axis='y', offset=0.0):

    if axis[0] == '-':
        s = -1
        axis = axis[1]
    else:
        s = 1

    trans_matrix = Matrix.Translation((0.0, offset, 0.0))
    rot_matrix = Matrix(((1.0, 0.0, 0.0, 0.0),
            (0.0, s*1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0)))

    if axis == "x":
        rot_matrix = Matrix.Rotation(-s*pi/2, 4, 'Z')
        trans_matrix = Matrix.Translation((offset, 0.0, 0.0))

    elif axis == "z":
        rot_matrix = Matrix.Rotation(s*pi/2, 4, 'X')
        trans_matrix = Matrix.Translation((0.0, 0.0, offset))

    for vert in mesh.vertices:
        vert.co = (trans_matrix @ rot_matrix @ vert.co.to_4d()).to_3d()


def create_chain_widget(rig, bone_name, cube=False, radius=0.5, invert=False, bone_transform_name=None, axis="y", offset=0.0):
    """Creates a basic chain widget
    """
    obj = create_widget(rig, bone_name, bone_transform_name)
    if obj is not None:
        r = radius
        if cube:
            rh = r
        else:
            rh = radius/2
        if invert:
            verts = [(rh, rh, rh), (r, -r, r), (-r, -r, r), (-rh, rh, rh), (rh, rh, -rh), (r, -r, -r), (-r, -r, -r), (-rh, rh, -rh)]
        else:
            verts = [(r, r, r), (rh, -rh, rh), (-rh, -rh, rh), (-r, r, r), (r, r, -r), (rh, -rh, -rh), (-rh, -rh, -rh), (-r, r, -r)]
        edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
        mesh = obj.data
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        adjust_widget(mesh, axis=axis, offset=offset)
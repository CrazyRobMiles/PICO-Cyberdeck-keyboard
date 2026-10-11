"""
A simple two layer autorouter for the keyboard PCB.

build_pcb.py uses this to add the tracks after it has placed the parts. It
is a grid router: the board is divided into a grid of cells (0.5mm by
default) on the front and back copper layers, and each connection is found
with an A* search through the cells, changing layers with vias.

Every cell that is too close to a pad of another net is blocked for that net,
using KiCad's own pad shapes, so the tracks keep the clearance from the
routing settings. On a 0.5mm grid, 0.25mm tracks in neighbouring cells are
0.25mm apart, so tracks never need checking against each other. Vias are
bigger, so a via also claims the cells on each side of it.

Tracks are cheaper horizontally on the front and vertically on the back. For
a key matrix this puts the rows on the front, in the gaps between the rows of
switches, and the columns on the back.

Nets are routed one connection at a time, joining each pad to the nearest
part of its net that is already routed. If some connections can't be made,
the whole board is routed again with the failed nets first, a few times.
"""

import heapq
import math

import pcbnew

FRONT, BACK = 0, 1
BLOCKED = 0xFFFF


def mm(v):
    return pcbnew.FromMM(v)


class Router:

    def __init__(self, board, rect, settings, keepouts=()):
        """rect is the board outline (x, y, w, h) in mm, page coordinates.
        keepouts is a list of (x0, y0, x1, y1, layers) rectangles in mm where
        no tracks or vias may go on those layers (0 front, 1 back)."""
        self.board = board
        self.s = settings
        self.pitch = settings["grid"]
        self.x0 = rect[0]
        self.y0 = rect[1]
        self.rect = rect
        self.nx = int(rect[2] / self.pitch) + 1
        self.ny = int(rect[3] / self.pitch) + 1
        self.layer_size = self.nx * self.ny
        self.keepouts = keepouts
        self.track_half = settings["track_width"] / 2
        self.via_radius = settings["via_diameter"] / 2

    # ----- grid helpers -----

    def node(self, layer, ix, iy):
        return layer * self.layer_size + iy * self.nx + ix

    def unpack(self, n):
        layer, rest = divmod(n, self.layer_size)
        iy, ix = divmod(rest, self.nx)
        return layer, ix, iy

    def cell_mm(self, ix, iy):
        return self.x0 + ix * self.pitch, self.y0 + iy * self.pitch

    def point(self, ix, iy):
        x, y = self.cell_mm(ix, iy)
        return pcbnew.VECTOR2I(mm(x), mm(y))

    # ----- obstacles -----

    def build_obstacles(self):
        """owner[layer cell] is 0 if any net may use the cell, a net code if
        only that net may, or BLOCKED. via_owner is the same for via centres,
        which need more room."""
        n = 2 * self.layer_size
        self.owner = [0] * n
        self.via_owner = [0] * n
        self.vias = {}          # node (front layer) -> net code
        self.used = {}          # node -> net code, for cells holding tracks
        clearance = self.s["clearance"]
        edge = self.s["edge_clearance"]

        def claim(array, node, net):
            current = array[node]
            if current == 0:
                array[node] = net
            elif current != net:
                array[node] = BLOCKED

        # board edge (allowing for rounded corners)
        x, y, w, h = self.rect
        r = self.s["corner_radius"]
        for iy in range(self.ny):
            for ix in range(self.nx):
                px, py = self.cell_mm(ix, iy)
                inset_track = edge + self.track_half
                inset_via = edge + self.via_radius
                for inset, array in ((inset_track, self.owner), (inset_via, self.via_owner)):
                    if not self.inside_outline(px, py, x, y, w, h, r, inset):
                        array[self.node(FRONT, ix, iy)] = BLOCKED
                        array[self.node(BACK, ix, iy)] = BLOCKED
        for kx0, ky0, kx1, ky1, layers in self.keepouts:
            for iy in range(max(0, int((ky0 - self.y0) / self.pitch)), min(self.ny, int((ky1 - self.y0) / self.pitch) + 2)):
                for ix in range(max(0, int((kx0 - self.x0) / self.pitch)), min(self.nx, int((kx1 - self.x0) / self.pitch) + 2)):
                    px, py = self.cell_mm(ix, iy)
                    if kx0 <= px <= kx1 and ky0 <= py <= ky1:
                        for layer in layers:
                            self.owner[self.node(layer, ix, iy)] = BLOCKED
                        # vias go through both layers
                        self.via_owner[self.node(FRONT, ix, iy)] = BLOCKED
                        self.via_owner[self.node(BACK, ix, iy)] = BLOCKED

        # pads
        self.terminals = {}     # net code -> list of sets of nodes (one set per pad)
        track_gap = mm(clearance + self.track_half)
        via_gap = mm(clearance + self.via_radius)
        reach = clearance + self.via_radius + self.pitch
        for pad in self.board.GetPads():
            net = pad.GetNetCode() or BLOCKED
            layers = [l for l, cu in ((FRONT, pcbnew.F_Cu), (BACK, pcbnew.B_Cu)) if pad.IsOnLayer(cu)]
            if not layers:
                continue
            box = pad.GetBoundingBox()
            bx0 = pcbnew.ToMM(box.GetX()) - reach
            by0 = pcbnew.ToMM(box.GetY()) - reach
            bx1 = pcbnew.ToMM(box.GetRight()) + reach
            by1 = pcbnew.ToMM(box.GetBottom()) + reach
            cells = set()
            for iy in range(max(0, int((by0 - self.y0) / self.pitch)), min(self.ny, int((by1 - self.y0) / self.pitch) + 1)):
                for ix in range(max(0, int((bx0 - self.x0) / self.pitch)), min(self.nx, int((bx1 - self.x0) / self.pitch) + 1)):
                    p = self.point(ix, iy)
                    if not pad.HitTest(p, via_gap):
                        continue
                    near_track = pad.HitTest(p, track_gap)
                    inside = pad.HitTest(p, 0)
                    for layer in layers:
                        node = self.node(layer, ix, iy)
                        claim(self.via_owner, node, net)
                        if near_track:
                            claim(self.owner, node, net)
                        if inside and net != BLOCKED:
                            cells.add(node)
                    # A through hole blocks vias on both layers
                    if len(layers) == 1 and pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                        claim(self.via_owner, self.node(1 - layers[0], ix, iy), net)
            if net != BLOCKED:
                self.terminals.setdefault(net, []).append((cells, pad))

    @staticmethod
    def inside_outline(px, py, x, y, w, h, r, inset):
        if not (x + inset <= px <= x + w - inset and y + inset <= py <= y + h - inset):
            return False
        # in a corner, keep inside the rounded edge
        cx = min(max(px, x + r), x + w - r)
        cy = min(max(py, y + r), y + h - r)
        if cx == px or cy == py:
            return True
        return math.hypot(px - cx, py - cy) <= r - inset

    # ----- searching -----

    def can_use(self, node, net):
        o = self.owner[node]
        return o == 0 or o == net

    def can_via(self, node, net):
        layer, ix, iy = self.unpack(node)
        for l in (FRONT, BACK):
            n = self.node(l, ix, iy)
            vo = self.via_owner[n]
            if vo != 0 and vo != net:
                return False
            if not self.can_use(n, net):
                return False
            # a track of another net in the next cell would be too close
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                jx, jy = ix + dx, iy + dy
                if 0 <= jx < self.nx and 0 <= jy < self.ny:
                    u = self.used.get(self.node(l, jx, jy))
                    if u is not None and u != net:
                        return False
        # other vias must be at least two cells away
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                v = self.vias.get(self.node(FRONT, ix + dx, iy + dy)) if 0 <= ix + dx < self.nx and 0 <= iy + dy < self.ny else None
                if v is not None and v != net:
                    return False
        return True

    def search(self, net, sources, targets):
        """A* from any source node to any target node. Returns the path as a
        list of nodes, source first, or None."""
        tx = [self.unpack(t)[1] for t in targets]
        ty = [self.unpack(t)[2] for t in targets]
        tx0, tx1, ty0, ty1 = min(tx), max(tx), min(ty), max(ty)
        wrong_way = self.s["wrong_way_cost"]
        via_cost = self.s["via_cost"]
        nx, ny, ls = self.nx, self.ny, self.layer_size

        def h(ix, iy):
            dx = tx0 - ix if ix < tx0 else (ix - tx1 if ix > tx1 else 0)
            dy = ty0 - iy if iy < ty0 else (iy - ty1 if iy > ty1 else 0)
            return dx + dy

        g = {}
        came = {}
        heap = []
        for s in sources:
            _, ix, iy = self.unpack(s)
            g[s] = 0
            came[s] = None
            heapq.heappush(heap, (h(ix, iy), 0, s))
        owner = self.owner
        while heap:
            f, cost, n = heapq.heappop(heap)
            if cost > g.get(n, 1e18):
                continue
            if n in targets:
                path = []
                while n is not None:
                    path.append(n)
                    n = came[n]
                return path[::-1]
            layer, rest = divmod(n, ls)
            iy, ix = divmod(rest, nx)
            moves = []
            # front prefers horizontal tracks, back prefers vertical
            hcost = 1 if layer == FRONT else wrong_way
            vcost = wrong_way if layer == FRONT else 1
            if ix > 0:
                moves.append((n - 1, hcost, ix - 1, iy))
            if ix < nx - 1:
                moves.append((n + 1, hcost, ix + 1, iy))
            if iy > 0:
                moves.append((n - nx, vcost, ix, iy - 1))
            if iy < ny - 1:
                moves.append((n + nx, vcost, ix, iy + 1))
            for m, step, mx, my in moves:
                o = owner[m]
                if o != 0 and o != net:
                    continue
                c = cost + step
                if c < g.get(m, 1e18):
                    g[m] = c
                    came[m] = n
                    heapq.heappush(heap, (c + h(mx, my), c, m))
            other = n + ls if layer == FRONT else n - ls
            c = cost + via_cost
            if c < g.get(other, 1e18) and self.can_via(n, net):
                g[other] = c
                came[other] = n
                heapq.heappush(heap, (c + h(ix, iy), c, other))
        return None

    def commit(self, net, path):
        """Mark a found path as used by the net, including room for its vias."""
        for a, b in zip(path, path[1:]):
            la, ix, iy = self.unpack(a)
            lb = self.unpack(b)[0]
            if la != lb:
                self.vias[self.node(FRONT, ix, iy)] = net
                for l in (FRONT, BACK):
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        jx, jy = ix + dx, iy + dy
                        if 0 <= jx < self.nx and 0 <= jy < self.ny and self.owner[self.node(l, jx, jy)] == 0:
                            self.owner[self.node(l, jx, jy)] = net
        for n in path:
            if self.owner[n] == 0:
                self.owner[n] = net
            self.used[n] = net

    def route_net(self, net):
        """Connect all the pads of a net. Returns (paths, number of failed pads)."""
        pads = [t for t in self.terminals.get(net, []) if t[0]]
        missing = len(self.terminals.get(net, [])) - len(pads)
        if len(pads) < 2:
            return [], missing
        centres = [(p.GetPosition().x, p.GetPosition().y) for _, p in pads]
        tree = set(pads[0][0])
        connected = [0]
        remaining = list(range(1, len(pads)))
        paths = []
        failed = missing
        while remaining:
            # the unconnected pad nearest to a connected one
            best = min(remaining, key=lambda i: min(math.hypot(centres[i][0] - centres[j][0],
                                                               centres[i][1] - centres[j][1]) for j in connected))
            remaining.remove(best)
            path = self.search(net, tree, pads[best][0])
            if path is None:
                failed += 1
                continue
            self.commit(net, path)
            paths.append(path)
            tree.update(path)
            tree.update(pads[best][0])
            connected.append(best)
        return paths, failed

    # ----- the whole board -----

    def route(self, net_order, passes=6):
        """Route the nets, trying again with the failures first if needed.
        Returns the number of pads that could not be connected."""
        order = list(net_order)
        best = None
        for attempt in range(passes):
            self.build_obstacles()
            results = {}
            failures = {}
            for net in order:
                paths, failed = self.route_net(net)
                results[net] = paths
                if failed:
                    failures[net] = failed
            total = sum(failures.values())
            print("Routing pass %d: %d connections failed" % (attempt + 1, total))
            if best is None or total < best[0]:
                best = (total, results, dict(self.vias))
            if total == 0:
                break
            order = [n for n in order if n in failures] + [n for n in order if n not in failures]
        total, results, vias = best
        self.add_copper(results)
        return total

    def add_copper(self, results):
        width = mm(self.s["track_width"])
        layers = {FRONT: pcbnew.F_Cu, BACK: pcbnew.B_Cu}
        for net, paths in results.items():
            netinfo = self.board.FindNet(net)
            # every path end is a junction, so tracks are split there
            joints = set()
            for path in paths:
                joints.add(path[0] % self.layer_size)
                joints.add(path[-1] % self.layer_size)
            for path in paths:
                for run in self.split_runs(path, joints):
                    layer = self.unpack(run[0])[0]
                    for a, b in zip(run, run[1:]):
                        t = pcbnew.PCB_TRACK(self.board)
                        t.SetStart(self.point(*self.unpack(a)[1:]))
                        t.SetEnd(self.point(*self.unpack(b)[1:]))
                        t.SetWidth(width)
                        t.SetLayer(layers[layer])
                        t.SetNet(netinfo)
                        self.board.Add(t)
                for a, b in zip(path, path[1:]):
                    if self.unpack(a)[0] != self.unpack(b)[0]:
                        v = pcbnew.PCB_VIA(self.board)
                        v.SetViaType(pcbnew.VIATYPE_THROUGH)
                        v.SetPosition(self.point(*self.unpack(a)[1:]))
                        v.SetWidth(mm(self.s["via_diameter"]))
                        v.SetDrill(mm(self.s["via_drill"]))
                        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                        v.SetNet(netinfo)
                        self.board.Add(v)

    def split_runs(self, path, joints):
        """Turn a path into lists of corner points, one list per layer run.
        Straight stretches become a single track, broken at corners and at
        joints where other tracks of the net meet."""
        runs = []
        current = [path[0]]
        for prev, n in zip(path, path[1:]):
            if self.unpack(prev)[0] != self.unpack(n)[0]:
                runs.append(current)
                current = [n]
                continue
            current.append(n)
        runs.append(current)
        out = []
        for run in runs:
            if len(run) < 2:
                continue
            pts = [run[0]]
            for i in range(1, len(run) - 1):
                a, b, c = self.unpack(run[i - 1]), self.unpack(run[i]), self.unpack(run[i + 1])
                straight = (b[1] - a[1], b[2] - a[2]) == (c[1] - b[1], c[2] - b[2])
                if not straight or run[i] % self.layer_size in joints:
                    pts.append(run[i])
            pts.append(run[-1])
            out.append(pts)
        return out

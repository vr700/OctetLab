import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ipaddress
import random
import os

# --------------------------
# Tabla de prefijos y hosts
# clave: prefijo, valor: hosts útiles
# --------------------------
PREFIX_HOSTS = {
    32: 1, 31: 2, 30: 2, 29: 6, 28: 14, 27: 30, 26: 62, 25: 126, 24: 254,
    23: 510, 22: 1022, 21: 2046, 20: 4094, 19: 8190, 18: 16382, 17: 32766,
    16: 65534, 15: 131070, 14: 262142, 13: 524286, 12: 1048574, 11: 2097150,
    10: 4194302
}


def smallest_prefix_for_hosts(requested_hosts: int, forbid_31=True):
    if requested_hosts <= 0:
        raise ValueError("Hosts must be > 0")
    for p in range(32, 9, -1):
        if forbid_31 and p == 31:
            continue
        if PREFIX_HOSTS.get(p, 0) >= requested_hosts:
            return p
    raise ValueError("Requested hosts too large for available prefixes.")


def roundup_to_network(addr_int: int, prefix: int):
    block = 1 << (32 - prefix)
    net_addr = (addr_int // block) * block
    if net_addr < addr_int:
        net_addr += block
    return net_addr


def mask_to_binary(netmask_str: str) -> str:
    parts = netmask_str.split('.')
    return '.'.join(f"{int(p):08b}" for p in parts)

# --------------------------
# Estructuras de datos
# --------------------------
class Router:
    def __init__(self, name: str):
        self.name = name
        self.groups = []
        self.pos = (random.randint(50, 400), random.randint(50, 400))
        self.color = random.choice(["lightblue", "lightgreen", "lightyellow", "orange", "pink", "violet"])

    def __repr__(self):
        return f"Router({self.name}, groups={self.groups})"


class Connection:
    def __init__(self, a: str, b: str):
        self.a = a
        self.b = b

    def __repr__(self):
        return f"Conn({self.a}-{self.b})"

# --------------------------
# Lógica de asignación
# --------------------------
class Allocator:
    def __init__(self, routers: dict, connections: list, mode: str, base_network: str = "192.168.0.0/16"):
        self.routers = routers
        self.connections = connections
        self.mode = mode
        self.base_network = ipaddress.ip_network(base_network, strict=False)
        self.current_addr_int = int(self.base_network.network_address)
        self.allocations = []

    def allocate(self):
        self.allocations.clear()
        demands = []
        for rname, router in self.routers.items():
            for i, h in enumerate(router.groups):
                if h and h > 0:
                    demands.append((f"{rname}-G{i+1}", int(h), False))
        for idx, c in enumerate(self.connections, start=1):
            name = f"{c.a}-{c.b}-link{idx}"
            demands.append((name, 2, True))

        flsm_prefix = None
        if self.mode == "FLSM":
            group_hosts = [h for _, h, is_conn in demands if not is_conn]
            if group_hosts:
                flsm_prefix = smallest_prefix_for_hosts(max(group_hosts))

        jobs = []
        for name, req_h, is_conn in demands:
            if is_conn:
                prefix = 30
            else:
                if self.mode == "FLSM" and flsm_prefix is not None:
                    prefix = flsm_prefix
                else:
                    prefix = smallest_prefix_for_hosts(req_h)
            jobs.append((name, req_h, is_conn, prefix))
        jobs.sort(key=lambda x: x[3])

        for name, req_h, is_conn, prefix in jobs:
            net_addr_int = roundup_to_network(self.current_addr_int, prefix)
            net = ipaddress.ip_network((ipaddress.IPv4Address(net_addr_int), prefix), strict=False)
            if not (net.network_address >= self.base_network.network_address and
                    (int(net.broadcast_address) <= int(self.base_network.broadcast_address))):
                raise RuntimeError(f"No hay espacio dentro de la red base {self.base_network} para asignar {name} ({prefix})")
            self.allocations.append((name, net))
            self.current_addr_int = int(net.network_address) + net.num_addresses

        return self.allocations

# --------------------------
# GUI
# --------------------------
class SubnetPlannerApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.pack(fill="both", expand=True)
        self.routers = {}
        self.connections = []
        self.alloc_map = {}
        self.drag_data = {"item": None, "x": 0, "y": 0}
        self.pan_data = {"x": 0, "y": 0, "active": False}
        self._build_ui()

    def _build_ui(self):
        self.master.title("Subnet Planner - PacketTracer Export")
        top = ttk.Frame(self)
        top.pack(side="top", fill="x", padx=6, pady=6)

        left = ttk.LabelFrame(top, text="Crear Router")
        left.pack(side="left", fill="y", padx=6, pady=6)
        ttk.Label(left, text="Nombre router:").grid(row=0, column=0, sticky="w")
        self.ent_router_name = ttk.Entry(left, width=16)
        self.ent_router_name.grid(row=0, column=1, sticky="w")
        self.group_entries = []
        for i in range(4):
            ttk.Label(left, text=f"Grupo {i+1} hosts:").grid(row=1 + i, column=0, sticky="w")
            e = ttk.Entry(left, width=8)
            e.grid(row=1 + i, column=1, sticky="w")
            self.group_entries.append(e)
        ttk.Button(left, text="Agregar Router", command=self.add_router).grid(row=5, column=0, columnspan=2, pady=4)

        mid = ttk.LabelFrame(top, text="Routers / Conexiones")
        mid.pack(side="left", fill="y", padx=6, pady=6)
        self.router_listbox = tk.Listbox(mid, height=8, exportselection=False, selectmode='extended')
        self.router_listbox.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        ttk.Button(mid, text="Eliminar Router Seleccionado(s)", command=self.delete_router).grid(row=1, column=0, columnspan=2, pady=2)
        ttk.Label(mid, text="Conectar (seleccionar 2):").grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Button(mid, text="Conectar Seleccionados", command=self.connect_selected).grid(row=3, column=0, columnspan=2, pady=2)
        ttk.Button(mid, text="Eliminar Conexión Seleccionada", command=self.delete_connection).grid(row=4, column=0, columnspan=2, pady=2)
        self.conn_listbox = tk.Listbox(mid, height=6, exportselection=False)
        self.conn_listbox.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)

        right = ttk.LabelFrame(top, text="Opciones & Ejecutar")
        right.pack(side="left", fill="both", padx=6, pady=6)
        self.mode_var = tk.StringVar(value="VLSM")
        ttk.Radiobutton(right, text="VLSM (máscaras por grupo)", variable=self.mode_var, value="VLSM").pack(anchor="w")
        ttk.Radiobutton(right, text="FLSM (una máscara para todos los grupos)", variable=self.mode_var, value="FLSM").pack(anchor="w")
        ttk.Label(right, text="Base network (ej: 192.168.0.0/16):").pack(anchor="w", pady=(8, 0))
        self.base_net_entry = ttk.Entry(right, width=18)
        self.base_net_entry.insert(0, "192.168.0.0/16")
        self.base_net_entry.pack(anchor="w", pady=(0, 4))
        ttk.Label(right, text="DNS (opcional):").pack(anchor="w")
        self.dns_entry = ttk.Entry(right, width=18)
        self.dns_entry.insert(0, "")
        self.dns_entry.pack(anchor="w", pady=(0, 4))
        self.include_dns_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(right, text="Incluir DNS en los routers", variable=self.include_dns_var).pack(anchor="w")
        ttk.Button(right, text="Generar Resultados", command=self.generate).pack(fill="x", pady=(2,2))
        #ttk.Button(right, text="Cargar Ejemplo de Prueba", command=self.load_example).pack(fill="x")
        ttk.Button(right, text="Exportar Cisco Topology (text)", command=self.export_cisco_topology).pack(fill="x", pady=(2,2))
        ttk.Button(right, text="Exportar Cisco CLI (configs .txt)", command=self.export_cisco_cli).pack(fill="x", pady=(2,2))
        ttk.Button(right, text="Exportar a TXT", command=self.export_to_txt).pack(fill="x", pady=(2,2))
        ttk.Button(right, text="Generar RIP para Routers", command=self.generate_rip_config).pack(fill="x", pady=(2,2))

        out = ttk.Frame(self)
        out.pack(side="top", fill="both", expand=True, padx=6, pady=6)
        t1_frame = ttk.LabelFrame(out, text="TABLA 1: Resumen de Redes")
        t1_frame.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        columns1 = ("name", "prefix", "first", "last", "broadcast")
        self.tree1 = ttk.Treeview(t1_frame, columns=columns1, show="headings", height=12)
        for col, title in zip(columns1, ("Nombre de RED", "Prefijo", "Primera IP Utilizable", "Última IP Utilizable", "Broadcast")):
            self.tree1.heading(col, text=title)
            self.tree1.column(col, width=120, anchor="center")
        self.tree1.pack(fill="both", expand=True)
        t2_frame = ttk.LabelFrame(out, text="TABLA 2: Detalle (IP+Prefijo / Broadcast / Rango hosts)")
        t2_frame.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        columns2 = ("name", "ip_pref", "broadcast", "host_range")
        self.tree2 = ttk.Treeview(t2_frame, columns=columns2, show="headings", height=12)
        for col, title in zip(columns2, ("Nombre de RED", "IP + Prefijo", "Broadcast", "Rango de Hosts [IP+1 ; Broadcast-1]")):
            self.tree2.heading(col, text=title)
            self.tree2.column(col, width=160, anchor="center")
        self.tree2.pack(fill="both", expand=True)

        canvas_frame = ttk.LabelFrame(top, text="Visualización de Routers y Conexiones")
        canvas_frame.pack(side="right", fill="both", expand=True, padx=6, pady=6)
        self.canvas = tk.Canvas(canvas_frame, bg="white", height=400)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-2>", self.on_middle_press)
        self.canvas.bind("<B2-Motion>", self.on_middle_motion)
        self.canvas.bind("<ButtonRelease-2>", self.on_middle_release)
        self.canvas.bind("<ButtonPress-3>", self.on_middle_press)
        self.canvas.bind("<B3-Motion>", self.on_middle_motion)
        self.canvas.bind("<ButtonRelease-3>", self.on_middle_release)

        summary_frame = ttk.LabelFrame(self, text="Resumen / Mensajes")
        summary_frame.pack(side="top", fill="x", padx=6, pady=4)
        self.txt_summary = tk.Text(summary_frame, height=6)
        self.txt_summary.pack(fill="x")

    # --------------------------
    # Métodos para canvas con drag
    # --------------------------
    def _refresh_canvas(self):
        self.canvas.delete("all")

        for conn in self.connections:
            if conn.a in self.routers and conn.b in self.routers:
                x1, y1 = self.routers[conn.a].pos
                x2, y2 = self.routers[conn.b].pos
                self.canvas.create_line(x1, y1, x2, y2, fill="red", width=2, tags="conn")

        for rname, router in self.routers.items():
            x, y = router.pos
            circle = self.canvas.create_oval(x-25, y-25, x+25, y+25,
                                            fill=router.color, outline="black", width=2, tags=("router", rname))
            label = self.canvas.create_text(x, y, text=rname, font=("Arial", 10, "bold"), tags=("label", rname))
            router.canvas_items = (circle, label)

            for tag in (circle, label):
                self.canvas.tag_bind(tag, "<Button-1>", self.on_drag_start)
                self.canvas.tag_bind(tag, "<B1-Motion>", self.on_drag_motion)
                self.canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_drag_release)

        self.canvas.tag_lower("conn")

    def on_drag_start(self, event):
        tags = self.canvas.gettags("current")
        if tags and len(tags) >= 2:
            rname = tags[1]
            self.drag_data["item"] = rname
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y
            self.canvas.grab_set()

    def on_drag_motion(self, event):
        if self.drag_data["item"] is None:
            return
        rname = self.drag_data["item"]
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]

        circle, label = self.routers[rname].canvas_items
        self.canvas.move(circle, dx, dy)
        self.canvas.move(label, dx, dy)

        x, y = self.routers[rname].pos
        self.routers[rname].pos = (x + dx, y + dy)

        self.canvas.delete("conn")
        for conn in self.connections:
            if conn.a in self.routers and conn.b in self.routers:
                x1, y1 = self.routers[conn.a].pos
                x2, y2 = self.routers[conn.b].pos
                self.canvas.create_line(x1, y1, x2, y2, fill="red", width=2, tags="conn")

        self.canvas.tag_lower("conn")

        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_drag_release(self, event):
        self.canvas.grab_release()
        self.drag_data["item"] = None

    # --------------------------
    # Métodos para pan con botón central (rueda)
    # --------------------------
    def on_middle_press(self, event):
        self.pan_data["active"] = True
        self.pan_data["x"] = event.x
        self.pan_data["y"] = event.y
        try:
            self.canvas.grab_set()
        except Exception:
            pass
        try:
            self.canvas.scan_mark(event.x, event.y)
        except Exception:
            pass
        try:
            self.canvas.config(cursor="fleur")
        except Exception:
            pass

    def on_middle_motion(self, event):
        if not self.pan_data.get("active", False):
            return
        try:
            self.canvas.scan_dragto(event.x, event.y, gain=1)
        except Exception:
            dx = event.x - self.pan_data["x"]
            dy = event.y - self.pan_data["y"]
            for r in self.routers.values():
                rx, ry = r.pos
                r.pos = (rx + dx, ry + dy)
            self.pan_data["x"] = event.x
            self.pan_data["y"] = event.y
            self._refresh_canvas()

    def on_middle_release(self, event):
        self.pan_data["active"] = False
        try:
            self.canvas.grab_release()
        except Exception:
            pass
        try:
            self.canvas.config(cursor="")
        except Exception:
            pass

    def add_router(self):
        name = self.ent_router_name.get().strip()
        if not name:
            messagebox.showwarning("Validación", "Ingrese un nombre de router.")
            return
        if name in self.routers:
            messagebox.showwarning("Duplicado", "Ya existe un router con ese nombre.")
            return
        groups = []
        for e in self.group_entries:
            val = e.get().strip()
            if val == "":
                groups.append(0)
            else:
                try:
                    iv = int(val)
                    if iv < 0:
                        raise ValueError()
                    groups.append(iv)
                except Exception:
                    messagebox.showerror("Error", "Los hosts por grupo deben ser enteros >= 0.")
                    return
        r = Router(name)
        r.groups = groups[:4]
        self.routers[name] = r
        self.router_listbox.insert("end", name)
        self.ent_router_name.delete(0, "end")
        for e in self.group_entries:
            e.delete(0, "end")
        self.log(f"Router '{name}' agregado con grupos: {r.groups}")
        self._refresh_canvas()

    def delete_router(self):
        sels = self.router_listbox.curselection()
        if not sels:
            messagebox.showinfo("Info", "Seleccione al menos un router para eliminar.")
            return
        names_to_delete = [self.router_listbox.get(i) for i in sels]
        for idx in sorted(sels, reverse=True):
            self.router_listbox.delete(idx)
        for name in names_to_delete:
            if name in self.routers:
                del self.routers[name]
        self.connections = [c for c in self.connections if c.a in self.routers and c.b in self.routers]
        self._refresh_conn_listbox()
        self.log(f"Router(s) eliminado(s): {', '.join(names_to_delete)}")
        self._refresh_canvas()

    def connect_selected(self):
        sels = self.router_listbox.curselection()
        if len(sels) != 2:
            messagebox.showinfo("Info", "Seleccione exactamente dos routers para conectar.")
            return
        r1 = self.router_listbox.get(sels[0])
        r2 = self.router_listbox.get(sels[1])
        if r1 == r2:
            messagebox.showerror("Error", "No se puede conectar un router a sí mismo.")
            return
        for c in self.connections:
            if (c.a == r1 and c.b == r2) or (c.a == r2 and c.b == r1):
                messagebox.showinfo("Info", "La conexión ya existe.")
                return
        conn = Connection(r1, r2)
        self.connections.append(conn)
        self._refresh_conn_listbox()
        self.log(f"Conexión creada: {r1} <-> {r2}")
        self._refresh_canvas()

    def delete_connection(self):
        sel = self.conn_listbox.curselection()
        if not sel:
            messagebox.showinfo("Info", "Seleccione una conexión para eliminar.")
            return
        idx = sel[0]
        del self.connections[idx]
        self._refresh_conn_listbox()
        self.log("Conexión eliminada.")
        self._refresh_canvas()

    def _refresh_conn_listbox(self):
        self.conn_listbox.delete(0, "end")
        for i, c in enumerate(self.connections, start=1):
            self.conn_listbox.insert("end", f"{c.a} <-> {c.b}")

    def load_example(self):
        self.routers.clear()
        self.connections.clear()
        self.router_listbox.delete(0, "end")
        self.conn_listbox.delete(0, "end")
        ra = Router("Router-ed1")
        ra.groups = [480, 0, 0, 0]
        rb = Router("ed2")
        rb.groups = [900, 0, 0, 0]
        rc = Router("ed3")
        rc.groups = [115, 0, 0, 0]
        rd = Router("ed4")
        rd.groups = [50, 0, 0, 0]
        self.routers[ra.name] = ra
        self.routers[rb.name] = rb
        self.routers[rc.name] = rc
        self.routers[rd.name] = rd
        for r in (ra, rb, rc, rd):
            self.router_listbox.insert("end", r.name)
        self.connections.append(Connection(ra.name, rc.name))
        self.connections.append(Connection(ra.name, rd.name))
        self.connections.append(Connection(ra.name, rb.name))
        self._refresh_conn_listbox()
        self.log("Ejemplo cargado (Router-ed1 y enlaces).")
        self._refresh_canvas()

    def generate(self):
        if not self.routers:
            messagebox.showerror("Error", "No hay routers definidos.")
            return
        base = self.base_net_entry.get().strip()
        try:
            _ = ipaddress.ip_network(base, strict=False)
        except Exception as e:
            messagebox.showerror("Error", f"Base network inválida: {e}")
            return
        mode = self.mode_var.get()
        try:
            allocator = Allocator(self.routers, self.connections, mode, base_network=base)
            allocations = allocator.allocate()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo asignar subredes: {e}")
            return

        self.alloc_map.clear()
        for name, net in allocations:
            self.alloc_map[name] = net

        for t in (self.tree1, self.tree2):
            for item in t.get_children():
                t.delete(item)

        last_net = None
        for name, net in allocations:
            last_net = net
            pref = net.prefixlen
            if net.num_addresses == 1:
                first = last = net.network_address
                broadcast = net.network_address
            elif net.num_addresses == 2:
                first = net.network_address
                last = net.broadcast_address
                broadcast = net.broadcast_address
            else:
                first = ipaddress.IPv4Address(int(net.network_address) + 1)
                last = ipaddress.IPv4Address(int(net.broadcast_address) - 1)
                broadcast = net.broadcast_address
            self.tree1.insert("", "end", values=(name, f"/{pref}", str(first), str(last), str(broadcast)))
            ip_pref = f"{net.network_address}/{pref}"
            if net.num_addresses > 2:
                host_range = f"[{str(ipaddress.IPv4Address(int(net.network_address) + 1))} ; {str(ipaddress.IPv4Address(int(net.broadcast_address) - 1))}]"
            elif net.num_addresses == 2:
                host_range = f"[{str(net.network_address)} ; {str(net.broadcast_address)}]"
            else:
                host_range = "N/A"
            self.tree2.insert("", "end", values=(name, ip_pref, str(broadcast), host_range))

        if last_net is not None:
            block_size = last_net.num_addresses
            next_network = ipaddress.ip_network((int(last_net.network_address) + block_size, last_net.max_prefixlen), strict=False).supernet(new_prefix=last_net.prefixlen)
            ip_pref_extra = f"{next_network.network_address}/{last_net.prefixlen}"
            self.tree2.insert("", "end", values=("Extra", ip_pref_extra, "-", "-"))

        self.log(f"Generado {len(self.alloc_map)} redes. Base={base}")

    def log(self, msg: str):
        self.txt_summary.insert("end", msg + "\n")
        self.txt_summary.see("end")

    def export_cisco_topology(self):
        if not self.alloc_map:
            messagebox.showerror("Error", "Primero genere las subredes (Generar Resultados).")
            return
        filename = filedialog.asksaveasfilename(
            title="Guardar Topology como...",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="cisco_topology.txt"
        )
        if not filename:
            return

        dns = self.dns_entry.get().strip() if self.include_dns_var.get() else None

        device_info = {}
        for rname in self.routers:
            device_info[rname] = {'type': 'Cisco 2901', 'interfaces': []}

        switch_records = {}
        scount = 0
        pcount = 0
        router_gig_idx = {r: 0 for r in self.routers}

        for rname, router in self.routers.items():
            for i, hosts in enumerate(router.groups, start=1):
                if not hosts or hosts <= 0:
                    continue
                net_name = f"{rname}-G{i}"
                net = self.alloc_map.get(net_name)
                if not net:
                    continue
                scount += 1
                pcount += 1
                sname = f"SW_{rname}_G{i}"
                pname = f"PC_{rname}_G{i}"
                switch_records[(rname, i)] = (sname, pname, net)

                gi_idx = router_gig_idx[rname]
                r_if = f"GigabitEthernet0/{gi_idx}"
                router_gig_idx[rname] += 1

                router_ip = ipaddress.IPv4Address(int(net.network_address) + 1)
                pc_ip = ipaddress.IPv4Address(int(net.network_address) + 2)
                mask_dec = str(net.netmask)
                mask_bin = mask_to_binary(mask_dec)

                device_info[rname]['interfaces'].append({
                    'name': r_if,
                    'ip': str(router_ip),
                    'mask_dec': mask_dec,
                    'mask_bin': mask_bin,
                    'connected_to': f"{sname} FastEthernet0/1",
                    'no_shutdown': True
                })

                device_info[sname] = {'type': 'Switch 2950/2960', 'interfaces': [
                    {'name': 'FastEthernet0/1', 'ip': None, 'mask_dec': None, 'mask_bin': None, 'connected_to': f"{rname} {r_if}", 'no_shutdown': True},
                    {'name': 'FastEthernet0/2', 'ip': str(pc_ip), 'mask_dec': mask_dec, 'mask_bin': mask_bin, 'connected_to': f"{pname} NIC", 'no_shutdown': True}
                ]}

                device_info[pname] = {'type': 'Generic PC', 'interfaces': [
                    {'name': 'NIC', 'ip': str(pc_ip), 'mask_dec': mask_dec, 'mask_bin': mask_bin, 'gateway': str(router_ip), 'dns': dns}
                ]}

        router_serial_idx = {r: 0 for r in self.routers}
        serial_links = [] 
        for idx, c in enumerate(self.connections, start=1):
            link_name = f"{c.a}-{c.b}-link{idx}"
            net = self.alloc_map.get(link_name)
            if not net:
                continue

            iface_a = f"Serial0/0/{router_serial_idx[c.a]}"
            router_serial_idx[c.a] += 1
            iface_b = f"Serial0/0/{router_serial_idx[c.b]}"
            router_serial_idx[c.b] += 1

            ip_a = ipaddress.IPv4Address(int(net.network_address) + 1)
            ip_b = ipaddress.IPv4Address(int(net.network_address) + 2)
            mask_dec = str(net.netmask)
            mask_bin = mask_to_binary(mask_dec)

            if c.a not in device_info:
                device_info[c.a] = {'type': 'Cisco 2901', 'interfaces': []}
            if c.b not in device_info:
                device_info[c.b] = {'type': 'Cisco 2901', 'interfaces': []}

            device_info[c.a]['interfaces'].append({
                'name': iface_a,
                'ip': str(ip_a),
                'mask_dec': mask_dec,
                'mask_bin': mask_bin,
                'connected_to': f"{c.b} {iface_b}",
                'no_shutdown': True
            })
            device_info[c.b]['interfaces'].append({
                'name': iface_b,
                'ip': str(ip_b),
                'mask_dec': mask_dec,
                'mask_bin': mask_bin,
                'connected_to': f"{c.a} {iface_a}",
                'no_shutdown': True
            })

            serial_links.append((c.a, iface_a, c.b, iface_b, 'Serial (DTE)', f"{net.network_address}/{net.prefixlen}", mask_dec, mask_bin))

        straight_links = []
        for (rname, i), (sname, pname, net) in switch_records.items():

            gi_iface = None
            for iface in device_info[rname]['interfaces']:
                if iface.get('connected_to') and iface['connected_to'].startswith(sname):
                    gi_iface = iface['name']
                    break
            if gi_iface is None:
                continue

            straight_links.append((rname, gi_iface, sname, 'FastEthernet0/1', 'Straight-through', f"{net.network_address}/{net.prefixlen}", str(net.netmask), mask_to_binary(str(net.netmask))))

        try:
            with open(filename, 'w', encoding='utf-8', newline='\n') as f:

                f.write("#Connections:\n")

                for a, ifa, b, ifb, ltype, netstr, mask_dec, mask_bin in serial_links:
                    f.write(f"{a} {ifa} [{ltype} Wire->] {b} {ifb}  network: {netstr} mask: {mask_dec} ({mask_bin})\n")

                for r, rif, s, sif, ltype, netstr, mask_dec, mask_bin in straight_links:
                    f.write(f"{r} {rif} [{ltype} ->] {s} {sif}  network: {netstr} mask: {mask_dec} ({mask_bin})\n")

                f.write("\n")
                for dev in sorted(device_info.keys()):
                    info = device_info[dev]
                    f.write(f"Device: {dev}\n")
                    f.write(f"Type: {info['type']}\n")
                    for iface in info['interfaces']:
                        f.write(f"Interface: {iface['name']}\n")
                        if iface.get('ip'):
                            f.write(f"  IP address: {iface['ip']}  Mask: {iface['mask_dec']}\n")
                            f.write(f"  Mask (binary): {iface['mask_bin']}\n")
                        if iface.get('connected_to'):
                            f.write(f"  Connected to: {iface['connected_to']}\n")
                        if iface.get('no_shutdown'):
                            f.write(f"  no shutdown\n")
                        if info['type'].startswith('Generic PC') and iface.get('ip'):
                            gw = iface.get('gateway')
                            if gw:
                                f.write(f"  Default gateway: {gw}\n")
                            if iface.get('dns'):
                                f.write(f"  DNS: {iface.get('dns')}\n")
                        f.write("\n")
                    f.write("\n")
        except Exception as e:
            messagebox.showerror('Error', f'No se pudo escribir el archivo: {e}')
            return

        messagebox.showinfo('Exportado', f'Topología Cisco exportada a: {filename}')
        self.log(f'Topología Cisco exportada: {filename}')
    
    def export_cisco_cli(self):
        if not self.alloc_map:
            messagebox.showerror("Error", "Primero genere las subredes (Generar Resultados).")
            return
        filename = filedialog.asksaveasfilename(
            title="Guardar CLI como...",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="cisco_cli.txt"
        )
        if not filename:
            return

        dns = self.dns_entry.get().strip() if self.include_dns_var.get() else None

        lines = []

        router_short = {}
        for idx, rname in enumerate(sorted(self.routers.keys()), start=1):
            router_short[rname] = f"R{idx}"

        router_ifc = {rname: {'serial': 0, 'gig': 0} for rname in self.routers}

        for rname in sorted(self.routers.keys()):
            short = router_short[rname]
            lines.append(f"! --- Router {rname} ({short}) ---")
            lines.append("enable")
            lines.append("configure terminal")
            lines.append(f"hostname {short}")
            lines.append("no ip domain-lookup")
            if dns:
                lines.append(f"ip name-server {dns}")
            lines.append("")

            for idx, c in enumerate(self.connections, start=1):
                if c.a != rname and c.b != rname:
                    continue
                link_name = f"{c.a}-{c.b}-link{idx}"
                net = self.alloc_map.get(link_name)
                if not net:
                    continue

                iface = f"Serial0/0/{router_ifc[rname]['serial']}"
                router_ifc[rname]['serial'] += 1
                ip_a = ipaddress.IPv4Address(int(net.network_address) + 1)
                ip_b = ipaddress.IPv4Address(int(net.network_address) + 2)
                ip = ip_a if c.a == rname else ip_b
                lines.append(f"interface {iface}")
                lines.append(f" ip address {ip} {str(net.netmask)}")
                lines.append(" no shutdown")
                lines.append(" exit")
                lines.append("")

            for i, hosts in enumerate(self.routers[rname].groups, start=1):
                if not hosts or hosts <= 0:
                    continue
                net = self.alloc_map.get(f"{rname}-G{i}")
                if not net:
                    continue
                gi = router_ifc[rname]['gig']
                iface = f"GigabitEthernet0/{gi}"
                router_ifc[rname]['gig'] += 1
                ip_router = ipaddress.IPv4Address(int(net.network_address) + 1)
                lines.append(f"interface {iface}")
                lines.append(f" ip address {ip_router} {str(net.netmask)}")
                lines.append(" no shutdown")
                lines.append(" exit")
                lines.append("")

            lines.append("end")
            lines.append("write memory")
            lines.append("")
            lines.append("")

        scount = 0
        pcount = 0
        for rname in sorted(self.routers.keys()):
            for i, hosts in enumerate(self.routers[rname].groups, start=1):
                if not hosts or hosts <= 0:
                    continue
                scount += 1
                pcount += 1
                sname = f"SW_{rname}_G{i}"
                pcname = f"PC_{rname}_G{i}"
                net = self.alloc_map.get(f"{rname}-G{i}")
                if not net:
                    continue
                ip_router = ipaddress.IPv4Address(int(net.network_address) + 1)
                ip_pc = ipaddress.IPv4Address(int(net.network_address) + 2)
                mask = str(net.netmask)

                lines.append(f"! --- Switch {sname} (para {rname}-G{i}) ---")
                lines.append("enable")
                lines.append("configure terminal")
                lines.append(f"hostname {sname}")
                lines.append("interface FastEthernet0/1")
                lines.append(" switchport mode access")
                lines.append(" no shutdown")
                lines.append(" exit")
                lines.append("end")
                lines.append("write memory")
                lines.append("")
                lines.append(f"# PC {pcname} settings:")
                lines.append(f"# IP address: {ip_pc}")
                lines.append(f"# Subnet mask: {mask}  (binary: {mask_to_binary(mask)})")
                lines.append(f"# Default gateway: {ip_router}")
                if dns:
                    lines.append(f"# DNS: {dns}")
                lines.append("")

        try:
            with open(filename, 'w', encoding='utf-8', newline='\n') as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            messagebox.showerror('Error', f'No se pudo escribir el archivo: {e}')
            return

        messagebox.showinfo('Exportado', f'CLI Cisco exportado a: {filename}')
        self.log(f'CLI Cisco exportado: {filename}')

    def export_to_txt(self):
        if not self.tree1.get_children() and not self.tree2.get_children():
            messagebox.showinfo("Info", "No hay resultados para exportar. Genere primero las tablas.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Archivo de texto", "*.txt")],
            title="Guardar resultados como...",
            initialfile="tablas_redes.txt"  
        )
        if not file_path:
            return  

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("==== TABLA 1: Resumen de Redes ====\n")
                f.write("{:<20} {:<10} {:<20} {:<20} {:<20}\n".format(
                    "Nombre de RED", "Prefijo", "Primera IP", "Última IP", "Broadcast"))
                f.write("-" * 90 + "\n")
                for item in self.tree1.get_children():
                    vals = self.tree1.item(item, "values")
                    f.write("{:<20} {:<10} {:<20} {:<20} {:<20}\n".format(*vals))

                f.write("\n==== TABLA 2: Detalle ====\n")
                f.write("{:<20} {:<20} {:<20} {:<40}\n".format(
                    "Nombre de RED", "IP + Prefijo", "Broadcast", "Rango Hosts"))
                f.write("-" * 110 + "\n")
                for item in self.tree2.get_children():
                    vals = self.tree2.item(item, "values")
                    f.write("{:<20} {:<20} {:<20} {:<40}\n".format(*vals))

            messagebox.showinfo("Éxito", f"Resultados exportados en:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar: {e}")

    def generate_rip_config(self):
        if not self.alloc_map:
            messagebox.showerror("Error", "Primero genere las subredes (Generar Resultados).")
            return

        filename = filedialog.asksaveasfilename(
            title="Guardar Config RIP como...",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="cisco_rip_configs.txt"
        )
        if not filename:
            return

        try:

            router_networks = {rname: set() for rname in self.routers.keys()}

            for rname in self.routers.keys():
                for i in range(1, 5):  
                    key = f"{rname}-G{i}"
                    net = self.alloc_map.get(key)
                    if net:
                        router_networks[rname].add(str(net.network_address))

            for idx, c in enumerate(self.connections, start=1):
                link_name = f"{c.a}-{c.b}-link{idx}"
                net = self.alloc_map.get(link_name)
                if not net:
                    continue
                netaddr = str(net.network_address)
                if c.a in router_networks:
                    router_networks[c.a].add(netaddr)
                if c.b in router_networks:
                    router_networks[c.b].add(netaddr)

            lines = []
            for rname in sorted(self.routers.keys()):
                lines.append(f"--{rname}:")
                lines.append("enable")
                lines.append("conf t")
                lines.append("router rip")
                lines.append(" version 2")
                lines.append(" no auto-summary")

                nets = sorted(router_networks.get(rname, set()), key=lambda ip: ipaddress.IPv4Address(ip))
                if not nets:
                    lines.append("! No networks assigned to this router")
                else:
                    for net in nets:
                        lines.append(f" network {net}")

                lines.append("end")
                lines.append("") 

            with open(filename, 'w', encoding='utf-8', newline='\n') as f:
                f.write("\n".join(lines))

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar RIP: {e}")
            return

        messagebox.showinfo("Exportado", f"Configuraciones RIP exportadas a: {filename}")
        self.log(f"Configuraciones RIP exportadas: {filename}")


    # --------------------------
    # Author: Mariano Obltias
    # --------------------------

def main():
    root = tk.Tk()
    app = SubnetPlannerApp(root)
    root.geometry("1200x650")
    root.mainloop()


if __name__ == "__main__":
    main()

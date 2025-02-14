import time
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, messagebox
import random
import re
import networkx as nx
from queue import Queue
from pyreadline3.console import event

class NetworkSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Network Simulator")
        self.root.geometry("1000x700")  # Increased window height for terminal
        self.is_transmitting = False  # Add this in the class initialization
        # Initialize devices BEFORE setup
        self.devices = {}
        self.connections = []
        self.network_graph = nx.Graph()
        self.current_connection_type = None
        self.connection_start_device = None
        self.selected_device = None
        self.delete_mode = False
        self.delete_connection_mode = False
        self.packet_queue = Queue()  # Queue for managing packet transmissions
        # Main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)

        # Canvas for network topology
        self.canvas = tk.Canvas(self.main_frame, bg="white", width=700, height=500)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # Frame for controls
        self.device_frame = ttk.Frame(self.main_frame, padding="5", width=480)  # Adjust width as needed
        self.device_frame.pack(side="right", fill="y")
        self.device_frame.pack_propagate(False)
        self.setup_sidebar()

        # Terminal Frame
        self.terminal_frame = ttk.Frame(self.root, padding="5", height=200)
        self.terminal_frame.pack(fill="x", side="bottom")
        self.setup_terminal()

    def setup_terminal(self):
        # Terminal text area
        self.terminal_text = tk.Text(self.terminal_frame, height=10, bg="black", fg="white")
        self.terminal_text.pack(fill="x", expand=True)
        self.terminal_text.insert("end", "Terminal ready. Type 'help' for commands.\n")
        self.terminal_text.configure(state="disabled")

        # Terminal input
        self.terminal_entry = ttk.Entry(self.terminal_frame)
        self.terminal_entry.pack(fill="x")
        self.terminal_entry.bind("<Return>", self.handle_terminal_command)

    def handle_terminal_command(self, event):
        """Process terminal commands entered by the user."""
        command = self.terminal_entry.get().strip()
        self.terminal_entry.delete(0, tk.END)

        # Convert command to lowercase for case-insensitive comparison
        normalized_command = command.lower()

        if normalized_command == "help":
            self.write_to_terminal(
                "Available commands:\n- Ping <source_ip> <destination_ip>\n- Show Devices\n- SendPacket <source_ip> <destination_ip> TCP/UDP")
        elif normalized_command == "show devices":
            self.show_devices()
        elif normalized_command.startswith("ping "):  # Ensure a space follows 'ping'
            self.execute_ping(command)
        elif normalized_command.startswith("sendpacket "):  # Ensure a space follows 'sendpacket'
            self.execute_send_packet(command)
        else:
            self.write_to_terminal("Unknown command. Type 'help' for a list of commands.\n")

    def write_to_terminal(self, message):
        self.terminal_text.configure(state="normal")
        self.terminal_text.insert("end", message + "\n")
        self.terminal_text.see("end")  # Scroll to the bottom
        self.terminal_text.configure(state="disabled")

    def execute_ping(self, command):
        """Handle the 'ping' command to simulate packet transmission."""
        try:
            parts = command.strip().split()
            if len(parts) != 3 or parts[0].lower() != "ping":
                self.write_to_terminal("Invalid command. Use: ping <source_ip> <destination_ip>")
                return

            ip1, ip2 = parts[1], parts[2]
            available_ips = {device.ip_address: device for device in self.devices.values()}

            if ip1 not in available_ips or ip2 not in available_ips:
                self.write_to_terminal("Error: One or both IPs not found in the network.")
                return

            src_device = available_ips[ip1]
            dest_device = available_ips[ip2]

            if nx.has_path(self.network_graph, src_device.id, dest_device.id):
                path = nx.shortest_path(self.network_graph, src_device.id, dest_device.id)
                hops = len(path) - 1  # Calculate hops (edges in the path)
                ttl = 64  # Initial TTL value

                self.write_to_terminal(f"Pinging {ip2} from {ip1} with 4 packets:")

                for packet_num in range(4):
                    total_delay = 0
                    for i in range(hops):
                        device1 = self.devices[path[i]]
                        device2 = self.devices[path[i + 1]]
                        edge_data = self.network_graph.get_edge_data(device1.id, device2.id)
                        connection_type = edge_data.get("type", "Copper")
                        # Calculate a slightly varied delay per hop for this packet
                        delay_per_hop = self.get_deterministic_delay(connection_type, variation=True)
                        total_delay += delay_per_hop

                    adjusted_ttl = ttl - hops  # Adjust TTL based on hops
                    if adjusted_ttl > 0:
                        self.write_to_terminal(
                            f"Reply from {ip2}: TTL={adjusted_ttl}, Delay={total_delay:.2f}ms (Packet {packet_num + 1})"
                        )
                    else:
                        self.write_to_terminal(f"Request timed out (TTL expired).")
            else:
                self.write_to_terminal(f"Ping failed: {ip2} is unreachable from {ip1}.")

        except Exception as e:
            self.write_to_terminal(f"Error executing ping: {str(e)}")

    def get_deterministic_delay(self, connection_type, variation=False):
        """Return a delay based on the cable type with optional slight variation."""
        cable_delays = {
            "Copper": 50,  # Base delay in milliseconds for copper cable
            "Fiber": 10,  # Base delay in milliseconds for fiber cable
        }
        base_delay = cable_delays.get(connection_type, 100)  # Default to a higher delay for unknown cable types

        if variation:
            # Introduce slight variation: Â±5% of base delay
            variation_percentage = 0.05
            min_delay = base_delay * (1 - variation_percentage)
            max_delay = base_delay * (1 + variation_percentage)
            return random.uniform(min_delay, max_delay)

        return base_delay

    def execute_send_packet(self, command):
        """Handle the 'SendPacket' command to simulate TCP/UDP packet transmission with animation."""
        try:
            parts = command.strip().split()
            if len(parts) != 4 or parts[0].lower() != "sendpacket":
                self.write_to_terminal("Invalid command. Use: SendPacket <source_ip> <destination_ip> TCP/UDP")
                return

            ip1, ip2, protocol = parts[1], parts[2], parts[3].upper()
            if protocol not in ("TCP", "UDP"):
                self.write_to_terminal("Invalid protocol. Use either TCP or UDP.")
                return

            available_ips = {device.ip_address: device for device in self.devices.values()}

            if ip1 not in available_ips or ip2 not in available_ips:
                self.write_to_terminal("Error: One or both IPs not found in the network.")
                return

            src_device = available_ips[ip1]
            dest_device = available_ips[ip2]

            if not nx.has_path(self.network_graph, src_device.id, dest_device.id):
                self.write_to_terminal(f"SendPacket failed: {ip2} is unreachable from {ip1}.")
                return

            path = nx.shortest_path(self.network_graph, src_device.id, dest_device.id)
            self.write_to_terminal(f"Sending {protocol} packet from {ip1} to {ip2}...")

            if protocol == "TCP":
                self.simulate_tcp_packet(path, src_device, dest_device)
            elif protocol == "UDP":
                self.simulate_packet(path, src_device, dest_device)

        except Exception as e:
            self.write_to_terminal(f"Error executing SendPacket: {str(e)}")

    def simulate_tcp_packet(self, path, src_device, dest_device):
        """Simulate TCP packet traveling from source to destination and back."""
        self.write_to_terminal(f"TCP packet sent from {src_device.ip_address} to {dest_device.ip_address}...")

        def return_packet():
            """Animate the packet's return to the source."""
            reversed_path = path[::-1]  # Reverse the path for return
            self.write_to_terminal(
                f"TCP acknowledgment sent from {dest_device.ip_address} to {src_device.ip_address}...")
            self.simulate_packet(reversed_path, dest_device, src_device, acknowledge=False)

        # Animate the forward path
        self.simulate_packet(path, src_device, dest_device)

        # Schedule the return animation
        self.root.after(len(path) * 1000, return_packet)

    def simulate_packet(self, path, src_device, dest_device, acknowledge=False):
        """Simulate packet transmission step-by-step along the path."""
        self.packet_queue.put((path, src_device, dest_device, acknowledge))
        if not self.is_transmitting:
            self._process_packet_queue()

    def _process_packet_queue(self):
        """Process the next packet in the queue."""
        if self.packet_queue.empty():
            return  # Nothing to process

        self.is_transmitting = True
        self._disable_device_dragging()

        # Clean up any lingering packet representation
        if hasattr(self, "active_packet") and self.active_packet is not None:
            self._delete_active_packet()

        # Get the next packet details
        path, src_device, dest_device, acknowledge = self.packet_queue.get()

        def move_along_path(segment_index):
            if segment_index < len(path) - 1:
                device1 = self.devices[path[segment_index]]
                device2 = self.devices[path[segment_index + 1]]

                is_final = (segment_index == len(path) - 2)

                self.animate_packet(device1, device2, is_final=is_final)

                self.root.after(1000, lambda: move_along_path(segment_index + 1))  # Delay for each segment
            else:
                if acknowledge:
                    # For TCP, reverse the path for acknowledgment
                    reversed_path = path[::-1]
                    self.simulate_packet(reversed_path, dest_device, src_device, acknowledge=False)
                else:
                    self.is_transmitting = False
                    self._enable_device_dragging()
                    self._process_packet_queue()

        move_along_path(0)

    def simulate_udp_packet(self, dest_device):
        """Simulate UDP packet transmission."""
        delay = random.uniform(10, 100)  # Simulate delay in milliseconds
        self.write_to_terminal(f"UDP packet sent to {dest_device.ip_address}. Delay={delay:.2f}ms")

    def simulate_packet(self, path, src_device, dest_device, acknowledge=False):
        """Simulate packet transmission step-by-step along the path."""
        self.packet_queue.put((path, src_device, dest_device, acknowledge))
        if not self.is_transmitting:
            self._process_packet_queue()

    def _process_packet_queue(self):
        """Process the next packet in the queue."""
        if self.packet_queue.empty():
            return  # Nothing to process

        self.is_transmitting = True
        self._disable_device_dragging()

        # Clean up any lingering packet representation
        if hasattr(self, "active_packet") and self.active_packet is not None:
            self._delete_active_packet()

        # Get the next packet details
        path, src_device, dest_device, acknowledge = self.packet_queue.get()

        animation_time_per_segment = 1000

        def move_to_next_segment(segment_index, reverse=False):
            """Handle movement for the current segment, then move to the next."""
            if segment_index < len(path) - 1:
                device1 = self.devices[path[segment_index]]
                device2 = self.devices[path[segment_index + 1]]

                is_final = (segment_index == len(path) - 2)
                self.animate_packet(device1, device2, is_final=is_final and not reverse)

                self.root.after(
                    animation_time_per_segment,
                    lambda: move_to_next_segment(segment_index + 1, reverse)
                )
            elif acknowledge and not reverse:
                # For TCP, reverse the path for acknowledgment
                reversed_path = path[::-1]
                move_to_next_segment(0, reverse=True)
            elif reverse:
                # Once acknowledgment completes
                self.write_to_terminal(f"Acknowledgment received by {src_device.ip_address}.")
                self.is_transmitting = False
                self._enable_device_dragging()

                # Resume processing the main queue
                self._process_packet_queue()
            else:
                # For UDP, just finish
                self.is_transmitting = False
                self._enable_device_dragging()
                self._process_packet_queue()

        move_to_next_segment(0)


    def _process_acknowledgment(self, path, src_device, dest_device):
        """Directly process the acknowledgment transmission."""
        self.is_transmitting = True  # Lock the system for acknowledgment
        self._disable_device_dragging()

        animation_time_per_segment = 1000

        def move_to_next_segment(segment_index):
            """Handle movement for the current segment, then move to the next."""
            if segment_index < len(path) - 1:
                device1 = self.devices[path[segment_index]]
                device2 = self.devices[path[segment_index + 1]]

                is_final = (segment_index == len(path) - 2)
                self.animate_packet(device1, device2, is_final=is_final)

                self.root.after(animation_time_per_segment, lambda: move_to_next_segment(segment_index + 1))
            else:
                # Once acknowledgment completes
                self.write_to_terminal(f"Acknowledgment received by {dest_device.ip_address}.")
                self.is_transmitting = False
                self._enable_device_dragging()

                # Resume processing the main queue
                self._process_packet_queue()

        move_to_next_segment(0)

    def _disable_device_dragging(self):
        """Disable dragging for all devices."""
        for device in self.devices.values():
            self.canvas.tag_unbind(device.shape_id, "<B1-Motion>")
            self.canvas.tag_unbind(device.text_id, "<B1-Motion>")
        self.write_to_terminal("Device dragging disabled during transmission.")

    def _enable_device_dragging(self):
        """Re-enable dragging for all devices."""
        for device in self.devices.values():
            self.canvas.tag_bind(device.shape_id, "<B1-Motion>", device.on_device_drag)
            self.canvas.tag_bind(device.text_id, "<B1-Motion>", device.on_device_drag)
        self.write_to_terminal("Device dragging re-enabled.")

    def get_connection_delay(self, connection_type):
        """Return delay based on connection type."""
        if connection_type == "Copper":
            return random.randint(10, 50)
        elif connection_type == "Fiber":
            return random.randint(1, 10)
        return random.randint(50, 100)

    def animate_packet(self, device1, device2, is_final=False):
        """Smoothly animate a packet moving along the connection line between two devices."""
        x1, y1 = self.get_device_center(device1)
        x2, y2 = self.get_device_center(device2)

        # Create the packet representation if it doesn't exist
        if not hasattr(self, "active_packet") or self.active_packet is None:
            self.active_packet = self.canvas.create_oval(x1 - 5, y1 - 5, x1 + 5, y1 + 5, fill="red")
        else:
            self.canvas.coords(self.active_packet, x1 - 5, y1 - 5, x1 + 5, y1 + 5)

        # Define the number of steps for smooth movement
        steps = 50  # Adjust for smoothness
        interval = 20  # Smaller interval for smoother animation (milliseconds)

        def move_step(step):
            """Move the packet in small increments."""
            progress = step / steps
            current_x = x1 + (x2 - x1) * progress
            current_y = y1 + (y2 - y1) * progress

            self.canvas.coords(
                self.active_packet, current_x - 5, current_y - 5, current_x + 5, current_y + 5
            )

            if step < steps:
                self.root.after(interval, lambda: move_step(step + 1))
            else:
                # Once the packet reaches the destination:
                if is_final:
                    # Turn the packet green if it's the final destination
                    self.canvas.itemconfig(self.active_packet, fill="green")
                    # Delete the packet after a short delay
                    self.root.after(2500, lambda: self._delete_active_packet())

        # Start the animation
        move_step(0)

    def _delete_active_packet(self):
        """Delete the active packet and clear its reference."""
        if self.active_packet is not None:
            self.canvas.delete(self.active_packet)
            self.active_packet = None

    def simulate_broadcast(self, hub_device):
        """Simulate broadcast behavior for hubs."""
        neighbors = list(self.network_graph.neighbors(hub_device.id))
        for neighbor_id in neighbors:
            neighbor_device = self.devices[neighbor_id]
            self.animate_packet(hub_device, neighbor_device)
            delay = self.get_connection_delay(self.network_graph.get_edge_data(hub_device.id, neighbor_id)["type"])
            self.root.after(delay)

    def show_devices(self):
        if not self.devices:
            self.write_to_terminal("No devices found in the network.")
            return
        for device in self.devices.values():
            self.write_to_terminal(f"{device.device_type} (ID: {device.id}) - IP: {device.ip_address}")

    def setup_sidebar(self):
        notebook = ttk.Notebook(self.device_frame)
        notebook.pack(fill="both", expand=True)

        # Tabs for devices, connections, and device configuration
        network_devices_frame = ttk.Frame(notebook)
        end_devices_frame = ttk.Frame(notebook)
        connections_frame = ttk.Frame(notebook)
        device_config_frame = ttk.Frame(notebook)
        ping_frame = ttk.Frame(notebook)

        notebook.add(network_devices_frame, text="Network Devices")
        notebook.add(end_devices_frame, text="End Devices")
        notebook.add(connections_frame, text="Connections")
        notebook.add(device_config_frame, text="Device Configuration")
        notebook.add(ping_frame, text="Pinging")
        self.setup_pinging_tab(ping_frame)
        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=(5, 5))
        # Network Devices
        for device in ["Router", "Switch", "Hub"]:
            ttk.Button(
                network_devices_frame,
                text=device,
                command=lambda d=device: self.add_device(d),
            ).pack(fill="x", padx=5, pady=2)

        # End Devices
        for device in ["PC", "TV", "Phone"]:
            ttk.Button(
                end_devices_frame,
                text=device,
                command=lambda d=device: self.add_device(d),
            ).pack(fill="x", padx=5, pady=2)

        # Connections buttons
        ttk.Button(connections_frame, text="Delete Connection Mode",
                   command=self.toggle_delete_connection_mode).pack(fill="x", padx=5, pady=2)
        ttk.Button(connections_frame, text="Cancel Delete Mode",
                   command=self.cancel_delete_mode).pack(fill="x", padx=5, pady=2)

        # Wire Connections
        ttk.Button(connections_frame, text="Copper Wire", command=lambda: self.set_connection("Copper")).pack(
            fill="x", padx=5, pady=2
        )
        ttk.Button(connections_frame, text="Fiber Wire", command=lambda: self.set_connection("Fiber")).pack(
            fill="x", padx=5, pady=2
        )
        ttk.Button(connections_frame, text="Deselect Wire", command=self.deselect_connection).pack(
            fill="x", padx=5, pady=2
        )

        # Device Configuration Tab
        self.setup_device_config_tab(device_config_frame)

    def toggle_delete_device_mode(self):
        """Enter mode to delete devices by clicking on them."""
        self.delete_mode = "device"
        self.current_connection_type = None
        self.connection_start_device = None
        messagebox.showinfo("Delete Mode", "Click on a device to delete it. Click 'Cancel Delete Mode' to exit.")

    def toggle_delete_connection_mode(self):
        """Enable connection deletion mode."""
        self.delete_connection_mode = True
        messagebox.showinfo("Delete Connection Mode", "Click near a connection to delete it.")

    def on_canvas_click(self, event):
        """Handle clicks on the canvas for connection deletion."""

        if self.delete_connection_mode:
            result = self.detect_connection(event.x, event.y)
            if result:
                line, d1, d2, port1, port2 = result
                confirm = messagebox.askyesno("Delete Connection",
                                              f"Are you sure you want to delete the connection between {d1.device_type} "
                                              f"and {d2.device_type}?")
                if confirm:
                    self.delete_connection_between_devices(d1, d2)
            else:
                messagebox.showwarning("Delete Connection", "No connection found near the clicked area.")
            return

    def cancel_delete_mode(self):
        self.delete_connection_mode = False
        self.connection_delete_start = None
        messagebox.showinfo("Delete Mode", "Delete mode cancelled.")

    def delete_connection_between_devices(self, device1, device2):
        # Find the connection to delete
        connection_to_remove = None
        for line, d1, d2, port1, port2 in self.connections:
            if (d1 == device1 and d2 == device2) or (d1 == device2 and d2 == device1):
                connection_to_remove = (line, d1, d2, port1, port2)
                break

        if connection_to_remove:
            line, d1, d2, port1, port2 = connection_to_remove

            # Remove from canvas
            self.canvas.delete(line)

            # Remove from connections list
            self.connections.remove(connection_to_remove)

            # Remove from network graph
            self.network_graph.remove_edge(d1.id, d2.id)

            # Release ports
            d1.release_port(port1)
            d2.release_port(port2)

            messagebox.showinfo("Connection Deleted",
                                f"Deleted connection between {d1.device_type} and {d2.device_type}")
        else:
            messagebox.showwarning("Delete Connection", "No connection found between these devices.")

        # Reset delete mode
        self.delete_connection_mode = False
        self.connection_delete_start = None

    def on_device_click(self, device):
        """Override the device click method to handle delete modes."""
        if self.delete_connection_mode:
            if not self.connection_delete_start:
                self.connection_delete_start = device
                messagebox.showinfo("Delete Connection",
                                    f"Selected {device.device_type}. Now select the second device.")
            else:
                self.delete_connection(self.connection_delete_start, device)
                self.connection_delete_start = None
            return

        if self.delete_mode == "device":
            confirm = messagebox.askyesno("Delete Device",
                                          f"Are you sure you want to delete {device.device_type} (ID: {device.id})?")
            if confirm:
                self.remove_device(device)
                self.update_device_selection()
            return

        # Normal connection or drag logic
        if self.current_connection_type:
            self.start_connection(device)
        else:
            device.on_device_drag_start(event)

    def delete_connection(self, device1, device2):
        """Enhanced connection deletion logic."""
        connection_to_remove = None
        for line, d1, d2, port1, port2 in self.connections:
            if (d1 == device1 and d2 == device2) or (d1 == device2 and d2 == device1):
                connection_to_remove = (line, d1, d2, port1, port2)
                break

        if connection_to_remove:
            line, d1, d2, port1, port2 = connection_to_remove

            # Remove connection visuals
            self.canvas.delete(line)
            self.connections.remove(connection_to_remove)
            self.network_graph.remove_edge(d1.id, d2.id)

            # Free up ports
            d1.release_port(port1)
            d2.release_port(port2)

            messagebox.showinfo("Connection Deleted",
                                f"Deleted connection between {d1.device_type} and {d2.device_type}")
        else:
            messagebox.showwarning("Delete Connection", "No connection found between these devices.")

        # Exit delete mode
        self.delete_connection_mode = False
        self.connection_delete_start = None

    def remove_device(self, device):
            """Enhanced remove_device method to handle connections."""
            # Remove from canvas
            self.canvas.delete(device.shape_id)
            self.canvas.delete(device.text_id)

            # Remove all connections to this device
            connections_to_remove = [c for c in self.connections if device in (c[1], c[2])]
            for line, dev1, dev2, port1, port2 in connections_to_remove:
                self.canvas.delete(line)
                self.connections.remove((line, dev1, dev2, port1, port2))
                self.network_graph.remove_edge(dev1.id, dev2.id)

                # Free up the used ports
                if dev1 == device:
                    dev2.release_port(port2)
                else:
                    dev1.release_port(port1)

            # Remove from network graph
            if device.id in self.network_graph:
                self.network_graph.remove_node(device.id)

            # Remove from devices
            del self.devices[device.id]

    # Modify Device class to support new click handling

    def setup_device_config_tab(self, frame):
        # Device Selection
        ttk.Label(frame, text="Select Device:", font=('Helvetica', 10, 'bold')).pack(pady=(10, 5))
        self.device_selection = ttk.Combobox(frame, state="readonly")
        self.device_selection.pack(fill="x", padx=10, pady=5)
        self.device_selection.bind("<<ComboboxSelected>>", self.load_device_config)

        # Configuration Fields
        config_fields = [
            ("Device Type", "device_type"),
            ("MAC Address", "mac_address"),
            ("IP Address", "ip_address"),
            ("Subnet Mask", "subnet_mask"),
            ("Available Ports", "available_ports")
        ]

        self.config_entries = {}
        for label, attr in config_fields:
            field_frame = ttk.Frame(frame)
            field_frame.pack(fill="x", padx=10, pady=2)

            ttk.Label(field_frame, text=f"{label}:").pack(side="left")
            entry = ttk.Entry(field_frame, width=20)
            entry.pack(side="right", fill="x", expand=True)

            self.config_entries[attr] = entry

        # Save and Remove Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text="Save Config", command=self.save_device_config).pack(side="left", expand=True,
                                                                                           padx=5)
        ttk.Button(button_frame, text="Remove Device", command=self.remove_selected_device).pack(side="right",
                                                                                                 expand=True, padx=5)

        # Update device list when devices are added or removed
        self.update_device_selection()

    def update_device_selection(self):
        device_list = [f"{device.id}: {device.device_type}" for device in self.devices.values()]
        self.device_selection['values'] = device_list

        if device_list:
            self.device_selection.current(0)
            self.load_device_config(None)

    def load_device_config(self, event):
        if not self.devices:
            return

        # Get selected device
        selection = self.device_selection.get()
        device_id = int(selection.split(':')[0])
        device = self.devices[device_id]

        # Populate configuration fields
        self.config_entries['device_type'].config(state='normal')
        self.config_entries['device_type'].delete(0, tk.END)
        self.config_entries['device_type'].insert(0, device.device_type)
        self.config_entries['device_type'].config(state='readonly')

        self.config_entries['mac_address'].config(state='normal')
        self.config_entries['mac_address'].delete(0, tk.END)
        self.config_entries['mac_address'].insert(0, device.mac_address)
        self.config_entries['mac_address'].config(state='readonly')

        self.config_entries['ip_address'].delete(0, tk.END)
        self.config_entries['ip_address'].insert(0, device.ip_address)

        self.config_entries['subnet_mask'].delete(0, tk.END)
        self.config_entries['subnet_mask'].insert(0, device.subnet_mask)

        # Update available ports dynamically
        self.config_entries['available_ports'].config(state='normal')
        self.config_entries['available_ports'].delete(0, tk.END)
        self.config_entries['available_ports'].insert(0, str(device.available_ports))  # Reflect actual port list
        self.config_entries['available_ports'].config(state='readonly')

        # Store currently selected device for saving or removing
        self.selected_device = device

    def save_device_config(self):
        if not self.selected_device:
            messagebox.showwarning("Error", "No device selected")
            return

        ip_address = self.config_entries['ip_address'].get()
        subnet_mask = self.config_entries['subnet_mask'].get()

        if not (self.selected_device.validate_ip(ip_address) and
                self.selected_device.validate_ip(subnet_mask)):
            messagebox.showwarning("Invalid Input", "Enter valid IP and Subnet.")
            return

        self.selected_device.ip_address = ip_address
        self.selected_device.subnet_mask = subnet_mask

        messagebox.showinfo("Configuration Saved",
                            f"Updated {self.selected_device.device_type} (ID: {self.selected_device.id})\n"
                            f"IP: {ip_address}, Subnet: {subnet_mask}")

    def remove_selected_device(self):
        if not self.selected_device:
            messagebox.showwarning("Error", "No device selected")
            return

        # Confirm device removal
        confirm = messagebox.askyesno("Remove Device",
                                      f"Are you sure you want to remove {self.selected_device.device_type} (ID: {self.selected_device.id})?")
        if confirm:
            self.remove_device(self.selected_device)
            self.update_device_selection()

    def add_device(self, device_type):
        device = Device(device_type, self.canvas, self)
        self.devices[device.id] = device
        self.network_graph.add_node(device.id, type=device_type, mac=device.mac_address)

        # Update device selection and ping dropdowns
        self.update_device_selection()
        self.update_ping_dropdowns()

    def remove_device(self, device):
        # Remove from canvas
        self.canvas.delete(device.shape_id)
        self.canvas.delete(device.text_id)

        # Remove connections
        connections_to_remove = [c for c in self.connections if device in (c[1], c[2])]
        for line, dev1, dev2, port1, port2 in connections_to_remove:
            self.canvas.delete(line)
            self.connections.remove((line, dev1, dev2, port1, port2))
            self.network_graph.remove_edge(dev1.id, dev2.id)

            # Free up the used ports
            if dev1 == device:
                dev2.release_port(port2)
            else:
                dev1.release_port(port1)

        # Remove from network graph
        if device.id in self.network_graph:
            self.network_graph.remove_node(device.id)

        # Remove from devices
        del self.devices[device.id]

        # Update device selection and ping dropdowns
        self.update_device_selection()
        self.update_ping_dropdowns()

    def set_connection(self, connection_type):
        self.current_connection_type = connection_type
        self.connection_start_device = None
        messagebox.showinfo("Connection Type", f"Selected {connection_type}. Click devices to connect.")

    def deselect_connection(self):
        self.current_connection_type = None
        self.connection_start_device = None
        messagebox.showinfo("Connection", "Deselected wire. You can now drag devices.")

    def start_connection(self, device):
        if not self.current_connection_type:
            messagebox.showwarning("Connection Error", "Select a connection type first!")
            return

        if not self.connection_start_device:
            self.connection_start_device = device
            messagebox.showinfo("Connection", f"Selected {device.device_type}. Choose another device to connect.")
        else:
            if self.connection_start_device != device:
                self.connect_devices(self.connection_start_device, device)
                self.connection_start_device = None

    def connect_devices(self, device1, device2):
        if not device1.has_available_ports() or not device2.has_available_ports():
            messagebox.showwarning("Connection Error", "One or both devices have no available ports.")
            return

        port1 = device1.choose_port()
        port2 = device2.choose_port()
        if port1 is not None and port2 is not None:
            device1.use_port(port1)
            device2.use_port(port2)
            line = self.draw_connection(device1, device2)
            self.connections.append((line, device1, device2, port1, port2))
            self.network_graph.add_edge(device1.id, device2.id, type=self.current_connection_type)
        else:
            messagebox.showwarning("Connection Error", "Could not establish connection. Ports are unavailable.")

    def detect_connection(self, x, y):
        """Detect if a click is near any connection."""
        threshold = 10  # Maximum distance from the line to count as a click
        for line, d1, d2, port1, port2 in self.connections:
            x1, y1 = self.get_device_center(d1)
            x2, y2 = self.get_device_center(d2)

            # Calculate the distance from the point (x, y) to the line segment (x1, y1)-(x2, y2)
            if self.is_point_near_line(x, y, x1, y1, x2, y2, threshold):
                return line, d1, d2, port1, port2
        return None

    def is_point_near_line(self, px, py, x1, y1, x2, y2, threshold):
        """Check if a point (px, py) is within a threshold distance to a line segment."""
        # Calculate the distance using vector projection
        line_length_squared = (x2 - x1) ** 2 + (y2 - y1) ** 2
        if line_length_squared == 0:  # Line segment is a point
            return (px - x1) ** 2 + (py - y1) ** 2 <= threshold ** 2

        # Projection factor t
        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / line_length_squared))
        nearest_x = x1 + t * (x2 - x1)
        nearest_y = y1 + t * (y2 - y1)
        # Distance from the point to the nearest point on the line
        return (px - nearest_x) ** 2 + (py - nearest_y) ** 2 <= threshold ** 2
    def draw_connection(self, device1, device2):
        x1, y1 = self.get_device_center(device1)
        x2, y2 = self.get_device_center(device2)
        return self.canvas.create_line(x1, y1, x2, y2, fill="black", width=2)

    def update_connections(self):
        for line, device1, device2, _, _ in self.connections:
            x1, y1 = self.get_device_center(device1)
            x2, y2 = self.get_device_center(device2)
            self.canvas.coords(line, x1, y1, x2, y2)

    def get_device_center(self, device):
        coords = self.canvas.coords(device.shape_id)
        if len(coords) == 2:  # It's an image
            x1, y1 = coords
            x2, y2 = x1 + 50, y1 + 50
        else:  # It's a shape
            x1, y1, x2, y2 = coords
        return (x1 + x2) / 2, (y1 + y2) / 2

    def setup_pinging_tab(self, frame):
        # Title
        ttk.Label(frame, text="Ping and Packet Tool", font=("Helvetica", 12, "bold")).pack(pady=10)

        # Dropdown for Source Device
        ttk.Label(frame, text="Source Device:").pack(anchor="w", padx=10, pady=5)
        self.source_device_combobox = ttk.Combobox(frame, state="readonly")
        self.source_device_combobox.pack(fill="x", padx=10, pady=5)

        # Dropdown for Destination Device
        ttk.Label(frame, text="Destination Device:").pack(anchor="w", padx=10, pady=5)
        self.destination_device_combobox = ttk.Combobox(frame, state="readonly")
        self.destination_device_combobox.pack(fill="x", padx=10, pady=5)

        # Dropdown for Protocol Selection
        ttk.Label(frame, text="Protocol:").pack(anchor="w", padx=10, pady=5)
        self.protocol_combobox = ttk.Combobox(frame, state="readonly", values=["TCP", "UDP"])
        self.protocol_combobox.pack(fill="x", padx=10, pady=5)
        self.protocol_combobox.current(0)  # Default to TCP

        # Ping Button
        ping_button = ttk.Button(frame, text="Ping", command=self.ping_devices)
        ping_button.pack(pady=5)

        # Send Packet Button
        send_packet_button = ttk.Button(frame, text="Send Packet", command=self.send_packet_devices)
        send_packet_button.pack(pady=5)

        # Output Label
        self.ping_output_label = ttk.Label(frame, text="", wraplength=300, justify="left")
        self.ping_output_label.pack(fill="x", padx=10, pady=5)

        # Initialize the dropdowns
        self.update_ping_dropdowns()

    def send_packet_devices(self):
        source_device_name = self.source_device_combobox.get()
        destination_device_name = self.destination_device_combobox.get()
        protocol = self.protocol_combobox.get()

        if not source_device_name or not destination_device_name:
            self.ping_output_label.config(text="Error: Both Source and Destination Devices must be selected.")
            return

        # Resolve device names to IP addresses
        source_device = next((device for device in self.devices.values()
                              if f"{device.device_type} {device.id}" == source_device_name), None)
        destination_device = next((device for device in self.devices.values()
                                   if f"{device.device_type} {device.id}" == destination_device_name), None)

        if not source_device or not destination_device:
            self.ping_output_label.config(text="Error: Device not found.")
            return

        source_ip = source_device.ip_address
        destination_ip = destination_device.ip_address

        # Construct the send packet command
        command = f"SendPacket {source_ip} {destination_ip} {protocol}"
        try:
            # Use the existing send packet function
            self.execute_send_packet(command)
            self.ping_output_label.config(
                text=f"{protocol} packet from {source_device_name} to {destination_device_name} executed. Check the terminal for details."
            )
        except Exception as e:
            self.ping_output_label.config(text=f"Error: {str(e)}")

    def update_ping_dropdowns(self):
        """Update the device name options in the ping dropdown menus."""
        device_names = [f"{device.device_type} {device.id}" for device in self.devices.values()]

        # Update the source device dropdown
        self.source_device_combobox['values'] = device_names
        if device_names:
            self.source_device_combobox.current(0)  # Select the first device by default

        # Update the destination device dropdown
        self.destination_device_combobox['values'] = device_names
        if device_names:
            self.destination_device_combobox.current(0)  # Select the first device by default

    def ping_devices(self):
        source_device_name = self.source_device_combobox.get()
        destination_device_name = self.destination_device_combobox.get()

        if not source_device_name or not destination_device_name:
            self.ping_output_label.config(text="Error: Both Source and Destination Devices must be selected.")
            return

        # Resolve device names to IP addresses
        source_device = next((device for device in self.devices.values()
                              if f"{device.device_type} {device.id}" == source_device_name), None)
        destination_device = next((device for device in self.devices.values()
                                   if f"{device.device_type} {device.id}" == destination_device_name), None)

        if not source_device or not destination_device:
            self.ping_output_label.config(text="Error: Device not found.")
            return

        source_ip = source_device.ip_address
        destination_ip = destination_device.ip_address

        # Construct the ping command
        command = f"ping {source_ip} {destination_ip}"
        try:
            # Use the existing ping function
            self.execute_ping(command)
            self.ping_output_label.config(
                text=f"Ping from {source_device_name} to {destination_device_name} executed. Check the terminal for details."
            )
        except Exception as e:
            self.ping_output_label.config(text=f"Error: {str(e)}")


class Device:
    id_counter = 1  # Shared counter for unique IDs

    def __init__(self, device_type, canvas, simulator):
        self.device_type = device_type
        self.canvas = canvas
        self.simulator = simulator
        self.id = Device.id_counter
        Device.id_counter += 1
        self.icon = None
        # Isolated initialization of ports
        self.available_ports = self.initialize_ports(device_type)

        self.mac_address = self.generate_mac()
        self.ip_address = f"192.168.0.{self.id}"
        self.subnet_mask = "255.255.255.0"

        self.create_device()

        # Bind device creation events
        self.canvas.tag_bind(self.shape_id, "<B1-Motion>", self.on_device_drag)
        self.canvas.tag_bind(self.shape_id, "<Button-1>", self.on_device_click)
        self.canvas.tag_bind(self.text_id, "<B1-Motion>", self.on_device_drag)
        self.canvas.tag_bind(self.text_id, "<Button-1>", self.on_device_click)

    def initialize_ports(self, device_type):
        """Initialize the correct number of ports based on device type."""
        if device_type == "PC":
            return list(range(1, 2))  # PCs have 1 port
        elif device_type == "Router":
            return list(range(1, 7))  # Routers have 6 ports
        elif device_type == "Switch":
            return list(range(1, 9))  # Switches have 8 ports
        elif device_type == "Hub":
            return list(range(1, 5))  # Hubs have 4 ports
        else:
            return list(range(1, 2))  # Default to 1 port for unknown devices

    def create_device(self):
        x, y = 100 + random.randint(0, 300), 100 + random.randint(0, 300)

        # Construct the icon path based on device type
        icon_path = "C:\\Users\\poopy\\PycharmProjects\\pythonProject6\\.venv\\Images\\" + f"{self.device_type.lower()}.png"



        try:
            # Load and resize the icon image
            img = Image.open(icon_path).resize((50, 50), Image.Resampling.LANCZOS)

            self.icon = ImageTk.PhotoImage(img)
            self.shape_id = self.canvas.create_image(x, y, image=self.icon, anchor=tk.NW)
        except FileNotFoundError:
            # Fallback to a blue circle if image not found
            self.shape_id = self.canvas.create_oval(x, y, x + 50, y + 50, fill="blue", tags=f"device_{self.id}")

        # Add device text
        self.text_id = self.canvas.create_text(
            x + 25, y + 65,  # Adjusted position for text below the icon
            text=f"{self.device_type}\nPorts: {len(self.available_ports)}",
            fill="black"
        )

    def on_device_click(self, event):
        if self.simulator.current_connection_type:
            # If in connection mode, start connection process
            self.simulator.start_connection(self)
        else:
            # Store initial click position for dragging
            self.start_x = event.x
            self.start_y = event.y

    def on_device_drag_start(self, event):
        """Store initial click position for dragging"""
        self.start_x = event.x
        self.start_y = event.y

    def on_device_drag(self, event):
        # Move device and update its position
        dx = event.x - self.start_x
        dy = event.y - self.start_y

        self.canvas.move(self.shape_id, dx, dy)
        self.canvas.move(self.text_id, dx, dy)

        # Update starting position for next drag event
        self.start_x = event.x
        self.start_y = event.y

        # Update any connections to this device
        self.simulator.update_connections()

    def generate_mac(self):
        return ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))

    def validate_ip(self, ip):
        return re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) and all(0 <= int(part) <= 255 for part in ip.split("."))

    def has_available_ports(self):
        # Check if any ports are available
        return len(self.available_ports) > 0

    def choose_port(self):
        # Choose the first available port, or None if no ports are left
        return self.available_ports[0] if self.available_ports else None

    def use_port(self, port):
        # Mark the port as used
        if port in self.available_ports:
            self.available_ports.remove(port)

    def release_port(self, port):
        # Re-enable a port (if needed)
        if port not in self.available_ports:
            self.available_ports.append(port)




if __name__ == "__main__":
    root = tk.Tk()
    app = NetworkSimulator(root)
    root.mainloop()
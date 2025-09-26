# OctetLab 🐙

![OctetLab](https://img.shields.io/badge/OctetLab-IP%20Subnetting%20Tool-brightgreen)
![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-OctetLab%20Non--Commercial%201.0-lightgrey)

**OctetLab** is a Python desktop application for working with IP addressing and subnetting. Built with `tkinter`, it provides a simple, educational interface to explore networking concepts.

---

## ✨ Features

* **Subnet calculator** with support for VLSM and FLSM
* **Graphical visualization** of routers and connections
* **Export to Cisco Packet Tracer** (topology and CLI configurations)
* **Export results** to text files
* **Intuitive interface** with drag-and-drop elements and pan navigation
* **Full management** of routers, host groups, and connections
* **DNS support** in router configurations

---

## 🚀 Getting Started

### Run the Application

```bash
python OctetLab.py
```

---

## 🎯 Main Functionalities

### 1. Router Management

* Create routers with custom names
* Configure up to 4 host groups per router
* Graphical visualization with random colors
* Drag and drop routers on the canvas

### 2. Router Connections

* Establish point-to-point connections
* Display links as red lines
* Full management of connections (add/remove)

### 3. Subnetting Modes

* **VLSM** (Variable Length Subnet Mask): Variable masks per group
* **FLSM** (Fixed Length Subnet Mask): Fixed mask for all groups

### 4. Advanced Export

* **Cisco Topology**: Text file with devices and connections
* **Cisco CLI**: Ready-to-use configurations for routers and switches
* **TXT Results**: Complete subnet tables in text format

### 5. Interactive Visualization

* **Interactive canvas** with zoom and pan (middle button/mouse wheel)
* **Drag routers** with the mouse
* **Dynamic connections** that update automatically

---

## 🛠️ Export Functions

### Export Cisco Topology

* Generates a text file with:

  * Devices (routers, switches, PCs)
  * Interfaces and IP addresses
  * Connections between devices
  * Subnet masks in decimal and binary

### Export Cisco CLI

* Ready-to-use configurations for:

  * Routers (hostname, interfaces, DNS)
  * Switches (access mode)
  * PCs (IP, gateway, DNS)

### Export to TXT

* Formatted tables with:

  * Network summary
  * Complete details of each subnet

---

## 🔧 Dependencies

No additional installations required. Only standard Python libraries:

```python
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ipaddress
import random
import os
import math
```

---

## 👨‍💻 Author

**Mariano Oblitas** (*alias vr700*) – Development and maintenance

---

## 📄 License

![License](https://img.shields.io/badge/license-OctetLab%20Non--Commercial%201.0-lightgrey)

**OctetLab - License Agreement**
Author: Mariano Oblitas (alias *vr700*)
Language: Python
Libraries: `tkinter`, `ttk`, `ipaddress`, `math`, `random`
Year: 2025

Permission is hereby granted to anyone to view, use, study, and modify this software for **non-commercial purposes**, under the following conditions:

1. **Attribution Required**
   You must give clear and visible credit to the original author:
   *"Based on the work of Mariano Oblitas (alias vr700)"*

2. **Share-Alike (Copyleft)**
   If you distribute this software or any modified version of it, you must also make the source code available under the same or a compatible license.

3. **Non-Commercial Use Only**
   This software may not be used for commercial purposes, including but not limited to selling, sublicensing, or integrating it into proprietary or commercial products.
   For commercial use, contact the author to request a separate license.

4. **No Warranty**
   This software is provided *"as is"*, without any express or implied warranty. The author is not liable for any damage or loss resulting from its use.

📌 This license is inspired by the GNU General Public License v3, but includes an additional **non-commercial clause**.


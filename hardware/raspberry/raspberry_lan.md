# 树莓派网络配置指南

## 硬件连接方式

```
台式机 (192.168.10.x)
    ↓
USB Hub (网络适配器)
    ↓
网线
    ↓
树莓派 (192.168.100.x)
```

**特点**：
- 树莓派通过 USB 网络适配器连接到台式机
- 形成独立的 192.168.100.x 子网
- 与主网络 192.168.10.x 隔离

---

## 网络原理解释

### 为什么需要配置 eth0？

**问题现象**：
```bash
eth0      Link encap:Ethernet  HWaddr 6c:1f:f7:5a:0f:76  
          UP BROADCAST RUNNING MULTICAST  MTU:1500 Metric:1
          # ⚠️ 注意：没有 inet addr（没有 IP 地址）
```

**原因分析**：

1. **USB 网络接口的自动配置失败**
   - USB hub 网络接口（eth0）在系统启动时可能未被正确初始化
   - 网络管理器可能没有为 USB 接口分配 IP 地址
   - 与主网络接口（enp0s31f6）不同，USB 接口需要手动配置

2. **触发原因**：
   - USB hub 重新连接或拔插
   - 系统重启后网络配置丢失
   - 网络管理器配置改变
   - 系统更新导致网络配置失效

3. **为什么 ping 不通树莓派**：
   ```
   台式机 eth0 (无 IP) ←→ 树莓派 (192.168.100.74)
   
   没有 IP 地址 = 无法在 192.168.100.x 网段通信
   结果：ping 192.168.100.74 → 无法路由 → 超时
   ```

### IP 地址分配原理

**子网划分**：
```
主网络：192.168.10.0/24
  - 台式机：192.168.10.122
  - 网关：192.168.10.1
  - 范围：192.168.10.1 - 192.168.10.254

USB 子网：192.168.100.0/24
  - 台式机 eth0：192.168.100.1
  - 树莓派：192.168.100.74
  - 范围：192.168.100.1 - 192.168.100.254
```

**为什么用 192.168.100.1？**
- 避免与主网络冲突（主网络是 192.168.10.x）
- 192.168.100.1 作为网关/主机
- 树莓派 192.168.100.74 作为客户端
- 子网掩码 /24 表示 256 个地址空间

---

## 快速修复方案

### 方案 1：临时修复（当前会话有效）

```bash
# 给 eth0 配置 IP 地址
sudo ip addr add 192.168.100.1/24 dev eth0

# 验证配置
ifconfig eth0

# 测试连接
ping -c 4 192.168.100.74
```

**优点**：立即生效  
**缺点**：重启后失效

---

### 方案 2：永久修复 - 编辑 /etc/network/interfaces（推荐）

**适用系统**：Debian/Ubuntu（使用 ifupdown）

```bash
# 编辑网络配置文件
sudo nano /etc/network/interfaces
```

**添加以下内容**：
```
# USB 网络接口配置
auto eth0
iface eth0 inet static
    address 192.168.100.1
    netmask 255.255.255.0
    # 可选：添加网关（如果需要树莓派访问外网）
    # gateway 192.168.100.254
    # 可选：添加 DNS
    # dns-nameservers 8.8.8.8 8.8.4.4
```

**应用配置**：
```bash
# 重启网络服务
sudo systemctl restart networking

# 或使用旧命令
sudo /etc/init.d/networking restart

# 验证
ifconfig eth0
ping 192.168.100.74
```

**优点**：永久生效，重启后自动配置  
**缺点**：需要编辑系统文件

---

### 方案 3：使用 netplan（现代 Ubuntu 18.04+）

**适用系统**：Ubuntu 18.04 及以上

```bash
# 编辑 netplan 配置
sudo nano /etc/netplan/01-netcfg.yaml
```

**添加以下内容**：
```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: no
      addresses:
        - 192.168.100.1/24
      # 可选：网关和 DNS
      # gateway4: 192.168.100.254
      # nameservers:
      #   addresses: [8.8.8.8, 8.8.4.4]
```

**应用配置**：
```bash
# 验证语法
sudo netplan validate

# 应用配置
sudo netplan apply

# 验证
ifconfig eth0
ping 192.168.100.74
```

**优点**：现代配置方式，更灵活  
**缺点**：仅适用于新版 Ubuntu

---

### 方案 4：自动启动脚本（开机自动配置）

如果上述方案都不生效，创建启动脚本：

```bash
# 创建脚本
sudo nano /etc/init.d/eth0-config
```

**脚本内容**：
```bash
#!/bin/bash
### BEGIN INIT INFO
# Provides:          eth0-config
# Required-Start:    $network
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:
# Description:       Configure eth0 for Raspberry Pi USB connection
### END INIT INFO

# 等待网络接口就绪
sleep 2

# 配置 eth0
ip link set eth0 up 2>/dev/null
ip addr add 192.168.100.1/24 dev eth0 2>/dev/null

exit 0
```

**启用脚本**：
```bash
# 添加执行权限
sudo chmod +x /etc/init.d/eth0-config

# 注册为启动脚本
sudo update-rc.d eth0-config defaults

# 验证
sudo systemctl status eth0-config
```

---

## 诊断步骤

### 快速诊断脚本

创建 `check_rpi.sh`：
```bash
#!/bin/bash
echo "=== 树莓派连接诊断 ==="
echo ""

# 1. 检查 eth0 状态
echo "[1] 检查 eth0 接口..."
if ip link show eth0 | grep -q "UP"; then
    echo "    ✓ eth0 已启用"
else
    echo "    ✗ eth0 未启用，尝试启用..."
    sudo ip link set eth0 up
fi

# 2. 检查 IP 地址
echo "[2] 检查 IP 地址..."
if ip addr show eth0 | grep -q "inet "; then
    echo "    ✓ eth0 已配置 IP"
    ip addr show eth0 | grep "inet "
else
    echo "    ✗ eth0 没有 IP 地址，正在配置..."
    sudo ip addr add 192.168.100.1/24 dev eth0
fi

# 3. 尝试 ping 树莓派
echo "[3] 测试连接..."
if ping -c 1 -W 2 192.168.100.74 &>/dev/null; then
    echo "    ✓ 树莓派连接正常"
else
    echo "    ✗ 无法 ping 通树莓派"
fi

# 4. 显示 ARP 表
echo "[4] ARP 表:"
arp -a | grep 192.168.100

# 5. 显示路由表
echo "[5] 路由表:"
route -n | grep 192.168.100
```

**使用**：
```bash
chmod +x check_rpi.sh
./check_rpi.sh
```

### 完整诊断命令

```bash
# 1. 检查所有网络接口
ifconfig

# 2. 检查 eth0 详细信息
ip addr show eth0
ip link show eth0

# 3. 检查 ARP 表
arp -a

# 4. 检查路由表
route -n
ip route show

# 5. 检查 USB 设备
lsusb

# 6. 查看内核日志
dmesg | tail -20

# 7. 尝试 ARP 扫描
sudo arp-scan 192.168.100.0/24

# 8. 尝试 SSH 连接
ssh pi@192.168.100.74
```

---

## 常见问题

### Q1: 重新插拔 USB 后能否自动恢复？

**A**: 不能自动恢复（除非配置了启动脚本）

**解决方案**：
- 使用方案 2 或 3（永久配置）
- 或使用方案 4（启动脚本）

### Q2: 为什么 ping 显示 `<incomplete>`？

**A**: ARP 解析失败，通常是因为：
- eth0 没有 IP 地址
- 网络接口未启用
- 树莓派离线

**解决**：
```bash
sudo ip addr add 192.168.100.1/24 dev eth0
sudo ip link set eth0 up
```

### Q3: 如何验证树莓派是否在线？

**A**: 多种方法：
```bash
# 方法 1: ping
ping 192.168.100.74

# 方法 2: ARP 扫描
sudo arp-scan 192.168.100.0/24

# 方法 3: SSH 连接
ssh pi@192.168.100.74

# 方法 4: 查看 ARP 表
arp -a | grep 192.168.100
```

### Q4: 如何在树莓派上验证网络配置？

**A**: SSH 到树莓派后：
```bash
# 查看 IP 地址
ifconfig

# 测试与台式机的连接
ping 192.168.100.1

# 查看路由表
route -n
```

---

## 推荐配置流程

### 首次配置

1. **检查硬件连接**
   ```bash
   lsusb  # 确认 USB 网络适配器被识别
   ```

2. **启用 eth0 接口**
   ```bash
   sudo ip link set eth0 up
   ```

3. **配置 IP 地址**
   ```bash
   sudo ip addr add 192.168.100.1/24 dev eth0
   ```

4. **测试连接**
   ```bash
   ping 192.168.100.74
   ```

5. **永久配置**（选择方案 2 或 3）

### 日常使用

- 如果配置了永久方案，重启后自动生效
- 如果 ping 不通，运行诊断脚本 `check_rpi.sh`
- 如果仍未解决，检查 USB hub 是否正常工作

---

## 参考资源

- [Linux 网络配置](https://wiki.debian.org/NetworkConfiguration)
- [netplan 文档](https://netplan.io/)
- [IP 地址和子网掩码](https://en.wikipedia.org/wiki/Subnetwork)
- [ARP 协议](https://en.wikipedia.org/wiki/Address_Resolution_Protocol)

---

**最后更新**：2026-05-08  
**适用系统**：Debian/Ubuntu Linux  
**树莓派型号**：Raspberry Pi 3B+/4B

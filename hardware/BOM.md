# Reachy Mini 辦公室助手 — 硬體 BOM 採購清單

> 日期：2026-02-12
> 總預算：約 NT$ 11,260
> 底盤方式：3D 列印（Creality K1C, 300mm 圓形底盤）

---

## 採購清單

| # | 零件 | 規格 | 數量 | 單價 (NT$) | 小計 (NT$) | 蝦皮搜尋 |
|---|------|------|------|-----------|-----------|---------|
| 1 | JGB37-520 馬達 | 12V 直流減速，含霍爾編碼器 | 2 | $350 | $700 | [搜尋](https://shopee.tw/search?keyword=JGB37-520%20%E7%B7%A8%E7%A2%BC%E5%99%A8%20%E9%A6%AC%E9%81%94%2012V) |
| 2 | 橡膠輪 | 80mm，D軸 6mm | 2 | $150 | $300 | [搜尋](https://shopee.tw/search?keyword=80mm%20%E6%A9%A1%E8%86%A0%E8%BC%AA%20D%E8%BB%B8%20%E6%A9%9F%E5%99%A8%E4%BA%BA) |
| 3 | 金屬萬向輪 | 1.5 吋 | 1 | $50 | $50 | [搜尋](https://shopee.tw/search?keyword=%E8%90%AC%E5%90%91%E8%BC%AA%20%E9%87%91%E5%B1%AC%201.5%E5%90%8B) |
| 4 | ESP32-S3 DevKitC | N8R2 或 N16R8 | 1 | $350 | $350 | [搜尋](https://shopee.tw/search?keyword=ESP32-S3-DevKitC) |
| 5 | BTS7960 馬達驅動板 | 43A 雙 H-Bridge | 2 | $160 | $320 | [搜尋](https://shopee.tw/search?keyword=BTS7960%2043A%20%E9%A6%AC%E9%81%94%E9%A9%85%E5%8B%95) |
| 6 | RPLIDAR C1 | DTOF 2D LiDAR，12m，5000次/秒 | 1 | $3,180 | $3,180 | [搜尋](https://shopee.tw/search?keyword=RPLIDAR%20C1) |
| 7 | HC-SR04 超音波 | 2-400cm 測距 | 4 | $40 | $160 | [搜尋](https://shopee.tw/search?keyword=HC-SR04%20%E8%B6%85%E9%9F%B3%E6%B3%A2) |
| 8 | BNO055 IMU | GY-BNO055 九軸，內建融合演算法 | 1 | $450 | $450 | [搜尋](https://shopee.tw/search?keyword=GY-BNO055%20IMU) |
| 9 | 24V LiFePO4 電池 | 10Ah (~240Wh) | 1 | $4,500 | $4,500 | [搜尋](https://shopee.tw/search?keyword=24V%20%E7%A3%B7%E9%85%B8%E9%90%B5%E9%8B%B0%E9%9B%BB%E6%B1%A0%2010Ah) |
| 10 | DC-DC 降壓模組 | 24V→12V 5A（Mac Mini 供電） | 1 | $350 | $350 | [搜尋](https://shopee.tw/search?keyword=DC-DC%20%E9%99%8D%E5%A3%93%2024V%2012V%205A) |
| 11 | DC-DC 降壓模組 | 24V→7.4V 3A（Reachy Mini 供電） | 1 | $80 | $80 | [搜尋](https://shopee.tw/search?keyword=DC-DC%20%E9%99%8D%E5%A3%93%207.4V) |
| 12 | DC-DC 降壓模組 | 24V→5V 3A（ESP32+感測器） | 1 | $35 | $35 | [搜尋](https://shopee.tw/search?keyword=LM2596%20%E9%99%8D%E5%A3%93%E6%A8%A1%E7%B5%84) |
| 13 | 8S BMS 保護板 | 24V LiFePO4 用 | 1 | $300 | $300 | [搜尋](https://shopee.tw/search?keyword=8S%20BMS%20%E7%A3%B7%E9%85%B8%E9%90%B5%E9%8B%B0) |
| 14 | IR 紅外線避障模組 | 懸崖偵測用，朝下安裝 | 3 | $25 | $75 | [搜尋](https://shopee.tw/search?keyword=%E7%B4%85%E5%A4%96%E7%B7%9A%E9%81%BF%E9%9A%9C%E6%A8%A1%E7%B5%84) |
| 15 | 微動開關 | KW11 碰撞感測用 | 4 | $15 | $60 | [搜尋](https://shopee.tw/search?keyword=%E5%BE%AE%E5%8B%95%E9%96%8B%E9%97%9C%20KW11) |
| 16 | 3D 列印耗材 | PETG 1kg（底盤+支架） | 1 | $150 | $150 | [搜尋](https://shopee.tw/search?keyword=PETG%201kg%20%E7%B7%9A%E6%9D%90%201.75mm) |
| 17 | 螺絲/銅柱/線材 | M3/M4 螺絲包、杜邦線、XT60 接頭 | 1 | $200 | $200 | [搜尋](https://shopee.tw/search?keyword=M3%20%E8%9E%BA%E7%B5%B2%20%E9%8A%85%E6%9F%B1%20%E5%A5%97%E8%A3%9D) |
| | | | | **總計** | **NT$ 11,260** | |

---

## 省錢替代方案

| 替換 | 原價 | 替代價 | 省下 |
|------|------|--------|------|
| BNO055 → MPU6050 (GY-521) | $450 | $129 | $321 |
| RPLIDAR C1 → RPLIDAR A1 | $3,180 | $2,900 | $280 |
| 24V 電池改用 2 組 12V/5Ah 串聯 | $4,500 | $3,200 | $1,300 |
| **最低版本總計** | | | **NT$ 9,359** |

---

## 電源架構

```
24V LiFePO4 電池 (10Ah, ~240Wh)
  │
  ├─ [直接 24V] ──→ BTS7960 × 2 ──→ JGB37-520 馬達 × 2
  │
  ├─ [24V→12V DC-DC 5A] ──→ Mac Mini M4（典型 12-15W）
  │
  ├─ [24V→7.4V DC-DC 3A] ──→ Reachy Mini Lite 伺服馬達
  │
  └─ [24V→5V DC-DC 3A] ──→ ESP32-S3 + HC-SR04×4 + BNO055 + RPLIDAR C1
```

預估續航：4+ 小時（典型辦公室運作）

---

## 通訊架構

```
Mac Mini M4
  │
  ├── USB ──→ Reachy Mini Lite（上半身 + 相機 + 喇叭）
  │
  ├── USB Serial (115200 baud) ──→ ESP32-S3（底盤控制器）
  │     ├── BTS7960 #1 ──→ 左馬達（PWM + 編碼器回讀）
  │     ├── BTS7960 #2 ──→ 右馬達（PWM + 編碼器回讀）
  │     ├── BNO055 ──→ IMU（I2C）
  │     ├── HC-SR04 × 4 ──→ 超音波避障（GPIO）
  │     ├── IR 模組 × 3 ──→ 懸崖偵測（GPIO）
  │     ├── 微動開關 × 4 ──→ 碰撞偵測（GPIO）
  │     └── ADC ──→ 電池電壓監測
  │
  └── USB ──→ RPLIDAR C1（直接連 Mac，Python SDK 處理點雲）
```

JSON Serial 通訊協定（沿用現有 SerialChassis）：
```json
Mac → ESP32: {"cmd":"vel","l":0.5,"a":0.1}
ESP32 → Mac: {"x":1.2,"y":3.4,"h":1.57,"ok":true}
```

---

## 3D 列印零件

印表機：Creality K1C (355×355×480mm)
材料：PETG（耐衝擊、耐熱）

| 零件 | 檔案 | 預估列印時間 |
|------|------|------------|
| 底板（300mm 圓形） | `chassis.scad` → `RENDER_BASE_PLATE` | 8-12 小時 |
| 馬達固定座 × 2 | `chassis.scad` → `RENDER_MOTOR_MOUNT` | 1-2 小時 |
| 第二層板（Mac Mini） | `chassis.scad` → `RENDER_SECOND_LAYER` | 5-8 小時 |
| LiDAR 頂部支架 | `chassis.scad` → `RENDER_LIDAR_MOUNT` | 2-3 小時 |

OpenSCAD 檔案位置：`hardware/chassis.scad`

---

## 採購優先順序（建議）

### 第一批（先驗證基本移動）
- [ ] JGB37-520 馬達 × 2
- [ ] 80mm 橡膠輪 × 2
- [ ] 萬向輪 × 1
- [ ] ESP32-S3 DevKitC
- [ ] BTS7960 × 2
- [ ] DC-DC 24V→5V
- [ ] 螺絲/線材
- [ ] 3D 列印耗材
- 小計：~NT$ 1,955

### 第二批（加入感測器和供電）
- [ ] RPLIDAR C1
- [ ] HC-SR04 × 4
- [ ] BNO055 IMU
- [ ] IR 避障模組 × 3
- [ ] 微動開關 × 4
- 小計：~NT$ 3,925

### 第三批（完整供電系統）
- [ ] 24V LiFePO4 電池
- [ ] 8S BMS
- [ ] DC-DC 24V→12V
- [ ] DC-DC 24V→7.4V
- 小計：~NT$ 5,230

---

## 參考資料

- 通訊協定詳細設計：見研究報告（通訊工程師）
- 感測器規格比較：見 `sensor_and_power_research.md`
- 3D 列印底盤參考設計：
  - [Custom 2WD Robot (Thingiverse)](https://www.thingiverse.com/thing:6771205)
  - [3D-Printed-ROS-SLAM-Robot (GitHub)](https://github.com/pliam1105/3D-Printed-ROS-SLAM-Robot)
  - [Linorobot2 ROS2 框架 (GitHub)](https://github.com/linorobot/linorobot2)

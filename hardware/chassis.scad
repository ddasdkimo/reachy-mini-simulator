// ═══════════════════════════════════════════════════════════════
// Reachy Mini Office Assistant — 圓形底盤 v1.0
// 適用印表機：Creality K1C (355x355x480mm)
// 馬達：JGB37-520 12V 編碼器馬達 × 2
// 輪子：80mm 橡膠輪（D軸 6mm）
// 萬向輪：1.5 吋金屬萬向輪
// ═══════════════════════════════════════════════════════════════

// ── 可調參數 ──────────────────────────────────────────────────
// 修改這些數值來調整底盤設計

// 底盤
base_diameter     = 300;   // 底盤直徑 (mm)
base_thickness    = 4;     // 底板厚度 (mm)
lip_height        = 8;     // 邊緣擋牆高度 (mm)
lip_thickness     = 3;     // 邊緣擋牆厚度 (mm)

// JGB37-520 馬達
motor_body_d      = 37;    // 馬達本體直徑 (mm)
motor_body_len    = 25;    // 馬達齒輪箱長度 (mm)
motor_shaft_d     = 6;     // 輸出軸直徑 (mm)
motor_mount_holes = 31;    // 馬達面板 M3 螺絲孔距 (mm)
motor_m3_d        = 3.4;   // M3 通孔直徑 (mm)

// 輪子
wheel_d           = 80;    // 輪子直徑 (mm)
wheel_w           = 26;    // 輪子寬度 (mm)

// 馬達位置（從中心到馬達軸的距離）
motor_y_offset    = 110;   // 馬達前後偏移（正 = 後方）
motor_x_spacing   = 180;   // 兩馬達間距（軸到軸）

// 萬向輪
caster_mount_d    = 25;    // 萬向輪安裝孔距 (mm)
caster_hole_d     = 4.5;   // 萬向輪 M4 螺絲孔 (mm)
caster_y_offset   = -110;  // 萬向輪位置（負 = 前方）

// 銅柱支撐（連接多層用）
standoff_d        = 4.5;   // M4 支撐柱通孔 (mm)
standoff_ring_r   = 120;   // 支撐柱圓環半徑 (mm)
standoff_count    = 6;     // 支撐柱數量

// 線材通孔
wire_hole_d       = 15;    // 走線孔直徑 (mm)

// Mac Mini M4 尺寸（參考用）
mac_mini_w        = 147;   // 寬 (mm)
mac_mini_d        = 147;   // 深 (mm)

// RPLIDAR C1 安裝
lidar_base_d      = 72;    // LiDAR 底座直徑 (mm)
lidar_mount_holes = 62;    // LiDAR M2.5 螺絲孔距 (mm)

// 電池區域
battery_w         = 120;   // 電池寬度預留 (mm)
battery_d         = 80;    // 電池深度預留 (mm)

// ── 選擇要產生的零件 ─────────────────────────────────────────
// 設為 true 來產生該零件，一次只開一個來匯出 STL

RENDER_BASE_PLATE    = true;   // 底板（主底盤）
RENDER_MOTOR_MOUNT   = false;  // 馬達固定座 × 2
RENDER_SECOND_LAYER  = false;  // 第二層板（放 Mac Mini）
RENDER_LIDAR_MOUNT   = false;  // LiDAR 頂部支架
RENDER_ALL_ASSEMBLY  = false;  // 全部組裝預覽（不要用這個匯出）

// ── 顏色定義 ──────────────────────────────────────────────────
color_base   = [0.2, 0.2, 0.2];
color_mount  = [0.8, 0.4, 0.1];
color_layer2 = [0.3, 0.3, 0.6];
color_lidar  = [0.1, 0.6, 0.3];

// ═══════════════════════════════════════════════════════════════
// 模組定義
// ═══════════════════════════════════════════════════════════════

// ── 底板（主底盤）────────────────────────────────────────────
module base_plate() {
    difference() {
        union() {
            // 主底板
            cylinder(d=base_diameter, h=base_thickness, $fn=120);

            // 邊緣擋牆
            difference() {
                cylinder(d=base_diameter, h=base_thickness + lip_height, $fn=120);
                translate([0, 0, -1])
                    cylinder(d=base_diameter - lip_thickness*2,
                             h=base_thickness + lip_height + 2, $fn=120);
                // 底板以下挖空
                translate([0, 0, -1])
                    cylinder(d=base_diameter + 2, h=base_thickness + 1, $fn=120);
            }

            // 馬達安裝區加強肋
            for (side = [-1, 1]) {
                translate([side * motor_x_spacing/2, motor_y_offset, 0])
                    cylinder(d=motor_body_d + 16, h=base_thickness + 3, $fn=60);
            }
        }

        // ── 馬達軸孔 ──
        for (side = [-1, 1]) {
            translate([side * motor_x_spacing/2, motor_y_offset, -1]) {
                // 馬達本體穿孔（讓軸伸出底板下方）
                cylinder(d=motor_shaft_d + 4, h=base_thickness + 10, $fn=30);

                // 馬達 M3 安裝螺絲孔（4 孔，十字排列）
                for (angle = [0, 90, 180, 270]) {
                    rotate([0, 0, angle])
                        translate([motor_mount_holes/2, 0, 0])
                            cylinder(d=motor_m3_d, h=base_thickness + 10, $fn=20);
                }
            }
        }

        // ── 馬達本體凹槽（底板上方，放馬達）──
        for (side = [-1, 1]) {
            translate([side * motor_x_spacing/2, motor_y_offset, base_thickness - 0.5])
                cylinder(d=motor_body_d + 1, h=20, $fn=60);
        }

        // ── 輪子開口（讓輪子突出底盤邊緣）──
        for (side = [-1, 1]) {
            translate([side * motor_x_spacing/2, motor_y_offset, -1])
                cube([wheel_w + 4, wheel_d + 10, base_thickness + lip_height + 5],
                     center=true);
        }

        // ── 萬向輪安裝孔 ──
        translate([0, caster_y_offset, -1]) {
            // 中心孔
            cylinder(d=12, h=base_thickness + 5, $fn=30);
            // 4 個 M4 螺絲孔
            for (angle = [0, 90, 180, 270]) {
                rotate([0, 0, angle + 45])
                    translate([caster_mount_d/2, 0, 0])
                        cylinder(d=caster_hole_d, h=base_thickness + 5, $fn=20);
            }
        }

        // ── 銅柱支撐孔（M4）──
        for (i = [0:standoff_count-1]) {
            angle = i * 360 / standoff_count + 30;
            translate([standoff_ring_r * cos(angle),
                       standoff_ring_r * sin(angle), -1])
                cylinder(d=standoff_d, h=base_thickness + lip_height + 5, $fn=20);
        }

        // ── 走線孔 ──
        // 中央走線孔
        translate([0, 0, -1])
            cylinder(d=wire_hole_d, h=base_thickness + 5, $fn=30);

        // 前方走線孔（感測器線）
        translate([0, -70, -1])
            cylinder(d=wire_hole_d, h=base_thickness + 5, $fn=30);

        // 後方走線孔（馬達線）
        translate([0, 70, -1])
            cylinder(d=wire_hole_d, h=base_thickness + 5, $fn=30);

        // 左右走線孔
        for (side = [-1, 1]) {
            translate([side * 60, 0, -1])
                cylinder(d=wire_hole_d, h=base_thickness + 5, $fn=30);
        }

        // ── 電池固定孔（M3 × 4）──
        for (dx = [-battery_w/2 + 10, battery_w/2 - 10]) {
            for (dy = [-battery_d/2 + 10, battery_d/2 - 10]) {
                translate([dx, dy - 20, -1])
                    cylinder(d=motor_m3_d, h=base_thickness + 5, $fn=20);
            }
        }

        // ── ESP32 安裝孔（M2.5 × 4）──
        translate([60, -40, 0]) {
            for (dx = [0, 52]) {
                for (dy = [0, 28]) {
                    translate([dx - 26, dy - 14, -1])
                        cylinder(d=2.8, h=base_thickness + 5, $fn=20);
                }
            }
        }

        // ── BTS7960 安裝孔（M3 × 4）× 2 ──
        for (side = [-1, 1]) {
            translate([side * 55, 50, 0]) {
                for (dx = [-20, 20]) {
                    for (dy = [-15, 15]) {
                        translate([dx, dy, -1])
                            cylinder(d=motor_m3_d, h=base_thickness + 5, $fn=20);
                    }
                }
            }
        }

        // ── 減重孔（可選）──
        for (angle = [60, 120, 240, 300]) {
            translate([85 * cos(angle), 85 * sin(angle), -1])
                cylinder(d=25, h=base_thickness + 5, $fn=30);
        }
    }

    // ── 標記文字 ──
    translate([0, base_diameter/2 - 25, base_thickness])
        linear_extrude(0.6)
            text("REACHY MINI", size=8, halign="center", font="Liberation Sans:style=Bold");

    translate([0, -(base_diameter/2 - 25), base_thickness])
        linear_extrude(0.6)
            text("FRONT", size=6, halign="center", font="Liberation Sans");
}


// ── 馬達固定座（L型支架）────────────────────────────────────
module motor_mount() {
    mount_wall   = 4;
    mount_height = motor_body_d/2 + 8;
    mount_width  = motor_body_d + 12;
    mount_depth  = motor_body_len + 8;

    difference() {
        union() {
            // 底部安裝面
            cube([mount_width, mount_depth, mount_wall]);

            // 垂直夾持壁
            translate([0, 0, 0])
                cube([mount_wall, mount_depth, mount_height]);
            translate([mount_width - mount_wall, 0, 0])
                cube([mount_wall, mount_depth, mount_height]);

            // 加強肋
            translate([0, mount_depth - mount_wall, 0])
                cube([mount_width, mount_wall, mount_height * 0.6]);
        }

        // 馬達本體凹槽（半圓形）
        translate([mount_width/2, mount_depth/2 - 2, mount_height])
            rotate([0, 0, 0])
                cylinder(d=motor_body_d + 0.5, h=mount_height + 1, $fn=60, center=true);

        // 底部 M3 安裝孔（固定到底板）
        for (dx = [-mount_width/2 + 8, mount_width/2 - 8]) {
            for (dy = [8, mount_depth - 8]) {
                translate([mount_width/2 + dx, dy, -1])
                    cylinder(d=motor_m3_d, h=mount_wall + 5, $fn=20);
            }
        }

        // 馬達軸穿孔
        translate([mount_width/2, -1, mount_height - motor_body_d/2 - 2])
            rotate([-90, 0, 0])
                cylinder(d=motor_shaft_d + 4, h=mount_depth + 5, $fn=30);

        // 側面鎖緊螺絲孔（M3，從側面穿過夾住馬達）
        translate([-1, mount_depth/2 - 2, mount_height - motor_body_d/2 - 2])
            rotate([0, 90, 0])
                cylinder(d=motor_m3_d, h=mount_width + 5, $fn=20);
    }
}


// ── 第二層板（Mac Mini + 電子元件）──────────────────────────
module second_layer() {
    layer_thickness = 3;

    difference() {
        cylinder(d=base_diameter - 20, h=layer_thickness, $fn=120);

        // 銅柱孔（對應底板）
        for (i = [0:standoff_count-1]) {
            angle = i * 360 / standoff_count + 30;
            translate([standoff_ring_r * cos(angle),
                       standoff_ring_r * sin(angle), -1])
                cylinder(d=standoff_d, h=layer_thickness + 5, $fn=20);
        }

        // Mac Mini 安裝區域（散熱通風孔）
        translate([0, -10, -1]) {
            // Mac Mini 輪廓標記槽
            difference() {
                cube([mac_mini_w + 2, mac_mini_d + 2, layer_thickness + 5], center=true);
                cube([mac_mini_w - 4, mac_mini_d - 4, layer_thickness + 5], center=true);
            }

            // Mac Mini 固定孔（M3 × 4，角落）
            for (dx = [-mac_mini_w/2 + 10, mac_mini_w/2 - 10]) {
                for (dy = [-mac_mini_d/2 + 10, mac_mini_d/2 - 10]) {
                    translate([dx, dy, 0])
                        cylinder(d=motor_m3_d, h=layer_thickness + 5, $fn=20);
                }
            }

            // 散熱孔陣列
            for (dx = [-50 : 15 : 50]) {
                for (dy = [-50 : 15 : 50]) {
                    if (sqrt(dx*dx + dy*dy) < 55) {
                        translate([dx, dy, 0])
                            cylinder(d=8, h=layer_thickness + 5, $fn=20);
                    }
                }
            }
        }

        // 走線大孔
        translate([0, 60, -1])
            cylinder(d=30, h=layer_thickness + 5, $fn=30);
        translate([0, -70, -1])
            cylinder(d=30, h=layer_thickness + 5, $fn=30);

        // 減重孔
        for (angle = [0, 72, 144, 216, 288]) {
            translate([110 * cos(angle), 110 * sin(angle), -1])
                cylinder(d=30, h=layer_thickness + 5, $fn=30);
        }
    }
}


// ── LiDAR 頂部支架 ──────────────────────────────────────────
module lidar_mount() {
    pole_d     = 12;
    pole_h     = 80;   // 從第二層到 LiDAR 的高度
    plate_d    = 90;
    plate_h    = 3;

    // 中央支柱
    cylinder(d=pole_d, h=pole_h, $fn=30);

    // 頂部平台
    translate([0, 0, pole_h]) {
        difference() {
            cylinder(d=plate_d, h=plate_h, $fn=60);

            // LiDAR M2.5 安裝孔
            for (angle = [0, 90, 180, 270]) {
                rotate([0, 0, angle])
                    translate([lidar_mount_holes/2, 0, -1])
                        cylinder(d=2.8, h=plate_h + 5, $fn=20);
            }

            // 線材穿孔
            translate([0, 0, -1])
                cylinder(d=pole_d - 2, h=plate_h + 5, $fn=30);
        }
    }

    // 底部固定法蘭
    difference() {
        cylinder(d=40, h=4, $fn=30);
        // M4 固定孔
        for (angle = [0, 120, 240]) {
            rotate([0, 0, angle])
                translate([14, 0, -1])
                    cylinder(d=standoff_d, h=10, $fn=20);
        }
    }
}


// ═══════════════════════════════════════════════════════════════
// 渲染控制
// ═══════════════════════════════════════════════════════════════

if (RENDER_ALL_ASSEMBLY) {
    // 組裝預覽
    color(color_base) base_plate();

    // 馬達固定座 × 2
    color(color_mount) {
        translate([-motor_x_spacing/2 - 25, motor_y_offset - 16, base_thickness])
            motor_mount();
        translate([motor_x_spacing/2 - 25, motor_y_offset - 16, base_thickness])
            mirror([1, 0, 0]) motor_mount();
    }

    // 第二層（銅柱高度 40mm）
    color(color_layer2, 0.6)
        translate([0, 0, base_thickness + lip_height + 40])
            second_layer();

    // LiDAR 支架
    color(color_lidar, 0.8)
        translate([0, 0, base_thickness + lip_height + 40 + 3])
            lidar_mount();

} else {
    if (RENDER_BASE_PLATE)   color(color_base)  base_plate();
    if (RENDER_MOTOR_MOUNT)  color(color_mount) motor_mount();
    if (RENDER_SECOND_LAYER) color(color_layer2) second_layer();
    if (RENDER_LIDAR_MOUNT)  color(color_lidar) lidar_mount();
}

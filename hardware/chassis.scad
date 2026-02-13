// ═══════════════════════════════════════════════════════════════
// Reachy Mini Office Assistant — 圓形底盤 v3.0（可組裝四片分割版）
// 適用印表機：220×220×250mm（或更大）
// 設計直徑：300mm → 分割成 4 片，每片 ~150×150mm
// 馬達：JGB37-520 12V 編碼器馬達 × 2
// 輪子：80mm 橡膠輪（D軸 6mm）
// 萬向輪：1.5 吋金屬萬向輪
// ═══════════════════════════════════════════════════════════════
//
// ── 組裝說明 ──────────────────────────────────────────────────
//
// 接合方式：拼圖榫互鎖 + M4 夾板固定
//
// 需要的五金：
//   M4×20mm 螺栓 × 12
//   M4 螺帽 × 12
//   M4 墊圈 × 24（選配）
//
// 列印件：
//   base_q1~q4（底板四片，有拼圖榫）
//   layer2_q1~q4（第二層四片）
//   motor_mount × 2
//   lidar_mount × 1
//   joint_bracket × 4（直線夾板）
//   center_bracket × 1（十字中心夾板）
//
// 組裝步驟：
//   1. 將 Q3（左前）放在桌上
//   2. 將 Q4（右前）從右方推入，X=0 分割線的榫互相卡合
//   3. 將 Q2（左後）從上方推入，Y=0 分割線的榫與 Q3 卡合
//   4. 將 Q1（右後）推入，完成四片拼合
//   5. 翻面，放上 4 個 joint_bracket 跨在分割線上
//   6. 放上 1 個 center_bracket 在中心十字處
//   7. 穿入 M4 螺栓，從內側（上方）鎖螺帽
//   8. 翻回正面，安裝銅柱、第二層板、馬達座、LiDAR
//
// ═══════════════════════════════════════════════════════════════

// ── 可調參數 ──────────────────────────────────────────────────

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
motor_y_offset    = 100;   // 馬達前後偏移（正 = 後方）
motor_x_spacing   = 170;   // 兩馬達間距（軸到軸）

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

// Mac Mini M4 尺寸
mac_mini_w        = 147;   // 寬 (mm)
mac_mini_d        = 147;   // 深 (mm)

// RPLIDAR C1 安裝
lidar_base_d      = 72;    // LiDAR 底座直徑 (mm)
lidar_mount_holes = 62;    // LiDAR M2.5 螺絲孔距 (mm)

// 電池區域
battery_w         = 120;   // 電池寬度預留 (mm)
battery_d         = 80;    // 電池深度預留 (mm)

// ── 拼圖榫參數 ──────────────────────────────────────────────
tab_len           = 20;    // 榫長（沿分割線方向）(mm)
tab_ext           = 10;    // 榫深（垂直分割線伸出量）(mm)
tab_clr           = 0.15;  // 單邊配合間隙 (mm)

// ── 夾板螺栓參數 ──────────────────────────────────────────────
bracket_bolt_d    = 4.5;   // M4 通孔直徑 (mm)
bracket_bolt_off  = 10;    // 螺栓離分割線的距離 (mm)

// ── 選擇要產生的零件 ─────────────────────────────────────────
// 底板分割片（一次只開一個來匯出 STL）
RENDER_BASE_Q1       = false;  // 底板 - 右後（第一象限）
RENDER_BASE_Q2       = false;  // 底板 - 左後（第二象限）
RENDER_BASE_Q3       = false;  // 底板 - 左前（第三象限）
RENDER_BASE_Q4       = false;  // 底板 - 右前（第四象限）

// 第二層分割片
RENDER_LAYER2_Q1     = false;  // 第二層 - 右後
RENDER_LAYER2_Q2     = false;  // 第二層 - 左後
RENDER_LAYER2_Q3     = false;  // 第二層 - 左前
RENDER_LAYER2_Q4     = false;  // 第二層 - 右前

// 整件零件（不需分割，可直接列印）
RENDER_MOTOR_MOUNT   = false;  // 馬達固定座
RENDER_LIDAR_MOUNT   = false;  // LiDAR 頂部支架
RENDER_BRACKET       = false;  // 分割線夾板（列印 4 個）
RENDER_CENTER_BRACKET = false; // 中心十字夾板（列印 1 個）

// 預覽
RENDER_BASE_FULL     = false;  // 底板完整預覽（不要匯出）
RENDER_LAYER2_FULL   = false;  // 第二層完整預覽（不要匯出）
RENDER_ALL_ASSEMBLY  = true;   // 全部組裝預覽（不要匯出）

// ── 顏色定義 ──────────────────────────────────────────────────
color_base    = [0.2, 0.2, 0.2];
color_mount   = [0.8, 0.4, 0.1];
color_layer2  = [0.3, 0.3, 0.6];
color_lidar   = [0.1, 0.6, 0.3];
color_bracket = [0.9, 0.2, 0.2];

// ═══════════════════════════════════════════════════════════════
// 拼圖榫工具模組
// ═══════════════════════════════════════════════════════════════

// Y=0 分割線上的榫塊
// cx  = X 中心座標
// dir = -1 伸入 -Y（下方），+1 伸入 +Y（上方）
// clr = 0 用於本體，tab_clr 用於槽口（加大以留間隙）
module y_tab(cx, dir, h, clr=0) {
    if (dir < 0)
        translate([cx - tab_len/2 - clr, -(tab_ext + clr), -1])
            cube([tab_len + 2*clr, tab_ext + 2*clr, h + 2]);
    else
        translate([cx - tab_len/2 - clr, -clr, -1])
            cube([tab_len + 2*clr, tab_ext + 2*clr, h + 2]);
}

// X=0 分割線上的榫塊
// cy  = Y 中心座標
// dir = -1 伸入 -X（左方），+1 伸入 +X（右方）
module x_tab(cy, dir, h, clr=0) {
    if (dir < 0)
        translate([-(tab_ext + clr), cy - tab_len/2 - clr, -1])
            cube([tab_ext + 2*clr, tab_len + 2*clr, h + 2]);
    else
        translate([-clr, cy - tab_len/2 - clr, -1])
            cube([tab_ext + 2*clr, tab_len + 2*clr, h + 2]);
}

// ═══════════════════════════════════════════════════════════════
// 象限切割（含拼圖榫）
// ═══════════════════════════════════════════════════════════════

// 基礎象限方塊
module quadrant_box(quadrant, height=50) {
    half = base_diameter / 2 + 5;
    if (quadrant == 1)
        translate([0, 0, -1]) cube([half, half, height + 2]);
    else if (quadrant == 2)
        translate([-half, 0, -1]) cube([half, half, height + 2]);
    else if (quadrant == 3)
        translate([-half, -half, -1]) cube([half, half, height + 2]);
    else if (quadrant == 4)
        translate([0, -half, -1]) cube([half, half, height + 2]);
}

// 帶榫的象限切割體
// 每個象限有 2 個伸出榫 + 2 個接收槽
//
// 榫配置表：
//   Y=0 分割線：x=-90 (↓Q2→Q3), x=-30 (↑Q3→Q2), x=30 (↓Q1→Q4), x=90 (↑Q4→Q1)
//   X=0 分割線：y=-88 (←Q4→Q3), y=-35 (→Q3→Q4), y=35 (←Q1→Q2), y=88 (→Q2→Q1)
//
module quadrant_cut(quadrant) {
    h = base_thickness + lip_height + 10;

    difference() {
        union() {
            quadrant_box(quadrant, h);

            // 伸出榫（精確尺寸，無間隙）
            if (quadrant == 1) {
                y_tab(30,  -1, h);  // Y=0 at x=30，伸入 Q4 區域
                x_tab(35,  -1, h);  // X=0 at y=35，伸入 Q2 區域
            }
            if (quadrant == 2) {
                y_tab(-90, -1, h);  // Y=0 at x=-90，伸入 Q3 區域
                x_tab(88,   1, h);  // X=0 at y=88，伸入 Q1 區域
            }
            if (quadrant == 3) {
                y_tab(-30,  1, h);  // Y=0 at x=-30，伸入 Q2 區域
                x_tab(-35,  1, h);  // X=0 at y=-35，伸入 Q4 區域
            }
            if (quadrant == 4) {
                y_tab(90,   1, h);  // Y=0 at x=90，伸入 Q1 區域
                x_tab(-88, -1, h);  // X=0 at y=-88，伸入 Q3 區域
            }
        }

        // 接收槽（加間隙，讓鄰片的榫能插入）
        if (quadrant == 1) {
            y_tab(90,   1, h, tab_clr);  // Q4 的榫伸入此處
            x_tab(88,   1, h, tab_clr);  // Q2 的榫伸入此處
        }
        if (quadrant == 2) {
            y_tab(-30,  1, h, tab_clr);  // Q3 的榫伸入此處
            x_tab(35,  -1, h, tab_clr);  // Q1 的榫伸入此處
        }
        if (quadrant == 3) {
            y_tab(-90, -1, h, tab_clr);  // Q2 的榫伸入此處
            x_tab(-88, -1, h, tab_clr);  // Q4 的榫伸入此處
        }
        if (quadrant == 4) {
            y_tab(30,  -1, h, tab_clr);  // Q1 的榫伸入此處
            x_tab(-35,  1, h, tab_clr);  // Q3 的榫伸入此處
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// 夾板螺栓孔
// ═══════════════════════════════════════════════════════════════

// 跨在分割線兩側的螺栓孔對
// 每對有 2 個孔，分別在分割線兩邊各 bracket_bolt_off (10mm)
module bracket_bolt_holes() {
    h = base_thickness + lip_height + 5;
    bo = bracket_bolt_off;

    // Y=0 分割線的夾板螺栓（x=-75 和 x=75）
    for (x_pos = [-75, 75]) {
        translate([x_pos, bo, -1])
            cylinder(d=bracket_bolt_d, h=h, $fn=20);
        translate([x_pos, -bo, -1])
            cylinder(d=bracket_bolt_d, h=h, $fn=20);
    }

    // X=0 分割線的夾板螺栓（y=-55 和 y=55）
    for (y_pos = [-55, 55]) {
        translate([bo, y_pos, -1])
            cylinder(d=bracket_bolt_d, h=h, $fn=20);
        translate([-bo, y_pos, -1])
            cylinder(d=bracket_bolt_d, h=h, $fn=20);
    }

    // 中心十字夾板螺栓（四角各一個）
    for (sx = [-1, 1]) {
        for (sy = [-1, 1]) {
            translate([sx * 15, sy * 15, -1])
                cylinder(d=bracket_bolt_d, h=h, $fn=20);
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// 底板（完整）
// ═══════════════════════════════════════════════════════════════

module base_plate_full() {
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
                translate([0, 0, -1])
                    cylinder(d=base_diameter + 2, h=base_thickness + 1, $fn=120);
            }

            // 馬達安裝區加強肋
            for (side = [-1, 1]) {
                translate([side * motor_x_spacing/2, motor_y_offset, 0])
                    cylinder(d=motor_body_d + 16, h=base_thickness + 3, $fn=60);
            }

            // 分割線加強肋（讓拼接處更強壯）
            intersection() {
                cylinder(d=base_diameter - 2, h=base_thickness, $fn=120);
                union() {
                    translate([-base_diameter/2, -8, 0])
                        cube([base_diameter, 16, base_thickness]);
                    translate([-8, -base_diameter/2, 0])
                        cube([16, base_diameter, base_thickness]);
                }
            }
        }

        // ── 馬達軸孔 ──
        for (side = [-1, 1]) {
            translate([side * motor_x_spacing/2, motor_y_offset, -1]) {
                cylinder(d=motor_shaft_d + 4, h=base_thickness + 10, $fn=30);
                for (angle = [0, 90, 180, 270]) {
                    rotate([0, 0, angle])
                        translate([motor_mount_holes/2, 0, 0])
                            cylinder(d=motor_m3_d, h=base_thickness + 10, $fn=20);
                }
            }
        }

        // ── 馬達本體凹槽 ──
        for (side = [-1, 1]) {
            translate([side * motor_x_spacing/2, motor_y_offset, base_thickness - 0.5])
                cylinder(d=motor_body_d + 1, h=20, $fn=60);
        }

        // ── 輪子開口 ──
        for (side = [-1, 1]) {
            translate([side * motor_x_spacing/2, motor_y_offset, -1])
                cube([wheel_w + 4, wheel_d + 10, base_thickness + lip_height + 5],
                     center=true);
        }

        // ── 萬向輪安裝孔 ──
        translate([0, caster_y_offset, -1]) {
            cylinder(d=12, h=base_thickness + 5, $fn=30);
            for (angle = [0, 90, 180, 270]) {
                rotate([0, 0, angle + 45])
                    translate([caster_mount_d/2, 0, 0])
                        cylinder(d=caster_hole_d, h=base_thickness + 5, $fn=20);
            }
        }

        // ── 銅柱支撐孔 ──
        for (i = [0:standoff_count-1]) {
            angle = i * 360 / standoff_count + 30;
            translate([standoff_ring_r * cos(angle),
                       standoff_ring_r * sin(angle), -1])
                cylinder(d=standoff_d, h=base_thickness + lip_height + 5, $fn=20);
        }

        // ── 走線孔 ──
        translate([0, 0, -1])
            cylinder(d=wire_hole_d, h=base_thickness + 5, $fn=30);
        translate([0, -70, -1])
            cylinder(d=wire_hole_d, h=base_thickness + 5, $fn=30);
        translate([0, 70, -1])
            cylinder(d=wire_hole_d, h=base_thickness + 5, $fn=30);
        for (side = [-1, 1]) {
            translate([side * 60, 0, -1])
                cylinder(d=wire_hole_d, h=base_thickness + 5, $fn=30);
        }

        // ── 電池固定孔 ──
        for (dx = [-battery_w/2 + 10, battery_w/2 - 10]) {
            for (dy = [-battery_d/2 + 10, battery_d/2 - 10]) {
                translate([dx, dy - 20, -1])
                    cylinder(d=motor_m3_d, h=base_thickness + 5, $fn=20);
            }
        }

        // ── ESP32 安裝孔 ──
        translate([60, -40, 0]) {
            for (dx = [0, 52]) {
                for (dy = [0, 28]) {
                    translate([dx - 26, dy - 14, -1])
                        cylinder(d=2.8, h=base_thickness + 5, $fn=20);
                }
            }
        }

        // ── BTS7960 安裝孔 ──
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

        // ── 減重孔 ──
        for (angle = [60, 120, 240, 300]) {
            translate([90 * cos(angle), 90 * sin(angle), -1])
                cylinder(d=25, h=base_thickness + 5, $fn=30);
        }

        // ── 夾板螺栓孔 ──
        bracket_bolt_holes();
    }

    // ── 標記文字 ──
    translate([0, base_diameter/2 - 25, base_thickness])
        linear_extrude(0.6)
            text("REACHY MINI", size=8, halign="center",
                 font="Liberation Sans:style=Bold");

    translate([0, -(base_diameter/2 - 25), base_thickness])
        linear_extrude(0.6)
            text("FRONT", size=6, halign="center",
                 font="Liberation Sans");
}


// ═══════════════════════════════════════════════════════════════
// 底板分割片（帶拼圖榫）
// ═══════════════════════════════════════════════════════════════

module base_quarter(quadrant) {
    intersection() {
        base_plate_full();
        quadrant_cut(quadrant);
    }
}


// ═══════════════════════════════════════════════════════════════
// 第二層板（完整）
// ═══════════════════════════════════════════════════════════════

module second_layer_full() {
    layer_thickness = 3;
    layer_d = base_diameter - 20;  // 280mm

    difference() {
        union() {
            cylinder(d=layer_d, h=layer_thickness, $fn=120);

            // 分割線加強肋
            intersection() {
                cylinder(d=layer_d, h=layer_thickness, $fn=120);
                union() {
                    translate([-layer_d/2, -6, 0])
                        cube([layer_d, 12, layer_thickness]);
                    translate([-6, -layer_d/2, 0])
                        cube([12, layer_d, layer_thickness]);
                }
            }
        }

        // 銅柱孔
        for (i = [0:standoff_count-1]) {
            angle = i * 360 / standoff_count + 30;
            translate([standoff_ring_r * cos(angle),
                       standoff_ring_r * sin(angle), -1])
                cylinder(d=standoff_d, h=layer_thickness + 5, $fn=20);
        }

        // Mac Mini 輪廓標記槽
        translate([0, -10, -1]) {
            difference() {
                cube([mac_mini_w + 2, mac_mini_d + 2, layer_thickness + 5],
                     center=true);
                cube([mac_mini_w - 4, mac_mini_d - 4, layer_thickness + 5],
                     center=true);
            }

            // Mac Mini 固定孔
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

        // 第二層夾板螺栓孔（與底板對應位置）
        layer2_bracket_bolt_holes();
    }
}

module layer2_bracket_bolt_holes() {
    layer_thickness = 3;
    h = layer_thickness + 5;
    bo = bracket_bolt_off;

    // Y=0 分割線
    for (x_pos = [-75, 75]) {
        translate([x_pos, bo, -1])
            cylinder(d=bracket_bolt_d, h=h, $fn=20);
        translate([x_pos, -bo, -1])
            cylinder(d=bracket_bolt_d, h=h, $fn=20);
    }

    // X=0 分割線
    for (y_pos = [-55, 55]) {
        translate([bo, y_pos, -1])
            cylinder(d=bracket_bolt_d, h=h, $fn=20);
        translate([-bo, y_pos, -1])
            cylinder(d=bracket_bolt_d, h=h, $fn=20);
    }

    // 中心
    for (sx = [-1, 1]) {
        for (sy = [-1, 1]) {
            translate([sx * 15, sy * 15, -1])
                cylinder(d=bracket_bolt_d, h=h, $fn=20);
        }
    }
}


// ═══════════════════════════════════════════════════════════════
// 第二層分割片（帶榫）
// ═══════════════════════════════════════════════════════════════

// 第二層用較小的榫（15mm × 8mm）
module y_tab_l2(cx, dir, h, clr=0) {
    tl = 15; te = 8;
    if (dir < 0)
        translate([cx - tl/2 - clr, -(te + clr), -1])
            cube([tl + 2*clr, te + 2*clr, h + 2]);
    else
        translate([cx - tl/2 - clr, -clr, -1])
            cube([tl + 2*clr, te + 2*clr, h + 2]);
}

module x_tab_l2(cy, dir, h, clr=0) {
    tl = 15; te = 8;
    if (dir < 0)
        translate([-(te + clr), cy - tl/2 - clr, -1])
            cube([te + 2*clr, tl + 2*clr, h + 2]);
    else
        translate([-clr, cy - tl/2 - clr, -1])
            cube([te + 2*clr, tl + 2*clr, h + 2]);
}

module layer2_quadrant_cut(quadrant) {
    h = 20;
    difference() {
        union() {
            quadrant_box(quadrant, h);
            if (quadrant == 1) {
                y_tab_l2(30,  -1, h);
                x_tab_l2(35,  -1, h);
            }
            if (quadrant == 2) {
                y_tab_l2(-90, -1, h);
                x_tab_l2(88,   1, h);
            }
            if (quadrant == 3) {
                y_tab_l2(-30,  1, h);
                x_tab_l2(-35,  1, h);
            }
            if (quadrant == 4) {
                y_tab_l2(90,   1, h);
                x_tab_l2(-88, -1, h);
            }
        }
        if (quadrant == 1) {
            y_tab_l2(90,   1, h, tab_clr);
            x_tab_l2(88,   1, h, tab_clr);
        }
        if (quadrant == 2) {
            y_tab_l2(-30,  1, h, tab_clr);
            x_tab_l2(35,  -1, h, tab_clr);
        }
        if (quadrant == 3) {
            y_tab_l2(-90, -1, h, tab_clr);
            x_tab_l2(-88, -1, h, tab_clr);
        }
        if (quadrant == 4) {
            y_tab_l2(30,  -1, h, tab_clr);
            x_tab_l2(-35,  1, h, tab_clr);
        }
    }
}

module layer2_quarter(quadrant) {
    intersection() {
        second_layer_full();
        layer2_quadrant_cut(quadrant);
    }
}


// ═══════════════════════════════════════════════════════════════
// 夾板（跨分割線固定用，從底部鎖上）
// ═══════════════════════════════════════════════════════════════

// 直線夾板 — 跨越一條分割線
// 尺寸：60mm × 28mm × 3mm，2 個 M4 螺栓孔間距 = 2 × bracket_bolt_off
module joint_bracket() {
    bw = 60;
    bh = 2 * bracket_bolt_off + 10;
    bt = 3;

    difference() {
        // 圓角矩形
        hull() {
            for (dx = [-bw/2 + 3, bw/2 - 3]) {
                for (dy = [-bh/2 + 3, bh/2 - 3]) {
                    translate([dx, dy, 0])
                        cylinder(r=3, h=bt, $fn=20);
                }
            }
        }

        // 螺栓孔
        translate([0, bracket_bolt_off, -1])
            cylinder(d=bracket_bolt_d, h=bt + 2, $fn=20);
        translate([0, -bracket_bolt_off, -1])
            cylinder(d=bracket_bolt_d, h=bt + 2, $fn=20);
    }
}

// 中心十字夾板 — 覆蓋四片交會的中心區域
// 尺寸：40mm × 40mm × 3mm，4 個 M4 螺栓孔
module center_bracket() {
    bt = 3;
    size = 40;

    difference() {
        // 圓角矩形
        hull() {
            for (dx = [-size/2 + 3, size/2 - 3]) {
                for (dy = [-size/2 + 3, size/2 - 3]) {
                    translate([dx, dy, 0])
                        cylinder(r=3, h=bt, $fn=20);
                }
            }
        }

        // 4 個螺栓孔
        for (sx = [-1, 1]) {
            for (sy = [-1, 1]) {
                translate([sx * 15, sy * 15, -1])
                    cylinder(d=bracket_bolt_d, h=bt + 2, $fn=20);
            }
        }

        // 中心走線孔（讓線材通過）
        translate([0, 0, -1])
            cylinder(d=10, h=bt + 2, $fn=30);
    }
}


// ═══════════════════════════════════════════════════════════════
// 馬達固定座（L型支架）— 不需分割
// ═══════════════════════════════════════════════════════════════

module motor_mount() {
    mount_wall   = 4;
    mount_height = motor_body_d/2 + 8;
    mount_width  = motor_body_d + 12;
    mount_depth  = motor_body_len + 8;

    difference() {
        union() {
            cube([mount_width, mount_depth, mount_wall]);
            translate([0, 0, 0])
                cube([mount_wall, mount_depth, mount_height]);
            translate([mount_width - mount_wall, 0, 0])
                cube([mount_wall, mount_depth, mount_height]);
            translate([0, mount_depth - mount_wall, 0])
                cube([mount_width, mount_wall, mount_height * 0.6]);
        }

        translate([mount_width/2, mount_depth/2 - 2, mount_height])
            rotate([0, 0, 0])
                cylinder(d=motor_body_d + 0.5, h=mount_height + 1,
                         $fn=60, center=true);

        for (dx = [-mount_width/2 + 8, mount_width/2 - 8]) {
            for (dy = [8, mount_depth - 8]) {
                translate([mount_width/2 + dx, dy, -1])
                    cylinder(d=motor_m3_d, h=mount_wall + 5, $fn=20);
            }
        }

        translate([mount_width/2, -1, mount_height - motor_body_d/2 - 2])
            rotate([-90, 0, 0])
                cylinder(d=motor_shaft_d + 4, h=mount_depth + 5, $fn=30);

        translate([-1, mount_depth/2 - 2, mount_height - motor_body_d/2 - 2])
            rotate([0, 90, 0])
                cylinder(d=motor_m3_d, h=mount_width + 5, $fn=20);
    }
}


// ═══════════════════════════════════════════════════════════════
// LiDAR 頂部支架 — 不需分割
// ═══════════════════════════════════════════════════════════════

module lidar_mount() {
    pole_d     = 12;
    pole_h     = 80;
    plate_d    = 90;
    plate_h    = 3;

    cylinder(d=pole_d, h=pole_h, $fn=30);

    translate([0, 0, pole_h]) {
        difference() {
            cylinder(d=plate_d, h=plate_h, $fn=60);
            for (angle = [0, 90, 180, 270]) {
                rotate([0, 0, angle])
                    translate([lidar_mount_holes/2, 0, -1])
                        cylinder(d=2.8, h=plate_h + 5, $fn=20);
            }
            translate([0, 0, -1])
                cylinder(d=pole_d - 2, h=plate_h + 5, $fn=30);
        }
    }

    difference() {
        cylinder(d=40, h=4, $fn=30);
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
    // ── 組裝預覽：四片拼合 + 夾板 + 所有零件 ──

    // 底板四片（爆炸圖可把 explode 改大）
    explode = 0;  // 改成 20 可看到爆炸圖效果
    color(color_base) {
        translate([ explode,  explode, 0]) base_quarter(1);
        translate([-explode,  explode, 0]) base_quarter(2);
        translate([-explode, -explode, 0]) base_quarter(3);
        translate([ explode, -explode, 0]) base_quarter(4);
    }

    // 夾板（紅色，底板內側）
    bracket_z = base_thickness + 0.5;
    color(color_bracket, 0.8) {
        // Y=0 分割線夾板
        translate([-75, 0, bracket_z]) joint_bracket();
        translate([75, 0, bracket_z]) joint_bracket();
        // X=0 分割線夾板（旋轉 90°）
        translate([0, -55, bracket_z]) rotate([0, 0, 90]) joint_bracket();
        translate([0, 55, bracket_z]) rotate([0, 0, 90]) joint_bracket();
        // 中心十字夾板
        translate([0, 0, bracket_z]) center_bracket();
    }

    // 馬達固定座
    color(color_mount) {
        translate([-motor_x_spacing/2 - 25, motor_y_offset - 16, base_thickness])
            motor_mount();
        translate([motor_x_spacing/2 - 25, motor_y_offset - 16, base_thickness])
            mirror([1, 0, 0]) motor_mount();
    }

    // 第二層板
    color(color_layer2, 0.6)
        translate([0, 0, base_thickness + lip_height + 40])
            second_layer_full();

    // LiDAR 支架
    color(color_lidar, 0.8)
        translate([0, 0, base_thickness + lip_height + 40 + 3])
            lidar_mount();

} else {
    // ── 單件匯出 ──
    if (RENDER_BASE_Q1)   color(color_base)   base_quarter(1);
    if (RENDER_BASE_Q2)   color(color_base)   base_quarter(2);
    if (RENDER_BASE_Q3)   color(color_base)   base_quarter(3);
    if (RENDER_BASE_Q4)   color(color_base)   base_quarter(4);

    if (RENDER_LAYER2_Q1) color(color_layer2)  layer2_quarter(1);
    if (RENDER_LAYER2_Q2) color(color_layer2)  layer2_quarter(2);
    if (RENDER_LAYER2_Q3) color(color_layer2)  layer2_quarter(3);
    if (RENDER_LAYER2_Q4) color(color_layer2)  layer2_quarter(4);

    if (RENDER_BASE_FULL)   color(color_base)   base_plate_full();
    if (RENDER_LAYER2_FULL) color(color_layer2)  second_layer_full();

    if (RENDER_MOTOR_MOUNT)    color(color_mount)    motor_mount();
    if (RENDER_LIDAR_MOUNT)    color(color_lidar)    lidar_mount();
    if (RENDER_BRACKET)        color(color_bracket)  joint_bracket();
    if (RENDER_CENTER_BRACKET) color(color_bracket)  center_bracket();
}

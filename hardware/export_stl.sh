#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Reachy Mini 底盤 — 批次匯出 STL
# 用法: bash hardware/export_stl.sh
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCAD="${SCRIPT_DIR}/chassis.scad"
STL_DIR="${SCRIPT_DIR}/stl"

mkdir -p "$STL_DIR"

# 所有零件關閉的基礎參數
ALL_OFF=(
  -D 'RENDER_ALL_ASSEMBLY=false'
  -D 'RENDER_BASE_FULL=false'
  -D 'RENDER_LAYER2_FULL=false'
  -D 'RENDER_BASE_Q1=false'
  -D 'RENDER_BASE_Q2=false'
  -D 'RENDER_BASE_Q3=false'
  -D 'RENDER_BASE_Q4=false'
  -D 'RENDER_LAYER2_Q1=false'
  -D 'RENDER_LAYER2_Q2=false'
  -D 'RENDER_LAYER2_Q3=false'
  -D 'RENDER_LAYER2_Q4=false'
  -D 'RENDER_MOTOR_MOUNT=false'
  -D 'RENDER_LIDAR_MOUNT=false'
  -D 'RENDER_BRACKET=false'
  -D 'RENDER_CENTER_BRACKET=false'
)

# 零件清單: 變數名=檔名
PARTS=(
  "RENDER_BASE_Q1=base_q1"
  "RENDER_BASE_Q2=base_q2"
  "RENDER_BASE_Q3=base_q3"
  "RENDER_BASE_Q4=base_q4"
  "RENDER_LAYER2_Q1=layer2_q1"
  "RENDER_LAYER2_Q2=layer2_q2"
  "RENDER_LAYER2_Q3=layer2_q3"
  "RENDER_LAYER2_Q4=layer2_q4"
  "RENDER_MOTOR_MOUNT=motor_mount"
  "RENDER_LIDAR_MOUNT=lidar_mount"
  "RENDER_BRACKET=joint_bracket"
  "RENDER_CENTER_BRACKET=center_bracket"
)

TOTAL=${#PARTS[@]}
COUNT=0
FAILED=0

echo "═══════════════════════════════════════════"
echo " Reachy Mini 底盤 STL 匯出（共 ${TOTAL} 個零件）"
echo "═══════════════════════════════════════════"
echo ""

for part in "${PARTS[@]}"; do
  VAR="${part%%=*}"
  NAME="${part##*=}"
  COUNT=$((COUNT + 1))

  echo "[${COUNT}/${TOTAL}] 匯出 ${NAME}.stl ..."

  openscad "${ALL_OFF[@]}" -D "${VAR}=true" -o "${STL_DIR}/${NAME}.stl" "$SCAD" 2>&1 | grep -E "^(ERROR|WARNING|Total)"

  SIZE=$(stat -f%z "${STL_DIR}/${NAME}.stl" 2>/dev/null || echo 0)
  if [ "$SIZE" -gt 0 ]; then
    SIZE_KB=$((SIZE / 1024))
    echo "    ✅ ${SIZE_KB} KB"
  else
    echo "    ❌ 匯出失敗！"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "═══════════════════════════════════════════"
if [ "$FAILED" -eq 0 ]; then
  echo " ✅ 全部 ${TOTAL} 個零件匯出成功！"
else
  echo " ⚠️  ${FAILED} 個零件匯出失敗"
fi
echo "═══════════════════════════════════════════"
echo ""
echo "列印數量提醒："
echo "  base_q1~q4     × 各 1 個"
echo "  layer2_q1~q4   × 各 1 個"
echo "  motor_mount    × 2 個（左右對稱）"
echo "  lidar_mount    × 1 個"
echo "  joint_bracket  × 4 個"
echo "  center_bracket × 1 個"
echo ""
ls -lh "${STL_DIR}/"*.stl

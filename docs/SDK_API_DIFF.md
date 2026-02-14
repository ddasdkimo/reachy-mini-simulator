# Reachy Mini SDK v1.3.0 — 真實 API vs 模擬器介面差異表

> 測試日期：2026-02-14
> SDK 版本：reachy_mini 1.3.0
> 連線方式：USB (/dev/cu.usbmodem5B420748681)
> Daemon：reachy-mini-daemon v1.3.0

## 真實 SDK 公開 API 清單

```
T_head_cam                              # 攝影機轉換矩陣
async_play_move()                       # 非同步播放動作
client                                  # Zenoh client
connection_mode                         # 連線模式
disable_gravity_compensation()          # 停用重力補償
disable_motors()                        # 停用所有馬達
enable_gravity_compensation()           # 啟用重力補償
enable_motors()                         # 啟用所有馬達
get_current_head_pose()                 # 取得頭部 4x4 矩陣
get_current_joint_positions()           # 取得關節位置 → (stewart[7], antenna[2])
get_present_antenna_joint_positions()   # 取得天線角度 [left, right]
goto_sleep()                            # 進入睡眠
goto_target()                           # 插值移動到目標
imu                                     # IMU 數據（目前回傳 None）
is_recording                            # 是否正在錄製
logger                                  # logging 實例
look_at_image(u, v)                     # 凝視畫面座標
look_at_world(x, y, z)                  # 凝視世界座標
media                                   # MediaManager 實例
media_manager                           # 同 media
play_move()                             # 同步播放動作
robot_name                              # 機器人名稱
set_automatic_body_yaw()                # 自動身體旋轉
set_target()                            # 立即設定目標（無插值）
set_target_antenna_joint_positions()    # 設定天線目標角度
set_target_body_yaw()                   # 設定身體旋轉目標
set_target_head_pose()                  # 設定頭部姿態目標
start_recording()                       # 開始錄製動作
stop_recording()                        # 停止錄製 → 回傳 Move
wake_up()                               # 喚醒
```

## 差異對照表

| 功能 | 模擬器 RealReachyMini 呼叫 | 真實 SDK API | 狀態 | 修復狀態 |
|------|---------------------------|-------------|------|---------|
| **頭部姿態讀取** | `sdk.get_current_head_pose()` | `sdk.get_current_head_pose()` | ✅ 已修復 | ✅ 已修復 |
| **天線角度讀取** | `sdk.get_present_antenna_joint_positions()` | `sdk.get_present_antenna_joint_positions()` | ✅ 已修復 | ✅ 已修復 |
| **身體旋轉讀取** | `sdk.get_current_joint_positions()[0][0]` | 無直接 getter（需從 joint_positions 推算） | ✅ 已修復 | ✅ 已修復 |
| **設定目標** | `sdk.set_target(**kwargs)` | `sdk.set_target()` 直接轉發 | ✅ 已修復 | ✅ 已修復 |
| **插值移動** | `sdk.goto_target(...)` + InterpolationTechnique enum 映射 | `sdk.goto_target(head, duration, method)` | ✅ 已修復 | ✅ 已修復 |
| **喚醒狀態** | 內部 `_is_awake` 追蹤 | 無此屬性（只有 wake_up/goto_sleep 方法） | ✅ 已修復 | ✅ 已修復 |
| **馬達控制** | `sdk.enable_motors(ids=[name])` / `sdk.disable_motors(ids=[name])` | `sdk.enable_motors()` / `sdk.disable_motors()` | ✅ 已修復 | ✅ 已修復 |
| **馬達狀態** | 內部 `_motor_states` dict 追蹤 | 無此方法 | ✅ 已修復 | ✅ 已修復 |
| **重力補償** | `sdk.enable_gravity_compensation()` / `sdk.disable_gravity_compensation()` | `sdk.enable_gravity_compensation()` / `sdk.disable_gravity_compensation()` | ✅ 已修復 | ✅ 已修復 |
| **關節位置** | `sdk.get_current_joint_positions()` → tuple 拆解為 dict | `sdk.get_current_joint_positions()` → (head[7], antenna[2]) | ✅ 已修復 | ✅ 已修復 |
| **IMU** | `sdk.imu` property 讀取 | `sdk.imu` → 目前 None | ✅ 已修復 | ✅ 已修復 |
| **動作錄製** | `sdk.start_recording()` | `sdk.start_recording()` | ✅ 已修復 | ✅ 已修復 |
| **動作停止** | `sdk.stop_recording()` → List[Dict] 轉 Move | `sdk.stop_recording()` | ✅ 已修復 | ✅ 已修復 |
| **動作回放** | `sdk.play_move(move, play_frequency, ...)` | `sdk.play_move()` / `sdk.async_play_move()` | ✅ 已修復 | ✅ 已修復 |
| **回放狀態** | 內部 `_is_motion_playing` 追蹤 | SDK 無對應 property | ✅ 已修復 | ✅ 已修復 |
| **凝視** | `sdk.look_at_image(u, v, duration, perform_movement)` | `sdk.look_at_image(u, v)` | ✅ 一致 | -- |
| **凝視世界** | `sdk.look_at_world(x, y, z, duration, perform_movement)` | `sdk.look_at_world(x, y, z)` | ✅ 一致 | -- |
| **喚醒** | `sdk.wake_up()` | `sdk.wake_up()` | ✅ 一致 | -- |
| **睡眠** | `sdk.goto_sleep()` | `sdk.goto_sleep()` | ✅ 一致 | -- |
| **媒體** | `sdk.media` | `sdk.media` | ✅ 一致 | -- |
| **DoA (聲源方向)** | `sdk.media.get_DoA()` → tuple[0] 取角度 | `sdk.media.get_DoA()` | ✅ 已修復 | ✅ 已修復 |

## 測試結果摘要

| 項目 | 結果 | 影像/數據 |
|------|------|-----------|
| 攝影機 | ✅ | 1920x1080 RGB (uint8) |
| 天線控制 | ✅ | 可讀可寫 |
| 頭部轉動 | ✅ | goto_target(head=4x4, duration) 正常 |
| 點頭動作 | ✅ | pitch 控制正常 |
| 表情動畫 | ✅ | 高興/好奇表情正常 |
| IMU | ⚠️ | 回傳 None |
| 音訊 | 未測試 | — |

## 需要研究的項目

1. `set_target()` 的完整參數簽名
2. `goto_target()` 是否支援 antennas / body_yaw / method 參數
3. `play_move()` 的參數格式和 Move 物件結構
4. `imu` 屬性為何回傳 None（硬體問題或需額外設定？）
5. `set_automatic_body_yaw()` 的用途和參數
6. Media 的音訊播放/錄音 API

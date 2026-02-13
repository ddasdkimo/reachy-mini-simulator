# Reachy Mini Simulator - Architecture

## 1. Module Dependency Graph

```mermaid
graph TD
    subgraph "Abstract Interfaces"
        RI[robot_interface.py<br/>RobotInterface + MediaInterface]
        CI[chassis_controller.py<br/>ChassisInterface]
        OI[obstacle_detector.py<br/>ObstacleDetectorInterface]
        PDI[person_detector.py<br/>PersonDetectorInterface]
    end

    subgraph "Mock Implementations"
        MR[mock_robot.py<br/>MockReachyMini]
        MM[mock_media.py<br/>MockMedia]
        MC[chassis_controller.py<br/>MockChassis]
        MO[obstacle_detector.py<br/>MockObstacleDetector]
        MPD[person_detector.py<br/>MockPersonDetector]
    end

    subgraph "Real Implementations"
        RR[real_robot.py<br/>RealReachyMini + RealMedia]
        SC[chassis_controller.py<br/>SerialChassis]
        SO[obstacle_detector.py<br/>SensorObstacleDetector]
        YPD[person_detector.py<br/>YOLOPersonDetector]
    end

    subgraph "Core Logic"
        OM[office_map.py<br/>OfficeMap + CellType]
        NAV[navigation.py<br/>Navigator + A*]
        SCN[scenario.py<br/>ScenarioEngine]
        EXP[expression.py<br/>ExpressionEngine]
        AB[ai_brain.py<br/>AIBrain + inject]
        CAL[calendar_mock.py<br/>CalendarMock]
        PRO[proactive.py<br/>ProactiveTrigger]
    end

    subgraph "Presentation"
        WS[web_server.py<br/>FastAPI + WebSocket]
        VIS[visualizer.py<br/>pygame 2D]
        WEB[web/index.html<br/>Canvas + Three.js]
    end

    subgraph "Audio Pipeline"
        AI_IN[audio_input.py<br/>VAD + STT]
        TTS[tts_engine.py<br/>OpenAI TTS]
    end

    subgraph "Factory"
        FAC[factory.py<br/>create_robot]
    end

    subgraph "New Modules (planned)"
        INTERP[interpolation.py<br/>Interpolation Engine]
        MOT[motion.py<br/>Move / Recorder / Player]
        UTL[utils.py<br/>create_head_pose + helpers]
    end

    %% Abstract -> Implementation
    RI --> MR
    RI --> RR
    CI --> MC
    CI --> SC
    OI --> MO
    OI --> SO
    PDI --> MPD
    PDI --> YPD

    %% Mock dependencies
    MR --> MM
    MR --> RI
    MM --> RI

    %% Real dependencies
    RR --> RI
    RR --> CI

    %% Factory
    FAC --> RI
    FAC -.-> MR
    FAC -.-> RR

    %% Core logic dependencies
    NAV --> OM
    NAV -.-> OI
    MO --> OM
    SCN -.-> |on_event callback| WS
    EXP -.-> MR

    %% Perception dependencies
    PRO --> PDI
    PRO -->|"on_trigger"| AB
    YPD --> MM
    WS --> PDI
    WS --> PRO

    %% Web server dependencies
    WS --> AB
    WS --> EXP
    WS --> MR
    WS --> SCN
    WS --> OM
    WS --> NAV
    WS --> CAL

    %% Visualizer dependencies
    VIS --> MR
    VIS --> OM
    VIS --> NAV
    VIS --> SCN
    VIS --> AB
    VIS --> EXP
    VIS --> CAL

    %% Web frontend
    WEB -.-> |WebSocket + REST| WS

    %% Audio pipeline
    AI_IN -.-> AB
    TTS -.-> MM
    AB -.-> EXP

    %% New module dependencies (planned)
    INTERP -.-> UTL
    MOT -.-> INTERP
    MR -.-> INTERP
    MR -.-> MOT
    MR -.-> UTL
    RR -.-> INTERP
    RR -.-> MOT

    %% Styling
    classDef iface fill:#e1f5fe,stroke:#0288d1
    classDef mock fill:#e8f5e9,stroke:#388e3c
    classDef real fill:#fff3e0,stroke:#f57c00
    classDef core fill:#f3e5f5,stroke:#7b1fa2
    classDef pres fill:#fce4ec,stroke:#c62828
    classDef audio fill:#fff9c4,stroke:#f9a825
    classDef factory fill:#e0e0e0,stroke:#616161
    classDef planned fill:#e0e0e0,stroke:#9e9e9e,stroke-dasharray: 5 5

    class RI,CI,OI,PDI iface
    class MR,MM,MC,MO,MPD mock
    class RR,SC,SO,YPD real
    class OM,NAV,SCN,EXP,AB,CAL,PRO core
    class WS,VIS,WEB pres
    class AI_IN,TTS audio
    class FAC factory
    class INTERP,MOT,UTL planned
```

## 2. Data Flow Diagram

```mermaid
flowchart LR
    subgraph Input["Input Sources"]
        USR["User<br/>(browser / pygame / mic)"]
        SCEN["Scenario Script<br/>(JSON / hardcoded)"]
        TIMER["System Clock<br/>(sim time)"]
    end

    subgraph Processing["Processing Layer"]
        direction TB
        WS_API["web_server.py<br/>REST API + WebSocket"]
        VIS_UI["visualizer.py<br/>pygame event loop"]
        AUDIO["audio_input.py<br/>VAD + STT"]

        BRAIN["ai_brain.py<br/>Claude API / fallback"]
        SCEN_ENG["scenario.py<br/>ScenarioEngine"]
        NAV_ENG["navigation.py<br/>Navigator + A*"]
        CAL_SVC["calendar_mock.py<br/>CalendarMock"]
        EXPR["expression.py<br/>ExpressionEngine"]
        DETECT["person_detector.py<br/>Mock / YOLO"]
        PROACT["proactive.py<br/>ProactiveTrigger"]
    end

    subgraph Robot["Robot Layer"]
        direction TB
        IFACE["RobotInterface<br/>(abstract)"]
        MOCK["MockReachyMini"]
        REAL["RealReachyMini"]
        MEDIA["MediaInterface<br/>(camera + audio)"]
    end

    subgraph Output["Output"]
        WEB_FE["Web Frontend<br/>(2D Canvas + 3D)"]
        PYG["pygame Window"]
        HW["Real Hardware<br/>(SDK + Chassis)"]
        TTS_OUT["tts_engine.py<br/>Speech Output"]
    end

    %% Input -> Processing
    USR -->|"POST /api/speak<br/>POST /api/navigate<br/>click / keyboard"| WS_API
    USR -->|"mouse click<br/>keyboard T"| VIS_UI
    USR -->|"microphone"| AUDIO
    SCEN -->|"load events"| SCEN_ENG
    TIMER -->|"tick(dt)"| SCEN_ENG

    %% Internal processing
    WS_API --> BRAIN
    WS_API --> NAV_ENG
    VIS_UI --> BRAIN
    VIS_UI --> NAV_ENG
    AUDIO -->|"transcribed text"| BRAIN

    SCEN_ENG -->|"on_event callback"| BRAIN
    SCEN_ENG -->|"calendar_event"| CAL_SVC
    SCEN_ENG -->|"navigate trigger"| NAV_ENG

    BRAIN -->|"emotion tag"| EXPR
    BRAIN -->|"nav_target"| NAV_ENG
    BRAIN -->|"response text"| TTS_OUT

    %% Perception pipeline
    MEDIA -->|"get_frame()"| DETECT
    DETECT -->|"on_person_appeared<br/>on_person_left"| PROACT
    PROACT -->|"inject(prompt)"| BRAIN

    %% Processing -> Robot
    NAV_ENG -->|"move_to(x, y)"| IFACE
    EXPR -->|"set_target(head, antennas)"| IFACE
    IFACE --> MOCK
    IFACE --> REAL
    MOCK --> MEDIA
    REAL --> MEDIA

    %% Robot -> Output
    MOCK -->|"state via WebSocket"| WEB_FE
    MOCK -->|"position / heading"| PYG
    REAL -->|"SDK set_target"| HW
    REAL -->|"chassis velocity"| HW
    TTS_OUT -->|"audio samples"| MEDIA
```

## 3. Interface Extension Reference

### 3.1 RobotInterface

| Method | Category | Existing | New | Description |
|--------|----------|:--------:|:---:|-------------|
| `set_target(head, antennas, body_yaw)` | Control | V | | Set target pose (instant) |
| `goto_target(head, antennas, body_yaw, duration, method)` | Control | | V | Interpolated motion over duration |
| `get_current_joint_positions() -> dict[str, float]` | Query | | V | All joint angles as flat dict |
| `move_to(x, y)` | Navigation | V | | Set chassis move target |
| `update_position(dt) -> bool` | Navigation | V | | Tick chassis movement |
| `is_moving -> bool` | Navigation | V | | Chassis in motion? |
| `position / heading` | Navigation | V | | 2D pose on map |
| `media -> MediaInterface` | Accessor | V | | Camera + audio access |
| `antenna_pos -> list[float]` | Query | V | | Current antenna angles (rad) |
| `head_pose -> ndarray(4,4)` | Query | V | | Current head pose matrix |
| `body_yaw -> float` | Query | V | | Current body yaw (rad) |
| `get_state_summary() -> dict` | Query | V | | Full state snapshot |
| `look_at_image(u, v)` | Gaze | | V | Point head at image pixel |
| `look_at_world(x, y, z)` | Gaze | | V | Point head at world coordinate |
| `wake_up() / goto_sleep()` | Lifecycle | | V | Power state transitions |
| `is_awake -> bool` | Lifecycle | | V | Power state query |
| `set_motor_enabled(motor, enabled)` | Motor | | V | Enable/disable individual motor |
| `is_motor_enabled(motor) -> bool` | Motor | | V | Query motor state |
| `set_gravity_compensation(enabled)` | Motor | | V | Toggle gravity compensation |
| `get_imu_data() -> dict` | Sensor | | V | Accelerometer + gyroscope data |
| `start_motion_recording()` | Motion | | V | Begin recording joint trajectory |
| `stop_motion_recording() -> Move` | Motion | | V | End recording, return Move object |
| `play_motion(move, speed)` | Motion | | V | Play back a recorded motion |
| `is_motion_playing -> bool` | Motion | | V | Is motion playback active? |
| `close()` | Lifecycle | V | | Release all resources |

### 3.2 MediaInterface

| Method | Category | Existing | New | Description |
|--------|----------|:--------:|:---:|-------------|
| `get_frame() -> ndarray` | Camera | V | | Capture one BGR frame |
| `get_output_audio_samplerate() -> int` | Audio | V | | Output sample rate (Hz) |
| `start_playing() / stop_playing()` | Audio | V | | Audio playback control |
| `push_audio_sample(samples)` | Audio | V | | Push samples to playback buffer |
| `is_playing -> bool` | Audio | V | | Playback active? |
| `play_sound(file_path)` | Sound | | V | Play a sound file (wav/mp3) |
| `is_sound_playing() -> bool` | Sound | | V | Sound file playback active? |
| `stop_sound()` | Sound | | V | Stop sound file playback |
| `start_recording() / stop_recording()` | Recording | | V | Microphone recording control |
| `get_audio_sample() -> ndarray` | Recording | | V | Get recorded audio buffer |
| `is_recording -> bool` | Recording | | V | Recording active? |
| `get_doa() -> float` | Spatial | | V | Direction of arrival (rad) |
| `close()` | Lifecycle | V | | Release resources |

### 3.3 PersonDetectorInterface (person_detector.py)

Person detection abstraction with Mock and YOLO implementations.

| Method / Property | Category | Description |
|-------------------|----------|-------------|
| `start()` | Lifecycle | Start detection |
| `stop()` | Lifecycle | Stop detection |
| `is_running -> bool` | Lifecycle | Running state |
| `person_visible -> bool` | Query | At least one person visible? |
| `person_count -> int` | Query | Number of detected persons |
| `person_positions -> list[tuple]` | Query | Normalized (0~1) positions |
| `get_person_absence_duration() -> float` | Query | Seconds since last person seen |
| `update(dt)` | Tick | Per-frame update (sim loop) |

**MockPersonDetector** adds `inject_person(name, pos)`, `remove_person(name)`, `get_persons()`.

**YOLOPersonDetector** requires `MediaInterface` for frames, runs YOLO in background thread.

### 3.4 ProactiveTrigger (proactive.py)

Monitors person events and idle state to proactively initiate conversation.

| Method / Property | Category | Description |
|-------------------|----------|-------------|
| `start() / stop()` | Lifecycle | Trigger lifecycle |
| `is_running -> bool` | Lifecycle | Running state |
| `enabled` | Config | Enable/disable toggle |
| `greet_cooldown -> float` | Config | Greet cooldown (seconds) |
| `idle_timeout -> float` | Config | Idle trigger timeout (seconds) |
| `reset_idle_timer()` | Control | Reset idle timer on user interaction |
| `update(dt)` | Tick | Per-frame idle check |
| `on_trigger` | Callback | `callback(trigger_type, prompt_text)` |

Trigger types: `greet`, `farewell`, `idle`.

### 3.5 New Module: interpolation.py

Smooth trajectory interpolation engine for joint movements.

| Class / Function | Description |
|------------------|-------------|
| `InterpolationMethod` | Enum: LINEAR, MINIMUM_JERK, CUBIC |
| `interpolate(start, end, t, method)` | Compute interpolated value at time t in [0,1] |
| `JointTrajectory` | Manages a multi-joint interpolation over duration |

### 3.6 New Module: motion.py

Motion recording and playback system.

| Class / Function | Description |
|------------------|-------------|
| `Move` | Dataclass holding recorded joint trajectory + metadata |
| `MotionRecorder` | Records joint positions at fixed interval into Move |
| `MotionPlayer` | Plays back a Move with speed control |
| `Move.save(path)` / `Move.load(path)` | Serialize / deserialize to JSON |

### 3.7 New Module: utils.py

Shared utility functions.

| Function | Description |
|----------|-------------|
| `create_head_pose(yaw, pitch, roll, degrees) -> ndarray(4,4)` | Build head pose matrix (extracted from expression.py) |
| `pose_to_euler(pose) -> (yaw, pitch, roll)` | Extract Euler angles from 4x4 matrix |
| `clamp(value, min_val, max_val)` | Numeric clamp helper |

## 4. Implementation Phases

| Phase | Scope | Key Modules | Owner |
|-------|-------|-------------|-------|
| **1A** | Interpolation + goto_target + get_joint_positions + utils | interpolation.py, utils.py, robot_interface.py, mock_robot.py | api-engineer |
| **1B** | Gaze control (look_at_image, look_at_world) | robot_interface.py, mock_robot.py | api-engineer |
| **1C** | Lifecycle (wake/sleep, motor enable, gravity comp) | robot_interface.py, mock_robot.py | api-engineer |
| **2A** | Sound file playback (play_sound, stop_sound) | robot_interface.py, mock_media.py | api-engineer |
| **2B** | Microphone recording + DOA | robot_interface.py, mock_media.py | api-engineer |
| **2C** | IMU data | robot_interface.py, mock_robot.py | api-engineer |
| **3** | Motion recording/playback | motion.py, robot_interface.py, mock_robot.py | api-engineer |
| **4A** | REST API + WebSocket extension | web_server.py | fullstack |
| **4B** | Frontend UI panels | web/index.html | fullstack |
| **4C** | Simulation loop integration | web_server.py, visualizer.py | fullstack |
| **4D** | Expression engine upgrade | expression.py | fullstack |
| **5A** | PersonDetectorInterface + Mock + YOLO | person_detector.py | api-engineer |
| **5B** | ProactiveTrigger + AIBrain.inject | proactive.py, ai_brain.py | api-engineer |
| **5C** | Perception Web API + WebSocket + Frontend | web_server.py, web/index.html | fullstack |
| **5D** | QA: unit + integration + regression + web tests | tests/ | qa |

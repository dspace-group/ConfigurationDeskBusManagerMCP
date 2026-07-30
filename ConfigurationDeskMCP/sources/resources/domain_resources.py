# -*- coding: utf-8 -*-
"""MCP Resources for ConfigurationDesk MCP Server."""

import json

from configurationdesk_com_bridge import get_connection
from sources.server.app import mcp
from sources.services.bus_element_properties import known_properties as known_bus_element_properties
from sources.services.function_port_properties import known_aliases
from sources.utils.logger import get_logger

logger = get_logger(__name__)

_AUTOMATION_GUIDE = """\
# ConfigurationDesk Automation Guide

## Overview
ConfigurationDesk provides a COM-based automation API for HIL (Hardware-in-the-Loop) and SIL (Software-in-the-Loop) workflows. This API allows programmatic control of ConfigurationDesk to create projects, add applications, import models, configure buses, assign hardware, and build or deploy a test system configuration. This MCP server wraps these capabilities as tools.

## Related resources
- `configurationdesk://reference/tool-selection` — pick the correct tool for an intent (READ THIS to avoid common confusions).
- `configurationdesk://reference/valid-values` — controlled vocabularies for tool arguments (part, platform_type, bus_type, element_type, baud rates).
- `configurationdesk://reference/error-recovery` — error codes, retryable flags, and recovery actions.
- `configurationdesk://reference/xpath` — element hierarchy and XPath patterns.
- `configurationdesk://reference/features` — full bus-feature catalog.
- `configurationdesk://reference/function-port-properties` and `.../bus-element-properties` — property name catalogs.

## Typical Workflow

1. **Start ConfigurationDesk** — Use `start_configurationdesk` to launch the application
2. **Set Project Root** — Use `set_project_root` to configure where projects are stored
3. **Create/Open Project** — Use `create_project` or `open_project`
4. **Add Application** — Use `add_application` within the project
5. **Add Model** — Use `add_model` to import Simulink (.slx/.mdl), SIC, or BSC files
6. **Analyze Models** — Use `analyze_models` to detect ports and interfaces
7. **Add Communication Matrix** — Use `add_communication_matrix` for ARXML/DBC/LDF files
8. **Configure Bus** — Use `create_bus_configuration` and `assign_matrix_to_bus_config`
9. **Create Application Process** — Use `create_application_process` (creates an application process providing a default periodic task; pass `bus_config_names` to also assign it to bus configurations) or `create_preconfigured_application_process` (model-driven)
10. **Configure Function Ports** — Use `set_function_port_property` for IsMappable etc.
10b. **Configure Feature/Matrix Properties** — Use `set_bus_config_element_property` for feature nodes like 'Countdown start value' or 'Overwrite value', and `set_matrix_element_property` for matrix properties like PDU/signal 'Length' or 'Initial value'.
11. **Connect Ports** — Use `auto_connect_matching_io_function_blocks_to_model_ports` for automatic name-based matching
12. **Add Hardware** — Use `add_hardware_platform` to register supported hardware systems
13. **Bus Access Assignment** — Complete workflow:
    a. Create I/O function block: `create_io_function_block` (CAN/LIN/Ethernet)
    b. Set baud rate: `set_io_function_block_property` (e.g., BaudRate=19200)
    c. Assign bus access: `assign_bus_access` to link requests to function block
    d. Assign channel set: `assign_channel_set` or `auto_assign_channel_set`
    e. Or use `assign_hardware_automatically` for automatic assignment
14. **Check Conflicts** — Use `check_conflicts` to verify configuration
15. **Build & Deploy** — Use `build_application` to compile, download, and start

## Bus Configuration Workflow

1. Add communication matrix files (ARXML, DBC, LDF)
2. Create bus configurations
3. Assign matrix ECUs to bus configurations (restbus simulation)
4. Add features (RawDataAccess, TriggerAccess, CommunicationControllerEnable)
5. Generate bus simulation containers

## Bus Access Assignment Workflow (Critical)

Bus access assignment connects bus configurations to physical hardware channels.
This requires multiple steps:

1. **Create an I/O function block** — `create_io_function_block` with the bus type
2. **Set baud rate** — `set_io_function_block_property` to match the cluster requirement
3. **Assign bus access** — `assign_bus_access` to set the function block on bus access requests
4. **List available channel sets** — `list_assignable_channel_sets` to see hardware options
5. **Assign channel set** — `assign_channel_set` (manual) or `auto_assign_channel_set` (auto)
6. **Verify** — `check_conflicts` to ensure no remaining hardware assignment issues

Alternatively, use `assign_hardware_automatically` to let ConfigurationDesk handle
all hardware assignments at once (steps 4-5).

## Algorithms API

The Algorithms API provides powerful automation methods:
- `assign_channel_set` / `auto_assign_channel_set` — Hardware channel assignment
- `assign_hardware_automatically` — Auto-assign all hardware at once
- `auto_connect_matching_io_function_blocks_to_model_ports` — Auto-wire I/O to model ports
- `create_preconfigured_application_process` — Auto-create application process for a specific behavior model
- `check_conflicts` — Export and parse all configuration conflicts

## XPath Queries
Bus and matrix elements can be queried using XPath expressions:
- `//BusEcu` — Find all ECUs
- `//BusFrame` — Find all frames
- `//BusISignalIPdu` — Find all signal PDUs
- `//BusCommunicationMatrix` — Find all matrices

## Hardware Platforms
SCALEXIO, MicroAutoBox III, and MicroLabBox II platforms are registered by
address and scanned to create the hardware topology. Use `list_platforms` to see
registered hardware. VEOS is NOT a platform — use `add_application_processing_unit`.
"""

_TOOL_CATEGORIES = """\
# ConfigurationDesk MCP Tool Categories

## Application Lifecycle
- `start_configurationdesk` — Start and connect to ConfigurationDesk
- `stop_configurationdesk` — Close ConfigurationDesk
- `save_project` — Save current project
- `get_application_status` — Get connection and project status
- `undo` / `redo` — Undo/redo last action

## Project Management
- `create_project` / `open_project` / `close_project` / `remove_project`
- `list_projects` — List all projects
- `set_project_root` / `get_project_path`
- `backup_project` / `open_project_from_backup`

## Application Management
- `add_application` / `activate_application` / `remove_application`
- `list_applications` — List apps in project

## Model Topology
- `add_model` / `replace_model` / `remove_model`
- `analyze_models` — Analyze model ports and interfaces
- `create_application_process` — Create an application process providing a default periodic task (model-less; optional bus-config assignment)
- `list_models` — List all models

## Hardware Topology
- `add_hardware_platform` — Register and scan SCALEXIO, MicroAutoBox III, or MicroLabBox II by address
- `import_hardware_topology` — Import from HTFX file
- `scan_hardware` / `remove_hardware` / `add_hardware_element`
- `list_platforms` / `refresh_platforms`

## Bus Configuration
- `create_bus_configuration` / `remove_bus_configuration` / `list_bus_configurations`
- `assign_matrix_to_bus_config` / `assign_ecu_to_bus_config`
- `add_feature_to_bus_element` / `remove_bus_config_elements`
- `generate_bus_containers` / `find_bus_config_elements`
- `assign_bus_config_to_application_process` / `set_function_port_property`

## Communication Matrix
- `add_communication_matrix` / `remove_communication_matrix`
- `list_matrices` / `find_matrix_elements`

## Build Management
- `build_application` — Build, download, and start
- `get_build_result` — Return the latest build result path

## Working Views & Conflicts
- `create_working_view` / `list_working_views` / `remove_working_view`
- `clear_all_working_views` / `export_working_view`
- `check_conflicts` — Detect and report configuration conflicts

## Configuration
- `list_configuration` — Show application configuration tree

## Hardware I/O Function Blocks & Bus Access
- `create_io_function_block` — Create CAN/LIN/Ethernet I/O function block (NOT for bus configurations)
- `set_io_function_block_property` — Set properties (e.g., BaudRate) on I/O function blocks
- `list_io_function_block_properties` — Discover available properties on an I/O function block
- `list_bus_access_requests` — List bus access requests across configurations
- `assign_bus_access` — Assign bus access requests to an I/O function block
- `list_assignable_channel_sets` — List available hardware channel sets
- `assign_channel_set` — Assign a specific channel set to a function block
- `auto_assign_channel_set` — Auto-assign channel set to a function block
- `assign_hardware_automatically` — Auto-assign all hardware to all function blocks
- `auto_connect_matching_io_function_blocks_to_model_ports` — Auto-wire I/O function blocks to model ports
- `create_preconfigured_application_process` — Auto-create application process for one model
"""


_XPATH_REFERENCE = """\
# XPath Reference for ConfigurationDesk Bus Manager

## Overview
XPath is used to navigate and query bus configuration and communication matrix elements.
ConfigurationDesk supports XPath 1.0 standard. Element names are CASE SENSITIVE.

## Bus Configuration Hierarchy (for find_bus_config_elements)

```
/BusConfiguration
  /BusConfigurationEnableGlobal
    /FunctionPort
  /BusConfigurationPartSimulatedEcus        <- Restbus simulation (most common)
    /BusCommunicationMatrix
      /BusEcu
        /BusCanCommunicationController
          /FunctionPort (Communication Controller Enable)
        /BusLinCommunicationController
          /FunctionPort (Lin Schedule Table, Communication Controller Enable)
        /BusISignalIPdu                     <- Most common PDU type
          /BusISignal
            /FunctionPort (ISignal Value, Counter Signal)
          /BusISignalGroup
            /FunctionPort (ISignal Group E2E Protection Status)
          /FunctionPort (PDU Enable, Frame Access, Raw Data, Rx Status, Trigger, etc.)
          /EventPort (Rx Interrupt)
        /BusContainerIPdu                   <- Container PDUs (AUTOSAR 4.2+)
          /FunctionPort
        /BusMultiplexedIPdu                 <- Multiplexed PDUs
          /FunctionPort
        /BusSecuredIPdu                     <- SecOC protected PDUs
          /FunctionPort
        /BusGeneralPurposeIPdu
          /FunctionPort
        /BusNmPdu
        /BusNPdu
        /BusUserDefinedIPdu
  /BusConfigurationPartInspection           <- Monitor/inspect RX traffic
    /BusCommunicationMatrix
      (same structure as Simulated ECUs)
  /BusConfigurationPartManipulation         <- Override/manipulate TX traffic
    /BusCommunicationMatrix
      (same structure as Simulated ECUs)
  /BusConfigurationPartGateways             <- Frame gateway routing
    /BusFrameGateway
      /BusFrameGatewayDirection
        /FunctionPort
      /BusFrameGatewayFilter
        /BusFilterControlGateways
          /FunctionPort
        /BusCanFilterRule
  /BusConfigurationPartBusAccessRequests    <- Hardware channel assignment
    /BusCommunicationMatrix
      /BusSystemCan
        /BusCanCommunicationCluster
          /BusCanPhysicalChannel
            /BusAccessRequestSimulatedEcus
              /FunctionBlock
            /BusAccessRequestInspection
              /FunctionBlock
            /BusAccessRequestManipulation
              /FunctionBlock
      /BusSystemLin
        /BusLinCommunicationCluster
          /BusLinPhysicalChannel
            /BusAccessRequestSimulatedEcus
              /FunctionBlock
    /BusFrameGateway
      /BusCanFrameGatewayCluster
        /BusAccessRequestGateways
          /FunctionBlock
```

## Communication Matrix Hierarchy (for find_matrix_elements)

### By Clusters view:
```
/BusCommunicationMatrix
  /BusCanCommunicationCluster
    /BusCanPhysicalChannel
      /BusISignalIPdu
        /BusISignal
  /BusLinCommunicationCluster
    /BusLinPhysicalChannel
      /BusISignalIPdu
        /BusISignal
  /BusEthernetCommunicationCluster
    /BusEthernetPhysicalChannel
```

### By ECUs view:
```
/BusCommunicationMatrix
  /BusEcu
    /TX
      /BusISignalIPdu
        /BusISignal
    /RX
      /BusISignalIPdu
        /BusISignal
```

## Common XPath Patterns

### Finding elements:
| Goal | XPath |
|------|-------|
| All ECUs | `//BusEcu` |
| Specific ECU | `//BusEcu[@Name="ECU_A"]` |
| All CAN clusters | `//BusCanCommunicationCluster` |
| All LIN clusters | `//BusLinCommunicationCluster` |
| All TX PDUs | `//BusISignalIPdu[@Direction="TX"]` |
| All RX PDUs | `//BusISignalIPdu[@Direction="RX"]` |
| PDU by name | `//BusISignalIPdu[@Name="EngineData"]` |
| Signal by name | `//BusISignal[@Name="EngineSpeed"]` |
| All function ports | `//FunctionPort` |
| Container PDUs | `//BusContainerIPdu` |
| Multiplexed PDUs | `//BusMultiplexedIPdu` |
| Secured PDUs | `//BusSecuredIPdu` |

### Bus configuration scoped queries:
| Goal | XPath |
|------|-------|
| PDUs in specific config | `/BusConfiguration[@Name="MyConfig"]/BusConfigurationPartSimulatedEcus//BusISignalIPdu` |
| TX PDUs in Simulated ECUs | `/BusConfiguration/BusConfigurationPartSimulatedEcus//BusISignalIPdu[@Direction="TX"]` |
| ECU's PDUs | `//BusEcu[@Name="ECU_A"]//BusISignalIPdu` |
| PDU parent element | `//*[@Name="MyPdu" and @Direction="TX"]/parent::*` |
| All elements 2 levels below CAN | `//BusSystemCan/*/*` |

### Attribute filters:
- `[@Name="value"]` — exact name match
- `[@Direction="TX"]` or `[@Direction="RX"]` — direction filter
- `[not(@Direction="TX")]` — negation
- Boolean operators: `and`, `or`, `not()`
- Comparisons: `=`, `!=`, `<`, `>`, `<=`, `>=`

### Wildcards and axes:
- `*` — any element at current level
- `//` — any descendant
- `..` or `parent::*` — parent element
- `/*[1]` — first child
"""

_FEATURE_REFERENCE = """\
# Bus Configuration Feature Reference

## Overview
Features add run-time capabilities to bus configuration elements (PDUs, signals,
controllers). Features are added with `add_feature_to_bus_element` using the exact
`feature_name` string. Each feature creates FunctionPorts that can be connected to
model ports.

The feature_name strings below are the automation-API type names verified against
the server implementation (the `add_feature_to_bus_element` contract and the COM
bridge resolver). Pass them exactly as written.

## Signal-level features (apply to `BusISignal`)
| feature_name | Purpose | Part |
|---|---|---|
| `BusISignalValueAccess` | Read/write physical signal values (MOST COMMON). In port for TX, Out port for RX. | Simulated ECUs |
| `BusISignalValueInspection` | Inspect received signal values. | Inspection |
| `BusISignalOverwriteValueManipulation` | Temporarily/permanently overwrite a signal value. | Manipulation |
| `BusISignalOffsetValueManipulation` | Add an offset to a signal value. | Manipulation |
| `BusCounterSignalAccess` | Configure ISignals as counter (alive) signals. | Simulated ECUs |

## PDU-level features (apply to `BusISignalIPdu`, `BusContainerIPdu`, `BusMultiplexedIPdu`)
| feature_name | Purpose | Direction |
|---|---|---|
| `BusPduEnableAccess` | Enable/disable PDU transmission at run time. | TX |
| `BusPduTriggerAccess` | Trigger PDU transmission from the model. | TX |
| `BusPduCyclicTimingControlAccess` | Control cyclic transmission timing at run time. | TX |
| `BusPduRawDataAccess` | Access the PDU payload in raw byte form. | TX and RX |
| `BusFrameAccess` | Access CAN frame settings (ID, length, raw bytes, FD flags, trigger). Cannot be combined with other PDU/ISignal features on the same PDU. | TX and RX |
| `BusPduRxStatusAccess` | PDU reception status (Simulated ECUs part). | RX |
| `BusPduRxStatusInspection` | PDU reception status (Inspection part). | RX |
| `BusPduUserCodeAccess` | Custom user-code hook for PDU processing. | TX and RX |
| `BusSuspendFrameTransmissionManipulation` | Temporarily/permanently suspend transmission of the frame containing the PDU. | Manipulation |
| `BusFrameLengthManipulation` | Manipulate the transmitted frame length (with padding). | Manipulation |

## Controller-level features (apply to `BusCanCommunicationController` / `BusLinCommunicationController`)
| feature_name | Purpose |
|---|---|
| `BusCommunicationControllerEnableAccess` | Enable/disable the communication controller at run time. |
| `BusCommunicationControllerLinScheduleTableAccess` | Switch LIN schedule tables at run time (LIN only). |

## Bus-configuration-level features (apply to `BusConfiguration`)
| feature_name | Purpose |
|---|---|
| `BusConfigurationEnableAccess` | Enable/disable the entire bus configuration at run time. |

## Global Time Synchronization (GTS) features
| feature_name | Purpose |
|---|---|
| `BusGtsTransmissionControlAccess` | Control transmission of time-sync messages. |
| `BusGtsTimeBaseDataAccess` | Access time-base data (time, status, user bytes). |

## Additional features present in the product UI
These features exist in ConfigurationDesk/Bus Manager (per the product
documentation) but their exact automation-API `feature_name` string is NOT part
of the server's verified set. Do NOT guess the string — if you need one of these,
confirm the exact name from the ConfigurationDesk automation API before use:
- Suspend PDU Transmission (manipulation)
- PDU Length, Frame Capture Data
- PDU RX Interrupt (creates an EventPort on a CAN RX PDU)
- Communication Controller LIN Wake-Up
- GTS Validation (on an RX global time domain)
- Frame Gateway Direction, Filter Control (gateway routing)

## Applicability rules
1. TX PDUs: PduEnable, PduTrigger, PduCyclicTimingControl, PduRawData, FrameAccess, UserCode; (Manipulation) SuspendFrameTransmission, FrameLength.
2. RX PDUs: PduRawData, FrameAccess, PduRxStatus(Access|Inspection), UserCode.
3. Signals: ISignalValueAccess (TX=In, RX=Out), ISignalValueInspection; (Manipulation) OverwriteValue, OffsetValue; CounterSignal.
4. Controllers: CommunicationControllerEnable; LinScheduleTable (LIN only).
5. Inspection part uses `BusPduRxStatusInspection` / `BusISignalValueInspection`, NOT the `*Access` variants.
6. `BusFrameAccess` conflicts with other PDU/ISignal features on the same PDU.

## Usage examples
```
# ISignal Value for all signals (most common)
add_feature_to_bus_element(feature_name="BusISignalValueAccess", element_type="BusISignal")

# Frame Access on a specific TX PDU
add_feature_to_bus_element(feature_name="BusFrameAccess",
    element_xpath='//BusISignalIPdu[@Name="EngineData" and @Direction="TX"]')

# PDU Enable on all TX PDUs in a config
add_feature_to_bus_element(feature_name="BusPduEnableAccess",
    bus_config_name="CAN_Config", element_xpath='//BusISignalIPdu[@Direction="TX"]')

# Communication Controller Enable on a CAN controller
add_feature_to_bus_element(feature_name="BusCommunicationControllerEnableAccess",
    element_type="BusCanCommunicationController")

# Bus Configuration Enable (config-level)
add_feature_to_bus_element(feature_name="BusConfigurationEnableAccess",
    bus_config_name="CAN_Config")
```
"""

_WORKFLOW_EXAMPLES = """\
# ConfigurationDesk Workflow Examples

These examples show DISTINCT patterns (multi-cluster, LIN, frame access,
inspection/manipulation, GTS) that complement the prompts. For the plain CAN
restbus flow, use the `bus_manager_restbus_simulation` prompt. For baud rates and
other argument values, see `configurationdesk://reference/valid-values`.

## Example 2: CAN-FD with Multiple Clusters

```
# Load matrix with multiple CAN-FD clusters
add_communication_matrix(path="D:/Databases/canfd_network.arxml")

# Create separate bus configs per cluster
create_bus_configuration(name="BC_EngineCluster")
create_bus_configuration(name="BC_BodyCluster")

# Assign specific ECUs to each config
assign_matrix_to_bus_config(bus_config_name="BC_EngineCluster",
    matrix_xpath="//BusCanCommunicationCluster[@Name='EngineCluster']")
assign_matrix_to_bus_config(bus_config_name="BC_BodyCluster",
    matrix_xpath="//BusCanCommunicationCluster[@Name='BodyCluster']")

# Create function blocks per cluster with CAN-FD baud rates
create_io_function_block(name="CANFD_Engine", bus_type="CAN")
set_io_function_block_property(function_block_name="CANFD_Engine",
    property_name="BaudRate", value="500000")
set_io_function_block_property(function_block_name="CANFD_Engine",
    property_name="DataPhaseBaudRate", value="4000000")

create_io_function_block(name="CANFD_Body", bus_type="CAN")
set_io_function_block_property(function_block_name="CANFD_Body",
    property_name="BaudRate", value="500000")
set_io_function_block_property(function_block_name="CANFD_Body",
    property_name="DataPhaseBaudRate", value="4000000")

# Assign bus access per cluster
assign_bus_access(function_block_name="CANFD_Engine", bus_config_name="BC_EngineCluster")
assign_bus_access(function_block_name="CANFD_Body", bus_config_name="BC_BodyCluster")
```

## Example 3: LIN Bus Configuration

```
add_communication_matrix(path="D:/Databases/lin_door.ldf")

create_bus_configuration(name="LIN_Door")
assign_ecu_to_bus_config(bus_config_name="LIN_Door", ecu_xpath="//BusEcu")

# Add LIN-specific features
add_feature_to_bus_element(feature_name="BusCommunicationControllerLinScheduleTableAccess",
    bus_config_name="LIN_Door", element_type="BusLinCommunicationController")
add_feature_to_bus_element(feature_name="BusCommunicationControllerEnableAccess",
    bus_config_name="LIN_Door", element_type="BusLinCommunicationController")

# LIN function block with typical baud rate
create_io_function_block(name="LIN_Door_Channel", bus_type="LIN")
set_io_function_block_property(function_block_name="LIN_Door_Channel",
    property_name="BaudRate", value="19200")
```

## Example 4: Adding Frame Access for Raw Data Monitoring

```
# Add Frame Access to specific TX PDUs for raw data transmission
add_feature_to_bus_element(feature_name="BusFrameAccess",
    bus_config_name="CAN_Config",
    element_xpath='//BusISignalIPdu[@Direction="TX"]')

# Frame Access ports: Trigger, Length, Raw Data, Identifier,
# Extended Addressing, CAN FD Frame Support, Bit Rate Switch

# Add Frame Access to RX PDUs for reception monitoring
add_feature_to_bus_element(feature_name="BusFrameAccess",
    bus_config_name="CAN_Config",
    element_xpath='//BusISignalIPdu[@Direction="RX"]')

# RX Frame Access ports: State, Length, Raw Data, Identifier,
# Extended Addressing, CAN FD Frame Support, Bit Rate Switch
```

## Example 5: Bus Configuration with Inspection and Manipulation

```
# Create config with all three parts populated
create_bus_configuration(name="FullConfig")

# Assign ECUs to Simulated ECUs part (automatic)
assign_ecu_to_bus_config(bus_config_name="FullConfig", ecu_xpath="//BusEcu")

# The above also auto-populates Inspection (RX) and Manipulation (TX)

# Add PDU Rx Status to Inspection part
add_feature_to_bus_element(feature_name="BusPduRxStatusInspection",
    bus_config_name="FullConfig",
    element_xpath='/BusConfiguration[@Name="FullConfig"]/BusConfigurationPartInspection//BusISignalIPdu')

# Add PDU Enable to Manipulation TX PDUs
add_feature_to_bus_element(feature_name="BusPduEnableAccess",
    bus_config_name="FullConfig",
    element_xpath='/BusConfiguration[@Name="FullConfig"]/BusConfigurationPartManipulation//BusISignalIPdu[@Direction="TX"]')
```

## Example 6: Global Time Synchronization (GTS)

```
# Load GTS-enabled communication matrix
add_communication_matrix(path="D:/Databases/gts_clusters.dbc")
create_bus_configuration(name="GTS_Config")
assign_ecu_to_bus_config(bus_config_name="GTS_Config", ecu_xpath="//BusEcu")

# Add GTS features
add_feature_to_bus_element(feature_name="BusGtsTransmissionControlAccess",
    bus_config_name="GTS_Config")
add_feature_to_bus_element(feature_name="BusGtsTimeBaseDataAccess",
    bus_config_name="GTS_Config")

# Add Frame Access for GTS frames
add_feature_to_bus_element(feature_name="BusFrameAccess",
    bus_config_name="GTS_Config",
    element_xpath='//BusISignalIPdu[@Name="GTS_Frame*"]')
```

## Common Baud Rates Reference
See `configurationdesk://reference/valid-values` for baud rates, `part`,
`bus_type`, `platform_type`, `element_type`, and build-flag values.
"""


_TOOL_SELECTION_REFERENCE = """\
# Tool Selection & Disambiguation Reference

Use this to pick the correct tool for an intent and avoid the most common
confusions. When a request names an exact PDU/signal, keep that scope literal —
do NOT widen it to a whole-ECU assignment unless whole-ECU population was
explicitly requested.

## Domain hierarchy (what each artifact is)
| Artifact | What it is | Create/edit with |
|---|---|---|
| Communication Matrix | Network definition file (.arxml/.dbc/.ldf) | `add_communication_matrix` |
| Bus Configuration | Simulation setup (create, assign ECUs, add features) | `create_bus_configuration` |
| Bus Config Element / Feature Node | Run-time value on a bus-config element (countdown, overwrite, offset, frame-length) | `set_bus_config_element_property` |
| Function Port | Port interface (IsMappable, IsTestAutomationSupportEnabled, InitialValue) | `set_function_port_property` |
| Matrix Element | Communication-database value (PDU/signal Length, signal Initial value) | `set_matrix_element_property` |
| I/O Function Block | Hardware access block + settings (BaudRate) | `create_io_function_block` / `set_io_function_block_property` |
| Bus Simulation Container (.bsc) | Compiled artifact for VEOS/explicit delivery | `generate_bus_containers` |

## Intent → tool
| User intent | Correct tool | NOT |
|---|---|---|
| "Create a bus configuration" | `create_bus_configuration` | `create_io_function_block` |
| "Create an I/O / function block" | `create_io_function_block` | `create_bus_configuration` |
| "Load .arxml/.dbc/.ldf database" | `add_communication_matrix` | anything else |
| "Assign an ECU to a bus config" | `assign_ecu_to_bus_config` | `assign_matrix_to_bus_config` |
| "Assign an EXACT PDU/signal" | `assign_matrix_to_bus_config` (precise matrix_xpath) | `assign_ecu_to_bus_config` |
| "Add a signal/PDU/controller feature" | `add_feature_to_bus_element` | — |
| "Set countdown / overwrite / offset / frame-length feature value" | `set_bus_config_element_property` | `set_function_port_property` |
| "Set signal/PDU Length or matrix Initial value" | `set_matrix_element_property` | `set_bus_config_element_property` |
| "Set IsMappable / InitialValue on a port" | `set_function_port_property` | `set_bus_config_element_property` |
| "Set the baud rate" | `set_io_function_block_property` | any bus-config tool |
| "Link bus access requests to a function block" | `assign_bus_access` | — |
| "Generate BSC / bus containers" | `generate_bus_containers` (only when asked) | — |

## Guardrails
- Do NOT call `generate_bus_containers` just to inspect or make function ports
  visible — assigned features already expose them. Use `find_bus_config_elements`
  (xpath="//FunctionPort") and `set_function_port_property` directly.
- If `set_function_port_property` fails, re-run `find_bus_config_elements` to
  verify the actual ports/features. `generate_bus_containers` is NOT recovery.
- Feature-node vs function-port vs matrix vs hardware property setters are four
  DIFFERENT tools — see the table above.
"""

_VALID_VALUES_REFERENCE = """\
# Controlled Vocabularies — Valid Argument Values

Use these exact values for tool arguments. Do NOT invent enum-like values.
For feature names see `configurationdesk://reference/features`; for XPath element
names see `configurationdesk://reference/xpath`.

## `part` (assign_ecu_to_bus_config, assign_matrix_to_bus_config, add_feature_to_bus_element)
- `simulated` (aliases: `simulated ecus`, `simulatedecus`) — Simulated ECUs (restbus). Most common.
- `inspection` — monitor received (RX) traffic.
- `manipulation` — override transmitted (TX) traffic.
- `gateways` (alias: `gateway`) — frame gateway routing.
- omit / `all` — assign to all three standard parts (Simulated ECUs, Inspection, Manipulation) at once.

## `platform_type` (add_hardware_platform)
- `SCALEXIO`
- `MicroAutoBox III`
- `MicroLabBox II`
(VEOS is NOT a platform — use `add_application_processing_unit`.)

## `bus_type` (create_io_function_block)
- `CAN`
- `LIN`
- `Ethernet`

## Common `element_type` values (find_matrix_elements, find_bus_config_elements, add_feature_to_bus_element)
- `BusEcu`
- `BusISignal`
- `BusISignalIPdu`
- `BusContainerIPdu`
- `BusMultiplexedIPdu`
- `BusCanCommunicationController`
- `BusLinCommunicationController`
- `BusCanCommunicationCluster`
- `BusLinCommunicationCluster`
- `FunctionPort`

## Model file extensions (add_model)
- `.slx` / `.mdl` — Simulink (require `analyze_models`).
- `.sic` — Simulink implementation container (pre-analyzed).
- `.bsc` — Bus Simulation Container.

## Communication matrix file extensions (add_communication_matrix)
- `.arxml` (AUTOSAR), `.dbc` (CAN), `.ldf` (LIN).

## Baud rates (set_io_function_block_property, property_name="BaudRate")
| Bus | Value | Notes |
|---|---|---|
| CAN | 500000 | High-speed, MOST COMMON |
| CAN | 250000 / 125000 | Medium / low speed |
| CAN-FD data phase | 2000000 / 4000000 / 5000000 | set `DataPhaseBaudRate` in addition to BaudRate |
| LIN | 19200 | Standard, MOST COMMON |
| LIN | 9600 | Low speed |
| Ethernet | 100000000 | 100 Mbit |

## `build_application` arguments
- `download` (bool) — download to hardware (false for offline builds).
- `start` (bool) — start after download.
- `unload` (bool) — unload a previously loaded application first.
There is NO `build_model` or `target_architecture` argument.

## Boolean-ish string arguments
Pass booleans as real booleans where the schema expects them (e.g. IsMappable=true).
"""

_ERROR_RECOVERY_REFERENCE = """\
# Error Codes & Recovery Reference

Every failing tool returns an envelope with `success=false`, `error_code`,
`retryable`, `recovery_hint`, and often `next_action`. ALWAYS read those fields.
Do NOT retry a call with `retryable=false` — follow its `recovery_hint` instead.

## Connection / COM errors
| error_code | retryable | Recovery |
|---|---|---|
| `COM_DISCONNECTED` | yes | Call `start_configurationdesk` to re-establish the connection, then retry. |
| `COM_SERVER_UNAVAILABLE` | yes | Call `start_configurationdesk` to start ConfigurationDesk. |
| `COM_SERVER_EXEC_FAILURE` | yes | ConfigurationDesk could not start — check the installation. |
| `COM_TIMEOUT` | yes | Retry once after a short delay. If it repeats, stop and ask the user. |
| `COM_UI_BLOCKING` | yes | A modal dialog is open in ConfigurationDesk — tell the user to dismiss it, then retry. |
| `COM_RPC_ERROR` | yes | Check the ConfigurationDesk connection, then retry once. |
| `COM_MEMBER_NOT_FOUND` | no | A prerequisite step is missing. Call `get_application_status`; ensure order (e.g. create_project before add_application). |

## Bridge / lifecycle errors
| error_code | retryable | Recovery |
|---|---|---|
| `BRIDGE_PRECONDITION` | no | A required state is missing. Call `get_application_status`; use the `next_action` tool from the envelope. |
| `BRIDGE_CIRCUIT_OPEN` | no | Too many reconnection failures. Call `stop_configurationdesk` then `start_configurationdesk`. |
| `BRIDGE_NOT_INSTALLED` | no | ConfigurationDesk is not installed on this machine. Stop. |
| `BRIDGE_UNKNOWN` | no | Unexpected failure. Report the message to the user; do not blindly retry. |

## Precondition `next_action` map
| Missing precondition | next_action tool |
|---|---|
| connection | `start_configurationdesk` |
| project | `create_project` |
| application | `add_application` |
| bus_config | `create_bus_configuration` |
| model | `add_model` |
| application_process | `create_application_process` |

## Common domain errors
| error_code | Meaning / fix |
|---|---|
| `INVALID_VALUE_TYPE` | The value passed to a property setter is the wrong type — check the property catalog resources for the expected type. |
| `FUNCTION_PORT_PROPERTY_NOT_FOUND` | The named function-port property/port does not exist. Re-run `find_bus_config_elements` to verify the actual port names — do NOT call `generate_bus_containers` as recovery. |

## Retry policy
Retry at most once, and only for `retryable=true` codes. On a second failure or
any `retryable=false` code, STOP and explain the failure to the user.
"""


@mcp.resource(
    "configurationdesk://reference/tool-selection",
    name="tool_selection_reference",
    title="Tool Selection Reference",
    description="Disambiguation reference: pick the correct tool for a given intent (bus config vs I/O block, matrix vs feature vs port property setters) and avoid the most common confusions",
    mime_type="text/markdown",
)
def get_tool_selection_reference() -> str:
    return _TOOL_SELECTION_REFERENCE


@mcp.resource(
    "configurationdesk://reference/valid-values",
    name="valid_values_reference",
    title="Valid Values Reference",
    description="Controlled vocabularies for tool arguments: part, platform_type, bus_type, element_type, file extensions, baud rates, and build flags — use to avoid invalid/hallucinated argument values",
    mime_type="text/markdown",
)
def get_valid_values_reference() -> str:
    return _VALID_VALUES_REFERENCE


@mcp.resource(
    "configurationdesk://reference/error-recovery",
    name="error_recovery_reference",
    title="Error Recovery Reference",
    description="Error code catalog with retryable flags and recovery actions (COM/connection, bridge/lifecycle, precondition next_action map, common domain errors) plus the retry policy",
    mime_type="text/markdown",
)
def get_error_recovery_reference() -> str:
    return _ERROR_RECOVERY_REFERENCE


@mcp.resource(
    "configurationdesk://guides/automation",
    name="automation_guide",
    title="ConfigurationDesk Automation Guide",
    description="ConfigurationDesk automation workflow guide with step-by-step instructions for project setup, bus configuration, and build",
    mime_type="text/markdown",
)
def get_automation_guide() -> str:
    return _AUTOMATION_GUIDE


@mcp.resource(
    "configurationdesk://guides/tools",
    name="tool_categories",
    title="Tool Categories",
    description="Complete list of all ConfigurationDesk MCP tools organized by category with descriptions",
    mime_type="text/markdown",
)
def get_tool_categories() -> str:
    return _TOOL_CATEGORIES


@mcp.resource(
    "configurationdesk://reference/xpath",
    name="xpath_reference",
    title="XPath Reference",
    description="XPath query reference for bus configurations and communication matrices - element hierarchy, common patterns, attribute filters, and examples",
    mime_type="text/markdown",
)
def get_xpath_reference() -> str:
    return _XPATH_REFERENCE


@mcp.resource(
    "configurationdesk://reference/features",
    name="feature_reference",
    title="Feature Reference",
    description="Complete reference of all bus configuration features (PDU, signal, controller, GTS) with exact feature_name strings, descriptions, ports created, and usage examples",
    mime_type="text/markdown",
)
def get_feature_reference() -> str:
    return _FEATURE_REFERENCE


@mcp.resource(
    "configurationdesk://guides/workflow-examples",
    name="workflow_examples",
    title="Workflow Examples",
    description="Real-world workflow examples: CAN restbus, CAN-FD multi-cluster, LIN, frame access, GTS, inspection/manipulation, offline build, with baud rate reference",
    mime_type="text/markdown",
)
def get_workflow_examples() -> str:
    return _WORKFLOW_EXAMPLES


@mcp.resource(
    "configurationdesk://status",
    name="application_status",
    title="ConfigurationDesk Application Status",
    description="Current ConfigurationDesk connection and project status",
    mime_type="application/json",
)
def get_status() -> str:
    conn = get_connection()
    if not conn.is_connected:
        return json.dumps({"connected": False}, indent=2)
    try:
        app = conn.app
        return json.dumps(
            {
                "connected": True,
                "project": (app.ActiveProject.Name if app.ActiveProject else None),
                "project_root": (
                    str(app.ActiveProjectRoot.PathName) if app.ActiveProjectRoot else None
                ),
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"connected": True, "error": str(e)}, indent=2)


@mcp.resource(
    "configurationdesk://reference/function-port-properties",
    name="function_port_properties",
    title="Function Port Properties",
    description=(
        "Catalog of function port properties accepted by "
        "set_function_port_property. Each entry lists the canonical "
        "automation-API name (the value passed to FunctionPort.Properties."
        "Item) together with the GUI label and additional aliases that the "
        "tool will resolve to the same canonical name."
    ),
    mime_type="application/json",
)
def get_function_port_properties() -> str:
    return json.dumps(known_aliases(), indent=2)


@mcp.resource(
    "configurationdesk://reference/bus-element-properties",
    name="bus_element_properties",
    title="Bus Element Properties",
    description=(
        "Catalog of common bus configuration feature-node and communication-"
        "matrix property names accepted by set_bus_config_element_property and "
        "set_matrix_element_property. Includes aliases, value types, and "
        "example values."
    ),
    mime_type="application/json",
)
def get_bus_element_properties() -> str:
    return json.dumps(known_bus_element_properties(), indent=2)

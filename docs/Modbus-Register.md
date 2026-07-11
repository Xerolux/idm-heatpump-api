# Modbus Register Reference

Register map verified against the official iDM **MODBUS TCP NAVIGATOR 10**
documentation (Stand 18.06.2025, software NAV10_20.23-903.iup / T_NAV10_20.23-1336.iup).

- Modbus TCP port: **502**, Unit ID: **1**
- `FLOAT` = IEEE 754, 32 bit, 2 registers, low word first (Reg_L, then Reg_H)
- `WORD` pump status registers are signed: **-1 = off**, 0 = min. speed, 100 = max. speed
- Registers marked **EEPROM** have limited write cycles — write sparingly!
- GLT demand temperatures (1696/1698) must be re-written cyclically (every 10 min)

## Base Registers

| Address | Name | Type | Access | Unit | Range | Notes |
|---------|------|------|--------|------|-------|-------|
| 74 | `pv_surplus` | FLOAT | RW | kW |  |  |
| 76 | `electric_heater_power` | FLOAT | RW | kW |  |  |
| 78 | `pv_production` | FLOAT | RW | kW |  |  |
| 82 | `house_consumption` | FLOAT | RW | kW |  |  |
| 84 | `battery_discharge` | FLOAT | RW | kW |  |  |
| 86 | `battery_soc` | INT16 | RW | % | 0..100 |  |
| 88 | `pv_target_value` | FLOAT | RW | kW |  |  |
| 90 | `smart_grid_status` | UCHAR | RO | - |  | 0=Red; 1=Yellow; 2=Green; 4=Supergreen |
| 1000 | `outdoor_temp` | FLOAT | RO | °C |  |  |
| 1002 | `outdoor_temp_avg` | FLOAT | RO | °C |  |  |
| 1004 | `internal_message` | UINT16 | RO | - |  |  |
| 1005 | `system_mode` | UCHAR | RW | - | 0..5 | EEPROM, 0=Standby; 1=Automatic; 2=Absent; 4=Hot Water Only; 5=Heating/Cooling Only |
| 1006 | `variable_input` | UCHAR | RO | - |  | 0=Not configured; 1=External DHW Charging; 2=PV / Digital Input; 3=External Heat/Cool Switch |
| 1008 | `storage_temp` | FLOAT | RO | °C |  |  |
| 1010 | `cold_storage_temp` | FLOAT | RO | °C |  |  |
| 1012 | `dhw_temp_bottom` | FLOAT | RO | °C |  |  |
| 1014 | `dhw_temp_top` | FLOAT | RO | °C |  |  |
| 1030 | `dhw_tapping_temp` | FLOAT | RO | °C |  |  |
| 1032 | `dhw_setpoint` | UCHAR | RW | °C | 35..95 | EEPROM |
| 1033 | `dhw_charge_on_temp` | UCHAR | RW | °C | 30..50 | EEPROM |
| 1034 | `dhw_charge_off_temp` | UCHAR | RW | °C | 46..53 | EEPROM |
| 1048 | `current_electricity_price` | FLOAT | RO | €/MWh |  |  |
| 1050 | `hp_flow_temp` | FLOAT | RO | °C |  |  |
| 1052 | `hp_return_temp` | FLOAT | RO | °C |  |  |
| 1054 | `hgl_flow_temp` | FLOAT | RO | °C |  |  |
| 1056 | `heat_source_inlet_temp` | FLOAT | RO | °C |  |  |
| 1058 | `heat_source_outlet_temp` | FLOAT | RO | °C |  |  |
| 1060 | `air_intake_temp` | FLOAT | RO | °C |  |  |
| 1062 | `air_heat_exchanger_temp` | FLOAT | RO | °C |  |  |
| 1064 | `air_intake_temp_2` | FLOAT | RO | °C |  |  |
| 1066 | `charging_sensor_temp` | FLOAT | RO | °C |  |  |
| 1068 | `heat_sink_return_temp` | FLOAT | RO | °C |  |  |
| 1070 | `heat_sink_flow_temp` | FLOAT | RO | °C |  |  |
| 1072 | `heat_sink_flow_rate` | UCHAR | RO | L/min |  |  |
| 1074 | `heat_sink_charging_pump_signal` | INT16 | RO | % |  |  |
| 1086 | `groundwater_inlet_temp_1` | FLOAT | RO | °C |  |  |
| 1088 | `groundwater_inlet_temp_2` | FLOAT | RO | °C |  |  |
| 1090 | `hp_operating_mode` | UCHAR | RO | - |  | 0=Standby; 1=Heating; 2=Cooling; 4=DHW; 8=Defrost |
| 1091 | `heating_demand` | UCHAR | RO | - |  |  |
| 1092 | `cooling_demand` | UCHAR | RO | - |  |  |
| 1093 | `dhw_demand` | UCHAR | RO | - |  |  |
| 1098 | `evu_lock` | UCHAR | RO | - |  | 0=Locked; 1=Not Locked |
| 1099 | `hp_sum_alarm` | UCHAR | RO | - |  |  |
| 1100 | `compressor_status_1` | UCHAR | RO | - |  |  |
| 1101 | `compressor_status_2` | UCHAR | RO | - |  |  |
| 1102 | `compressor_status_3` | UCHAR | RO | - |  |  |
| 1103 | `compressor_status_4` | UCHAR | RO | - |  |  |
| 1104 | `charging_pump_status` | INT16 | RO | % |  |  |
| 1105 | `brine_pump_status` | INT16 | RO | % |  |  |
| 1106 | `heat_source_pump_status` | INT16 | RO | % |  |  |
| 1108 | `isc_cold_storage_pump_status` | INT16 | RO | % |  |  |
| 1109 | `isc_recooling_pump_status` | INT16 | RO | % |  |  |
| 1110 | `valve_hc_heat_cool` | UINT16 | RO | - |  |  |
| 1111 | `valve_storage_heat_cool` | UINT16 | RO | - |  |  |
| 1112 | `valve_heat_dhw` | UINT16 | RO | - |  |  |
| 1113 | `valve_heat_source_heat_cool` | UINT16 | RO | - |  |  |
| 1114 | `valve_solar_heat_dhw` | UINT16 | RO | - |  |  |
| 1115 | `valve_solar_storage_heat_source` | UINT16 | RO | - |  |  |
| 1116 | `valve_isc_heat_source_cold_storage` | UINT16 | RO | - |  |  |
| 1117 | `valve_isc_storage_bypass` | UINT16 | RO | - |  |  |
| 1118 | `circulation_pump` | UINT16 | RO | - |  |  |
| 1120 | `bivalence_point_1_2nd_gen` | INT16 | RW | °C | -40..40 | EEPROM |
| 1121 | `bivalence_point_2_2nd_gen` | INT16 | RW | °C | -40..40 | EEPROM |
| 1122 | `bivalence_point_1_3rd_gen` | INT16 | RW | °C | -40..40 | EEPROM |
| 1123 | `bivalence_point_2_3rd_gen` | INT16 | RW | °C | -40..40 | EEPROM |
| 1124 | `bivalence_state` | UCHAR | RO | - |  | 0=Off; 1=Bivalence 1 Active; 2=Bivalence 2 Active; 3=Bivalence 1+2 Active |
| 1147 | `cascade_available_heating` | UCHAR | RO | - |  |  |
| 1148 | `cascade_available_cooling` | UCHAR | RO | - |  |  |
| 1149 | `cascade_available_dhw` | UCHAR | RO | - |  |  |
| 1150 | `cascade_running_heating` | UCHAR | RO | - |  |  |
| 1151 | `cascade_running_cooling` | UCHAR | RO | - |  |  |
| 1152 | `cascade_running_dhw` | UCHAR | RO | - |  |  |
| 1200 | `cascade_req_heating_temp` | FLOAT | RO | °C |  |  |
| 1202 | `cascade_req_cooling_temp` | FLOAT | RO | °C |  |  |
| 1204 | `cascade_req_dhw_temp` | FLOAT | RO | °C |  |  |
| 1206 | `cascade_avg_flow_heating` | FLOAT | RO | °C |  |  |
| 1208 | `cascade_avg_flow_cooling` | FLOAT | RO | °C |  |  |
| 1210 | `cascade_avg_flow_dhw` | FLOAT | RO | °C |  |  |
| 1220 | `cascade_min_power_heating` | UCHAR | RW | % | 0..100 |  |
| 1221 | `cascade_max_power_heating` | UCHAR | RW | % | 0..100 |  |
| 1222 | `cascade_min_power_cooling` | UCHAR | RW | % | 0..100 |  |
| 1223 | `cascade_max_power_cooling` | UCHAR | RW | % | 0..100 |  |
| 1224 | `cascade_min_power_dhw` | UCHAR | RW | % | 0..100 |  |
| 1225 | `cascade_max_power_dhw` | UCHAR | RW | % | 0..100 |  |
| 1226 | `cascade_bivalence_heating_parallel` | INT16 | RW | °C | -40..40 |  |
| 1227 | `cascade_bivalence_heating_alternative` | INT16 | RW | °C | -40..40 |  |
| 1228 | `cascade_bivalence_cooling_parallel` | INT16 | RW | °C | -40..40 |  |
| 1229 | `cascade_bivalence_cooling_alternative` | INT16 | RW | °C | -40..40 |  |
| 1230 | `cascade_bivalence_dhw_parallel` | INT16 | RW | °C | -40..40 |  |
| 1231 | `cascade_bivalence_dhw_alternative` | INT16 | RW | °C | -40..40 |  |
| 1350 | `hc_a_flow_temp` | FLOAT | RO | °C |  |  |
| 1352 | `hc_b_flow_temp` | FLOAT | RO | °C |  |  |
| 1354 | `hc_c_flow_temp` | FLOAT | RO | °C |  |  |
| 1356 | `hc_d_flow_temp` | FLOAT | RO | °C |  |  |
| 1358 | `hc_e_flow_temp` | FLOAT | RO | °C |  |  |
| 1360 | `hc_f_flow_temp` | FLOAT | RO | °C |  |  |
| 1362 | `hc_g_flow_temp` | FLOAT | RO | °C |  |  |
| 1364 | `hc_a_room_temp` | FLOAT | RO | °C |  |  |
| 1366 | `hc_b_room_temp` | FLOAT | RO | °C |  |  |
| 1368 | `hc_c_room_temp` | FLOAT | RO | °C |  |  |
| 1370 | `hc_d_room_temp` | FLOAT | RO | °C |  |  |
| 1372 | `hc_e_room_temp` | FLOAT | RO | °C |  |  |
| 1374 | `hc_f_room_temp` | FLOAT | RO | °C |  |  |
| 1376 | `hc_g_room_temp` | FLOAT | RO | °C |  |  |
| 1378 | `hc_a_setpoint_flow_temp` | FLOAT | RO | °C |  |  |
| 1380 | `hc_b_setpoint_flow_temp` | FLOAT | RO | °C |  |  |
| 1382 | `hc_c_setpoint_flow_temp` | FLOAT | RO | °C |  |  |
| 1384 | `hc_d_setpoint_flow_temp` | FLOAT | RO | °C |  |  |
| 1386 | `hc_e_setpoint_flow_temp` | FLOAT | RO | °C |  |  |
| 1388 | `hc_f_setpoint_flow_temp` | FLOAT | RO | °C |  |  |
| 1390 | `hc_g_setpoint_flow_temp` | FLOAT | RO | °C |  |  |
| 1392 | `humidity_sensor` | UCHAR | RO | % |  |  |
| 1393 | `hc_a_mode` | UCHAR | RW | - | 0..5 | EEPROM, 0=Off; 1=Time Program; 2=Normal; 3=Eco; 4=Manual Heat; 5=Manual Cool; 255=Not configured / Unavailable |
| 1394 | `hc_b_mode` | UCHAR | RW | - | 0..5 | EEPROM, 0=Off; 1=Time Program; 2=Normal; 3=Eco; 4=Manual Heat; 5=Manual Cool; 255=Not configured / Unavailable |
| 1395 | `hc_c_mode` | UCHAR | RW | - | 0..5 | EEPROM, 0=Off; 1=Time Program; 2=Normal; 3=Eco; 4=Manual Heat; 5=Manual Cool; 255=Not configured / Unavailable |
| 1396 | `hc_d_mode` | UCHAR | RW | - | 0..5 | EEPROM, 0=Off; 1=Time Program; 2=Normal; 3=Eco; 4=Manual Heat; 5=Manual Cool; 255=Not configured / Unavailable |
| 1397 | `hc_e_mode` | UCHAR | RW | - | 0..5 | EEPROM, 0=Off; 1=Time Program; 2=Normal; 3=Eco; 4=Manual Heat; 5=Manual Cool; 255=Not configured / Unavailable |
| 1398 | `hc_f_mode` | UCHAR | RW | - | 0..5 | EEPROM, 0=Off; 1=Time Program; 2=Normal; 3=Eco; 4=Manual Heat; 5=Manual Cool; 255=Not configured / Unavailable |
| 1399 | `hc_g_mode` | UCHAR | RW | - | 0..5 | EEPROM, 0=Off; 1=Time Program; 2=Normal; 3=Eco; 4=Manual Heat; 5=Manual Cool; 255=Not configured / Unavailable |
| 1401 | `hc_a_room_setpoint_heat_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1403 | `hc_b_room_setpoint_heat_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1405 | `hc_c_room_setpoint_heat_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1407 | `hc_d_room_setpoint_heat_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1409 | `hc_e_room_setpoint_heat_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1411 | `hc_f_room_setpoint_heat_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1413 | `hc_g_room_setpoint_heat_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1415 | `hc_a_room_setpoint_heat_eco` | FLOAT | RW | °C | 10..25 | EEPROM |
| 1417 | `hc_b_room_setpoint_heat_eco` | FLOAT | RW | °C | 10..25 | EEPROM |
| 1419 | `hc_c_room_setpoint_heat_eco` | FLOAT | RW | °C | 10..25 | EEPROM |
| 1421 | `hc_d_room_setpoint_heat_eco` | FLOAT | RW | °C | 10..25 | EEPROM |
| 1423 | `hc_e_room_setpoint_heat_eco` | FLOAT | RW | °C | 10..25 | EEPROM |
| 1425 | `hc_f_room_setpoint_heat_eco` | FLOAT | RW | °C | 10..25 | EEPROM |
| 1427 | `hc_g_room_setpoint_heat_eco` | FLOAT | RW | °C | 10..25 | EEPROM |
| 1429 | `hc_a_heating_curve` | FLOAT | RW | - | 0.1..3.5 | EEPROM |
| 1431 | `hc_b_heating_curve` | FLOAT | RW | - | 0.1..3.5 | EEPROM |
| 1433 | `hc_c_heating_curve` | FLOAT | RW | - | 0.1..3.5 | EEPROM |
| 1435 | `hc_d_heating_curve` | FLOAT | RW | - | 0.1..3.5 | EEPROM |
| 1437 | `hc_e_heating_curve` | FLOAT | RW | - | 0.1..3.5 | EEPROM |
| 1439 | `hc_f_heating_curve` | FLOAT | RW | - | 0.1..3.5 | EEPROM |
| 1441 | `hc_g_heating_curve` | FLOAT | RW | - | 0.1..3.5 | EEPROM |
| 1443 | `hc_a_heating_limit` | UCHAR | RW | °C | 0..50 | EEPROM |
| 1444 | `hc_b_heating_limit` | UCHAR | RW | °C | 0..50 | EEPROM |
| 1445 | `hc_c_heating_limit` | UCHAR | RW | °C | 0..50 | EEPROM |
| 1446 | `hc_d_heating_limit` | UCHAR | RW | °C | 0..50 | EEPROM |
| 1447 | `hc_e_heating_limit` | UCHAR | RW | °C | 0..50 | EEPROM |
| 1448 | `hc_f_heating_limit` | UCHAR | RW | °C | 0..50 | EEPROM |
| 1449 | `hc_g_heating_limit` | UCHAR | RW | °C | 0..50 | EEPROM |
| 1450 | `hc_a_setpoint_flow_constant` | UCHAR | RW | °C | 20..90 | EEPROM |
| 1451 | `hc_b_setpoint_flow_constant` | UCHAR | RW | °C | 20..90 | EEPROM |
| 1452 | `hc_c_setpoint_flow_constant` | UCHAR | RW | °C | 20..90 | EEPROM |
| 1453 | `hc_d_setpoint_flow_constant` | UCHAR | RW | °C | 20..90 | EEPROM |
| 1454 | `hc_e_setpoint_flow_constant` | UCHAR | RW | °C | 20..90 | EEPROM |
| 1455 | `hc_f_setpoint_flow_constant` | UCHAR | RW | °C | 20..90 | EEPROM |
| 1456 | `hc_g_setpoint_flow_constant` | UCHAR | RW | °C | 20..90 | EEPROM |
| 1457 | `hc_a_room_setpoint_cool_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1459 | `hc_b_room_setpoint_cool_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1461 | `hc_c_room_setpoint_cool_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1463 | `hc_d_room_setpoint_cool_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1465 | `hc_e_room_setpoint_cool_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1467 | `hc_f_room_setpoint_cool_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1469 | `hc_g_room_setpoint_cool_normal` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1471 | `hc_a_room_setpoint_cool_eco` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1473 | `hc_b_room_setpoint_cool_eco` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1475 | `hc_c_room_setpoint_cool_eco` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1477 | `hc_d_room_setpoint_cool_eco` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1479 | `hc_e_room_setpoint_cool_eco` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1481 | `hc_f_room_setpoint_cool_eco` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1483 | `hc_g_room_setpoint_cool_eco` | FLOAT | RW | °C | 15..30 | EEPROM |
| 1485 | `hc_a_cooling_limit` | UCHAR | RW | °C | 0..36 | EEPROM |
| 1486 | `hc_b_cooling_limit` | UCHAR | RW | °C | 0..36 | EEPROM |
| 1487 | `hc_c_cooling_limit` | UCHAR | RW | °C | 0..36 | EEPROM |
| 1488 | `hc_d_cooling_limit` | UCHAR | RW | °C | 0..36 | EEPROM |
| 1489 | `hc_e_cooling_limit` | UCHAR | RW | °C | 0..36 | EEPROM |
| 1490 | `hc_f_cooling_limit` | UCHAR | RW | °C | 0..36 | EEPROM |
| 1491 | `hc_g_cooling_limit` | UCHAR | RW | °C | 0..36 | EEPROM |
| 1492 | `hc_a_setpoint_flow_cooling` | UCHAR | RW | °C | 8..30 | EEPROM |
| 1493 | `hc_b_setpoint_flow_cooling` | UCHAR | RW | °C | 8..30 | EEPROM |
| 1494 | `hc_c_setpoint_flow_cooling` | UCHAR | RW | °C | 8..30 | EEPROM |
| 1495 | `hc_d_setpoint_flow_cooling` | UCHAR | RW | °C | 8..30 | EEPROM |
| 1496 | `hc_e_setpoint_flow_cooling` | UCHAR | RW | °C | 8..30 | EEPROM |
| 1497 | `hc_f_setpoint_flow_cooling` | UCHAR | RW | °C | 8..30 | EEPROM |
| 1498 | `hc_g_setpoint_flow_cooling` | UCHAR | RW | °C | 8..30 | EEPROM |
| 1499 | `hc_a_active_mode` | UCHAR | RO | - |  | 0=Off; 1=Heating; 2=Cooling; 255=Not configured / Unavailable |
| 1500 | `hc_b_active_mode` | UCHAR | RO | - |  | 0=Off; 1=Heating; 2=Cooling; 255=Not configured / Unavailable |
| 1501 | `hc_c_active_mode` | UCHAR | RO | - |  | 0=Off; 1=Heating; 2=Cooling; 255=Not configured / Unavailable |
| 1502 | `hc_d_active_mode` | UCHAR | RO | - |  | 0=Off; 1=Heating; 2=Cooling; 255=Not configured / Unavailable |
| 1503 | `hc_e_active_mode` | UCHAR | RO | - |  | 0=Off; 1=Heating; 2=Cooling; 255=Not configured / Unavailable |
| 1504 | `hc_f_active_mode` | UCHAR | RO | - |  | 0=Off; 1=Heating; 2=Cooling; 255=Not configured / Unavailable |
| 1505 | `hc_g_active_mode` | UCHAR | RO | - |  | 0=Off; 1=Heating; 2=Cooling; 255=Not configured / Unavailable |
| 1506 | `hc_a_parallel_shift` | UCHAR | RW | °C | 0..30 | EEPROM |
| 1507 | `hc_b_parallel_shift` | UCHAR | RW | °C | 0..30 | EEPROM |
| 1508 | `hc_c_parallel_shift` | UCHAR | RW | °C | 0..30 | EEPROM |
| 1509 | `hc_d_parallel_shift` | UCHAR | RW | °C | 0..30 | EEPROM |
| 1510 | `hc_e_parallel_shift` | UCHAR | RW | °C | 0..30 | EEPROM |
| 1511 | `hc_f_parallel_shift` | UCHAR | RW | °C | 0..30 | EEPROM |
| 1512 | `hc_g_parallel_shift` | UCHAR | RW | °C | 0..30 | EEPROM |
| 1650 | `hc_a_ext_room_temp` | FLOAT | RW | °C | 15..30 |  |
| 1652 | `hc_b_ext_room_temp` | FLOAT | RW | °C | 15..30 |  |
| 1654 | `hc_c_ext_room_temp` | FLOAT | RW | °C | 15..30 |  |
| 1656 | `hc_d_ext_room_temp` | FLOAT | RW | °C | 15..30 |  |
| 1658 | `hc_e_ext_room_temp` | FLOAT | RW | °C | 15..30 |  |
| 1660 | `hc_f_ext_room_temp` | FLOAT | RW | °C | 15..30 |  |
| 1662 | `hc_g_ext_room_temp` | FLOAT | RW | °C | 15..30 |  |
| 1680 | `fault_heat_source_circuit` | UCHAR | RO | - |  |  |
| 1681 | `fault_heat_source_pressure_switch` | UCHAR | RO | - |  |  |
| 1682 | `fault_charging_pump_1_intermediate` | UCHAR | RO | - |  |  |
| 1683 | `fault_charging_pump_2_intermediate` | UCHAR | RO | - |  |  |
| 1690 | `ext_outdoor_temp` | FLOAT | RW | °C |  |  |
| 1692 | `ext_humidity` | FLOAT | RW | % | 0..100 |  |
| 1694 | `ext_demand_temp_heating` | UCHAR | RW | °C | 20..65 | EEPROM |
| 1695 | `ext_demand_temp_cooling` | UCHAR | RW | °C | 10..25 | EEPROM |
| 1696 | `glt_temp_demand_heating` | FLOAT | RW | °C |  | cyclic write required |
| 1698 | `glt_temp_demand_cooling` | FLOAT | RW | °C |  | cyclic write required |
| 1710 | `demand_heating` | BOOL | RW | - |  |  |
| 1711 | `demand_cooling` | BOOL | RW | - |  |  |
| 1712 | `demand_dhw_charging` | BOOL | RW | - |  |  |
| 1713 | `demand_onetime_dhw` | BOOL | RW | - |  |  |
| 1714 | `ext_demand_groundwater_pump_m15` | UCHAR | RW | % | 0..100 |  |
| 1715 | `ext_demand_groundwater_pump_m15_sw_max` | UCHAR | RW | % | 0..100 |  |
| 1716 | `glt_heat_storage_temp` | FLOAT | RW | °C |  |  |
| 1718 | `glt_cold_storage_temp` | FLOAT | RW | °C |  |  |
| 1720 | `glt_dhw_temp_bottom` | FLOAT | RW | °C |  |  |
| 1722 | `glt_dhw_temp_top` | FLOAT | RW | °C |  |  |
| 1748 | `energy_heating` | FLOAT | RO | kWh |  |  |
| 1750 | `energy_total` | FLOAT | RO | kWh |  |  |
| 1752 | `energy_cooling` | FLOAT | RO | kWh |  |  |
| 1754 | `energy_dhw` | FLOAT | RO | kWh |  |  |
| 1756 | `energy_defrost` | FLOAT | RO | kWh |  |  |
| 1758 | `energy_passive_cooling` | FLOAT | RO | kWh |  |  |
| 1760 | `energy_solar` | FLOAT | RO | kWh |  |  |
| 1762 | `energy_electric_heater` | FLOAT | RO | kWh |  |  |
| 1790 | `current_power` | FLOAT | RO | kW |  |  |
| 1792 | `current_power_solar` | FLOAT | RO | kW |  |  |
| 1850 | `solar_collector_temp` | FLOAT | RO | °C |  |  |
| 1852 | `solar_return_temp` | FLOAT | RO | °C |  |  |
| 1854 | `solar_charging_temp` | FLOAT | RO | °C |  |  |
| 1856 | `solar_mode` | UCHAR | RW | - | 0..4 | EEPROM, 0=Automatic; 1=DHW; 2=Heating; 3=DHW + Heating; 4=Heat Source / Pool |
| 1857 | `solar_wq_pool_temp` | FLOAT | RO | °C |  |  |
| 1870 | `isc_charging_temp_cooling` | FLOAT | RO | °C |  |  |
| 1872 | `isc_recooling_temp` | FLOAT | RO | °C |  |  |
| 1874 | `isc_mode` | UCHAR | RO | - |  | 0=No Waste Heat; 1=Heating; 4=DHW; 8=Heat Source; 255=Not configured / Unavailable |
| 1999 | `error_acknowledge` | UCHAR | W | - |  |  |
| 4001 | `booster_fault` | UCHAR | RO | - |  | 0=No fault; 1=Booster A fault; 2=Booster B fault; 3=Booster A + B fault |
| 4002 | `booster_interlock` | UCHAR | RO | - |  |  |
| 4010 | `booster_a_source_inlet_temp` | FLOAT | RO | °C |  |  |
| 4012 | `booster_a_source_outlet_temp` | FLOAT | RO | °C |  |  |
| 4014 | `booster_a_storage_temp` | FLOAT | RO | °C |  |  |
| 4016 | `booster_a_flow_temp` | FLOAT | RO | °C |  |  |
| 4018 | `booster_a_return_temp` | FLOAT | RO | °C |  |  |
| 4020 | `booster_a_source_pump` | INT16 | RO | % |  |  |
| 4021 | `booster_a_charging_pump` | INT16 | RO | % |  |  |
| 4022 | `booster_a_compressor` | UCHAR | RO | - |  |  |
| 4040 | `booster_b_source_inlet_temp` | FLOAT | RO | °C |  |  |
| 4042 | `booster_b_source_outlet_temp` | FLOAT | RO | °C |  |  |
| 4044 | `booster_b_storage_temp` | FLOAT | RO | °C |  |  |
| 4046 | `booster_b_flow_temp` | FLOAT | RO | °C |  |  |
| 4048 | `booster_b_return_temp` | FLOAT | RO | °C |  |  |
| 4050 | `booster_b_source_pump` | INT16 | RO | % |  |  |
| 4051 | `booster_b_charging_pump` | INT16 | RO | % |  |  |
| 4052 | `booster_b_compressor` | UCHAR | RO | - |  |  |
| 4108 | `power_limit_hp` | FLOAT | RW | kW |  |  |
| 4112 | `power_limit_cascade` | FLOAT | RW | kW |  |  |
| 4120 | `firmware_version` | FLOAT | RO | - | not enabled by default; use local web `software_version` where available |  |
| 4122 | `power_consumption_hp` | FLOAT | RO | kW |  |  |
| 4124 | `power_consumption_hp_smartfox` | FLOAT | RO | kW |  |  |
| 4126 | `thermal_power_flow_sensor` | FLOAT | RO | kW |  |  |
| 4128 | `total_heat_energy` | FLOAT | RO | kWh |  |  |

## Heating Circuits A–G

Per-circuit registers (index: A=0 … G=6):

| Base address | Step | Name pattern | Type | Access | Unit | Range |
|--------------|------|--------------|------|--------|------|-------|
| 1350 | 2 | `hc_X_flow_temp` | FLOAT | RO | °C |  |
| 1364 | 2 | `hc_X_room_temp` | FLOAT | RO | °C |  |
| 1378 | 2 | `hc_X_setpoint_flow_temp` | FLOAT | RO | °C |  |
| 1393 | 1 | `hc_X_mode` | UCHAR | RW | - | 0..5 |
| 1401 | 2 | `hc_X_room_setpoint_heat_normal` | FLOAT | RW | °C | 15..30 |
| 1415 | 2 | `hc_X_room_setpoint_heat_eco` | FLOAT | RW | °C | 10..25 |
| 1429 | 2 | `hc_X_heating_curve` | FLOAT | RW | - | 0.1..3.5 |
| 1443 | 1 | `hc_X_heating_limit` | UCHAR | RW | °C | 0..50 |
| 1450 | 1 | `hc_X_setpoint_flow_constant` | UCHAR | RW | °C | 20..90 |
| 1457 | 2 | `hc_X_room_setpoint_cool_normal` | FLOAT | RW | °C | 15..30 |
| 1471 | 2 | `hc_X_room_setpoint_cool_eco` | FLOAT | RW | °C | 15..30 |
| 1485 | 1 | `hc_X_cooling_limit` | UCHAR | RW | °C | 0..36 |
| 1492 | 1 | `hc_X_setpoint_flow_cooling` | UCHAR | RW | °C | 8..30 |
| 1499 | 1 | `hc_X_active_mode` | UCHAR | RO | - |  |
| 1506 | 1 | `hc_X_parallel_shift` | UCHAR | RW | °C | 0..30 |
| 1650 | 2 | `hc_X_ext_room_temp` | FLOAT | RW | °C | 15..30 |

## Zone Modules 1–10 (Single Room Control)

Base addresses: 2000, 2065, 2130, 2195, 2260, 2325, 2390, 2455, 2520, 2585
(zone module N base = 2000 + (N-1) × 65). Each module supports up to 8
configurable rooms (6 is the current Navigator 10 default); each room block is
**7 registers** wide, starting at base+2.

| Offset | Name pattern | Type | Access | Unit | Notes |
|--------|--------------|------|--------|------|-------|
| base+0 | `zmN_mode_heat_cool` | UCHAR | RO | - | 0=Cooling, 1=Heating |
| base+1 | `zmN_dehumidification` | UCHAR | RO | - | 0=Off, 1=On |
| base+2+(room-1)×7 | `zmN_roomR_temp` | FLOAT | RW/RO | °C | RW with external (GLT) sensors |
| +2 | `zmN_roomR_setpoint` | FLOAT | RW | °C | 0.5 °C steps only |
| +4 | `zmN_roomR_humidity` | UCHAR | RW/RO | % | RW with external (GLT) sensors |
| +5 | `zmN_roomR_mode` | UCHAR | RW | - | 0=Off, 1=Automatic, 2=Eco, 3=Normal, 4=Comfort |
| +6 | `zmN_roomR_relay` | UCHAR | RO | - | 0=Off, 1=On |

Example (zone module 1): room 1 temperature = 2002, setpoint = 2004, humidity = 2006,
mode = 2007, relay = 2008; room 2 starts at 2009.

## Notes

- Address 1004 (internal message): message numbers 020–999 — read as 16-bit value.
- Address 1050/1052 are not readable on systems with a separating heat exchanger (TWT); use 1068/1070 instead.
- Address 1072 (flow rate heat sink) is only available with a separating heat exchanger (TWT).
- Address 1712 (DHW charge demand): write 0 to end the charge — it does not stop on storage temperature.
- Address 1999 (error acknowledge) must not be written permanently.
- Addresses 1710/1711 (heat/cool demand) should be written cyclically so demands survive a restart.

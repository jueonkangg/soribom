-- 설치된 WirePlumber 0.4의 Lua 설정 형식이다.
-- Bose 출력이 잠깐 조용해질 때마다 중단되어 다음 말하기의 연결을 다시 여는 일을 줄인다.
table.insert(bluez_monitor.rules, {
  matches = {
    {
      { "node.name", "matches", "bluez_output.C8_7B_23_EF_4E_9A.*" },
    },
  },
  apply_properties = {
    ["session.suspend-timeout-seconds"] = 0,
  },
})

# 실험 데이터

실험 원자료는 **이 저장소에 커밋하지 않습니다** (`.gitignore`로 차단).

참가자에게 "연구 종료 직후 폐기"를 약속했고, 익명 처리했더라도 소규모 표본에서는
재식별 가능성이 있기 때문입니다.

분석 시 `scores.csv`를 이 폴더에 두고 실행하세요.

```csv
id,order,score_device,score_control
1,device_first,17,12
2,control_first,15,13
```

| 열 | 뜻 |
|---|---|
| `id` | 익명 번호 (이름 아님) |
| `order` | 조건 순서 (`device_first` / `control_first`) |
| `score_device` | 단말 사용 조건 퀴즈 점수 |
| `score_control` | 단말 미사용 조건 퀴즈 점수 |

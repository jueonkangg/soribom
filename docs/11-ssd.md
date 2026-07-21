# SSD 설정 — 저장소 역할 나누기

Jetson에 꽂은 NVMe SSD를 어떻게 쓸지에 대한 안내입니다.

---

## 우리 팀 방침

| 저장장치 | 역할 |
|---|---|
| **microSD (64GB)** | **부팅 전용.** 운영체제만. 건드리지 않는다 |
| **NVMe SSD (500GB)** | **작업 공간.** 코드·AI 모델·가상환경·녹음·실험 데이터 전부 |

**부팅 이전(SSD로 부팅)은 하지 않습니다.**

이유는 세 가지입니다.

1. NVIDIA 공식 방법이 "SSD에 처음부터 다시 설치"라서, 지금 잘 켜지는 microSD를 버려야 합니다
2. **Ubuntu PC가 한 대 더 필요합니다** (SDK Manager는 리눅스 전용). 우리 팀은 전원 맥·윈도우입니다
3. 마감이 8일 남았습니다. **작동하는 기기를 건드려 안 켜지게 만드는 게 지금 가장 큰 위험**입니다

부팅만 microSD에서 하고 나머지를 전부 SSD에 두면, 속도 이득은 거의 다 얻습니다.
느린 지점은 부팅이 아니라 **AI 모델(1~2GB)을 읽어 들일 때**이기 때문입니다.

---

## ⚠️ 한 가지 예외 — 시스템 패키지

"SSD에 전부 설치"에서 **`sudo apt install` 로 까는 것들은 예외**입니다.

`apt` 로 설치하는 프로그램은 microSD의 `/usr` 에 들어가도록 정해져 있어서
위치를 바꾸기 어렵고, 억지로 옮기면 시스템이 깨집니다.

**대신 파이썬 가상환경(.venv)을 통째로 SSD에 두면 됩니다.**
`pip install` 로 까는 것들(faster-whisper, PySide6, MeloTTS 등)은 전부 그 안에 들어가므로,
용량을 많이 먹는 것들은 결국 다 SSD에 놓이게 됩니다.

| 종류 | 어디에 설치되나 |
|---|---|
| `sudo apt install ...` (ffmpeg, python3-pip 등) | microSD — 어쩔 수 없음. 용량 작음 |
| `pip install ...` (faster-whisper, torch 등) | **SSD** — 가상환경을 SSD에 두면 됨 ✅ |
| AI 모델 (Whisper, MeloTTS) | **SSD** ✅ |
| 우리 코드, 녹음 파일, 실험 데이터 | **SSD** ✅ |

---

# 설정하기 (약 15분, 한 번만)

## 1. SSD가 보이는지 확인

```bash
lsblk
```

`nvme0n1` 이 보여야 합니다. 안 보이면 [Day1](Day1.md)의 1-4로 돌아가세요.

## 2. 포맷하기

> ⚠️ **SSD 안의 내용이 전부 지워집니다.** 새 SSD니까 괜찮습니다.
>
> 다만 **`nvme0n1` 이 맞는지 다시 한 번 확인**하세요.
> `mmcblk0` 은 microSD(운영체제)입니다. **이걸 포맷하면 기기가 안 켜집니다.**

```bash
sudo mkfs.ext4 /dev/nvme0n1
```

`Proceed anyway? (y,N)` 이 나오면 `y` 를 누릅니다.

## 3. 연결(마운트)하기

```bash
sudo mkdir -p /mnt/ssd
sudo mount /dev/nvme0n1 /mnt/ssd
sudo chown -R $USER:$USER /mnt/ssd
```

이제 `/mnt/ssd` 폴더가 SSD입니다.

> `chown` 은 "이 폴더의 주인을 나로 바꾼다"는 뜻입니다.
> 이걸 안 하면 파일을 만들 때마다 `sudo` 를 붙여야 해서 불편합니다.

## 4. 껐다 켜도 유지되게 하기

위 3번은 재부팅하면 풀립니다. 자동으로 연결되게 등록합니다.

```bash
echo "UUID=$(sudo blkid -s UUID -o value /dev/nvme0n1) /mnt/ssd ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab
```

> **`nofail` 이 중요합니다.** SSD에 문제가 생겨도 **기기는 정상 부팅**되게 하는 옵션입니다.
> 이게 없으면 SSD가 빠지거나 고장났을 때 부팅 자체가 멈춥니다.
> 시연 당일에 그런 일이 생기면 끝입니다.

확인:

```bash
sudo mount -a        # 아무 메시지도 안 나오면 성공
df -h /mnt/ssd       # 용량(약 460G)이 보이면 성공
```

## 5. 폴더 구조 만들기

```bash
mkdir -p /mnt/ssd/{code,models,data,recordings}
```

| 폴더 | 용도 |
|---|---|
| `/mnt/ssd/code` | 우리 프로젝트 코드 (soribom) |
| `/mnt/ssd/models` | AI 모델 (Whisper, MeloTTS) |
| `/mnt/ssd/data` | 실험 데이터, 측정 결과 |
| `/mnt/ssd/recordings` | 녹음 파일, 시연 영상 소스 |

## 6. 코드를 SSD에 내려받기

```bash
cd /mnt/ssd/code
git clone https://github.com/jueonkangg/soribom.git
cd soribom
git config user.name  "본인_GitHub_아이디"
git config user.email "본인_GitHub_이메일"
```

## 7. 가상환경을 SSD에 만들기 ← 핵심

**이 단계가 "pip로 까는 것 전부를 SSD에 두는" 방법입니다.**

```bash
cd /mnt/ssd/code/soribom
python3 -m venv .venv
source .venv/bin/activate
```

앞에 `(.venv)` 가 붙으면 성공입니다.

```bash
pip install --upgrade pip
pip install -r src/requirements.txt
```

**10~20분 걸립니다.** 2GB 정도가 설치되는데, **전부 SSD의 `.venv` 안**에 들어갑니다.

## 8. AI 모델도 SSD로

모델이 SSD에 받아지고 SSD에서 읽히도록 경로를 지정합니다.

```bash
echo 'export HF_HOME=/mnt/ssd/models/huggingface' >> ~/.bashrc
echo 'export TORCH_HOME=/mnt/ssd/models/torch' >> ~/.bashrc
source ~/.bashrc
```

> `HF_HOME` 은 AI 모델 저장소(허깅페이스)의 캐시 위치를 정하는 설정입니다.
> faster-whisper가 이 경로를 따라갑니다.
> 이걸 안 하면 모델이 microSD의 `~/.cache` 에 들어가서 SSD를 쓰는 의미가 없어집니다.

---

# 확인하기

전부 제대로 됐는지 점검합니다.

```bash
# 1) SSD가 붙어 있나
df -h /mnt/ssd

# 2) 모델 경로가 SSD를 가리키나
echo $HF_HOME
# → /mnt/ssd/models/huggingface

# 3) 가상환경이 SSD에 있나
cd /mnt/ssd/code/soribom
source .venv/bin/activate
which python
# → /mnt/ssd/code/soribom/.venv/bin/python

# 4) 패키지가 깔렸나
pip list | head
```

음성인식을 한 번 돌린 뒤:

```bash
du -sh /mnt/ssd/models/huggingface
```

용량이 잡히면 **모델이 SSD에 잘 들어간 것**입니다.

---

# 앞으로 작업할 때

Jetson에서 작업을 시작할 때마다:

```bash
cd /mnt/ssd/code/soribom
source .venv/bin/activate
```

> **홈 폴더(`~/`)가 아니라 `/mnt/ssd/code/soribom` 입니다.**
> 습관적으로 `cd ~/soribom` 을 치면 "그런 폴더 없음" 에러가 납니다.

편하게 하려면 짧은 별명을 만들어두세요:

```bash
echo "alias soribom='cd /mnt/ssd/code/soribom && source .venv/bin/activate'" >> ~/.bashrc
source ~/.bashrc
```

이제 터미널에서 `soribom` 만 치면 폴더 이동과 가상환경 켜기가 한 번에 됩니다.

---

# 문제가 생기면

| 증상 | 해결 |
|---|---|
| 재부팅 후 `/mnt/ssd` 가 비어 있음 | `sudo mount -a` → 안 되면 4단계 `/etc/fstab` 등록 확인 |
| `Permission denied` | `sudo chown -R $USER:$USER /mnt/ssd` 다시 실행 |
| 모델이 계속 microSD에 받아짐 | `echo $HF_HOME` 확인. 비어 있으면 8단계 다시 + `source ~/.bashrc` |
| microSD 용량이 자꾸 참 | `du -sh ~/.cache/*` 로 확인 후 큰 것들을 SSD로 옮기기 |

**microSD 용량이 부족해지면** 지금 구조가 어딘가 새고 있다는 뜻입니다.
`df -h` 로 확인하고 팀에 알리세요.

---

## 요약

- **microSD = 부팅만.** 건드리지 않는다
- **SSD = 코드·가상환경·모델·데이터 전부**
- `sudo apt` 로 까는 것만 예외 (용량 작으니 괜찮음)
- 부팅 이전은 **하지 않는다**

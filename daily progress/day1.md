# Day 1 — Building the SO-101 Arms & First Software Setup

**Date:** 2026-06-23

---

## English

### Overview

Today was the first day of my journey into robotic arms and Vision-Language-Action (VLA) models.
We did two things: (1) physically built the two **SO-101** arms in the lab, and (2) set up the full
software environment (Python, LeRobot, motor configuration) on my Mac.

The SO-101 setup is a **leader / follower** pair:
- **Follower** = the robot arm that actually does the work.
- **Leader** = the smaller arm I move by hand to teleoperate the follower.

My two arm serial ports (saved in `myport.txxt`):
- `leader  = /dev/tty.usbmodem5B420006171`
- `follower = /dev/tty.usbmodem5B421352311`

### Part 1 — Hardware (in the lab)

- Assembled the **3D-printed parts** together with the motors to build both arms (leader + follower).
- Wired and routed the **motor cables** using the **SO-101 Motor Pro kit**.
- Configured the motors — each Feetech servo on the bus needs a unique **ID** (1–6) and the correct
  **baud rate**, so the controller can address all six joints of each arm individually.

### Part 2 — Software setup (commands)

Everything below was run from the project folder `~/Documents/coding/fouad_so101`.

**1. Check the environment.** First I checked which Python versions, git and ffmpeg were available.
The system Python is 3.9, which is **too old** for LeRobot.

```bash
python3 --version                 # 3.9.6 -> too old
which python3.11 python3.12 python3.13
ffmpeg -version                   # already installed (needed by LeRobot for video)
```

**2. Create the virtual environment.** I first tried Python 3.11, but LeRobot's `pyproject.toml`
requires **Python >= 3.12**, so I recreated the venv with 3.12 (Apple-Silicon native / arm64).

```bash
rm -rf .venv
/usr/local/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python --version        # Python 3.12.3
```

**3. Clone LeRobot.** A shallow clone (only the latest commit) to save space/time.

```bash
git clone --depth 1 https://github.com/huggingface/lerobot.git lerobot
```

**4. Install LeRobot with the `feetech` extra.** The SO-101 uses **Feetech** servos, so I install the
`feetech` optional dependency group. `-e` makes it an *editable* install (pointing at the cloned source).

```bash
.venv/bin/pip install -e "./lerobot[feetech]"
```

> ⚠️ **Gotcha — disk space.** The first install failed with `No space left on device` while
> downloading PyTorch. I freed ~1.5 GB and re-ran the exact same command; the cached wheels were
> reused, so it finished quickly the second time.

**5. Verify the install.** Confirm the library imports, PyTorch sees the Apple GPU (MPS), the Feetech
SDK is present, and the CLI works.

```bash
.venv/bin/python -c "import lerobot, torch; print(lerobot.__version__, torch.__version__, torch.backends.mps.is_available())"
# -> 0.5.2  2.11.0  True       (MPS = Apple GPU available)
.venv/bin/python -c "import scservo_sdk; print('feetech-servo-sdk OK')"
.venv/bin/lerobot-find-port      # lists serial ports / helps identify each arm
```

**6. Reclaim disk space** (optional cleanup of the pip download cache):

```bash
.venv/bin/pip cache purge
```

### Part 3 — Motor configuration with LeRobot

To use the CLI without the `.venv/bin/` prefix, activate the environment first:

```bash
source .venv/bin/activate
```

**Find the port for each arm** (unplug/replug when prompted so it can tell which is which):

```bash
lerobot-find-port
```

**Set up the motors** — assigns each servo its ID + baud rate. Run **one arm at a time**, and follow
the prompts to connect the motors one by one.

> 🔑 **Key detail (we hit this):** the **follower** is a `--robot.type`, and the **leader** is a
> `--teleop.type`. Passing `--teleop.type=so101_follower` is **wrong** and errors, because `follower`
> only exists under `--robot.type`.

```bash
# Follower (robot arm)
lerobot-setup-motors --robot.type=so101_follower --robot.port=/dev/tty.usbmodem5B421352311

# Leader (teleop arm)
lerobot-setup-motors --teleop.type=so101_leader --teleop.port=/dev/tty.usbmodem5B420006171
```

### Part 4 — Git & GitHub

Turn the folder into a git repo, add LeRobot as a **submodule** (so I can update it later), commit, and
push as a **public** repo.

```bash
git init -b main

# Add lerobot as a submodule. Because the folder was already a clone, git reused it in place
# ("Adding existing repo at 'lerobot' to the index") — no re-download.
git submodule add https://github.com/huggingface/lerobot.git lerobot

git add -A
git commit -m "Day 1: project setup — diary, env, and lerobot submodule"

# Create + push the public repo under my account
gh repo create fouad_so101 --public --source=. --remote=origin --push \
  --description "My journey with the SO-101 robotic arms and VLA models"
```

Repo: <https://github.com/fouad1233/fouad_so101>

**Cloning this repo later (with the submodule):**

```bash
git clone --recurse-submodules https://github.com/fouad1233/fouad_so101.git
# or, if already cloned without it:
git submodule update --init --recursive
```

**Updating the LeRobot submodule later:**

```bash
cd lerobot && git checkout main && git pull && cd ..
git add lerobot && git commit -m "Update lerobot submodule" && git push
```

### Next — Day 2

- **Calibrate** both arms (move each joint through its full range; saved under an `id`):

  ```bash
  lerobot-calibrate --robot.type=so101_follower  --robot.port=/dev/tty.usbmodem5B421352311 --robot.id=my_follower
  lerobot-calibrate --teleop.type=so101_leader   --teleop.port=/dev/tty.usbmodem5B420006171 --teleop.id=my_leader
  ```

- **Teleoperate** — control the follower with the leader (reuse the same `id`s):

  ```bash
  lerobot-teleoperate \
    --robot.type=so101_follower --robot.port=/dev/tty.usbmodem5B421352311 --robot.id=my_follower \
    --teleop.type=so101_leader  --teleop.port=/dev/tty.usbmodem5B420006171 --teleop.id=my_leader
  ```

---

## Türkçe

### Genel Bakış

Bugün robotik kollar ve Görü-Dil-Eylem (VLA) modelleri yolculuğumun ilk günüydü.
İki şey yaptık: (1) laboratuvarda iki **SO-101** kolunu fiziksel olarak monte ettik ve (2) Mac'imde
tüm yazılım ortamını (Python, LeRobot, motor yapılandırması) kurduk.

SO-101 kurulumu bir **lider / takipçi (leader / follower)** çiftidir:
- **Takipçi (follower)** = asıl işi yapan robot kol.
- **Lider (leader)** = takipçiyi teleoperasyonla kontrol etmek için elimle hareket ettirdiğim küçük kol.

İki kolumun seri portları (`myport.txxt` dosyasına kaydedildi):
- `leader  = /dev/tty.usbmodem5B420006171`
- `follower = /dev/tty.usbmodem5B421352311`

### Bölüm 1 — Donanım (laboratuvarda)

- **3D baskı parçalarını** motorlarla birleştirerek iki kolu da (lider + takipçi) monte ettik.
- **SO-101 Motor Pro kitini** kullanarak **motor kablolarını** bağladık ve düzenledik.
- Motorları yapılandırdık — veri yolundaki her Feetech servonun benzersiz bir **kimliğe (ID, 1–6)** ve
  doğru **baud hızına** ihtiyacı var; böylece denetleyici her koldaki altı eklemi tek tek adresleyebiliyor.

### Bölüm 2 — Yazılım kurulumu (komutlar)

Aşağıdaki her şey `~/Documents/coding/fouad_so101` proje klasöründen çalıştırıldı.

**1. Ortamı kontrol et.** Önce hangi Python sürümlerinin, git ve ffmpeg'in mevcut olduğunu kontrol ettim.
Sistemdeki Python 3.9, LeRobot için **çok eski**.

```bash
python3 --version                 # 3.9.6 -> çok eski
which python3.11 python3.12 python3.13
ffmpeg -version                   # zaten kurulu (LeRobot video için gerekli)
```

**2. Sanal ortamı oluştur.** Önce Python 3.11 denedim, ama LeRobot'un `pyproject.toml` dosyası
**Python >= 3.12** gerektiriyor; bu yüzden ortamı 3.12 (Apple Silicon yerel / arm64) ile yeniden kurdum.

```bash
rm -rf .venv
/usr/local/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python --version        # Python 3.12.3
```

**3. LeRobot'u klonla.** Yer/zaman kazanmak için yüzeysel (shallow, sadece son commit) klon.

```bash
git clone --depth 1 https://github.com/huggingface/lerobot.git lerobot
```

**4. LeRobot'u `feetech` ekiyle kur.** SO-101 **Feetech** servoları kullanır; bu yüzden `feetech`
isteğe bağlı bağımlılık grubunu kuruyorum. `-e` bunu *editable* (klonlanan kaynağa işaret eden) kurulum yapar.

```bash
.venv/bin/pip install -e "./lerobot[feetech]"
```

> ⚠️ **Dikkat — disk alanı.** İlk kurulum, PyTorch indirilirken `No space left on device` (disk dolu)
> hatasıyla başarısız oldu. ~1.5 GB yer açtım ve aynı komutu tekrar çalıştırdım; önbellekteki wheel
> dosyaları yeniden kullanıldığı için ikinci seferde hızlıca tamamlandı.

**5. Kurulumu doğrula.** Kütüphanenin import edildiğini, PyTorch'un Apple GPU'yu (MPS) gördüğünü,
Feetech SDK'nın mevcut olduğunu ve CLI'nin çalıştığını doğrula.

```bash
.venv/bin/python -c "import lerobot, torch; print(lerobot.__version__, torch.__version__, torch.backends.mps.is_available())"
# -> 0.5.2  2.11.0  True       (MPS = Apple GPU mevcut)
.venv/bin/python -c "import scservo_sdk; print('feetech-servo-sdk OK')"
.venv/bin/lerobot-find-port      # seri portları listeler / her kolu tanımlamaya yardımcı olur
```

**6. Disk alanını geri kazan** (pip indirme önbelleğini temizleme, isteğe bağlı):

```bash
.venv/bin/pip cache purge
```

### Bölüm 3 — LeRobot ile motor yapılandırması

CLI'yi `.venv/bin/` öneki olmadan kullanmak için önce ortamı etkinleştir:

```bash
source .venv/bin/activate
```

**Her kolun portunu bul** (istendiğinde USB'yi çıkar/tak, böylece hangisinin hangisi olduğunu anlar):

```bash
lerobot-find-port
```

**Motorları kur** — her servoya kimliğini (ID) + baud hızını atar. **Her seferinde tek kol** çalıştır
ve motorları tek tek bağlamak için yönergeleri izle.

> 🔑 **Önemli ayrıntı (bununla karşılaştık):** **takipçi (follower)** bir `--robot.type`'tır,
> **lider (leader)** ise bir `--teleop.type`'tır. `--teleop.type=so101_follower` vermek **yanlıştır**
> ve hata verir; çünkü `follower` yalnızca `--robot.type` altında bulunur.

```bash
# Takipçi (robot kol)
lerobot-setup-motors --robot.type=so101_follower --robot.port=/dev/tty.usbmodem5B421352311

# Lider (teleop kol)
lerobot-setup-motors --teleop.type=so101_leader --teleop.port=/dev/tty.usbmodem5B420006171
```

### Bölüm 4 — Git & GitHub

Klasörü bir git deposuna dönüştür, LeRobot'u **submodule** olarak ekle (sonra güncelleyebilmek için),
commit'le ve **public (herkese açık)** depo olarak gönder.

```bash
git init -b main

# lerobot'u submodule olarak ekle. Klasör zaten bir klon olduğu için git onu yerinde yeniden kullandı
# ("Adding existing repo at 'lerobot' to the index") — yeniden indirme yok.
git submodule add https://github.com/huggingface/lerobot.git lerobot

git add -A
git commit -m "Day 1: project setup — diary, env, and lerobot submodule"

# Hesabımın altında public depo oluştur + gönder
gh repo create fouad_so101 --public --source=. --remote=origin --push \
  --description "My journey with the SO-101 robotic arms and VLA models"
```

Depo: <https://github.com/fouad1233/fouad_so101>

**Bu depoyu sonra klonlamak (submodule ile birlikte):**

```bash
git clone --recurse-submodules https://github.com/fouad1233/fouad_so101.git
# veya, submodule olmadan klonladıysan:
git submodule update --init --recursive
```

**LeRobot submodule'ünü sonra güncellemek:**

```bash
cd lerobot && git checkout main && git pull && cd ..
git add lerobot && git commit -m "Update lerobot submodule" && git push
```

### Sıradaki — 2. Gün

- İki kolu da **kalibre et** (her eklemi tam hareket aralığında hareket ettir; bir `id` altına kaydedilir):

  ```bash
  lerobot-calibrate --robot.type=so101_follower  --robot.port=/dev/tty.usbmodem5B421352311 --robot.id=my_follower
  lerobot-calibrate --teleop.type=so101_leader   --teleop.port=/dev/tty.usbmodem5B420006171 --teleop.id=my_leader
  ```

- **Teleoperasyon** — lider ile takipçiyi kontrol et (aynı `id`'leri tekrar kullan):

  ```bash
  lerobot-teleoperate \
    --robot.type=so101_follower --robot.port=/dev/tty.usbmodem5B421352311 --robot.id=my_follower \
    --teleop.type=so101_leader  --teleop.port=/dev/tty.usbmodem5B420006171 --teleop.id=my_leader
  ```

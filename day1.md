# Day 1 — Building the SO-101 Arms & First Software Setup

**Date:** 2026-06-23

## English

Today was the first day of my journey into robotic arms and Vision-Language-Action (VLA) models.

In the lab we set up the two **SO-101** robotic arms — the **leader** and the **follower**:

- Assembled the 3D-printed parts together with the motors to build both arms.
- Wired and routed the motor cables using the **SO-101 Motor Pro kit**.
- Configured the motors — assigning each servo its **ID** and **baud rate** — so the bus can address all six joints of each arm.

On the software side I prepared my development environment:

- Created a **Python 3.12** virtual environment (`.venv`).
- Cloned the **LeRobot** repository and added it as a **git submodule** so I can keep it updated later.
- Installed LeRobot with the `feetech` extra (the SO-101 uses Feetech servos) and confirmed **PyTorch** works with the Apple GPU (MPS available).
- Ran `lerobot-setup-motors` to write the motor IDs/baud rate for the follower arm.

**Tomorrow (Day 2):** calibrate both arms and try **teleoperation** — controlling the follower with the leader.

## Türkçe

Bugün robotik kollar ve Görü-Dil-Eylem (VLA) modelleri yolculuğumun ilk günüydü.

Laboratuvarda iki **SO-101** robotik kolunu kurduk — **lider (leader)** ve **takipçi (follower)**:

- 3D baskı parçalarını motorlarla birleştirerek iki kolu da monte ettik.
- **SO-101 Motor Pro kitini** kullanarak motor kablolarını bağladık ve düzenledik.
- Motorları yapılandırdık — her servoya **kimlik (ID)** ve **baud hızı** atayarak — böylece veri yolu her koldaki altı eklemi de adresleyebiliyor.

Yazılım tarafında geliştirme ortamımı hazırladım:

- **Python 3.12** sanal ortamı (`.venv`) oluşturdum.
- **LeRobot** deposunu klonladım ve daha sonra güncelleyebilmek için **git submodule** olarak ekledim.
- LeRobot'u `feetech` ekiyle kurdum (SO-101 Feetech servoları kullanıyor) ve **PyTorch**'un Apple GPU (MPS) ile çalıştığını doğruladım.
- Takipçi kol için motor kimliklerini/baud hızını yazmak üzere `lerobot-setup-motors` komutunu çalıştırdım.

**Yarın (2. Gün):** iki kolu da kalibre etmek ve **teleoperasyonu** (lider ile takipçiyi kontrol etmeyi) denemek.

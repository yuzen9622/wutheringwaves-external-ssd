# 鳴潮 Mac：將遊戲內追加資源放到外接 SSD

繁體中文 | [English](README_en.md)

> 單機實測紀錄與可還原操作指南，不是官方支援方案。

**本體裝到外接還不夠：這次透過「獨立測試副本重新簽章 + 將該副本的 Saved 資料夾連到外接 SSD」，成功下載追加資源，使用者也回報可以實際遊玩。沒有關閉 SIP。**

## 先看風險與適用範圍

- 這會移除**測試副本**原有的 entitlements（權利設定），包含 App Sandbox，並改用本機 ad-hoc 簽章。**不是只有換下載位置，也會降低這個副本的隔離保護。**
- 沒有關閉系統 SIP、Gatekeeper 或全機沙盒；沒有修改遊戲執行邏輯、繞過反作弊或帳號驗證。
- 重新簽章的副本不再具有原本的 Apple／開發者簽署身分。Apple 登入、鑰匙圈、App Store 收據／完整性驗證、更新等功能可能失效。
- **不保證符合遊戲服務條款、不保證帳號不受影響。**在意帳號風險者，請先向官方確認；不願承擔者不要操作。
- 測試過程曾發生當機，之後使用者回報可以玩；**長時間穩定性、所有登入方式、後續版本更新與其他電腦均未驗證。**
- 只從 App Store 取得正版原件。不要下載別人重新簽章的遊戲；分享這份說明即可，不要散布遊戲副本、收據或個人資料。
- **保留原版、備份現有資料。不要直接修改唯一一份遊戲。**

## 實測環境

| 項目         | 環境                       |
| ------------ | -------------------------- |
| 系統         | macOS 27.0.1               |
| 遊戲         | Mac App Store《鳴潮》3.7.0 |
| 執行檔架構   | arm64                      |
| 外接磁碟     | APFS SSD                   |
| 遊戲安裝位置 | 外接 SSD                   |

## 為什麼 App Store 的外接安裝設定不夠？

App Store 可以把大型 App 本體安裝到外接磁碟，但遊戲自己下載的資源仍可能存入使用者的內建磁碟資料夾。

本次觀察到的路徑：

| 版本             | 資料位置                                                                            |
| ---------------- | ----------------------------------------------------------------------------------- |
| 原版（有沙盒）   | `~/Library/Containers/com.kurogame.wutheringwaves.global/Data/Library/Client/Saved` |
| 本次重新簽章副本 | `~/Library/Client/Saved`                                                            |

**必須確認你自己的實際路徑。**`Client` 名稱很普通，其他 Unreal Engine 遊戲也可能使用；若不是此次副本新建或無法確定歸屬，先停下，不能照抄搬走。

## 操作前準備

- 遊戲本體已透過 App Store 裝到外接 APFS 磁碟。
- 外接有足夠空間放本體、追加資源、備份及日後更新。APFS clone 可先共用區塊，但後續變更會繼續占空間。
- 內建也要留系統、交換檔與快取空間；這個方案**不是內建零占用**。
- 完全退出原版與測試版。不要在下載、更新或遊戲執行中搬資料。
- 下方命令需要 macOS Terminal、`codesign`、`ditto` 和 Python 3。Python 3 若不存在，先由可信來源自行安裝；文件不會自動安裝任何工具。
- 不要使用 `sudo`、`chmod -R 777` 或關閉安全保護來掩蓋操作錯誤。

## 腳本包與依賴

這個資料夾可以整包分享。腳本只整理原指南流程；**尚未在真實遊戲上執行這組腳本，不要在既有正常運作的安裝上重跑。**原本單機成功不等於新機、新版或這組包裝腳本已通過遊戲驗收。

需要 macOS、Python 3，以及系統的 `diskutil`、`cp`、`ditto`、`codesign`、`pgrep`、`ps`、`open`、`lsof`。不自動安裝、不使用 sudo。沒有一鍵全部執行、更新或刪除命令。

```text
wutheringwaves-external-ssd/
├── README.md
├── README.en.md
├── config.env.example
├── scripts/
│   ├── common.sh
│   ├── safety.py
│   ├── preflight.sh
│   ├── create-test-app.sh
│   ├── launch.sh
│   ├── inspect.sh
│   ├── migrate-saved.sh
│   ├── verify.sh
│   ├── restore-saved.sh
│   ├── migrate_saved.py
│   └── restore_saved.py
└── tests/test_safety.py
```

## 1. 設定自己的路徑

在 Terminal 切到**這個資料夾**（例如 `cd "$HOME/Documents/wutheringwaves-external-ssd"`），複製範本，編輯 `config.env` 後保存：

```bash
cp -n config.env.example config.env
open -e config.env
bash scripts/preflight.sh
```

`config.env` 是可信任的 shell 設定檔，不要載入別人不明的程式碼。範本的 `VOLUME`、`ORIGINAL`、`WORK`、`TEST_APP` 都使用帶引號的通用路徑；磁碟名可以有空白。請改成自己的路徑，不要把個人設定檔一起分享。

每個腳本會自行從本包位置載入設定，不依賴上一個 shell 的 export。除了離線還原，會檢查實際掛載、`diskutil` 的 APFS 資訊、解析後路徑在選定 volume 中、來源與副本同 volume、正確原版 bundle ID、工作目錄不在原版內，並拒絕符號連結路徑／祖先。仍需人工閱讀容量與裝置資訊，確認選的是正確 SSD。原版名稱或位置不同時修正 `ORIGINAL`，**不可把 `TEST_APP` 設成原版**。命令報錯就停止，不要跳過檢查。

## 2. 建立獨立副本，再重新簽章

完全退出原版與測試版，再執行：

```bash
bash scripts/create-test-app.sh
```

會提示輸入 `YES`。建立副本、啟動、搬移、還原等會寫入的腳本均需確認；明確接受風險時可加 `--yes`，但不會略過安全檢查。

此腳本要求 **WORK 尚不存在**，以排他方式建立工作目錄，避免同時執行或覆寫已有副本。使用 macOS `cp -cR` 的 APFS copy-on-write clone，再以空 entitlements 重新 ad-hoc 簽章，執行 `codesign --verify --deep --strict`，並顯示原版簽章。原版應仍顯示 Apple Mac OS Application Signing，而非 ad-hoc。

若失敗，副本／工作目錄會保留以供檢查，不會刪除原版或自動清理。不要直接重跑或改成覆寫；確認後使用另一個全新 WORK。驗證可能超過一分鐘，等它結束。

`codesign --verify` 成功不代表遊戲官方接受這個副本，也不代表 Gatekeeper、登入、反作弊或更新一定會通過。若系統或遊戲拒絕，停止；本指南不提供繞過那些檢查的步驟。

## 3. 首次啟動副本，確認資料位置

```bash
bash scripts/launch.sh
pgrep -fl '/Contents/MacOS/Client-Mac-Shipping'
# 將 12345 改成剛剛看到的「測試副本」PID。
bash scripts/inspect.sh 12345
```

檢查腳本要求正整數 PID，使用 `ps` 核對其 executable 完全等於設定中的測試 App 路徑，再以 `lsof` 顯示檔案。不接受原版 PID，也不把輸出當成成功證明。

本次副本能進到資源下載前的空間檢查。**先不要開始大量下載，也不要為了測試輸入帳號密碼。**

本次看到 `~/Library/Client/Saved/DeviceSaved/DeviceStorage.db` 等檔案。如果你看到不同位置、看到原版程序，或原先已有不明來源的 `~/Library/Client`，**停止，不要執行下一步**。

確認後，按取消並**完全退出遊戲**。資料庫仍開啟時不能搬移。

## 4. 備份 Saved、複製到外接、建立符號連結

此程式只適用於上一步確認屬於測試遊戲的 `~/Library/Client/Saved`，不動原版 container。`Client` 名稱很普通，所以必須明確加上歸屬確認旗標：

```bash
bash scripts/migrate-saved.sh --ack-client-saved
# 非互動執行也必須確認歸屬：
# bash scripts/migrate-saved.sh --ack-client-saved --yes
```

程式會逐檔 SHA-256 核對、保留內建原件，拒絕覆寫既有外接 Saved（包括懸空連結）。它在搬原件**之前**檢查外接實際為另一個 device、備份與來源同 device，並再次確認遊戲關閉；`pgrep` 的 0 表示仍在執行、1 才是沒程序、其他結果視為錯誤。來源或祖先有符號連結也會停止。

備份／階段 JSON 位於 `~/.local/state/wuthering-external-test/`，使用唯一名稱與排他鎖。外接目的地先排他保留，複製核對完成才把本機原件改名、建立連結。各階段先後寫入還原紀錄，不刪除任何備份。**若已成功，不要再次執行。**

備份包含遊戲個人資料，請妥善保管，不要上傳分享。保存輸出的**還原紀錄完整路徑**。若任何階段失敗，先查看 JSON 的 `phase` 與來源、備份、外接目錄狀態，不要刪掉「看起來多出來」的資料夾，也不要盲目重跑。程序中斷可能留下 `.operation-lock` 或 `.tmp`；先確認沒有腳本／遊戲仍在執行、保全各份資料，再人工處理。未建立 matching symlink 的中間階段，還原脚本會拒絕猜測，需依紀錄人工恢復；沒有提供自動刪除／強制繼續命令。

## 5. 驗證真的下載到外接

```bash
bash scripts/launch.sh
pgrep -fl '/Contents/MacOS/Client-Mac-Shipping'
# 將 12345 改成這次測試副本的 PID。
bash scripts/verify.sh 12345
```

若不再出現空間不足，開始下載約 20～30 秒，再暫停並檢查。`verify.sh` 只顯示 `readlink`、`df`、`du` 與該 PID 的外接 `lsof` 快照；可再次檢查比較大小變化，**不會自動宣稱成功**。

成功的判準：

1. 啟動的是外接的 `WutheringWaves-Test.app`，不是原版。
2. 空間檢查通過。
3. 外接 `Saved/Resources` 實際增長。
4. 下載時 `lsof` 顯示外接的 `.pak.download` 或其他資源檔正在開啟。暫停或下載完成後可能看不到 `.download`，不能只靠它判定失敗。
5. 後續再確認下載完成、登入與遊玩；每一項分開驗證。

**只有連結建立成功、或畫面顯示「下載中」，都不足以宣稱完成。**

## 日常使用、當機與更新

- 在 Finder 找到 `WutheringWaves-Test.app`，拖到 Dock。每次先接上 SSD，確認掛載名稱沒有變。
- 依 `config.env` 的 TEST_APP 路徑在 Finder 找到副本；不要從 App Store 按「開啟」誤開原版。
- 遊戲執行或下載時不要拔線、退出磁碟或讓連接不穩。
- 即使資源在外接，內建仍可能產生快取、日誌、交換檔。當機時也要檢查內建剩餘空間，但不能未查證就認定這是當機原因。
- 當機不等於資料消失。先確認副本和連結仍在、是否誤開原版，再查看錯誤資訊；不要立即刪除數十 GB 的資源。
- **不要把更新視為已解決。**App Store 通常管理原版，不保證管理這個測試副本；遊戲內更新也可能更改執行檔、簽章或資料格式。
- 更新前退出遊戲、備份資料。若需要新版副本，從新的正版原件建立**另一個新測試目錄**，重新驗證相容性；不要直接覆蓋唯一能用的版本，也不要讓兩個版本同時寫同一份 Saved。
- 不提供自動移除安全限制、反作弊繞過或每次開啟自動重簽工具。

## 如何還原

先完全退出所有《鳴潮》程序。

### 只想回到官方原版

原版 App 與 container 在本指南中沒有修改，可直接從 App Store 或原版位置啟動。原版仍可能要求內建空間；它**不會自動接手測試副本的外接資源**。

### 還原測試副本的 Saved 路徑

下面會將 symlink 改名保留，並把操作前的本機原件放回來。**外接新資料仍完整保留，但遊戲會回到操作前那份本機資料。**如果之後有新的本機存檔／設定，應先備份外接 Saved 並自行確認如何保留，不能假設全部都在雲端。

傳入步驟 4 印出的 **JSON 完整絕對路徑**，不自動猜「最新備份」：

```bash
bash scripts/restore-saved.sh "$HOME/.local/state/wuthering-external-test/migration-請換成實際時間.json"
# 明確接受回到搬移前資料時，可在最後加 --yes。
```

還原不載入 `config.env`、不要求外接掛載或原版 App 存在，懸空連結也可以還原。仍要求遊戲完全退出、來源精確為本機 `~/Library/Client/Saved`、JSON 與備份直接位於指定 state 目錄、無 symlink 祖先、備份 SHA 與紀錄一致、目前連結完全符合紀錄。連結會改名保留，外接 Saved 與 App 不刪除；最後 phase 記為 `restored`。不符合紀錄時停止，不會覆寫另一份來源或猜測資料位置。

沒有提供自動刪除命令。確認不再需要後，再自行清理測試副本與備份；切勿在遊戲仍使用它們時清理。

## 換電腦時怎麼做？

1. 保存這份 README、原版來源資訊、外接 `Saved` 及必要的個人備份；**不要只複製 App 而漏掉 Saved**。
2. 新電腦先確認硬體、macOS 與遊戲相容性；透過 App Store 取得自己帳號可用的正版原件。不要假設舊副本的收據／簽章在新電腦一定可用。
3. 在新電腦重新建立獨立副本，先確認能啟動和實際資料位置。
4. 如果外接已有舊 Saved，**步驟 4 會故意停止**。先把舊資料做另一份備份，再決定測試新版的副本資料；不要為了通過檢查刪掉舊資料。
5. 新電腦的 `~/Library/Client/Saved` 連結必須重新建立；SSD 掛載名稱不同時，舊絕對路徑不會自動修正。
6. 既有資源能否沿用、是否需要重新驗證／下載，取決於遊戲版本。帳號仍可能需要重新登入，鑰匙圈項目不保證跟著 Saved 搬移。

本指南可重現本次測試流程，**不是新機或新版免驗證的一鍵遷移工具**。

## 隔離測試（不操作遊戲）

```bash
for script in scripts/*.sh; do bash -n "$script" || break; done
python3 -m unittest discover -s tests -v
python3 -O -m unittest discover -s tests -v
```

測試只在臨時目錄建立小型假資料，mock macOS 命令與跨 device 判斷；涵蓋既有目的地、遊戲執行／檢查錯誤、複製不一致、還原 matching／懸空連結、路徑與備份篡改等。`-O` 同樣檢查 guards 不因 Python 最佳化失效。這不是實際 APFS clone、簽章、下載、登入或新機的驗收。

## 參考與分享界線

- [Apple：更改 App Store 設定](https://support.apple.com/guide/app-store/change-settings-mchlp2257/mac)：大型 App 的外接 APFS 安裝選項；不等於遊戲內資源位置也可選。
- [Apple：Accessing files from the macOS App Sandbox](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox)：沙盒檔案授權原理；不是本方案的官方背書。
- [鳴潮官方網站](https://wutheringwaves.kurogames.com/en/main)
- 本機命令說明：`man codesign`、`man cp`、`man ditto`、`man lsof`。

分享時請保留風險、實測版本與未驗證項目。不要宣稱「官方支援」「絕對不會封號」「不用內建空間」或「永久適用」。

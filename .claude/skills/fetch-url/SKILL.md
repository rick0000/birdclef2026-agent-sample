---
name: fetch-url
description: URL を引数に取り、Kaggle Discussion なら公式 CLI (`uv run kaggle ... topics show`) で本文＋コメントを取得、それ以外の JS レンダリングページは Playwright MCP で取得し、`knowledge/resources/<slug>.md` に L1 知見ファイルとして保存し、`knowledge/resources/index.md` に 1 行 summary を追記する。
allowed-tools: Bash, Read, Write, Edit, Glob, mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_close, mcp__playwright__browser_wait_for, mcp__playwright__browser_click
argument-hint: <url>
---

# fetch-url

URL のページ本文を取得し、`knowledge/resources/<slug>.md` に L1 知見ファイルとして保存する。さらに `knowledge/resources/index.md` に 1 行 summary を追記する。

**取得手段は URL で振り分ける:**

- **Kaggle Discussion**（コンペ/一般フォーラム）→ 公式 Kaggle CLI (`uv run kaggle`) で本文＋コメントを取得（**Playwright 不要**。安定・軽量・トークン節約）。
- **それ以外**（Kaggle Code/notebook、Datasets ページ、非 Kaggle の JS ページ等）→ 従来どおり Playwright MCP で snapshot 取得。

> kaggle CLI は `>=2.2.0`（forums/competitions topics 対応）が必要。**必ず `uv run kaggle`** で呼ぶ（PATH の bare `kaggle` は旧 1.7.x で forums 非対応）。

## 設計原則

- **L1 (`knowledge/resources/<slug>.md`)**: 取得した本文を **そのまま残す**。**要約・抜粋・編集はしない。情報を落とさない。**（本文・コメント・コード・表をそのまま）
- **L2 (`knowledge/resources/index.md`)**: L1 の一覧。**1 行 summary はここで初めて書く**。要約はこの層だけ。

## 引数

- `<url>` — 取得したいページの URL。なければユーザに求める。

## 手順

### 1. URL を判定して経路を決める

URL のパスから種別を判定する:

| URL パターン | 経路 | コマンド |
|---|---|---|
| `kaggle.com/competitions/<slug>/discussion/<id>`（`/c/<slug>/...` も同様） | CLI | `uv run kaggle competitions topics show <slug> <id> --page-size 200` |
| `kaggle.com/discussions/<category>/<id>` | CLI | `uv run kaggle forums topics show <id> --page-size 200` |
| 上記以外（Kaggle Code/notebook, Datasets, 非 Kaggle 等） | Playwright | → 「手順 B」へ |

`<slug>` `<id>` は URL パスから抽出する。判定できない Kaggle Discussion は `forums topics show <id>` を試す。

### 2. slug（保存ファイル名）を決める

URL のパス末尾やタイトルから kebab-case で生成する。例:
- `https://www.kaggle.com/competitions/birdclef-2026/discussion/123456` → `kaggle-birdclef2026-discussion-123456`
- 既存ファイルと衝突したら `<slug>-2` のように連番を足して上書きを防ぐ。

---

## 手順 A: Kaggle Discussion（CLI 経路）

### A-1. CLI で取得

```bash
# コンペ discussion
uv run kaggle competitions topics show <slug> <id> --page-size 200
# 一般フォーラム discussion
uv run kaggle forums topics show <id> --page-size 200
```

- 出力は本文＋コメントの整形済みテキスト。**そのまま L1 に保存する**（snapshot 変換は不要）。
- エラー（403 / not found 等）が出たらユーザに報告して停止。コンペ discussion を `forums` 側で叩くと 403 になることがあるので、その場合は `competitions topics show` を使う。
- コメントが 200 件を超える場合は `--page-token` で続きを取得して連結する。

### A-2. L1 を作成

`knowledge/resources/<slug>.md` を作る。CLI 出力を **そのまま本文として貼る**（要約・編集しない）。冒頭に frontmatter:

```markdown
---
source_url: <url>
fetched_at: <ISO8601 UTC>
title: <トピックタイトル>
slug: <slug>
source: kaggle-cli
---

# <タイトル>

<CLI 出力をそのまま>
```

→ 手順 C（L2 更新）へ。

---

## 手順 B: その他のページ（Playwright 経路）

### B-1. navigate

```
mcp__playwright__browser_navigate(url=<url>)
```
SPA で遅延ロードする場合は `mcp__playwright__browser_wait_for(text=<本文の一部>)` で待機。

### B-2. snapshot をファイルに保存

```
mcp__playwright__browser_snapshot(filename=".playwright-mcp/<slug>.md")
```
- **必ず filename 指定**（応答に乗せると context 圧迫）。保存 root は `.playwright-mcp/` か project root 配下のみ。
- 本文が取れなければ `browser_wait_for(text=...)` で待ってから再取得。それでも不可ならユーザに報告して停止。

### B-3. 折りたたみを展開して取り直す

snapshot 内に `button "N more replies"` / `"Show more"` / `"Read more"` 等の **本文を開く展開ボタン**があれば `mcp__playwright__browser_click(target=<ref>, element=...)` で順に開く。
- 1 クリック → snapshot 取り直し → 次のボタン、を繰り返す（DOM が変わり ref が振り直されるため）。`more` 系が無くなるまで（上限 20 回目安）。
- Cookie 同意 / ログイン誘導 / 「次へ」/ Hide replies 等のナビゲーション系は押さない。
- 全部開いたら最終 snapshot を上書き保存。

### B-4. snapshot を md 化して L1 を作成

`.playwright-mcp/<slug>.md` を読み、`knowledge/resources/<slug>.md` を作る。**形式変換のみ。要約・抜粋・編集しない。**

| snapshot 要素 | md 変換 |
|---|---|
| `heading [level=N]` | `#`×N 見出し |
| `paragraph` | 段落 |
| `list`/`listitem` | `-` リスト（ネスト保持） |
| `table` | md table |
| `code` | ` ``` ` フェンス |
| `link "text"`(/url:) | `[text](url)` |
| `blockquote` | `>` |
| `strong` | `**...**` |
| 投稿者名・日時・upvote・rank | コメントヘッダとして残す |

除いてよいノイズ: ページヘッダ/フッターのナビ、Skip to content、Cookie banner、Sign in/Register、装飾画像、upvote/more/reply ボタン、"(opens in a new tab)"。サイドバー/tag 一覧は本文末尾に残す。

frontmatter（`source: playwright`）を付けて保存:

```markdown
---
source_url: <url>
fetched_at: <ISO8601 UTC>
title: <ページタイトル>
slug: <slug>
source: playwright
---

# <タイトル>

<本文 md>
```

### B-5. browser を閉じる

```
mcp__playwright__browser_close()
```

---

## 手順 C: L2 index.md を更新（両経路共通）

`knowledge/resources/index.md` に 1 行追記（無ければ新規作成）。

```markdown
| <slug> | <title> | <summary> | <source_url> | <fetched_at> |
```

`summary` は **このリソースが何の話か / 何が学べるか** を ~80 字以内で 1 行に。L1 を読んで判断する（**要約はこの層でだけ行う**）。

ヘッダが無ければ先頭に追加:

```markdown
# 外部リソース知見一覧

source: fetch-url skill が保存した L1 知見ファイルの一覧。要約はこの index にだけ書く。

| slug | title | summary | source_url | fetched_at |
|------|-------|---------|------------|------------|
```

## 完了報告

- L1 知見ファイル `knowledge/resources/<slug>.md` のパス
- L2 index に書いた summary（1 行）
- 使った経路（kaggle-cli / playwright）

## 注意事項

- **Kaggle Discussion は CLI 優先**（`uv run kaggle`、要 `kaggle>=2.2.0`）。Playwright は CLI で取れないページのフォールバック。
- **L1 は要約しない**（本文・コメント・コード・表をそのまま）。**L2 の summary だけが要約**。
- 1 サイクル 1 URL。既存 slug と衝突したら連番で上書き防止。
- Kaggle Discussions は login 不要で取れる。

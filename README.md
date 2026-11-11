# MoomooAI 市場カレンダーデモ

米国の主要な経済指標、NYSEの休場日を月間カレンダーに表示します。日付や種類を選ぶと、発表時刻と出典を確認できます。

![初版のカレンダー画面](screenshot.jpg)

## 起動方法

リポジトリをダウンロードし、ブラウザで index.html を開きます。Python 3 がある場合は、以下で [ローカル画面](http://127.0.0.1:8000/) も開けます。

```sh
python -m http.server 8000 --bind 127.0.0.1
```

## データ更新

GitHub Actions が毎日 11:23 JST に今月・翌月のデータを取得します。Actions の「Refresh public market calendar」から手動実行もできます。取得エラー時は前回の公開データを保持します。ローカルで更新する場合は以下を実行します。

```sh
python -m pip install -r requirements.txt
python scripts/update_calendar.py
```

- 経済指標は [FRED](https://fred.stlouisfed.org/releases/calendar) のCPI、PPI、雇用統計、GDP、PCE、FOMC声明、JOLTSを収録。米国中部時間から日本時間へ換算します。
- 休場は [NYSE](https://www.nyse.com/trade/hours-calendars) の公表表から全日休場を取得し、取引所の現地日付で表示します。
- 決算予定・EPS予想・アナリスト推奨件数は、公開再配布を許諾する [Finnhub契約](https://api.finnhub.io/pricing-startups-and-enterprise) がある場合に利用できます。契約確認後、Actionsのシークレット FINNHUB_API_KEY と変数 ENABLE_LICENSED_DATA=true を設定します。対象は米国の主要7銘柄です。公開されるのは正規化したデータで、キーはActions内に保持されます。

公開対象は市場情報の取得と表示です。自動売買、発注、口座情報、本番システムへの接続は含みません。

市場ニュースではFRB・BEA・ECB・日本銀行・EIA・米国勢調査局と企業IRの公式発表を、日付・見出し・原典リンクで毎日更新します。発表元で絞り込めます。

[非公開版の表示項目と公開範囲](DISPLAY-INVENTORY.md)

決算予定は [Home Depot公式IR](https://ir.homedepot.com/events-and-presentations) の公表済みイベントから日付・時刻・出典リンクを毎日取得します。Walmartも公式イベントから取得し、各社の現地時刻を表示します。

### 発表済みの指標と決算書

- 米国CPI、PPI、雇用統計、GDP、PCEの公表値を掲載します。対象期間を揃えた値がある場合は前回と今回を比較できます。
- 雇用者数の前月差は[BLSの公表系列](https://www.bls.gov/ces/)から計算し、[ALFRED](https://alfred.stlouisfed.org/series?seid=PAYEMS)の発表日時点の値と異なる場合に初回値を併記します。
- GDPはBEAの速報値と改定値が揃った場合、同じ四半期で比較できます。
- 財務指標はHome Depot、Walmart、Apple、Microsoft、NVIDIAの売上高・純利益・希薄化後EPSと公式原文を表示します。

### 公式IRと移動平均線

- 公式決算予定: [Home Depot](https://ir.homedepot.com/events-and-presentations)、[Walmart](https://corporate.walmart.com/news/events)。取得結果を銘柄別に表示し、0件と取得失敗を区別します。
- 移動平均線: 銘柄と日足CSVを指定します。列は `date,close`（単一銘柄）か `symbol,date,close`（複数銘柄）、日付は YYYY-MM-DD、対象銘柄は201営業日以上。株式分割の影響を避けるには調整済み終値を close 列に入れてください。50日・200日線と直近の交差をブラウザで計算します。CSVは外部に送信されません。

公開画面: https://takayakato0519-spec.github.io/moomoo-market-calendar-demo/

カレンダーの日付カードは非公開版のカレンダータブから移植しています。公開データに合わせた接続部分とイベント詳細は calendar-ui/src にあります。UI変更時は calendar-ui で npm ci と npm run build を実行し、calendar-assets を更新します。

### 非公開版からの移植範囲

| タブ | 公開版の範囲 |
| --- | --- |
| カレンダー | 元の日付カードと、公式出典の予定。 |
| ニュース | 元のニュースカードと記事リンク。官公庁・中央銀行・企業IRの公式発表を表示。銘柄別記事・感情スコアは対象外。 |
| 本日予定 | 公開カレンダーから当日のイベントを抽出。非公開版の売買予定・取引時間帯の分析は対象外。 |
| アナリスト、商品先物、指数・レバレッジ状況 | 元のデータの公開再配布条件や、戦略との分離を確認できていないため移植対象外。 |
| おすすめ銘柄・スクリーニング・運用関連 | 戦略、注文、口座・運用データを参照するため移植対象外。 |

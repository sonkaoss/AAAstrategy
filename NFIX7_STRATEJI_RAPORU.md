# NostalgiaForInfinityX7 - Kapsamli Strateji Analiz Raporu
## Yeni Strateji Icin Referans Dokumani

**Dosya:** NostalgiaForInfinityX7.py (76,385 satir)
**Versiyon:** v17.3.971
**Framework:** Freqtrade IStrategy (INTERFACE_VERSION = 3)
**Yazar:** iterativ

---

## 1. GENEL MIMARI

### 1.1 Temel Yapilandirma
```
Timeframe: 5m (ana islem zamandilimi)
Informative Timeframes: [15m, 1h, 4h, 1d]
BTC Informative Timeframes: [5m, 15m, 1h, 4h, 1d]
Startup Candle Count: 800
Stoploss: -0.99 (cok gevsek - gercek cikislar sinyal bazli)
Trailing Stop: Devre disi
ROI: Kullanilmiyor (tamamen sinyal bazli cikis)
Position Adjustment: Aktif
```

### 1.2 Neden Guclu?
Bu strateji su temel prensiplere dayanarak guclu:

1. **Coklu Mod Sistemi** - 10 farkli giris modu (normal, pump, quick, rapid, rebuy, grind, btc, top_coins, scalp, high_profit)
2. **Coklu Zaman Dilimi Analizi** - 5 farkli timeframe uzerinde 60+ indikator
3. **Gelismis Pozisyon Yonetimi** - Grinding (DCA), derisk, buyback sistemleri
4. **Adaptif Cikis** - Kar seviyesine gore degisen cikis kosullari
5. **Global Koruma** - Piyasa kosullarina gore giris filtreleme
6. **Spot/Futures Esnekligi** - Her iki mod icin ayri parametreler

---

## 2. INDIKATORLER (Tam Liste)

### 2.1 RSI Ailesi
| Indikator | Periyot | Timeframe | Kullanim |
|-----------|---------|-----------|----------|
| RSI | 3 | 5m, 15m, 1h, 4h, 1d | Hizli momentum, asiri satis tespiti |
| RSI | 4 | 5m | Cok kisa vadeli momentum |
| RSI | 14 | 5m, 15m, 1h, 4h, 1d | Standart asiri alis/satis |
| RSI | 20 | 5m | Orta vadeli momentum |
| RSI_3_change_pct | - | 5m | RSI degisim hizi |
| RSI_14_change_pct | - | 5m | RSI degisim hizi |

### 2.2 Hareketli Ortalamalar
| Indikator | Periyot | Timeframe |
|-----------|---------|-----------|
| EMA | 3, 9, 12, 16, 20, 26, 50, 100, 200 | 5m (ana) |
| EMA | 12, 20, 26 | 15m |
| EMA | 12, 200 | 1h, 4h |
| SMA | 9, 16, 21, 30, 200 | 5m |
| SMA | 16 | 1h |

### 2.3 Bollinger Bands
| Yapilandirma | Timeframe | Bilesenler |
|--------------|-----------|------------|
| BB(20, 2.0) | 5m, 1h, 4h, 1d | BBL, BBM, BBU, BBB, BBP, BBD, BBT |
| BB(40, 2.0) | 5m | BBL, BBM, BBU, BBP |

### 2.4 Diger Indikatorler
| Indikator | Periyot | Timeframe | Aciklama |
|-----------|---------|-----------|----------|
| Williams %R | 14 | 5m, 15m, 1h, 4h, 1d | Asiri alis/satis |
| Williams %R | 84 | 1h | Uzun vadeli W%R |
| Williams %R | 480 | 5m | Cok uzun vadeli W%R |
| MFI | 14 | 5m, 15m, 1h, 4h, 1d | Para akis endeksi |
| CMF | 20 | 5m, 15m, 1h, 4h, 1d | Chaikin para akisi |
| CCI | 20 | 5m, 15m, 1h, 4h | Emtia kanal endeksi |
| AROON | 14 | 5m, 15m, 1h, 4h, 1d | Trend gucu (Up/Down) |
| Stochastic | 14,3,3 | 5m, 15m, 1h, 4h, 1d | Stokastik osilator |
| StochRSI | 14,14,3,3 | 5m, 15m, 1h, 4h, 1d | Stokastik RSI |
| KST | 10,15,20,30 | 5m, 1h, 4h | Know Sure Thing |
| UO | 7,14,28 | 5m, 15m, 1h, 4h | Ultimate Oscillator |
| ROC | 2, 9 | 5m, 15m, 1h, 4h, 1d | Degisim orani |
| OBV | - | 5m, 15m, 1h, 4h | Dengeli hacim |

### 2.5 Ozel Hesaplamalar
```
change_pct          = (close - open) / open * 100
close_max_6/12/48   = Rolling max close (6/12/48 mum)
close_min_6/12/48   = Rolling min close
high_max_6/12/24    = Rolling max high
low_min_6/12/24     = Rolling min low
top_wick_pct        = Ust fitil yuzdesi
bot_wick_pct        = Alt fitil yuzdesi
num_empty_288       = 288 mumda bos mum sayisi (hacim <= 0)
live_data_ok        = 72 mumda canli veri kontrolu
OBV_change_pct      = OBV degisim yuzdesi
CCI_20_change_pct   = CCI degisim yuzdesi
```

### 2.6 BTC Informative Verisi
- BTC ciftinin OHLCV verisi 5 timeframe'de cekilir
- Tum sutunlar "btc_" on ekiyle birlestirilir
- Genel piyasa yonu ve duyarlilik analizi icin kullanilir
- Stake para birimine gore otomatik cift tespiti (USDT, EUR, TRY, vb.)

---

## 3. GIRIS SINYALLERI MIMARISI

### 3.1 Giris Modlari (10 Mod)

#### LONG MODLARI:
| Mod | Tag'ler | Aciklama | Karmasiklik |
|-----|---------|----------|-------------|
| Normal | 1-13 | Standart giris, en cok kosul | ~250-400 satir/kosul |
| Pump | 21-26 | Momentum yukselisleri | ~150 satir |
| Quick | 41-53 | Hizli giris sinyalleri | ~200 satir |
| Rebuy | 61-63 | Mevcut pozisyona ek alis | Sistem V3 destekli |
| High Profit | 81-82 | Yuksek kar potansiyeli | Ozel kosullar |
| Rapid | 101-110 | Cok hizli girisler | ~300 satir |
| Grind | 120 | Mikro-olceklendirme | ~25-30 satir |
| BTC | 121 | Sadece Bitcoin | Varsayilan devre disi |
| Top Coins | 141-145 | Buyuk altcoinler (60 coin) | Ozel coin listesi |
| Scalp | 161-163 | Ultra kisa vadeli | Siki stop-loss |

#### SHORT MODLARI:
| Mod | Tag'ler |
|-----|---------|
| Normal | 501-502 |
| Pump | 521-526 |
| Quick | 541-550 |
| Rebuy | 561 |
| High Profit | 581-582 |
| Rapid | 601-610 |
| Grind | 620 |
| Top Coins | 641-642 |
| Scalp | 661 |

### 3.2 Giris Kosulu Yapisi (3 Katmanli)

```
KATMAN 1: Koruma Listesi (AND mantigi)
  |- num_empty_288 <= izin_verilen_bos_mum
  |- protections_long_global == True
  |- global_protections_long_pump == True

KATMAN 2: Ana Sinyal Kosullari (AND mantigi icinde OR gruplari)
  |- (KosulA1 | KosulA2 | KosulA3)    <-- OR grubu 1
  &  (KosulB1 | KosulB2)              <-- OR grubu 2
  &  (KosulC1 | KosulC2 | KosulC3)    <-- OR grubu 3
  ... (100-400+ satir karmasik boolean ifadeler)

KATMAN 3: Hacim Filtresi
  |- volume > 0

BIRLESIM:
  - Tek kosul icinde: Tum katmanlar AND ile birlesir
  - Kosullar arasi: Tum kosullar OR ile birlesir (herhangi biri tetiklenebilir)
```

### 3.3 Global Koruma Sistemi

**protections_long_global** (30+ alt kosul):
- RSI_3 asiri volatilite kontrolu
- RSI_14 asiri alis/satis esikleri (30-50 arasi)
- CCI asiri kosullar (< -250 @ 1h, < -200 @ 4h)
- StochRSI ust/alt sinirlar
- AROON trend gucu kontrolleri
- ROC momentum esikleri

**global_protections_long_pump** - Pump tuzagi engelleme
**global_protections_long_dump** - Dump tuzagi engelleme

### 3.4 Mod-Ozel Filtreler

```
Grind Mode:
  - grind_mode_max_slots = 1 (esanli max 1 grind pozisyonu)
  - grind_mode_coins = 54 coin listesi
  - Stake carpani: spot 0.20-0.70x, futures 0.20-0.50x

Rebuy Mode:
  - rebuy_mode_min_free_slots = 2 (en az 2 bos slot gerekli)
  - system_v3_rebuy_mode_stake_multiplier = 0.25x

Scalp Mode:
  - min_free_slots_scalp_mode = 1
  - Derisk: -0.05 (cok siki)

Top Coins Mode:
  - 60 buyuk marketcap coin listesi (BTC, ETH, SOL, vb.)

BTC Mode:
  - Sadece BTC (varsayilan devre disi)
```

### 3.5 Coklu Zaman Dilimi Onay Hierarsisi

```
5m  (Baz)  -> Giris tetikleyici (RSI_3, EMA, BB)
15m        -> 5m onay, trend hizalama
1h         -> Orta vade trend dogrulama
4h         -> Gunluk trend onay, makro baglam
1d         -> Uzun vade trend filtresi
```

Tipik oruntu: 5m'de dip + 15m'de destek + 1h'de asiri satilmamis + 4h trend destegi

---

## 4. CIKIS SINYALLERI MIMARISI

### 4.1 Temel Ilke
- `populate_exit_trend()` BOS (exit_long = 0, exit_short = 0)
- TUM cikislar `custom_exit()` uzerinden yonetilir
- Giris tag'ine gore mod-ozel cikis fonksiyonuna yonlendirilir

### 4.2 Cikis Hiyerarsisi (Her Mod Icin)

```
1. KAR KONTROLLERI (profit_init_ratio > 0.0 ise)
   |-- long_exit_signals()     -> Asiri alis kosullari (RSI > 84-88)
   |-- long_exit_main()        -> Kar seviyesine gore RSI cikislari
   |-- long_exit_williams_r()  -> Williams %R bazli karmasik cikislar
   |-- long_exit_dec()         -> Dusus trendi cikislari

2. STOPLOSS KONTROLLERI (her zaman)
   |-- long_exit_stoploss()    -> Zarar bazli acil cikislar

3. KAR HEDEFI YONETIMI
   |-- exit_profit_target()    -> Dinamik kar hedefi takip sistemi
```

### 4.3 Kar Seviyesine Gore Cikis Esikleri

#### EMA_200 Ustunde (Yukselis Boglami):
| Kar Araligi | Cikis RSI Esigi |
|-------------|-----------------|
| %0.1 - %1.0 | RSI < 10 |
| %1.0 - %2.0 | RSI < 28 |
| %2.0 - %3.0 | RSI < 30 |
| %3.0 - %4.0 | RSI < 32 |
| %4.0 - %5.0 | RSI < 34 |
| %5.0 - %6.0 | RSI < 36 |
| %6.0 - %7.0 | RSI < 38 |
| %7.0 - %8.0 | RSI < 40 |
| %8.0 - %9.0 | RSI < 42 |
| %9.0 - %10.0 | RSI < 44 |
| %10.0 - %12.0 | RSI < 46 |
| %12.0 - %20.0 | RSI < 44 |
| > %20.0 | RSI < 42 |

#### EMA_200 Altinda (Dusus Baglami):
- Benzer katmanlar ama DAHA YUKSEK RSI esikleri (daha muhafazakar)

### 4.4 Williams %R Cikis Sistemi
- Her kar katmani icin 8-15 karmasik kosul
- Kullanan indikatorler: WILLR_14, WILLR_480, RSI_3, RSI_14, ROC, CMF, StochRSI, AROON
- Coklu zaman dilimi kontrolu (5m, 1h, 4h, 1d)

### 4.5 Stoploss Mantigi (3 Tip)

#### A. Doom Stop (Felaket Durdurma):
```
System V3_2: spot %12 / futures %35
System V3_1: spot %24 / futures %70
System V3:   spot %14 / futures %35
Varsayilan:  spot %20 / futures %20
```
- Gecerlilik tarih filtresi var (13 Eylul 2024 sonrasi)
- `has_valid_entry_conditions()` kontrolu

#### B. U_E Stop (EMA Alti Durma):
- Varsayilan DEVRE DISI
- Kosullar: Zarar > esik VE Close < EMA_200 VE CMF_20 < 0 VE RSI kosullari

#### C. Doom Kurtarma:
- Stoploss tetiklendikten sonra kar toparlanirsa iptal edilebilir
- 60 dakikalik toparlanma penceresi

### 4.6 Kar Hedefi Onbellekleme
- `target_profit_cache`: Ulasilan kar hedeflerini depolar
- Fiyat iyilesirse pozisyonu tutar (kar maksimizasyonu)
- 60 dakika icerisinde hedef guncellemesi

### 4.7 confirm_trade_exit()
- `_should_hold_trade()` ile hold listesi kontrolu
- Force exit'ler her zaman gecerli
- Stop loss ve trailing stop cikislarini iptal edebilir

---

## 5. POZISYON YONETIMI

### 5.1 Grinding Sistemi (6 Seviye DCA)

Her seviye bagimsiz yapilandirilir:

| Seviye | Stake'ler (spot) | Esikler | Kar Hedefi |
|--------|-----------------|---------|------------|
| Grind_1 | [0.24, 0.26, 0.28] | [-0.12, -0.16, -0.20] | %1.8 |
| Grind_2 | [0.20, 0.24, 0.28] | [-0.12, -0.16, -0.20] | %1.8 |
| Grind_3 | [0.20, 0.22, 0.24] | [-0.12, -0.16, -0.20] | %1.8 |
| Grind_4 | [0.20, 0.22, 0.24] | [-0.12, -0.16, -0.20] | %1.8 |
| Grind_5 | [0.20, 0.22, 0.24] | [-0.12, -0.16, -0.20] | %4.8 |
| Grind_6 | [0.10-0.18 x9] | [-0.03 ile -0.22] | %1.8 |

**Nasil Calisir:**
1. Ilk giris maliyeti baz alinir
2. Fiyat esik degerine dustugunde ek alis yapilir
3. Her seviyede max 3-9 alis olabilir
4. Kar hedefine ulasilinca grind seviyesi kapatilir

### 5.2 Derisk Sistemi (3 Seviye Risk Azaltma)

#### Grinding V2 Derisk:
| Seviye | Spot Esikleri | Futures Esikleri | Stake |
|--------|---------------|------------------|-------|
| Level 1 | [-0.06, -0.15] | [-0.18, -0.35] | %20 |
| Level 2 | [-0.08, -0.18] | [-0.16, -0.54] | %30 |
| Level 3 | [-0.10, -0.20] | [-0.30, -0.60] | %50 |

#### System V3 Derisk:
| Seviye | Spot | Futures | Stake |
|--------|------|---------|-------|
| Level 1 | [-0.04, -0.06] | [-0.12, -0.18] | %10 |
| Level 2 | [-0.06, -0.08] | [-0.18, -0.24] | %10 |
| Level 3 | [-0.08, -0.10] | [-0.24, -0.30] | %10 |

**Nasil Calisir:**
1. Pozisyon zarardayken belirli esiklerde kismi satis yapilir
2. Pozisyon boyutu kuculur, ortalama maliyet duser
3. Level 3'te grinding moduna gecis yapilabilir

### 5.3 Rebuy Sistemi

```
rebuy_mode_stake_multiplier = 0.35
rebuy_mode_stakes = [1.0, 1.0] (2 ek alis)
rebuy_mode_thresholds = [-0.08, -0.10]

System V3:
  stake_multiplier = 0.25
  stakes = [1.0, 1.0, 1.0, 1.0] (4 ek alis)
  thresholds = [-0.08, -0.12, -0.16, -0.20]
```

### 5.4 Buyback Sistemi (3 Seviye)

```
Buyback_1: Hafif yeniden giris (mesafe: -0.06)
Buyback_2: Orta yogunluk (mesafe: -0.12)
Buyback_3: Agresif (mesafe: -0.16)
```
- Teknik kosullarla onaylanmis yeniden giris
- RSI, AROON, ROC, EMA kontrolleri

### 5.5 Stake Miktari Yonetimi (custom_stake_amount)

| Mod | Spot Carpani | Futures Carpani |
|-----|-------------|-----------------|
| Normal | [1.0] | [1.0] |
| Rebuy | 0.25x | 0.25x |
| Rapid | [0.75] | [0.75] |
| Grind | [0.20-0.70] | [0.20-0.50] |
| BTC | 0.20x | 0.20x |
| System V3_1 | 0.50x | 0.50x |
| System V3_2 | 1.0x | 1.0x |

### 5.6 Kaldirac Yonetimi (Futures)

```
Regular: futures_mode_leverage = 3.0
Rebuy:   futures_mode_leverage_rebuy_mode = 3.0
Grind:   futures_mode_leverage_grind_mode = 3.0
```

---

## 6. OZEL OZELLIKLER

### 6.1 Hold Trades (Islem Tutma)
- `nfi-hold-trades.json` dosyasindan yapilandirilir
- Belirli islem ID'si veya coin cifti icin kar hedefi belirlenebilir
- `bot_loop_start()` her dongude dosyayi yeniden yukler
- `confirm_trade_exit()` cikis oncesi kontrol eder

### 6.2 Sistem Versiyonlama (V3, V3.1, V3.2)
- Her versiyon farkli stop esikleri ve stake carpanlari
- `order_filled()` ile ilk giriste sistem versiyonu kaydedilir
- Trade custom data uzerinden takip

### 6.3 Coin Listeleri
```
grind_mode_coins:     54 coin (AAVE, ADA, BTC, ETH, SOL...)
top_coins_mode_coins: 60 coin (buyuk marketcap)
btc_mode_coins:       1 coin (sadece BTC)
```

### 6.4 Giris Tag Sistemi
- Boslukla ayrilmis tag'ler: "1", "21", "101 61"
- Birden fazla mod ayni anda tetiklenebilir
- Cikis mantigi tag'e gore yonlendirilir
- Sonradan analiz icin hangi sinyalin tetiklendigini takip eder

### 6.5 Cache Sistemi
- `Cache` sinifi: JSON bazli dosya onbellegi (RapidJSON)
- `HoldsCache` sinifi: Salt okunur hold trades onbellegi
- Kar hedefleri icin cache kullanimi

### 6.6 Koruma Mekanizmalari
- Bos mum kontrolu (num_empty_288)
- Canli veri dogrulama (live_data_ok)
- Backtest yas filtresi (bt_agefilter_ok)
- Kayma (slippage) kontrolu (%0.5-1)
- Futures islem limitleri

---

## 7. METOT KATALOGU (Tam Liste)

### Freqtrade Override Metotlari:
- `version()` - Strateji versiyonu
- `populate_indicators()` - Indikator hesaplama
- `populate_entry_trend()` - Giris sinyali uretimi
- `populate_exit_trend()` - Cikis sinyali (bos)
- `custom_exit()` - Ozel cikis mantigi
- `custom_stake_amount()` - Dinamik stake hesaplama
- `adjust_trade_position()` - Pozisyon ayarlama (DCA/Grind)
- `confirm_trade_entry()` - Giris onaylama
- `confirm_trade_exit()` - Cikis onaylama
- `leverage()` - Kaldirac belirleme
- `bot_loop_start()` - Bot dongu baslangici
- `informative_pairs()` - Bilgi ciftleri
- `order_filled()` - Emir dolum islemi

### Indikator Hesaplama Metotlari (12):
- `informative_1d/4h/1h/15m_indicators()` - Timeframe bazli
- `base_tf_5m_indicators()` - 5m baz indikatorler
- `info_switcher()` / `btc_info_switcher()` - Yonlendirici
- `btc_info_1d/4h/1h/15m/5m_indicators()` - BTC ozel

### Cikis Metotlari (29):
- Long: `long_exit_normal/pump/quick/rebuy/high_profit/rapid/grind/btc/top_coins/scalp()`
- Long alt: `long_exit_signals/main/williams_r/dec/stoploss()`
- Short: Ayni yapilar `short_` on ekiyle

### Pozisyon Yonetimi Metotlari (24):
- `long_grind_adjust_trade_position_v2/v3()`
- `long_rebuy_adjust_trade_position(_v3)()`
- `long_adjust_trade_position_no_derisk()`
- `long_grind_entry_v2/v3()`
- `long_buyback_entry_v2/v3()`
- `long_buyback_exit_v2()`
- Short versiyonlari

### Yardimci Metotlar:
- `calc_total_profit()` - Toplam kar hesabi
- `mark_profit_target()` / `exit_profit_target()` - Kar hedefi yonetimi
- `_should_hold_trade()` - Hold kontrolu
- `has_valid_entry_conditions()` - Giris kosul dogrulama
- `correct_min_stake()` - Min stake duzeltme
- `is_backtest_mode()` - Mod kontrolu
- `is_system_v3/v3_1/v3_2()` - Sistem versiyon kontrolu

---

## 8. YENI STRATEJI ICIN KONTROL LISTESI

Yeni bir guclu strateji yazarken su bilesenlerin OLMASI GEREKIR:

### ZORUNLU BILESENLER:

- [ ] **Coklu Zaman Dilimi Analizi** - En az 3 timeframe (5m + 1h + 4h veya 1d)
- [ ] **Global Koruma Sistemi** - Asiri piyasa kosullarinda giris engelleme
- [ ] **Coklu Indikator Onay** - RSI + Trend (EMA) + Momentum (ROC/MACD) + Hacim (CMF/MFI)
- [ ] **Sinyal Bazli Cikis** - ROI yerine custom_exit ile akilli cikis
- [ ] **Kar Seviyesine Gore Adaptif Cikis** - Farkli kar katmanlarinda farkli kosullar
- [ ] **Grinding/DCA Sistemi** - Kayiptaki pozisyonlara kontrollü ek alis
- [ ] **Derisk Sistemi** - Buyuk zararlarda kismi satis ile risk azaltma
- [ ] **Stoploss Katmanlari** - Doom stop + normal stop + kosullu stop
- [ ] **Spot/Futures Ayirimi** - Her mod icin ayri parametreler
- [ ] **Giris Tag Sistemi** - Hangi sinyalin tetiklendigini takip
- [ ] **Hacim ve Veri Kalitesi Kontrolu** - Bos mum, canli veri dogrulama

### ONERILMEYEN AMA GUCLU BILESENLER:

- [ ] **Coklu Giris Modu** - Normal, quick, pump, scalp vb.
- [ ] **BTC Informative** - Genel piyasa yonu icin BTC verisi
- [ ] **Top Coins Ozel Modu** - Buyuk coinler icin farkli parametreler
- [ ] **Buyback Sistemi** - Karli cikilmis pozisyonlara yeniden giris
- [ ] **Hold Trades** - Manuel mudahale imkani
- [ ] **Sistem Versiyonlama** - Farkli parametre setleri arasi gecis
- [ ] **Kar Hedefi Onbellekleme** - Profit target trailing
- [ ] **Kaldirac Yonetimi** - Mod bazli dinamik kaldirac

### KRITIK TASARIM PRENSIPLERI:

1. **Izin Verici Koruma + Kisitlayici Sinyal**: Korumalar genel, giris kosullari spesifik
2. **Indikator Yedekliligi**: Ayni sinyal 4+ farkli indikatorle dogrulanir
3. **Kademeli Risk Yonetimi**: Zarar buyudukce derisk -> grind -> doom stop
4. **Asimetrik Cikis**: Yukseliste sabir, dususte hiz
5. **Mod Bazli Izolasyon**: Her mod kendi risk/odul parametrelerine sahip
6. **800 Baslangic Mumu**: Uzun periyot indikatorleri icin yeterli veri

---

## 9. INDIKATOR ONCELIK SIRASI (Onem Derecesine Gore)

### Tier 1 - VAZGECILMEZ:
1. **RSI (3, 14)** - Hem giris hem cikis icin en cok kullanilan
2. **EMA (12, 26, 200)** - Trend yonu ve destek/direnc
3. **Bollinger Bands (20, 2.0)** - Volatilite ve fiyat konumu

### Tier 2 - COK ONEMLI:
4. **Williams %R (14, 480)** - Cikis sinyallerinde agirlikli kullanim
5. **CMF (20)** - Para akisi yonu
6. **StochRSI (14,14,3,3)** - Momentum onay
7. **AROON (14)** - Trend gucu

### Tier 3 - DESTEKLEYICI:
8. **ROC (2, 9)** - Momentum hizi
9. **CCI (20)** - Asiri kosul tespiti
10. **MFI (14)** - Hacim bazli momentum
11. **KST** - Uzun vade trend
12. **UO (7,14,28)** - Coklu periyot momentum
13. **OBV** - Hacim trendi

### Tier 4 - OZEL DURUMLAR:
14. **SMA (200)** - Uzun vade trend filtresi
15. **Stochastic (14,3,3)** - Ek momentum
16. **BB (40, 2.0)** - Genis volatilite

---

## 10. ORNEK GIRIS KOSUL YAPISI

Basitletirilmis bir Normal Mod giris kosulu ornegi:

```python
# Kosul 1: Dip Alis
long_entry_logic = []

# Korumalar (AND)
long_entry_logic.append(reduce(lambda x, y: x & y, protection_list))
long_entry_logic.append(df["num_empty_288"] <= 60)
long_entry_logic.append(df["protections_long_global"] == True)

# Ana Sinyal (karmasik AND/OR kombinasyonu)
long_entry_logic.append(
    (df["RSI_3"] > 6.0)                           # 5m RSI cok dusuk degil
    & (df["RSI_3_15m"] > 6.0)                      # 15m RSI cok dusuk degil
    & (df["RSI_14"] < 36.0)                         # 5m asiri satilmis
    & (df["close"] < df["BBL_20_2.0"])              # BB alt bandinin altinda
    & (df["close"] < df["EMA_26"] * 0.94)           # EMA_26'nin %6 altinda
    & (
        (df["RSI_3_1h"] > 16.0)                     # 1h momentum ok
        | (df["STOCHRSIk_14_14_3_3_1h"] < 15.0)    # VEYA 1h StochRSI dusuk
    )
    & (
        (df["RSI_3_4h"] > 16.0)                     # 4h momentum ok
        | (df["ROC_9_4h"] > -20.0)                  # VEYA 4h ROC makul
    )
    & (df["AROONU_14_4h"] < 75.0)                   # 4h asiri yukselis degil
    & (df["close"] > df["EMA_200"] * 0.80)          # EMA_200'den cok uzak degil
)

# Hacim filtresi
long_entry_logic.append(df["volume"] > 0)

# Birlesim
item_long_entry = reduce(lambda x, y: x & y, long_entry_logic)
```

---

Bu rapor, NostalgiaForInfinityX7 stratejisinin tum guclu yonlerini ve
yeni strateji yazarken referans alinmasi gereken tum bilesenleri kapsar.

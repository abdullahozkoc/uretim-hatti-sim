"""Halı dokuma salonu: tezgâhlar, operatörler, teknisyen ve çözgü ekibi (SimPy).

Akış
----
Her tezgâh sırayla halı topu dokur. Dokuma sırasında dört olay yarışır:
atkı kopuşu, çözgü kopuşu, mekanik arıza ve bobin/iplik besleme ihtiyacı
(üçü tezgâhı durdurur, besleme durdurmaz). Top bitince operatör topu indirir;
sıradaki sipariş başka kaliteyse operatör ürün değişimi/ayar yapar. Çözgü
bitince çözgü ekibi çözgü levendini değiştirir. Arızayı teknisyen onarır.

Durduran bir işi bekleyen tezgâh "operatör bekleme" durumundadır: bu süre
iş etüdündeki makine girişimi (machine interference) kaybıdır.

Operatör, sorumlu olduğu tezgâhların iş listesinden seçim kuralına göre
(fifo | en_yakin | oncelikli) iş alır, tezgâha yürür ve işi yapar. İş yoksa
gözetimdedir. Molayı ve kişisel ihtiyacı iş aralarında kullanır. Mola düzeni:
  toplu    : herkes aynı anda; molada tezgâhlarına kimse bakmaz
  kademeli : komşu iki operatör sırayla molaya çıkar, biri diğerine bakar
  yedek    : operatörler sırayla çıkar, bir yedek (yüzer) operatör bakar
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import simpy

from src.hali.parametre import Dagilim, HaliParam

TEZGAH_DURUMLARI = ("dokuma", "operator_bekleme", "atki_kopusu", "cozgu_kopusu",
                    "top_indirme", "ayar", "cozgu_degisimi", "ariza")
OPERATOR_DURUMLARI = ("atki_kopusu", "cozgu_kopusu", "top_indirme", "ayar", "besleme",
                      "yurume", "gozetim", "mola", "kisisel")
ETIKET = {
    "dokuma": "Dokuma", "operator_bekleme": "Operatör bekleme (girişim)",
    "atki_kopusu": "Atkı kopuşu müdahalesi", "cozgu_kopusu": "Çözgü kopuşu müdahalesi",
    "top_indirme": "Top indirme", "ayar": "Ürün değişimi / ayar", "cozgu_degisimi": "Çözgü değişimi",
    "ariza": "Arıza (bekleme + onarım)", "besleme": "İplik / bobin besleme", "yurume": "Yürüme",
    "gozetim": "Gözetim / boş", "mola": "Mola", "kisisel": "Kişisel ihtiyaç",
}
# İş etüdü sınıflaması (operatör)
OPERATOR_SINIF = {
    "atki_kopusu": "Verimli iş", "cozgu_kopusu": "Verimli iş", "top_indirme": "Verimli iş",
    "ayar": "Verimli iş", "besleme": "Verimli iş", "yurume": "Yardımcı iş (yürüme)",
    "gozetim": "Boş / gözetim", "mola": "Mola ve kişisel", "kisisel": "Mola ve kişisel",
}
DURDURAN_ISLER = ("atki_kopusu", "cozgu_kopusu", "top_indirme", "ayar")


class Kaydedici:
    """Durumda geçen süreyi ve (ısınma sonrası) zaman çizelgesini tutar."""

    def __init__(self, env, isinma, durumlar, ilk, ad, cizelge: list):
        self.env, self.isinma, self.ad, self.cizelge = env, isinma, ad, cizelge
        self.sure = {d: 0.0 for d in durumlar}
        self.simdiki = ilk
        self.son_t = 0.0

    def _kapat(self) -> None:
        t = self.env.now
        bas = max(self.son_t, self.isinma)
        if t > bas:
            self.sure[self.simdiki] += t - bas
            self.cizelge.append((self.ad, bas, t, self.simdiki))
        self.son_t = t

    def durum(self, yeni: str) -> None:
        if yeni != self.simdiki:
            self._kapat()
            self.simdiki = yeni

    def oranlar(self) -> dict:
        self._kapat()
        top = sum(self.sure.values())
        return {d: (v / top if top else 0.0) for d, v in self.sure.items()}


@dataclass(eq=False)
class Is:
    tezgah: "_Tezgah"
    tur: str
    talep_t: float
    sure: float
    durdurur: bool
    basladi: simpy.Event
    bitti: simpy.Event
    operator: str | None = None
    baslama_t: float = math.nan


def _akis(seed: int, tur: int, i: int) -> np.random.Generator:
    """Ortak rastgele sayılar: her tezgâh/operatör ve amaç için ayrı akış."""
    return np.random.default_rng([seed, tur, i])


class _Tezgah:
    def __init__(self, salon: "_Salon", i: int):
        self.s, self.i, self.konum = salon, i, float(i)
        p, env = salon.p, salon.env
        self.ad = f"T{i + 1:02d}"
        self.kayit = Kaydedici(env, p.isinma_dk, TEZGAH_DURUMLARI, "dokuma", self.ad, salon.cizelge)
        self.r_kopus, self.r_sure = _akis(salon.seed, 1, i), _akis(salon.seed, 2, i)
        self.r_siparis, self.r_ariza = _akis(salon.seed, 3, i), _akis(salon.seed, 4, i)
        self.r_besleme = _akis(salon.seed, 5, i)
        self.urun = self._urun_sec()
        self.kalan_top = self.r_siparis.uniform(0.05, 1) * self.urun.top_uzunlugu.ornek(self.r_siparis)
        self.kalan_cozgu = self.r_siparis.uniform(0.05, 1) * p.cozgu_uzunlugu_m
        self.ariza_kalan = self._ariza_araligi()
        self.besleme_kalan = p.besleme_aralik.ornek(self.r_besleme)
        self.m2 = 0.0
        self.top_sayisi = 0
        self.kopus_sayisi = 0
        self.ariza_sayisi = 0
        self.cozgu_sayisi = 0
        self.dokuma_dk = 0.0
        self._aktif = None
        env.process(self.calis())

    def _urun_sec(self):
        u = self.s.p.urunler
        pay = np.array([x.oran for x in u], float)
        return u[self.r_siparis.choice(len(u), p=pay / pay.sum())]

    def _ariza_araligi(self) -> float:
        m = self.s.p.ariza_mtbf_saat
        return self.r_ariza.exponential(m * 60) if m and m > 0 else math.inf

    def _olcumde(self) -> bool:
        return self.s.env.now >= self.s.p.isinma_dk

    def _uretim_yaz(self, t0: float, t1: float, m2_dk: float) -> None:
        """[t0, t1] dokuma aralığının ölçüm penceresindeki kısmını üretime ekler."""
        sure = t1 - max(t0, self.s.p.isinma_dk)
        if sure > 0:
            self.m2 += sure * m2_dk
            self.dokuma_dk += sure

    def kapat(self) -> None:
        """Koşu sonunda süren dokumanın üretimini sayar."""
        if self._aktif is not None:
            t0, m2_dk = self._aktif
            self._uretim_yaz(t0, self.s.env.now, m2_dk)
            self._aktif = None

    def operatore_is(self, tur: str, dag: Dagilim):
        env = self.s.env
        is_ = Is(self, tur, env.now, dag.ornek(self.r_sure), True, env.event(), env.event())
        self.kayit.durum("operator_bekleme")
        self.s.talep_ekle(is_)
        yield is_.basladi
        self.kayit.durum(tur)
        yield is_.bitti

    def calis(self):
        s, p, env = self.s, self.s.p, self.s.env
        while True:
            if self.kalan_top <= 1e-9:
                yield from self.operatore_is("top_indirme", p.top_indirme)
                self.top_sayisi += self._olcumde()
                yeni = self._urun_sec()
                if yeni is not self.urun:
                    self.urun = yeni
                    yield from self.operatore_is("ayar", p.ayar)
                self.kalan_top = self.urun.top_uzunlugu.ornek(self.r_siparis)
            if self.kalan_cozgu <= 1e-9:
                self.kayit.durum("cozgu_degisimi")
                with s.ekip.request() as r:
                    yield r
                    yield env.timeout(p.cozgu_degisim.ornek(self.r_sure))
                self.kalan_cozgu = p.cozgu_uzunlugu_m
                self.cozgu_sayisi += self._olcumde()

            u = self.urun
            hiz = p.devir / u.atki_sikligi                       # m / dk
            ka = p.atki_kopus_saat * u.kopus_carpani / 60
            kc = p.cozgu_kopus_saat * u.kopus_carpani / 60
            adaylar = {
                "top": self.kalan_top / hiz,
                "cozgu_bitti": self.kalan_cozgu / hiz,
                "atki_kopusu": self.r_kopus.exponential(1 / ka) if ka > 0 else math.inf,
                "cozgu_kopusu": self.r_kopus.exponential(1 / kc) if kc > 0 else math.inf,
                "ariza": self.ariza_kalan,
                "besleme": self.besleme_kalan,
            }
            olay = min(adaylar, key=adaylar.get)
            dt = adaylar[olay]
            self.kayit.durum("dokuma")
            t0 = env.now
            self._aktif = (t0, hiz * u.en_m * p.yuz_sayisi)
            yield env.timeout(dt)
            self._aktif = None
            self._uretim_yaz(t0, env.now, hiz * u.en_m * p.yuz_sayisi)
            self.kalan_top = max(0.0, self.kalan_top - dt * hiz) if olay != "top" else 0.0
            self.kalan_cozgu = max(0.0, self.kalan_cozgu - dt * hiz) if olay != "cozgu_bitti" else 0.0
            self.ariza_kalan -= dt
            self.besleme_kalan -= dt

            if olay == "besleme":
                is_ = Is(self, "besleme", env.now, p.besleme_sure.ornek(self.r_sure), False,
                         env.event(), env.event())
                s.talep_ekle(is_)
                self.besleme_kalan = p.besleme_aralik.ornek(self.r_besleme)
            elif olay in ("atki_kopusu", "cozgu_kopusu"):
                self.kopus_sayisi += self._olcumde()
                dag = p.atki_mudahale if olay == "atki_kopusu" else p.cozgu_mudahale
                yield from self.operatore_is(olay, dag)
            elif olay == "ariza":
                self.ariza_sayisi += self._olcumde()
                self.kayit.durum("ariza")
                with s.teknisyen.request() as r:
                    yield r
                    yield env.timeout(p.ariza_onarim.ornek(self.r_sure))
                self.ariza_kalan = self._ariza_araligi()


class _Operator:
    def __init__(self, salon: "_Salon", k: int, tezgahlar: list[int], yedek: bool = False):
        self.s, self.k, self.yedek = salon, k, yedek
        p, env = salon.p, salon.env
        self.ad = "Yedek" if yedek else f"O{k + 1}"
        self.tezgahlar = set(tezgahlar)
        self.konum = float(np.mean(tezgahlar)) if tezgahlar else (p.tezgah_sayisi - 1) / 2
        self.kayit = Kaydedici(env, p.isinma_dk, OPERATOR_DURUMLARI, "gozetim", self.ad, salon.cizelge)
        self.r = _akis(salon.seed, 10, k)
        self.mola_kuyrugu: list[float] = []
        self.kisisel_bekliyor = 0
        self.molada = False
        self.bosta = False
        self._uyari = env.event()
        self.is_sayisi = 0
        env.process(self.calis())
        if not yedek:
            env.process(self.mola_takvimi())
            env.process(self.kisisel_ihtiyac())

    def uyandir(self) -> None:
        if self.bosta and not self._uyari.triggered:
            self._uyari.succeed()

    def sorumlu(self) -> set[int]:
        kume = set(self.tezgahlar)
        for o in self.s.operatorler:
            if o is not self and o.molada and self.s.kapsayan(o) is self:
                kume |= o.tezgahlar
        return kume

    def mola_ofseti(self, sure: float) -> float:
        d = self.s.p.mola_duzeni
        if d == "kademeli":
            return sure if self.k % 2 else 0.0
        if d == "yedek":
            return self.k * sure
        return 0.0

    def mola_takvimi(self):
        p, env = self.s.p, self.s.env
        vardiya = 0
        while True:
            bas = vardiya * p.vardiya_dk
            for t, sure in p.molalar:
                hedef = bas + t + self.mola_ofseti(sure)
                if hedef > env.now:
                    yield env.timeout(hedef - env.now)
                self.mola_kuyrugu.append(sure)
                self.uyandir()
            vardiya += 1
            sonraki = vardiya * p.vardiya_dk
            if sonraki > env.now:
                yield env.timeout(sonraki - env.now)

    def kisisel_ihtiyac(self):
        p, env = self.s.p, self.s.env
        while True:
            yield env.timeout(p.kisisel_aralik.ornek(self.r))
            self.kisisel_bekliyor += 1
            self.uyandir()

    def calis(self):
        s, p, env = self.s, self.s.p, self.s.env
        while True:
            if self.mola_kuyrugu:
                sure = self.mola_kuyrugu.pop(0)
                self.molada = True
                self.kayit.durum("mola")
                k = s.kapsayan(self)
                if k is not None:
                    k.uyandir()
                yield env.timeout(sure)
                self.molada = False
                continue
            if self.kisisel_bekliyor:
                self.kisisel_bekliyor -= 1
                self.kayit.durum("kisisel")
                yield env.timeout(p.kisisel_sure.ornek(self.r))
                continue
            is_ = s.is_sec(self)
            if is_ is None:
                self.kayit.durum("gozetim")
                self.bosta = True
                self._uyari = env.event()
                yield self._uyari
                self.bosta = False
                continue
            s.talepler.remove(is_)
            mesafe = abs(self.konum - is_.tezgah.konum)
            if mesafe > 0:
                self.kayit.durum("yurume")
                yield env.timeout(p.yurume_sabit + mesafe * p.yurume_tezgah_arasi)
                self.konum = is_.tezgah.konum
            is_.operator, is_.baslama_t = self.ad, env.now
            is_.basladi.succeed()
            self.kayit.durum(is_.tur)
            yield env.timeout(is_.sure)
            is_.bitti.succeed()
            if env.now >= p.isinma_dk:
                self.is_sayisi += 1
                s.isler.append((is_.tezgah.ad, is_.tur, is_.talep_t, is_.baslama_t, env.now, self.ad,
                                is_.durdurur))


class _Salon:
    def __init__(self, p: HaliParam, seed: int):
        if p.mola_duzeni not in ("toplu", "kademeli", "yedek"):
            raise ValueError("mola_duzeni: toplu | kademeli | yedek")
        if p.secim_kurali not in ("fifo", "en_yakin", "oncelikli"):
            raise ValueError("secim_kurali: fifo | en_yakin | oncelikli")
        self.p, self.seed = p, seed
        self.env = simpy.Environment()
        self.cizelge: list = []
        self.isler: list = []
        self.talepler: list[Is] = []
        self.teknisyen = simpy.Resource(self.env, p.teknisyen_sayisi)
        self.ekip = simpy.Resource(self.env, p.cozgu_ekibi)
        self.operatorler: list[_Operator] = []
        n, m = p.tezgah_sayisi, p.operator_basina_tezgah
        for k in range(p.operator_sayisi):
            self.operatorler.append(_Operator(self, k, list(range(k * m, min(n, (k + 1) * m)))))
        self.yedek = _Operator(self, p.operator_sayisi, [], yedek=True) if p.mola_duzeni == "yedek" else None
        if self.yedek:
            self.operatorler.append(self.yedek)
        self.tezgahlar = [_Tezgah(self, i) for i in range(n)]

    def kapsayan(self, o: _Operator) -> _Operator | None:
        d = self.p.mola_duzeni
        if d == "yedek":
            return self.yedek
        if d == "kademeli":
            duz = [x for x in self.operatorler if not x.yedek]
            k = o.k + 1 if o.k % 2 == 0 and o.k + 1 < len(duz) else o.k - 1
            return duz[k] if 0 <= k < len(duz) and k != o.k else None
        return None

    def talep_ekle(self, is_: Is) -> None:
        self.talepler.append(is_)
        for o in self.operatorler:
            if o.bosta and is_.tezgah.i in o.sorumlu():
                o.uyandir()

    def is_sec(self, o: _Operator) -> Is | None:
        kume = o.sorumlu()
        aday = [t for t in self.talepler if t.tezgah.i in kume]
        if not aday:
            return None
        kural = self.p.secim_kurali
        if kural == "en_yakin":
            return min(aday, key=lambda t: (abs(o.konum - t.tezgah.konum), t.talep_t))
        if kural == "oncelikli":     # tezgâhı durduran işler önce
            return min(aday, key=lambda t: (not t.durdurur, t.talep_t))
        return aday[0]


@dataclass
class HaliSonuc:
    ozet: dict
    tezgah: pd.DataFrame
    operator: pd.DataFrame
    cizelge: pd.DataFrame = field(repr=False)
    isler: pd.DataFrame = field(repr=False)


def kos(p: HaliParam, seed: int) -> HaliSonuc:
    s = _Salon(p, seed)
    s.env.run(until=p.bitis_dk)
    for t in s.tezgahlar:
        t.kapat()
    olcum_saat = p.sure_gun * 24

    tz = []
    for t in s.tezgahlar:
        r = t.kayit.oranlar()
        tz.append({"tezgah": t.ad, **r, "m2": t.m2, "top": t.top_sayisi, "kopus": t.kopus_sayisi,
                   "ariza_sayisi": t.ariza_sayisi, "cozgu_sayisi": t.cozgu_sayisi,
                   "operator": next(o.ad for o in s.operatorler if t.i in o.tezgahlar)})
    tz = pd.DataFrame(tz)
    op = []
    for o in s.operatorler:
        r = o.kayit.oranlar()
        is_payi = sum(r[d] for d in OPERATOR_DURUMLARI if OPERATOR_SINIF[d] == "Verimli iş")
        op.append({"operator": o.ad, **r, "verimli_is": is_payi,
                   "doluluk": is_payi + r["yurume"], "is_sayisi": o.is_sayisi,
                   "tezgah_sayisi": len(o.tezgahlar)})
    op = pd.DataFrame(op)
    isler = pd.DataFrame(s.isler, columns=["tezgah", "tur", "talep", "baslama", "bitis", "operator", "durdurur"])
    isler["bekleme"] = isler["baslama"] - isler["talep"]
    duz = op[op["operator"] != "Yedek"]

    toplam_m2 = float(tz["m2"].sum())
    dokuma_saat = sum(t.dokuma_dk for t in s.tezgahlar) / 60
    operator_n = len(op)
    durduran = isler[isler["durdurur"]]
    ozet = {
        "m2_gun": toplam_m2 / p.sure_gun,
        "m2_vardiya": toplam_m2 / (olcum_saat * 60 / p.vardiya_dk),
        "tezgah_verimi": float(tz["dokuma"].mean()),
        "girisim": float(tz["operator_bekleme"].mean()),
        "operator_doluluk": float(duz["doluluk"].mean()),
        "operator_verimli": float(duz["verimli_is"].mean()),
        "operator_gozetim": float(duz["gozetim"].mean()),
        "m2_operator_saat": toplam_m2 / (operator_n * olcum_saat),
        "ort_bekleme_dk": float(durduran["bekleme"].mean()) if len(durduran) else 0.0,
        "kopus_dokuma_saati": float(tz["kopus"].sum() / dokuma_saat) if dokuma_saat else 0.0,
        "top_gun": float(tz["top"].sum() / p.sure_gun),
        "operator_sayisi": operator_n,
    }
    for d in TEZGAH_DURUMLARI:
        ozet[f"tz:{d}"] = float(tz[d].mean())
    for d in OPERATOR_DURUMLARI:
        ozet[f"op:{d}"] = float(duz[d].mean())
    cizelge = pd.DataFrame(s.cizelge, columns=["kaynak", "bas", "bit", "durum"])
    return HaliSonuc(ozet, tz, op, cizelge, isler)

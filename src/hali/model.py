"""Halı dokuma salonu: tezgâhlar, halfeler, telciler, renk ekibi, teknisyen ve çözgü ekibi (SimPy).

Akış
----
Her tezgâh kendi kalitesinde (tarak, sıra sıklığı, en) sırayla halı topu dokur.
Devir değişkendir: her yeni topta tezgâhın devir dağılımından çekilir.
Dokuma sırasında dört olay yarışır: atkı kopuşu, çözgü/hav kopuşu, mekanik arıza
besleme ve halı kontrolü ihtiyacı (bu ikisi tezgâhı durdurmaz). Top bitince halfe topu indirir.
Sonraki top renk değişimi gerektiriyorsa bunu çoğunlukla renk ekibi, kalan durumda
halfe yapar; yalnızca desen değişiyorsa halfe kısa bir ayar yapar. Çözgü
bitince çözgü ekibi, arıza olunca teknisyen gelir.

Durduran bir işi bekleyen tezgâh "personel_bekleme" durumundadır: bu süre iş
etüdündeki makine girişimi (machine interference) kaybıdır.

Personel: her işin bir rolü vardır (halfe ya da telci, `is_rolleri`). Kişi,
sorumlu olduğu (tezgâh, rol) çiftlerindeki işlerden seçim kuralına göre iş alır,
yürür ve işi yapar; iş yoksa gözetimdedir. Mola ve kişisel ihtiyaç iş aralarında
kullanılır. Mola iki seçimle tanımlanır:
  mola_zamani  : toplu (herkes aynı anda çıkar) | ayri (dalgalar halinde ayrı ayrı)
  mola_kapsama : molada çıkanın işine kim bakar
                 yok    : kimse (tezgâh bekler)
                 komsu  : aynı roldeki komşu kişi
                 capraz : aynı tezgâhın halfesi/telcisi birbirine bakar
                 yedek  : yüzer yedek personel
Yorgunluk: iş süresi, son moladan bu yana geçen saatle doğrusal uzar
(yorgunluk_orani, tavan yorgunluk_tavan; molada sıfırlanır).
Öğrenme: deneyimsiz kişide iş süresi Wright eğrisiyle (n/standart)^log2(oran)
çarpanı alır; tekrar sayısı arttıkça 1'e iner.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import simpy

from src.hali.parametre import ROLLER, Dagilim, HaliParam

TEZGAH_DURUMLARI = ("dokuma", "personel_bekleme", "atki_kopusu", "cozgu_kopusu", "top_indirme",
                    "ayar", "renk_degisimi", "cozgu_degisimi", "ariza")
PERSONEL_DURUMLARI = ("atki_kopusu", "cozgu_kopusu", "top_indirme", "ayar", "renk_degisimi", "besleme",
                      "kontrol", "yurume", "gozetim", "mola", "kisisel")
OPERATOR_DURUMLARI = PERSONEL_DURUMLARI          # geriye dönük ad
ETIKET = {
    "dokuma": "Dokuma", "personel_bekleme": "Personel bekleme (girişim)",
    "atki_kopusu": "Atkı kopuşu müdahalesi", "cozgu_kopusu": "Çözgü/hav kopuşu müdahalesi",
    "top_indirme": "Top indirme", "ayar": "Desen ayarı", "renk_degisimi": "Renk değişimi",
    "cozgu_degisimi": "Çözgü değişimi", "ariza": "Arıza (bekleme + onarım)", "besleme": "İplik / bobin besleme",
    "kontrol": "Halı kontrolü / düzeltme",
    "yurume": "Yürüme", "gozetim": "Gözetim / boş", "mola": "Mola", "kisisel": "Kişisel ihtiyaç",
}
PERSONEL_SINIF = {
    "atki_kopusu": "Verimli iş", "cozgu_kopusu": "Verimli iş", "top_indirme": "Verimli iş",
    "ayar": "Verimli iş", "renk_degisimi": "Verimli iş", "besleme": "Verimli iş", "kontrol": "Verimli iş",
    "yurume": "Yardımcı iş (yürüme)", "gozetim": "Boş / gözetim", "mola": "Mola ve kişisel",
    "kisisel": "Mola ve kişisel",
}
OPERATOR_SINIF = PERSONEL_SINIF
ROL_ONEK = {"halfe": "hf", "telci": "tl", "yedek": "yd"}


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
    rol: str
    talep_t: float
    sure: float
    durdurur: bool
    basladi: simpy.Event
    bitti: simpy.Event
    personel: str | None = None
    baslama_t: float = math.nan


def _akis(seed: int, tur: int, i: int) -> np.random.Generator:
    """Ortak rastgele sayılar: her tezgâh/kişi ve amaç için ayrı akış."""
    return np.random.default_rng([seed, tur, i])


class _Tezgah:
    def __init__(self, salon: "_Salon", i: int):
        self.s, self.i, self.konum = salon, i, float(i)
        p, env = salon.p, salon.env
        self.tanim = p.tezgahlar[i]
        self.ad = self.tanim.ad
        self.kayit = Kaydedici(env, p.isinma_dk, TEZGAH_DURUMLARI, "dokuma", self.ad, salon.cizelge)
        self.r_kopus, self.r_sure = _akis(salon.seed, 1, i), _akis(salon.seed, 2, i)
        self.r_siparis, self.r_ariza = _akis(salon.seed, 3, i), _akis(salon.seed, 4, i)
        self.r_besleme, self.r_devir = _akis(salon.seed, 5, i), _akis(salon.seed, 6, i)
        self.devir = self.tanim.devir.ornek(self.r_devir)
        self.kalan_top = self.r_siparis.uniform(0.05, 1) * p.top_uzunlugu.ornek(self.r_siparis)
        self.kalan_cozgu = self.r_siparis.uniform(0.05, 1) * p.cozgu_uzunlugu_m
        self.ariza_kalan = self._ariza_araligi()
        self.besleme_kalan = p.besleme_aralik.ornek(self.r_besleme)
        self.r_kontrol = _akis(salon.seed, 7, i)
        self.kontrol_kalan = p.kontrol_aralik.ornek(self.r_kontrol)
        self.m2 = 0.0
        self.top_sayisi = self.kopus_sayisi = self.ariza_sayisi = self.cozgu_sayisi = 0
        self.renk_sayisi = self.desen_sayisi = 0
        self.dokuma_dk = 0.0
        self.devir_dk = 0.0                # devir × dokuma dk (ağırlıklı ortalama için)
        self.m2_vardiyalar: dict[int, float] = {}
        self._aktif = None
        env.process(self.calis())

    def _ariza_araligi(self) -> float:
        m = self.s.p.ariza_mtbf_saat
        return self.r_ariza.exponential(m * 60) if m and m > 0 else math.inf

    def _olcumde(self) -> bool:
        return self.s.env.now >= self.s.p.isinma_dk

    def _uretim_yaz(self, t0: float, t1: float, m2_dk: float, devir: float) -> None:
        p = self.s.p
        bas = max(t0, p.isinma_dk)
        sure = t1 - bas
        if sure > 0:
            self.m2 += sure * m2_dk
            self.dokuma_dk += sure
            self.devir_dk += sure * devir
            # vardiya bazında üretim (ölçüm başından itibaren vardiya no)
            t = bas
            while t < t1:
                v = int((t - p.isinma_dk) // p.vardiya_dk)
                son = min(t1, p.isinma_dk + (v + 1) * p.vardiya_dk)
                self.m2_vardiyalar[v] = self.m2_vardiyalar.get(v, 0.0) + (son - t) * m2_dk
                t = son

    def kapat(self) -> None:
        """Koşu sonunda süren dokumanın üretimini sayar."""
        if self._aktif is not None:
            self._uretim_yaz(*self._aktif[:1], self.s.env.now, *self._aktif[1:])
            self._aktif = None

    def personele_is(self, tur: str, dag: Dagilim):
        env = self.s.env
        is_ = Is(self, tur, self.s.p.rol(tur), env.now, dag.ornek(self.r_sure), True, env.event(), env.event())
        self.kayit.durum("personel_bekleme")
        self.s.talep_ekle(is_)
        yield is_.basladi
        self.kayit.durum(tur)
        yield is_.bitti

    def calis(self):
        s, p, env, tz = self.s, self.s.p, self.s.env, self.tanim
        while True:
            if self.kalan_top <= 1e-9:
                yield from self.personele_is("top_indirme", p.top_indirme)
                self.top_sayisi += self._olcumde()
                u_degisim, u_ekip = self.r_siparis.random(2)
                if u_degisim < p.renk_degisim_olasiligi:
                    self.renk_sayisi += self._olcumde()
                    if u_ekip < p.renk_ekip_payi:
                        self.kayit.durum("renk_degisimi")
                        with s.renk_ekibi.request() as r:
                            yield r
                            yield env.timeout(p.renk_degisim.ornek(self.r_sure))
                    else:
                        yield from self.personele_is("renk_degisimi", p.renk_degisim)
                elif u_degisim < p.renk_degisim_olasiligi + p.desen_degisim_olasiligi:
                    self.desen_sayisi += self._olcumde()
                    yield from self.personele_is("ayar", p.ayar)
                self.kalan_top = p.top_uzunlugu.ornek(self.r_siparis)
                self.devir = tz.devir.ornek(self.r_devir)
            if self.kalan_cozgu <= 1e-9:
                self.kayit.durum("cozgu_degisimi")
                with s.ekip.request() as r:
                    yield r
                    yield env.timeout(p.cozgu_degisim.ornek(self.r_sure))
                self.kalan_cozgu = p.cozgu_uzunlugu_m
                self.cozgu_sayisi += self._olcumde()

            hiz = tz.hiz_m_dk(self.devir, p.atki_sistemi)        # m / dk
            m2_dk = hiz * tz.en_m * p.yuz_sayisi
            ka = p.atki_kopus_saat * tz.kopus_carpani / 60
            kc = p.cozgu_kopus_saat * tz.kopus_carpani / 60
            adaylar = {
                "top": self.kalan_top / hiz,
                "cozgu_bitti": self.kalan_cozgu / hiz,
                "atki_kopusu": self.r_kopus.exponential(1 / ka) if ka > 0 else math.inf,
                "cozgu_kopusu": self.r_kopus.exponential(1 / kc) if kc > 0 else math.inf,
                "ariza": self.ariza_kalan,
                "besleme": self.besleme_kalan,
                "kontrol": self.kontrol_kalan,
            }
            olay = min(adaylar, key=adaylar.get)
            dt = adaylar[olay]
            self.kayit.durum("dokuma")
            t0 = env.now
            self._aktif = (t0, m2_dk, self.devir)
            yield env.timeout(dt)
            self._aktif = None
            self._uretim_yaz(t0, env.now, m2_dk, self.devir)
            self.kalan_top = max(0.0, self.kalan_top - dt * hiz) if olay != "top" else 0.0
            self.kalan_cozgu = max(0.0, self.kalan_cozgu - dt * hiz) if olay != "cozgu_bitti" else 0.0
            self.ariza_kalan -= dt
            self.besleme_kalan -= dt
            self.kontrol_kalan -= dt

            if olay in ("besleme", "kontrol"):           # tezgâhı durdurmayan işler
                sure_d = p.besleme_sure if olay == "besleme" else p.kontrol_sure
                is_ = Is(self, olay, p.rol(olay), env.now, sure_d.ornek(self.r_sure), False,
                         env.event(), env.event())
                s.talep_ekle(is_)
                if olay == "besleme":
                    self.besleme_kalan = p.besleme_aralik.ornek(self.r_besleme)
                else:
                    self.kontrol_kalan = p.kontrol_aralik.ornek(self.r_kontrol)
            elif olay in ("atki_kopusu", "cozgu_kopusu"):
                self.kopus_sayisi += self._olcumde()
                dag = p.atki_mudahale if olay == "atki_kopusu" else p.cozgu_mudahale
                yield from self.personele_is(olay, dag)
            elif olay == "ariza":
                self.ariza_sayisi += self._olcumde()
                self.kayit.durum("ariza")
                with s.teknisyen.request() as r:
                    yield r
                    yield env.timeout(p.ariza_onarim.ornek(self.r_sure))
                self.ariza_kalan = self._ariza_araligi()


class _Personel:
    def __init__(self, salon: "_Salon", rol: str, k: int, tezgahlar: list[int]):
        self.s, self.rol, self.k = salon, rol, k
        p, env = salon.p, salon.env
        self.yedek = rol == "yedek"
        self.ad = {"halfe": "H", "telci": "TL", "yedek": "Y"}[rol] + f"{k + 1:02d}"
        self.tezgahlar = list(tezgahlar)
        self.isler = {(i, rol) for i in tezgahlar}
        self.konum = float(np.mean(tezgahlar)) if tezgahlar else (p.tezgah_sayisi - 1) / 2
        self.kayit = Kaydedici(env, p.isinma_dk, PERSONEL_DURUMLARI, "gozetim", self.ad, salon.cizelge)
        self.r = _akis(salon.seed, 10 + ROLLER.index(rol) if rol in ROLLER else 19, k)
        self.mola_kuyrugu: list[float] = []
        self.kisisel_bekliyor = 0
        self.molada = False
        self.bosta = False
        self._uyari = env.event()
        self.is_sayisi = 0
        self.son_dinlenme = 0.0                       # son mola ya da vardiya başı
        d = dict(p.deneyim)
        self.deneyimli = self.ad not in d
        self.tekrar: dict[str, int] = {}
        self.baslangic_tekrar = int(d.get(self.ad, 0))
        env.process(self.calis())
        if not self.yedek:
            env.process(self.mola_takvimi())
            env.process(self.kisisel_ihtiyac())

    def yorgunluk_carpani(self) -> float:
        p, now = self.s.p, self.s.env.now
        vardiya_bas = (now // p.vardiya_dk) * p.vardiya_dk
        saat = (now - max(self.son_dinlenme, vardiya_bas)) / 60
        f = min(p.yorgunluk_orani * saat, p.yorgunluk_tavan)
        if p.yorgunluk_gece_ek and int(now // p.vardiya_dk) % 3 == 2:
            f += p.yorgunluk_gece_ek
        return 1.0 + max(0.0, f)

    def ogrenme_carpani(self, tur: str) -> float:
        """Wright öğrenme eğrisi; deneyimli personelde 1."""
        if self.deneyimli:
            return 1.0
        p = self.s.p
        n = self.baslangic_tekrar + self.tekrar.get(tur, 0) + 1
        b = np.log2(p.ogrenme_orani)
        return max(1.0, (n / p.ogrenme_standart_tekrar) ** b)

    def uyandir(self) -> None:
        if self.bosta and not self._uyari.triggered:
            self._uyari.succeed()

    def sorumlu(self) -> set:
        kume = set(self.isler)
        for o in self.s.personel:
            if o is not self and o.molada and self in self.s.kapsayanlar(o):
                kume |= o.isler
        return kume

    def mola_ofseti(self, sure: float) -> float:
        """Ayrı ayrı molada kişiler dalgalara bölünür; aynı tezgâhın halfesi ile telcisi farklı dalgadadır."""
        p = self.s.p
        if p.mola_zamani != "ayri":
            return 0.0
        dalga = max(2, p.mola_dalga_sayisi)
        kaydir = dalga // 2 if self.rol == "telci" else 0
        return ((self.k + kaydir) % dalga) * sure

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
                for k in s.kapsayanlar(self):
                    k.uyandir()
                yield env.timeout(sure)
                self.molada = False
                self.son_dinlenme = env.now
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
            is_.personel, is_.baslama_t = self.ad, env.now
            yorgunluk, ogrenme = self.yorgunluk_carpani(), self.ogrenme_carpani(is_.tur)
            is_.basladi.succeed()
            self.kayit.durum(is_.tur)
            yield env.timeout(is_.sure * yorgunluk * ogrenme)
            is_.bitti.succeed()
            self.tekrar[is_.tur] = self.tekrar.get(is_.tur, 0) + 1
            if env.now >= p.isinma_dk:
                self.is_sayisi += 1
                s.isler.append((is_.tezgah.ad, is_.tur, is_.rol, is_.talep_t, is_.baslama_t, env.now,
                                self.ad, self.rol, is_.durdurur, yorgunluk, ogrenme))


class _Salon:
    def __init__(self, p: HaliParam, seed: int):
        if p.mola_zamani not in ("toplu", "ayri"):
            raise ValueError("mola_zamani: toplu | ayri")
        if p.mola_kapsama not in ("yok", "komsu", "capraz", "yedek"):
            raise ValueError("mola_kapsama: yok | komsu | capraz | yedek")
        if p.secim_kurali not in ("fifo", "en_yakin", "oncelikli"):
            raise ValueError("secim_kurali: fifo | en_yakin | oncelikli")
        if set(dict(p.is_rolleri).values()) - set(ROLLER):
            raise ValueError(f"is_rolleri yalnızca {ROLLER} rollerini kullanabilir")
        self.p, self.seed = p, seed
        self.env = simpy.Environment()
        self.cizelge: list = []
        self.isler: list = []
        self.talepler: list[Is] = []
        self.teknisyen = simpy.Resource(self.env, p.teknisyen_sayisi)
        self.ekip = simpy.Resource(self.env, p.cozgu_ekibi)
        self.renk_ekibi = simpy.Resource(self.env, max(1, p.renk_ekibi))
        n = p.tezgah_sayisi
        self.personel: list[_Personel] = []
        self.rol_listesi: dict[str, list[_Personel]] = {}
        for rol in ROLLER:
            m = p.halfe_basina_tezgah if rol == "halfe" else p.telci_basina_tezgah
            kisiler = [_Personel(self, rol, k, list(range(k * m, min(n, (k + 1) * m))))
                       for k in range(p.kisi_sayisi(rol))]
            self.rol_listesi[rol] = kisiler
            self.personel += kisiler
        self.yedekler = [_Personel(self, "yedek", k, []) for k in range(p.yedek_sayisi)] \
            if p.mola_kapsama == "yedek" else []
        self.personel += self.yedekler
        self._kapsama = {o: self._kapsayanlari_bul(o) for o in self.personel}
        self.tezgahlar = [_Tezgah(self, i) for i in range(n)]

    def _kapsayanlari_bul(self, o: _Personel) -> list[_Personel]:
        d = self.p.mola_kapsama
        if o.yedek or d == "yok":
            return []
        if d == "yedek":
            return list(self.yedekler)
        if d == "komsu":
            liste = self.rol_listesi[o.rol]
            return [x for x in (liste[o.k - 1] if o.k > 0 else None, liste[o.k + 1] if o.k + 1 < len(liste) else None)
                    if x is not None]
        diger = "telci" if o.rol == "halfe" else "halfe"       # capraz
        ilk = o.tezgahlar[0]
        return [x for x in self.rol_listesi[diger] if ilk in x.tezgahlar][:1]

    def kapsayanlar(self, o: _Personel) -> list[_Personel]:
        return self._kapsama[o]

    def _alabilir(self, o: _Personel, t: Is, kume: set) -> bool:
        if (t.tezgah.i, t.rol) in kume:
            return True
        p = self.p
        return (p.telci_yardim and o.rol == "telci" and t.rol == "halfe" and t.tur in p.yardim_isleri
                and (t.tezgah.i, "telci") in kume)

    def talep_ekle(self, is_: Is) -> None:
        self.talepler.append(is_)
        for o in self.personel:
            if o.bosta and self._alabilir(o, is_, o.sorumlu()):
                o.uyandir()

    def is_sec(self, o: _Personel) -> Is | None:
        kume = o.sorumlu()
        aday = [t for t in self.talepler if self._alabilir(o, t, kume)]
        if not aday:
            return None
        kural = self.p.secim_kurali
        if kural == "en_yakin":
            return min(aday, key=lambda t: (abs(o.konum - t.tezgah.konum), t.talep_t))
        if kural == "oncelikli":
            return min(aday, key=lambda t: (not t.durdurur, t.talep_t))
        return aday[0]


@dataclass
class HaliSonuc:
    ozet: dict
    tezgah: pd.DataFrame
    personel: pd.DataFrame
    cizelge: pd.DataFrame = field(repr=False)
    isler: pd.DataFrame = field(repr=False)
    vardiya_uretim: pd.DataFrame = field(default=None, repr=False)   # tezgah, vardiya, m2

    @property
    def operator(self) -> pd.DataFrame:     # geriye dönük ad
        return self.personel


def kos(p: HaliParam, seed: int) -> HaliSonuc:
    s = _Salon(p, seed)
    s.env.run(until=p.bitis_dk)
    for t in s.tezgahlar:
        t.kapat()
    olcum_saat = p.sure_gun * 24
    vardiya_sayisi = olcum_saat * 60 / p.vardiya_dk

    tz = []
    for t in s.tezgahlar:
        r = t.kayit.oranlar()
        tz.append({"tezgah": t.ad, "marka": t.tanim.marka, "tarak": t.tanim.tarak, **r,
                   "m2": t.m2, "m2_vardiya": t.m2 / vardiya_sayisi,
                   "ort_devir": t.devir_dk / t.dokuma_dk if t.dokuma_dk else 0.0,
                   "top": t.top_sayisi, "kopus": t.kopus_sayisi, "renk_degisimi_sayisi": t.renk_sayisi,
                   "desen_sayisi": t.desen_sayisi, "ariza_sayisi": t.ariza_sayisi, "cozgu_sayisi": t.cozgu_sayisi})
    tz = pd.DataFrame(tz)
    pr = []
    for o in s.personel:
        r = o.kayit.oranlar()
        verimli = sum(r[d] for d in PERSONEL_DURUMLARI if PERSONEL_SINIF[d] == "Verimli iş")
        pr.append({"personel": o.ad, "rol": o.rol, **r, "verimli_is": verimli, "doluluk": verimli + r["yurume"],
                   "is_sayisi": o.is_sayisi, "tezgah_sayisi": len(o.tezgahlar)})
    pr = pd.DataFrame(pr)
    isler = pd.DataFrame(s.isler, columns=["tezgah", "tur", "rol", "talep", "baslama", "bitis", "personel",
                                           "personel_rol", "durdurur", "yorgunluk", "ogrenme"])
    isler["vardiya_saati"] = ((isler["baslama"] % p.vardiya_dk) // 60).astype(int) + 1
    isler["bekleme"] = isler["baslama"] - isler["talep"]
    durduran = isler[isler["durdurur"]]
    toplam_m2 = float(tz["m2"].sum())
    dokuma_saat = sum(t.dokuma_dk for t in s.tezgahlar) / 60

    ozet = {
        "m2_vardiya": toplam_m2 / vardiya_sayisi,
        "m2_vardiya_tezgah": toplam_m2 / vardiya_sayisi / p.tezgah_sayisi,
        "m2_gun": toplam_m2 / p.sure_gun,
        "tezgah_verimi": float(tz["dokuma"].mean()),
        "girisim": float(tz["personel_bekleme"].mean()),
        "m2_personel_saat": toplam_m2 / (len(pr) * olcum_saat),
        "ort_bekleme_dk": float(durduran["bekleme"].mean()) if len(durduran) else 0.0,
        "kopus_dokuma_saati": float(tz["kopus"].sum() / dokuma_saat) if dokuma_saat else 0.0,
        "top_vardiya": float(tz["top"].sum() / vardiya_sayisi),
        "ort_yorgunluk": float(isler["yorgunluk"].mean()) if len(isler) else 1.0,
        "ort_ogrenme": float(isler["ogrenme"].mean()) if len(isler) else 1.0,
        "personel_sayisi": len(pr),
        "halfe_sayisi": int((pr["rol"] == "halfe").sum()),
        "telci_sayisi": int((pr["rol"] == "telci").sum()),
    }
    for rol, onek in ROL_ONEK.items():
        g = pr[pr["rol"] == rol]
        if len(g):
            ozet[f"{rol}_doluluk"] = float(g["doluluk"].mean())
            for d in PERSONEL_DURUMLARI:
                ozet[f"{onek}:{d}"] = float(g[d].mean())
    for d in TEZGAH_DURUMLARI:
        ozet[f"tz:{d}"] = float(tz[d].mean())
    cizelge = pd.DataFrame(s.cizelge, columns=["kaynak", "bas", "bit", "durum"])
    n_v = int(round(vardiya_sayisi))
    vu = pd.DataFrame([(t.ad, v + 1, t.m2_vardiyalar.get(v, 0.0)) for t in s.tezgahlar for v in range(n_v)],
                      columns=["tezgah", "vardiya", "m2"])
    return HaliSonuc(ozet, tz, pr, cizelge, isler, vu)

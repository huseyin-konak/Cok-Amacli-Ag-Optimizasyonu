"""
Algoritma karşılaştırması.

Aynı kaynak-hedef talebi için Q-Learning, Genetik Algoritma, Tabu Search ve
Simulated Annealing çalıştırılır; sonuçlar kesin optimum (Dijkstra) ile karşılaştırılır.

Kullanım:
    python calistir.py              # 13. talep (indeks 12) için ayrıntılı karşılaştırma
    python calistir.py --talep 0    # başka bir talep
    python calistir.py --tum        # tüm talepler için özet tablo
    python calistir.py --tum --grafik  # özet + algoritma_karsilastirma.png
"""
import argparse
import math
import random
import time

import numpy as np

import network_model
import q_learning
import tabusearch
from genetik_algoritma import genetic_algorithm
from simulated_annealing import SimulatedAnnealing

# Q-Learning parametreleri. EPSILON > 1: ilk ~800 bölüm tamamen rastgele keşif.
EPSILON = 5.0
EPSILON_MIN = 0.1
EPSILON_DECAY = 0.998
MAX_STEPS = 50
EPISODE = 1500
ALPHA = 0.9
GAMMA = 0.9


def algoritmalari_calistir(ag, talep):
    """Her algoritmanın bulduğu yolu ve süresini {ad: (yol, süre_sn)} olarak döndürür."""
    S, D, bw = talep['kaynak'], talep['hedef'], talep['miktar']
    sonuc = {}

    t = time.time()
    sonuc['Dijkstra (optimum)'] = (ag.optimum_yol(S, D, bw), time.time() - t)

    t = time.time()
    env = q_learning.NetworkRoutingEnv(ag, S, D, bw)
    q_table = q_learning.q_learning_egit(env, EPISODE, EPSILON, EPSILON_MIN, EPSILON_DECAY,
                                         ALPHA, GAMMA, MAX_STEPS)
    sonuc['Q-Learning'] = (q_learning.q_learning_calistir(env, q_table, MAX_STEPS), time.time() - t)

    t = time.time()
    yol, _ = genetic_algorithm(ag, S, D, bw, pop_size=50, generations=100)
    sonuc['Genetik Algoritma'] = (yol, time.time() - t)

    t = time.time()
    sonuc['Tabu Search'] = (tabusearch.tabu_search(ag, S, D, bw), time.time() - t)

    t = time.time()
    yol, _, _ = SimulatedAnnealing(ag, S, D, bw).optimize()
    sonuc['Simulated Annealing'] = (yol or None, time.time() - t)
    return sonuc


def tek_talep(ag, indeks):
    talep = ag.talep_listesini_getir()[indeks]
    bw = talep['miktar']
    print(f"\nTalep #{indeks}: {talep['kaynak']} -> {talep['hedef']}  (istenen bant genişliği {bw:.0f} Mbps)\n")

    sonuc = algoritmalari_calistir(ag, talep)
    optimum = ag.yol_maliyeti_hesapla(sonuc['Dijkstra (optimum)'][0], bw)[0]

    print(f"\n{'Algoritma':<22}{'Fitness':>9}{'Fark':>9}{'Gecikme':>11}{'Güvenilirlik':>14}{'Kaynak':>9}{'Süre':>9}  Yol")
    for ad, (yol, sure) in sonuc.items():
        if not yol:
            print(f"{ad:<22}{'-':>9}{'-':>9}{'-':>11}{'-':>14}{'-':>9}{sure:>8.2f}s  bulunamadı")
            continue
        skor, gecikme, guv, kaynak = ag.yol_maliyeti_hesapla(yol, bw)
        fark = (skor - optimum) / optimum * 100
        print(f"{ad:<22}{skor:>9.4f}{fark:>8.1f}%{gecikme:>9.2f}ms{math.exp(-guv) * 100:>13.2f}%"
              f"{kaynak:>9.2f}{sure:>8.2f}s  {yol}")
    print("\nFark: kesin optimuma göre fitness farkı (düşük fitness = daha iyi yol).")


def tum_talepler(ag):
    talepler = ag.talep_listesini_getir()
    farklar, bulunan, sureler = {}, {}, {}
    for i, talep in enumerate(talepler):
        print(f"\n=== Talep {i + 1}/{len(talepler)} ===")
        sonuc = algoritmalari_calistir(ag, talep)
        optimum = ag.yol_maliyeti_hesapla(sonuc['Dijkstra (optimum)'][0], talep['miktar'])[0]
        for ad, (yol, sure) in sonuc.items():
            sureler.setdefault(ad, []).append(sure)
            if yol:
                skor = ag.yol_maliyeti_hesapla(yol, talep['miktar'])[0]
                farklar.setdefault(ad, []).append((skor - optimum) / optimum * 100)
                bulunan[ad] = bulunan.get(ad, 0) + 1

    print(f"\n{'Algoritma':<22}{'Geçerli yol':>13}{'Ort. fark':>11}{'Optimum bulundu':>17}{'Ort. süre':>11}")
    ozet = {}
    for ad in sureler:
        f = farklar.get(ad, [])
        optimum_sayisi = sum(1 for x in f if x < 1e-9)
        ozet[ad] = (optimum_sayisi, float(np.mean(f)) if f else float('nan'), float(np.mean(sureler[ad])))
        ort_fark = f"%{np.mean(f):.2f}" if f else "-"
        print(f"{ad:<22}{bulunan.get(ad, 0):>8}/{len(talepler):<4}{ort_fark:>11}"
              f"{optimum_sayisi:>11}/{len(talepler):<5}{np.mean(sureler[ad]):>10.2f}s")
    return ozet, len(talepler)


def grafik_kaydet(ozet, talep_sayisi, dosya="algoritma_karsilastirma.png"):
    """Tüm talepler özetini iki panelli çubuk grafik olarak kaydeder."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    adlar = [ad for ad in ozet if not ad.startswith("Dijkstra")]
    renk = "#3b6ea8"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

    sayilar = [ozet[ad][0] for ad in adlar]
    ax1.barh(adlar, sayilar, color=renk)
    ax1.set_xlim(0, talep_sayisi)
    ax1.set_title(f"Kesin optimumu bulduğu talep sayısı (toplam {talep_sayisi})")
    for y, v in enumerate(sayilar):
        ax1.text(v - 0.4, y, f"{v}/{talep_sayisi}", va="center", ha="right", color="white", fontweight="bold")

    farklar = [ozet[ad][1] for ad in adlar]
    ax2.barh(adlar, farklar, color=renk)
    ax2.set_title("Optimuma ortalama uzaklık (%) — düşük daha iyi")
    for y, v in enumerate(farklar):
        ax2.text(v + 0.03, y, f"%{v:.2f}", va="center")
    ax2.set_xlim(0, max(farklar + [1.0]) * 1.3)
    ax2.set_yticklabels([])

    for ax in (ax1, ax2):
        ax.invert_yaxis()
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", alpha=0.3)
    fig.suptitle("Çok amaçlı yönlendirme — sezgisel algoritmalar ve kesin optimum (Dijkstra)", fontsize=13)
    fig.tight_layout()
    fig.savefig(dosya, dpi=150)
    print(f"\n📊 Grafik kaydedildi: {dosya}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Çok amaçlı yönlendirme algoritmalarını karşılaştırır.")
    parser.add_argument("--talep", type=int, default=12, help="talep indeksi (0'dan başlar)")
    parser.add_argument("--tum", action="store_true", help="tüm talepler için özet tablo")
    parser.add_argument("--grafik", action="store_true", help="--tum ile birlikte: özet grafiğini kaydet")
    parser.add_argument("--seed", type=int, default=42, help="tekrarlanabilir sonuç için rastgelelik tohumu")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    ag = network_model.AgOrtami()
    ag.verileri_yukle_ve_agi_kur()
    if args.tum:
        ozet, talep_sayisi = tum_talepler(ag)
        if args.grafik:
            grafik_kaydet(ozet, talep_sayisi)
    else:
        tek_talep(ag, args.talep)

"""
Ağ modeli: CSV verilerinden topolojiyi kurar ve bir yolun çok amaçlı maliyetini hesaplar.

Her yol için üç maliyet hesaplanır ve ağırlıklı toplamla tek bir uygunluk (fitness)
değerine indirgenir (düşük = iyi):
  - Gecikme      : bağlantı gecikmeleri + ara düğümlerin işlem süreleri (ms)
  - Güvenilirlik : -log(güvenilirlik) toplamı (çarpımsal olasılık toplanabilir maliyete çevrilir)
  - Kaynak       : her bağlantı için 1000 / kapasite (Mbps)
İstenen bant genişliğini karşılamayan bir bağlantı içeren yol geçersizdir (sonsuz maliyet).
"""
import math
import os

import networkx as nx
import pandas as pd

VERI_KLASORU = os.path.dirname(os.path.abspath(__file__))
DUGUM_DOSYASI = os.path.join(VERI_KLASORU, "BSM307_317_Guz2025_TermProject_NodeData.csv")
KENAR_DOSYASI = os.path.join(VERI_KLASORU, "BSM307_317_Guz2025_TermProject_EdgeData.csv")
TALEP_DOSYASI = os.path.join(VERI_KLASORU, "BSM307_317_Guz2025_TermProject_DemandData.csv")

# Amaç ağırlıkları (toplamları 1). Varsayılan: üç amaca yaklaşık eşit önem.
W_GECIKME = 0.33
W_GUVENILIRLIK = 0.33
W_KAYNAK = 0.34


class AgOrtami:
    """CSV dosyalarından ağ topolojisini kurar ve yol maliyetlerini hesaplar."""

    def __init__(self):
        self.graf = nx.Graph()
        self.w_gecikme = W_GECIKME
        self.w_guvenilirlik = W_GUVENILIRLIK
        self.w_kaynak = W_KAYNAK

    def verileri_yukle_ve_agi_kur(self):
        """Düğüm ve bağlantı verilerini okuyup NetworkX grafını oluşturur."""
        print("📂 Veriler okunuyor ve ağ oluşturuluyor...")

        # CSV'lerde ayraç ';', ondalık ayracı ',' kullanılır
        try:
            dugum_verisi = pd.read_csv(DUGUM_DOSYASI, sep=';', decimal=',')
        except FileNotFoundError:
            print(f"❌ HATA: '{DUGUM_DOSYASI}' dosyası bulunamadı!")
            return None

        for _, satir in dugum_verisi.iterrows():
            dugum_id = int(satir['node_id'])
            guvenilirlik = float(satir['r_node'])
            self.graf.add_node(
                dugum_id,
                islem_suresi=float(satir['s_ms']),         # düğümdeki işlem süresi (ms)
                guvenilirlik=guvenilirlik,                  # 0-1 arası
                guv_maliyeti=-math.log(guvenilirlik),
            )
        print(f"✅ {len(dugum_verisi)} adet düğüm yüklendi.")

        try:
            kenar_verisi = pd.read_csv(KENAR_DOSYASI, sep=';', decimal=',')
        except FileNotFoundError:
            print(f"❌ HATA: '{KENAR_DOSYASI}' dosyası bulunamadı!")
            return None

        for _, satir in kenar_verisi.iterrows():
            kapasite = float(satir['capacity_mbps'])
            guvenilirlik = float(satir['r_link'])
            self.graf.add_edge(
                int(satir['src']), int(satir['dst']),
                bant_genisligi=kapasite,                    # Mbps
                gecikme=float(satir['delay_ms']),           # ms
                guvenilirlik=guvenilirlik,
                kaynak_maliyeti=1000.0 / kapasite,          # yüksek kapasite = düşük maliyet
                guv_maliyeti=-math.log(guvenilirlik),
            )
        print(f"✅ {len(kenar_verisi)} adet bağlantı yüklendi.")

        if nx.is_connected(self.graf):
            print("Bilgi: Ağ bağlı; tüm düğümler birbirine erişebilir.")
        else:
            print("UYARI: Ağ bağlı değil; bazı düğümler arasında yol yok.")
        return self.graf

    def talep_listesini_getir(self):
        """Talep dosyasındaki (kaynak, hedef, istenen bant genişliği) kayıtlarını döndürür."""
        try:
            talep_verisi = pd.read_csv(TALEP_DOSYASI, sep=';', decimal=',')
        except FileNotFoundError:
            print(f"❌ HATA: '{TALEP_DOSYASI}' dosyası bulunamadı.")
            return []
        return [
            {'kaynak': int(s['src']), 'hedef': int(s['dst']), 'miktar': float(s['demand_mbps'])}
            for _, s in talep_verisi.iterrows()
        ]

    def filtrele(self, istenen_bw):
        """Yalnızca istenen bant genişliğini karşılayan bağlantılardan oluşan alt graf (görünüm)."""
        gecerli = [(u, v) for u, v, d in self.graf.edges(data=True) if d['bant_genisligi'] >= istenen_bw]
        return self.graf.edge_subgraph(gecerli)

    def yol_maliyeti_hesapla(self, yol, istenen_bw=0):
        """
        Yolun ağırlıklı toplam maliyetini ve bileşenlerini döndürür:
        (fitness, toplam_gecikme_ms, guvenilirlik_maliyeti, kaynak_maliyeti)

        Yol geçersizse (2 düğümden kısa, bağlantı yok ya da kapasite yetersiz) maliyet sonsuzdur.
        Güvenilirlik yüzdesine geri dönmek için: exp(-guvenilirlik_maliyeti) * 100
        """
        sonsuz = float('inf')
        if not yol or len(yol) < 2:
            return sonsuz, sonsuz, sonsuz, sonsuz

        toplam_gecikme = 0.0
        toplam_guv_maliyeti = 0.0
        toplam_kaynak_maliyeti = 0.0

        for u, v in zip(yol, yol[1:]):
            if not self.graf.has_edge(u, v):
                return sonsuz, sonsuz, sonsuz, sonsuz
            baglanti = self.graf[u][v]
            if baglanti['bant_genisligi'] < istenen_bw:
                return sonsuz, sonsuz, sonsuz, sonsuz
            toplam_gecikme += baglanti['gecikme']
            toplam_guv_maliyeti += baglanti['guv_maliyeti']
            toplam_kaynak_maliyeti += baglanti['kaynak_maliyeti']

        # Her düğüm güvenilirliği etkiler; işlem süresi yalnızca ara düğümlerde eklenir
        for dugum in yol:
            toplam_guv_maliyeti += self.graf.nodes[dugum]['guv_maliyeti']
        for dugum in yol[1:-1]:
            toplam_gecikme += self.graf.nodes[dugum]['islem_suresi']

        genel_skor = (self.w_gecikme * toplam_gecikme
                      + self.w_guvenilirlik * toplam_guv_maliyeti
                      + self.w_kaynak * toplam_kaynak_maliyeti)
        return genel_skor, toplam_gecikme, toplam_guv_maliyeti, toplam_kaynak_maliyeti

    def optimum_yol(self, kaynak, hedef, istenen_bw):
        """
        Referans çözüm: kesin optimum yol.

        Ağırlıklı toplam maliyet bağlantılar üzerinde toplanabilir olduğundan, her bağlantıya
        (bağlantı maliyeti + girilen düğümün maliyeti) ağırlığı verilip bant genişliği
        filtrelenmiş grafta Dijkstra çalıştırılırsa global optimum bulunur. Sezgisel
        algoritmaların optimuma uzaklığı bu çözümle ölçülür.
        """
        graf = self.filtrele(istenen_bw)

        def agirlik(u, v, d):
            gecikme = d['gecikme'] + (graf.nodes[v]['islem_suresi'] if v != hedef else 0.0)
            guv = d['guv_maliyeti'] + graf.nodes[v]['guv_maliyeti']
            return self.w_gecikme * gecikme + self.w_guvenilirlik * guv + self.w_kaynak * d['kaynak_maliyeti']

        try:
            return nx.dijkstra_path(graf, kaynak, hedef, weight=agirlik)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None


if __name__ == "__main__":
    ag = AgOrtami()
    ag.verileri_yukle_ve_agi_kur()
    talep = ag.talep_listesini_getir()[0]
    yol = ag.optimum_yol(talep['kaynak'], talep['hedef'], talep['miktar'])
    skor, gecikme, guv, kaynak = ag.yol_maliyeti_hesapla(yol, talep['miktar'])
    print(f"\nTalep: {talep['kaynak']} -> {talep['hedef']} ({talep['miktar']} Mbps)")
    print(f"Optimum yol   : {yol}")
    print(f"Fitness       : {skor:.4f}")
    print(f"Gecikme       : {gecikme:.2f} ms")
    print(f"Güvenilirlik  : %{math.exp(-guv) * 100:.2f}")
    print(f"Kaynak maliyeti: {kaynak:.2f}")

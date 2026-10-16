"""
Tabu Search ile yönlendirme.

Başlangıç çözümü: bant genişliği filtrelenmiş grafta en az atlamalı yol (her zaman geçerli).
Komşuluk: yoldaki bir ara düğümü, önceki ve sonraki düğümün ortak komşusuyla değiştirmek.
Son ziyaret edilen çözümler tabu listesinde tutulur; tabu bir hamle yalnızca şimdiye
kadarki en iyi çözümden daha iyiyse kabul edilir (aspiration kriteri).
"""
import networkx as nx


def komsu_yollar_uret(graf, mevcut_yol):
    """Bir ara düğümü değiştirerek elde edilen tüm komşu yolları üretir."""
    komsular = []
    for i in range(1, len(mevcut_yol) - 1):
        onceki, sonraki = mevcut_yol[i - 1], mevcut_yol[i + 1]
        alternatifler = set(graf.neighbors(onceki)) & set(graf.neighbors(sonraki))
        for dugum in alternatifler:
            if dugum not in mevcut_yol:
                komsular.append(mevcut_yol[:i] + [dugum] + mevcut_yol[i + 1:])
    return komsular


def tabu_search(ag_objesi, kaynak, hedef, istenen_bw, iterasyon=50, tabu_boyutu=10):
    """En iyi bulunan yolu döndürür; kaynak ile hedef arasında geçerli yol yoksa None."""
    graf = ag_objesi.filtrele(istenen_bw)
    try:
        mevcut_yol = nx.shortest_path(graf, kaynak, hedef)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    en_iyi_yol = mevcut_yol
    en_iyi_skor = ag_objesi.yol_maliyeti_hesapla(mevcut_yol, istenen_bw)[0]
    tabu_listesi = [mevcut_yol]

    for _ in range(iterasyon):
        en_iyi_komsu, en_iyi_komsu_skor = None, float('inf')

        for yol in komsu_yollar_uret(graf, mevcut_yol):
            skor = ag_objesi.yol_maliyeti_hesapla(yol, istenen_bw)[0]
            if yol in tabu_listesi and skor >= en_iyi_skor:
                continue                           # tabu ve aspiration'ı geçmiyor
            if skor < en_iyi_komsu_skor:
                en_iyi_komsu, en_iyi_komsu_skor = yol, skor

        if en_iyi_komsu is None:
            break

        # Komşu daha kötü olsa bile ona geçilir: yerel minimumdan çıkmayı sağlar
        mevcut_yol = en_iyi_komsu
        tabu_listesi.append(mevcut_yol)
        if len(tabu_listesi) > tabu_boyutu:
            tabu_listesi.pop(0)

        if en_iyi_komsu_skor < en_iyi_skor:
            en_iyi_yol, en_iyi_skor = en_iyi_komsu, en_iyi_komsu_skor

    return en_iyi_yol
